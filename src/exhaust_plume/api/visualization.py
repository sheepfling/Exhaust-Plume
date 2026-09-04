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
from typing import Any, TypeAlias

from exhaust_plume.api.capabilities import VISUAL_SECTIONED_TUBE_V1
from exhaust_plume.api.contracts import (
  FeatureAssociation,
  FeatureChannel,
  ItemStatus,
  PlumeFluxSectionResult,
  ProductResult,
  ResultStatus,
  ResultEnvelope,
  SectionedTubeResult,
  SpectralRadiantIntensityResult,
  SpectralRayTransferResult,
)
from exhaust_plume.api.visualization_spec import VisualizationSpec

Vector3: TypeAlias = tuple[float, float, float]
ScalarValue: TypeAlias = float | None
Matrix2: TypeAlias = tuple[tuple[float, float], tuple[float, float]]


def _as_vector3(values: tuple[float, ...]) -> Vector3:
  if len(values) != 3:
    raise ValueError('contract vector must contain exactly three values')
  ####
  return (float(values[0]), float(values[1]), float(values[2]))
####


def _check_result_envelope(envelope: ResultEnvelope) -> None:
  if envelope.status is ResultStatus.FAILED:
    raise ValueError('a FAILED product result cannot be visualized')
  ####
  if not envelope.applicability.supported:
    raise ValueError('an out-of-applicability product result cannot be visualized')
  ####
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
    ####
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
  try:
    _check_result_envelope(result.envelope)
  except ValueError as error:
    raise ValueError(str(error).replace('product result', 'sectioned-tube result')) from error
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


@dataclass(frozen=True, slots=True)
class SpectralRadiantIntensityGrid:
  """Renderer-neutral wavelength/direction grid for the signature product."""

  frame_id: str
  directions: tuple[Vector3, ...]
  wavelengths_m: tuple[float, ...]
  radiant_intensity_W_sr_m: tuple[tuple[ScalarValue, ...], ...]
  validity_mask: tuple[tuple[bool, ...], ...]
  uncertainty: dict[str, Any]

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('spectral-intensity grid frame_id must not be empty')
    ####
    if not self.directions or not self.wavelengths_m:
      raise ValueError('spectral-intensity grid axes must not be empty')
    ####
    if len(self.radiant_intensity_W_sr_m) != len(self.directions):
      raise ValueError('spectral-intensity direction axis does not match directions')
    ####
    if len(self.validity_mask) != len(self.directions):
      raise ValueError('spectral-intensity validity axis does not match directions')
    ####
    if any(not isfinite(value) or value <= 0. for value in self.wavelengths_m):
      raise ValueError('spectral-intensity wavelengths must be finite and positive')
    ####
    if any(right <= left for left, right in zip(self.wavelengths_m, self.wavelengths_m[1:])):
      raise ValueError('spectral-intensity wavelengths must be strictly increasing')
    ####
    wavelength_count = len(self.wavelengths_m)
    for direction_index, (direction, values, validity) in enumerate(zip(
      self.directions,
      self.radiant_intensity_W_sr_m,
      self.validity_mask,
      strict=True,
    )):
      if len(direction) != 3 or not all(isfinite(value) for value in direction):
        raise ValueError(f'spectral-intensity direction {direction_index} must be finite')
      ####
      if len(values) != wavelength_count or len(validity) != wavelength_count:
        raise ValueError('spectral-intensity wavelength axes do not match')
      ####
      if any(
        valid != (value is not None)
        for value, valid in zip(values, validity, strict=True)
      ):
        raise ValueError('spectral-intensity values and validity mask disagree')
      ####
      if any(value is not None and (not isfinite(value) or value < 0.) for value in values):
        raise ValueError('spectral-intensity values must be finite and nonnegative')
      ####
    ####
    object.__setattr__(self, 'directions', tuple(_as_vector3(direction) for direction in self.directions))
    object.__setattr__(self, 'wavelengths_m', tuple(float(value) for value in self.wavelengths_m))
    object.__setattr__(
      self,
      'radiant_intensity_W_sr_m',
      tuple(
        tuple(None if value is None else float(value) for value in row)
        for row in self.radiant_intensity_W_sr_m
      ),
    )
    object.__setattr__(self, 'validity_mask', tuple(tuple(row) for row in self.validity_mask))
    object.__setattr__(self, 'uncertainty', dict(self.uncertainty))
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRadiantIntensityLine:
  """One direction's wavelength line from a spectral-intensity grid."""

  frame_id: str
  direction_index: int
  direction: Vector3
  wavelengths_m: tuple[float, ...]
  values_W_sr_m: tuple[ScalarValue, ...]
  validity_mask: tuple[bool, ...]

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('spectral-intensity line frame_id must not be empty')
    ####
    if self.direction_index < 0:
      raise ValueError('spectral-intensity line direction_index must be nonnegative')
    ####
    if len(self.wavelengths_m) != len(self.values_W_sr_m) or len(self.wavelengths_m) != len(self.validity_mask):
      raise ValueError('spectral-intensity line axes must have matching lengths')
    ####
    object.__setattr__(self, 'direction', _as_vector3(self.direction))
    object.__setattr__(self, 'wavelengths_m', tuple(float(value) for value in self.wavelengths_m))
    object.__setattr__(
      self,
      'values_W_sr_m',
      tuple(None if value is None else float(value) for value in self.values_W_sr_m),
    )
    object.__setattr__(self, 'validity_mask', tuple(self.validity_mask))
  ####
