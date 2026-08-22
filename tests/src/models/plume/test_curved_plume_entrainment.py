from __future__ import annotations

from math import exp, pi, sqrt

import numpy as np
from numpy.testing import assert_allclose

from exhaust_plume import (
    AmbientState,
    ConstantDensityMixtureThermodynamics,
    CurvedPlumeOptions,
    CurvedPlumeSource,
    UniformAmbientField,
    solveCurvedPlume,
)
from exhaust_plume.models.plume.curved_plume_entrainment import (
    DevelopingShearForcedEntrainment,
)


def test_developing_free_jet_matches_exact_integrated_solution() -> None:
  density_kgpm3 = 1.1
  radius_m = .17
  speed_mps = 32.
  mass_flow_kgps = density_kgpm3 * pi * radius_m ** 2 * speed_mps
  shear_coefficient = .071
  initial_fraction = .28
  development_length_m = .9
  pressure_Pa = 101325.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray((speed_mps, 0., 0.)),
      mass_flow_kgps=mass_flow_kgps,
      temperature_K=500.,
      static_pressure_Pa=pressure_Pa,
  )
  result = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(AmbientState(
          velocity_mps=np.zeros(3),
          pressure_Pa=pressure_Pa,
          temperature_K=300.,
          density_kgpm3=density_kgpm3,
      )),
      entrainment_model=DevelopingShearForcedEntrainment(
          shear_coefficient=shear_coefficient,
          initial_development_fraction=initial_fraction,
          development_length_m=development_length_m,
      ),
      thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3),
      options=CurvedPlumeOptions(
          max_arc_length_m=12.,
          number_of_stations=241,
          relative_tolerance=1.e-10,
          absolute_tolerance=1.e-12,
          max_step_m=.01,
      ),
  )
  s = result.arc_lengths_m
  effective_length_m = s - (
      (1. - initial_fraction)
      * development_length_m
      * (1. - np.exp(-s / development_length_m))
  )
  mass_ratio = 1. + 2. * shear_coefficient * effective_length_m / radius_m
  assert_allclose(
      [station.mass_flow_kgps for station in result.stations],
      mass_flow_kgps * mass_ratio,
      rtol=3.e-10,
      atol=3.e-11,
  )
  assert_allclose(
      [station.speed_mps for station in result.stations],
      speed_mps / mass_ratio,
      rtol=3.e-10,
      atol=3.e-10,
  )
  assert_allclose(
      [station.radius_m for station in result.stations],
      radius_m * mass_ratio,
      rtol=3.e-10,
      atol=3.e-11,
  )
  assert_allclose(
      [station.exhaust_mass_fraction for station in result.stations],
      1. / mass_ratio,
      rtol=3.e-10,
      atol=3.e-11,
  )
####


def test_development_factor_has_exact_initial_and_asymptotic_limits() -> None:
  model = DevelopingShearForcedEntrainment(
      shear_coefficient=.07,
      initial_development_fraction=.31,
      development_length_m=2.4,
  )
  assert model.calculateDevelopmentFactor(0.) == .31
  assert_allclose(
      model.calculateDevelopmentFactor(2.4),
      1. - .69 / exp(1.),
      rtol=1.e-14,
  )
  assert_allclose(model.calculateDevelopmentFactor(100.), 1., atol=1.e-14)
####


