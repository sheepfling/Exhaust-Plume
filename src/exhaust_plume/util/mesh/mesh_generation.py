# -*- coding: utf-8 -*-
from __future__ import annotations

from itertools import product
from typing import List, Sequence, Tuple, Union

from numpy import (abs, arange, arcsin, array, asarray, column_stack, concatenate, cos, cross, eye, full_like, isfinite, linspace, meshgrid, nan, ndarray, newaxis, ones, pi, repeat, sign, sin, tile, vstack, zeros, zeros_like)
from numpy.linalg import matrix_power, norm
from scipy.spatial.transform import Rotation

from exhaust_plume.log.log import getLogger
from exhaust_plume.util.math_util import calculateAxisRotationMatrix, null_space
from exhaust_plume.util.mesh.triangular_mesh import TriangularMesh
from exhaust_plume.util.misc import getVectorRotation
from exhaust_plume.util.numpy_util import makeReadOnly, unitize

__all__ = (
    'generateBoxMesh',
    'generateEllipticalConeMesh',
    'generateEllipsoidMesh',
    'generateEllipticalFrustumMesh',
    'generateDiskMesh',
    'generateTriangleMesh',
    'generateTorusMesh',
    'generateTriangleStripMesh',
    'generateRegularPolygonMesh',
    'generateRhombicPyramidMesh',
    'generatePolygonalPrismMesh',
    'generateSheet',
    'generateDenseBoxMesh',
    'generateRevolvedMesh',
)
########################################
log = getLogger(__name__)

NOSE, STARBOARD, DOWN = makeReadOnly(eye(3))
ArrayLike = Union[Sequence[float], ndarray]
PI_2 = pi / 2.

_box_vertices = makeReadOnly(array([
    [-1., +1., +1.],
    [-1., -1., +1.],
    [+1., -1., +1.],
    [+1., +1., +1.],
    [-1., +1., -1.],
    [-1., -1., -1.],
    [+1., -1., -1.],
    [+1., +1., -1.],
]))
_box_vert_normals = makeReadOnly(_box_vertices / norm(_box_vertices, axis=-1, keepdims=True))

_box_faces = makeReadOnly(array([
    [3, 2, 6],
    [3, 6, 7],
    [3, 7, 4],
    [3, 4, 0],
    [0, 2, 3],
    [0, 1, 2],
    [4, 1, 0],
    [4, 5, 1],
    [2, 1, 5],
    [6, 2, 5],
    [7, 6, 5],
    [7, 5, 4],
], 'int'))


def _checkExtents(extents: ndarray, expected_num: int) -> ndarray:
  if extents.size == 1:
    extents = tile(extents, (expected_num,))
  ##
  if extents.shape != (expected_num,) or not all(isfinite(extents)):
    raise ValueError(f'Expected value to be scalar or shape ({expected_num},) and all finite. Got:{extents}')
  ##
  return extents
##


def generateBoxMesh(extents: ArrayLike) -> TriangularMesh:
  """ Generates a minimal box mesh using 8 vertices. """
  extents = _checkExtents(asarray(extents, 'float'), 3)
  out = TriangularMesh(
      vertices=_box_vertices * extents[newaxis, ...],
      faces=_box_faces,
      normals=_box_vert_normals,
  )
  return out
##


def generateSheet(extents: ArrayLike, num_axis_points: Union[int, Sequence[int], ndarray]) -> TriangularMesh:
  """ Generates sheet in XY(01) plane facing DOWN(+2). """
  extents = _checkExtents(asarray(extents, 'float'), 2)
  num_axis_points = _checkExtents(asarray(num_axis_points, 'int'), 2)
  faces: List[Tuple[int, int, int]] = []
  if num_axis_points.size == 1:
    num_x = int(num_axis_points)
    num_y = num_x
  else:
    num_x = num_axis_points[0]
    num_y = num_axis_points[1]
  ##
  for idx_x, idx_y in product(range(num_x - 1), range(num_y - 1)):
    index0 = idx_x + idx_y * num_x
    index1 = index0 + 1
    index2 = index0 + num_x
    index3 = index1 + num_x
    faces.extend((
        (index0, index1, index3),
        (index0, index3, index2),
    ))
  ##
  xx, yy = meshgrid(linspace(-1., 1., num_x), linspace(-1., 1., num_y))
  num_points = num_x * num_y
  out = TriangularMesh(
      vertices=column_stack([
          xx.ravel() * extents[0],
          yy.ravel() * extents[1],
          zeros((num_points,)),
      ]),
      faces=asarray(vstack(faces), 'int'),
      normals=tile(DOWN, (num_points, 1)),
  )
  return out
