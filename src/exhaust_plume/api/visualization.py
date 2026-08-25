"""Renderer-neutral consumers for the public sectioned-tube API result.

The sectioned-tube contract is deliberately independent of any particular
renderer.  This module provides small, deterministic adapters for consumers
that need line data or a tessellated display mesh.  It consumes only the
public :class:`SectionedTubeResult`; solver zones, meshes, and other private
states never cross this boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, pi, sin
from typing import TypeAlias

from exhaust_plume.api.capabilities import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.api.contracts import (
  FeatureAssociation,
  FeatureChannel,
  ResultStatus,
  SectionedTubeResult,
)

Vector3: TypeAlias = tuple[float, float, float]
ScalarValue: TypeAlias = float | None


def _as_vector3(values: tuple[float, ...]) -> Vector3:
  if len(values) != 3:
    raise ValueError('contract vector must contain exactly three values')
  ####
  return (float(values[0]), float(values[1]), float(values[2]))
####


@dataclass(frozen=True, slots=True)
class SectionedTubeGeometrySeries:
  """Line-friendly geometry sampled at the contract's section stations."""

  frame_id: str
  arc_length_m: tuple[float, ...]
  centerline_m: tuple[Vector3, ...]
  tangent: tuple[Vector3, ...]
  normal_1: tuple[Vector3, ...]
  normal_2: tuple[Vector3, ...]
  semi_axis_1_m: tuple[float, ...]
  semi_axis_2_m: tuple[float, ...]

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('geometry series frame_id must not be empty')
    ####
    section_count = len(self.arc_length_m)
    if section_count < 2:
      raise ValueError('geometry series must contain at least two sections')
    ####
    for name, vectors in (
      ('centerline', self.centerline_m),
      ('tangent', self.tangent),
      ('normal_1', self.normal_1),
      ('normal_2', self.normal_2),
    ):
      if len(vectors) != section_count:
        raise ValueError(f'geometry series {name} length must match arc length')
      ####
    ####
    if len(self.semi_axis_1_m) != section_count or len(self.semi_axis_2_m) != section_count:
      raise ValueError('geometry series axes must match arc length')
    ####
    if any(not isfinite(value) for value in self.arc_length_m):
      raise ValueError('geometry series arc lengths must be finite')
    ####
    if any(right <= left for left, right in zip(self.arc_length_m, self.arc_length_m[1:])):
      raise ValueError('geometry series arc lengths must be strictly increasing')
    ####
    for name, vectors in (
      ('centers', self.centerline_m),
      ('tangents', self.tangent),
      ('normal_1', self.normal_1),
      ('normal_2', self.normal_2),
    ):
      if any(len(vector) != 3 or not all(isfinite(value) for value in vector) for vector in vectors):
        raise ValueError(f'geometry series {name} must contain finite 3-vectors')
    ####
    if any(
      not isfinite(value) or value <= 0.
      for value in (*self.semi_axis_1_m, *self.semi_axis_2_m)
    ):
      raise ValueError('geometry series axes must be finite and positive')
    ####
    object.__setattr__(self, 'arc_length_m', tuple(float(value) for value in self.arc_length_m))
    object.__setattr__(
      self,
      'centerline_m',
      tuple(tuple(float(value) for value in center) for center in self.centerline_m),
    )
    for name in ('tangent', 'normal_1', 'normal_2'):
      object.__setattr__(
        self,
        name,
        tuple(
          tuple(float(value) for value in vector)
          for vector in getattr(self, name)
        ),
      )
    object.__setattr__(self, 'semi_axis_1_m', tuple(float(value) for value in self.semi_axis_1_m))
    object.__setattr__(self, 'semi_axis_2_m', tuple(float(value) for value in self.semi_axis_2_m))
  ####
####