def test_forced_component_uses_normal_ambient_speed_and_projected_width() -> None:
  density_kgpm3 = 1.2
  radius_m = .2
  source_speed_mps = 30.
  crossflow_speed_mps = 8.
  forced_coefficient = .63
  pressure_Pa = 101325.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray((source_speed_mps, 0., 0.)),
      mass_flow_kgps=density_kgpm3 * pi * radius_m ** 2 * source_speed_mps,
      temperature_K=400.,
      static_pressure_Pa=pressure_Pa,
  )
  baseline = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(AmbientState(
          velocity_mps=np.asarray((3., crossflow_speed_mps, 0.)),
          pressure_Pa=pressure_Pa,
          temperature_K=300.,
          density_kgpm3=density_kgpm3,
      )),
      entrainment_model=DevelopingShearForcedEntrainment(0.),
      thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3),
      options=CurvedPlumeOptions(max_arc_length_m=.1, number_of_stations=2),
  )
  station = baseline.stations[0]
  model = DevelopingShearForcedEntrainment(
      shear_coefficient=0.,
      forced_coefficient=forced_coefficient,
  )
  components = model.calculateComponents(
      arc_length_m=0., station=station, source=source
  )
  expected_rate_kgpspm = (
      2. * radius_m
      * forced_coefficient
      * density_kgpm3
      * crossflow_speed_mps
  )
  assert_allclose(components.crossflow_speed_mps, crossflow_speed_mps, rtol=1.e-14)
  assert_allclose(components.shear_mass_rate_kgpspm, 0., atol=0.)
  assert_allclose(components.forced_mass_rate_kgpspm, expected_rate_kgpspm, rtol=1.e-14)
  assert_allclose(components.total_mass_rate_kgpspm, expected_rate_kgpspm, rtol=1.e-14)
####


def test_component_combination_exponent_selects_sum_and_root_sum_square() -> None:
  density_kgpm3 = 1.
  radius_m = .1
  speed_mps = 20.
  pressure_Pa = 101325.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray((speed_mps, 0., 0.)),
      mass_flow_kgps=density_kgpm3 * pi * radius_m ** 2 * speed_mps,
      temperature_K=400.,
      static_pressure_Pa=pressure_Pa,
  )
  baseline = solveCurvedPlume(
      source=source,
      ambient_field=UniformAmbientField(AmbientState(
          velocity_mps=np.asarray((0., 6., 0.)),
          pressure_Pa=pressure_Pa,
          temperature_K=300.,
          density_kgpm3=density_kgpm3,
      )),
      entrainment_model=DevelopingShearForcedEntrainment(0.),
      thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3),
      options=CurvedPlumeOptions(max_arc_length_m=.1, number_of_stations=2),
  )
  station = baseline.stations[0]
  common = dict(
      shear_coefficient=.08,
      forced_coefficient=.4,
      initial_development_fraction=1.,
      development_length_m=1.,
  )
  summed = DevelopingShearForcedEntrainment(
      **common, combination_exponent=1.
  ).calculateComponents(arc_length_m=0., station=station, source=source)
  rss = DevelopingShearForcedEntrainment(
      **common, combination_exponent=2.
  ).calculateComponents(arc_length_m=0., station=station, source=source)
  expected_sum = summed.shear_mass_rate_kgpspm + summed.forced_mass_rate_kgpspm
  expected_rss = sqrt(
      rss.shear_mass_rate_kgpspm ** 2
      + rss.forced_mass_rate_kgpspm ** 2
  )
  assert_allclose(summed.total_mass_rate_kgpspm, expected_sum, rtol=1.e-14)
  assert_allclose(rss.total_mass_rate_kgpspm, expected_rss, rtol=1.e-14)
  assert rss.total_mass_rate_kgpspm < summed.total_mass_rate_kgpspm
####


def test_invalid_entrainment_parameters_are_rejected() -> None:
  invalid_arguments = (
      {'shear_coefficient': -1.},
      {'shear_coefficient': 0., 'forced_coefficient': -1.},
      {'shear_coefficient': 0., 'initial_development_fraction': 1.1},
      {'shear_coefficient': 0., 'development_length_m': 0.},
      {'shear_coefficient': 0., 'combination_exponent': .5},
  )
  for arguments in invalid_arguments:
    try:
      DevelopingShearForcedEntrainment(**arguments)
    except ValueError:
      pass
    else:
      raise AssertionError(f'Expected ValueError for {arguments}.')
    ####
  ####
####