##


def generateDenseBoxMesh(extents: ArrayLike, num_axis_points: Union[int, Sequence[int], ndarray]) -> TriangularMesh:
  extents = _checkExtents(asarray(extents, 'float'), 3)
  num_axis_points = _checkExtents(asarray(num_axis_points, 'int'), 3)
  roll180 = Rotation.from_rotvec(pi * NOSE)
  rots = [Rotation.identity(), Rotation.from_rotvec(PI_2 * NOSE), Rotation.from_rotvec(PI_2 * STARBOARD), ]
  meshes = []
  for idx, (rot, other_idxs) in enumerate(zip(rots, [[0, 1], [0, 2], [2, 1]])):
    offset = zeros((3,))
    opp_idx = 2 - idx
    offset[opp_idx] = extents[opp_idx]
    mesh0 = generateSheet(extents=extents[other_idxs], num_axis_points=num_axis_points[other_idxs])
    meshes.append(mesh0.applyRotationAndOffset(rotation=rot, offset=offset))
    meshes.append(mesh0.applyRotationAndOffset(rotation=rot * roll180, offset=-offset))
  ##
  mesh = TriangularMesh.combineMeshes(*meshes).consolidateVertices()

  # Box face-normals should all be in the same direction as face-centers (positive dot)
  should_reorders = (mesh.face_normals * mesh.face_centers).sum(axis=-1) <= 0.
  rev_idx = [0, 2, 1]
  faces = vstack([
      face[rev_idx] if should_reorder else face for
      face, should_reorder in zip(mesh.faces, should_reorders)
  ])

  # Fix any poitns to be on exact grid
  normals = zeros_like(mesh.normals)
  verts = mesh.vertices
  extent_threshold = extents * (num_axis_points - 1) / num_axis_points
  for idx in range(3):
    normals[verts[..., idx] > extent_threshold[idx], idx] = 1.
    normals[verts[..., idx] < -extent_threshold[idx], idx] = -1.
  ##
  mesh = TriangularMesh(
      vertices=verts,
      normals=unitize(normals),
      faces=faces,
  )
  return mesh
##


def generateDiskMesh(extents: ArrayLike, num_points: int) -> TriangularMesh:
  """ Generates an Elliptical Disk fan Facing DOWN(+2). """
  extents = _checkExtents(asarray(extents, 'float'), 2)
  num_points = int(num_points)
  if num_points < 3:
    raise ValueError(f'`num_points` must be greater than or equal to 3. Got:{num_points}')
  ##
  th = linspace(-pi, pi, num_points + 1)[:-1]
  hub_index = num_points
  faces: List[Tuple[int, int, int]] = []
  for spoke_index in range(num_points):
    spoke_index %= num_points
    next_index = (spoke_index + 1) % num_points
    faces.append((spoke_index, next_index, hub_index,))
  ##
  circle_verts_nsd = vstack([
      column_stack([
          cos(th),
          sin(th),
          zeros((num_points,))
      ]),
      zeros((3,)),
  ])
  verts_nsd = circle_verts_nsd * array([*extents[:2], 0.])
  normals_nsd = column_stack([
      zeros((num_points + 1, 2)),
      ones((num_points + 1,)),
  ])
  out = TriangularMesh(
      vertices=verts_nsd,
      normals=normals_nsd,
      faces=vstack(faces),
  )
  return out
##


def generateRegularPolygonMesh(radius: float, num_points: int) -> TriangularMesh:
  """ Generates a regular polygon with radius facing DOWN(+2) """
  return generateDiskMesh(
      extents=array([radius, radius], 'float'), num_points=num_points,
  )
##


