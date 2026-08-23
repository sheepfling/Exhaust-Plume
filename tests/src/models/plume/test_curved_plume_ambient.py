from __future__ import annotations

from math import pi

import numpy as np
from numpy.testing import assert_allclose

from exhaust_plume import (
    ActuatorDiskWakeField,
    AmbientState,
    CompositeVelocityField,
    ConstantDensityMixtureThermodynamics,
    ConstantEntrainment,
    CurvedPlumeOptions,
    CurvedPlumeSource,
    UniformAmbientField,
    UniformVelocityField,
    VelocityAugmentedAmbientField,
    solveCurvedPlume,
)


def test_composite_velocity_preserves_background_thermodynamics() -> None:
  background_state = AmbientState.fromIdealGas(
      velocity_mps=np.asarray([1., 2., 3.]),
      pressure_Pa=90000.,
      temperature_K=280.,
      specific_heat_JpkgK=1007.,
      gas_constant_JpkgK=287.2,
  )
  field = VelocityAugmentedAmbientField(
      background_field=UniformAmbientField(background_state),
      velocity_field=CompositeVelocityField((
          UniformVelocityField(np.asarray([4., 0., 0.])),
          UniformVelocityField(np.asarray([-1., 1., 0.])),
      )),
  )
  sampled = field.sample(np.asarray([10., -3., 7.]))
  assert_allclose(sampled.velocity_mps, [4., 3., 3.], rtol=0., atol=0.)
  assert sampled.pressure_Pa == background_state.pressure_Pa
  assert sampled.temperature_K == background_state.temperature_K
  assert sampled.density_kgpm3 == background_state.density_kgpm3
  assert sampled.specific_heat_JpkgK == background_state.specific_heat_JpkgK
  assert sampled.gas_constant_JpkgK == background_state.gas_constant_JpkgK
####


def test_actuator_disk_preserves_mean_axial_velocity_and_wake_contraction() -> None:
  radius = 4.
  density = 1.2
  thrust = 5000.
  development_length = 2. * radius
  wake = ActuatorDiskWakeField(
      rotor_center_m=np.zeros(3),
      wake_axis=np.asarray([0., 0., -1.]),
      rotor_radius_m=radius,
      thrust_N=thrust,
      ambient_density_kgpm3=density,
      wake_development_length_m=development_length,
      radial_profile_exponent=1.,
  )
  induced = np.sqrt(thrust / (2. * density * pi * radius ** 2))
  assert_allclose(wake.induced_velocity_at_disk_mps, induced, rtol=1.e-14)
  assert_allclose(wake.calculateMeanAxialVelocityMps(0.), induced, rtol=1.e-14)
  assert_allclose(wake.calculateWakeRadiusM(0.), radius, rtol=1.e-14)

  number_of_cells = 20000
  radial_step = radius / number_of_cells
  radial_midpoints = (np.arange(number_of_cells) + .5) * radial_step
  axial_velocities = np.asarray([
      wake.sampleVelocity(np.asarray([radial, 0., 0.])) @ wake.wake_axis
      for radial in radial_midpoints
  ])
  area_mean = 2. / radius ** 2 * np.sum(axial_velocities * radial_midpoints) * radial_step
  assert_allclose(area_mean, induced, rtol=3.e-9)

  downstream_distance = 20. * development_length
  mean_far = wake.calculateMeanAxialVelocityMps(downstream_distance)
  radius_far = wake.calculateWakeRadiusM(downstream_distance)
  assert_allclose(mean_far, 2. * induced, rtol=2.e-9)
  assert_allclose(radius_far, radius / np.sqrt(2.), rtol=2.e-9)
  assert_allclose(wake.sampleVelocity(np.asarray([0., 0., 1.])), 0., atol=0.)
  assert_allclose(
      wake.sampleVelocity(np.asarray([1.001 * radius_far, 0., -downstream_distance])),
      0.,
      atol=0.,
  )
####


def test_actuator_disk_swirl_conserves_prescribed_torque() -> None:
  radius = 3.5
  density = 1.18
  torque = 900.
  downstream_distance = 5.
  wake = ActuatorDiskWakeField(
      rotor_center_m=np.zeros(3),
      wake_axis=np.asarray([0., 0., 1.]),
      rotor_radius_m=radius,
      thrust_N=4200.,
      ambient_density_kgpm3=density,
      torque_Nm=torque,
      wake_development_length_m=radius,
      radial_profile_exponent=1.5,
      swirl_taper_exponent=.75,
  )
  wake_radius = wake.calculateWakeRadiusM(downstream_distance)
  number_of_cells = 30000
  radial_step = wake_radius / number_of_cells
  radial_midpoints = (np.arange(number_of_cells) + .5) * radial_step
  angular_momentum_flux = 0.
  for radial in radial_midpoints:
    velocity = wake.sampleVelocity(np.asarray([radial, 0., downstream_distance]))
    axial_velocity = velocity[2]
    tangential_velocity = velocity[1]
    angular_momentum_flux += (
        2. * pi * density * axial_velocity * tangential_velocity * radial ** 2 * radial_step
    )
  ####
  assert_allclose(angular_momentum_flux, torque, rtol=2.e-8)
