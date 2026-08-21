# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, fields
from pprint import pformat
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from numpy import all as aall, any as aany, arange, array, asarray, cross, cumsum, full_like, isclose, isin, isnan, logical_not, nan, ndarray, newaxis, ptp, tile, unique, vstack, where, zeros
from numpy.linalg import norm
from scipy.spatial.transform import Rotation

from exhaust_plume.loader.ignorable_config import getNonIgnorableConfig, hasNonIgnorableConfig
from exhaust_plume.log.extra_log_levels import CONFIG, TRACE_EXTRA, VERBOSE
from exhaust_plume.log.log import getLogger
from exhaust_plume.settings.settings_interface import AggregateFieldMetadata, CallerIds, FloatFieldMetadata, IntFieldMetadata, RepeatedFieldMetadata, SettingsInterface
from exhaust_plume.util.aabb import FrozenBounds
from exhaust_plume.util.aabb_interface import FrozenBoundsInterface
from exhaust_plume.util.cached_property import cached_property
from exhaust_plume.util.config_util import RotationLike, convertRotationLikeToRotation
from exhaust_plume.util.dataclass_util import dataclassIsClose, dataclassRepr
from exhaust_plume.util.math_util import applyTwistDeformation
from exhaust_plume.util.numpy_util import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT, makeReadOnly, unitize

__all__ = (
    'TriangularMesh',
)
########################################
log = getLogger(__name__)

_z3 = makeReadOnly(zeros((3,)))
ArrayLike = Union[ndarray, Sequence[float]]


