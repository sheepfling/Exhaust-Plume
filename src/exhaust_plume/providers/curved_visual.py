"""Canonical visual provider for the curved/washed integral plume lane.

The provider adapts an already-solved :class:`CurvedPlumeResult` into the
standard sectioned-tube product at request time.  It intentionally exposes no
signature, ray-transfer, or detector capability: the swept tube is an
engineering visualization envelope, not an optical source field.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from exhaust_plume.api.v1 import (
  GeometryClaim,
  ImmutableProductSnapshot,
  Pose,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  RadiationClaim,
  SessionMetadata,
  SnapshotMetadata,
  TimeModel,
  VISUAL_SECTIONED_TUBE_CAPABILITY,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  canonical_digest,
)
from exhaust_plume.models.plume.curved_plume_closures import CurvedPlumeResult
from exhaust_plume.products.model_visualization import (
  ModelVisualizationLane,
  evaluate_standardized_model_visualization,
  standardize_model_visualization,
)

__all__ = (
  'CurvedIntegralVisualConfiguration',
  'CurvedIntegralVisualDefinition',
  'CurvedIntegralVisualProvider',
  'CurvedIntegralVisualSession',
)


@dataclass(frozen=True, slots=True)
class CurvedIntegralVisualDefinition:
  """A solved curved integral result and the frame of its coordinates."""

  frame_id: str
  result: CurvedPlumeResult

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ProviderConfigurationError('curved visual frame_id must not be empty')
    ####
    if not isinstance(self.result, CurvedPlumeResult):
      raise ProviderConfigurationError('curved visual result must be CurvedPlumeResult')
    ####
    if len(self.result.stations) < 2:
      raise ProviderConfigurationError('curved visual result requires at least two stations')
    ####
    arc_lengths = tuple(station.arc_length_m for station in self.result.stations)
    if any(next_value <= value for value, next_value in zip(arc_lengths, arc_lengths[1:])):
      raise ProviderConfigurationError('curved visual station arc lengths must be strictly increasing')
    ####
  ####

  @property
  def digest(self) -> str:
    """Return a JSON-safe identity for the immutable solved geometry."""

    return canonical_digest({
      'frame_id': self.frame_id,
      'termination': self.result.termination.value,
      'function_evaluations': self.result.function_evaluations,
      'stations': tuple({
        'arc_length_m': station.arc_length_m,
        'position_m': tuple(float(value) for value in station.position_m),
        'radius_m': station.radius_m,
        'temperature_K': station.temperature_K,
        'pressure_Pa': station.pressure_Pa,
        'density_kgpm3': station.density_kgpm3,
        'speed_mps': station.speed_mps,
        'exhaust_mass_fraction': station.exhaust_mass_fraction,
      } for station in self.result.stations),
    })
  ####
####


@dataclass(frozen=True, slots=True)
class CurvedIntegralVisualConfiguration:
  """Claim ceiling and identity for the curved visual provider."""

  provider_id: str = 'plume.visual.curved-integral'
  provider_version: str = '1.0.0'
  geometry_claim: GeometryClaim = GeometryClaim.ENGINEERING_APPROXIMATE
  radiation_claim: RadiationClaim = RadiationClaim.APPEARANCE_ONLY
  time_model: TimeModel = TimeModel.STEADY

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('curved visual provider identity must not be empty')
    ####
    if not isinstance(self.time_model, TimeModel):
      raise ProviderConfigurationError('curved visual time_model must be TimeModel')
    ####
  ####
####


def _descriptor(configuration: CurvedIntegralVisualConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(VISUAL_SECTIONED_TUBE_CAPABILITY,),
    provider_definition_schema_id='plume.visual.curved-integral-definition.v1',
    dynamic_state_schema_id='plume.visual.curved-integral-dynamic-state.v1',
    configuration_schema_id='plume.visual.curved-integral-configuration.v1',
    supported_morphologies=('curved-integral',),
    deterministic=True,
    notes=('curved/washed integral swept-tube visualization only',),
  )
####


class _CurvedIntegralVisualEvaluator:
  def __init__(
      self,
      definition: CurvedIntegralVisualDefinition,
      configuration: CurvedIntegralVisualConfiguration,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
  ####

  def evaluate(
      self,
      request: VisualSectionedTubeRequest,
      snapshot: SnapshotMetadata,
  ) -> VisualSectionedTubeResult:
    if request.output_frame_id != self._definition.frame_id:
      raise ProviderConfigurationError(
        f'curved visual provider supports output frame {self._definition.frame_id!r}, '
        f'not {request.output_frame_id!r}'
      )
    ####
    visualization = standardize_model_visualization(
      self._definition.result,
      lane=ModelVisualizationLane.CURVED_INTEGRAL,
      frame_id=self._definition.frame_id,
      section_count=request.sampling.maximum_section_count,
      maximum_axial_extent_m=request.sampling.maximum_axial_extent_m,
    )
    return evaluate_standardized_model_visualization(
      visualization,
      request,
      snapshot,
      provider_id=self._configuration.provider_id,
      provider_version=self._configuration.provider_version,
      time_model=self._configuration.time_model,
    )
  ####
####


class CurvedIntegralVisualProvider:
  """Expose the curved integral model through the standard visual lifecycle."""

  def __init__(self, configuration: CurvedIntegralVisualConfiguration | None = None) -> None:
    self._configuration = configuration or CurvedIntegralVisualConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: CurvedIntegralVisualDefinition,
      configuration: CurvedIntegralVisualConfiguration | None = None,
  ) -> 'CurvedIntegralVisualSession':
    if not isinstance(definition, CurvedIntegralVisualDefinition):
      raise ProviderConfigurationError('definition must be CurvedIntegralVisualDefinition')
    ####
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return CurvedIntegralVisualSession(self._descriptor, definition, selected_configuration)
  ####
####


class CurvedIntegralVisualSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: CurvedIntegralVisualDefinition,
      configuration: CurvedIntegralVisualConfiguration,
  ) -> None:
    self._descriptor = descriptor
    self._definition = definition
    self._configuration = configuration
    self._closed = False
    configuration_digest = canonical_digest(configuration)
    self._metadata = SessionMetadata(
      session_id=canonical_digest({
        'provider': descriptor.provider_id,
        'version': descriptor.provider_version,
        'definition': definition.digest,
        'configuration': configuration_digest,
      })[:24],
      provider_id=descriptor.provider_id,
      provider_version=descriptor.provider_version,
      configuration_digest_sha256=configuration_digest,
    )
  ####

  @property
  def metadata(self) -> SessionMetadata:
    return self._metadata
  ####

  def create_snapshot(
      self,
      *,
      time_s: float,
      source_pose: Pose,
      dynamic_state: Mapping[str, Any],
      ambient_state: Mapping[str, Any],
  ) -> ImmutableProductSnapshot:
    if self._closed:
      raise ProviderClosedError('curved visual session is closed')
    ####
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    ####
    dynamic_digest = canonical_digest(dynamic_state)
    ambient_digest = canonical_digest(ambient_state)
    provider_digest = canonical_digest({
      'definition': self._definition.digest,
      'configuration': self._configuration,
    })
    snapshot_id = canonical_digest({
      'session': self._metadata.session_id,
      'time_s': time_s,
      'dynamic': dynamic_digest,
      'ambient': ambient_digest,
      'provider': provider_digest,
      'source_pose': source_pose,
    })[:24]
    metadata = SnapshotMetadata(
      snapshot_id=snapshot_id,
      session_id=self._metadata.session_id,
      time_s=time_s,
      source_pose=source_pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=provider_digest,
    )
    return ImmutableProductSnapshot(
      metadata=metadata,
      _evaluators={VISUAL_SECTIONED_TUBE_CAPABILITY: _CurvedIntegralVisualEvaluator(self._definition, self._configuration)},
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
