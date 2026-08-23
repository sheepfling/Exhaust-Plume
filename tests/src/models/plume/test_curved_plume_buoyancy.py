from __future__ import annotations

from dataclasses import dataclass
from math import cos, pi, sin

import numpy as np
from numpy.testing import assert_allclose
from numpy.typing import NDArray

from exhaust_plume import (
    AmbientState,
    ConstantDensityMixtureThermodynamics,
    ConstantEntrainment,
    CurvedPlumeOptions,
    CurvedPlumeSource,
    CurvedPlumeSourceTerms,
    CurvedPlumeStation,
    UniformAmbientField,
    solveCurvedPlume,
)
from exhaust_plume.models.plume.curved_plume_buoyancy import (
    CompositeCurvedPlumeSourceTermModel,
    HydrostaticBuoyancySourceTermModel,
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


def test_vertical_light_plume_matches_exact_reduced_gravity_solution() -> None:
  plume_density_kgpm3 = 1.
  ambient_density_kgpm3 = 1.2
  gravity_mps2 = 9.80665
  initial_radius_m = .2
  initial_speed_mps = 20.
  initial_temperature_K = 500.
  specific_heat_JpkgK = 1100.
  pressure_Pa = 101325.
  initial_mass_flow_kgps = (
      plume_density_kgpm3
      * pi
      * initial_radius_m ** 2
      * initial_speed_mps
  )
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray((0., 0., initial_speed_mps)),
      mass_flow_kgps=initial_mass_flow_kgps,
      temperature_K=initial_temperature_K,
      static_pressure_Pa=pressure_Pa,
      specific_heat_JpkgK=specific_heat_JpkgK,
  )
  ambient = UniformAmbientField(AmbientState(
      velocity_mps=np.zeros(3),
      pressure_Pa=pressure_Pa,
      temperature_K=300.,
      density_kgpm3=ambient_density_kgpm3,
      specific_heat_JpkgK=1004.5,
  ))
  result = solveCurvedPlume(
      source=source,
      ambient_field=ambient,
      entrainment_model=ConstantEntrainment(0.),
      source_term_model=HydrostaticBuoyancySourceTermModel(
          gravity_mps2=np.asarray((0., 0., -gravity_mps2))
      ),
      thermodynamics=ConstantDensityMixtureThermodynamics(
          density_kgpm3=plume_density_kgpm3
      ),
      options=CurvedPlumeOptions(
          max_arc_length_m=12.,
          number_of_stations=241,
          relative_tolerance=1.e-10,
          absolute_tolerance=1.e-12,
          max_step_m=.01,
      ),
  )

  reduced_acceleration_mps2 = (
      (ambient_density_kgpm3 - plume_density_kgpm3)
      / plume_density_kgpm3
      * gravity_mps2
  )
  expected_speed_mps = np.sqrt(
      initial_speed_mps ** 2
      + 2. * reduced_acceleration_mps2 * result.arc_lengths_m
  )
  expected_radius_m = np.sqrt(
      initial_mass_flow_kgps
      / (plume_density_kgpm3 * pi * expected_speed_mps)
  )
  expected_total_energy_flow_W = initial_mass_flow_kgps * (
      specific_heat_JpkgK * initial_temperature_K
      + .5 * expected_speed_mps ** 2
  )

  assert_allclose(result.positions_m[:, :2], 0., atol=2.e-12)
  assert_allclose(result.positions_m[:, 2], result.arc_lengths_m, rtol=1.e-12, atol=2.e-12)
  assert_allclose(
      [station.speed_mps for station in result.stations],
      expected_speed_mps,
      rtol=2.e-10,
      atol=2.e-10,
  )
  assert_allclose(
      [station.radius_m for station in result.stations],
      expected_radius_m,
      rtol=2.e-10,
      atol=2.e-12,
  )
  assert_allclose(
      [station.temperature_K for station in result.stations],
      initial_temperature_K,
      rtol=2.e-11,
      atol=2.e-9,
  )
  assert_allclose(
      [station.total_energy_flow_W for station in result.stations],
      expected_total_energy_flow_W,
      rtol=2.e-10,
      atol=2.e-7,
  )
  assert_allclose(
      [station.curvature_per_m for station in result.stations],
      0.,
      atol=2.e-13,
  )
####


def test_horizontal_light_plume_bends_upward_with_expected_initial_curvature() -> None:
  plume_density_kgpm3 = .9
  ambient_density_kgpm3 = 1.2
  gravity_vector_mps2 = np.asarray((0., 0., -9.80665))
  radius_m = .18
  speed_mps = 25.
  mass_flow_kgps = plume_density_kgpm3 * pi * radius_m ** 2 * speed_mps
  pressure_Pa = 101325.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray((speed_mps, 0., 0.)),
      mass_flow_kgps=mass_flow_kgps,
      temperature_K=600.,
      static_pressure_Pa=pressure_Pa,
  )
  result = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(AmbientState(
          velocity_mps=np.zeros(3),
          pressure_Pa=pressure_Pa,
          temperature_K=300.,
          density_kgpm3=ambient_density_kgpm3,
      )),
      entrainment_model=ConstantEntrainment(0.),
      source_term_model=HydrostaticBuoyancySourceTermModel(gravity_vector_mps2),
      thermodynamics=ConstantDensityMixtureThermodynamics(plume_density_kgpm3),
      options=CurvedPlumeOptions(
          max_arc_length_m=5.,
          number_of_stations=101,
          relative_tolerance=1.e-10,
          absolute_tolerance=1.e-12,
          max_step_m=.01,
      ),
  )
  initial_station = result.stations[0]
  expected_force_Npm = (
      (plume_density_kgpm3 - ambient_density_kgpm3)
      * initial_station.area_m2
      * gravity_vector_mps2
  )
  expected_curvature_per_m = (
      np.linalg.norm(expected_force_Npm)
      / np.linalg.norm(initial_station.momentum_flux_N)
  )
  assert_allclose(initial_station.momentum_derivative_Npm, expected_force_Npm, rtol=1.e-13)
  assert_allclose(initial_station.curvature_per_m, expected_curvature_per_m, rtol=1.e-13)
  assert result.positions_m[-1, 0] > 0.
  assert result.positions_m[-1, 2] > 0.
  assert_allclose(result.positions_m[:, 1], 0., atol=2.e-12)
  assert_allclose(
      [station.temperature_K for station in result.stations],
      source.temperature_K,
      rtol=2.e-10,
      atol=2.e-8,
  )
