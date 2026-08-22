from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin
from unittest import TestCase

import numpy as np
from numpy.testing import assert_allclose
from numpy.typing import NDArray

from exhaust_plume import (
    AmbientState,
    ConstantDensityMixtureThermodynamics,
    ConstantEntrainment,
    CurvedPlumeOptions,
    CurvedPlumeResult,
    CurvedPlumeSource,
    CurvedPlumeSourceTerms,
    CurvedPlumeStation,
    CurvedPlumeTermination,
    DevelopingShearForcedEntrainment,
    UniformAmbientField,
    calculateConstantDensityFreeJetExact,
    calculateOrthogonalUniformCrossflowExact,
    solveCurvedPlume,
)


@dataclass(frozen=True)
class ConstantSourceTermModel:
  force_Npm: NDArray[np.float64]
  energy_source_Wpm: float

  def calculateSourceTerms(
      self,
      *,
      arc_length_m: float,
      station: CurvedPlumeStation,
      source: CurvedPlumeSource,
  ) -> CurvedPlumeSourceTerms:
    del arc_length_m, station, source
    return CurvedPlumeSourceTerms(
        force_Npm=self.force_Npm,
        energy_source_Wpm=self.energy_source_Wpm,
    )
  ####
####


class TestCurvedPlume(TestCase):
  def test_constant_density_free_jet_matches_exact_solution(self) -> None:
    density_kgpm3 = 1.2
    initial_radius_m = .25
    initial_speed_mps = 50.
    initial_temperature_K = 300.
    ambient_temperature_K = 300.
    specific_heat_JpkgK = 1000.
    entrainment_coefficient = .06
    pressure_Pa = 101325.
    initial_mass_flow_kgps = density_kgpm3 * pi * initial_radius_m ** 2 * initial_speed_mps
    ambient = UniformAmbientField(AmbientState(
        velocity_mps=np.zeros(3),
        pressure_Pa=pressure_Pa,
        temperature_K=ambient_temperature_K,
        density_kgpm3=density_kgpm3,
        specific_heat_JpkgK=specific_heat_JpkgK,
        gas_constant_JpkgK=287.05,
    ))
    source = CurvedPlumeSource(
        position_m=np.zeros(3),
        velocity_mps=np.asarray((0., 0., initial_speed_mps)),
        mass_flow_kgps=initial_mass_flow_kgps,
        temperature_K=initial_temperature_K,
        static_pressure_Pa=pressure_Pa,
        specific_heat_JpkgK=specific_heat_JpkgK,
        gas_constant_JpkgK=287.05,
    )
    result = solveCurvedPlume(
        source=source,
        ambient_field=ambient,
        entrainment_model=DevelopingShearForcedEntrainment(
            shear_coefficient=entrainment_coefficient,
            forced_coefficient=0.,
            combination_exponent=2.,
            initial_development_fraction=1.,
            development_length_m=1.,
        ),
        thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3=density_kgpm3),
        options=CurvedPlumeOptions(
            max_arc_length_m=5.,
            number_of_stations=101,
            relative_tolerance=1.e-10,
            absolute_tolerance=1.e-12,
            max_step_m=.02,
        ),
    )
    exact = calculateConstantDensityFreeJetExact(
        arc_lengths_m=result.arc_lengths_m,
        initial_radius_m=initial_radius_m,
        initial_speed_mps=initial_speed_mps,
        density_kgpm3=density_kgpm3,
        entrainment_coefficient=entrainment_coefficient,
        initial_temperature_K=initial_temperature_K,
        ambient_temperature_K=ambient_temperature_K,
        specific_heat_JpkgK=specific_heat_JpkgK,
    )

    self.assertEqual(result.termination, CurvedPlumeTermination.DOMAIN_LIMIT)
    assert_allclose([station.mass_flow_kgps for station in result.stations], exact.mass_flow_kgps, rtol=2.e-10, atol=1.e-12)
    assert_allclose([station.radius_m for station in result.stations], exact.radius_m, rtol=2.e-10, atol=1.e-12)
    assert_allclose([station.speed_mps for station in result.stations], exact.speed_mps, rtol=2.e-10, atol=1.e-12)
    assert_allclose([station.temperature_K for station in result.stations], exact.temperature_K, rtol=2.e-10, atol=1.e-12)
    assert_allclose(
        [station.exhaust_mass_fraction for station in result.stations],
        exact.exhaust_mass_fraction,
        rtol=2.e-10,
        atol=1.e-12,
    )
    assert_allclose(result.positions_m[:, :2], 0., atol=1.e-12)
    assert_allclose(result.positions_m[:, 2], result.arc_lengths_m, rtol=1.e-12, atol=1.e-12)
  ####

  def test_uniform_crossflow_matches_exact_constant_entrainment_trajectory(self) -> None:
    density_kgpm3 = 1.1
    pressure_Pa = 101325.
    temperature_K = 300.
    initial_mass_flow_kgps = 2.
    initial_speed_mps = 40.
    crossflow_speed_mps = 10.
    mass_entrainment_kgpspm = .4
    source_position_m = np.asarray((1., -2., .5))
    jet_direction = np.asarray((0., 0., 1.))
    crossflow_direction = np.asarray((1., 0., 0.))
    ambient_velocity = crossflow_speed_mps * crossflow_direction
    ambient = UniformAmbientField(AmbientState(
        velocity_mps=ambient_velocity,
        pressure_Pa=pressure_Pa,
        temperature_K=temperature_K,
        density_kgpm3=density_kgpm3,
        specific_heat_JpkgK=1000.,
        gas_constant_JpkgK=287.05,
    ))
    source = CurvedPlumeSource(
        position_m=source_position_m,
        velocity_mps=initial_speed_mps * jet_direction,
        mass_flow_kgps=initial_mass_flow_kgps,
        temperature_K=temperature_K,
        static_pressure_Pa=pressure_Pa,
        specific_heat_JpkgK=1000.,
        gas_constant_JpkgK=287.05,
    )
    result = solveCurvedPlume(
        source=source,
        ambient_field=ambient,
        entrainment_model=ConstantEntrainment(mass_entrainment_kgpspm=mass_entrainment_kgpspm),
        thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3=density_kgpm3),
        options=CurvedPlumeOptions(
            max_arc_length_m=10.,
            number_of_stations=201,
            relative_tolerance=1.e-10,
            absolute_tolerance=1.e-12,
            max_step_m=.02,
        ),
    )
    exact = calculateOrthogonalUniformCrossflowExact(
        arc_lengths_m=result.arc_lengths_m,
        source_position_m=source_position_m,
        jet_direction=jet_direction,
        crossflow_direction=crossflow_direction,
        initial_speed_mps=initial_speed_mps,
        crossflow_speed_mps=crossflow_speed_mps,
        initial_mass_flow_kgps=initial_mass_flow_kgps,
        mass_entrainment_kgpspm=mass_entrainment_kgpspm,
    )

    assert_allclose(result.positions_m, exact.positions_m, rtol=3.e-10, atol=2.e-11)
    assert_allclose([station.mass_flow_kgps for station in result.stations], exact.mass_flow_kgps, rtol=2.e-12, atol=2.e-12)
    assert_allclose([station.momentum_flux_N for station in result.stations], exact.momentum_flux_N, rtol=2.e-12, atol=2.e-12)
    assert_allclose([station.velocity_mps for station in result.stations], exact.velocity_mps, rtol=2.e-12, atol=2.e-12)

    relative_momentum = np.vstack([
        station.momentum_flux_N - station.mass_flow_kgps * ambient_velocity
        for station in result.stations
    ])
    expected_relative_momentum = np.repeat(
        (initial_mass_flow_kgps * (source.velocity_mps - ambient_velocity))[np.newaxis, :],
        len(result.stations),
        axis=0,
    )
    assert_allclose(relative_momentum, expected_relative_momentum, rtol=2.e-12, atol=2.e-12)
    assert_allclose(
        [station.exhaust_mass_flow_kgps for station in result.stations],
        source.exhaust_mass_flow_kgps,
        rtol=0.,
        atol=1.e-12,
    )
    assert_allclose(
        result.stations[0].curvature_per_m,
        1. / exact.turning_length_m,
        rtol=2.e-12,
        atol=2.e-12,
    )
  ####

  def test_pressure_mismatch_fails_before_integration(self) -> None:
    ambient = UniformAmbientField(AmbientState.fromIdealGas(
        velocity_mps=np.zeros(3),
        pressure_Pa=101325.,
        temperature_K=300.,
    ))
    source = CurvedPlumeSource(
        position_m=np.zeros(3),
        velocity_mps=np.asarray((1., 0., 0.)),
        mass_flow_kgps=1.,
        temperature_K=500.,
        static_pressure_Pa=2. * 101325.,
    )
    with self.assertRaises(ValueError):
      solveCurvedPlume(
          source=source,
          ambient_field=ambient,
          entrainment_model=ConstantEntrainment(0.),
          options=CurvedPlumeOptions(max_arc_length_m=1.),
      )
    ####
  ####
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