####


def extract_spectral_radiant_intensity_grid(
  result: SpectralRadiantIntensityResult,
) -> SpectralRadiantIntensityGrid:
  """Extract the signature product as a renderer-neutral spectral grid."""

  if not isinstance(result, SpectralRadiantIntensityResult):
    raise TypeError('result must be an exhaust_plume.api SpectralRadiantIntensityResult')
  ####
  _check_result_envelope(result.envelope)
  payload = result.payload
  return SpectralRadiantIntensityGrid(
    frame_id=result.envelope.frame.frame_id,
    directions=tuple(_as_vector3(direction) for direction in payload.directions),
    wavelengths_m=tuple(payload.wavelengths_m),
    radiant_intensity_W_sr_m=tuple(
      tuple(value for value in row)
      for row in payload.radiant_intensity_W_sr_m
    ),
    validity_mask=tuple(tuple(row) for row in payload.validity_mask),
    uncertainty=payload.uncertainty,
  )
####


def extract_spectral_radiant_intensity_lines(
  result: SpectralRadiantIntensityResult,
  *,
  direction_index: int | None = None,
) -> tuple[SpectralRadiantIntensityLine, ...]:
  """Extract one wavelength line per requested signature direction."""

  grid = extract_spectral_radiant_intensity_grid(result)
  if direction_index is None:
    selected_indices = tuple(range(len(grid.directions)))
  else:
    if direction_index < 0 or direction_index >= len(grid.directions):
      raise IndexError(f'direction_index out of range: {direction_index}')
    ####
    selected_indices = (direction_index,)
  ####
  return tuple(
    SpectralRadiantIntensityLine(
      frame_id=grid.frame_id,
      direction_index=index,
      direction=grid.directions[index],
      wavelengths_m=grid.wavelengths_m,
      values_W_sr_m=grid.radiant_intensity_W_sr_m[index],
      validity_mask=grid.validity_mask[index],
    )
    for index in selected_indices
  )
####


