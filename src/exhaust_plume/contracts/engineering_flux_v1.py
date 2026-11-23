"""Versioned request/result contracts for conservative flux-section queries."""

from __future__ import annotations

from math import isclose, isfinite, sqrt
from typing import Any, Literal

from pydantic import Field, StrictBool, field_validator, model_validator

from exhaust_plume.contracts.capability import ENGINEERING_FLUX_SECTION_CAPABILITY
from exhaust_plume.contracts.common_v1 import (
  ApiModel,
  ResultMetadata,
  SampleStatus,
  SampleStatusCode,
  Vector3,
  canonical_digest,
)
from exhaust_plume.contracts.handoff_v1 import PlumeFluxSectionV1
from exhaust_plume.contracts._validation import contains_boolean


class EngineeringFluxSectionRequest(ApiModel):
  """Query conservative sections at centerline arc-length stations.

  Arc length is measured from the caller-named source handoff centerline
  reference. Providers return their native station state unless interpolation
  is explicitly enabled. The requested frame and source reference are part of
  the query identity.
  """

  output_frame_id: str = Field(min_length=1)
  centerline_reference_id: str = Field(min_length=1)
  centerline_arclength_m: tuple[float, ...] = Field(min_length=1)
  allow_interpolation: StrictBool = False
  allow_partial_results: StrictBool = False

  @field_validator('centerline_arclength_m', mode='before')
  @classmethod
  def reject_boolean_stations(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('centerline arc-length stations must not be booleans')
    return value
  ####

  @field_validator('centerline_arclength_m')
  @classmethod
  def validate_stations(cls, values: tuple[float, ...]) -> tuple[float, ...]:
    if any(not isfinite(value) or value < 0.0 for value in values):
      raise ValueError('centerline arc-length stations must be finite and nonnegative')
    if any(later <= earlier for earlier, later in zip(values, values[1:])):
      raise ValueError('centerline arc-length stations must be strictly increasing')
    return values
  ####
####


class EngineeringFluxSectionSampleV1(ApiModel):
  """One source-bound section sample or one explicit failed sample."""

  station_arclength_m: float = Field(ge=0.0)
  centerline_position_m: Vector3 | None = None
  centerline_tangent: Vector3 | None = None
  sampling_method: Literal['native', 'provider-interpolated'] | None = None
  status: SampleStatus
  section: PlumeFluxSectionV1 | None = None

  @field_validator(
    'station_arclength_m',
    'centerline_position_m',
    'centerline_tangent',
    mode='before',
  )
  @classmethod
  def reject_boolean_geometry(cls, value: Any) -> Any:
    if contains_boolean(value):
      raise ValueError('flux-section station and geometry values must not be booleans')
    return value
  ####

  @field_validator('station_arclength_m')
  @classmethod
  def validate_station(cls, value: float) -> float:
    if not isfinite(value):
      raise ValueError('station_arclength_m must be finite')
    return value
  ####

  @model_validator(mode='after')
  def validate_sample(self) -> 'EngineeringFluxSectionSampleV1':
    if self.status.code is not SampleStatusCode.OK:
      if any(value is not None for value in (
          self.centerline_position_m,
          self.centerline_tangent,
          self.sampling_method,
          self.section,
      )):
        raise ValueError('a failed flux-section sample must not carry geometry or flux values')
      return self
    ####
    if (
        self.centerline_position_m is None
        or self.centerline_tangent is None
        or self.sampling_method is None
        or self.section is None
    ):
      raise ValueError('an OK flux-section sample requires geometry, sampling method, and section data')
    if any(not isfinite(value) for value in (*self.centerline_position_m, *self.centerline_tangent)):
      raise ValueError('flux-section centerline geometry must be finite')
    tangent_norm = sqrt(sum(value * value for value in self.centerline_tangent))
    if abs(tangent_norm - 1.0) > 1.0e-8:
      raise ValueError('centerline_tangent must be a unit vector')
    if any(
      not isclose(center, section_center, rel_tol=0.0, abs_tol=1.0e-12)
      for center, section_center in zip(
        self.centerline_position_m,
        self.section.center_m,
        strict=True,
      )
    ):
      raise ValueError('centerline position must match the flux section center')
    if any(
      not isclose(tangent, section_normal, rel_tol=0.0, abs_tol=1.0e-8)
      for tangent, section_normal in zip(
        self.centerline_tangent,
        self.section.normal,
        strict=True,
      )
    ):
      raise ValueError('centerline tangent must match the flux section normal')
    if not self.section.applicability.supported:
      raise ValueError('an OK flux-section sample must be inside provider applicability')
    return self
  ####
####


class EngineeringFluxSectionResult(ApiModel):
  """Ordered conservative sections bound to one exact request and snapshot."""

  metadata: ResultMetadata
  request: EngineeringFluxSectionRequest
  samples: tuple[EngineeringFluxSectionSampleV1, ...] = Field(min_length=1)

  @model_validator(mode='after')
  def validate_result(self) -> 'EngineeringFluxSectionResult':
    if self.metadata.capability != ENGINEERING_FLUX_SECTION_CAPABILITY:
      raise ValueError('flux-section metadata must identify plume.engineering.flux-section@1')
    if self.metadata.output_frame_id != self.request.output_frame_id:
      raise ValueError('flux-section result frame must match the requested output frame')
    if self.metadata.provenance.metadata.get('centerline_reference_id') != self.request.centerline_reference_id:
      raise ValueError('result provenance must identify the requested centerline reference')
    if self.metadata.request_digest_sha256 != canonical_digest(self.request):
      raise ValueError('flux-section result request digest does not match the echoed request')
    stations = tuple(sample.station_arclength_m for sample in self.samples)
    if stations != self.request.centerline_arclength_m:
      raise ValueError('flux-section sample stations must match the request in order')
    if not self.request.allow_partial_results and any(
        sample.status.code is not SampleStatusCode.OK for sample in self.samples
    ):
      raise ValueError('failed flux-section samples require allow_partial_results')
    for sample in self.samples:
      if sample.status.code is not SampleStatusCode.OK:
        continue
      ####
      assert sample.section is not None
      if sample.section.frame.frame_id != self.request.output_frame_id:
        raise ValueError('flux-section sample frame must match the requested output frame')
      if not isclose(
          sample.section.time_s,
          self.metadata.snapshot.time_s,
          rel_tol=0.0,
          abs_tol=1.0e-12,
      ):
        raise ValueError('flux-section sample time must match its exact snapshot time')
      if sample.sampling_method == 'provider-interpolated' and not self.request.allow_interpolation:
        raise ValueError('interpolated flux-section samples require allow_interpolation')
    ####
    return self
  ####
####


__all__ = (
  'EngineeringFluxSectionRequest',
  'EngineeringFluxSectionResult',
  'EngineeringFluxSectionSampleV1',
)
