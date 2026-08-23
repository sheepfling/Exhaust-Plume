from __future__ import annotations

import pytest
from pydantic import ValidationError

from exhaust_plume import calcNozzleExitFlowState
from exhaust_plume.models.gas import CaloricallyPerfectGas, SpeciesMassFraction
from exhaust_plume.models.nozzle import (
    AmbientInput,
    NozzleExitInput,
    derive_ambient_state,
    derive_uniform_nozzle_exit,
)
from exhaust_plume.util.physical_constants import PASCAL_PER_ATM


def test_uniform_nozzle_exit_derives_static_state_and_mass_flow() -> None:
  gas = CaloricallyPerfectGas(
      gamma=1.33,
      molar_mass_kg_per_mol=0.022,
      species_mass_fractions=(SpeciesMassFraction(species='test-gas', mass_fraction=1.0),),
  )
  config = NozzleExitInput(
      mach=3.0,
      total_pressure_Pa=20.0 * PASCAL_PER_ATM,
      total_temperature_K=1600.0,
      exit_radius_m=0.4,
  )
  state = derive_uniform_nozzle_exit(config, gas)
  assert state.static_pressure_Pa < config.total_pressure_Pa
  assert state.static_temperature_K < config.total_temperature_K
  assert state.density_kgpm3 == pytest.approx(
      state.static_pressure_Pa / (gas.specific_gas_constant_JpkgK * state.static_temperature_K)
  )
  assert state.axial_velocity_mps == pytest.approx(state.velocity_mps)
  assert state.mass_flow_rate_kgps == pytest.approx(
      state.density_kgpm3 * state.axial_velocity_mps * state.area_m2
  )
  ####
####


def test_supplied_mass_flow_must_match_derived_value() -> None:
  gas = CaloricallyPerfectGas(gamma=1.33, molar_mass_kg_per_mol=0.022)
  base = NozzleExitInput(mach=2.5, total_pressure_Pa=2.0e6, total_temperature_K=1200.0, exit_radius_m=0.2)
  derived = derive_uniform_nozzle_exit(base, gas)
  matched = base.model_copy(update={'mass_flow_rate_kg_per_s': derived.mass_flow_rate_kgps})
  assert derive_uniform_nozzle_exit(matched, gas).mass_flow_rate_kgps == pytest.approx(derived.mass_flow_rate_kgps)
  with pytest.raises(ValueError):
    derive_uniform_nozzle_exit(base.model_copy(update={'mass_flow_rate_kg_per_s': 1.0}), gas)
  ####
####


def test_nozzle_input_rejects_non_supersonic_or_nonpositive_values() -> None:
  with pytest.raises(ValidationError):
    NozzleExitInput(mach=1.0, total_pressure_Pa=1.0e5, total_temperature_K=300.0, exit_radius_m=0.1)
  with pytest.raises(ValidationError):
    NozzleExitInput(mach=2.0, total_pressure_Pa=0.0, total_temperature_K=300.0, exit_radius_m=0.1)
  ####
####


def test_ambient_state_uses_explicit_gas_and_retains_altitude_metadata() -> None:
  gas = CaloricallyPerfectGas(
      gamma=1.4,
      molar_mass_kg_per_mol=0.030,
      species_mass_fractions=(SpeciesMassFraction(species='ambient-gas', mass_fraction=1.0),),
  )
  state = derive_ambient_state(AmbientInput(
      pressure_Pa=90000.0,
      temperature_K=280.0,
      velocity_x_m_per_s=12.0,
      geopotential_altitude_m=1000.0,
  ), gas)
  assert state.density_kgpm3 == pytest.approx(90000.0 / (gas.specific_gas_constant_JpkgK * 280.0))
  assert state.velocity_xyz_mps == (12.0, 0.0, 0.0)
  assert state.geopotential_altitude_m == 1000.0
  assert state.species_mass_fractions == gas.species_mass_fractions
  ####
####


def test_legacy_nozzle_wrapper_matches_explicit_dry_air_contract() -> None:
  mach = 4.13
  total_temperature = 2000.0
  total_pressure = 69.0 * PASCAL_PER_ATM
  gamma = 1.33
  legacy = calcNozzleExitFlowState(mach, total_temperature, total_pressure, gamma)
  explicit = derive_uniform_nozzle_exit(
      NozzleExitInput(
          mach=mach,
          total_temperature_K=total_temperature,
          total_pressure_Pa=total_pressure,
          exit_radius_m=1.0,
      ),
      CaloricallyPerfectGas.dry_air(gamma=gamma),
  )
  assert legacy.static_pressure == pytest.approx(explicit.static_pressure_Pa)
  assert legacy.static_temperature == pytest.approx(explicit.static_temperature_K)
  assert legacy.static_density == pytest.approx(explicit.density_kgpm3)
  ####
####