@dataclass(frozen=True, slots=True)
class SectionedTubeChannelLine:
  """One component of one public feature channel as a line series."""

  frame_id: str
  channel_id: str
  semantic: str
  unit: str
  association: FeatureAssociation
  component_index: int
  arc_length_m: tuple[float, ...]
  values: tuple[ScalarValue, ...]

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('channel line frame_id must not be empty')
    ####
    if not self.channel_id or not self.semantic or not self.unit:
      raise ValueError('channel line identity and unit fields must not be empty')
    ####
    if self.component_index < 0:
      raise ValueError('channel line component_index must be nonnegative')
    ####
    if len(self.arc_length_m) != len(self.values):
      raise ValueError('channel line arc length and value arrays must match')
    ####
    if len(self.arc_length_m) < 2:
      raise ValueError('channel line must contain at least two samples')
    ####
    if any(not isfinite(value) for value in self.arc_length_m):
      raise ValueError('channel line arc lengths must be finite')
    ####
    if any(right <= left for left, right in zip(self.arc_length_m, self.arc_length_m[1:])):
      raise ValueError('channel line arc lengths must be strictly increasing')
    ####
    if any(value is not None and not isfinite(value) for value in self.values):
      raise ValueError('channel line values must be finite or null')
    ####
    object.__setattr__(self, 'arc_length_m', tuple(float(value) for value in self.arc_length_m))
    object.__setattr__(
      self,
      'values',
      tuple(None if value is None else float(value) for value in self.values),
    )
  ####
####


@dataclass(frozen=True, slots=True)
class SectionedTubeLineData:
  """All line-friendly geometry and feature data from one result."""

  geometry: SectionedTubeGeometrySeries
  channels: tuple[SectionedTubeChannelLine, ...]

  def __post_init__(self) -> None:
    if any(channel.frame_id != self.geometry.frame_id for channel in self.channels):
      raise ValueError('line data channels must use the geometry frame')
    ####
    if any(channel.arc_length_m != self.geometry.arc_length_m for channel in self.channels):
      raise ValueError('line data channels must use the geometry arc-length axis')
    ####
    object.__setattr__(self, 'channels', tuple(self.channels))
  ####
####


@dataclass(frozen=True, slots=True)
class SectionedTubeRenderMesh:
  """Triangle mesh derived from public sectioned-tube geometry.

  ``feature_channels`` are retained as contract objects instead of being
  folded into vertex colors.  A renderer may choose how to display them while
  preserving their semantic names, units, associations, and null validity.
  """

  frame_id: str
  section_count: int
  radial_segments: int
  vertices: tuple[Vector3, ...]
  faces: tuple[tuple[int, int, int], ...]
  face_section_indices: tuple[int, ...]
  feature_channels: tuple[FeatureChannel, ...] = ()

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('mesh frame_id must not be empty')
    ####
    if self.section_count < 2:
      raise ValueError('mesh section_count must be at least two')
    ####
    if self.radial_segments < 3:
      raise ValueError('mesh radial_segments must be at least three')
    ####
    if not self.vertices:
      raise ValueError('mesh must contain vertices')
    ####
    if len(self.faces) != len(self.face_section_indices):
      raise ValueError('mesh faces and face_section_indices must have matching lengths')
    ####
    normalized_vertices: list[Vector3] = []
    for vertex in self.vertices:
      if len(vertex) != 3 or not all(isfinite(value) for value in vertex):
        raise ValueError('mesh vertices must be finite 3-vectors')
      ####
      normalized_vertices.append((float(vertex[0]), float(vertex[1]), float(vertex[2])))
    ####
    normalized_faces: list[tuple[int, int, int]] = []
    for face in self.faces:
      if len(face) != 3 or any(index < 0 or index >= len(normalized_vertices) for index in face):
        raise ValueError('mesh faces must contain valid vertex indices')
      ####
      normalized_faces.append((int(face[0]), int(face[1]), int(face[2])))
    ####
    if any(index < 0 or index >= self.section_count for index in self.face_section_indices):
      raise ValueError('mesh face section indices must reference sections')
    ####
    object.__setattr__(self, 'vertices', tuple(normalized_vertices))
    object.__setattr__(self, 'faces', tuple(normalized_faces))
    object.__setattr__(self, 'face_section_indices', tuple(int(index) for index in self.face_section_indices))
    object.__setattr__(self, 'feature_channels', tuple(self.feature_channels))
  ####

  @property
  def minimum_m(self) -> Vector3:
    """Minimum coordinate of the tessellated display geometry."""

    return tuple(min(vertex[axis] for vertex in self.vertices) for axis in range(3))  # type: ignore[return-value]
  ####

  @property
  def maximum_m(self) -> Vector3:
    """Maximum coordinate of the tessellated display geometry."""

    return tuple(max(vertex[axis] for vertex in self.vertices) for axis in range(3))  # type: ignore[return-value]
  ####

  def model_dump(self) -> dict[str, object]:
    """Return a JSON-compatible representation for a renderer adapter."""

    return {
      'schema': 'plume.visual.sectioned-tube-render-mesh@1',
      'capability_id': VISUAL_SECTIONED_TUBE_V1,
      'frame_id': self.frame_id,
      'section_count': self.section_count,
      'radial_segments': self.radial_segments,
      'vertices': [list(vertex) for vertex in self.vertices],
      'faces': [list(face) for face in self.faces],
      'face_section_indices': list(self.face_section_indices),
      'feature_channels': [channel.model_dump(mode='json') for channel in self.feature_channels],
      'bounds': {
        'minimum_m': list(self.minimum_m),
        'maximum_m': list(self.maximum_m),
      },
    }
  ####
