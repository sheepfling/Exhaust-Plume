from __future__ import annotations

from math import pi

import numpy as np
from numpy.testing import assert_allclose

from exhaust_plume import (
    AmbientState,
    ConstantDensityMixtureThermodynamics,
    ConstantEntrainment,
    CurvedPlumeOptions,
    CurvedPlumeSource,
    CurvedPlumeTermination,
    DevelopingShearForcedEntrainment,
    UniformAmbientField,
    calculateConstantDensityFreeJetExact,
    calculateOrthogonalUniformCrossflowExact,
    solveCurvedPlume,
)


def test_constant_density_free_jet_matches_exact_solution() -> None:
  density = 1.2
  initial_radius = .25
  initial_speed = 50.
  initial_temperature = 600.
  ambient_temperature = 300.
  specific_heat = 1000.
  alpha = .06
  pressure = 101325.
  gas_constant = 287.05
  mass_flow = density * pi * initial_radius ** 2 * initial_speed
  source = CurvedPlumeSource(
      position_m=np.asarray([0., 0., 0.]),
      velocity_mps=np.asarray([0., 0., initial_speed]),
      mass_flow_kgps=mass_flow,
      temperature_K=initial_temperature,
      static_pressure_Pa=pressure,
      specific_heat_JpkgK=specific_heat,
      gas_constant_JpkgK=gas_constant,
  )
  ambient = UniformAmbientField(AmbientState(
      velocity_mps=np.zeros(3),
      pressure_Pa=pressure,
      temperature_K=ambient_temperature,
      density_kgpm3=density,
      specific_heat_JpkgK=specific_heat,
      gas_constant_JpkgK=gas_constant,
  ))
  options = CurvedPlumeOptions(
      max_arc_length_m=5.,
      number_of_stations=101,
      relative_tolerance=1.e-10,
      absolute_tolerance=1.e-12,
      max_step_m=.02,
  )
  result = solveCurvedPlume(
      source=source,
      ambient_field=ambient,
      entrainment_model=DevelopingShearForcedEntrainment(
          shear_coefficient=alpha,
          forced_coefficient=0.,
          combination_exponent=2.,
          initial_development_fraction=1.,
          development_length_m=1.,
      ),
      options=options,
      thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3=density),
  )
  exact = calculateConstantDensityFreeJetExact(
      arc_lengths_m=result.arc_lengths_m,
      initial_radius_m=initial_radius,
      initial_speed_mps=initial_speed,
      density_kgpm3=density,
      entrainment_coefficient=alpha,
      initial_temperature_K=initial_temperature,
      ambient_temperature_K=ambient_temperature,
      specific_heat_JpkgK=specific_heat,
  )
  stations = result.stations
  assert result.termination is CurvedPlumeTermination.DOMAIN_LIMIT
  assert_allclose([station.mass_flow_kgps for station in stations], exact.mass_flow_kgps, rtol=2.e-9)
  assert_allclose([station.radius_m for station in stations], exact.radius_m, rtol=2.e-9)
  assert_allclose([station.speed_mps for station in stations], exact.speed_mps, rtol=2.e-9)
  assert_allclose([station.temperature_K for station in stations], exact.temperature_K, rtol=2.e-9)
  assert_allclose([station.exhaust_mass_fraction for station in stations], exact.exhaust_mass_fraction, rtol=2.e-9)
  assert_allclose(result.positions_m[:, :2], 0., atol=1.e-12)
  assert_allclose(result.positions_m[:, 2], result.arc_lengths_m, atol=1.e-11)
####