@dataclass(frozen=True, slots=True)
class SpectralRayTransferLine:
  """One ray's spectrum and ray-domain metadata.

  The standard API exposes origin/direction and item status here; it does not
  expose a plume intersection interval, so this adapter does not infer one.
  """

  frame_id: str
  ray_id: str
  origin_m: Vector3
  direction: Vector3
  wavelengths_m: tuple[float, ...]
  source_radiance_W_m2_sr_m: tuple[ScalarValue, ...]
  background_transmittance: tuple[ScalarValue, ...]
  validity_mask: tuple[bool, ...]
  item_status: ItemStatus

  def __post_init__(self) -> None:
    if not self.frame_id or not self.ray_id:
      raise ValueError('ray-transfer line frame_id and ray_id must not be empty')
    ####
    if len(self.origin_m) != 3 or len(self.direction) != 3:
      raise ValueError('ray-transfer line origin and direction must be 3-vectors')
    ####
    if not (
      len(self.wavelengths_m) == len(self.source_radiance_W_m2_sr_m)
      == len(self.background_transmittance) == len(self.validity_mask)
    ):
      raise ValueError('ray-transfer line wavelength axes must have matching lengths')
    ####
    if any(
      valid != (source is not None and transmittance is not None)
      for source, transmittance, valid in zip(
        self.source_radiance_W_m2_sr_m,
        self.background_transmittance,
        self.validity_mask,
        strict=True,
      )
    ):
      raise ValueError('ray-transfer line values and validity mask disagree')
    ####
    object.__setattr__(self, 'origin_m', _as_vector3(self.origin_m))
    object.__setattr__(self, 'direction', _as_vector3(self.direction))
    object.__setattr__(self, 'wavelengths_m', tuple(float(value) for value in self.wavelengths_m))
    object.__setattr__(
      self,
      'source_radiance_W_m2_sr_m',
      tuple(None if value is None else float(value) for value in self.source_radiance_W_m2_sr_m),
    )
    object.__setattr__(
      self,
      'background_transmittance',
      tuple(None if value is None else float(value) for value in self.background_transmittance),
    )
    object.__setattr__(self, 'validity_mask', tuple(self.validity_mask))
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRayTransferData:
  """All ray lines sharing one resolved-transfer wavelength axis."""

  frame_id: str
  wavelengths_m: tuple[float, ...]
  lines: tuple[SpectralRayTransferLine, ...]

  def __post_init__(self) -> None:
    if not self.frame_id or not self.lines:
      raise ValueError('ray-transfer data requires a frame and at least one line')
    ####
    if any(line.frame_id != self.frame_id for line in self.lines):
      raise ValueError('ray-transfer lines must use the shared frame')
    ####
    if any(line.wavelengths_m != self.wavelengths_m for line in self.lines):
      raise ValueError('ray-transfer lines must use the shared wavelength axis')
    ####
    object.__setattr__(self, 'wavelengths_m', tuple(float(value) for value in self.wavelengths_m))
    object.__setattr__(self, 'lines', tuple(self.lines))
  ####
####


def extract_spectral_ray_transfer_lines(
  result: SpectralRayTransferResult,
  *,
  ray_id: str | None = None,
) -> tuple[SpectralRayTransferLine, ...]:
  """Extract ray spectra, hit/miss state, and optional plume intervals."""

  if not isinstance(result, SpectralRayTransferResult):
    raise TypeError('result must be an exhaust_plume.api SpectralRayTransferResult')
  ####
  _check_result_envelope(result.envelope)
  payload = result.payload
  selected_indices = tuple(
    index for index, candidate in enumerate(payload.ray_ids)
    if ray_id is None or candidate == ray_id
  )
  if ray_id is not None and not selected_indices:
    raise KeyError(f'unknown ray_id {ray_id!r}')
  ####
  return tuple(
    SpectralRayTransferLine(
      frame_id=result.envelope.frame.frame_id,
      ray_id=payload.ray_ids[index],
      origin_m=_as_vector3(payload.origins_m[index]),
      direction=_as_vector3(payload.directions[index]),
      wavelengths_m=tuple(payload.wavelengths_m),
      source_radiance_W_m2_sr_m=tuple(payload.source_radiance_W_m2_sr_m[index]),
      background_transmittance=tuple(payload.background_transmittance[index]),
      validity_mask=tuple(payload.validity_mask[index]),
      item_status=payload.item_status[index],
    )
    for index in selected_indices
  )
####


def extract_spectral_ray_transfer_data(
  result: SpectralRayTransferResult,
  *,
  ray_id: str | None = None,
) -> SpectralRayTransferData:
  """Extract ray-transfer lines with their shared spectral axis."""

  if not isinstance(result, SpectralRayTransferResult):
    raise TypeError('result must be an exhaust_plume.api SpectralRayTransferResult')
  ####
  lines = extract_spectral_ray_transfer_lines(result, ray_id=ray_id)
  return SpectralRayTransferData(
    frame_id=result.envelope.frame.frame_id,
    wavelengths_m=tuple(result.payload.wavelengths_m),
    lines=lines,
  )
####