####


def _require_renderable_result(result: object) -> SectionedTubeResult:
  if not isinstance(result, SectionedTubeResult):
    raise TypeError('result must be an exhaust_plume.api SectionedTubeResult')
  ####
  if result.envelope.status is ResultStatus.FAILED:
    raise ValueError('a FAILED sectioned-tube result cannot be visualized')
  ####
  if not result.envelope.applicability.supported:
    raise ValueError('an out-of-applicability sectioned-tube result cannot be visualized')
  ####
  return result
####


def extract_sectioned_tube_geometry(result: SectionedTubeResult) -> SectionedTubeGeometrySeries:
  """Extract contract geometry as aligned line-friendly arrays."""

  checked = _require_renderable_result(result)
  sections = checked.payload.sections
  return SectionedTubeGeometrySeries(
    frame_id=checked.envelope.frame.frame_id,
    arc_length_m=tuple(section.arc_length_m for section in sections),
    centerline_m=tuple(_as_vector3(section.center_m) for section in sections),
    tangent=tuple(_as_vector3(section.tangent) for section in sections),
    normal_1=tuple(_as_vector3(section.normal_1) for section in sections),
    normal_2=tuple(_as_vector3(section.normal_2) for section in sections),
    semi_axis_1_m=tuple(section.semi_axis_1_m for section in sections),
    semi_axis_2_m=tuple(section.semi_axis_2_m for section in sections),
  )
####


def extract_sectioned_tube_channel_lines(
  result: SectionedTubeResult,
  *,
  channel_id: str | None = None,
) -> tuple[SectionedTubeChannelLine, ...]:
  """Extract feature channels without discarding component or validity data.

  A multi-component channel yields one line per component.  Null values remain
  null so a plotting or analysis consumer can distinguish missing samples from
  zero-valued samples.
  """

  checked = _require_renderable_result(result)
  channels = checked.payload.feature_channels
  if channel_id is not None:
    channels = tuple(channel for channel in channels if channel.channel_id == channel_id)
    if not channels:
      available = ', '.join(channel.channel_id for channel in checked.payload.feature_channels) or '<none>'
      raise KeyError(f'unknown feature channel {channel_id!r}; available: {available}')
    ####
  ####
  arc_lengths = tuple(section.arc_length_m for section in checked.payload.sections)
  frame_id = checked.envelope.frame.frame_id
  lines: list[SectionedTubeChannelLine] = []
  for channel in channels:
    for component_index in range(channel.component_count):
      values = tuple(
        channel.values[section_index * channel.component_count + component_index]
        for section_index in range(len(arc_lengths))
      )
      lines.append(SectionedTubeChannelLine(
        frame_id=frame_id,
        channel_id=channel.channel_id,
        semantic=channel.semantic,
        unit=channel.unit,
        association=channel.association,
        component_index=component_index,
        arc_length_m=arc_lengths,
        values=values,
      ))
    ####
  ####
  return tuple(lines)