def generateEllipsoidMesh(extents: Union[ArrayLike, float], num_latitude_lines: int,
                          num_longitude_lines: int, equal_area: bool = False, ) -> TriangularMesh:
  """
  Number of latitude lines (not including poles), min 1
  Number of longitude lines, min 3
  """
  extents = _checkExtents(asarray(extents, 'float'), 3)
  num_longitude_lines = int(num_longitude_lines)
  if num_longitude_lines < 3:
    raise ValueError(f'Expected `num_longitude_lines` to be greater than or equal to 3. Got:{num_longitude_lines}')
  ##
  num_latitude_lines = int(num_latitude_lines)
  if num_latitude_lines < 1:
    raise ValueError(f'Expected `num_latitude_lines` to be greater than or equal to 1. Got:{num_latitude_lines}')
  ##
  # Start at south-pole and work upwards
  num_vertices = 2 + num_latitude_lines * num_longitude_lines

  def getVertexIndex(lat_index: int, lon_index: int) -> int:
    # Index of point = 1 + (latitude_index * num_longitudes + longitude_index)
    return 1 + (lat_index * num_longitude_lines) + lon_index
  ##
  # Create pole fans/caps
  south_pole_index = 0
  south_latitude_index = 0
  north_pole_index = num_vertices - 1
  north_latitude_index = num_latitude_lines - 1
  south_faces = []
  north_faces = []
  for longitude_index in range(num_longitude_lines):
    longitude_index %= num_longitude_lines
    longitude_next_index = (longitude_index + 1) % num_longitude_lines
    first_south_vert_index = getVertexIndex(lat_index=south_latitude_index, lon_index=longitude_next_index)
    second_south_vert_index = getVertexIndex(lat_index=south_latitude_index, lon_index=longitude_index)
    south_faces.append(
        (first_south_vert_index, south_pole_index, second_south_vert_index,)
    )
    first_north_vert_index = getVertexIndex(lat_index=north_latitude_index, lon_index=longitude_index)
    second_north_vert_index = getVertexIndex(lat_index=north_latitude_index, lon_index=longitude_next_index)
    north_faces.append(
        (first_north_vert_index, north_pole_index, second_north_vert_index,)
    )
  ##
  # Create triangular strips
  strip_faces: List[Tuple[int, int, int]] = []
  num_strips = max(0, num_latitude_lines - 1)
  for strip_index in range(num_strips):
    lower_latitude_index = strip_index
    upper_latitude_index = strip_index + 1
    for left_longitude_index in range(num_longitude_lines):
      left_longitude_index %= num_longitude_lines
      right_longitude_index = (left_longitude_index + 1) % num_longitude_lines
      upper_right_point_index = getVertexIndex(lat_index=upper_latitude_index, lon_index=right_longitude_index)
      lower_right_point_index = getVertexIndex(lat_index=lower_latitude_index, lon_index=right_longitude_index)
      upper_left_point_index = getVertexIndex(lat_index=upper_latitude_index, lon_index=left_longitude_index)
      lower_left_point_index = getVertexIndex(lat_index=lower_latitude_index, lon_index=left_longitude_index)
      strip_faces.extend((
          (upper_right_point_index, lower_left_point_index, upper_left_point_index),
          (upper_right_point_index, lower_right_point_index, lower_left_point_index),
      ))
    ##
  ##
  if equal_area:
    latitudes = arcsin(linspace(-1, 1, num_latitude_lines + 2))
  else:
    latitudes = linspace(-pi / 2, pi / 2, num_latitude_lines + 2)
  ##
  longitudes = linspace(-pi, pi, num_longitude_lines + 1)[:-1]
  verts_latitude = array([-pi / 2., *repeat(latitudes[1:-1], num_longitude_lines), +pi / 2.])
  verts_longitude = array([0., *tile(longitudes, num_latitude_lines), 0.])
  clat = cos(verts_latitude)
  slat = sin(verts_latitude)
  sphere_vertex_nsd = column_stack([
      clat * cos(verts_longitude),  # Nose
      clat * sin(verts_longitude),  # Starboard
      -slat,  # Down
  ])
  ellipsoid_vertex_nsd = sphere_vertex_nsd * extents[newaxis, ...]
  ellipsoid_normals_nsd = sphere_vertex_nsd / extents[newaxis, ...]
  ellipsoid_normals_nsd /= norm(ellipsoid_normals_nsd, axis=-1, keepdims=True)
  out = TriangularMesh(
      faces=asarray(vstack([
          south_faces,
          strip_faces,
          north_faces,
      ]), 'int'),
      vertices=ellipsoid_vertex_nsd,
      normals=ellipsoid_normals_nsd,
  )
  return out
##


