# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, List, Mapping, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from numpy import array, cross, maximum, ones_like
from numpy.linalg import norm

from exhaust_plume.util.aabb import FrozenBounds
from exhaust_plume.util.color_util import ColorRGB
from exhaust_plume.util.mesh.triangular_mesh import TriangularMesh
from exhaust_plume.util.numpy_util import makeReadOnly
from exhaust_plume.util.plot_types import AxesSubplotType, PlotColorType
from exhaust_plume.util.plot_util import equalizeAxes3D

__all__ = (
    'plotTriangularMesh',
    'plotTriangularMeshes',
)
########################################

_M_snu_from_nsd = makeReadOnly(array([
    [0., 1., 0.],
    [1., 0., 0.],
    [0., 0., -1.],
]))

DEFAULT_COLOR = ColorRGB.fromHexColorCode('#DEDBEF')
DEFAULT_EDGE_COLOR = 'black'
VERTEX_NORMAL_COLOR = 'red'
DEFAULT_FACE_NORMAL_COLOR = 'blue'


def plotTriangularMesh(
        mesh: TriangularMesh,
        ax: Optional[AxesSubplotType] = None,
        face_alpha: Optional[float] = None,
        face_color: Optional[PlotColorType] = None,
        face_kwargs: Optional[Mapping[str, Any]] = None,
        show_vertex_normals: bool = True,
        vertex_normal_quiver_kwargs: Optional[Mapping[str, Any]] = None,
        show_face_normals: bool = True,
        face_normal_quiver_kwargs: Optional[Mapping[str, Any]] = None,
        view_margin: float = .2,
        set_axis_limits: bool = True,
        equalize_axes: bool = True,
        quiver_scale: float = 1.,
) -> Tuple[AxesSubplotType, Poly3DCollection, Optional[Any], Optional[Any]]:
  """ Plots a given mesh, given in Nose-Starboard-Down, as Starboard-Nose-Up (for easier interpretation and right-handedness) """
  if ax is None:
    ax = plt.gcf().add_subplot(111, projection='3d')
  ##
  if face_kwargs is None:
    face_kwargs = {}
  ##
  if vertex_normal_quiver_kwargs is None:
    vertex_normal_quiver_kwargs = {}
  ##
  if face_normal_quiver_kwargs is None:
    face_normal_quiver_kwargs = {}
  ##
  verts_snu = mesh.vertices @ _M_snu_from_nsd
  normals_snu = mesh.normals @ _M_snu_from_nsd

  face_kwargs = {
      'edgecolor': DEFAULT_EDGE_COLOR,
      'alpha': face_alpha,
      'facecolor': face_color,
      **face_kwargs,
  }
  poly_mesh = Poly3DCollection(verts_snu[mesh.faces], **face_kwargs)
  ax.add_collection3d(poly_mesh)

  if show_vertex_normals:
    vertex_normal_quiver_kwargs = {
        **{
            'length': .3 * quiver_scale,
            'normalize': True,
            'color': VERTEX_NORMAL_COLOR,
        },
        **vertex_normal_quiver_kwargs
    }
    h_vertex_quiver = ax.quiver(
        *(verts_snu[..., i] for i in range(3)), *(normals_snu[..., i] for i in range(3)),
        **vertex_normal_quiver_kwargs,
    )
  else:
    h_vertex_quiver = None
  ##
  if show_face_normals:
    versts_face_nsu = verts_snu[mesh.faces]
    face_centers = versts_face_nsu.mean(axis=1)
    face_normals = cross(versts_face_nsu[..., 1, :] - versts_face_nsu[..., 0, :], versts_face_nsu[..., 2, :] - versts_face_nsu[..., 0, :], axis=-1)
    face_normals /= norm(face_centers, axis=-1, keepdims=True)
    face_normal_quiver_kwargs = {
        **{
            'length': .3 * quiver_scale,
            'normalize': True,
            'color': DEFAULT_FACE_NORMAL_COLOR,
        },
        **face_normal_quiver_kwargs,
    }
    h_face_quiver = ax.quiver(
        *(face_centers[..., i] for i in range(3)), *(face_normals[..., i] for i in range(3)),
        **face_normal_quiver_kwargs,
    )
  else:
    h_face_quiver = None
  ##
  if set_axis_limits:
    k = 1 + view_margin
    bounds = FrozenBounds.fromPoints(verts_snu)
    extents = maximum(bounds.extents, ones_like(bounds.extents))
    ax.set_xlim([-k * extents[0], k * extents[0]])
    ax.set_ylim([-k * extents[1], k * extents[1]])
    ax.set_zlim([-k * extents[2], k * extents[2]])
  ##

  ax.set_xlabel('Right')
  ax.set_ylabel('Forward')
  ax.set_zlabel('Up')
  ax.grid()
  if equalize_axes:
    equalizeAxes3D(ax)
  ##
  out = (ax, poly_mesh, h_vertex_quiver, h_face_quiver)
  return out
##


def plotTriangularMeshes(
        meshes: Sequence[TriangularMesh],
        ax: Optional[AxesSubplotType] = None,
        face_colors: Optional[Sequence[PlotColorType]] = None,
        face_kwargs: Optional[Mapping[str, Any]] = None,
        view_margin: float = .2,
        set_axis_limits: bool = True,
        equalize_axes: bool = True,
) -> Tuple[AxesSubplotType, List[Tuple[Poly3DCollection, Optional[Any], Optional[Any]]]]:
  if not meshes:
    raise ValueError('No meshes to plot')
  ##
  if ax is None:
    ax = plt.gcf().add_subplot(111, projection='3d')
  ##
  bb_total = type(meshes[0].bounds).fromBounds(*[mesh.bounds for mesh in meshes]).asScaled(1 + view_margin)
  out_values = []
  if face_colors is None:
    face_colors = [DEFAULT_COLOR, ] * len(meshes)
  ##
  for mesh, face_color in zip(meshes, face_colors):
    plot_out = plotTriangularMesh(
        ax=ax, mesh=mesh,
        face_color=face_color,
        show_vertex_normals=False,
        show_face_normals=False,
        view_margin=view_margin,
        equalize_axes=False,
        set_axis_limits=False,
        quiver_scale=max(bb_total.extents),
        face_kwargs=face_kwargs,
    )
    out_values.append(plot_out[1:])
  ##
  if set_axis_limits:
    axis_lim_min = bb_total.min
    axis_lim_max = bb_total.max
    ax.set_xlim(axis_lim_min[1], axis_lim_max[1])  # starboard/right
    ax.set_ylim(axis_lim_min[0], axis_lim_max[0])  # nose/forward
    ax.set_zlim(-axis_lim_min[2], -axis_lim_max[2])  # bounds extents[2] is down, but plot is UP
  ##
  if equalize_axes:
    equalizeAxes3D(ax)
  ##
  out = (ax, out_values,)
  return out
##
