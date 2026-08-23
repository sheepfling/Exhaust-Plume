"""Strict immutable DTOs for versioned exhaust-plume products.

The contracts intentionally separate visual geometry, unresolved spectral
signature, resolved spectral ray transfer, and conservative engineering handoff
products. They contain no solver-private plume-zone or mesh types.
"""

from __future__ import annotations

import hashlib
import json
from enum import Enum
from math import sqrt
from typing import Annotated, Any, Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exhaust_plume.api.capabilities import (
    ENGINEERING_FLUX_SECTION_V1,
    OPTICAL_SPECTRAL_RAY_TRANSFER_V1,
    SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1,
    VISUAL_SECTIONED_TUBE_V1,
)

FiniteFloat: TypeAlias = Annotated[float, Field(allow_inf_nan=False)]
PositiveFloat: TypeAlias = Annotated[FiniteFloat, Field(gt=0.)]
NonnegativeFloat: TypeAlias = Annotated[FiniteFloat, Field(ge=0.)]
UnitFraction: TypeAlias = Annotated[FiniteFloat, Field(ge=0., le=1.)]
Vec3: TypeAlias = tuple[FiniteFloat, FiniteFloat, FiniteFloat]
QuatXYZW: TypeAlias = tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat]
Matrix2: TypeAlias = tuple[tuple[FiniteFloat, FiniteFloat], tuple[FiniteFloat, FiniteFloat]]

_VECTOR_TOLERANCE = 1.e-6
_SEMVER_PATTERN = r'^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$'
_SHA256_PATTERN = r'^[0-9a-f]{64}$'


def _dot(left: Vec3, right: Vec3) -> float:
  return float(sum(a * b for a, b in zip(left, right)))
####


def _norm(vector: Vec3) -> float:
  return sqrt(_dot(vector, vector))
####


def _cross(left: Vec3, right: Vec3) -> tuple[float, float, float]:
  return (
      left[1] * right[2] - left[2] * right[1],
      left[2] * right[0] - left[0] * right[2],
      left[0] * right[1] - left[1] * right[0],
  )
####


def _validate_unit_vector(name: str, vector: Vec3) -> None:
  if abs(_norm(vector) - 1.) > _VECTOR_TOLERANCE:
    raise ValueError(f'{name} must be a unit vector')
  ####
####


def _validate_strictly_increasing(name: str, values: tuple[float, ...]) -> None:
  if any(right <= left for left, right in zip(values, values[1:])):
    raise ValueError(f'{name} must be strictly increasing')
  ####
####


class StrictFrozenModel(BaseModel):
  """Base configuration for public immutable DTOs."""

  model_config = ConfigDict(frozen=True, extra='forbid', strict=True)
####


class TimeAccessPolicy(str, Enum):
  EXACT = 'EXACT'
  INTERPOLATE = 'INTERPOLATE'
  NEAREST = 'NEAREST'
####


class ResultStatus(str, Enum):
  OK = 'OK'
  PARTIAL = 'PARTIAL'
  DEGRADED = 'DEGRADED'
  FAILED = 'FAILED'
####


class ItemStatus(str, Enum):
  OK = 'OK'
  OUT_OF_DOMAIN = 'OUT_OF_DOMAIN'
  INVALID_REQUEST = 'INVALID_REQUEST'
  NUMERICAL_FAILURE = 'NUMERICAL_FAILURE'
  APPLICABILITY_VIOLATION = 'APPLICABILITY_VIOLATION'
####


class ModelFidelity(str, Enum):
  PRESCRIBED = 'PRESCRIBED'
  EXPLORATORY_ANALYTICAL = 'EXPLORATORY_ANALYTICAL'
  CALIBRATED_REDUCED_ORDER = 'CALIBRATED_REDUCED_ORDER'
  VALIDATED_REDUCED_ORDER = 'VALIDATED_REDUCED_ORDER'
  IMPORTED_NUMERICAL = 'IMPORTED_NUMERICAL'
  REFERENCE_NUMERICAL = 'REFERENCE_NUMERICAL'
