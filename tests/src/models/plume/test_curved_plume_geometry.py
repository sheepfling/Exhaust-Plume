from __future__ import annotations

from math import pi

import numpy as np
from numpy.testing import assert_allclose
from numpy.typing import NDArray

from exhaust_plume import (
    AmbientState,
    ConstantDensityMixtureThermodynamics,
    ConstantEntrainment,
    CurvedPlumeOptions,
    CurvedPlumeSource,
    SweptTubeMesh,
    UniformAmbientField,
    calculateRotationMinimizingFrames,
    generateCurvedPlumeMesh,
    generateSweptTubeMesh,
    solveCurvedPlume,
)


def _rotation_matrix() -> NDArray[np.float64]:
  axis = np.asarray([1., -2., 3.])
  axis /= np.linalg.norm(axis)
  angle = .73
  cross = np.asarray([
      [0., -axis[2], axis[1]],
      [axis[2], 0., -axis[0]],
      [-axis[1], axis[0], 0.],
  ])
  return (
      np.cos(angle) * np.eye(3)
      + (1. - np.cos(angle)) * np.outer(axis, axis)
      + np.sin(angle) * cross
  )
####


def test_straight_swept_tube_has_expected_topology_and_ring_geometry() -> None:
  number_of_rings = 5
  ring_size = 16
  centerline = np.column_stack((
      np.zeros(number_of_rings),
      np.zeros(number_of_rings),
      np.linspace(0., 4., number_of_rings),
  ))
  radii = np.linspace(.2, .5, number_of_rings)
  mesh: SweptTubeMesh = generateSweptTubeMesh(
      centerline_m=centerline,
      radii_m=radii,
      number_of_ring_vertices=ring_size,
      initial_normal=np.asarray([1., 0., 0.]),
      cap_ends=True,
  )
  assert mesh.vertices_m.shape == (number_of_rings * ring_size + 2, 3)
  assert mesh.faces.shape == (2 * (number_of_rings - 1) * ring_size + 2 * ring_size, 3)
  assert mesh.number_of_rings == number_of_rings
  assert_allclose(mesh.centerline_m, centerline, atol=0.)
  assert_allclose(mesh.radii_m, radii, atol=0.)
  assert_allclose(
      mesh.ring_vertices_m,
      mesh.vertices_m[:number_of_rings * ring_size].reshape((number_of_rings, ring_size, 3)),
      atol=0.,
  )
  assert mesh.number_of_ring_vertices == ring_size
  assert mesh.cap_ends
  assert not mesh.vertices_m.flags.writeable
  assert not mesh.faces.flags.writeable
  assert int(mesh.faces.min()) == 0
  assert int(mesh.faces.max()) < len(mesh.vertices_m)

  ring_vertices = mesh.vertices_m[:number_of_rings * ring_size].reshape((number_of_rings, ring_size, 3))
  offsets = ring_vertices - centerline[:, np.newaxis, :]
  assert_allclose(
      np.linalg.norm(offsets, axis=2),
      np.broadcast_to(radii[:, np.newaxis], (number_of_rings, ring_size)),
      rtol=2.e-14,
      atol=2.e-14,
  )
  assert_allclose(np.einsum('rij,ri->rj', offsets.transpose(0, 2, 1), mesh.tangents), 0., atol=1.e-14)
  assert_allclose(mesh.tangents, np.asarray([[0., 0., 1.]] * number_of_rings), atol=0.)
  assert_allclose(mesh.normals, np.asarray([[1., 0., 0.]] * number_of_rings), atol=0.)
  assert_allclose(mesh.binormals, np.asarray([[0., 1., 0.]] * number_of_rings), atol=0.)
  assert_allclose(mesh.vertices_m[-2], centerline[0], atol=0.)
  assert_allclose(mesh.vertices_m[-1], centerline[-1], atol=0.)
####