def generateTriangleMesh(corners: ArrayLike) -> TriangularMesh:
  # Assumes a->b->c
  corners = asarray(corners, 'float')
  point_a = corners[0, ...]
  point_b = corners[1, ...]
  point_c = corners[2, ...]
  normal_dir = cross(point_b - point_a, point_c - point_a)
  normal_norm = norm(normal_dir)
  if normal_norm == 0.:
    log.warning(f'Triangle mesh generated is degenerate. No normal can be inferred from given corners:{corners}')
  else:
    normal_dir /= normal_norm
  ##
  out = TriangularMesh(
      vertices=vstack([point_a, point_b, point_c]),
      faces=array([[0, 1, 2]], 'int'),
      normals=tile(normal_dir, (3, 1)),
  )
  return out
##


def generateEllipticalConeMesh(height: float, base_extents: ArrayLike, num_points: int, with_base: bool = True, angle_offset: float = 0.) -> TriangularMesh:
  """ Cone Pointing UP(-2). with center of base at the origin. """
  base_extents = _checkExtents(asarray(base_extents, 'float'), 2)
  tip_index = num_points
  lateral_faces = []
  num_points = int(num_points)
  if num_points < 3:
    raise ValueError(f'Expected `num_points` to be greater than or equal to 3. Got:{num_points}')
  ##
  for spoke_index in range(num_points):
    spoke_index %= num_points
    next_index = (spoke_index + 1) % num_points
    lateral_faces.append((next_index, spoke_index, tip_index,))  # next, spoke, tip (because viewed from above)
  ##
  th = linspace(-pi, pi, num_points + 1)[:-1] + angle_offset
  lateral_verts_nsd = vstack([
      column_stack([
          cos(th),
          sin(th),
          zeros((num_points,))
      ]),
      array([0., 0., -height]),
  ])
  extents = array([*base_extents[:2], 1.])
  lateral_verts_nsd *= extents
  lateral_normals = column_stack([
      cos(th), sin(th), zeros_like(th),
  ]) / extents
  lateral_normals[..., :2] *= height
  lateral_normals[..., 2] = -1
  lateral_normals /= norm(lateral_normals, axis=-1, keepdims=True)
  tip_normal = array([0., 0., -1.])
  verts = [
      *lateral_verts_nsd,
  ]
  faces = [
      *lateral_faces,
  ]
  normals = [
      *lateral_normals,
      tip_normal
  ]
  if with_base:
    base_index = num_points + 1
    base_faces = []
    for spoke_index in range(num_points + 0):
      spoke_index %= num_points
      next_index = (spoke_index + 1) % num_points
      base_faces.append((spoke_index, next_index, base_index,))  # spoke, next because viewed from BELOW
    ##
    verts.append(zeros((3,)))
    normals.append(array([0., 0., 1.]))  # normal DOWN
    faces.extend(base_faces)
  ##
  out = TriangularMesh(
      vertices=vstack(verts),
      normals=vstack(normals),
      faces=asarray(vstack(faces), 'int'),
  )
  return out
##


