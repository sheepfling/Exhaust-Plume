"""Standardized visualization adapters for the five plume-model lanes.

The public visualization product remains the renderer-neutral
``plume.visual.sectioned-tube@1`` result.  This module adds the evaluation
seam around that product: every model lane is converted to the same oriented
section stations, unit-bearing channel descriptions, optional region fields,
and boundary paths.  Claim metadata is retained beside the display geometry
so a renderer cannot accidentally present a lower-fidelity envelope as a
higher-fidelity solution.

The bundle is an evaluation adapter, not a new physics or product capability.
In particular, the planar MOC lane keeps its 2-D field polygons and boundary
paths in addition to its optional sectioned-tube display envelope.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite, sqrt
import re
from typing import Any, Literal, TypeAlias, cast

import numpy as np

from exhaust_plume.api.v1 import (
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  ProviderConfigurationError,
  RadiationClaim,
  SnapshotMetadata,
  TimeModel,
  VisualSection,
  VisualSectionedTubeRequest,
  VisualSectionedTubeResult,
  canonical_digest,
)
from exhaust_plume.models.integral.straight import IntegralStraightResult
from exhaust_plume.models.plume.curved_plume_closures import CurvedPlumeResult
from exhaust_plume.models.plume.curved_plume_geometry import calculateRotationMinimizingFrames
from exhaust_plume.models.shock_cells.contracts import (
  AnalyticalFirstCellSolution,
  ShockCellSolveResult,
)
from exhaust_plume.models.shock_train.contracts import ShockTrainResult
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  _evaluate_prescribed_definition,
)

__all__ = (
  'MODEL_VISUALIZATION_SCHEMA',
  'MODEL_VISUALIZATION_LANES',
  'ModelVisualizationClaims',
  'ModelVisualizationLane',
  'ModelVisualChannel',
  'ModelVisualField',
  'ModelVisualPath',
  'StandardizedModelVisualization',
  'evaluate_standardized_model_visualization',
  'standardize_all_model_visualizations',
  'standardize_model_result',
  'standardize_model_visualization',
)


MODEL_VISUALIZATION_SCHEMA = 'plume.visual.model-lane@1'


class ModelVisualizationLane(str, Enum):
  """The five computational model lanes exposed by the evaluation tool."""

  BASIC_SHOCK_CELL = 'shock-cell-basic-v1'
  REDUCED_ORDER_SHOCK_TRAIN = 'shock-cell-reduced-order-v1'
  STRAIGHT_INTEGRAL = 'straight-integral-v1'
  CURVED_INTEGRAL = 'washed-integral-v1'
  PLANAR_MOC = 'planar-moc-primitives-v1'


MODEL_VISUALIZATION_LANES = (
  ModelVisualizationLane.BASIC_SHOCK_CELL,
  ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN,
  ModelVisualizationLane.STRAIGHT_INTEGRAL,
  ModelVisualizationLane.CURVED_INTEGRAL,
  ModelVisualizationLane.PLANAR_MOC,
)

Vector2: TypeAlias = tuple[float, float]
Vector3: TypeAlias = tuple[float, float, float]
Scalar: TypeAlias = float | None
DiagnosticValue: TypeAlias = bool | float | int | str | None

_CHANNEL_NAME = re.compile(r'^[a-z0-9][a-z0-9_-]*$')
_AXIAL_SECTION_QUATERNION = (0.5, 0.5, 0.5, 0.5)


def _finite(name: str, value: object) -> float:
  try:
    numeric = float(cast(Any, value))
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  if not isfinite(numeric):
    raise ValueError(f'{name} must be finite')
  return numeric


def _vector2(name: str, value: Sequence[float]) -> Vector2:
  if len(value) != 2:
    raise ValueError(f'{name} must contain two coordinates')
  return (_finite(f'{name}[0]', value[0]), _finite(f'{name}[1]', value[1]))


def _vector3(name: str, value: Sequence[float]) -> Vector3:
  if len(value) != 3:
    raise ValueError(f'{name} must contain three coordinates')
  return (
    _finite(f'{name}[0]', value[0]),
    _finite(f'{name}[1]', value[1]),
    _finite(f'{name}[2]', value[2]),
  )


def _status_value(result: object) -> str:
  status = getattr(result, 'status', None)
  if status is not None:
    value = getattr(status, 'value', status)
    return str(value)
  termination = getattr(result, 'termination_reason', None)
  if termination is not None:
    value = getattr(termination, 'value', termination)
    return str(value)
  return 'available'


def _coerce_lane(value: ModelVisualizationLane | str) -> ModelVisualizationLane:
  if isinstance(value, ModelVisualizationLane):
    return value
  try:
    return ModelVisualizationLane(str(value))
  except ValueError as error:
    raise ValueError(f'unknown model visualization lane: {value!r}') from error


def _normalized(values: Sequence[float], *, zero_value: float = 0.0) -> tuple[float, ...]:
  finite_values = tuple(_finite('normalized value', value) for value in values)
  maximum = max(finite_values, default=0.0)
  if maximum <= 0.0:
    return tuple(zero_value for _ in finite_values)
  return tuple(min(1.0, max(0.0, value / maximum)) for value in finite_values)


def _sample_indices(total_count: int, maximum_count: int) -> tuple[int, ...]:
  if total_count < 2:
    raise ValueError('a visualization sequence requires at least two samples')
  if isinstance(maximum_count, bool) or maximum_count < 2:
    raise ValueError('section_count must be an integer at least two')
  if total_count <= maximum_count:
    return tuple(range(total_count))
  return tuple(
    int(round(index * (total_count - 1) / (maximum_count - 1)))
    for index in range(maximum_count)
  )


def _clip_sequence(
  axis: Sequence[float],
  *,
  maximum_extent_m: float | None,
) -> tuple[int, ...]:
  values = tuple(_finite('axis value', value) for value in axis)
  if len(values) < 2:
    raise ValueError('a visualization sequence requires at least two samples')
  if maximum_extent_m is None:
    return tuple(range(len(values)))
  extent = _finite('maximum_axial_extent_m', maximum_extent_m)
  if extent <= 0.0:
    raise ValueError('maximum_axial_extent_m must be positive')
  limit = values[0] + extent
  indices = tuple(index for index, value in enumerate(values) if value <= limit + 1.0e-12)
  if len(indices) < 2:
    raise ValueError('maximum_axial_extent_m leaves fewer than two visualization samples')
  return indices


def _quaternion_from_frames(
  normal: Sequence[float],
  binormal: Sequence[float],
  tangent: Sequence[float],
) -> tuple[float, float, float, float]:
  """Return a unit quaternion whose local x/y/z axes map to the frame."""

  # The frame vectors are the columns of the output rotation matrix.
  matrix = np.asarray((normal, binormal, tangent), dtype=float).T
  trace = float(np.trace(matrix))
  if trace > 0.0:
    scale = 2.0 * sqrt(trace + 1.0)
    quaternion = (
      (matrix[2, 1] - matrix[1, 2]) / scale,
      (matrix[0, 2] - matrix[2, 0]) / scale,
      (matrix[1, 0] - matrix[0, 1]) / scale,
      0.25 * scale,
    )
  else:
    diagonal = np.diag(matrix)
    largest = int(np.argmax(diagonal))
    if largest == 0:
      scale = 2.0 * sqrt(max(1.0e-30, 1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2]))
      quaternion = (
        0.25 * scale,
        (matrix[0, 1] + matrix[1, 0]) / scale,
        (matrix[0, 2] + matrix[2, 0]) / scale,
        (matrix[2, 1] - matrix[1, 2]) / scale,
      )
    elif largest == 1:
      scale = 2.0 * sqrt(max(1.0e-30, 1.0 + matrix[1, 1] - matrix[0, 0] - matrix[2, 2]))
      quaternion = (
        (matrix[0, 1] + matrix[1, 0]) / scale,
        0.25 * scale,
        (matrix[1, 2] + matrix[2, 1]) / scale,
        (matrix[0, 2] - matrix[2, 0]) / scale,
      )
    else:
      scale = 2.0 * sqrt(max(1.0e-30, 1.0 + matrix[2, 2] - matrix[0, 0] - matrix[1, 1]))
      quaternion = (
        (matrix[0, 2] + matrix[2, 0]) / scale,
        (matrix[1, 2] + matrix[2, 1]) / scale,
        0.25 * scale,
        (matrix[1, 0] - matrix[0, 1]) / scale,
      )
  norm = sqrt(sum(component * component for component in quaternion))
  if not isfinite(norm) or norm <= 0.0:
    raise ValueError('visual frame produced an invalid quaternion')
  normalized = tuple(component / norm for component in quaternion)
  return normalized  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class ModelVisualizationClaims:
  """Fidelity and promotion metadata displayed with one model lane."""

  model_fidelity: str
  validation_level: str
  geometry_claim: GeometryClaim
  production_claim_allowed: bool
  claim_notes: tuple[str, ...] = ()

  def __post_init__(self) -> None:
    if not self.model_fidelity or not self.validation_level:
      raise ValueError('model_fidelity and validation_level must not be empty')
    if not isinstance(self.geometry_claim, GeometryClaim):
      raise TypeError('geometry_claim must be a GeometryClaim')
    if not isinstance(self.production_claim_allowed, bool):
      raise TypeError('production_claim_allowed must be a bool')
    object.__setattr__(self, 'claim_notes', tuple(str(note) for note in self.claim_notes))

  def model_dump(self) -> dict[str, object]:
    return {
      'model_fidelity': self.model_fidelity,
      'validation_level': self.validation_level,
      'geometry_claim': self.geometry_claim.value,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_notes': list(self.claim_notes),
    }


@dataclass(frozen=True, slots=True)
class ModelVisualChannel:
  """A unit-bearing scalar trace aligned with section stations."""

  channel_id: str
  semantic: str
  unit: str
  values: tuple[float, ...]
  association: Literal['section'] = 'section'

  def __post_init__(self) -> None:
    if not _CHANNEL_NAME.fullmatch(self.channel_id):
      raise ValueError(f'invalid model visualization channel: {self.channel_id!r}')
    if not self.semantic or not self.unit:
      raise ValueError('model visualization channel semantic and unit are required')
    if self.association != 'section':
      raise ValueError('model visualization channels must be section-associated')
    values = tuple(_finite(f'{self.channel_id} value', value) for value in self.values)
    if len(values) < 2:
      raise ValueError('model visualization channels require at least two samples')
    object.__setattr__(self, 'values', values)

  def model_dump(self) -> dict[str, object]:
    return {
      'channel_id': self.channel_id,
      'semantic': self.semantic,
      'unit': self.unit,
      'association': self.association,
      'values': list(self.values),
    }


@dataclass(frozen=True, slots=True)
class ModelVisualPath:
  """A named 3-D boundary or centerline path for overlays."""

  path_id: str
  semantic: str
  points_m: tuple[Vector3, ...]

  def __post_init__(self) -> None:
    if not self.path_id or not self.semantic:
      raise ValueError('model visualization paths require an id and semantic')
    points = tuple(_vector3('path point', point) for point in self.points_m)
    if len(points) < 2:
      raise ValueError('model visualization paths require at least two points')
    object.__setattr__(self, 'points_m', points)

  def model_dump(self) -> dict[str, object]:
    return {
      'path_id': self.path_id,
      'semantic': self.semantic,
      'points_m': [list(point) for point in self.points_m],
    }


@dataclass(frozen=True, slots=True)
class ModelVisualField:
  """Polygonal 2-D region data retained for field-aware views."""

  field_id: str
  semantic: str
  polygons_xr_m: tuple[tuple[Vector2, ...], ...]
  channels: Mapping[str, tuple[Scalar, ...]] = field(default_factory=dict)
  channel_units: Mapping[str, str] = field(default_factory=dict)
  channel_semantics: Mapping[str, str] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not self.field_id or not self.semantic:
      raise ValueError('model visualization fields require an id and semantic')
    polygons = tuple(
      tuple(_vector2('field polygon point', point) for point in polygon)
      for polygon in self.polygons_xr_m
    )
    if not polygons or any(len(polygon) < 3 for polygon in polygons):
      raise ValueError('model visualization fields require nondegenerate polygons')
    normalized_channels: dict[str, tuple[Scalar, ...]] = {}
    normalized_units: dict[str, str] = {}
    normalized_semantics: dict[str, str] = {}
    for channel_id, values in self.channels.items():
      if not _CHANNEL_NAME.fullmatch(channel_id):
        raise ValueError(f'invalid field channel: {channel_id!r}')
      normalized_values = tuple(
        None if value is None else _finite(f'{channel_id} field value', value)
        for value in values
      )
      if len(normalized_values) != len(polygons):
        raise ValueError(f'field channel {channel_id!r} must match polygon count')
      normalized_channels[channel_id] = normalized_values
      unit = str(self.channel_units.get(channel_id, '1'))
      semantic = str(self.channel_semantics.get(channel_id, channel_id))
      if not unit or not semantic:
        raise ValueError(f'field channel {channel_id!r} requires a unit and semantic')
      normalized_units[channel_id] = unit
      normalized_semantics[channel_id] = semantic
    unknown_units = set(self.channel_units) - set(normalized_channels)
    unknown_semantics = set(self.channel_semantics) - set(normalized_channels)
    if unknown_units or unknown_semantics:
      raise ValueError('field channel metadata must describe declared channels only')
    object.__setattr__(self, 'polygons_xr_m', polygons)
    object.__setattr__(self, 'channels', normalized_channels)
    object.__setattr__(self, 'channel_units', normalized_units)
    object.__setattr__(self, 'channel_semantics', normalized_semantics)

  def model_dump(self) -> dict[str, object]:
    return {
      'field_id': self.field_id,
      'semantic': self.semantic,
      'polygons_xr_m': [[list(point) for point in polygon] for polygon in self.polygons_xr_m],
      'channels': {
        channel_id: {
          'semantic': self.channel_semantics[channel_id],
          'unit': self.channel_units[channel_id],
          'values': list(values),
        }
        for channel_id, values in self.channels.items()
      },
    }


@dataclass(frozen=True, slots=True)
class StandardizedModelVisualization:
  """One lane converted to the common renderer-neutral evaluation shape."""

  lane: ModelVisualizationLane
  model_id: str
  model_version: str
  source_status: str
  applicability_status: ApplicabilityStatus
  applicability_reasons: tuple[str, ...]
  claims: ModelVisualizationClaims
  sectioned_tube: PrescribedVisualDefinition
  section_channels: tuple[ModelVisualChannel, ...]
  paths: tuple[ModelVisualPath, ...] = ()
  fields: tuple[ModelVisualField, ...] = ()
  diagnostics: Mapping[str, DiagnosticValue] = field(default_factory=dict)
  warnings: tuple[str, ...] = ()
  schema: str = MODEL_VISUALIZATION_SCHEMA

  def __post_init__(self) -> None:
    if self.schema != MODEL_VISUALIZATION_SCHEMA:
      raise ValueError(f'unsupported model visualization schema: {self.schema!r}')
    if not isinstance(self.lane, ModelVisualizationLane):
      raise TypeError('lane must be a ModelVisualizationLane')
    if not self.model_id or not self.model_version or not self.source_status:
      raise ValueError('model identity and source status are required')
    if not isinstance(self.applicability_status, ApplicabilityStatus):
      raise TypeError('applicability_status must be an ApplicabilityStatus')
    if self.applicability_status is ApplicabilityStatus.OUTSIDE and not self.applicability_reasons:
      raise ValueError('outside applicability requires reasons')
    section_count = len(self.sectioned_tube.sections)
    channels = tuple(self.section_channels)
    if len({channel.channel_id for channel in channels}) != len(channels):
      raise ValueError('section channel IDs must be unique')
    definition_channels = set(self.sectioned_tube.channels)
    if definition_channels != {channel.channel_id for channel in channels}:
      raise ValueError('section channel metadata must match the sectioned-tube channels')
    if any(len(channel.values) != section_count for channel in channels):
      raise ValueError('section channel values must match section count')
    paths = tuple(self.paths)
    fields = tuple(self.fields)
    if len({path.path_id for path in paths}) != len(paths):
      raise ValueError('model visualization path IDs must be unique')
    if len({field.field_id for field in fields}) != len(fields):
      raise ValueError('model visualization field IDs must be unique')
    diagnostics: dict[str, DiagnosticValue] = {}
    for key, value in self.diagnostics.items():
      if not key:
        raise ValueError('diagnostic keys must not be empty')
      if isinstance(value, float) and not isfinite(value):
        raise ValueError(f'diagnostic {key!r} must be finite')
      if not isinstance(value, (bool, float, int, str)) and value is not None:
        raise ValueError(f'diagnostic {key!r} must be a JSON scalar')
      diagnostics[str(key)] = value
    object.__setattr__(self, 'section_channels', channels)
    object.__setattr__(self, 'paths', paths)
    object.__setattr__(self, 'fields', fields)
    object.__setattr__(self, 'applicability_reasons', tuple(str(reason) for reason in self.applicability_reasons))
    object.__setattr__(self, 'diagnostics', diagnostics)
    object.__setattr__(self, 'warnings', tuple(str(warning) for warning in self.warnings))

  @property
  def lane_id(self) -> str:
    return self.lane.value

  @property
  def frame_id(self) -> str:
    return self.sectioned_tube.frame_id

  def model_dump(self) -> dict[str, object]:
    """Return a JSON-compatible evaluation artifact."""

    return {
      'schema': self.schema,
      'lane_id': self.lane_id,
      'model': {'id': self.model_id, 'version': self.model_version},
      'source_status': self.source_status,
      'applicability': {
        'status': self.applicability_status.value,
        'reasons': list(self.applicability_reasons),
      },
      'claims': self.claims.model_dump(),
      'sectioned_tube': {
        'frame_id': self.sectioned_tube.frame_id,
        'sections': [section.model_dump(mode='json') for section in self.sectioned_tube.sections],
        'channels': {name: list(values) for name, values in self.sectioned_tube.channels.items()},
      },
      'section_channels': [channel.model_dump() for channel in self.section_channels],
      'paths': [path.model_dump() for path in self.paths],
      'fields': [field.model_dump() for field in self.fields],
      'diagnostics': dict(self.diagnostics),
      'warnings': list(self.warnings),
    }


def _section_channel(
  channel_id: str,
  semantic: str,
  unit: str,
  values: Sequence[float],
) -> ModelVisualChannel:
  return ModelVisualChannel(
    channel_id=channel_id,
    semantic=semantic,
    unit=unit,
    values=tuple(float(value) for value in values),
  )


def _definition(
  frame_id: str,
  sections: Sequence[VisualSection],
  channels: Sequence[ModelVisualChannel],
) -> PrescribedVisualDefinition:
  return PrescribedVisualDefinition(
    frame_id=frame_id,
    sections=tuple(sections),
    channels={channel.channel_id: channel.values for channel in channels},
  )


def _bundle(
  *,
  lane: ModelVisualizationLane,
  model_id: str,
  model_version: str,
  result: object,
  frame_id: str,
  sections: Sequence[VisualSection],
  channels: Sequence[ModelVisualChannel],
  claims: ModelVisualizationClaims,
  applicability_status: ApplicabilityStatus,
  applicability_reasons: Sequence[str],
  paths: Sequence[ModelVisualPath] = (),
  fields: Sequence[ModelVisualField] = (),
  diagnostics: Mapping[str, DiagnosticValue] | None = None,
  warnings: Sequence[str] = (),
) -> StandardizedModelVisualization:
  return StandardizedModelVisualization(
    lane=lane,
    model_id=model_id,
    model_version=model_version,
    source_status=_status_value(result),
    applicability_status=applicability_status,
    applicability_reasons=tuple(applicability_reasons),
    claims=claims,
    sectioned_tube=_definition(frame_id, sections, channels),
    section_channels=tuple(channels),
    paths=tuple(paths),
    fields=tuple(fields),
    diagnostics={} if diagnostics is None else diagnostics,
    warnings=tuple(warnings),
  )


def _basic_visualization(
  result: ShockCellSolveResult,
  *,
  frame_id: str,
  section_count: int,
  maximum_axial_extent_m: float | None,
) -> StandardizedModelVisualization:
  from exhaust_plume.products.workflow_visual import visual_definition_from_zone_results

  definition = visual_definition_from_zone_results(
    result.zones,
    frame_id=frame_id,
    section_count=section_count,
    maximum_axial_extent_m=maximum_axial_extent_m,
  )
  zones = tuple(result.zones)
  station_values: dict[str, list[float]] = {
    'temperature': [],
    'pressure': [],
    'density': [],
    'mach': [],
    'total_pressure': [],
  }
  radii = tuple(section.radius_major_m for section in definition.sections)
  for section in definition.sections:
    candidates = []
    for zone in zones:
      vertices = np.asarray(zone.vertices_xr_m, dtype=float)
      if vertices.ndim == 2 and vertices.shape[1] == 2:
        minimum = float(np.min(vertices[:, 0]))
        maximum = float(np.max(vertices[:, 0]))
        if minimum - 1.0e-10 <= section.center_m[0] <= maximum + 1.0e-10:
          candidates.append(zone)
    selected = max(candidates, key=lambda zone: float(np.max(zone.vertices_xr_m[:, 1]))) if candidates else zones[0]
    flow = selected.flow
    station_values['temperature'].append(float(flow.static_temperature))
    station_values['pressure'].append(float(flow.static_pressure))
    station_values['density'].append(float(flow.static_density))
    station_values['mach'].append(float(flow.mach))
    station_values['total_pressure'].append(float(flow.total_pressure))
  channels = (
    _section_channel('core_radius_fraction', 'display envelope radius normalized by the maximum zone radius', '1', _normalized(radii, zero_value=1.0)),
    _section_channel('opacity_weight', 'display occupancy weight for the modeled zone envelope', '1', tuple(1.0 for _ in radii)),
    _section_channel('shock_weight', 'basic-solver zone occupancy; not a radiance or shock-strength field', '1', tuple(1.0 for _ in radii)),
    _section_channel('temperature', 'zone static temperature', 'K', station_values['temperature']),
    _section_channel('pressure', 'zone static pressure', 'Pa', station_values['pressure']),
    _section_channel('density', 'zone static density', 'kg m^-3', station_values['density']),
    _section_channel('mach', 'zone Mach number', '1', station_values['mach']),
    _section_channel('total_pressure', 'zone total pressure', 'Pa', station_values['total_pressure']),
  )
  fields = (
    _field_from_zones(
      'basic-shock-cell-zones',
      'finite axisymmetric zones from the basic shock-cell solver',
      zones,
      flow_values={
        'temperature': ('static_temperature', 'K', 'zone static temperature'),
        'pressure': ('static_pressure', 'Pa', 'zone static pressure'),
        'density': ('static_density', 'kg m^-3', 'zone static density'),
        'mach': ('mach', '1', 'zone Mach number'),
      },
    ),
  )
  return _bundle(
    lane=ModelVisualizationLane.BASIC_SHOCK_CELL,
    model_id='shock-cell-basic',
    model_version='1',
    result=result,
    frame_id=frame_id,
    sections=definition.sections,
    channels=channels,
    claims=ModelVisualizationClaims(
      model_fidelity='EXPLORATORY_ANALYTICAL',
      validation_level='UNVERIFIED',
      geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
      production_claim_allowed=True,
      claim_notes=(
        'fast straight low-order shock-cell construction',
        'visualization geometry only; no radiation, signature, or detector claim',
      ),
    ),
    applicability_status=ApplicabilityStatus.INSIDE,
    applicability_reasons=('basic solver supplied finite closed zone geometry',),
    fields=fields,
    diagnostics={
      'cell_count': len(result.cells),
      'zone_count': len(result.zones),
      'pressure_residual': float(result.pressure_residual),
      'termination_reason': getattr(result.termination_reason, 'value', str(result.termination_reason)),
    },
    warnings=(
      'shock_weight marks modeled zones; it is not a measured shock strength or radiance',
      'zone geometry is not a conservative or optical medium between samples',
    ),
  )


def _field_from_zones(
  field_id: str,
  semantic: str,
  zones: Sequence[object],
  *,
  flow_values: Mapping[str, tuple[str, str, str]],
) -> ModelVisualField:
  polygons: list[tuple[Vector2, ...]] = []
  channel_values: dict[str, list[float]] = {name: [] for name in flow_values}
  for zone in zones:
    raw = getattr(zone, 'vertices_xr_m', None)
    if raw is None:
      coordinates = getattr(zone, 'coordinates', None)
      raw = None if coordinates is None else getattr(coordinates, 'corners_ru', None)
    if raw is None:
      continue
    polygon = tuple(_vector2('zone vertex', point) for point in np.asarray(raw, dtype=float))
    if len(polygon) < 3:
      continue
    polygons.append(polygon)
    flow = getattr(zone, 'flow', None)
    for channel_id, (attribute, _unit, _semantic) in flow_values.items():
      value = getattr(flow, attribute, None)
      channel_values[channel_id].append(_finite(f'{channel_id} zone value', value))
  if not polygons:
    raise ValueError(f'{field_id} contains no finite polygons')
  units = {name: values[1] for name, values in flow_values.items()}
  semantics = {name: values[2] for name, values in flow_values.items()}
  return ModelVisualField(
    field_id=field_id,
    semantic=semantic,
    polygons_xr_m=tuple(polygons),
    channels={name: tuple(values) for name, values in channel_values.items()},
    channel_units=units,
    channel_semantics=semantics,
  )


def _reduced_order_visualization(
  result: ShockTrainResult,
  *,
  frame_id: str,
  maximum_axial_extent_m: float | None,
) -> StandardizedModelVisualization:
  if not result.cells:
    raise ValueError('reduced-order shock-train visualization requires at least one cell')
  raw_stations: list[tuple[float, Any]] = []
  for cell in result.cells:
    metrics = cell.metrics
    raw_stations.extend(((float(metrics.start_x_m), metrics), (float(metrics.end_x_m), metrics)))
  raw_stations.sort(key=lambda item: item[0])
  stations: list[tuple[float, Any]] = []
  for station in raw_stations:
    if stations and abs(station[0] - stations[-1][0]) <= 1.0e-12:
      stations[-1] = station
    else:
      stations.append(station)
  if stations[0][0] > 0.0:
    stations.insert(0, (0.0, stations[0][1]))
  if maximum_axial_extent_m is not None:
    limit = _finite('maximum_axial_extent_m', maximum_axial_extent_m)
    if limit <= 0.0:
      raise ValueError('maximum_axial_extent_m must be positive')
    stations = [station for station in stations if station[0] <= limit + 1.0e-12]
  if len(stations) < 2:
    raise ValueError('maximum_axial_extent_m leaves fewer than two shock-train stations')
  x_values = tuple(station[0] for station in stations)
  radius_values = tuple(max(1.0e-9, float(station[1].effective_core_diameter_m) / 2.0) for station in stations)
  maximum_amplitude = max(float(station[1].pressure_oscillation_ratio) for station in stations)
  amplitude_scale = maximum_amplitude if maximum_amplitude > 0.0 else 1.0
  sections = tuple(
    VisualSection(
      arc_length_m=x_value - x_values[0],
      center_m=(x_value, 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=radius,
      radius_minor_m=radius,
    )
    for x_value, radius in zip(x_values, radius_values, strict=True)
  )
  metrics = tuple(station[1] for station in stations)
  channels = (
    _section_channel('core_radius_fraction', 'coherent-core radius normalized by the maximum displayed radius', '1', _normalized(radius_values, zero_value=1.0)),
    _section_channel('opacity_weight', 'reduced-order pressure oscillation display weight', '1', tuple(min(1.0, max(0.0, float(item.pressure_oscillation_ratio) / amplitude_scale)) for item in metrics)),
    _section_channel('shock_weight', 'reduced-order pressure oscillation display weight', '1', tuple(min(1.0, max(0.0, float(item.pressure_oscillation_ratio) / amplitude_scale)) for item in metrics)),
    _section_channel('core_mach', 'coherent-core Mach number', '1', tuple(float(item.core_mach) for item in metrics)),
    _section_channel('mean_pressure', 'cell mean static pressure', 'Pa', tuple(float(item.mean_pressure_Pa) for item in metrics)),
    _section_channel('maximum_pressure', 'cell maximum static pressure', 'Pa', tuple(float(item.maximum_pressure_Pa) for item in metrics)),
    _section_channel('minimum_pressure', 'cell minimum static pressure', 'Pa', tuple(float(item.minimum_pressure_Pa) for item in metrics)),
    _section_channel('pressure_oscillation_ratio', 'cell pressure oscillation ratio', '1', tuple(float(item.pressure_oscillation_ratio) for item in metrics)),
    _section_channel('total_pressure_ratio', 'cell outlet-to-inlet total pressure ratio', '1', tuple(float(item.outlet_total_pressure_Pa) / float(item.inlet_total_pressure_Pa) for item in metrics)),
  )
  polygons: list[tuple[Vector2, ...]] = []
  field_pressure: list[float] = []
  field_mach: list[float] = []
  for cell in result.cells:
    if cell.zones:
      for zone in cell.zones:
        polygon = tuple(_vector2('shock-train zone vertex', point) for point in np.asarray(zone.vertices_xr_m, dtype=float))
        if len(polygon) >= 3:
          polygons.append(polygon)
          field = getattr(zone, 'flow', None)
          field_pressure.append(float(getattr(field, 'static_pressure', cell.metrics.mean_pressure_Pa)))
          field_mach.append(float(getattr(field, 'mach', cell.metrics.core_mach)))
    else:
      item = cell.metrics
      radius = max(1.0e-9, float(item.effective_core_diameter_m) / 2.0)
      polygons.append(((item.start_x_m, -radius), (item.end_x_m, -radius), (item.end_x_m, radius), (item.start_x_m, radius)))
      field_pressure.append(float(item.mean_pressure_Pa))
      field_mach.append(float(item.core_mach))
  fields = (
    ModelVisualField(
      field_id='reduced-order-shock-train-cells',
      semantic='resolved first-cell and calibrated reduced-order downstream cell envelopes',
      polygons_xr_m=tuple(polygons),
      channels={'pressure': tuple(field_pressure), 'mach': tuple(field_mach)},
      channel_units={'pressure': 'Pa', 'mach': '1'},
      channel_semantics={'pressure': 'cell static pressure or reduced-order mean pressure', 'mach': 'cell core Mach number'},
    ),
  )
  return _bundle(
    lane=ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN,
    model_id='shock-train-reduced-order',
    model_version='1',
    result=result,
    frame_id=frame_id,
    sections=sections,
    channels=channels,
    claims=ModelVisualizationClaims(
      model_fidelity='CALIBRATED_REDUCED_ORDER',
      validation_level='CALIBRATED',
      geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
      production_claim_allowed=False,
      claim_notes=(
        'one resolved first cell followed by explicitly calibrated reduced-order cells',
        'calibration identity and validation split remain part of the claim boundary',
      ),
    ),
    applicability_status=ApplicabilityStatus.MARGINAL,
    applicability_reasons=(f'calibration identity: {result.calibration_id}',),
    paths=(ModelVisualPath(
      path_id='reduced-order-core-centerline',
      semantic='straight reduced-order core centerline',
      points_m=tuple((x_value, 0.0, 0.0) for x_value in x_values),
    ),),
    fields=fields,
    diagnostics={
      'cell_count': result.cell_count,
      'calibration_id': result.calibration_id,
      'was_domain_truncated': bool(result.was_domain_truncated),
      'termination_reason': getattr(result.termination_reason, 'value', str(result.termination_reason)),
    },
    warnings=(
      'downstream geometry is reduced-order and is not resolved planar-MOC geometry',
      'pressure and opacity channels are display diagnostics, not spectral radiance',
    ),
  )


def _straight_integral_visualization(
  result: IntegralStraightResult,
  *,
  frame_id: str,
  section_count: int,
  maximum_axial_extent_m: float | None,
) -> StandardizedModelVisualization:
  states = result.states
  indices = _clip_sequence(tuple(state.x_m for state in states), maximum_extent_m=maximum_axial_extent_m)
  indices = tuple(indices[index] for index in _sample_indices(len(indices), section_count))
  selected = tuple(states[index] for index in indices)
  x_values = tuple(float(state.x_m) for state in selected)
  radii = tuple(float(state.radius_m) for state in selected)
  sections = tuple(
    VisualSection(
      arc_length_m=x_value - x_values[0],
      center_m=(x_value, 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=radius,
      radius_minor_m=radius,
    )
    for x_value, radius in zip(x_values, radii, strict=True)
  )
  channels = (
    _section_channel('core_radius_fraction', 'top-hat radius normalized by the maximum displayed radius', '1', _normalized(radii, zero_value=1.0)),
    _section_channel('temperature', 'top-hat static temperature', 'K', tuple(float(state.temperature_K) for state in selected)),
    _section_channel('pressure', 'top-hat static pressure', 'Pa', tuple(float(state.pressure_Pa) for state in selected)),
    _section_channel('density', 'top-hat density', 'kg m^-3', tuple(float(state.density_kgpm3) for state in selected)),
    _section_channel('speed', 'top-hat axial speed', 'm s^-1', tuple(float(state.velocity_mps) for state in selected)),
    _section_channel('mass_flow_rate', 'integral mass-flow rate', 'kg s^-1', tuple(float(state.mass_flow_rate_kg_s) for state in selected)),
    _section_channel('momentum_flux', 'integral axial momentum flux', 'N', tuple(float(state.momentum_flux_N) for state in selected)),
    _section_channel('total_enthalpy_flux', 'integral total enthalpy flux', 'W', tuple(float(state.total_enthalpy_flux_W) for state in selected)),
  )
  polygons = tuple(
    (
      (first.x_m, -first.radius_m),
      (second.x_m, -second.radius_m),
      (second.x_m, second.radius_m),
      (first.x_m, first.radius_m),
    )
    for first, second in zip(selected, selected[1:])
  )
  field = ModelVisualField(
    field_id='straight-integral-top-hat',
    semantic='straight top-hat integral plume envelope',
    polygons_xr_m=polygons,
    channels={
      'temperature': tuple((first.temperature_K + second.temperature_K) / 2.0 for first, second in zip(selected, selected[1:])),
      'pressure': tuple((first.pressure_Pa + second.pressure_Pa) / 2.0 for first, second in zip(selected, selected[1:])),
    },
    channel_units={'temperature': 'K', 'pressure': 'Pa'},
    channel_semantics={'temperature': 'interval-average top-hat temperature', 'pressure': 'interval-average top-hat pressure'},
  )
  return _bundle(
    lane=ModelVisualizationLane.STRAIGHT_INTEGRAL,
    model_id='straight-integral-top-hat',
    model_version='1',
    result=result,
    frame_id=frame_id,
    sections=sections,
    channels=channels,
    claims=ModelVisualizationClaims(
      model_fidelity='EXPLORATORY_ANALYTICAL',
      validation_level='UNVERIFIED',
      geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
      production_claim_allowed=False,
      claim_notes=(
        'pressure-matched straight top-hat continuation',
        'finite domain endpoint is a display truncation, not a physical plume endpoint',
      ),
    ),
    applicability_status=ApplicabilityStatus.MARGINAL,
    applicability_reasons=('straight integral continuation is a supporting/reference primitive',),
    paths=(
      ModelVisualPath('straight-integral-centerline', 'top-hat centerline', tuple((x, 0.0, 0.0) for x in x_values)),
      ModelVisualPath('straight-integral-upper-boundary', 'top-hat upper boundary', tuple((state.x_m, state.radius_m, 0.0) for state in selected)),
      ModelVisualPath('straight-integral-lower-boundary', 'top-hat lower boundary', tuple((state.x_m, -state.radius_m, 0.0) for state in selected)),
    ),
    fields=(field,),
    diagnostics={
      'state_count': len(result.states),
      'displayed_state_count': len(selected),
      'termination_reason': getattr(result.termination_reason, 'value', str(result.termination_reason)),
      'termination_is_physical': bool(result.termination_is_physical),
      'momentum_relative_residual': float(result.conservation_residuals.get('momentum_relative', 0.0)),
      'total_enthalpy_relative_residual': float(result.conservation_residuals.get('total_enthalpy_relative', 0.0)),
    },
    warnings=(
      'mixing_weight is intentionally not synthesized from species or radiance',
      'straight top-hat geometry has no resolved shear layer or shock-diamond field',
    ),
  )


def _curved_integral_visualization(
  result: CurvedPlumeResult,
  *,
  frame_id: str,
  section_count: int,
  maximum_axial_extent_m: float | None,
) -> StandardizedModelVisualization:
  stations = result.stations
  indices = _clip_sequence(tuple(station.arc_length_m for station in stations), maximum_extent_m=maximum_axial_extent_m)
  indices = tuple(indices[index] for index in _sample_indices(len(indices), section_count))
  selected = tuple(stations[index] for index in indices)
  tangents = np.asarray([station.tangent for station in selected], dtype=float)
  normals, binormals = calculateRotationMinimizingFrames(tangents=tangents)
  first_arc = float(selected[0].arc_length_m)
  sections = tuple(
    VisualSection(
      arc_length_m=float(station.arc_length_m) - first_arc,
      center_m=_vector3('curved plume center', cast(Sequence[float], station.position_m)),
      section_to_output_xyzw=_quaternion_from_frames(normal, binormal, tangent),
      radius_major_m=float(station.radius_m),
      radius_minor_m=float(station.radius_m),
    )
    for station, normal, binormal, tangent in zip(selected, normals, binormals, tangents, strict=True)
  )
  radii = tuple(float(station.radius_m) for station in selected)
  entrainment = tuple(float(station.entrainment_kgpspm) for station in selected)
  channels = (
    _section_channel('core_radius_fraction', 'curved-envelope radius normalized by the maximum displayed radius', '1', _normalized(radii, zero_value=1.0)),
    _section_channel('mixing_weight', 'source-origin exhaust mass fraction', '1', tuple(float(station.exhaust_mass_fraction) for station in selected)),
    _section_channel('temperature', 'curved integral mixture temperature', 'K', tuple(float(station.temperature_K) for station in selected)),
    _section_channel('pressure', 'curved integral static pressure', 'Pa', tuple(float(station.pressure_Pa) for station in selected)),
    _section_channel('density', 'curved integral mixture density', 'kg m^-3', tuple(float(station.density_kgpm3) for station in selected)),
    _section_channel('speed', 'curved integral centerline speed', 'm s^-1', tuple(float(station.speed_mps) for station in selected)),
    _section_channel('mass_flow', 'curved integral total mass flow', 'kg s^-1', tuple(float(station.mass_flow_kgps) for station in selected)),
    _section_channel('entrainment_rate', 'ambient entrainment rate per arc length', 'kg s^-1 m^-1', entrainment),
    _section_channel('curvature', 'centerline curvature', 'm^-1', tuple(float(station.curvature_per_m) for station in selected)),
    _section_channel('slenderness', 'local radius-to-arc-length slenderness diagnostic', '1', tuple(float(station.slenderness_ratio) for station in selected)),
  )
  return _bundle(
    lane=ModelVisualizationLane.CURVED_INTEGRAL,
    model_id='curved-washed-integral',
    model_version='1',
    result=result,
    frame_id=frame_id,
    sections=sections,
    channels=channels,
    claims=ModelVisualizationClaims(
      model_fidelity='EXPLORATORY_ANALYTICAL',
      validation_level='UNVERIFIED',
      geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
      production_claim_allowed=False,
      claim_notes=(
        'curved, entraining integral plume with ambient and buoyancy closures',
        'visual and engineering supporting lane; no automatic spectral or ray-transfer claim',
      ),
    ),
    applicability_status=ApplicabilityStatus.MARGINAL,
    applicability_reasons=('curved/washed integral provider and validation gate remain separate from the fast visual lane',),
    paths=(ModelVisualPath(
      path_id='curved-integral-centerline',
      semantic='curved integral plume centerline',
      points_m=tuple(
        _vector3('curved centerline point', cast(Sequence[float], station.position_m))
        for station in selected
      ),
    ),),
    diagnostics={
      'station_count': len(result.stations),
      'displayed_station_count': len(selected),
      'termination': getattr(result.termination, 'value', str(result.termination)),
      'function_evaluations': int(result.function_evaluations),
    },
    warnings=(
      'channels are integral-model diagnostics, not pixel radiance or detector counts',
      'the swept tube is a visualization envelope and does not replace a transport operator',
    ),
  )


def _moc_field_from_result(result: object) -> tuple[object | None, object]:
  """Find a retained planar field without requiring one concrete MOC wrapper."""

  candidates: list[object] = [result]
  candidate_field = getattr(result, 'candidate_field', None)
  if candidate_field is not None:
    candidates.append(candidate_field)
  physical_field = getattr(result, 'physical_field', None)
  if physical_field is not None:
    candidates.append(physical_field)
  global_euler = getattr(result, 'global_euler', None)
  if global_euler is not None:
    candidates.append(global_euler)
    global_physical = getattr(global_euler, 'physical_field', None)
    if global_physical is not None:
      candidates.append(global_physical)
  nested_candidates: list[object] = []
  for candidate in candidates:
    field_value = getattr(candidate, 'field', None)
    if field_value is not None:
      nested_candidates.append(field_value)
  candidates.extend(nested_candidates)
  for candidate in candidates:
    if all(hasattr(candidate, name) for name in ('cells', 'shock_boundary_points_m', 'ambient_boundary_points_m', 'centerline_boundary_points_m')):
      return candidate, result
  for candidate in candidates:
    if hasattr(candidate, 'cells') and hasattr(candidate, 'centerline_boundary_points_m'):
      return candidate, result
  return None, result


def _finite_path(value: object) -> tuple[Vector2, ...]:
  try:
    points = tuple(_vector2('MOC path point', point) for point in value)  # type: ignore[arg-type]
  except (TypeError, ValueError, IndexError) as error:
    raise ValueError('MOC boundary paths must contain finite 2-D points') from error
  return points


def _path3(path_id: str, semantic: str, points: Sequence[Sequence[float]]) -> ModelVisualPath | None:
  if len(points) < 2:
    return None
  return ModelVisualPath(path_id, semantic, tuple((float(point[0]), float(point[1]), 0.0) for point in points))


def _interpolated_y(points: Sequence[Vector2], x_value: float) -> float | None:
  candidates: list[float] = []
  for first, second in zip(points, points[1:]):
    x0, y0 = first
    x1, y1 = second
    lower = min(x0, x1) - 1.0e-12
    upper = max(x0, x1) + 1.0e-12
    if lower <= x_value <= upper:
      if abs(x1 - x0) <= 1.0e-14:
        candidates.extend((y0, y1))
      else:
        fraction = (x_value - x0) / (x1 - x0)
        candidates.append(y0 + fraction * (y1 - y0))
  return max((abs(value) for value in candidates), default=None)


def _moc_visualization(
  result: object,
  *,
  frame_id: str,
  section_count: int,
  maximum_axial_extent_m: float | None,
) -> StandardizedModelVisualization:
  field_value, source = _moc_field_from_result(result)
  field: Any = field_value
  if field is None:
    raise ValueError('planar-MOC visualization requires a retained field with cells and boundaries')
  cell_polygons: list[tuple[Vector2, ...]] = []
  all_points: list[Vector2] = []
  for cell in getattr(field, 'cells', ()):
    raw = getattr(cell, 'vertices_xr_m', None)
    if raw is None:
      continue
    polygon = tuple(_vector2('MOC cell vertex', point) for point in raw)
    if len(polygon) >= 3:
      cell_polygons.append(polygon)
      all_points.extend(polygon)
  if not cell_polygons:
    raise ValueError('planar-MOC field contains no finite cell polygons')

  boundary_specs = (
    ('moc-shock-boundary', 'fitted shock boundary', getattr(field, 'shock_boundary_points_m', ())),
    ('moc-ambient-boundary', 'ambient-pressure boundary', getattr(field, 'ambient_boundary_points_m', ())),
    ('moc-centerline-boundary', 'centerline reflection boundary', getattr(field, 'centerline_boundary_points_m', ())),
  )
  paths: list[ModelVisualPath] = []
  boundary_points: dict[str, tuple[Vector2, ...]] = {}
  for path_id, semantic, raw_points in boundary_specs:
    points = _finite_path(raw_points)
    if points:
      boundary_points[path_id] = points
      all_points.extend(points)
      path = _path3(path_id, semantic, points)
      if path is not None:
        paths.append(path)
  incoming_states = getattr(field, 'incoming_handoff_states', ())
  if len(incoming_states) >= 2:
    points = tuple((float(state.x_m), float(state.y_m)) for state in incoming_states)
    path = _path3('moc-incoming-frontier', 'retained incoming shock-cell frontier', points)
    if path is not None:
      paths.append(path)
      all_points.extend(points)

  centerline = boundary_points.get('moc-centerline-boundary', ())
  if len(centerline) < 2:
    x_values = sorted({point[0] for point in all_points})
    centerline = tuple((x_value, 0.0) for x_value in x_values)
  if len(centerline) < 2:
    raise ValueError('planar-MOC visualization requires at least two centerline stations')
  centerline = tuple(sorted(centerline, key=lambda point: point[0]))
  centerline = tuple(point for index, point in enumerate(centerline) if index == 0 or point[0] > centerline[index - 1][0] + 1.0e-12)
  if maximum_axial_extent_m is not None:
    limit = centerline[0][0] + _finite('maximum_axial_extent_m', maximum_axial_extent_m)
    centerline = tuple(point for point in centerline if point[0] <= limit + 1.0e-12)
  if len(centerline) < 2:
    raise ValueError('maximum_axial_extent_m leaves fewer than two MOC stations')
  if len(centerline) > section_count:
    centerline = tuple(centerline[index] for index in _sample_indices(len(centerline), section_count))
  radii: list[float] = []
  for point in centerline:
    candidates = [abs(other[1]) for other in all_points if abs(other[0] - point[0]) <= 1.0e-10]
    for path_points in boundary_points.values():
      interpolated = _interpolated_y(path_points, point[0])
      if interpolated is not None:
        candidates.append(interpolated)
    if not candidates:
      candidates = [abs(other[1]) for other in all_points]
    radii.append(max(1.0e-9, max(candidates, default=1.0e-9)))
  sections = tuple(
    VisualSection(
      arc_length_m=point[0] - centerline[0][0],
      center_m=(point[0], 0.0, 0.0),
      section_to_output_xyzw=_AXIAL_SECTION_QUATERNION,
      radius_major_m=radius,
      radius_minor_m=radius,
    )
    for point, radius in zip(centerline, radii, strict=True)
  )

  centerline_states = tuple(getattr(field, 'centerline_boundary_states', ()))
  centerline_pressures = tuple(getattr(field, 'centerline_boundary_total_pressure_Pa', ()))
  centerline_points = tuple(getattr(field, 'centerline_boundary_points_m', ()))
  state_by_x: list[tuple[float, Any, float | None]] = []
  if len(centerline_states) == len(centerline_points):
    for index, state in enumerate(centerline_states):
      pressure = centerline_pressures[index] if index < len(centerline_pressures) else None
      state_by_x.append((float(centerline_points[index][0]), state, None if pressure is None else float(pressure)))
  def sample_axis_state(x_value: float) -> tuple[Any | None, float | None]:
    if state_by_x:
      nearest = min(state_by_x, key=lambda item: abs(item[0] - x_value))
      return nearest[1], nearest[2]
    sampler = getattr(field, 'state_at', None)
    if callable(sampler):
      state = sampler((x_value, 0.0))
      pressure_sampler = getattr(field, 'total_pressure_at', None)
      pressure: Any = pressure_sampler((x_value, 0.0)) if callable(pressure_sampler) else None
      return state, None if pressure is None else float(pressure)
    return None, None
  axis_states = tuple(sample_axis_state(point[0]) for point in centerline)
  base_channels: list[ModelVisualChannel] = [
    _section_channel('core_radius_fraction', 'planar field envelope radius normalized by the maximum displayed radius', '1', _normalized(radii, zero_value=1.0)),
    _section_channel('opacity_weight', 'field coverage display weight', '1', tuple(1.0 for _ in radii)),
  ]
  optional_channels: list[ModelVisualChannel] = []
  mach_values = [float(getattr(state, 'mach')) for state, _pressure in axis_states if state is not None]
  theta_values = [float(getattr(state, 'theta_rad')) for state, _pressure in axis_states if state is not None]
  pressure_values = [pressure for _state, pressure in axis_states if pressure is not None]
  if len(mach_values) == len(centerline):
    optional_channels.append(_section_channel('mach', 'centerline MOC Mach number', '1', mach_values))
  if len(theta_values) == len(centerline):
    optional_channels.append(_section_channel('flow_angle', 'centerline MOC flow angle', 'rad', theta_values))
  if len(pressure_values) == len(centerline):
    optional_channels.append(_section_channel('total_pressure', 'centerline MOC total pressure', 'Pa', pressure_values))
  channels = tuple(base_channels + optional_channels)

  field_channel_values: dict[str, list[Scalar]] = {
    'mach': [],
    'flow_angle': [],
    'static_pressure': [],
    'total_pressure': [],
  }
  for polygon in cell_polygons:
    centroid = (
      sum(point[0] for point in polygon) / len(polygon),
      sum(point[1] for point in polygon) / len(polygon),
    )
    sampler = getattr(field, 'state_at', None)
    state: Any = sampler(centroid) if callable(sampler) else None
    total_pressure_sampler = getattr(field, 'total_pressure_at', None)
    total_pressure: Any = total_pressure_sampler(centroid) if callable(total_pressure_sampler) else None
    field_channel_values['mach'].append(None if state is None else float(getattr(state, 'mach')))
    field_channel_values['flow_angle'].append(None if state is None else float(getattr(state, 'theta_rad')))
    if state is None or total_pressure is None:
      field_channel_values['static_pressure'].append(None)
      field_channel_values['total_pressure'].append(None if total_pressure is None else float(total_pressure))
    else:
      pressure_ratio = (1.0 + 0.5 * (float(state.gamma) - 1.0) * float(state.mach) ** 2) ** (float(state.gamma) / (float(state.gamma) - 1.0))
      field_channel_values['static_pressure'].append(float(total_pressure) / pressure_ratio)
      field_channel_values['total_pressure'].append(float(total_pressure))
  moc_field = ModelVisualField(
    field_id='planar-moc-cells',
    semantic='retained planar characteristic field cells',
    polygons_xr_m=tuple(cell_polygons),
    channels={name: tuple(values) for name, values in field_channel_values.items()},
    channel_units={'mach': '1', 'flow_angle': 'rad', 'static_pressure': 'Pa', 'total_pressure': 'Pa'},
    channel_semantics={
      'mach': 'cell-center sampled MOC Mach number',
      'flow_angle': 'cell-center sampled MOC flow angle',
      'static_pressure': 'cell-center isentropic static pressure',
      'total_pressure': 'cell-center carried total pressure',
    },
  )
  gates = getattr(source, 'production_promotion_gates', {})
  diagnostics: dict[str, DiagnosticValue] = {
    'cell_count': len(cell_polygons),
    'node_count': len(getattr(field, 'nodes', ())),
    'physical_closure_verified': bool(getattr(source, 'physical_closure_verified', getattr(field, 'physical_closure_verified', False))),
    'state_sampling_available': bool(getattr(source, 'state_sampling_available', getattr(field, 'state_sampling_available', False))),
    'production_claim_allowed': bool(getattr(source, 'production_claim_allowed', False)),
  }
  if isinstance(gates, Mapping):
    for key, value in gates.items():
      diagnostics[f'gate_{key}'] = bool(value)
  warnings = [
    'planar-MOC geometry is retained as 2-D field polygons and boundary paths',
    'the sectioned-tube view is a display envelope projected from the planar field, not an axisymmetric claim',
    'MOC production promotion remains blocked until canonical closure, refinement, and external validation gates pass',
  ]
  if not optional_channels or any(
    value is None
    for values in field_channel_values.values()
    for value in values
  ):
    warnings.append('state samples were unavailable on the centerline; field values remain masked where unavailable')
  return _bundle(
    lane=ModelVisualizationLane.PLANAR_MOC,
    model_id='planar-moc-reflected-domain',
    model_version='1',
    result=result,
    frame_id=frame_id,
    sections=sections,
    channels=channels,
    claims=ModelVisualizationClaims(
      model_fidelity='REFERENCE_NUMERICAL',
      validation_level='RESEARCH_ONLY',
      geometry_claim=GeometryClaim.ILLUSTRATIVE,
      production_claim_allowed=False,
      claim_notes=(
        'higher-fidelity planar characteristic/reflected-domain field retained for evaluation',
        'local field closure does not imply a production chain-cell or axisymmetric plume claim',
      ),
    ),
    applicability_status=ApplicabilityStatus.MARGINAL,
    applicability_reasons=('planar MOC field is a bounded research/foundation lane with explicit promotion gates',),
    paths=paths,
    fields=(moc_field,),
    diagnostics=diagnostics,
    warnings=warnings,
  )


def _looks_like_moc_result(result: object) -> bool:
  field, _source = _moc_field_from_result(result)
  return field is not None


def standardize_model_visualization(
  result: object,
  *,
  lane: ModelVisualizationLane | str | None = None,
  frame_id: str = 'source-local',
  section_count: int = 64,
  maximum_axial_extent_m: float | None = None,
) -> StandardizedModelVisualization:
  """Adapt one of the five model result shapes to the common visual bundle."""

  if not frame_id:
    raise ValueError('frame_id must not be empty')
  resolved_lane = None if lane is None else _coerce_lane(lane)
  source = result.result if isinstance(result, AnalyticalFirstCellSolution) else result
  if isinstance(source, ShockCellSolveResult):
    if resolved_lane not in (None, ModelVisualizationLane.BASIC_SHOCK_CELL):
      raise TypeError(f'{resolved_lane.value} does not accept ShockCellSolveResult')
    return _basic_visualization(
      source,
      frame_id=frame_id,
      section_count=section_count,
      maximum_axial_extent_m=maximum_axial_extent_m,
    )
  if isinstance(source, ShockTrainResult):
    if resolved_lane not in (None, ModelVisualizationLane.REDUCED_ORDER_SHOCK_TRAIN):
      raise TypeError(f'{resolved_lane.value} does not accept ShockTrainResult')
    return _reduced_order_visualization(
      source,
      frame_id=frame_id,
      maximum_axial_extent_m=maximum_axial_extent_m,
    )
  if isinstance(source, IntegralStraightResult):
    if resolved_lane not in (None, ModelVisualizationLane.STRAIGHT_INTEGRAL):
      raise TypeError(f'{resolved_lane.value} does not accept IntegralStraightResult')
    return _straight_integral_visualization(
      source,
      frame_id=frame_id,
      section_count=section_count,
      maximum_axial_extent_m=maximum_axial_extent_m,
    )
  if isinstance(source, CurvedPlumeResult):
    if resolved_lane not in (None, ModelVisualizationLane.CURVED_INTEGRAL):
      raise TypeError(f'{resolved_lane.value} does not accept CurvedPlumeResult')
    return _curved_integral_visualization(
      source,
      frame_id=frame_id,
      section_count=section_count,
      maximum_axial_extent_m=maximum_axial_extent_m,
    )
  if _looks_like_moc_result(source):
    if resolved_lane not in (None, ModelVisualizationLane.PLANAR_MOC):
      raise TypeError(f'{resolved_lane.value} does not accept a planar-MOC result')
    return _moc_visualization(
      source,
      frame_id=frame_id,
      section_count=section_count,
      maximum_axial_extent_m=maximum_axial_extent_m,
    )
  raise TypeError(
    'result must be a ShockCellSolveResult, ShockTrainResult, '
    'IntegralStraightResult, CurvedPlumeResult, or retained planar-MOC result'
  )


standardize_model_result = standardize_model_visualization


def standardize_all_model_visualizations(
  results: Mapping[ModelVisualizationLane | str, object],
  *,
  frame_id: str = 'source-local',
  section_count: int = 64,
  maximum_axial_extent_m: float | None = None,
) -> tuple[StandardizedModelVisualization, ...]:
  """Require and return exactly one standardized bundle for each model lane."""

  normalized: dict[ModelVisualizationLane, object] = {}
  for key, result in results.items():
    lane = _coerce_lane(key)
    if lane in normalized:
      raise ValueError(f'duplicate model visualization lane: {lane.value}')
    normalized[lane] = result
  missing = tuple(lane.value for lane in MODEL_VISUALIZATION_LANES if lane not in normalized)
  unexpected = tuple(lane.value for lane in normalized if lane not in MODEL_VISUALIZATION_LANES)
  if missing or unexpected:
    details = []
    if missing:
      details.append(f'missing={missing!r}')
    if unexpected:
      details.append(f'unexpected={unexpected!r}')
    raise ValueError('all five model visualization lanes are required: ' + ', '.join(details))
  return tuple(
    standardize_model_visualization(
      normalized[lane],
      lane=lane,
      frame_id=frame_id,
      section_count=section_count,
      maximum_axial_extent_m=maximum_axial_extent_m,
    )
    for lane in MODEL_VISUALIZATION_LANES
  )


def evaluate_standardized_model_visualization(
  visualization: StandardizedModelVisualization,
  request: VisualSectionedTubeRequest,
  snapshot: SnapshotMetadata,
  *,
  provider_id: str | None = None,
  provider_version: str = '1.0.0',
  time_model: TimeModel = TimeModel.STEADY,
) -> VisualSectionedTubeResult:
  """Evaluate a standardized bundle through the canonical visual product."""

  if not isinstance(visualization, StandardizedModelVisualization):
    raise TypeError('visualization must be a StandardizedModelVisualization')
  if not isinstance(time_model, TimeModel):
    raise TypeError('time_model must be TimeModel')
  resolved_provider_id = provider_id or f'plume.visual.model-lane.{visualization.lane.value}'
  if not resolved_provider_id or not provider_version:
    raise ProviderConfigurationError('provider identity and version must not be empty')
  configuration = PrescribedVisualConfiguration(
    provider_id=resolved_provider_id,
    provider_version=provider_version,
    geometry_claim=visualization.claims.geometry_claim,
    radiation_claim=RadiationClaim.APPEARANCE_ONLY,
    time_model=time_model,
    derivation=Derivation.ADAPTED,
    consistency=ConsistencyLevel.INDEPENDENT,
    applicability_status=visualization.applicability_status,
    applicability_reasons=visualization.applicability_reasons,
    warnings=visualization.warnings,
  )
  result = _evaluate_prescribed_definition(
    visualization.sectioned_tube,
    configuration,
    request,
    snapshot,
  )
  provenance = result.metadata.provenance.model_copy(update={
    'metadata': {
      'model_lane': visualization.lane.value,
      'model_fidelity': visualization.claims.model_fidelity,
      'validation_level': visualization.claims.validation_level,
      'production_claim_allowed': str(visualization.claims.production_claim_allowed).lower(),
      'standardization_schema': MODEL_VISUALIZATION_SCHEMA,
      'bundle_digest_sha256': canonical_digest(visualization.model_dump()),
    },
  })
  return result.model_copy(update={
    'metadata': result.metadata.model_copy(update={'provenance': provenance}),
  })
