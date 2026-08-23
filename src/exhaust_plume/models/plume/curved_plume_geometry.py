"""Rotation-minimizing swept geometry for curved-plume centerlines."""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral
from typing import TypeAlias

import numpy as np
from numpy.typing import ArrayLike, NDArray

from exhaust_plume.models.plume._curved_plume_common import (
    FloatArray,
    _asReadOnlyArray,
    _asReadOnlyVector3,
)
from exhaust_plume.models.plume.curved_plume_closures import CurvedPlumeResult

IntArray: TypeAlias = NDArray[np.int64]


def _asReadOnlyPoints(name: str, value: ArrayLike, *, minimum_count: int) -> FloatArray:
  points = np.asarray(value, dtype=float)
  if points.ndim != 2 or points.shape[1] != 3 or len(points) < minimum_count:
    raise ValueError(
        f'Expected `{name}` to have shape (N, 3) with N >= {minimum_count}. '
        f'Got:{points.shape}'
    )
  ####
  if not np.isfinite(points).all():
    raise ValueError(f'Expected `{name}` to contain finite values.')
  ####
  return _asReadOnlyArray(name, points)
####


def _asReadOnlyFaces(value: ArrayLike, *, number_of_vertices: int) -> IntArray:
  faces = np.asarray(value, dtype=np.int64)
  if faces.ndim != 2 or faces.shape[1] != 3:
    raise ValueError(f'Expected faces to have shape (N, 3). Got:{faces.shape}')
  ####
  if faces.size and (int(np.min(faces)) < 0 or int(np.max(faces)) >= number_of_vertices):
    raise ValueError('Mesh faces contain an invalid vertex index.')
  ####
  out = np.array(faces, dtype=np.int64, copy=True)
  out.flags.writeable = False
  return out
####


def _normalizeRows(name: str, vectors: FloatArray) -> FloatArray:
  magnitudes = np.linalg.norm(vectors, axis=1)
  if np.any(~np.isfinite(magnitudes)) or np.any(magnitudes <= 0.):
    raise ValueError(f'Expected `{name}` rows to be finite and non-zero.')
  ####
  return _asReadOnlyArray(name, vectors / magnitudes[:, np.newaxis])
####


def _calculateCenterlineTangents(centerline_m: FloatArray) -> FloatArray:
  differences = np.empty_like(centerline_m)
  differences[0] = centerline_m[1] - centerline_m[0]
  differences[-1] = centerline_m[-1] - centerline_m[-2]
  if len(centerline_m) > 2:
    differences[1:-1] = centerline_m[2:] - centerline_m[:-2]
  ####
  return _normalizeRows('tangents', differences)
####


def _selectInitialNormal(tangent: FloatArray, requested_normal: ArrayLike | None) -> FloatArray:
  if requested_normal is None:
    basis = np.zeros(3)
    basis[int(np.argmin(np.abs(tangent)))] = 1.
    candidate = basis
  else:
    candidate = _asReadOnlyVector3('initial_normal', requested_normal)
  ####
  projected = candidate - float(candidate @ tangent) * tangent
  magnitude = float(np.linalg.norm(projected))
  if magnitude <= 1.e-12:
    raise ValueError('The initial normal must not be parallel to the first tangent.')
  ####
  return _asReadOnlyVector3('initial_normal', projected / magnitude)
####


def _parallelTransportVector(
    *,
    vector: FloatArray,
    previous_tangent: FloatArray,
    current_tangent: FloatArray,
) -> FloatArray:
  cross = np.cross(previous_tangent, current_tangent)
  sine = float(np.linalg.norm(cross))
  cosine = float(np.clip(previous_tangent @ current_tangent, -1., 1.))
  if sine <= 1.e-12:
    if cosine < 0.:
      raise ValueError('Adjacent centerline tangents are antiparallel; a rotation-minimizing frame is undefined.')
    ####
    return _asReadOnlyVector3('transported_vector', vector)
  ####
  axis = cross / sine
  transported = (
      cosine * vector
      + sine * np.cross(axis, vector)
      + (1. - cosine) * float(axis @ vector) * axis
  )
  return _asReadOnlyVector3('transported_vector', transported)
####