@dataclass(frozen=True, slots=True)
class PlumeFluxSectionGlyph:
  """Renderer-neutral scalar/vector glyph data for one flux section."""

  frame_id: str
  section_frame_id: str
  time_s: float
  section_translation_m: Vector3
  section_rotation_xyzw: tuple[float, float, float, float]
  normal: Vector3
  area_m2: float
  mass_flow_kgps: float
  momentum_flux_N: Vector3
  total_energy_flow_W: float
  species_mass_flows_kgps: tuple[tuple[str, float], ...]
  pressure_Pa: float
  ambient_pressure_Pa: float
  pressure_match_relative_residual: float
  cross_section_second_moment_m2: Matrix2

  def __post_init__(self) -> None:
    if not self.frame_id or not self.section_frame_id:
      raise ValueError('flux glyph frame IDs must not be empty')
    ####
    if len(self.section_rotation_xyzw) != 4:
      raise ValueError('flux glyph section rotation must have four components')
    ####
    if len(self.cross_section_second_moment_m2) != 2 or any(
      len(row) != 2 for row in self.cross_section_second_moment_m2
    ):
      raise ValueError('flux glyph second moment must be a 2x2 matrix')
    ####
    if len(self.species_mass_flows_kgps) != len({species_id for species_id, _ in self.species_mass_flows_kgps}):
      raise ValueError('flux glyph species IDs must be unique')
    ####
    object.__setattr__(self, 'section_translation_m', _as_vector3(self.section_translation_m))
    object.__setattr__(self, 'normal', _as_vector3(self.normal))
    object.__setattr__(self, 'momentum_flux_N', _as_vector3(self.momentum_flux_N))
    object.__setattr__(
      self,
      'section_rotation_xyzw',
      tuple(float(value) for value in self.section_rotation_xyzw),
    )
    object.__setattr__(
      self,
      'species_mass_flows_kgps',
      tuple((str(species_id), float(mass_flow)) for species_id, mass_flow in self.species_mass_flows_kgps),
    )
    object.__setattr__(
      self,
      'cross_section_second_moment_m2',
      tuple(tuple(float(value) for value in row) for row in self.cross_section_second_moment_m2),
    )
  ####
####


def extract_plume_flux_section_glyph(result: PlumeFluxSectionResult) -> PlumeFluxSectionGlyph:
  """Extract engineering flux data without turning it into visual geometry."""

  if not isinstance(result, PlumeFluxSectionResult):
    raise TypeError('result must be an exhaust_plume.api PlumeFluxSectionResult')
  ####
  _check_result_envelope(result.envelope)
  if not result.payload.applicability.supported:
    raise ValueError('an out-of-applicability flux-section result cannot be visualized')
  ####
  payload = result.payload
  return PlumeFluxSectionGlyph(
    frame_id=result.envelope.frame.frame_id,
    section_frame_id=payload.frame.frame_id,
    time_s=payload.time_s,
    section_translation_m=payload.section_pose.translation_m,
    section_rotation_xyzw=payload.section_pose.rotation_xyzw,
    normal=payload.normal,
    area_m2=payload.area_m2,
    mass_flow_kgps=payload.mass_flow_kgps,
    momentum_flux_N=payload.momentum_flux_N,
    total_energy_flow_W=payload.total_energy_flow_W,
    species_mass_flows_kgps=tuple(
      (species.species_id, species.mass_flow_kgps)
      for species in payload.species_mass_flows_kgps
    ),
    pressure_Pa=payload.pressure_Pa,
    ambient_pressure_Pa=payload.ambient_pressure_Pa,
    pressure_match_relative_residual=payload.pressure_match_relative_residual,
    cross_section_second_moment_m2=payload.cross_section_second_moment_m2,
  )
####


ProductVisualizationData: TypeAlias = (
  SectionedTubeLineData
  | SpectralRadiantIntensityGrid
  | SpectralRayTransferData
  | PlumeFluxSectionGlyph
)