####


class ValidationLevel(str, Enum):
  UNVERIFIED = 'UNVERIFIED'
  VERIFIED = 'VERIFIED'
  CALIBRATED = 'CALIBRATED'
  VALIDATED = 'VALIDATED'
####


class FeatureAssociation(str, Enum):
  SECTION = 'SECTION'
  CENTERLINE = 'CENTERLINE'
####


class Pose3(StrictFrozenModel):
  translation_m: Vec3
  rotation_xyzw: QuatXYZW

  @model_validator(mode='after')
  def validate_quaternion(self) -> Pose3:
    norm_sq = sum(component * component for component in self.rotation_xyzw)
    if not 0.999_999 <= norm_sq <= 1.000_001:
      raise ValueError('rotation_xyzw must be a unit quaternion in (x, y, z, w) order')
    ####
    return self
  ####
####


class FrameRef(StrictFrozenModel):
  frame_id: str = Field(min_length=1)
  parent_frame_id: str | None = None
  pose_parent_from_frame: Pose3

  @model_validator(mode='after')
  def validate_parent(self) -> FrameRef:
    if self.parent_frame_id == self.frame_id:
      raise ValueError('frame_id cannot be its own parent')
    ####
    return self
  ####
####


class FidelityClaim(StrictFrozenModel):
  model_fidelity: ModelFidelity
  validation_level: ValidationLevel
  claim_notes: tuple[str, ...] = ()
####


class Applicability(StrictFrozenModel):
  supported: bool
  domain: dict[str, Any] = Field(default_factory=dict)
  violations: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validate_violations(self) -> Applicability:
    if self.supported and self.violations:
      raise ValueError('supported applicability cannot contain violations')
    ####
    if not self.supported and not self.violations:
      raise ValueError('unsupported applicability must explain at least one violation')
    ####
    return self
  ####
####


class Provenance(StrictFrozenModel):
  model_id: str = Field(min_length=1)
  model_version: str = Field(min_length=1)
  code_revision: str = Field(min_length=1)
  configuration_sha256: str = Field(pattern=_SHA256_PATTERN)
  asset_digests_sha256: tuple[str, ...] = ()

  @model_validator(mode='after')
  def validate_asset_digests(self) -> Provenance:
    if any(len(digest) != 64 or any(character not in '0123456789abcdef' for character in digest) for digest in self.asset_digests_sha256):
      raise ValueError('asset_digests_sha256 must contain lowercase SHA-256 digests')
    ####
    return self
  ####
####


class DerivationStep(StrictFrozenModel):
  adapter_id: str = Field(min_length=1)
  adapter_version: str = Field(min_length=1)
  source_capability_id: str = Field(min_length=1)
  source_snapshot_id: UUID
####


class SnapshotRequest(StrictFrozenModel):
  time_s: FiniteFloat
  time_policy: TimeAccessPolicy = TimeAccessPolicy.EXACT
####


class ResultEnvelope(StrictFrozenModel):
  capability_id: str = Field(min_length=1)
  schema_version: str = Field(pattern=_SEMVER_PATTERN)
  provider_id: UUID
  session_id: UUID
  snapshot_id: UUID
  content_sha256: str = Field(pattern=_SHA256_PATTERN)
  requested_time_s: FiniteFloat
  actual_time_s: FiniteFloat
  frame: FrameRef
  status: ResultStatus
  fidelity: FidelityClaim
  applicability: Applicability
  provenance: Provenance
  derivation: tuple[DerivationStep, ...] = ()
  warnings: tuple[str, ...] = ()
####