def calculateRotationMinimizingFrames(
    *,
    tangents: ArrayLike,
    initial_normal: ArrayLike | None = None,
) -> tuple[FloatArray, FloatArray]:
  """Return normal and binormal rows parallel-transported along tangents."""
  tangent_rows = _normalizeRows('tangents', _asReadOnlyPoints('tangents', tangents, minimum_count=2))
  normals = np.empty_like(tangent_rows)
  binormals = np.empty_like(tangent_rows)
  normals[0] = _selectInitialNormal(tangent_rows[0], initial_normal)
  binormals[0] = np.cross(tangent_rows[0], normals[0])
  for index in range(1, len(tangent_rows)):
    transported = _parallelTransportVector(
        vector=normals[index - 1],
        previous_tangent=tangent_rows[index - 1],
        current_tangent=tangent_rows[index],
    )
    projected = transported - float(transported @ tangent_rows[index]) * tangent_rows[index]
    magnitude = float(np.linalg.norm(projected))
    if magnitude <= 1.e-12:
      raise ValueError(f'Failed to construct a normal at centerline index {index}.')
    ####
    normals[index] = projected / magnitude
    binormals[index] = np.cross(tangent_rows[index], normals[index])
  ####
  return _asReadOnlyArray('normals', normals), _asReadOnlyArray('binormals', binormals)
####


@dataclass(frozen=True)
class SweptTubeMesh:
  """Triangular tube swept through rotation-minimizing centerline frames."""

  centerline_m: FloatArray
  radii_m: FloatArray
  vertices_m: FloatArray
  faces: IntArray
  tangents: FloatArray
  normals: FloatArray
  binormals: FloatArray
  number_of_ring_vertices: int
  cap_ends: bool

  def __post_init__(self) -> None:
    centerline = _asReadOnlyPoints('centerline_m', self.centerline_m, minimum_count=2)
    radii = np.asarray(self.radii_m, dtype=float)
    if radii.shape != (len(centerline),) or not np.isfinite(radii).all() or np.any(radii <= 0.):
      raise ValueError('Expected one finite positive radius per centerline point.')
    ####
    radii_read_only = _asReadOnlyArray('radii_m', radii)
    vertices = _asReadOnlyPoints('vertices_m', self.vertices_m, minimum_count=1)
    faces = _asReadOnlyFaces(self.faces, number_of_vertices=len(vertices))
    tangents = _asReadOnlyPoints('tangents', self.tangents, minimum_count=2)
    normals = _asReadOnlyPoints('normals', self.normals, minimum_count=2)
    binormals = _asReadOnlyPoints('binormals', self.binormals, minimum_count=2)
    if tangents.shape != centerline.shape or normals.shape != centerline.shape or binormals.shape != centerline.shape:
      raise ValueError('Centerline, tangent, normal, and binormal arrays must have identical shapes.')
    ####
    ring_size = self.number_of_ring_vertices
    if isinstance(ring_size, bool) or not isinstance(ring_size, Integral) or ring_size < 3:
      raise ValueError('Expected an integer with at least three vertices per ring.')
    ####
    if not isinstance(self.cap_ends, bool):
      raise ValueError(f'Expected `cap_ends` to be bool. Got:{self.cap_ends}')
    ####
    expected_vertices = len(centerline) * int(ring_size) + (2 if self.cap_ends else 0)
    if len(vertices) != expected_vertices:
      raise ValueError(
          f'Expected {expected_vertices} vertices for the declared rings and caps. '
          f'Got:{len(vertices)}'
      )
    ####
    object.__setattr__(self, 'centerline_m', centerline)
    object.__setattr__(self, 'radii_m', radii_read_only)
    object.__setattr__(self, 'vertices_m', vertices)
    object.__setattr__(self, 'faces', faces)
    object.__setattr__(self, 'tangents', tangents)
    object.__setattr__(self, 'normals', normals)
    object.__setattr__(self, 'binormals', binormals)
    object.__setattr__(self, 'number_of_ring_vertices', int(ring_size))
  ####

  @property
  def number_of_rings(self) -> int:
    return len(self.centerline_m)
  ####

  @property
  def ring_vertices_m(self) -> FloatArray:
    count = self.number_of_rings * self.number_of_ring_vertices
    rings = self.vertices_m[:count].reshape((self.number_of_rings, self.number_of_ring_vertices, 3))
    return _asReadOnlyArray('ring_vertices_m', rings)
  ####

  @property
  def min_m(self) -> FloatArray:
    return _asReadOnlyVector3('min_m', np.min(self.vertices_m, axis=0))
  ####

  @property
  def max_m(self) -> FloatArray:
    return _asReadOnlyVector3('max_m', np.max(self.vertices_m, axis=0))
  ####
####