def generateEllipticalFrustumMesh(height: float, top_extents: Union[float, ArrayLike], base_extents: Union[float, ArrayLike], num_points: int,
                                  with_top: bool = True, with_base: bool = True, angle_offset: float = 0.) -> TriangularMesh:
  """ Conic Frustum with Top side Pointing UP(-2). with center of base at the origin.
  top_extents: Should be a float or shape (2,)
  base_extents: Should be a float or shape (2,)
  """
  top_extents = _checkExtents(asarray(top_extents, 'float'), 2)
  base_extents = _checkExtents(asarray(base_extents, 'float'), 2)
  num_points = int(num_points)
  if num_points < 3:
    raise ValueError(f'Expected `num_points` to be greater than or equal to 3. Got:{num_points}')
  ##
  if all((top_extents == 0.).ravel()):
    return generateEllipticalConeMesh(
        height=height,
        base_extents=base_extents,
        with_base=with_base,
        angle_offset=angle_offset,
        num_points=num_points,
    )
  elif all((base_extents == 0.).ravel()):
    # Generate top as bottom and then flip the other way
    return generateEllipticalConeMesh(
        height=height,
        base_extents=top_extents,
        with_base=with_top,
        angle_offset=angle_offset,
        num_points=num_points,
    ).applyRotationAndOffset(offset=height * DOWN, rotation=Rotation.from_rotvec(pi * STARBOARD))
  ##
  bottom_lateral_faces = []
  top_lateral_faces = []
  for spoke_index in range(num_points):
    spoke_index %= num_points
    next_index = (spoke_index + 1) % num_points
    # next, spoke, tip (because viewed from above)
    bottom_lateral_faces.append((next_index, spoke_index, num_points + spoke_index))
    top_lateral_faces.append((num_points + spoke_index, num_points + next_index, next_index))
  ##
  base_th = linspace(-pi, pi, num_points + 1)[:-1] + angle_offset
  top_th = base_th + (base_th[1] - base_th[0]) / 2.
  thetas = concatenate([base_th, top_th])
  radial_verts_nsd = column_stack([
      cos(thetas),
      sin(thetas),
      zeros_like(thetas),
  ])
  lateral_normals = radial_verts_nsd.copy()
  lateral_verts_nsd = radial_verts_nsd.copy()
  # Now scale points by extents
  base_extents = array([*base_extents[:2], 1.])
  top_extents = array([*top_extents[:2], 1.])
  lateral_verts_nsd[:num_points, ...] *= base_extents
  lateral_verts_nsd[num_points:, ...] *= top_extents
  lateral_verts_nsd[num_points:, 2] = -height  # Add offset
  lateral_normals[:num_points, ...] /= base_extents
  lateral_normals[num_points:, ...] /= top_extents
  lateral_normals /= norm(lateral_normals, axis=-1, keepdims=True)
  ####
  # Now determine up or DOWN-ness for faces
  vert_rhos = norm(lateral_verts_nsd[..., :2], axis=-1)
  vert_opp_rhos = radial_verts_nsd.copy()
  vert_opp_rhos[:num_points, ...] *= top_extents
  vert_opp_rhos[num_points:, ...] *= base_extents
  vert_opp_rhos = norm(vert_opp_rhos[..., :2], axis=-1)
  delta_rho = vert_rhos - vert_opp_rhos
  lateral_normals[..., :2] *= height
  # if drho Positive, then up; Negative if DOWN (opposite for top vertices)
  downness = -sign(delta_rho) * ((arange(2 * num_points) < num_points) * 2. - 1)
  lateral_normals[..., 2] = downness * abs(delta_rho)
  lateral_normals /= norm(lateral_normals, axis=-1, keepdims=True)
  ####
  verts = [
      *lateral_verts_nsd,
  ]
  faces = [
      *bottom_lateral_faces,
      *top_lateral_faces,
  ]
  normals = [
      *lateral_normals,
  ]
  if with_base:
    base_index = len(verts)
    base_faces = []
    for spoke_index in range(num_points + 0):
      spoke_index %= num_points
      next_index = (spoke_index + 1) % num_points
      base_faces.append((spoke_index, next_index, base_index,))  # spoke, next because viewed from BELOW
    ##
    verts.append(zeros((3,)))
    normals.append(array([0., 0., 1.]))  # normal DOWN
    faces.extend(base_faces)
  ##
  if with_top:
    top_index = len(verts)
    top_ring_index_offset = num_points
    top_faces = []
    for spoke_index in range(num_points + 0):
      if spoke_index >= num_points:
        spoke_index %= num_points
      ##
      next_index = spoke_index + 1
      if next_index >= num_points:
        next_index %= num_points
      ##
      top_faces.append((spoke_index + top_ring_index_offset, top_index, next_index + top_ring_index_offset,))
    ##
    verts.append(array([0., 0., -height]))
    normals.append(array([0., 0., -1.]))  # normal up
    faces.extend(top_faces)
  ##
  out = TriangularMesh(
      vertices=vstack(verts),
      normals=vstack(normals),
      faces=asarray(vstack(faces), 'int'),
  )
  return out
##


def generatePlaneMesh(normal: ndarray, offset: float, points: ndarray) -> TriangularMesh:
  """ Generates a rectangular mesh that encompasses the points projected onto the given plane.
  If given only a single point, then the mesh will include the center (=normal*offset)
  """
  normal = unitize(normal)
  points = asarray(points, 'float')
  if len(points.shape) == 1:
    points = vstack([points, normal * offset])
  ##
  # Calculate nullspace of normal vector
  ns = null_space(normal.reshape((1, 3)))
  if cross(ns[0], ns[1]) @ normal < 0:
    # Ensure right-handed rotation
    ns[1] *= -1
  ##
  bfw = vstack([ns, normal]).T
  plane_points = points @ bfw
  plane_min = plane_points.min(axis=0)
  plane_max = plane_points.max(axis=0)
  #          ^ plane Nose(0)
  #          |
  # mx,mn +-----+ mx,mx
  #  [3]  |   _/| [0]
  #       | _/  |  ---> plane Starboard(1)
  #       |/    |
  # mn,mn +-----+ mn,mx
  #  [2]           [1]
  plane_corners = vstack([
      [plane_max[0], plane_max[1], offset],
      [plane_min[0], plane_max[1], offset],
      [plane_min[0], plane_min[1], offset],
      [plane_max[0], plane_min[1], offset],
  ])
  world_corners = (plane_corners @ bfw.T)
  out = TriangularMesh(
      vertices=world_corners,
      faces=vstack([
          [0, 1, 2],
          [0, 2, 3],
      ]),
      normals=vstack([
          normal, normal, normal, normal
      ])
  )
  return out