####


def test_actuator_disk_velocity_is_rotation_invariant() -> None:
  angle = .61
  axis = np.asarray([1., -2., 3.])
  axis /= np.linalg.norm(axis)
  cross = np.asarray([
      [0., -axis[2], axis[1]],
      [axis[2], 0., -axis[0]],
      [-axis[1], axis[0], 0.],
  ])
  rotation = np.cos(angle) * np.eye(3) + (1. - np.cos(angle)) * np.outer(axis, axis) + np.sin(angle) * cross
  center = np.asarray([1., 2., -1.])
  wake_axis = np.asarray([0., 0., -1.])
  point = center + np.asarray([.8, -.4, -3.])
  baseline = ActuatorDiskWakeField(
      rotor_center_m=center,
      wake_axis=wake_axis,
      rotor_radius_m=4.,
      thrust_N=5000.,
      ambient_density_kgpm3=1.2,
      torque_Nm=-700.,
      radial_profile_exponent=1.2,
      swirl_taper_exponent=.8,
  )
  rotated = ActuatorDiskWakeField(
      rotor_center_m=rotation @ center,
      wake_axis=rotation @ wake_axis,
      rotor_radius_m=baseline.rotor_radius_m,
      thrust_N=baseline.thrust_N,
      ambient_density_kgpm3=baseline.ambient_density_kgpm3,
      torque_Nm=baseline.torque_Nm,
      radial_profile_exponent=baseline.radial_profile_exponent,
      swirl_taper_exponent=baseline.swirl_taper_exponent,
  )
  assert_allclose(
      rotated.sampleVelocity(rotation @ point),
      rotation @ baseline.sampleVelocity(point),
      rtol=3.e-13,
      atol=3.e-13,
  )
####


def test_rotor_wake_bends_side_exhaust_downward_and_swirl_reversal_mirrors_lateral_motion() -> None:
  pressure = 101325.
  density = 1.2
  background = UniformAmbientField(AmbientState(
      velocity_mps=np.zeros(3),
      pressure_Pa=pressure,
      temperature_K=300.,
      density_kgpm3=density,
  ))
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray([25., 0., 0.]),
      mass_flow_kgps=1.2,
      temperature_K=600.,
      static_pressure_Pa=pressure,
  )
  options = CurvedPlumeOptions(
      max_arc_length_m=5.,
      number_of_stations=101,
      relative_tolerance=1.e-9,
      absolute_tolerance=1.e-11,
      max_step_m=.02,
  )

  def calculate(torque_Nm: float):
    wake = ActuatorDiskWakeField(
        rotor_center_m=np.zeros(3),
        wake_axis=np.asarray([0., 0., -1.]),
        rotor_radius_m=8.,
        thrust_N=12000.,
        ambient_density_kgpm3=density,
        torque_Nm=torque_Nm,
        radial_profile_exponent=1.,
        swirl_taper_exponent=1.,
    )
    return solveCurvedPlume(
        source=source,
        ambient_field=VelocityAugmentedAmbientField(background, wake),
        entrainment_model=ConstantEntrainment(.18),
        thermodynamics=ConstantDensityMixtureThermodynamics(density),
        options=options,
    )
  ####

  no_swirl = calculate(0.)
  positive_swirl = calculate(2500.)
  negative_swirl = calculate(-2500.)
  assert no_swirl.positions_m[-1, 0] > 0.
  assert no_swirl.positions_m[-1, 2] < 0.
  assert_allclose(no_swirl.positions_m[:, 1], 0., atol=2.e-12)
  assert_allclose(
      positive_swirl.positions_m[:, 0],
      negative_swirl.positions_m[:, 0],
      rtol=2.e-9,
      atol=2.e-10,
  )
  assert_allclose(
      positive_swirl.positions_m[:, 2],
      negative_swirl.positions_m[:, 2],
      rtol=2.e-9,
      atol=2.e-10,
  )
  assert_allclose(
      positive_swirl.positions_m[:, 1],
      -negative_swirl.positions_m[:, 1],
      rtol=2.e-9,
      atol=2.e-10,
  )
  assert abs(positive_swirl.positions_m[-1, 1]) > 1.e-3
####