def test_rotation_invariance() -> None:
  axis = np.asarray([1., 2., 3.])
  axis /= np.linalg.norm(axis)
  angle = .73
  cross_matrix = np.asarray((
      (0., -axis[2], axis[1]),
      (axis[2], 0., -axis[0]),
      (-axis[1], axis[0], 0.),
  ))
  rotation = (
      cos(angle) * np.eye(3)
      + (1. - cos(angle)) * np.outer(axis, axis)
      + sin(angle) * cross_matrix
  )
  pressure = 101325.
  density = 1.15
  source_position = np.asarray([1., -2., .5])
  source_velocity = np.asarray([0., 0., 35.])
  ambient_velocity = np.asarray([8., 0., 0.])
  options = CurvedPlumeOptions(
      max_arc_length_m=6.,
      number_of_stations=121,
      relative_tolerance=1.e-10,
      absolute_tolerance=1.e-12,
      max_step_m=.02,
  )

  def calculate(
      position_m: NDArray[np.float64],
      velocity_mps: NDArray[np.float64],
      ambient_mps: NDArray[np.float64],
  ) -> CurvedPlumeResult:
    return solveCurvedPlume(
        source=CurvedPlumeSource(
            position_m=position_m,
            velocity_mps=velocity_mps,
            mass_flow_kgps=1.7,
            temperature_K=500.,
            static_pressure_Pa=pressure,
            specific_heat_JpkgK=1100.,
        ),
        ambient_field=UniformAmbientField(AmbientState(
            velocity_mps=ambient_mps,
            pressure_Pa=pressure,
            temperature_K=290.,
            density_kgpm3=density,
        )),
        entrainment_model=ConstantEntrainment(.25),
        thermodynamics=ConstantDensityMixtureThermodynamics(density),
        options=options,
    )
  ####

  baseline = calculate(source_position, source_velocity, ambient_velocity)
  rotated = calculate(rotation @ source_position, rotation @ source_velocity, rotation @ ambient_velocity)
  assert_allclose(rotated.positions_m, baseline.positions_m @ rotation.T, rtol=3.e-10, atol=3.e-11)
  assert_allclose(
      [station.momentum_flux_N for station in rotated.stations],
      np.asarray([station.momentum_flux_N for station in baseline.stations]) @ rotation.T,
      rtol=3.e-11,
      atol=3.e-11,
  )
  assert_allclose(
      [station.mass_flow_kgps for station in rotated.stations],
      [station.mass_flow_kgps for station in baseline.stations],
      rtol=2.e-12,
      atol=2.e-12,
  )
  assert_allclose(
      [station.temperature_K for station in rotated.stations],
      [station.temperature_K for station in baseline.stations],
      rtol=3.e-11,
      atol=3.e-11,
  )