def test_uniform_crossflow_constant_entrainment_matches_exact_trajectory() -> None:
  pressure = 101325.
  density = 1.15
  temperature = 300.
  specific_heat = 1000.
  initial_mass_flow = 2.
  initial_speed = 40.
  crossflow_speed = 10.
  entrainment = .4
  source_position = np.asarray([1., -2., 3.])
  jet_direction = np.asarray([0., 0., 1.])
  crossflow_direction = np.asarray([1., 0., 0.])
  source = CurvedPlumeSource(
      position_m=source_position,
      velocity_mps=initial_speed * jet_direction,
      mass_flow_kgps=initial_mass_flow,
      temperature_K=temperature,
      static_pressure_Pa=pressure,
      specific_heat_JpkgK=specific_heat,
  )
  ambient_velocity = crossflow_speed * crossflow_direction
  ambient = UniformAmbientField(AmbientState(
      velocity_mps=ambient_velocity,
      pressure_Pa=pressure,
      temperature_K=temperature,
      density_kgpm3=density,
      specific_heat_JpkgK=specific_heat,
  ))
  options = CurvedPlumeOptions(
      max_arc_length_m=12.,
      number_of_stations=121,
      relative_tolerance=1.e-11,
      absolute_tolerance=1.e-13,
      max_step_m=.02,
  )
  result = solveCurvedPlume(
      source=source,
      ambient_field=ambient,
      entrainment_model=ConstantEntrainment(entrainment),
      options=options,
      thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3=density),
  )
  exact = calculateOrthogonalUniformCrossflowExact(
      arc_lengths_m=result.arc_lengths_m,
      source_position_m=source_position,
      jet_direction=jet_direction,
      crossflow_direction=crossflow_direction,
      initial_speed_mps=initial_speed,
      crossflow_speed_mps=crossflow_speed,
      initial_mass_flow_kgps=initial_mass_flow,
      mass_entrainment_kgpspm=entrainment,
  )
  assert_allclose(result.positions_m, exact.positions_m, rtol=2.e-10, atol=2.e-11)
  assert_allclose([station.mass_flow_kgps for station in result.stations], exact.mass_flow_kgps, rtol=2.e-11)
  assert_allclose([station.velocity_mps for station in result.stations], exact.velocity_mps, rtol=2.e-11)
  relative_momentum = np.asarray([
      station.momentum_flux_N - station.mass_flow_kgps * ambient_velocity
      for station in result.stations
  ])
  expected_relative_momentum = initial_mass_flow * (initial_speed * jet_direction - ambient_velocity)
  assert_allclose(
      relative_momentum,
      np.broadcast_to(expected_relative_momentum, relative_momentum.shape),
      rtol=2.e-11,
      atol=2.e-11,
  )
  assert_allclose(
      [station.exhaust_mass_flow_kgps for station in result.stations],
      source.exhaust_mass_flow_kgps,
      rtol=0.,
      atol=1.e-13,
  )
  expected_initial_curvature = entrainment * crossflow_speed / (initial_mass_flow * initial_speed)
  assert_allclose(result.stations[0].curvature_per_m, expected_initial_curvature, rtol=1.e-12)
####


def test_rotation_invariance_for_uniform_crossflow() -> None:
  angle = np.deg2rad(37.)
  rotation = np.asarray([
      [np.cos(angle), -np.sin(angle), 0.],
      [np.sin(angle), np.cos(angle), 0.],
      [0., 0., 1.],
  ])
  pressure = 101325.
  density = 1.2
  ambient_state = AmbientState(
      velocity_mps=np.asarray([8., 0., 0.]),
      pressure_Pa=pressure,
      temperature_K=300.,
      density_kgpm3=density,
  )
  source = CurvedPlumeSource(
      position_m=np.asarray([0., 0., 0.]),
      velocity_mps=np.asarray([0., 0., 30.]),
      mass_flow_kgps=1.5,
      temperature_K=500.,
      static_pressure_Pa=pressure,
  )
  options = CurvedPlumeOptions(max_arc_length_m=4., number_of_stations=81, max_step_m=.02)
  baseline = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(ambient_state),
      entrainment_model=ConstantEntrainment(.25),
      options=options,
      thermodynamics=ConstantDensityMixtureThermodynamics(density),
  )
  rotated = solveCurvedPlume(
      source=CurvedPlumeSource(
          position_m=rotation @ source.position_m,
          velocity_mps=rotation @ source.velocity_mps,
          mass_flow_kgps=source.mass_flow_kgps,
          temperature_K=source.temperature_K,
          static_pressure_Pa=source.static_pressure_Pa,
      ),
      ambient_field=UniformAmbientField(AmbientState(
          velocity_mps=rotation @ ambient_state.velocity_mps,
          pressure_Pa=ambient_state.pressure_Pa,
          temperature_K=ambient_state.temperature_K,
          density_kgpm3=ambient_state.density_kgpm3,
      )),
      entrainment_model=ConstantEntrainment(.25),
      options=options,
      thermodynamics=ConstantDensityMixtureThermodynamics(density),
  )
  assert_allclose(rotated.positions_m, baseline.positions_m @ rotation.T, rtol=2.e-9, atol=2.e-10)