##


def generateTorusMesh(center: ndarray, axis: ndarray, ring_radius: float, tube_radius: float, num_ring_lines: int, num_tube_lines: int) -> TriangularMesh:
  """ Generates a Toroidal mesh with the hole pointing in the given axis direction. """
  center = asarray(center, 'float')
  axis = unitize(asarray(axis, 'float'))
  num_ring_lines = int(num_ring_lines)
  if num_ring_lines < 3:
    raise ValueError(f'`num_ring_lines` must be greater than or equal to 3. Got:{num_ring_lines}')
  ##
  num_tube_lines = int(num_tube_lines)
  if num_tube_lines < 3:
    raise ValueError(f'`num_tube_lines` must be greater than or equal to 3. Got:{num_tube_lines}')
  ##

  def getIndex(ring_index: int, tube_index: int) -> int:
    return (tube_index % num_tube_lines) + (ring_index % num_ring_lines) * num_tube_lines
  ##
  # [0]       [3]
  #   +-------+
  #   |\_     |
  #   |  \_   |
  #   |    \_ |
  #   |      \|
  #   +-------+
  # [1]       [2]
  # [0,1,2],[0,2,3]
  faces: List[Tuple[int, int, int]] = []
  for nr, nt in product(range(num_ring_lines), range(num_tube_lines)):
    index0 = getIndex(ring_index=nr, tube_index=nt)
    index1 = getIndex(ring_index=nr, tube_index=nt + 1)
    index2 = getIndex(ring_index=nr + 1, tube_index=nt + 1)
    index3 = getIndex(ring_index=nr + 1, tube_index=nt)
    faces.extend((
        (index0, index2, index1),
        (index0, index3, index2),
    ))
  ##
  tube_th = linspace(-pi, pi, num_tube_lines + 1)[:-1, newaxis]
  ct = cos(tube_th)
  st = sin(tube_th)
  tube0_vertices = (tube_radius * ct) * NOSE + (tube_radius * st + ring_radius) * STARBOARD
  # Ring default axis is X
  tube0_normals = (ct * NOSE) + (st * STARBOARD)
  ring_th = linspace(-pi, pi, num_ring_lines + 1)[:-1]
  R = calculateAxisRotationMatrix(axis=NOSE, angles=ring_th)
  body_vertices = vstack([tube0_vertices @ R[nr, ...] for nr in range(num_ring_lines)])
  body_normals = vstack([tube0_normals @ R[nr, ...] for nr in range(num_ring_lines)])
  axis_from_body = getVectorRotation(v_start=NOSE, v_end=axis)
  out = TriangularMesh(
      vertices=axis_from_body.apply(body_vertices) + center,
      faces=vstack(faces),
      normals=axis_from_body.apply(body_normals),
  )
  return out
##


def generatePolygonalPrismMesh(points_2D: ndarray, height: float,
                               with_top: bool = True, with_bottom: bool = True, with_lateral: bool = True,
                               ) -> TriangularMesh:
  """ Generates a polygonal prism from the given 2d points. The center of the prism will be at the origin with half height on either side.
  The prism polygon faces will point UP(-2) and DOWN(+2).
  with_top, with_bottom, and with_lateral control if the faces are supplied in the output.
  """
  bottom_mesh = generateTriangleStripMesh(points_2D=points_2D, cyclical=False).applyRotationAndOffset(
      offset=height / 2. * DOWN,
  )
  top_mesh = TriangularMesh(
      vertices=bottom_mesh.vertices + height * -DOWN,
      normals=-1 * bottom_mesh.normals,
      faces=bottom_mesh.faces[..., (0, 2, 1)],
  )
  lateral_faces: List[Tuple[int, int, int]] = []
  N = len(points_2D)
  for n in range(N):
    next_n = (n + 1) % N
    lateral_faces.extend((
        (n, next_n, n + N,),
        (next_n, next_n + N, n + N),
    ))
  ##
  out = TriangularMesh.combineMeshes(
      bottom_mesh if with_bottom else bottom_mesh.removeAllFaces(),
      top_mesh if with_top else top_mesh.removeAllFaces(),
  )
  if with_lateral:
    out = out.addFaces(asarray(lateral_faces, 'int'))
  ##
  return out