@dataclass(frozen=True, slots=True)
class SectionedTubeViewProjection:
  """Selection-resolved geometry view without renderer-specific state."""

  data: SectionedTubeLineData
  station_index: int
  selected_channel: SectionedTubeChannelLine | None

  @property
  def station_center_m(self) -> Vector3:
    return self.data.geometry.centerline_m[self.station_index]
  ####

  @property
  def station_normal_1(self) -> Vector3:
    return self.data.geometry.normal_1[self.station_index]
  ####

  @property
  def station_normal_2(self) -> Vector3:
    return self.data.geometry.normal_2[self.station_index]
  ####

  @property
  def station_semi_axes_m(self) -> tuple[float, float]:
    return (
      self.data.geometry.semi_axis_1_m[self.station_index],
      self.data.geometry.semi_axis_2_m[self.station_index],
    )
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRadiantIntensityViewProjection:
  """Selection-resolved signature view with exact direction identity."""

  grid: SpectralRadiantIntensityGrid
  direction_index: int
  wavelength_index: int

  @property
  def selected_direction(self) -> Vector3:
    return self.grid.directions[self.direction_index]
  ####

  @property
  def selected_wavelength_m(self) -> float:
    return self.grid.wavelengths_m[self.wavelength_index]
  ####

  @property
  def selected_values_W_sr_m(self) -> tuple[ScalarValue, ...]:
    return self.grid.radiant_intensity_W_sr_m[self.direction_index]
  ####
####


@dataclass(frozen=True, slots=True)
class SpectralRayTransferViewProjection:
  """Selection-resolved ray view with source and transmittance kept apart."""

  data: SpectralRayTransferData
  ray_index: int
  wavelength_index: int

  @property
  def selected_line(self) -> SpectralRayTransferLine:
    return self.data.lines[self.ray_index]
  ####

  @property
  def selected_wavelength_m(self) -> float:
    return self.data.wavelengths_m[self.wavelength_index]
  ####
####


@dataclass(frozen=True, slots=True)
class PlumeFluxViewProjection:
  """Selection-resolved flux glyph view with optional species selection."""

  glyph: PlumeFluxSectionGlyph
  species_index: int | None

  @property
  def selected_species(self) -> tuple[str, float] | None:
    if self.species_index is None:
      return None
    ####
    return self.glyph.species_mass_flows_kgps[self.species_index]
  ####
####


def _validate_view_spec(
  result: ProductResult,
  spec: VisualizationSpec,
  product_prefix: str,
) -> None:
  spec.validate_for_result(result)
  if not spec.view_kind.startswith(f'{product_prefix}.'):
    raise ValueError(
      f'view spec {spec.view_kind!r} is not valid for the {product_prefix} product'
    )
  ####
####


def _selected_index(index: int | None, count: int, name: str, default: int = 0) -> int:
  selected = default if index is None else index
  if selected < 0 or selected >= count:
    raise IndexError(f'{name} out of range: {selected}')
  ####
  return selected
####


def project_sectioned_tube_view(
  result: SectionedTubeResult,
  spec: VisualizationSpec,
) -> SectionedTubeViewProjection:
  """Resolve a visual station/channel selection against a tube result."""

  _validate_view_spec(result, spec, 'visual')
  selection = spec.selection
  data = extract_sectioned_tube_line_data(result, channel_id=selection.channel_id)
  station_index = _selected_index(
    selection.station_index,
    len(data.geometry.arc_length_m),
    'station_index',
    default=len(data.geometry.arc_length_m) // 2,
  )
  selected_channel: SectionedTubeChannelLine | None = None
  if selection.channel_id is not None:
    matching = tuple(
      channel for channel in data.channels
      if selection.component_index is None or channel.component_index == selection.component_index
    )
    if not matching:
      raise IndexError(
        f'component_index out of range for channel {selection.channel_id!r}: '
        f'{selection.component_index}'
      )
    ####
    selected_channel = matching[0]
  elif selection.component_index is not None:
    raise ValueError('component_index selection requires channel_id for a visual view')
  ####
  return SectionedTubeViewProjection(
    data=data,
    station_index=station_index,
    selected_channel=selected_channel,
  )
####