####


def extract_sectioned_tube_line_data(
  result: SectionedTubeResult,
  *,
  channel_id: str | None = None,
) -> SectionedTubeLineData:
  """Extract geometry and optional feature lines in one renderer-neutral object."""

  return SectionedTubeLineData(
    geometry=extract_sectioned_tube_geometry(result),
    channels=extract_sectioned_tube_channel_lines(result, channel_id=channel_id),
  )
####


def build_sectioned_tube_render_mesh(
  result: SectionedTubeResult,
  *,
  radial_segments: int = 24,
  cap_ends: bool = True,
) -> SectionedTubeRenderMesh:
  """Tessellate public section frames into a deterministic display mesh.

  The ring point is constructed directly from ``normal_1`` and ``normal_2``:

  ``center + semi_axis_1*cos(theta)*normal_1 + semi_axis_2*sin(theta)*normal_2``.

  This preserves the section frame supplied by the contract and does not infer
  orientation from a private solver or from a fixed world axis.
  """

  checked = _require_renderable_result(result)
  if isinstance(radial_segments, bool) or not isinstance(radial_segments, int):
    raise TypeError('radial_segments must be an integer')
  ####
  if radial_segments < 3:
    raise ValueError('radial_segments must be at least three')
  ####
  sections = checked.payload.sections
  vertices: list[Vector3] = []
  faces: list[tuple[int, int, int]] = []
  face_section_indices: list[int] = []
  for section in sections:
    for radial_index in range(radial_segments):
      angle = 2.0 * pi * radial_index / radial_segments
      cosine = cos(angle)
      sine = sin(angle)
      vertices.append((
        section.center_m[0]
        + section.semi_axis_1_m * cosine * section.normal_1[0]
        + section.semi_axis_2_m * sine * section.normal_2[0],
        section.center_m[1]
        + section.semi_axis_1_m * cosine * section.normal_1[1]
        + section.semi_axis_2_m * sine * section.normal_2[1],
        section.center_m[2]
        + section.semi_axis_1_m * cosine * section.normal_1[2]
        + section.semi_axis_2_m * sine * section.normal_2[2],
      ))
    ####
  ####
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
    ####
  ####
  if cap_ends:
    start_center = len(vertices)
    vertices.append(_as_vector3(sections[0].center_m))
    end_center = len(vertices)
    vertices.append(_as_vector3(sections[-1].center_m))
    first_ring = 0
    last_ring = (len(sections) - 1) * radial_segments
    for radial_index in range(radial_segments):
      next_index = (radial_index + 1) % radial_segments
      faces.append((start_center, first_ring + next_index, first_ring + radial_index))
      face_section_indices.append(0)
      faces.append((end_center, last_ring + radial_index, last_ring + next_index))
      face_section_indices.append(len(sections) - 1)
    ####
  ####
  return SectionedTubeRenderMesh(
    frame_id=checked.envelope.frame.frame_id,
    section_count=len(sections),
    radial_segments=radial_segments,
    vertices=tuple(vertices),
    faces=tuple(faces),
    face_section_indices=tuple(face_section_indices),
    feature_channels=tuple(checked.payload.feature_channels),
  )
####


__all__ = (
  'SectionedTubeChannelLine',
  'SectionedTubeGeometrySeries',
  'SectionedTubeLineData',
  'SectionedTubeRenderMesh',
  'build_sectioned_tube_render_mesh',
  'extract_sectioned_tube_channel_lines',
  'extract_sectioned_tube_geometry',
  'extract_sectioned_tube_line_data',
)
