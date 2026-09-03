"""Bounded homogeneous gray ray-transfer provider.

This provider intentionally serves only a straight sectioned,
calorically independent support with a wavelength-resolved source function and
absorption coefficient table.  It is a physical transfer kernel, not a
thermochemical plume or detector model; signature and FPA products remain
separate capabilities.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping

from exhaust_plume.api.v1 import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  Pose,
  ProductClaims,
  ProductOutsideApplicabilityError,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SessionMetadata,
  SnapshotMetadata,
  SpectralRayTransferRequest,
  SpectralRayTransferResult,
  SPECTRAL_RAY_TRANSFER_CAPABILITY,
  TimeModel,
  canonical_digest,
)
from exhaust_plume.geometry.ray_intervals import SectionedTubeSupport, intersect_sectioned_tube
from exhaust_plume.radiation.gray import HomogeneousSegment, compose_homogeneous_segments

__all__ = (
  'GrayRayTransferConfiguration',
  'GrayRayTransferDefinition',
  'GrayRayTransferProvider',
  'GrayRayTransferSession',
)


def _axis(values: tuple[float, ...], field_name: str) -> tuple[float, ...]:
  normalized = tuple(float(value) for value in values)
  if len(normalized) < 2:
    raise ProviderConfigurationError(f'{field_name} requires at least two values')
  ####
  if not all(isfinite(value) and value > 0.0 for value in normalized):
    raise ProviderConfigurationError(f'{field_name} must be finite and positive')
  ####
  if any(next_value <= value for value, next_value in zip(normalized, normalized[1:])):
    raise ProviderConfigurationError(f'{field_name} must be strictly increasing')
  ####
  return normalized
####


def _spectrum(values: tuple[float, ...], field_name: str) -> tuple[float, ...]:
  normalized = tuple(float(value) for value in values)
  if not normalized or not all(isfinite(value) and value >= 0.0 for value in normalized):
    raise ProviderConfigurationError(f'{field_name} must be finite and nonnegative')
  ####
  return normalized
####


@dataclass(frozen=True, slots=True)
class GrayRayTransferDefinition:
  """Straight sectioned support plus wavelength-node optical properties."""

  frame_id: str
  support: SectionedTubeSupport
  wavelengths_m: tuple[float, ...]
  source_function_w_sr_m: tuple[float, ...]
  absorption_coefficient_per_m: tuple[float, ...]
  asset_id: str = 'gray-ray-transfer-definition'
  asset_sha256: str | None = None
  allow_curved_support: bool = False

  def __post_init__(self) -> None:
    if not self.frame_id or not self.asset_id:
      raise ProviderConfigurationError('gray definition frame_id and asset_id must not be empty')
    ####
    if not isinstance(self.support, SectionedTubeSupport):
      raise ProviderConfigurationError('support must be SectionedTubeSupport')
    ####
    if self.support.frame_id != self.frame_id:
      raise ProviderConfigurationError('support frame_id must match the definition frame_id')
    ####
    ####
    wavelengths = _axis(self.wavelengths_m, 'wavelengths_m')
    source = _spectrum(self.source_function_w_sr_m, 'source_function_w_sr_m')
    absorption = _spectrum(self.absorption_coefficient_per_m, 'absorption_coefficient_per_m')
    if len(wavelengths) != len(source) or len(wavelengths) != len(absorption):
      raise ProviderConfigurationError('optical property arrays must match wavelengths_m')
    ####
    if self.asset_sha256 is not None and (
        len(self.asset_sha256) != 64
        or any(character not in '0123456789abcdefABCDEF' for character in self.asset_sha256)
    ):
      raise ProviderConfigurationError('asset_sha256 must be a 64-character hexadecimal digest')
    ####
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'source_function_w_sr_m', source)
    object.__setattr__(self, 'absorption_coefficient_per_m', absorption)
    object.__setattr__(self, 'asset_sha256', self.asset_sha256.lower() if self.asset_sha256 else None)
    if not isinstance(self.allow_curved_support, bool):
      raise ProviderConfigurationError('allow_curved_support must be bool')
  ####


@dataclass(frozen=True, slots=True)
class GrayRayTransferConfiguration:
  """Provider identity and numerical policy for the gray transfer lane."""

  provider_id: str = 'plume.gray-ray-transfer'
  provider_version: str = '1.0.0'
  intersection_tolerance_m: float = 1.0e-10

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('gray provider identity must not be empty')
    ####
    if not isfinite(self.intersection_tolerance_m) or self.intersection_tolerance_m <= 0.0:
      raise ProviderConfigurationError('intersection_tolerance_m must be finite and positive')
  ####


def _descriptor(configuration: GrayRayTransferConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(SPECTRAL_RAY_TRANSFER_CAPABILITY,),
    provider_definition_schema_id='plume.optical.gray-ray-transfer-definition.v1',
    dynamic_state_schema_id='plume.optical.gray-ray-transfer-dynamic-state.v1',
    configuration_schema_id='plume.optical.gray-ray-transfer-configuration.v1',
    supported_morphologies=('straight', 'axisymmetric'),
    deterministic=True,
    notes=(
      'exact homogeneous segment transfer through a straight sectioned support',
      'constant-radius support uses an exact finite cylinder; varying radius uses a conservative segment-maximum capsule union',
      'source radiance and background transmittance are returned separately',
      'gray-approximate radiation only; no chemistry, atmosphere, detector, or FPA',
      'curved sectioned-support intervals are available as geometry-only primitives',
      'fidelity profile: optical-transfer-v1',
    ),
  )
####


def _interpolate(nodes: tuple[float, ...], values: tuple[float, ...], value: float) -> float:
  if value < nodes[0] or value > nodes[-1]:
    raise ProductOutsideApplicabilityError('requested wavelength is outside the gray optical property domain')
  ####
  if value == nodes[0]:
    return values[0]
  ####
  if value == nodes[-1]:
    return values[-1]
  ####
  upper = bisect_right(nodes, value)
  lower = upper - 1
  fraction = (value - nodes[lower]) / (nodes[upper] - nodes[lower])
  return values[lower] + fraction * (values[upper] - values[lower])
####


class _GrayRayTransferEvaluator:
  def __init__(
      self,
      definition: GrayRayTransferDefinition,
      configuration: GrayRayTransferConfiguration,
  ) -> None:
    self._definition = definition
    self._configuration = configuration
    self._lineage_id = canonical_digest(definition)
  ####

  def evaluate(
      self,
      request: SpectralRayTransferRequest,
      snapshot: SnapshotMetadata,
  ) -> SpectralRayTransferResult:
    if request.ray_frame_id != self._definition.frame_id:
      raise ProductOutsideApplicabilityError(
        f'gray ray provider supports frame {self._definition.frame_id!r}, not {request.ray_frame_id!r}',
      )
    ####
    source_spectrum = tuple(
      _interpolate(self._definition.wavelengths_m, self._definition.source_function_w_sr_m, wavelength)
      for wavelength in request.wavelengths_m
    )
    absorption_spectrum = tuple(
      _interpolate(self._definition.wavelengths_m, self._definition.absorption_coefficient_per_m, wavelength)
      for wavelength in request.wavelengths_m
    )
    ####
    source_matrix: list[tuple[float, ...]] = []
    transmittance_matrix: list[tuple[float, ...]] = []
    validity_matrix: list[tuple[bool, ...]] = []
    optical_depth_matrix: list[tuple[float, ...]] = []
    statuses: list[SampleStatus] = []
    hit_mask: list[bool] = []
    intersection_intervals: list[tuple[float, float] | None] = []
    for origin, direction, t_min, t_max in zip(
        request.ray_origins_m,
        request.ray_directions,
        request.ray_t_min_m,
        request.ray_t_max_m,
    ):
      intervals = intersect_sectioned_tube(
        origin,
        direction,
        self._definition.support,
        t_min_m=t_min,
        t_max_m=t_max,
        tolerance=self._configuration.intersection_tolerance_m,
      )
      if not intervals:
        source_matrix.append(tuple(0.0 for _ in request.wavelengths_m))
        transmittance_matrix.append(tuple(1.0 for _ in request.wavelengths_m))
        optical_depth_matrix.append(tuple(0.0 for _ in request.wavelengths_m))
        validity_matrix.append(tuple(True for _ in request.wavelengths_m))
        statuses.append(SampleStatus(code=SampleStatusCode.OK))
        hit_mask.append(False)
        intersection_intervals.append(None)
        continue
      ####
      segments = tuple(
        HomogeneousSegment(source_spectrum, absorption_spectrum, interval.t_exit_m - interval.t_enter_m)
        for interval in intervals
      )
      transfer = compose_homogeneous_segments(segments)
      source_matrix.append(transfer.source_radiance_w_sr_m)
      transmittance_matrix.append(transfer.background_transmittance)
      optical_depth_matrix.append(transfer.optical_depth)
      validity_matrix.append(tuple(True for _ in request.wavelengths_m))
      statuses.append(SampleStatus(code=SampleStatusCode.OK))
      hit_mask.append(True)
      intersection_intervals.append((intervals[0].t_enter_m, intervals[-1].t_exit_m))
    ####
    request_digest = canonical_digest(request)
    metadata = ResultMetadata(
      capability=SPECTRAL_RAY_TRANSFER_CAPABILITY,
      result_id=canonical_digest({'snapshot': snapshot.snapshot_id, 'request': request_digest})[:24],
      request_digest_sha256=request_digest,
      snapshot=snapshot,
      output_frame_id=request.ray_frame_id,
      claims=ProductClaims(
        geometry=GeometryClaim.NOT_APPLICABLE,
        radiation=RadiationClaim.GRAY_APPROXIMATE,
        time_model=TimeModel.STEADY,
        derivation=Derivation.NATIVE,
        consistency=ConsistencyLevel.INDEPENDENT,
      ),
      applicability=ApplicabilityReport(status=ApplicabilityStatus.INSIDE),
      provenance=ResultProvenance(
        model_lineage_id=self._lineage_id,
        provider_id=self._configuration.provider_id,
        provider_version=self._configuration.provider_version,
        configuration_digest_sha256=canonical_digest(self._configuration),
        asset_digests_sha256=(self._definition.asset_sha256,) if self._definition.asset_sha256 else (),
        metadata={
          'direction_convention': 'ray origin toward scene; segments composed near-to-far',
          'support_geometry': (
            'exact finite straight circular cylinder'
            if self._definition.support.is_straight and self._definition.support.is_constant_radius
            else 'curved piecewise capsule path using segment-maximum radius'
            if not self._definition.support.is_straight
            else 'straight piecewise capsule union using segment-maximum radius; conservative support geometry'
          ),
          'source_function_convention': 'L_out = L_in*T + S*(1-T)',
          'wavelength_interpolation': 'linear within definition domain',
        },
      ),
      warnings=(),
    )
    return SpectralRayTransferResult(
      metadata=metadata,
      source_spectral_radiance=tuple(source_matrix),
      background_transmittance=tuple(transmittance_matrix),
      validity_mask=tuple(validity_matrix),
      ray_status=tuple(statuses),
      hit_mask=tuple(hit_mask),
      optical_depth=tuple(optical_depth_matrix),
      plume_intersection_t_m=tuple(intersection_intervals),
    )
  ####
####


class GrayRayTransferProvider:
  """Canonical provider for the bounded gray optical-transfer lane."""

  def __init__(self, configuration: GrayRayTransferConfiguration | None = None) -> None:
    self._configuration = configuration or GrayRayTransferConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: GrayRayTransferDefinition,
      configuration: GrayRayTransferConfiguration | None = None,
  ) -> 'GrayRayTransferSession':
    if not isinstance(definition, GrayRayTransferDefinition):
      raise ProviderConfigurationError('definition must be GrayRayTransferDefinition')
    if not definition.support.is_straight:
      raise ProviderConfigurationError('gray-ray-transfer-v1 requires a straight support; use the curved provider for curved supports')
    ####
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return GrayRayTransferSession(self._descriptor, definition, selected_configuration)
  ####
####


class GrayRayTransferSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: GrayRayTransferDefinition,
      configuration: GrayRayTransferConfiguration,
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
        'definition': canonical_digest(definition),
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
      raise ProviderClosedError('gray ray-transfer session is closed')
    ####
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    ####
    dynamic_digest = canonical_digest(dynamic_state)
    ambient_digest = canonical_digest(ambient_state)
    provider_digest = canonical_digest(self._definition)
    snapshot_id = canonical_digest({
      'session': self._metadata.session_id,
      'time_s': time_s,
      'source_pose': source_pose,
      'dynamic': dynamic_digest,
      'ambient': ambient_digest,
      'provider': provider_digest,
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
      _evaluators={
        SPECTRAL_RAY_TRANSFER_CAPABILITY: _GrayRayTransferEvaluator(
          self._definition,
          self._configuration,
        ),
      },
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
