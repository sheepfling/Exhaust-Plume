"""Neutral table-backed unresolved directional spectral lookup provider."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass, field
from enum import Enum
from math import exp, isfinite, log, sqrt
from typing import Any, Mapping

from exhaust_plume.contracts import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  Pose,
  ProductClaims,
  ProductOutsideApplicabilityError,
  ProviderConfigurationError,
  ProviderDescriptor,
  RadiationClaim,
  ResultMetadata,
  ResultProvenance,
  SampleStatus,
  SampleStatusCode,
  SessionMetadata,
  SnapshotMetadata,
  SpectralSignatureRequest,
  SpectralSignatureResult,
  SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
  TimeModel,
  Vector3,
  canonical_digest,
)
from exhaust_plume.contracts.errors import ProviderClosedError

__all__ = (
  'LookupInterpolationPolicy',
  'SignatureTableConfiguration',
  'SignatureTableDefinition',
  'SignatureTableProvider',
  'SignatureTableSession',
)
####


TableMatrix = tuple[tuple[float, ...], ...]
TableTensor = tuple[TableMatrix, ...]


class LookupInterpolationPolicy(str, Enum):
  """Explicit interpolation policies supported by the host-array table MVP."""

  LINEAR = 'linear'
  LOG_LINEAR = 'log-linear'
  NEAREST = 'nearest'
  EXACT_ONLY = 'exact-only'
  ####


def _validate_axis(values: tuple[float, ...], field_name: str, *, minimum_count: int = 2) -> None:
  if len(values) < minimum_count:
    raise ProviderConfigurationError(f'{field_name} requires at least {minimum_count} values')
  if not all(isfinite(value) for value in values):
    raise ProviderConfigurationError(f'{field_name} must contain finite values')
  if any(next_value <= value for value, next_value in zip(values, values[1:])):
    raise ProviderConfigurationError(f'{field_name} must be strictly increasing')
####


def _coerce_policy(
    value: LookupInterpolationPolicy | str,
    field_name: str,
    allowed: tuple[LookupInterpolationPolicy, ...],
) -> LookupInterpolationPolicy:
  try:
    policy = LookupInterpolationPolicy(value)
  except (TypeError, ValueError) as error:
    allowed_values = ', '.join(item.value for item in allowed)
    raise ProviderConfigurationError(
      f'{field_name} must be one of: {allowed_values}'
    ) from error
  if policy not in allowed:
    allowed_values = ', '.join(item.value for item in allowed)
    raise ProviderConfigurationError(
      f'{field_name} must be one of: {allowed_values}'
    )
  return policy


def _validate_asset_sha256(value: str | None) -> None:
  if value is None:
    return
  if len(value) != 64 or any(character not in '0123456789abcdefABCDEF' for character in value):
    raise ProviderConfigurationError('asset_sha256 must be a 64-character hexadecimal digest')
####


def _validate_unit_vector(value: Vector3, field_name: str) -> None:
  if not all(isfinite(component) for component in value):
    raise ProviderConfigurationError(f'{field_name} must be finite')
  norm = sqrt(sum(component * component for component in value))
  if abs(norm - 1.0) > 1.0e-6:
    raise ProviderConfigurationError(f'{field_name} must be unit length')
####


@dataclass(frozen=True, slots=True)
class SignatureTableDefinition:
  """Axisymmetric table over direction cosine, wavelength, and optional time nodes."""

  frame_id: str
  wavelengths_m: tuple[float, ...]
  direction_cosine_nodes: tuple[float, ...]
  spectral_radiant_intensity_w_sr_m: tuple[tuple[float, ...], ...]
  absolute_standard_uncertainty_w_sr_m: tuple[tuple[float, ...], ...] | None = None
  axis_direction: Vector3 = (1.0, 0.0, 0.0)
  asset_id: str = 'signature-table'
  operating_point_id: str = 'unspecified'
  source_total_pressure_Pa: float | None = None
  source_total_temperature_K: float | None = None
  ambient_pressure_Pa: float | None = None
  wavelength_interpolation: LookupInterpolationPolicy = LookupInterpolationPolicy.LINEAR
  angular_interpolation: LookupInterpolationPolicy = LookupInterpolationPolicy.LINEAR
  time_interpolation: LookupInterpolationPolicy = LookupInterpolationPolicy.LINEAR
  time_nodes_s: tuple[float, ...] = ()
  spectral_radiant_intensity_w_sr_m_by_time: TableTensor | None = None
  absolute_standard_uncertainty_w_sr_m_by_time: TableTensor | None = None
  asset_sha256: str | None = field(default=None, compare=False, repr=False)

  def __post_init__(self) -> None:
    if not self.frame_id or not self.asset_id or not self.operating_point_id:
      raise ProviderConfigurationError('signature table frame_id, asset_id, and operating_point_id must not be empty')
    _validate_axis(self.wavelengths_m, 'wavelengths_m')
    _validate_axis(self.direction_cosine_nodes, 'direction_cosine_nodes')
    if self.direction_cosine_nodes[0] < -1.0 or self.direction_cosine_nodes[-1] > 1.0:
      raise ProviderConfigurationError('direction cosine nodes must lie in [-1, 1]')
    _validate_unit_vector(self.axis_direction, 'axis_direction')
    wavelength_interpolation = _coerce_policy(
      self.wavelength_interpolation,
      'wavelength_interpolation',
      (
        LookupInterpolationPolicy.LINEAR,
        LookupInterpolationPolicy.LOG_LINEAR,
        LookupInterpolationPolicy.NEAREST,
        LookupInterpolationPolicy.EXACT_ONLY,
      ),
    )
    angular_interpolation = _coerce_policy(
      self.angular_interpolation,
      'angular_interpolation',
      (
        LookupInterpolationPolicy.LINEAR,
        LookupInterpolationPolicy.NEAREST,
        LookupInterpolationPolicy.EXACT_ONLY,
      ),
    )
    time_interpolation = _coerce_policy(
      self.time_interpolation,
      'time_interpolation',
      (
        LookupInterpolationPolicy.LINEAR,
        LookupInterpolationPolicy.NEAREST,
        LookupInterpolationPolicy.EXACT_ONLY,
      ),
    )
    time_nodes = tuple(float(value) for value in self.time_nodes_s)
    if time_nodes:
      _validate_axis(time_nodes, 'time_nodes_s', minimum_count=1)
    for field_name, value in (
        ('source_total_pressure_Pa', self.source_total_pressure_Pa),
        ('source_total_temperature_K', self.source_total_temperature_K),
        ('ambient_pressure_Pa', self.ambient_pressure_Pa),
    ):
      if value is not None and (not isfinite(value) or value <= 0.0):
        raise ProviderConfigurationError(f'{field_name} must be finite and positive when supplied')
    expected_shape = (len(self.direction_cosine_nodes), len(self.wavelengths_m))
    _validate_matrix(self.spectral_radiant_intensity_w_sr_m, expected_shape, 'spectral_radiant_intensity_w_sr_m')
    if self.absolute_standard_uncertainty_w_sr_m is not None:
      _validate_matrix(
        self.absolute_standard_uncertainty_w_sr_m,
        expected_shape,
        'absolute_standard_uncertainty_w_sr_m',
      )
    normalized_intensity = _readonly_matrix(self.spectral_radiant_intensity_w_sr_m)
    normalized_uncertainty = (
      _readonly_matrix(self.absolute_standard_uncertainty_w_sr_m)
      if self.absolute_standard_uncertainty_w_sr_m is not None
      else None
    )
    normalized_intensity_by_time = (
      _readonly_tensor(self.spectral_radiant_intensity_w_sr_m_by_time)
      if self.spectral_radiant_intensity_w_sr_m_by_time is not None
      else None
    )
    normalized_uncertainty_by_time = (
      _readonly_tensor(self.absolute_standard_uncertainty_w_sr_m_by_time)
      if self.absolute_standard_uncertainty_w_sr_m_by_time is not None
      else None
    )
    if time_nodes:
      if normalized_intensity_by_time is None:
        raise ProviderConfigurationError(
          'spectral_radiant_intensity_w_sr_m_by_time is required when time_nodes_s is supplied'
        )
      _validate_tensor(
        normalized_intensity_by_time,
        (len(time_nodes), *expected_shape),
        'spectral_radiant_intensity_w_sr_m_by_time',
      )
      if normalized_intensity_by_time[0] != normalized_intensity:
        raise ProviderConfigurationError(
          'spectral_radiant_intensity_w_sr_m must equal the first time slice'
        )
      if normalized_uncertainty_by_time is not None:
        if normalized_uncertainty is None:
          raise ProviderConfigurationError(
            'absolute_standard_uncertainty_w_sr_m is required when time-sliced uncertainty is supplied'
          )
        _validate_tensor(
          normalized_uncertainty_by_time,
          (len(time_nodes), *expected_shape),
          'absolute_standard_uncertainty_w_sr_m_by_time',
        )
        if normalized_uncertainty_by_time[0] != normalized_uncertainty:
          raise ProviderConfigurationError(
            'absolute_standard_uncertainty_w_sr_m must equal the first time-sliced uncertainty'
          )
    elif normalized_intensity_by_time is not None or normalized_uncertainty_by_time is not None:
      raise ProviderConfigurationError(
        'time_nodes_s is required when time-sliced table values are supplied'
      )
    _validate_asset_sha256(self.asset_sha256)
    object.__setattr__(self, 'wavelengths_m', tuple(float(value) for value in self.wavelengths_m))
    object.__setattr__(self, 'direction_cosine_nodes', tuple(float(value) for value in self.direction_cosine_nodes))
    object.__setattr__(self, 'axis_direction', tuple(float(value) for value in self.axis_direction))
    object.__setattr__(self, 'spectral_radiant_intensity_w_sr_m', normalized_intensity)
    object.__setattr__(self, 'absolute_standard_uncertainty_w_sr_m', normalized_uncertainty)
    object.__setattr__(self, 'wavelength_interpolation', wavelength_interpolation)
    object.__setattr__(self, 'angular_interpolation', angular_interpolation)
    object.__setattr__(self, 'time_interpolation', time_interpolation)
    object.__setattr__(self, 'time_nodes_s', time_nodes)
    object.__setattr__(self, 'spectral_radiant_intensity_w_sr_m_by_time', normalized_intensity_by_time)
    object.__setattr__(self, 'absolute_standard_uncertainty_w_sr_m_by_time', normalized_uncertainty_by_time)
    object.__setattr__(
      self,
      'asset_sha256',
      self.asset_sha256.lower() if self.asset_sha256 is not None else None,
    )
  ####
####


@dataclass(frozen=True, slots=True)
class SignatureTableConfiguration:
  provider_id: str = 'signature.table-lookup'
  provider_version: str = '1.1.0'
  allow_extrapolation: bool = False
  radiation_claim: RadiationClaim = RadiationClaim.TABULATED
  time_model: TimeModel = TimeModel.STEADY

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('signature table provider identity must not be empty')
    try:
      object.__setattr__(self, 'radiation_claim', RadiationClaim(self.radiation_claim))
      object.__setattr__(self, 'time_model', TimeModel(self.time_model))
    except (TypeError, ValueError) as error:
      raise ProviderConfigurationError('signature table claims must use supported contract enum values') from error
  ####
####


def _validate_matrix(
    matrix: TableMatrix,
    expected_shape: tuple[int, int],
    field_name: str,
) -> None:
  if len(matrix) != expected_shape[0] or any(len(row) != expected_shape[1] for row in matrix):
    raise ProviderConfigurationError(f'{field_name} must have shape {expected_shape}')
  if any(not isfinite(value) or value < 0.0 for row in matrix for value in row):
    raise ProviderConfigurationError(f'{field_name} must be finite and nonnegative')
####


def _validate_tensor(
    tensor: TableTensor,
    expected_shape: tuple[int, int, int],
    field_name: str,
) -> None:
  if len(tensor) != expected_shape[0]:
    raise ProviderConfigurationError(f'{field_name} must have shape {expected_shape}')
  for matrix in tensor:
    _validate_matrix(matrix, expected_shape[1:], field_name)
####


def _readonly_matrix(matrix: TableMatrix) -> TableMatrix:
  return tuple(tuple(float(value) for value in row) for row in matrix)
####


def _readonly_tensor(tensor: TableTensor) -> TableTensor:
  return tuple(_readonly_matrix(matrix) for matrix in tensor)
####


def _interpolate_1d(
    nodes: tuple[float, ...],
    values: tuple[float, ...],
    value: float,
    *,
    policy: LookupInterpolationPolicy,
    allow_extrapolation: bool,
    axis_name: str,
) -> float:
  if policy is LookupInterpolationPolicy.EXACT_ONLY:
    try:
      exact_index = nodes.index(value)
    except ValueError as error:
      raise ProductOutsideApplicabilityError(
        f'{axis_name} requires an exact table node'
      ) from error
    return values[exact_index]

  outside_domain = value < nodes[0] or value > nodes[-1]
  if outside_domain and not allow_extrapolation:
    raise ProductOutsideApplicabilityError(f'{axis_name} is outside the table domain')

  if policy is LookupInterpolationPolicy.NEAREST:
    nearest_index = min(range(len(nodes)), key=lambda index: (abs(nodes[index] - value), index))
    return values[nearest_index]

  if value <= nodes[0]:
    lower_index = 0
    upper_index = 1
    if value == nodes[0]:
      return values[0]
  elif value >= nodes[-1]:
    if value > nodes[-1] and not allow_extrapolation:
      raise ProductOutsideApplicabilityError('lookup value is above the table domain')
    if value == nodes[-1]:
      return values[-1]
    lower_index = len(nodes) - 2
    upper_index = len(nodes) - 1
  else:
    upper_index = bisect_right(nodes, value)
    lower_index = upper_index - 1
  fraction = (value - nodes[lower_index]) / (nodes[upper_index] - nodes[lower_index])
  if policy is LookupInterpolationPolicy.LOG_LINEAR:
    if any(item <= 0.0 for item in (values[lower_index], values[upper_index])):
      raise ProviderConfigurationError(
        f'log-linear interpolation requires strictly positive {axis_name} values'
      )
    return exp(
      log(values[lower_index])
      + fraction * (log(values[upper_index]) - log(values[lower_index]))
    )
  interpolated = values[lower_index] + fraction * (values[upper_index] - values[lower_index])
  if not isfinite(interpolated) or interpolated < 0.0:
    raise ProductOutsideApplicabilityError(
      f'{axis_name} interpolation produced a negative or non-finite value'
    )
  return interpolated
####


def _interpolate_table(
    direction_cosine: float,
    wavelength_m: float,
    definition: SignatureTableDefinition,
    matrix: TableMatrix,
    *,
    wavelength_policy: LookupInterpolationPolicy,
    angular_policy: LookupInterpolationPolicy,
    allow_extrapolation: bool,
) -> float:
  wavelength_values = tuple(
    _interpolate_1d(
      definition.wavelengths_m,
      row,
      wavelength_m,
      policy=wavelength_policy,
      allow_extrapolation=allow_extrapolation,
      axis_name='wavelength',
    )
    for row in matrix
  )
  return _interpolate_1d(
    definition.direction_cosine_nodes,
    wavelength_values,
    direction_cosine,
    policy=angular_policy,
    allow_extrapolation=allow_extrapolation,
    axis_name='direction cosine',
  )
####


def _interpolate_time_table(
    direction_cosine: float,
    wavelength_m: float,
    time_s: float,
    definition: SignatureTableDefinition,
    matrix: TableMatrix,
    matrix_by_time: TableTensor | None,
    *,
    allow_extrapolation: bool,
) -> float:
  if not definition.time_nodes_s:
    return _interpolate_table(
      direction_cosine,
      wavelength_m,
      definition,
      matrix,
      wavelength_policy=definition.wavelength_interpolation,
      angular_policy=definition.angular_interpolation,
      allow_extrapolation=allow_extrapolation,
    )
  if matrix_by_time is None:
    raise ProviderConfigurationError('time-varying signature table is missing time slices')
  values_by_time = tuple(
    _interpolate_table(
      direction_cosine,
      wavelength_m,
      definition,
      time_matrix,
      wavelength_policy=definition.wavelength_interpolation,
      angular_policy=definition.angular_interpolation,
      allow_extrapolation=allow_extrapolation,
    )
    for time_matrix in matrix_by_time
  )
  return _interpolate_1d(
    definition.time_nodes_s,
    values_by_time,
    time_s,
    policy=definition.time_interpolation,
    allow_extrapolation=allow_extrapolation,
    axis_name='snapshot time',
  )
####


def _semantic_definition_digest(definition: SignatureTableDefinition) -> str:
  payload = asdict(definition)
  payload.pop('asset_sha256', None)
  return canonical_digest(payload)


def _descriptor(configuration: SignatureTableConfiguration) -> ProviderDescriptor:
  extrapolation_policy = 'allow' if configuration.allow_extrapolation else 'reject'
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(SPECTRAL_RADIANT_INTENSITY_CAPABILITY,),
    provider_definition_schema_id='plume.signature.table-definition.v1',
    dynamic_state_schema_id='plume.signature.table-dynamic-state.v1',
    configuration_schema_id='plume.signature.table-configuration.v1',
    supported_morphologies=('axisymmetric-lookup',),
    deterministic=True,
    notes=(
      'definition-declared wavelength, direction-cosine, and optional time interpolation',
      f'extrapolation policy: {extrapolation_policy}',
    ),
  )
####


class SignatureTableProvider:
  """Deterministic lookup provider for unresolved directional intensity."""

  def __init__(self, configuration: SignatureTableConfiguration | None = None) -> None:
    self._configuration = configuration or SignatureTableConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: SignatureTableDefinition,
      configuration: SignatureTableConfiguration | None = None,
  ) -> 'SignatureTableSession':
    if not isinstance(definition, SignatureTableDefinition):
      raise ProviderConfigurationError('definition must be SignatureTableDefinition')
    selected_configuration = configuration or self._configuration
    if selected_configuration != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    if definition.time_nodes_s and selected_configuration.time_model is TimeModel.STEADY:
      raise ProviderConfigurationError(
        'time-varying signature tables require time_model=prescribed_transient'
      )
    return SignatureTableSession(self._descriptor, definition, selected_configuration)
  ####
####


class _SignatureTableEvaluator:
  def __init__(self, definition: SignatureTableDefinition, configuration: SignatureTableConfiguration) -> None:
    self._definition = definition
    self._configuration = configuration
    self._definition_digest = _semantic_definition_digest(definition)
    self._asset_digest = definition.asset_sha256 or self._definition_digest

  def _provenance_metadata(self) -> dict[str, str]:
    definition = self._definition
    time_domain = (
      f'[{definition.time_nodes_s[0]:g}, {definition.time_nodes_s[-1]:g}] s'
      if definition.time_nodes_s
      else 'static table; snapshot time does not select a table slice'
    )
    return {
      'asset_digest_kind': 'content_sha256' if definition.asset_sha256 is not None else 'definition_sha256',
      'asset_id': definition.asset_id,
      'coordinate_convention': 'direction cosine = dot(source_to_observer_direction, axis_direction)',
      'direction_frame_id': definition.frame_id,
      'direction_cosine_domain': (
        f'[{definition.direction_cosine_nodes[0]:g}, {definition.direction_cosine_nodes[-1]:g}]'
      ),
      'extrapolation_policy': 'allow' if self._configuration.allow_extrapolation else 'reject',
      'interpolation_angular': definition.angular_interpolation.value,
      'interpolation_time': definition.time_interpolation.value if definition.time_nodes_s else 'not_applicable',
      'interpolation_wavelength': definition.wavelength_interpolation.value,
      'operating_point_id': definition.operating_point_id,
      'time_domain': time_domain,
      'wavelength_domain_m': f'[{definition.wavelengths_m[0]:g}, {definition.wavelengths_m[-1]:g}]',
    }
  ####

  def evaluate(self, request: SpectralSignatureRequest, snapshot: SnapshotMetadata) -> SpectralSignatureResult:
    if request.direction_frame_id != self._definition.frame_id:
      raise ProductOutsideApplicabilityError(
        f'signature table supports direction frame {self._definition.frame_id!r}, '
        f'not {request.direction_frame_id!r}'
      )
    if request.operating_point_id is not None and request.operating_point_id != self._definition.operating_point_id:
      raise ProductOutsideApplicabilityError(
        f'signature table supports operating point {self._definition.operating_point_id!r}, '
        f'not {request.operating_point_id!r}'
      )
    wavelength_extrapolation = any(
        wavelength < self._definition.wavelengths_m[0] or wavelength > self._definition.wavelengths_m[-1]
        for wavelength in request.wavelengths_m
    )
    if wavelength_extrapolation and not self._configuration.allow_extrapolation:
      raise ProductOutsideApplicabilityError('requested wavelengths are outside the table domain')
    if self._definition.wavelength_interpolation is LookupInterpolationPolicy.EXACT_ONLY and any(
        wavelength not in self._definition.wavelengths_m for wavelength in request.wavelengths_m
    ):
      raise ProductOutsideApplicabilityError('requested wavelengths require exact table nodes')
    time_extrapolation = bool(
      self._definition.time_nodes_s
      and (
        snapshot.time_s < self._definition.time_nodes_s[0]
        or snapshot.time_s > self._definition.time_nodes_s[-1]
      )
    )
    if time_extrapolation and not self._configuration.allow_extrapolation:
      raise ProductOutsideApplicabilityError('snapshot time is outside the temporal table domain')
    if self._definition.time_nodes_s and self._definition.time_interpolation is LookupInterpolationPolicy.EXACT_ONLY:
      if snapshot.time_s not in self._definition.time_nodes_s:
        raise ProductOutsideApplicabilityError('snapshot time requires an exact table node')
    direction_cosines = tuple(
      sum(direction[axis] * self._definition.axis_direction[axis] for axis in range(3))
      for direction in request.source_to_observer_directions
    )
    angular_extrapolation = any(
      direction_cosine < self._definition.direction_cosine_nodes[0]
      or direction_cosine > self._definition.direction_cosine_nodes[-1]
      for direction_cosine in direction_cosines
    )
    invalid_indices = tuple(
      index for index, direction_cosine in enumerate(direction_cosines)
      if (
        not self._configuration.allow_extrapolation
        and (
          direction_cosine < self._definition.direction_cosine_nodes[0]
          or direction_cosine > self._definition.direction_cosine_nodes[-1]
        )
      )
      or (
        self._definition.angular_interpolation is LookupInterpolationPolicy.EXACT_ONLY
        and direction_cosine not in self._definition.direction_cosine_nodes
      )
    )
    if invalid_indices and not request.allow_partial_results:
      if angular_extrapolation and not self._configuration.allow_extrapolation:
        raise ProductOutsideApplicabilityError(
          f'{len(invalid_indices)} requested directions are outside the angular table domain'
        )
      raise ProductOutsideApplicabilityError(
        f'{len(invalid_indices)} requested directions require exact angular table nodes'
      )
    invalid_set = set(invalid_indices)
    values: list[tuple[float, ...]] = []
    validity: list[tuple[bool, ...]] = []
    statuses: list[SampleStatus] = []
    uncertainties: list[tuple[float, ...]] = []
    for index, direction_cosine in enumerate(direction_cosines):
      if index in invalid_set:
        values.append(tuple(0.0 for _ in request.wavelengths_m))
        validity.append(tuple(False for _ in request.wavelengths_m))
        if (
          self._definition.angular_interpolation is LookupInterpolationPolicy.EXACT_ONLY
          and direction_cosine not in self._definition.direction_cosine_nodes
        ):
          status_message = 'direction cosine does not match an exact lookup node'
        else:
          status_message = 'direction cosine is outside the lookup domain'
        statuses.append(SampleStatus(
          code=SampleStatusCode.OUTSIDE_APPLICABILITY,
          message=status_message,
        ))
        if self._definition.absolute_standard_uncertainty_w_sr_m is not None:
          uncertainties.append(tuple(0.0 for _ in request.wavelengths_m))
        continue
      values.append(tuple(
        _interpolate_time_table(
          direction_cosine,
          wavelength_m,
          snapshot.time_s,
          self._definition,
          self._definition.spectral_radiant_intensity_w_sr_m,
          self._definition.spectral_radiant_intensity_w_sr_m_by_time,
          allow_extrapolation=self._configuration.allow_extrapolation,
        )
        for wavelength_m in request.wavelengths_m
      ))
      validity.append(tuple(True for _ in request.wavelengths_m))
      statuses.append(SampleStatus(code=SampleStatusCode.OK))
      if self._definition.absolute_standard_uncertainty_w_sr_m is not None:
        uncertainties.append(tuple(
          _interpolate_time_table(
            direction_cosine,
            wavelength_m,
            snapshot.time_s,
            self._definition,
            self._definition.absolute_standard_uncertainty_w_sr_m,
            self._definition.absolute_standard_uncertainty_w_sr_m_by_time,
            allow_extrapolation=self._configuration.allow_extrapolation,
          )
          for wavelength_m in request.wavelengths_m
        ))
    request_digest = canonical_digest(request)
    extrapolation_used = wavelength_extrapolation or angular_extrapolation or time_extrapolation
    applicability_reasons: list[str] = []
    if invalid_indices:
      applicability_reasons.append('one or more directions were outside the lookup domain')
    if extrapolation_used:
      applicability_reasons.append('explicit extrapolation was used')
    metadata = ResultMetadata(
      capability=SPECTRAL_RADIANT_INTENSITY_CAPABILITY,
      result_id=canonical_digest({'snapshot': snapshot.snapshot_id, 'request': request_digest})[:24],
      request_digest_sha256=request_digest,
      snapshot=snapshot,
      output_frame_id=request.direction_frame_id,
      claims=ProductClaims(
        geometry=GeometryClaim.NOT_APPLICABLE,
        radiation=self._configuration.radiation_claim,
        time_model=self._configuration.time_model,
        derivation=Derivation.TABULATED,
        consistency=ConsistencyLevel.INDEPENDENT,
      ),
      applicability=ApplicabilityReport(
        status=ApplicabilityStatus.MARGINAL if (invalid_indices or extrapolation_used) else ApplicabilityStatus.INSIDE,
        reasons=tuple(applicability_reasons),
      ),
      provenance=ResultProvenance(
        model_lineage_id=self._definition_digest,
        provider_id=self._configuration.provider_id,
        provider_version=self._configuration.provider_version,
        configuration_digest_sha256=canonical_digest(self._configuration),
        asset_digests_sha256=(self._asset_digest,),
        metadata=self._provenance_metadata(),
      ),
      warnings=(
        'explicit table extrapolation enabled',
      ) if self._configuration.allow_extrapolation and extrapolation_used else (),
    )
    return SpectralSignatureResult(
      metadata=metadata,
      spectral_radiant_intensity=tuple(values),
      validity_mask=tuple(validity),
      direction_status=tuple(statuses),
      absolute_standard_uncertainty=tuple(uncertainties) if uncertainties else None,
    )
  ####
####


class SignatureTableSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: SignatureTableDefinition,
      configuration: SignatureTableConfiguration,
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
        'asset': _semantic_definition_digest(definition),
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
      raise ProviderClosedError('signature table session is closed')
    if not isfinite(time_s):
      raise ProviderConfigurationError('time_s must be finite')
    dynamic_digest = canonical_digest(dynamic_state)
    ambient_digest = canonical_digest(ambient_state)
    provider_digest = _semantic_definition_digest(self._definition)
    metadata = SnapshotMetadata(
      snapshot_id=canonical_digest({
        'session': self._metadata.session_id,
        'time_s': time_s,
        'dynamic': dynamic_digest,
        'ambient': ambient_digest,
        'provider': provider_digest,
        'source_pose': source_pose,
      })[:24],
      session_id=self._metadata.session_id,
      time_s=time_s,
      source_pose=source_pose,
      dynamic_state_digest_sha256=dynamic_digest,
      ambient_state_digest_sha256=ambient_digest,
      provider_state_digest_sha256=provider_digest,
    )
    evaluator = _SignatureTableEvaluator(self._definition, self._configuration)
    return ImmutableProductSnapshot(
      metadata=metadata,
      _evaluators={SPECTRAL_RADIANT_INTENSITY_CAPABILITY: evaluator},
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