class SupportDefinition(StrictFrozenModel):
  kind: Literal[
      'ENCLOSED_EXHAUST_MASS_FRACTION',
      'INTEGRAL_TOP_HAT_BOUNDARY',
      'PHYSICAL_ZONE_BOUNDARY',
      'EXHAUST_MASS_FRACTION_THRESHOLD',
      'TEMPERATURE_EXCESS_THRESHOLD',
  ]
  fraction: UnitFraction | None = None
  threshold: FiniteFloat | None = None
  unit: str | None = None

  @model_validator(mode='after')
  def validate_definition(self) -> SupportDefinition:
    if self.kind == 'ENCLOSED_EXHAUST_MASS_FRACTION':
      if self.fraction is None or self.fraction <= 0.:
        raise ValueError('enclosed-mass support requires fraction in (0, 1]')
      ####
      if self.threshold is not None or self.unit is not None:
        raise ValueError('enclosed-mass support does not accept threshold or unit')
      ####
    elif self.kind in {'INTEGRAL_TOP_HAT_BOUNDARY', 'PHYSICAL_ZONE_BOUNDARY'}:
      if self.fraction is not None or self.threshold is not None or self.unit is not None:
        raise ValueError('boundary support does not accept fraction, threshold, or unit')
      ####
    else:
      if self.threshold is None or self.unit is None or not self.unit:
        raise ValueError('threshold support requires threshold and unit')
      ####
      if self.fraction is not None:
        raise ValueError('threshold support does not accept fraction')
      ####
    ####
    return self
  ####
####


class TubeSection(StrictFrozenModel):
  arc_length_m: NonnegativeFloat
  center_m: Vec3
  tangent: Vec3
  normal_1: Vec3
  normal_2: Vec3
  semi_axis_1_m: PositiveFloat
  semi_axis_2_m: PositiveFloat

  @model_validator(mode='after')
  def validate_frame(self) -> TubeSection:
    _validate_unit_vector('tangent', self.tangent)
    _validate_unit_vector('normal_1', self.normal_1)
    _validate_unit_vector('normal_2', self.normal_2)
    if abs(_dot(self.tangent, self.normal_1)) > _VECTOR_TOLERANCE:
      raise ValueError('tangent and normal_1 must be orthogonal')
    ####
    if abs(_dot(self.tangent, self.normal_2)) > _VECTOR_TOLERANCE:
      raise ValueError('tangent and normal_2 must be orthogonal')
    ####
    if abs(_dot(self.normal_1, self.normal_2)) > _VECTOR_TOLERANCE:
      raise ValueError('normal_1 and normal_2 must be orthogonal')
    ####
    handedness = _dot(_cross(self.tangent, self.normal_1), self.normal_2)
    if handedness < 1. - _VECTOR_TOLERANCE:
      raise ValueError('(tangent, normal_1, normal_2) must form a right-handed frame')
    ####
    return self
  ####
####


class FeatureChannel(StrictFrozenModel):
  channel_id: str = Field(min_length=1)
  semantic: str = Field(min_length=1)
  unit: str = Field(min_length=1)
  association: FeatureAssociation
  component_count: int = Field(ge=1)
  values: tuple[FiniteFloat | None, ...]
####


class SectionedTubePayload(StrictFrozenModel):
  sections: tuple[TubeSection, ...] = Field(min_length=2)
  feature_channels: tuple[FeatureChannel, ...] = ()
  support_definition: SupportDefinition

  @model_validator(mode='after')
  def validate_payload(self) -> SectionedTubePayload:
    arc_lengths = tuple(section.arc_length_m for section in self.sections)
    _validate_strictly_increasing('section arc lengths', arc_lengths)
    expected_sections = len(self.sections)
    channel_ids: set[str] = set()
    for channel in self.feature_channels:
      if channel.channel_id in channel_ids:
        raise ValueError(f'duplicate feature channel_id:{channel.channel_id}')
      ####
      channel_ids.add(channel.channel_id)
      expected_values = expected_sections * channel.component_count
      if len(channel.values) != expected_values:
        raise ValueError(
            f'feature channel {channel.channel_id!r} has {len(channel.values)} values; '
            f'expected {expected_values}'
        )
      ####
    ####
    return self
  ####
####