####


def test_external_source_terms_drive_momentum_energy_and_curvature() -> None:
  pressure = 101325.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray([20., 0., 0.]),
      mass_flow_kgps=2.,
      temperature_K=400.,
      static_pressure_Pa=pressure,
      specific_heat_JpkgK=1000.,
  )
  force_Npm = np.asarray([0., 4., 0.])
  energy_source_Wpm = 25.
  result = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(AmbientState.fromIdealGas(
          velocity_mps=np.zeros(3),
          pressure_Pa=pressure,
          temperature_K=300.,
      )),
      entrainment_model=ConstantEntrainment(0.),
      source_term_model=ConstantSourceTermModel(force_Npm, energy_source_Wpm),
      options=CurvedPlumeOptions(
          max_arc_length_m=3.,
          number_of_stations=61,
          relative_tolerance=1.e-10,
          absolute_tolerance=1.e-12,
          max_step_m=.01,
      ),
  )
  arc_lengths = result.arc_lengths_m
  initial_momentum = source.mass_flow_kgps * source.velocity_mps
  expected_momentum = initial_momentum[np.newaxis, :] + arc_lengths[:, np.newaxis] * force_Npm[np.newaxis, :]
  initial_energy = source.mass_flow_kgps * (
      source.specific_heat_JpkgK * source.temperature_K
      + .5 * float(source.velocity_mps @ source.velocity_mps)
  )
  expected_energy = initial_energy + arc_lengths * energy_source_Wpm
  assert_allclose([station.momentum_flux_N for station in result.stations], expected_momentum, rtol=2.e-11, atol=2.e-11)
  assert_allclose([station.total_energy_flow_W for station in result.stations], expected_energy, rtol=2.e-11, atol=2.e-8)
  assert_allclose(result.stations[0].curvature_per_m, np.linalg.norm(force_Npm) / np.linalg.norm(initial_momentum), rtol=1.e-13)
####