def generateSweptTubeMesh(
    *,
    centerline_m: ArrayLike,
    radii_m: ArrayLike,
    tangents: ArrayLike | None = None,
    number_of_ring_vertices: int = 32,
    initial_normal: ArrayLike | None = None,
    cap_ends: bool = False,
) -> SweptTubeMesh:
  """Sweep circular rings along a centerline using a minimal-twist frame."""
  centerline = _asReadOnlyPoints('centerline_m', centerline_m, minimum_count=2)
  radii = np.asarray(radii_m, dtype=float)
  if radii.shape != (len(centerline),) or not np.isfinite(radii).all() or np.any(radii <= 0.):
    raise ValueError(
        'Expected `radii_m` to be finite, positive, and have one entry per centerline point. '
        f'Got:{radii.shape}'
    )
  ####
  if isinstance(number_of_ring_vertices, bool) or not isinstance(number_of_ring_vertices, Integral) or number_of_ring_vertices < 3:
    raise ValueError(f'Expected `number_of_ring_vertices` to be an integer at least 3. Got:{number_of_ring_vertices}')
  ####
  ring_size = int(number_of_ring_vertices)
  if tangents is None:
    tangent_rows = _calculateCenterlineTangents(centerline)
  else:
    tangent_rows = _normalizeRows('tangents', _asReadOnlyPoints('tangents', tangents, minimum_count=2))
    if tangent_rows.shape != centerline.shape:
      raise ValueError('Expected one tangent per centerline point.')
    ####
  ####
  normals, binormals = calculateRotationMinimizingFrames(
      tangents=tangent_rows,
      initial_normal=initial_normal,
  )
  angles = 2. * np.pi * np.arange(ring_size) / ring_size
  cosine = np.cos(angles)
  sine = np.sin(angles)
  ring_vertices = np.empty((len(centerline), ring_size, 3), dtype=float)
  for index in range(len(centerline)):
    ring_directions = (
        cosine[:, np.newaxis] * normals[index]
        + sine[:, np.newaxis] * binormals[index]
    )
    ring_vertices[index] = centerline[index] + radii[index] * ring_directions
  ####
  vertices = list(ring_vertices.reshape((-1, 3)))
  faces: list[tuple[int, int, int]] = []
  for ring_index in range(len(centerline) - 1):
    current_offset = ring_index * ring_size
    next_offset = (ring_index + 1) * ring_size
    for vertex_index in range(ring_size):
      next_vertex = (vertex_index + 1) % ring_size
      current = current_offset + vertex_index
      current_next = current_offset + next_vertex
      following = next_offset + vertex_index
      following_next = next_offset + next_vertex
      faces.extend(((current, current_next, following), (current_next, following_next, following)))
    ####
  ####
  if cap_ends:
    start_center = len(vertices)
    vertices.append(centerline[0])
    end_center = len(vertices)
    vertices.append(centerline[-1])
    end_offset = (len(centerline) - 1) * ring_size
    for vertex_index in range(ring_size):
      next_vertex = (vertex_index + 1) % ring_size
      faces.append((start_center, next_vertex, vertex_index))
      faces.append((end_center, end_offset + vertex_index, end_offset + next_vertex))
    ####
  ####
  return SweptTubeMesh(
      centerline_m=centerline,
      radii_m=radii,
      vertices_m=np.asarray(vertices, dtype=float),
      faces=np.asarray(faces, dtype=np.int64),
      tangents=tangent_rows,
      normals=normals,
      binormals=binormals,
      number_of_ring_vertices=ring_size,
      cap_ends=cap_ends,
  )
####


def generateCurvedPlumeMesh(
    *,
    result: CurvedPlumeResult,
    number_of_ring_vertices: int = 32,
    initial_normal: ArrayLike | None = None,
    cap_ends: bool = False,
) -> SweptTubeMesh:
  """Generate swept circular geometry from a calculated plume result."""
  centerline = np.vstack([station.position_m for station in result.stations])
  radii = np.asarray([station.radius_m for station in result.stations])
  tangents = np.vstack([station.tangent for station in result.stations])
  return generateSweptTubeMesh(
      centerline_m=centerline,
      radii_m=radii,
      tangents=tangents,
      number_of_ring_vertices=number_of_ring_vertices,
      initial_normal=initial_normal,
      cap_ends=cap_ends,
  )
####


__all__ = (
    'SweptTubeMesh',
    'calculateRotationMinimizingFrames',
    'generateCurvedPlumeMesh',
    'generateSweptTubeMesh',
)
