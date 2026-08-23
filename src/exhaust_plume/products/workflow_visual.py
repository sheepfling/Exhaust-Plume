"""User-facing visual-product MVP helpers.

The public visual contract remains renderer-neutral.  This module adds the
smallest practical local workflow on top of it: straight geometry can be
loaded from JSON, converted to a deterministic triangle mesh, exported as
JSON or OBJ, and rendered through the optional plotting dependency.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from math import cos, isfinite, sin
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence

from exhaust_plume.api.v1 import (
  ApplicabilityStatus,
  ConsistencyLevel,
  Derivation,
  GeometryClaim,
  Pose,
  VisualSampling,
  VisualSection,
  VisualSectionedTubeRequest,
  ProductOutsideApplicabilityError,
  ProviderConfigurationError,
  Vector3,
  VISUAL_SECTIONED_TUBE_V1,
)
from exhaust_plume.models.gas import CaloricallyPerfectGas
from exhaust_plume.models.nozzle import AmbientInput, NozzleGeometry, derive_ambient_state, derive_nozzle_exit_from_geometry
from exhaust_plume.models.shock_cells import ShockCellSolveResult
from exhaust_plume.models.shock_cells import ShockCellSolveConfig, solve_shock_cells
from exhaust_plume.providers.prescribed_visual import (
  PrescribedVisualConfiguration,
  PrescribedVisualDefinition,
  PrescribedVisualProvider,
)
from exhaust_plume.providers.straight_visual import StraightVisualDefinition, StraightVisualProvider

__all__ = (
  'VisualMesh',
  'build_sectioned_tube_mesh',
  'evaluate_shock_cell_visual',
  'evaluate_nozzle_geometry_visual',
  'evaluate_visual_definition',
  'load_straight_visual_definition',
  'render_visual_preview',
  'visual_definition_from_shock_cells',
  'visual_definition_from_zone_results',
  'write_visual_mesh_json',
  'write_visual_obj',
  'write_visual_result_json',
  'write_straight_visual_asset',
)

_VISUAL_ASSET_SCHEMA = 'plume.visual.straight-definition@1'


@dataclass(frozen=True, slots=True)
class VisualMesh:
  """Deterministic triangle mesh derived from sectioned-tube sections."""

  frame_id: str
  section_count: int
  vertices: tuple[Vector3, ...]
  faces: tuple[tuple[int, int, int], ...]
  face_section_indices: tuple[int, ...]
  section_channels: Mapping[str, tuple[float, ...]] = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('mesh frame_id must not be empty')
    if self.section_count < 2:
      raise ValueError('mesh section_count must be at least two')
    if not self.vertices:
      raise ValueError('mesh must contain vertices')
    if len(self.faces) != len(self.face_section_indices):
      raise ValueError('mesh faces and face_section_indices must have matching lengths')
    normalized_vertices: list[Vector3] = []
    for vertex in self.vertices:
      if len(vertex) != 3 or not all(isfinite(value) for value in vertex):
        raise ValueError('mesh vertices must be finite 3-vectors')
      normalized_vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
    normalized_faces: list[tuple[int, int, int]] = []
    for face in self.faces:
      if len(face) != 3 or any(index < 0 or index >= len(normalized_vertices) for index in face):
        raise ValueError('mesh faces must contain valid vertex indices')
      normalized_faces.append((int(face[0]), int(face[1]), int(face[2])))
    normalized_channels: dict[str, tuple[float, ...]] = {}
    for channel_name, values in self.section_channels.items():
      if len(values) != self.section_count:
        raise ValueError(f'mesh channel {channel_name!r} must have one value per section')
      if not all(isfinite(value) for value in values):
        raise ValueError(f'mesh channel {channel_name!r} must be finite')
      normalized_channels[channel_name] = tuple(float(value) for value in values)
    if any(index < 0 or index >= self.section_count for index in self.face_section_indices):
      raise ValueError('mesh face section indices must reference sections')
    object.__setattr__(self, 'vertices', tuple(normalized_vertices))
    object.__setattr__(self, 'faces', tuple(normalized_faces))
    object.__setattr__(self, 'face_section_indices', tuple(int(index) for index in self.face_section_indices))
    object.__setattr__(self, 'section_channels', MappingProxyType(normalized_channels))
  ####

  @property
  def minimum_m(self) -> Vector3:
    return tuple(min(vertex[axis] for vertex in self.vertices) for axis in range(3))  # type: ignore[return-value]
  ####

  @property
  def maximum_m(self) -> Vector3:
    return tuple(max(vertex[axis] for vertex in self.vertices) for axis in range(3))  # type: ignore[return-value]
  ####

  def model_dump(self) -> dict[str, Any]:
    """Return a JSON-compatible representation of the mesh."""

    return {
      'schema': 'plume.visual.triangle-mesh@1',
      'frame_id': self.frame_id,
      'section_count': self.section_count,
      'vertices': [list(vertex) for vertex in self.vertices],
      'faces': [list(face) for face in self.faces],
      'face_section_indices': list(self.face_section_indices),
      'section_channels': {
        name: list(values)
        for name, values in self.section_channels.items()
      },
      'bounds': {
        'minimum_m': list(self.minimum_m),
        'maximum_m': list(self.maximum_m),
      },
    }
  ####
####


def _rotate_vector(quaternion: tuple[float, float, float, float], vector: Vector3) -> Vector3:
  x, y, z, w = quaternion
  vx, vy, vz = vector
  # q * v * q^-1, expanded to avoid a renderer or numerical dependency.
  tx = 2.0 * (y * vz - z * vy)
  ty = 2.0 * (z * vx - x * vz)
  tz = 2.0 * (x * vy - y * vx)
  return (
    vx + w * tx + y * tz - z * ty,
    vy + w * ty + z * tx - x * tz,
    vz + w * tz + x * ty - y * tx,
  )
####


def build_sectioned_tube_mesh(
    result: Any,
    *,
    radial_segments: int = 24,
    cap_ends: bool = True,
) -> VisualMesh:
  """Build a deterministic triangle mesh from a visual contract result."""

  if radial_segments < 3:
    raise ValueError('radial_segments must be at least three')
  sections = tuple(result.sections)
  vertices: list[Vector3] = []
  faces: list[tuple[int, int, int]] = []
  face_section_indices: list[int] = []
  for section in sections:
    for radial_index in range(radial_segments):
      angle = 2.0 * 3.141592653589793 * radial_index / radial_segments
      local = (
        section.radius_major_m * cos(angle),
        section.radius_minor_m * sin(angle),
        0.0,
      )
      offset = _rotate_vector(section.section_to_output_xyzw, local)
      vertices.append((
        section.center_m[0] + offset[0],
        section.center_m[1] + offset[1],
        section.center_m[2] + offset[2],
      ))
  for section_index in range(len(sections) - 1):
    first_ring = section_index * radial_segments
    second_ring = (section_index + 1) * radial_segments
    for radial_index in range(radial_segments):
      next_index = (radial_index + 1) % radial_segments
      a = first_ring + radial_index
      b = first_ring + next_index
      c = second_ring + radial_index
      d = second_ring + next_index
      faces.extend(((a, c, b), (b, c, d)))
      face_section_indices.extend((section_index, section_index))
  if cap_ends:
    start_center = len(vertices)
    vertices.append((
      float(sections[0].center_m[0]),
      float(sections[0].center_m[1]),
      float(sections[0].center_m[2]),
    ))
    end_center = len(vertices)
    vertices.append((
      float(sections[-1].center_m[0]),
      float(sections[-1].center_m[1]),
      float(sections[-1].center_m[2]),
    ))
    first_ring = 0
    last_ring = (len(sections) - 1) * radial_segments
    for radial_index in range(radial_segments):
      next_index = (radial_index + 1) % radial_segments
      faces.append((start_center, first_ring + next_index, first_ring + radial_index))
      face_section_indices.append(0)
      faces.append((end_center, last_ring + radial_index, last_ring + next_index))
      face_section_indices.append(len(sections) - 1)
  return VisualMesh(
    frame_id=result.metadata.output_frame_id,
    section_count=len(sections),
    vertices=tuple(vertices),
    faces=tuple(faces),
    face_section_indices=tuple(face_section_indices),
    section_channels=result.channels,
  )
####


def _load_json(path: str | Path) -> dict[str, Any]:
  payload = json.loads(Path(path).read_text(encoding='utf-8'))
  if not isinstance(payload, dict):
    raise ValueError(f'{path} must contain a JSON object')
  return payload
####


def load_straight_visual_definition(path: str | Path) -> StraightVisualDefinition:
  """Load a straight visual definition from raw or wrapped JSON."""

  payload = _load_json(path)
  if 'definition' in payload:
    schema = payload.get('asset_schema')
    if schema is not None and schema != _VISUAL_ASSET_SCHEMA:
      raise ValueError(f'unsupported visual asset schema: {schema}')
    payload = payload['definition']
  elif 'asset_schema' in payload:
    schema = payload.pop('asset_schema')
    if schema != _VISUAL_ASSET_SCHEMA:
      raise ValueError(f'unsupported visual asset schema: {schema}')
  if not isinstance(payload, dict):
    raise ValueError('visual definition must be a JSON object')
  return StraightVisualDefinition(**payload)
####


def write_straight_visual_asset(definition: StraightVisualDefinition, path: str | Path) -> Path:
  """Write a canonical wrapped v1 straight visual asset."""

  if not isinstance(definition, StraightVisualDefinition):
    raise ProviderConfigurationError('definition must be StraightVisualDefinition')
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  payload = {
    'asset_schema': _VISUAL_ASSET_SCHEMA,
    'definition': asdict(definition),
  }
  output.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')
  return output
####


def write_visual_result_json(result: Any, path: str | Path) -> Path:
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(result.model_dump_json(indent=2), encoding='utf-8')
  return output
####


def write_visual_mesh_json(mesh: VisualMesh, path: str | Path) -> Path:
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  output.write_text(json.dumps(mesh.model_dump(), indent=2) + '\n', encoding='utf-8')
  return output
####


def write_visual_obj(mesh: VisualMesh, path: str | Path) -> Path:
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  lines = [
    '# plume.visual.triangle-mesh@1',
    f'# frame_id: {mesh.frame_id}',
  ]
  lines.extend(f'v {x:.17g} {y:.17g} {z:.17g}' for x, y, z in mesh.vertices)
  lines.extend(f'f {a + 1} {b + 1} {c + 1}' for a, b, c in mesh.faces)
  output.write_text('\n'.join(lines) + '\n', encoding='utf-8')
  return output
####


def render_visual_preview(
    result: Any,
    path: str | Path,
    *,
    channel: str | None = None,
    radial_segments: int = 24,
    title: str = 'Sectioned-tube visual preview',
) -> Path:
  """Render one static 3-D preview using the optional ``plot`` extra."""

  try:
    from matplotlib import pyplot as plt
    from matplotlib.colors import Normalize
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
  except ImportError as error:
    raise RuntimeError('visual previews require the optional plot dependency: pip install .[plot]') from error
  mesh = build_sectioned_tube_mesh(result, radial_segments=radial_segments)
  if channel is not None and channel not in mesh.section_channels:
    raise ValueError(f'visual channel is not present: {channel}')
  output = Path(path)
  output.parent.mkdir(parents=True, exist_ok=True)
  figure = plt.figure(figsize=(8.0, 6.0))
  axes = figure.add_subplot(111, projection='3d')
  polygons = [
    [mesh.vertices[index] for index in face]
    for face in mesh.faces
  ]
  if channel is None:
    colors: Any = '#5b8ff9'
  else:
    values = mesh.section_channels[channel]
    minimum = min(values)
    maximum = max(values)
    normalizer = Normalize(vmin=minimum, vmax=maximum if maximum > minimum else minimum + 1.0)
    colors = [plt.get_cmap('viridis')(normalizer(values[index])) for index in mesh.face_section_indices]
  collection = Poly3DCollection(polygons, facecolor=colors, edgecolor='none', alpha=0.82)
  axes.add_collection3d(collection)
  lower = mesh.minimum_m
  upper = mesh.maximum_m
  center = tuple((lower[axis] + upper[axis]) / 2.0 for axis in range(3))
  extent = max(max(upper[axis] - lower[axis] for axis in range(3)), 1.0)
  axes.set_xlim(center[0] - extent / 2.0, center[0] + extent / 2.0)
  axes.set_ylim(center[1] - extent / 2.0, center[1] + extent / 2.0)
  axes.set_zlim(center[2] - extent / 2.0, center[2] + extent / 2.0)
  axes.set_box_aspect((max(upper[0] - lower[0], 1.0), max(upper[1] - lower[1], 1.0), max(upper[2] - lower[2], 1.0)))
  axes.set_xlabel('x [m]')
  axes.set_ylabel('y [m]')
  axes.set_zlabel('z [m]')
  axes.set_title(title)
  if channel is not None:
    figure.colorbar(plt.cm.ScalarMappable(norm=normalizer, cmap='viridis'), ax=axes, label=channel)
  figure.tight_layout()
  figure.savefig(output, dpi=140)
  plt.close(figure)
  return output
####


def evaluate_visual_definition(
    definition: StraightVisualDefinition | PrescribedVisualDefinition,
    *,
    maximum_section_count: int | None = None,
    requested_channels: tuple[str, ...] = (),
    configuration: PrescribedVisualConfiguration | None = None,
    time_s: float = 0.0,
) -> Any:
  """Evaluate a visual definition through the public session/snapshot path."""

  source_frame = definition.frame_id
  if isinstance(definition, StraightVisualDefinition):
    provider = StraightVisualProvider()
    session = provider.create_session(definition=definition)
    default_count = definition.base_section_count
  elif isinstance(definition, PrescribedVisualDefinition):
    provider = PrescribedVisualProvider(configuration)
    session = provider.create_session(definition=definition)
    default_count = len(definition.sections)
  else:
    raise ProviderConfigurationError('definition must be a supported visual definition')
  snapshot = session.create_snapshot(
    time_s=time_s,
    source_pose=Pose(
      frame_id='world',
      translation_m=(0.0, 0.0, 0.0),
      rotation_xyzw=(0.0, 0.0, 0.0, 1.0),
    ),
    dynamic_state={},
    ambient_state={},
  )
  try:
    return snapshot.evaluate(
      VISUAL_SECTIONED_TUBE_V1,
      VisualSectionedTubeRequest(
        output_frame_id=source_frame,
        sampling=VisualSampling(maximum_section_count=maximum_section_count or default_count),
        requested_channels=requested_channels,
      ),
    )
  finally:
    session.close()
####


def evaluate_shock_cell_visual(
    result: ShockCellSolveResult,
    *,
    section_count: int = 64,
    minimum_radius_m: float = 1.0e-6,
    requested_channels: tuple[str, ...] = ('core_radius_fraction',),
    configuration: PrescribedVisualConfiguration | None = None,
    time_s: float = 0.0,
) -> Any:
  """Evaluate a simple straight solver result as a visual product."""

  if result.status.name in {'INVALID_INPUT', 'NUMERICAL_FAILURE', 'OUTSIDE_MODEL_VALIDITY'}:
    raise ProductOutsideApplicabilityError(
        'simple straight visual geometry is unavailable because the source solver '
        f'reported {result.status.value}'
    )
  if not result.zones:
    raise ProductOutsideApplicabilityError(
        'simple straight visual geometry requires at least one finite solved zone'
    )

  definition = visual_definition_from_shock_cells(
    result,
    section_count=section_count,
    minimum_radius_m=minimum_radius_m,
  )
  selected_configuration = configuration or PrescribedVisualConfiguration(
    geometry_claim=GeometryClaim.ENGINEERING_APPROXIMATE,
    derivation=Derivation.ADAPTED,
    consistency=ConsistencyLevel.INDEPENDENT,
    applicability_status=(
      ApplicabilityStatus.MARGINAL
      if result.status.name == 'CONVERGED_AT_BOUNDARY'
      else ApplicabilityStatus.INSIDE
    ),
    applicability_reasons=(
      'visual envelope is adapted from a finite low-order shock-cell construction',
      'result is limited by the requested low-order construction boundary',
    ) if result.status.name == 'CONVERGED_AT_BOUNDARY' else (
      'visual envelope is adapted from a finite low-order shock-cell construction',
    ),
    warnings=(
      'geometry is an engineering-approximate display envelope; it is not a conservative plume boundary',
    ),
  )
  return evaluate_visual_definition(
    definition,
    requested_channels=requested_channels,
    configuration=selected_configuration,
    time_s=time_s,
  )
####


def evaluate_nozzle_geometry_visual(
    geometry: NozzleGeometry,
    *,
    total_pressure_Pa: float,
    total_temperature_K: float,
    ambient_pressure_Pa: float,
    gas: CaloricallyPerfectGas,
    ambient_temperature_K: float = 300.0,
    section_count: int = 64,
    expansion_characteristics: int = 2,
    compression_characteristics: int = 1,
    max_cells: int = 1,
    pressure_match_rtol: float = 1.0e-4,
    requested_channels: tuple[str, ...] = ('core_radius_fraction',),
    time_s: float = 0.0,
) -> Any:
  """Run the supported geometry path and adapt finite zones to visual output."""

  exit_state = derive_nozzle_exit_from_geometry(
      geometry,
      total_pressure_Pa=total_pressure_Pa,
      total_temperature_K=total_temperature_K,
      gas=gas,
  )
  ambient = derive_ambient_state(
      AmbientInput(
          pressure_Pa=ambient_pressure_Pa,
          temperature_K=ambient_temperature_K,
      ),
      gas,
  )
  solved = solve_shock_cells(ShockCellSolveConfig(
      exit=exit_state,
      ambient=ambient,
      expansion_characteristics=expansion_characteristics,
      compression_characteristics=compression_characteristics,
      max_cells=max_cells,
      pressure_match_rtol=pressure_match_rtol,
  ))
  return evaluate_shock_cell_visual(
      solved,
      section_count=section_count,
      requested_channels=requested_channels,
      time_s=time_s,
  )
####


def _zone_vertices(zone: Any) -> tuple[tuple[float, float], ...]:
  if hasattr(zone, 'vertices_xr_m'):
    raw_vertices = zone.vertices_xr_m
  elif hasattr(zone, 'coordinates'):
    raw_vertices = zone.coordinates.corners_ru
  else:
    raise ProviderConfigurationError('zone does not expose x/r vertices')
  vertices = tuple((float(vertex[0]), float(vertex[1])) for vertex in raw_vertices)
  if len(vertices) < 3 or not all(isfinite(value) for vertex in vertices for value in vertex):
    raise ProviderConfigurationError('zone vertices must be finite polygons')
  return vertices
####


def _radius_at_x(vertices: tuple[tuple[float, float], ...], x_value: float, tolerance: float) -> float | None:
  candidates: list[float] = []
  for first, second in zip(vertices, vertices[1:] + vertices[:1]):
    x0, r0 = first
    x1, r1 = second
    if abs(x1 - x0) <= tolerance:
      if abs(x_value - x0) <= tolerance:
        candidates.extend((abs(r0), abs(r1)))
      continue
    lower = min(x0, x1) - tolerance
    upper = max(x0, x1) + tolerance
    if lower <= x_value <= upper:
      fraction = (x_value - x0) / (x1 - x0)
      candidates.append(abs(r0 + fraction * (r1 - r0)))
  return max(candidates) if candidates else None
####


def visual_definition_from_zone_results(
    zones: Sequence[Any],
    *,
    frame_id: str = 'source-local',
    section_count: int = 64,
    minimum_radius_m: float = 1.0e-6,
    maximum_axial_extent_m: float | None = None,
) -> PrescribedVisualDefinition:
  """Adapt finite straight x/r zones into an axisymmetric visual envelope."""

  if len(zones) == 0:
    raise ProviderConfigurationError('at least one finite zone is required')
  if section_count < 2:
    raise ProviderConfigurationError('section_count must be at least two')
  if not isfinite(minimum_radius_m) or minimum_radius_m <= 0.0:
    raise ProviderConfigurationError('minimum_radius_m must be finite and positive')
  if maximum_axial_extent_m is not None and (
      not isfinite(maximum_axial_extent_m) or maximum_axial_extent_m <= 0.0
  ):
    raise ProviderConfigurationError('maximum_axial_extent_m must be finite and positive')
  polygon_list = tuple(_zone_vertices(zone) for zone in zones)
  x_values = tuple(value for polygon in polygon_list for value, _ in polygon)
  start_x = min(x_values)
  end_x = max(x_values)
  if maximum_axial_extent_m is not None:
    end_x = min(end_x, start_x + maximum_axial_extent_m)
  span = end_x - start_x
  if not isfinite(span) or span <= 0.0:
    raise ProviderConfigurationError('zone geometry must span a positive axial distance')
  tolerance = max(1.0e-10, span * 1.0e-9)
  characteristic_x = _unique_sorted(
    (
      value
      for polygon in polygon_list
      for value, _ in polygon
      if start_x - tolerance <= value <= end_x + tolerance
    ),
    tolerance,
  )
  if len(characteristic_x) > section_count:
    characteristic_x = tuple(
      characteristic_x[index]
      for index in _sample_station_indices(len(characteristic_x), section_count)
    )
  uniform_x = tuple(start_x + span * index / (section_count - 1) for index in range(section_count))
  regular_x = tuple(
    value for value in uniform_x
    if not any(abs(value - critical) <= tolerance for critical in characteristic_x)
  )
  remaining = section_count - len(characteristic_x)
  if remaining <= 0:
    selected_regular = ()
  elif len(regular_x) <= remaining:
    selected_regular = regular_x[:remaining]
  else:
    selected_regular = tuple(
      regular_x[index]
      for index in _sample_station_indices(len(regular_x), remaining)
    )
  station_x = _unique_sorted((*characteristic_x, *selected_regular), tolerance)
  if len(station_x) < 2:
    raise ProviderConfigurationError('zone geometry must produce at least two axial stations')
  radii: list[float] = []
  for station in station_x:
    candidates = tuple(
      radius
      for polygon in polygon_list
      for radius in (_radius_at_x(polygon, station, tolerance),)
      if radius is not None
    )
    if not candidates:
      raise ProviderConfigurationError(f'zone geometry has no cross-section at x={station}')
    radii.append(max(candidates))
  maximum_radius = max(radii)
  floor = max(minimum_radius_m, maximum_radius * 1.0e-6)
  normalized_radii = tuple(max(radius, floor) for radius in radii)
  sections = tuple(
    VisualSection(
      arc_length_m=station - start_x,
      center_m=(station, 0.0, 0.0),
      section_to_output_xyzw=(0.0, 0.0, 0.0, 1.0),
      radius_major_m=radius,
      radius_minor_m=radius,
    )
    for station, radius in zip(station_x, normalized_radii, strict=True)
  )
  return PrescribedVisualDefinition(
    frame_id=frame_id,
    sections=sections,
    channels={
      'core_radius_fraction': tuple(radius / max(normalized_radii) for radius in normalized_radii),
      'opacity_weight': tuple(1.0 for _ in normalized_radii),
    },
  )
####


def _unique_sorted(values: Iterable[float], tolerance: float) -> tuple[float, ...]:
  ordered = sorted(float(value) for value in values)
  unique: list[float] = []
  for value in ordered:
    if not unique or abs(value - unique[-1]) > tolerance:
      unique.append(value)
  return tuple(unique)
####


def _sample_station_indices(total_count: int, selected_count: int) -> tuple[int, ...]:
  if selected_count <= 0:
    return ()
  if selected_count >= total_count:
    return tuple(range(total_count))
  return tuple(
    int(round(index * (total_count - 1) / (selected_count - 1)))
    for index in range(selected_count)
  )
####


def visual_definition_from_shock_cells(
    result: ShockCellSolveResult,
    *,
    frame_id: str = 'source-local',
    section_count: int = 64,
    minimum_radius_m: float = 1.0e-6,
    maximum_axial_extent_m: float | None = None,
) -> PrescribedVisualDefinition:
  """Adapt the current simple straight shock-cell result to visual geometry."""

  if not isinstance(result, ShockCellSolveResult):
    raise ProviderConfigurationError('result must be ShockCellSolveResult')
  return visual_definition_from_zone_results(
    result.zones,
    frame_id=frame_id,
    section_count=section_count,
    minimum_radius_m=minimum_radius_m,
    maximum_axial_extent_m=maximum_axial_extent_m,
  )
####