def project_spectral_radiant_intensity_view(
  result: SpectralRadiantIntensityResult,
  spec: VisualizationSpec,
) -> SpectralRadiantIntensityViewProjection:
  """Resolve direction and wavelength selections for a signature result."""

  _validate_view_spec(result, spec, 'signature')
  grid = extract_spectral_radiant_intensity_grid(result)
  direction_index = _selected_index(
    spec.selection.direction_index,
    len(grid.directions),
    'direction_index',
  )
  wavelength_index = _selected_index(
    spec.selection.wavelength_index,
    len(grid.wavelengths_m),
    'wavelength_index',
    default=len(grid.wavelengths_m) // 2,
  )
  return SpectralRadiantIntensityViewProjection(
    grid=grid,
    direction_index=direction_index,
    wavelength_index=wavelength_index,
  )
####


def project_spectral_ray_transfer_view(
  result: SpectralRayTransferResult,
  spec: VisualizationSpec,
) -> SpectralRayTransferViewProjection:
  """Resolve ray and wavelength selections without inferring intersections."""

  _validate_view_spec(result, spec, 'ray-transfer')
  data = extract_spectral_ray_transfer_data(result)
  if spec.selection.ray_id is None:
    ray_index = 0
  else:
    matching = tuple(index for index, line in enumerate(data.lines) if line.ray_id == spec.selection.ray_id)
    if not matching:
      raise KeyError(f'unknown ray_id {spec.selection.ray_id!r}')
    ####
    ray_index = matching[0]
  ####
  ray_index = _selected_index(ray_index, len(data.lines), 'ray_index')
  wavelength_index = _selected_index(
    spec.selection.wavelength_index,
    len(data.wavelengths_m),
    'wavelength_index',
    default=len(data.wavelengths_m) // 2,
  )
  return SpectralRayTransferViewProjection(
    data=data,
    ray_index=ray_index,
    wavelength_index=wavelength_index,
  )
####


def project_plume_flux_view(
  result: PlumeFluxSectionResult,
  spec: VisualizationSpec,
) -> PlumeFluxViewProjection:
  """Resolve an optional species/component selection for a flux result."""

  _validate_view_spec(result, spec, 'flux')
  glyph = extract_plume_flux_section_glyph(result)
  species_index = spec.selection.component_index
  if species_index is not None:
    _selected_index(species_index, len(glyph.species_mass_flows_kgps), 'component_index')
  ####
  return PlumeFluxViewProjection(glyph=glyph, species_index=species_index)
####


def extract_product_visualization_data(result: ProductResult) -> ProductVisualizationData:
  """Dispatch one standard API result to its product-specific visualization data.

  The return type is a tagged Python union rather than a combined omnibus
  product.  Callers retain the independent semantics of visual geometry,
  spectral signature, ray transfer, and engineering flux.
  """

  if isinstance(result, SectionedTubeResult):
    return extract_sectioned_tube_line_data(result)
  ####
  if isinstance(result, SpectralRadiantIntensityResult):
    return extract_spectral_radiant_intensity_grid(result)
  ####
  if isinstance(result, SpectralRayTransferResult):
    return extract_spectral_ray_transfer_data(result)
  ####
  if isinstance(result, PlumeFluxSectionResult):
    return extract_plume_flux_section_glyph(result)
  ####
  raise TypeError('result must be one of the standard exhaust_plume.api product results')
####


__all__ = (
  'SectionedTubeChannelLine',
  'SectionedTubeGeometrySeries',
  'SectionedTubeLineData',
  'SectionedTubeRenderMesh',
  'SpectralRadiantIntensityGrid',
  'SpectralRadiantIntensityLine',
  'SpectralRayTransferData',
  'SpectralRayTransferLine',
  'PlumeFluxSectionGlyph',
  'PlumeFluxViewProjection',
  'ProductVisualizationData',
  'SectionedTubeViewProjection',
  'SpectralRadiantIntensityViewProjection',
  'SpectralRayTransferViewProjection',
  'build_sectioned_tube_render_mesh',
  'extract_sectioned_tube_channel_lines',
  'extract_sectioned_tube_geometry',
  'extract_sectioned_tube_line_data',
  'extract_spectral_radiant_intensity_grid',
  'extract_spectral_radiant_intensity_lines',
  'extract_spectral_ray_transfer_data',
  'extract_spectral_ray_transfer_lines',
  'extract_plume_flux_section_glyph',
  'extract_product_visualization_data',
  'project_plume_flux_view',
  'project_sectioned_tube_view',
  'project_spectral_radiant_intensity_view',
  'project_spectral_ray_transfer_view',
)