def test_rotation_minimizing_frame_remains_continuous_on_planar_quarter_circle() -> None:
  radius = 3.
  angles = np.linspace(0., .5 * pi, 101)
  centerline = np.column_stack((
      radius * np.sin(angles),
      np.zeros_like(angles),
      radius * (1. - np.cos(angles)),
  ))
  tangents = np.column_stack((
      np.cos(angles),
      np.zeros_like(angles),
      np.sin(angles),
  ))
  normals, binormals = calculateRotationMinimizingFrames(
      tangents=tangents,
      initial_normal=np.asarray([0., 1., 0.]),
  )
  assert_allclose(normals, np.asarray([[0., 1., 0.]] * len(angles)), atol=2.e-14)
  expected_binormals = np.cross(tangents, normals)
  assert_allclose(binormals, expected_binormals, atol=2.e-14)
  assert_allclose(np.einsum('ij,ij->i', tangents, normals), 0., atol=2.e-14)
  assert_allclose(np.einsum('ij,ij->i', tangents, binormals), 0., atol=2.e-14)
  assert_allclose(np.einsum('ij,ij->i', normals, binormals), 0., atol=2.e-14)
  assert_allclose(np.linalg.norm(normals, axis=1), 1., atol=2.e-14)
  assert_allclose(np.linalg.norm(binormals, axis=1), 1., atol=2.e-14)
  assert np.all(np.einsum('ij,ij->i', normals[:-1], normals[1:]) > .999999999)

  mesh = generateSweptTubeMesh(
      centerline_m=centerline,
      radii_m=np.full(len(centerline), .2),
      tangents=tangents,
      number_of_ring_vertices=24,
      initial_normal=np.asarray([0., 1., 0.]),
  )
  assert_allclose(mesh.normals, normals, atol=2.e-14)
  assert_allclose(mesh.binormals, binormals, atol=2.e-14)
####


def test_swept_tube_is_rotation_invariant() -> None:
  centerline = np.asarray([
      [0., 0., 0.],
      [1., .2, .1],
      [1.8, .7, .4],
      [2.3, 1.5, 1.],
  ])
  tangents = np.asarray([
      [1., .2, .1],
      [.9, .35, .2],
      [.7, .6, .5],
      [.5, .8, .6],
  ])
  tangents /= np.linalg.norm(tangents, axis=1)[:, np.newaxis]
  radii = np.asarray([.1, .13, .17, .22])
  initial_normal = np.asarray([0., 0., 1.])
  rotation = _rotation_matrix()
  baseline = generateSweptTubeMesh(
      centerline_m=centerline,
      radii_m=radii,
      tangents=tangents,
      number_of_ring_vertices=20,
      initial_normal=initial_normal,
      cap_ends=True,
  )
  rotated = generateSweptTubeMesh(
      centerline_m=centerline @ rotation.T,
      radii_m=radii,
      tangents=tangents @ rotation.T,
      number_of_ring_vertices=20,
      initial_normal=rotation @ initial_normal,
      cap_ends=True,
  )
  assert_allclose(rotated.vertices_m, baseline.vertices_m @ rotation.T, rtol=3.e-13, atol=3.e-13)
  assert_allclose(rotated.tangents, baseline.tangents @ rotation.T, rtol=3.e-13, atol=3.e-13)
  assert_allclose(rotated.normals, baseline.normals @ rotation.T, rtol=3.e-13, atol=3.e-13)
  assert_allclose(rotated.binormals, baseline.binormals @ rotation.T, rtol=3.e-13, atol=3.e-13)
  assert_allclose(rotated.faces, baseline.faces, atol=0.)
####


def test_generate_curved_plume_mesh_uses_station_centerline_radius_and_tangent() -> None:
  pressure = 101325.
  density = 1.2
  result = solveCurvedPlume(
      source=CurvedPlumeSource(
          position_m=np.zeros(3),
          velocity_mps=np.asarray([25., 0., 0.]),
          mass_flow_kgps=1.5,
          temperature_K=500.,
          static_pressure_Pa=pressure,
      ),
      ambient_field=UniformAmbientField(AmbientState(
          velocity_mps=np.asarray([0., 0., -8.]),
          pressure_Pa=pressure,
          temperature_K=300.,
          density_kgpm3=density,
      )),
      entrainment_model=ConstantEntrainment(.2),
      thermodynamics=ConstantDensityMixtureThermodynamics(density),
      options=CurvedPlumeOptions(
          max_arc_length_m=3.,
          number_of_stations=31,
          relative_tolerance=1.e-10,
          absolute_tolerance=1.e-12,
          max_step_m=.02,
      ),
  )
  ring_size = 12
  mesh = generateCurvedPlumeMesh(
      result=result,
      number_of_ring_vertices=ring_size,
      initial_normal=np.asarray([0., 1., 0.]),
  )
  centerline = np.vstack([station.position_m for station in result.stations])
  radii = np.asarray([station.radius_m for station in result.stations])
  tangents = np.vstack([station.tangent for station in result.stations])
  ring_vertices = mesh.vertices_m.reshape((len(result.stations), ring_size, 3))
  offsets = ring_vertices - centerline[:, np.newaxis, :]
  assert_allclose(
      np.linalg.norm(offsets, axis=2),
      np.broadcast_to(radii[:, np.newaxis], (len(result.stations), ring_size)),
      rtol=2.e-13,
      atol=2.e-13,
  )
  assert_allclose(np.einsum('rij,ri->rj', offsets.transpose(0, 2, 1), tangents), 0., atol=2.e-13)
  assert_allclose(mesh.tangents, tangents, rtol=2.e-14, atol=2.e-14)
####