####


def test_ideal_gas_kernel_conserves_uniform_ambient_invariants() -> None:
  pressure = 101325.
  ambient_state = AmbientState.fromIdealGas(
      velocity_mps=np.asarray([6., -2., 1.]),
      pressure_Pa=pressure,
      temperature_K=290.,
      specific_heat_JpkgK=1005.,
      gas_constant_JpkgK=287.05,
  )
  source = CurvedPlumeSource(
      position_m=np.asarray([0., 0., 0.]),
      velocity_mps=np.asarray([20., 3., 12.]),
      mass_flow_kgps=1.8,
      temperature_K=700.,
      static_pressure_Pa=pressure,
      specific_heat_JpkgK=1160.,
      gas_constant_JpkgK=300.,
      exhaust_mass_fraction=.85,
  )
  result = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(ambient_state),
      entrainment_model=ConstantEntrainment(.3),
      options=CurvedPlumeOptions(max_arc_length_m=8., number_of_stations=81, max_step_m=.025),
  )
  ambient_total_energy = (
      ambient_state.specific_heat_JpkgK * ambient_state.temperature_K
      + .5 * float(ambient_state.velocity_mps @ ambient_state.velocity_mps)
  )
  relative_momentum = np.asarray([
      station.momentum_flux_N - station.mass_flow_kgps * ambient_state.velocity_mps
      for station in result.stations
  ])
  relative_energy = np.asarray([
      station.total_energy_flow_W - station.mass_flow_kgps * ambient_total_energy
      for station in result.stations
  ])
  assert_allclose(
      relative_momentum,
      np.broadcast_to(relative_momentum[0], relative_momentum.shape),
      rtol=5.e-9,
      atol=5.e-9,
  )
  assert_allclose(relative_energy, relative_energy[0], rtol=5.e-9, atol=5.e-6)
  assert_allclose(
      [station.exhaust_mass_flow_kgps for station in result.stations],
      source.exhaust_mass_flow_kgps,
      rtol=0.,
      atol=1.e-12,
  )
  for station in result.stations:
    assert_allclose(
        station.density_kgpm3,
        station.pressure_Pa / (station.gas_constant_JpkgK * station.temperature_K),
        rtol=1.e-13,
    )
  ####
####


def test_source_pressure_mismatch_is_rejected() -> None:
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray([1., 0., 0.]),
      mass_flow_kgps=1.,
      temperature_K=400.,
      static_pressure_Pa=2. * 101325.,
  )
  ambient = UniformAmbientField(AmbientState.fromIdealGas(
      velocity_mps=np.zeros(3),
      pressure_Pa=101325.,
      temperature_K=300.,
  ))
  try:
    solveCurvedPlume(
        source=source,
        ambient_field=ambient,
        entrainment_model=ConstantEntrainment(0.),
        options=CurvedPlumeOptions(max_arc_length_m=1.),
    )
  except ValueError as exc:
    assert 'pressure matched' in str(exc)
  else:
    raise AssertionError('Expected a pressure-mismatch ValueError.')
  ####
####
