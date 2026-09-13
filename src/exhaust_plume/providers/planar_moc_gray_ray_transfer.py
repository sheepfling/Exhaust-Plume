"""Cell-wise gray ray transfer through a retained planar-MOC field.

This provider is a deliberately separate research lane.  It consumes a
renderer-neutral 2-D polygon field and caller-supplied optical properties for
each cell; it does not infer radiation from Mach, pressure, temperature, or
the sectioned-tube display envelope.  The planar field is treated as an
explicit slice extruded by a caller-provided depth for projected-area
integration.  No axisymmetric, curved-flow, chemistry, detector, FPA, or
external-validation claim is implied.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

from exhaust_plume.api.v1 import (
  ApplicabilityReport,
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ImmutableProductSnapshot,
  Pose,
  ProductClaims,
  ProviderClosedError,
  ProviderConfigurationError,
  ProviderDescriptor,
  ProductOutsideApplicabilityError,
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
from exhaust_plume.geometry.polygons import validate_polygon
from exhaust_plume.radiation.gray import HomogeneousSegment, compose_homogeneous_segments

__all__ = (
  'PlanarMocGrayRayTransferConfiguration',
  'PlanarMocGrayRayTransferDefinition',
  'PlanarMocGrayRayTransferProvider',
  'PlanarMocGrayRayTransferSession',
)


Vector2 = tuple[float, float]


def _axis(values: Sequence[float], field_name: str) -> tuple[float, ...]:
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


def _spectrum(values: Sequence[float], field_name: str) -> tuple[float, ...]:
  normalized = tuple(float(value) for value in values)
  if not normalized or not all(isfinite(value) and value >= 0.0 for value in normalized):
    raise ProviderConfigurationError(f'{field_name} must be finite and nonnegative')
  ####
  return normalized
####


def _interpolate(
    nodes: tuple[float, ...],
    values: tuple[float, ...],
    value: float,
) -> float:
  if value < nodes[0] or value > nodes[-1]:
    raise ProductOutsideApplicabilityError(
      'requested wavelength is outside the planar optical property domain'
    )
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


def _vector2(value: Sequence[float], field_name: str) -> Vector2:
  if len(value) != 2:
    raise ProviderConfigurationError(f'{field_name} must contain two coordinates')
  ####
  normalized = (float(value[0]), float(value[1]))
  if not all(isfinite(component) for component in normalized):
    raise ProviderConfigurationError(f'{field_name} must be finite')
  ####
  return normalized
####


def _cross(first: Vector2, second: Vector2) -> float:
  return first[0] * second[1] - first[1] * second[0]
####


def _dot(first: Vector2, second: Vector2) -> float:
  return first[0] * second[0] + first[1] * second[1]
####


def _point_on_segment(point: Vector2, first: Vector2, second: Vector2, tolerance: float) -> bool:
  edge = (second[0] - first[0], second[1] - first[1])
  relative = (point[0] - first[0], point[1] - first[1])
  if abs(_cross(edge, relative)) > tolerance:
    return False
  ####
  return (
    min(first[0], second[0]) - tolerance <= point[0] <= max(first[0], second[0]) + tolerance
    and min(first[1], second[1]) - tolerance <= point[1] <= max(first[1], second[1]) + tolerance
  )
####


def _point_in_polygon(point: Vector2, polygon: tuple[Vector2, ...], tolerance: float) -> bool:
  inside = False
  for first, second in zip(polygon, (*polygon[1:], polygon[0])):
    if _point_on_segment(point, first, second, tolerance):
      return True
    ####
    first_above = first[1] > point[1]
    second_above = second[1] > point[1]
    if first_above == second_above:
      continue
    ####
    crossing_x = first[0] + (point[1] - first[1]) * (second[0] - first[0]) / (second[1] - first[1])
    if point[0] < crossing_x:
      inside = not inside
    ####
  ####
  return inside
####


def _unique_sorted(values: Sequence[float], tolerance: float) -> tuple[float, ...]:
  ordered = sorted(float(value) for value in values)
  unique: list[float] = []
  for value in ordered:
    if not unique or value - unique[-1] > tolerance:
      unique.append(value)
    else:
      unique[-1] = 0.5 * (unique[-1] + value)
    ####
  ####
  return tuple(unique)
####


def _line_polygon_intervals(
    origin: Vector2,
    direction: Vector2,
    polygon: tuple[Vector2, ...],
    t_min: float,
    t_max: float,
    tolerance: float,
) -> tuple[tuple[float, float], ...]:
  """Return positive ray intervals inside one simple polygon.

  The retained MOC cells are normally convex quadrilaterals, but this
  edge-crossing implementation also handles simple non-convex cells without
  converting the field to an envelope.  Collinear edge endpoints are kept as
  break points so a ray lying on a cell boundary does not create an
  unbounded or guessed interval.
  """

  parameters: list[float] = [t_min, t_max]
  for first, second in zip(polygon, (*polygon[1:], polygon[0])):
    edge = (second[0] - first[0], second[1] - first[1])
    relative = (first[0] - origin[0], first[1] - origin[1])
    denominator = _cross(direction, edge)
    if abs(denominator) <= tolerance:
      if abs(_cross(relative, direction)) <= tolerance:
        for vertex in (first, second):
          projected = _dot(
            (vertex[0] - origin[0], vertex[1] - origin[1]),
            direction,
          )
          if t_min - tolerance <= projected <= t_max + tolerance:
            parameters.append(min(t_max, max(t_min, projected)))
        ####
      ####
      continue
    ####
    edge_fraction = _cross(relative, direction) / denominator
    if -tolerance <= edge_fraction <= 1.0 + tolerance:
      crossing = _cross(relative, edge) / denominator
      if t_min - tolerance <= crossing <= t_max + tolerance:
        parameters.append(min(t_max, max(t_min, crossing)))
      ####
    ####
  ####
  parameters_sorted = _unique_sorted(parameters, tolerance)
  intervals: list[tuple[float, float]] = []
  for first, second in zip(parameters_sorted, parameters_sorted[1:]):
    if second - first <= tolerance:
      continue
    ####
    midpoint = (
      origin[0] + 0.5 * (first + second) * direction[0],
      origin[1] + 0.5 * (first + second) * direction[1],
    )
    if _point_in_polygon(midpoint, polygon, tolerance):
      intervals.append((first, second))
    ####
  ####
  return tuple(intervals)
####


@dataclass(frozen=True, slots=True)
class PlanarMocGrayRayTransferDefinition:
  """A polygonal planar field plus explicit per-cell gray optical inputs."""

  frame_id: str
  polygons_xr_m: tuple[tuple[Vector2, ...], ...]
  wavelengths_m: tuple[float, ...]
  source_function_w_sr_m_by_cell: tuple[tuple[float, ...], ...]
  absorption_coefficient_per_m_by_cell: tuple[tuple[float, ...], ...]
  extrusion_depth_m: float = 1.0
  field_id: str = 'planar-moc-field'
  asset_id: str = 'planar-moc-gray-ray-transfer-definition'
  asset_sha256: str | None = None

  def __post_init__(self) -> None:
    if not self.frame_id or not self.field_id or not self.asset_id:
      raise ProviderConfigurationError('planar definition identity fields must not be empty')
    ####
    polygons: list[tuple[Vector2, ...]] = []
    for index, raw_polygon in enumerate(self.polygons_xr_m):
      polygon = tuple(
        _vector2(point, f'polygons_xr_m[{index}] vertex')
        for point in raw_polygon
      )
      if len(polygon) < 3:
        raise ProviderConfigurationError('planar field polygons require at least three vertices')
      ####
      validation = validate_polygon(polygon)
      if validation.status.value != 'valid':
        raise ProviderConfigurationError(
          f'planar field polygon {index} is invalid: {validation.message}'
        )
      ####
      polygons.append(polygon)
    ####
    if not polygons:
      raise ProviderConfigurationError('planar field requires at least one polygon')
    ####
    wavelengths = _axis(self.wavelengths_m, 'wavelengths_m')
    sources = tuple(
      _spectrum(spectrum, f'source_function_w_sr_m_by_cell[{index}]')
      for index, spectrum in enumerate(self.source_function_w_sr_m_by_cell)
    )
    absorptions = tuple(
      _spectrum(spectrum, f'absorption_coefficient_per_m_by_cell[{index}]')
      for index, spectrum in enumerate(self.absorption_coefficient_per_m_by_cell)
    )
    if len(sources) != len(polygons) or len(absorptions) != len(polygons):
      raise ProviderConfigurationError(
        'per-cell optical property arrays must match polygon count'
      )
    ####
    if any(len(spectrum) != len(wavelengths) for spectrum in (*sources, *absorptions)):
      raise ProviderConfigurationError('per-cell optical property arrays must match wavelengths_m')
    ####
    depth = float(self.extrusion_depth_m)
    if not isfinite(depth) or depth <= 0.0:
      raise ProviderConfigurationError('extrusion_depth_m must be finite and positive')
    ####
    if self.asset_sha256 is not None and (
        len(self.asset_sha256) != 64
        or any(character not in '0123456789abcdefABCDEF' for character in self.asset_sha256)
    ):
      raise ProviderConfigurationError('asset_sha256 must be a 64-character hexadecimal digest')
    ####
    object.__setattr__(self, 'polygons_xr_m', tuple(polygons))
    object.__setattr__(self, 'wavelengths_m', wavelengths)
    object.__setattr__(self, 'source_function_w_sr_m_by_cell', sources)
    object.__setattr__(self, 'absorption_coefficient_per_m_by_cell', absorptions)
    object.__setattr__(self, 'extrusion_depth_m', depth)
    object.__setattr__(self, 'asset_sha256', self.asset_sha256.lower() if self.asset_sha256 else None)
  ####
####


@dataclass(frozen=True, slots=True)
class PlanarMocGrayRayTransferConfiguration:
  """Provider identity and polygon/ray intersection policy."""

  provider_id: str = 'plume.planar-moc-gray-ray-transfer'
  provider_version: str = '1.0.0'
  intersection_tolerance_m: float = 1.0e-10

  def __post_init__(self) -> None:
    if not self.provider_id or not self.provider_version:
      raise ProviderConfigurationError('planar provider identity must not be empty')
    ####
    if not isfinite(self.intersection_tolerance_m) or self.intersection_tolerance_m <= 0.0:
      raise ProviderConfigurationError('intersection_tolerance_m must be finite and positive')
    ####
  ####
####


def _descriptor(configuration: PlanarMocGrayRayTransferConfiguration) -> ProviderDescriptor:
  return ProviderDescriptor(
    provider_id=configuration.provider_id,
    provider_version=configuration.provider_version,
    supported_capabilities=(SPECTRAL_RAY_TRANSFER_CAPABILITY,),
    provider_definition_schema_id='plume.optical.planar-moc-gray-ray-transfer-definition.v1',
    dynamic_state_schema_id='plume.optical.planar-moc-gray-ray-transfer-dynamic-state.v1',
    configuration_schema_id='plume.optical.planar-moc-gray-ray-transfer-configuration.v1',
    supported_morphologies=('planar-moc-field',),
    deterministic=True,
    notes=(
      'cell-wise gray transfer through an explicit 2-D planar-MOC polygon field',
      'the planar field is extruded by a caller-supplied depth for projected-area integration',
      'per-cell source and absorption are explicit inputs; no flow-to-radiation inference',
      'research-only planar slice; no axisymmetric, curved-flow, chemistry, detector, or FPA claim',
      'fidelity profile: planar-moc-gray-transfer-v1',
    ),
  )
####


class _PlanarMocGrayRayTransferEvaluator:
  def __init__(
      self,
      definition: PlanarMocGrayRayTransferDefinition,
      configuration: PlanarMocGrayRayTransferConfiguration,
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
      raise ProviderConfigurationError(
        f'planar provider supports frame {self._definition.frame_id!r}, not {request.ray_frame_id!r}'
      )
    ####
    source_cells = tuple(
      tuple(
        _interpolate(self._definition.wavelengths_m, spectrum, wavelength)
        for wavelength in request.wavelengths_m
      )
      for spectrum in self._definition.source_function_w_sr_m_by_cell
    )
    absorption_cells = tuple(
      tuple(
        _interpolate(self._definition.wavelengths_m, spectrum, wavelength)
        for wavelength in request.wavelengths_m
      )
      for spectrum in self._definition.absorption_coefficient_per_m_by_cell
    )
    ####
    tolerance = self._configuration.intersection_tolerance_m
    source_matrix: list[tuple[float, ...]] = []
    transmittance_matrix: list[tuple[float, ...]] = []
    optical_depth_matrix: list[tuple[float, ...]] = []
    validity_matrix: list[tuple[bool, ...]] = []
    statuses: list[SampleStatus] = []
    hit_mask: list[bool] = []
    intersection_intervals: list[tuple[float, float] | None] = []
    invalid_ray_count = 0
    for origin_raw, direction_raw, t_min, t_max in zip(
        request.ray_origins_m,
        request.ray_directions,
        request.ray_t_min_m,
        request.ray_t_max_m,
    ):
      if abs(origin_raw[2]) > tolerance or abs(direction_raw[2]) > tolerance:
        invalid_ray_count += 1
        source_matrix.append((0.0,) * len(request.wavelengths_m))
        transmittance_matrix.append((1.0,) * len(request.wavelengths_m))
        optical_depth_matrix.append((0.0,) * len(request.wavelengths_m))
        validity_matrix.append((False,) * len(request.wavelengths_m))
        statuses.append(SampleStatus(
          code=SampleStatusCode.OUTSIDE_APPLICABILITY,
          message='planar-MOC transfer requires rays and origins in the declared x-r plane',
        ))
        hit_mask.append(False)
        intersection_intervals.append(None)
        continue
      ####
      origin = (float(origin_raw[0]), float(origin_raw[1]))
      direction = (float(direction_raw[0]), float(direction_raw[1]))
      raw_intervals: list[tuple[float, float, int]] = []
      for cell_index, polygon in enumerate(self._definition.polygons_xr_m):
        raw_intervals.extend(
          (enter, exit, cell_index)
          for enter, exit in _line_polygon_intervals(
            origin,
            direction,
            polygon,
            float(t_min),
            float(t_max),
            tolerance,
          )
        )
      ####
      raw_intervals.sort(key=lambda item: (item[0], item[1], item[2]))
      distinct_intervals: list[tuple[float, float, int]] = []
      for interval in raw_intervals:
        if distinct_intervals and (
            abs(interval[0] - distinct_intervals[-1][0]) <= tolerance
            and abs(interval[1] - distinct_intervals[-1][1]) <= tolerance
        ):
          # A ray exactly on a shared cell edge has two equal, measure-zero
          # representations.  Keep the deterministic lower-index cell and
          # continue to reject positive-length overlapping intervals.
          continue
        ####
        distinct_intervals.append(interval)
      ####
      raw_intervals = distinct_intervals
      if any(
        current[0] < previous[1] - tolerance
        for previous, current in zip(raw_intervals, raw_intervals[1:])
      ):
        invalid_ray_count += 1
        source_matrix.append((0.0,) * len(request.wavelengths_m))
        transmittance_matrix.append((1.0,) * len(request.wavelengths_m))
        optical_depth_matrix.append((0.0,) * len(request.wavelengths_m))
        validity_matrix.append((False,) * len(request.wavelengths_m))
        statuses.append(SampleStatus(
          code=SampleStatusCode.INVALID_SAMPLE,
          message='planar-MOC cells overlap along the requested ray; transfer is undefined',
        ))
        hit_mask.append(False)
        intersection_intervals.append(None)
        continue
      ####
      if not raw_intervals:
        source_matrix.append((0.0,) * len(request.wavelengths_m))
        transmittance_matrix.append((1.0,) * len(request.wavelengths_m))
        optical_depth_matrix.append((0.0,) * len(request.wavelengths_m))
        validity_matrix.append((True,) * len(request.wavelengths_m))
        statuses.append(SampleStatus(code=SampleStatusCode.OK))
        hit_mask.append(False)
        intersection_intervals.append(None)
        continue
      ####
      segments = tuple(
        HomogeneousSegment(
          source_cells[cell_index],
          absorption_cells[cell_index],
          exit - enter,
        )
        for enter, exit, cell_index in raw_intervals
      )
      transfer = compose_homogeneous_segments(segments)
      source_matrix.append(transfer.source_radiance_w_sr_m)
      transmittance_matrix.append(transfer.background_transmittance)
      optical_depth_matrix.append(transfer.optical_depth)
      validity_matrix.append((True,) * len(request.wavelengths_m))
      statuses.append(SampleStatus(code=SampleStatusCode.OK))
      hit_mask.append(True)
      intersection_intervals.append((raw_intervals[0][0], raw_intervals[-1][1]))
    ####
    request_digest = canonical_digest(request)
    applicability_status = (
      ApplicabilityStatus.MARGINAL
      if invalid_ray_count
      else ApplicabilityStatus.INSIDE
    )
    applicability_reasons = (
      ('one or more rays were outside the declared planar x-r transfer domain',)
      if invalid_ray_count
      else ()
    )
    metadata = ResultMetadata(
      capability=SPECTRAL_RAY_TRANSFER_CAPABILITY,
      result_id=canonical_digest({'snapshot': snapshot.snapshot_id, 'request': request_digest})[:24],
      request_digest_sha256=request_digest,
      snapshot=snapshot,
      output_frame_id=request.ray_frame_id,
      claims=ProductClaims(
        geometry=GeometryClaim.ILLUSTRATIVE,
        radiation=RadiationClaim.GRAY_APPROXIMATE,
        time_model=TimeModel.STEADY,
        derivation=Derivation.NATIVE,
        consistency=ConsistencyLevel.INDEPENDENT,
      ),
      applicability=ApplicabilityReport(
        status=applicability_status,
        reasons=applicability_reasons,
      ),
      provenance=ResultProvenance(
        model_lineage_id=self._lineage_id,
        provider_id=self._configuration.provider_id,
        provider_version=self._configuration.provider_version,
        configuration_digest_sha256=canonical_digest(self._configuration),
        asset_digests_sha256=(self._definition.asset_sha256,) if self._definition.asset_sha256 else (),
        metadata={
          'field_id': self._definition.field_id,
          'field_geometry': 'retained planar-MOC polygons in x-r coordinates',
          'extrusion_depth_m': str(self._definition.extrusion_depth_m),
          'projected_area_semantics': 'ray transverse width multiplied by explicit slice extrusion depth',
          'optical_property_mode': 'explicit-cell-wise-gray',
          'cell_count': str(len(self._definition.polygons_xr_m)),
          'source_function_convention': 'L_out = L_in*T + S*(1-T)',
          'claim_ceiling': 'research-only planar slice; no resolved 3-D radiation or production source claim',
        },
      ),
      warnings=(
        'planar-MOC transfer is a research-only 2-D slice operator with caller-supplied per-cell gray optics',
      ),
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


class PlanarMocGrayRayTransferProvider:
  """Provider for explicit cell-wise gray transfer through a planar-MOC field."""

  def __init__(self, configuration: PlanarMocGrayRayTransferConfiguration | None = None) -> None:
    self._configuration = configuration or PlanarMocGrayRayTransferConfiguration()
    self._descriptor = _descriptor(self._configuration)
  ####

  @property
  def descriptor(self) -> ProviderDescriptor:
    return self._descriptor
  ####

  def create_session(
      self,
      *,
      definition: PlanarMocGrayRayTransferDefinition,
      configuration: PlanarMocGrayRayTransferConfiguration | None = None,
  ) -> 'PlanarMocGrayRayTransferSession':
    if not isinstance(definition, PlanarMocGrayRayTransferDefinition):
      raise ProviderConfigurationError(
        'definition must be PlanarMocGrayRayTransferDefinition'
      )
    ####
    selected = configuration or self._configuration
    if selected != self._configuration:
      raise ProviderConfigurationError('session configuration must match provider configuration')
    ####
    return PlanarMocGrayRayTransferSession(self._descriptor, definition, selected)
  ####
####


class PlanarMocGrayRayTransferSession:
  def __init__(
      self,
      descriptor: ProviderDescriptor,
      definition: PlanarMocGrayRayTransferDefinition,
      configuration: PlanarMocGrayRayTransferConfiguration,
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
      raise ProviderClosedError('planar-MOC gray ray-transfer session is closed')
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
        SPECTRAL_RAY_TRANSFER_CAPABILITY: _PlanarMocGrayRayTransferEvaluator(
          self._definition,
          self._configuration,
        ),
      },
    )
  ####

  def close(self) -> None:
    self._closed = True
  ####
####