class SectionedTubeResult(StrictFrozenModel):
  envelope: ResultEnvelope
  payload: SectionedTubePayload

  @model_validator(mode='after')
  def validate_capability(self) -> SectionedTubeResult:
    if self.envelope.capability_id != VISUAL_SECTIONED_TUBE_V1:
      raise ValueError('capability_id does not match SectionedTubeResult')
    ####
    return self
  ####
####


class SpectralRadiantIntensityPayload(StrictFrozenModel):
  directions: tuple[Vec3, ...] = Field(min_length=1)
  wavelengths_m: tuple[PositiveFloat, ...] = Field(min_length=1)
  radiant_intensity_W_sr_m: tuple[tuple[FiniteFloat | None, ...], ...]
  validity_mask: tuple[tuple[bool, ...], ...]
  uncertainty: dict[str, Any] = Field(default_factory=dict)

  @model_validator(mode='after')
  def validate_payload(self) -> SpectralRadiantIntensityPayload:
    for index, direction in enumerate(self.directions):
      _validate_unit_vector(f'directions[{index}]', direction)
    ####
    _validate_strictly_increasing('wavelengths_m', self.wavelengths_m)
    if len(self.radiant_intensity_W_sr_m) != len(self.directions):
      raise ValueError('radiant-intensity observer axis does not match directions')
    ####
    if len(self.validity_mask) != len(self.directions):
      raise ValueError('validity-mask observer axis does not match directions')
    ####
    wavelength_count = len(self.wavelengths_m)
    for values, mask in zip(self.radiant_intensity_W_sr_m, self.validity_mask):
      if len(values) != wavelength_count or len(mask) != wavelength_count:
        raise ValueError('signature wavelength axis does not match wavelengths_m')
      ####
      if any(is_valid != (value is not None) for value, is_valid in zip(values, mask)):
        raise ValueError('signature values and validity_mask disagree')
      ####
    ####
    return self
  ####
####


class SpectralRadiantIntensityResult(StrictFrozenModel):
  envelope: ResultEnvelope
  payload: SpectralRadiantIntensityPayload

  @model_validator(mode='after')
  def validate_capability(self) -> SpectralRadiantIntensityResult:
    if self.envelope.capability_id != SIGNATURE_SPECTRAL_RADIANT_INTENSITY_V1:
      raise ValueError('capability_id does not match SpectralRadiantIntensityResult')
    ####
    return self
  ####
####


class SpectralRayTransferPayload(StrictFrozenModel):
  ray_ids: tuple[str, ...] = Field(min_length=1)
  origins_m: tuple[Vec3, ...]
  directions: tuple[Vec3, ...]
  wavelengths_m: tuple[PositiveFloat, ...] = Field(min_length=1)
  source_radiance_W_m2_sr_m: tuple[tuple[FiniteFloat | None, ...], ...]
  background_transmittance: tuple[tuple[FiniteFloat | None, ...], ...]
  validity_mask: tuple[tuple[bool, ...], ...]
  item_status: tuple[ItemStatus, ...]
  next_page_token: str | None = None

  @model_validator(mode='after')
  def validate_payload(self) -> SpectralRayTransferPayload:
    ray_count = len(self.ray_ids)
    if len(set(self.ray_ids)) != ray_count:
      raise ValueError('ray_ids must be unique')
    ####
    if any(len(sequence) != ray_count for sequence in (self.origins_m, self.directions, self.item_status)):
      raise ValueError('ray-axis arrays do not match ray_ids')
    ####
    for index, direction in enumerate(self.directions):
      _validate_unit_vector(f'directions[{index}]', direction)
    ####
    _validate_strictly_increasing('wavelengths_m', self.wavelengths_m)
    wavelength_count = len(self.wavelengths_m)
    matrices = (
        self.source_radiance_W_m2_sr_m,
        self.background_transmittance,
        self.validity_mask,
    )
    if any(len(matrix) != ray_count for matrix in matrices):
      raise ValueError('ray-transfer matrix ray axis does not match ray_ids')
    ####
    for source_values, transmittance_values, mask in zip(*matrices):
      if any(len(row) != wavelength_count for row in (source_values, transmittance_values, mask)):
        raise ValueError('ray-transfer wavelength axis does not match wavelengths_m')
      ####
      if any(value is not None and not 0. <= value <= 1. for value in transmittance_values):
        raise ValueError('background_transmittance must be in [0, 1]')
      ####
      if any(
          is_valid != (source is not None and transmittance is not None)
          for source, transmittance, is_valid in zip(source_values, transmittance_values, mask)
      ):
        raise ValueError('ray-transfer values and validity_mask disagree')
      ####
    ####
    return self
  ####
