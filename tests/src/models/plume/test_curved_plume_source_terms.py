from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.testing import assert_allclose

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


@dataclass(frozen=True)
class ConstantSourceTermModel:
  force_Npm: np.ndarray
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


def test_constant_external_source_terms_integrate_exactly() -> None:
  pressure_Pa = 101325.
  density_kgpm3 = 1.2
  specific_heat_JpkgK = 1000.
  source = CurvedPlumeSource(
      position_m=np.zeros(3),
      velocity_mps=np.asarray([30., 0., 0.]),
      mass_flow_kgps=2.,
      temperature_K=500.,
      static_pressure_Pa=pressure_Pa,
      specific_heat_JpkgK=specific_heat_JpkgK,
  )
  ambient = UniformAmbientField(AmbientState(
      velocity_mps=np.zeros(3),
      pressure_Pa=pressure_Pa,
      temperature_K=300.,
      density_kgpm3=density_kgpm3,
      specific_heat_JpkgK=specific_heat_JpkgK,
  ))
  force_Npm = np.asarray([0., 3., 0.])
  energy_source_Wpm = 50.
  result = solveCurvedPlume(
      source=source,
      ambient_field=ambient,
      entrainment_model=ConstantEntrainment(0.),
      source_term_model=ConstantSourceTermModel(
          force_Npm=force_Npm,
          energy_source_Wpm=energy_source_Wpm,
      ),
      thermodynamics=ConstantDensityMixtureThermodynamics(density_kgpm3),
      options=CurvedPlumeOptions(
          max_arc_length_m=4.,
          number_of_stations=81,
          relative_tolerance=1.e-11,
          absolute_tolerance=1.e-13,
          max_step_m=.02,
      ),
  )

  arc_lengths_m = result.arc_lengths_m
  initial_momentum_N = source.mass_flow_kgps * source.velocity_mps
  initial_energy_W = source.mass_flow_kgps * (
      source.specific_heat_JpkgK * source.temperature_K
      + .5 * float(source.velocity_mps @ source.velocity_mps)
  )
  expected_momentum_N = initial_momentum_N + arc_lengths_m[:, None] * force_Npm
  expected_energy_W = initial_energy_W + arc_lengths_m * energy_source_Wpm

  assert_allclose(
      [station.momentum_flux_N for station in result.stations],
      expected_momentum_N,
      rtol=2.e-11,
      atol=2.e-11,
  )
  assert_allclose(
      [station.total_energy_flow_W for station in result.stations],
      expected_energy_W,
      rtol=2.e-11,
      atol=2.e-8,
  )
  assert_allclose(result.stations[0].momentum_derivative_Npm, force_Npm, rtol=0., atol=1.e-13)
  assert_allclose(
      result.stations[0].curvature_per_m,
      np.linalg.norm(force_Npm) / np.linalg.norm(initial_momentum_N),
      rtol=1.e-12,
  )
####