####


def test_composite_source_term_model_adds_force_and_energy() -> None:
  pressure_Pa = 101325.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray((10., 0., 0.)),
      mass_flow_kgps=1.,
      temperature_K=400.,
      static_pressure_Pa=pressure_Pa,
  )
  ambient = UniformAmbientField(AmbientState(
      velocity_mps=np.zeros(3),
      pressure_Pa=pressure_Pa,
      temperature_K=300.,
      density_kgpm3=1.2,
  ))
  baseline = solveCurvedPlume(
      source=source,
      ambient_field=ambient,
      entrainment_model=ConstantEntrainment(0.),
      thermodynamics=ConstantDensityMixtureThermodynamics(1.),
      options=CurvedPlumeOptions(max_arc_length_m=.1, number_of_stations=2),
  )
  station = baseline.stations[0]
  buoyancy = HydrostaticBuoyancySourceTermModel()
  constant = ConstantSourceTermModel(
      force_Npm=np.asarray((1., 2., 3.)),
      energy_source_Wpm=17.,
  )
  combined = CompositeCurvedPlumeSourceTermModel((buoyancy, constant))
  buoyancy_terms = buoyancy.calculateSourceTerms(
      arc_length_m=0., station=station, source=source
  )
  combined_terms = combined.calculateSourceTerms(
      arc_length_m=0., station=station, source=source
  )
  assert_allclose(
      combined_terms.force_Npm,
      buoyancy_terms.force_Npm + constant.force_Npm,
      rtol=0.,
      atol=1.e-14,
  )
  assert_allclose(
      combined_terms.energy_source_Wpm,
      buoyancy_terms.energy_source_Wpm + constant.energy_source_Wpm,
      rtol=0.,
      atol=1.e-14,
  )
####


def test_buoyancy_solution_is_rotation_invariant() -> None:
  axis = np.asarray((1., -2., 3.))
  axis /= np.linalg.norm(axis)
  angle = .67
  cross = np.asarray((
      (0., -axis[2], axis[1]),
      (axis[2], 0., -axis[0]),
      (-axis[1], axis[0], 0.),
  ))
  rotation = (
      cos(angle) * np.eye(3)
      + (1. - cos(angle)) * np.outer(axis, axis)
      + sin(angle) * cross
  )
  pressure_Pa = 101325.
  gravity = np.asarray((0., 0., -9.80665))
  position = np.asarray((1., -2., .5))
  velocity = np.asarray((20., 3., 1.))
  ambient_velocity = np.asarray((2., -1., .5))
  options = CurvedPlumeOptions(
      max_arc_length_m=4.,
      number_of_stations=81,
      relative_tolerance=1.e-10,
      absolute_tolerance=1.e-12,
      max_step_m=.01,
  )

  def calculate(
      source_position_m: NDArray[np.float64],
      source_velocity_mps: NDArray[np.float64],
      local_ambient_velocity_mps: NDArray[np.float64],
      local_gravity_mps2: NDArray[np.float64],
  ):
    return solveCurvedPlume(
        source=CurvedPlumeSource(
            position_m=source_position_m,
            velocity_mps=source_velocity_mps,
            mass_flow_kgps=1.5,
            temperature_K=500.,
            static_pressure_Pa=pressure_Pa,
        ),
        ambient_field=UniformAmbientField(AmbientState(
            velocity_mps=local_ambient_velocity_mps,
            pressure_Pa=pressure_Pa,
            temperature_K=300.,
            density_kgpm3=1.2,
        )),
        entrainment_model=ConstantEntrainment(.1),
        source_term_model=HydrostaticBuoyancySourceTermModel(local_gravity_mps2),
        thermodynamics=ConstantDensityMixtureThermodynamics(1.),
        options=options,
    )
  ####

  baseline = calculate(position, velocity, ambient_velocity, gravity)
  rotated = calculate(
      rotation @ position,
      rotation @ velocity,
      rotation @ ambient_velocity,
      rotation @ gravity,
  )
  assert_allclose(
      rotated.positions_m,
      baseline.positions_m @ rotation.T,
      rtol=4.e-10,
      atol=4.e-10,
  )
  assert_allclose(
      [station.momentum_flux_N for station in rotated.stations],
      np.asarray([station.momentum_flux_N for station in baseline.stations]) @ rotation.T,
      rtol=4.e-10,
      atol=4.e-10,
  )
  assert_allclose(
      [station.temperature_K for station in rotated.stations],
      [station.temperature_K for station in baseline.stations],
      rtol=4.e-10,
      atol=4.e-8,
  )
####


def test_zero_gravity_is_rejected() -> None:
  try:
    HydrostaticBuoyancySourceTermModel(np.zeros(3))
  except ValueError as exc:
    assert 'non-zero' in str(exc)
  else:
    raise AssertionError('Expected a zero-gravity ValueError.')
  ####
####