####


class SpectralRayTransferResult(StrictFrozenModel):
  envelope: ResultEnvelope
  payload: SpectralRayTransferPayload

  @model_validator(mode='after')
  def validate_capability(self) -> SpectralRayTransferResult:
    if self.envelope.capability_id != OPTICAL_SPECTRAL_RAY_TRANSFER_V1:
      raise ValueError('capability_id does not match SpectralRayTransferResult')
    ####
    return self
  ####
####


class SpeciesMassFlow(StrictFrozenModel):
  species_id: str = Field(min_length=1)
  mass_flow_kgps: NonnegativeFloat
####


class PlumeFluxSection(StrictFrozenModel):
  time_s: FiniteFloat
  frame: FrameRef
  section_pose: Pose3
  normal: Vec3
  area_m2: PositiveFloat
  mass_flow_kgps: PositiveFloat
  momentum_flux_N: Vec3
  total_energy_flow_W: PositiveFloat
  species_mass_flows_kgps: tuple[SpeciesMassFlow, ...]
  pressure_Pa: PositiveFloat
  ambient_pressure_Pa: PositiveFloat
  pressure_match_relative_residual: NonnegativeFloat
  cross_section_second_moment_m2: Matrix2
  provenance: Provenance
  applicability: Applicability
  uncertainty: dict[str, Any] = Field(default_factory=dict)

  @model_validator(mode='after')
  def validate_section(self) -> PlumeFluxSection:
    _validate_unit_vector('normal', self.normal)
    if len({species.species_id for species in self.species_mass_flows_kgps}) != len(self.species_mass_flows_kgps):
      raise ValueError('species_id values must be unique')
    ####
    expected_residual = abs(self.pressure_Pa - self.ambient_pressure_Pa) / self.ambient_pressure_Pa
    if abs(self.pressure_match_relative_residual - expected_residual) > 1.e-9 * max(1., expected_residual):
      raise ValueError('pressure_match_relative_residual does not match pressure values')
    ####
    moment = self.cross_section_second_moment_m2
    if abs(moment[0][1] - moment[1][0]) > 1.e-12:
      raise ValueError('cross_section_second_moment_m2 must be symmetric')
    ####
    determinant = moment[0][0] * moment[1][1] - moment[0][1] * moment[1][0]
    if determinant < -1.e-12:
      raise ValueError('cross_section_second_moment_m2 must be positive semidefinite')
    ####
    return self
  ####
####


class PlumeFluxSectionResult(StrictFrozenModel):
  envelope: ResultEnvelope
  payload: PlumeFluxSection

  @model_validator(mode='after')
  def validate_capability(self) -> PlumeFluxSectionResult:
    if self.envelope.capability_id != ENGINEERING_FLUX_SECTION_V1:
      raise ValueError('capability_id does not match PlumeFluxSectionResult')
    ####
    return self
  ####
####


ProductResult: TypeAlias = (
    SectionedTubeResult
    | SpectralRadiantIntensityResult
    | SpectralRayTransferResult
    | PlumeFluxSectionResult
)


def calculate_content_sha256(payload: StrictFrozenModel) -> str:
  """Hash canonical JSON content for caching and deterministic comparisons."""
  normalized = json.dumps(
      payload.model_dump(mode='json'),
      allow_nan=False,
      ensure_ascii=False,
      separators=(',', ':'),
      sort_keys=True,
  ).encode('utf-8')
  return hashlib.sha256(normalized).hexdigest()
####