@dataclass(frozen=True)
class TriangularMesh(SettingsInterface):
  vertices: ndarray  # (V,3)
  faces: ndarray  # (F,3)
  normals: ndarray  # (V,3)

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if isinstance(v, ndarray):
        v.flags.writeable = False
      ##
      shape = v.shape
      if len(shape) != 2 or shape[-1] != 3:
        raise ValueError(f'Expected `{f.name}` to have shape (...,3) got {shape}')
      ##
    ##
    num_verts = len(self.vertices)
    if len(self.vertices) != len(self.normals):
      raise ValueError(f'Number of vertices:{len(self.vertices)} must be equal to the number of normals:{len(self.normals)}')
    ##
    for face_idx, face in enumerate(self.faces):
      if any((idx < 0 or idx >= num_verts) for idx in face.ravel()):
        raise ValueError(f'faces[{face_idx}] = {face!r} contains invalid vertex indices. Num vertices:{len(self.vertices)}')
      ##
      vv = unique(face)
      if len(vv) <= 2:
        log.info(f'faces[{face_idx}] = {face!r} is degenerate')
      ##
    ##
  ##

  @property
  def num_vertices(self) -> int:
    return len(self.vertices)
  ##

  @property
  def num_faces(self) -> int:
    return len(self.faces)
  ##

  @cached_property
  def bounds(self) -> FrozenBoundsInterface:
    """ Gets bounding box for the mesh """
    return FrozenBounds.fromPoints(self.vertices)
  ##

  @cached_property
  def face_centers(self) -> ndarray:
    vf = self.vertices[self.faces]
    return vf.mean(axis=1)
  ##

  @cached_property
  def face_normals(self) -> ndarray:
    return self.calculateFaceNormals(vertices=self.vertices, faces=self.faces)
  ##

  @classmethod
  def getConfigMetadata(cls) -> AggregateFieldMetadata:
    return _tm_metadata
  ##

  def applyRotationAboutCenter(self, rotation: RotationLike) -> TriangularMesh:
    """ Applies rotation about center. """
    center = self.bounds.center
    rotation = convertRotationLikeToRotation(rotation)
    out = TriangularMesh(
        vertices=rotation.apply(self.vertices - center) + center,
        normals=rotation.apply(self.normals),
        faces=self.faces,
    )
    return out
  ##

  def applyRotation(self, rotation: RotationLike) -> TriangularMesh:
    """ Applies rotation about origin """
    rotation = convertRotationLikeToRotation(rotation)
    out = TriangularMesh(
        vertices=rotation.apply(self.vertices),
        normals=rotation.apply(self.normals),
        faces=self.faces,
    )
    return out
  ##

  def applyOffset(self, offset: ArrayLike) -> TriangularMesh:
    """ Translates the mesh. """
    out = TriangularMesh(
        vertices=self.vertices + asarray(offset, 'float'),
        normals=self.normals,
        faces=self.faces,
    )
    return out
  ##

  def applyRotationAndOffset(self, offset: Optional[ArrayLike] = None, rotation: Optional[RotationLike] = None) -> TriangularMesh:
    """ First apply rotation about origin and then offset. """
    if offset is None and rotation is None:
      return self
    ##
    if offset is None:
      offset = _z3
    ##
    offset = asarray(offset, 'float')
    if rotation is None:
      rotation = Rotation.identity()
    ##
    rotation = convertRotationLikeToRotation(rotation)
    out = TriangularMesh(
        vertices=rotation.apply(self.vertices) + offset[newaxis, ...],
        normals=rotation.apply(self.normals),
        faces=self.faces,
    )
    return out
  ##

  def applyScale(self, scale: Union[float, Sequence[float], ndarray], about_center: bool = True) -> TriangularMesh:
    """ Scales coordinates and adjusts normals.
    about_center: if true, then applies scale about the bounding box center, otherwise it just scales about the origin (simple multiply)
    """
    scale = asarray(scale, 'float')
    if scale.size <= 0:
      raise ValueError(f'Expected at least one scale value. Got:{scale}')
    ##
    if scale.size == 1:
      scale = tile(scale, (3,))
      normals = self.normals  # if same scaling in each dimension, then no change because of normalization
    else:
      normals = unitize(self.normals / scale[newaxis, ...])
    ##
    if about_center:
      center = self.bounds.center
      verts = (self.vertices - center) * scale + center
    else:
      verts = self.vertices * scale
    ##
    out = TriangularMesh(
        vertices=verts,
        faces=self.faces,
        normals=normals,
    )
    return out
  ##

  def applyTwist(self, frequency: float, twist_axis: ArrayLike, body_axis: Optional[ArrayLike] = None,
                 normalize_by_length: bool = True,
                 ) -> TriangularMesh:
    """ Applies Twist or Bend deformation
    If body_axis==twist_axis (or None), then a Twist deformation is applied
    If body_axis!=twist_axis, then a Bend deformation is applied
    If normalize_by_length is True, then frequency relates to the number of twists along that axis. Eg frequency=3, then 3 twists/bends
    """
    if frequency == 0.:
      return self
    ##
    center = self.bounds.center
    twist_axis = asarray(twist_axis, 'float')
    if body_axis is None:
      body_axis = twist_axis
    else:
      body_axis = asarray(body_axis, 'float')
    ##
    body_points = self.vertices - center
    body_length = ptp(body_points @ body_axis)
    if normalize_by_length:
      frequency /= body_length
    ##
    twisted_points, twisted_normals = applyTwistDeformation(
        points=body_points,
        twist_axis=twist_axis, body_axis=body_axis,
        normals=self.normals, frequency=frequency,
    )
    out = TriangularMesh(
        vertices=(twisted_points + center),
        normals=twisted_normals,
        faces=self.faces,
    )
    return out
  ##

  def removeAllFaces(self) -> TriangularMesh:
    out = TriangularMesh(
        vertices=self.vertices,
        faces=zeros((0, 3), 'int'),
        normals=self.normals,
    )
    return out
  ##

  def addFaces(self, faces: ndarray) -> TriangularMesh:
    """ Adds faces to copy of mesh """
    out = TriangularMesh(
        vertices=self.vertices,
        faces=asarray(vstack([self.faces, faces]), 'int'),
        normals=self.normals,
    )
    return out
  ##

  def flipFaces(self) -> TriangularMesh:
    """ Flips directions of all faces normals by re-ordering second and third face indices"""
    out = TriangularMesh(
        vertices=self.vertices,
        normals=self.normals,
        faces=self.faces[..., [0, 2, 1]],
    )
    return out
  ##

  def keepVerticesByLogical(self, vertices_to_keep: ndarray) -> TriangularMesh:
    """ Takes in a logical vector of vertices to keep. Removes any faces that have a rejected vertex. """
    keep_indices = frozenset(arange(len(vertices_to_keep))[vertices_to_keep])
    faces = vstack([face for face in self.faces if all((f in keep_indices) for f in face)])
    # Now re-index the face list
    for new_idx, old_idx in enumerate(sorted(keep_indices)):
      faces[faces == old_idx] = new_idx
    ##
    out = TriangularMesh(
        vertices=self.vertices[vertices_to_keep, ...],
        normals=self.normals[vertices_to_keep, ...],
        faces=faces,
    )
    return out
  ##

  def pruneUnusedVertices(self) -> TriangularMesh:
    """ Removes any vertices unused by the face indices """
    keep_vindices = sorted(set(self.faces.ravel()))
    if len(keep_vindices) == self.num_vertices:
      return self
    ##
    old2new = {old_idx: new_idx for new_idx, old_idx in enumerate(keep_vindices)}
    faces = vstack([[old2new[f] for f in face] for face in self.faces])
    prune_lgc = array([idx in keep_vindices for idx in range(self.num_vertices)], 'bool')
    out = TriangularMesh(
        vertices=self.vertices[prune_lgc, ...],
        normals=self.normals[prune_lgc, ...],
        faces=faces,
    )
    return out
  ##

  def removeDegenerateFaces(self) -> TriangularMesh:
    """ Removes any faces that have duplicated face indices """
    non_degenerate_faces = array([unique(face).size == 3 for face in self.faces])
    if all(non_degenerate_faces.ravel()):
      # no degenerate
      return self
    ##
    faces = self.faces[non_degenerate_faces]
    return TriangularMesh(
        vertices=self.vertices,
        faces=faces,
        normals=self.normals,
    )
  ##

  def consolidateVertices(self, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT,
                          remove_degenerate_faces: bool = True, average_normals: bool = True,
                          ) -> TriangularMesh:
    """ Consolidates vertices that are close within a tolerance
    Optionally removing degenerate faces
    and also re-calculating vertex normals as aveage of joined vertices
    """
    vindex2equivalents = {}
    initial_num_verts = self.num_vertices
    initial_num_faces = self.num_faces
    for vindex, vertex in enumerate(self.vertices[:-1, ...]):
      equiv_row = aall(isclose(vertex, self.vertices[vindex + 1:, ...], rtol=rtol, atol=atol, equal_nan=equal_nan), axis=-1)
      equivalents = where(equiv_row)[0] + vindex + 1
      if equivalents.size == 0:
        continue
      ##
      vindex2equivalents[vindex] = equivalents
    ##
    if not vindex2equivalents:
      return self.pruneUnusedVertices()
    ##
    faces = self.faces.copy()
    vnormals = self.normals.copy()
    for vindex, equivalents in vindex2equivalents.items():
      # Replace face indices
      replace_lgc = isin(faces, equivalents)
      faces[replace_lgc] = vindex
      # Get an average of the normals for the equivalent vertex
      equivalent_vnormals = vnormals[[vindex, ] + equivalents.tolist(), :]
      if average_normals:
        vnormal_equiv = equivalent_vnormals.mean(axis=0)
        vnormal_norm = norm(vnormal_equiv)
        if vnormal_norm != 0:
          vnormal_equiv /= vnormal_norm
        else:
          log.log(VERBOSE, f'Did not average vertex normals {vindex}:{equivalents} because average had zero norm. Normals:{equivalent_vnormals}')
        ##
      else:
        vnormal_equiv = equivalent_vnormals[0]
      ##
      vnormals[vindex] = vnormal_equiv
    ##
    remove_vindexes = unique([eindex for equivalents in vindex2equivalents.values() for eindex in equivalents])
    # Remove unused vertexes and normals, and non-unique faces
    keep_vindex_lgc = logical_not(isin(arange(len(self.vertices)), remove_vindexes))
    faces = unique(faces, axis=0)
    if remove_degenerate_faces:
      non_degenerate_faces = array([unique(face).size == 3 for face in faces])
      faces = faces[non_degenerate_faces]
    ##
    verts = self.vertices[keep_vindex_lgc]
    vnormals = vnormals[keep_vindex_lgc]
    # Re-index face indices to reflect new ordering
    old_indices = unique(faces.ravel())
    new_indices = arange(len(verts))
    for old_idx, new_idx in zip(old_indices, new_indices):
      if old_idx == new_idx:
        continue
      ##
      # This sequencing is okay because old indexes are going to be greater than the new ones
      faces[faces == old_idx] = new_idx
    ##
    out = TriangularMesh(
        vertices=verts,
        faces=faces,
        normals=vnormals,
    ).pruneUnusedVertices()
    final_num_verts = out.num_vertices
    final_num_faces = out.num_faces
    log.log(VERBOSE, f'Reduced mesh from V:{initial_num_verts}, F:{initial_num_faces} '
                     f'to V:{final_num_verts}, F:{final_num_faces};'
                     f' ΔV:{initial_num_verts - final_num_verts}, ΔF:{initial_num_faces - final_num_faces}')
    return out
  ##

  def _asConfig(self, caller_ids: CallerIds) -> Dict[str, Any]:
    out = {
        'vertices': self.vertices.tolist(),
        'faces': self.faces.tolist(),
    }
    if not all(isnan(self.normals).ravel()):
      out['normals'] = self.normals.tolist()
    ##
    return out
  ##

  def __repr__(self) -> str:
    return dataclassRepr(self)
  ##

  def __eq__(self, other: object) -> bool:
    if not isinstance(other, type(self)):
      return False
    ##
    if self is other:
      return True
    ##
    out = (
        (self.vertices.shape == other.vertices.shape) and
        all((self.vertices == other.vertices).ravel()) and
        (self.faces.shape == other.faces.shape) and
        all((self.faces == other.faces).ravel()) and
        (self.normals.shape == other.normals.shape) and
        (
            all((self.normals == other.normals).ravel()) or
            (
                all(isnan(self.normals)) and all(isnan(other.normals))
            )
        )
    )
    return out
  ##

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    """ Checks if is close to other class. Keyword arguments are passed along to numpy isclose. """
    return dataclassIsClose(self, other, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ##

  def __hash__(self) -> int:
    tup = (
        self.vertices.shape,
        self.faces.shape,
        self.vertices.data.tobytes(),
        self.normals.data.tobytes(),
        self.faces.data.tobytes(),
    )
    return hash(tup)
  ##

  @classmethod
  def fromConfig(cls, config: Mapping[str, Any], debug_config_prefix: str = '') -> TriangularMesh:
    if not config:
      raise ValueError(f'{debug_config_prefix}: config must be a dictionary of values. Got:{config}')
    ##
    config = {**config}
    # Shape checking for null meshes
    verts = asarray(config.pop('vertices'), 'float')
    if verts.size == 0:
      verts = verts.reshape((0, 3))
    ##
    if 'normals' in config:
      normals = asarray(config.pop('normals'), 'float')
      if normals.size == 0:
        normals = normals.reshape((0, 3))
      ##
    else:
      normals = full_like(verts, nan)
    ##
    faces = asarray(config.pop('faces'), 'int')
    if faces.size == 0:
      faces = faces.reshape((0, 3))
    ##
    out = TriangularMesh(
        vertices=verts,
        normals=normals,
        faces=faces,
    )
    if hasNonIgnorableConfig(config):
      log.info(f'{debug_config_prefix}: Unused Parameters in {cls.__name__} config: {getNonIgnorableConfig(config)}', extra={})
    ##
    log.log(CONFIG, f'{debug_config_prefix}: loaded {pformat(out)}', extra={})
    if log.isEnabledFor(TRACE_EXTRA):
      log.log(TRACE_EXTRA, f'{debug_config_prefix}: Loaded config:\n{pformat(out.asConfig(tuple()))}')
    ##
    return out
  ##

  @classmethod
  def combineMeshes(cls, *meshes: TriangularMesh) -> TriangularMesh:
    if len(meshes) == 0:
      return cls.generateNullMesh()
    elif len(meshes) == 1:
      return meshes[0]
    ##
    faces_offsets = cumsum([0, *(mesh.num_vertices for mesh in meshes[:-1])])
    out = TriangularMesh(
        vertices=vstack([mesh.vertices for mesh in meshes]),
        normals=vstack([mesh.normals for mesh in meshes]),
        faces=vstack([mesh.faces + offset for offset, mesh in zip(faces_offsets, meshes)]),
    )
    return out
  ##

  @classmethod
  def generateNullMesh(cls) -> TriangularMesh:
    out = TriangularMesh(
        vertices=zeros((0, 3)),
        normals=zeros((0, 3)),
        faces=zeros((0, 3), 'int'),
    )
    return out
  ##

  @classmethod
  def calculateFaceNormals(cls, vertices: ndarray, faces: ndarray) -> ndarray:
    vf = vertices[faces]
    return cross(vf[:, 1, ...] - vf[:, 0, ...], vf[:, 2, ...] - vf[:, 0, ...], axis=-1)
  ##

  @classmethod
  def calculateAverageVertexNormalsFromFaces(cls, vertices: ndarray, faces: ndarray) -> ndarray:
    face_normals = cls.calculateFaceNormals(vertices=vertices, faces=faces)
    # Now average the face normals for all faces each vertex is part of
    avg_v_fn = unitize(vstack([face_normals[aany(faces == i, axis=-1)].mean(axis=0) for i in range(len(vertices))]))
    return avg_v_fn
  ##
##


_face_index = IntFieldMetadata(
    label='Vertex Index',
    description=None,
    optional=False,
    default=None,
    min_value=0,
    max_value=None,
)

_point_coordinate = FloatFieldMetadata.createFinite(
    label='Coordinate',
    description=None,
    optional=False,
    default=None,
    units=None,
)

_point_xyz_tuple_metadata = RepeatedFieldMetadata.createFixedRepeat(
    label='Array XYZ',
    description='3D point in generic XYZ',
    optional=False,
    count=3,
    value=_point_coordinate,
)

_face_indices_tuple_metadata = RepeatedFieldMetadata.createFixedRepeat(
    label='Face Indices',
    description='List of 3 vertex indices that indicate a single triangular face.',
    optional=False,
    count=3,
    value=_face_index,
)

_tm_metadata = AggregateFieldMetadata(
    label='Triangular Mesh',
    description=None,
    optional=False,
    fields={
        'vertices': RepeatedFieldMetadata.createZeroOrMoreRepeat(
            label='Vertices',
            description='All vertices in the mesh',
            optional=False,
            repeat_label='Number of Vertices',
            repeat_description=None,
            value=_point_xyz_tuple_metadata.replace(
                label='Vertex',
            ),
        ),
        'faces': RepeatedFieldMetadata.createZeroOrMoreRepeat(
            label='Faces',
            description='All faces in the mesh',
            optional=False,
            repeat_label='Number of Faces',
            repeat_description=None,
            value=_face_indices_tuple_metadata.replace(
                label='Face Indices',
            ),
        ),
        'normals': RepeatedFieldMetadata.createZeroOrMoreRepeat(
            label='Normals',
            description='All vertex normals in the mesh. If Unknown then supply all nan',
            optional=True,
            repeat_label='Number of Faces',
            repeat_description=None,
            value=_point_xyz_tuple_metadata.replace(
                label='Vertex Normal',
                # TODO update float field to allow for nans
            ),
        ),
    }
)