##


def generateTriangleStripMesh(points_2D: ndarray, cyclical: bool = False, flip_faces_to_point_down: bool = True) -> TriangularMesh:
  """ Creates strip of triangles assuming that each sequential group of three points is a face.
  If flip_faces_to_point_down is True, then the order is re-arranged so that the face normals all point DOWN(+2)

  Assumes points is shape (N,2)
  """
  N = len(points_2D)
  num_faces = N - 1
  if not cyclical:
    num_faces -= 1
  ##
  faces = asarray(vstack([
      [n, n + 1, n + 2] for n in range(num_faces)
  ]), 'int') % N
  verts = column_stack([points_2D, zeros((N,))])
  if flip_faces_to_point_down:
    face_normals = cross(verts[faces[..., 1], ...] - verts[faces[..., 0], ...], verts[faces[..., 2], ...] - verts[faces[..., 0], ...], axis=-1)
    should_reverses = (face_normals @ DOWN) < 0
    rev_idx = [0, 2, 1]
    faces = vstack([
        face[rev_idx] if should_reverse else face
        for face, should_reverse in zip(faces, should_reverses)
    ])
  ##
  out = TriangularMesh(
      vertices=verts,
      faces=faces,
      normals=tile(DOWN, (N, 1)),
  )
  return out
##


def generateRevolvedMesh(points: ndarray, axis: ndarray, num_rotations: int) -> TriangularMesh:
  """ Generates a quad mesh type rotated around the given axis

  Assumes points is shape (...,3) or (...,2) [will be padded with zeros.]
  """
  num_rotations = int(num_rotations)
  if num_rotations < 3:
    raise ValueError(f'Unable to rotate with only {num_rotations} rotations. Needs to be at least 3.')
  ##
  faces: List[Tuple[int, int, int]] = []
  num_points = len(points)
  # generate N strips connected in sequence

  def getIndex(strip_index: int, point_index: int) -> int:
    return (point_index % num_points) + (strip_index % num_rotations) * num_points
  ##
  for s, p in product(range(num_rotations), range(num_points)):
    i0 = getIndex(s, p)
    i1 = getIndex(s, p + 1)
    i2 = getIndex(s + 1, p)
    i3 = getIndex(s + 1, p + 1)
    faces.extend((
        (i0, i1, i2),
        (i1, i3, i2),
    ))
  ##

  M = Rotation.from_rotvec((2 * pi / num_rotations) * unitize(axis)).as_matrix()

  if points.shape[-1] == 2:
    points = concatenate([points, zeros(tuple(points.shape[:-1]) + (1,))], axis=-1)
  ##
  rotated_points = vstack([
      points @ matrix_power(M, s) for s in range(num_rotations)
  ])

  out = TriangularMesh(
      vertices=rotated_points,
      faces=asarray(faces, 'int'),
      normals=full_like(rotated_points, nan),  # TODO[improvement,feature] calculate normals
  )
  return out
##


def generateRhombicPyramidMesh(height: float, hortizontal_diagonal: float, vertical_diagonal: float) -> TriangularMesh:
  out = TriangularMesh(
      vertices=vstack([
          [height / 2., 0., 0.],
          [-height / 2., hortizontal_diagonal / 2., 0.],
          [-height / 2., 0., vertical_diagonal / 2.],
          [-height / 2., -hortizontal_diagonal / 2., 0.],
          [-height / 2., 0., -vertical_diagonal / 2.],
      ]),
      normals=vstack([
          NOSE,
          STARBOARD,
          DOWN,
          -STARBOARD,
          -DOWN,
      ]),
      faces=array([
          [0, 1, 2],
          [0, 2, 3],
          [0, 3, 4],
          [0, 4, 1],
          [1, 4, 3],
          [1, 3, 2],
      ], 'int'),
  )
  return out
##
