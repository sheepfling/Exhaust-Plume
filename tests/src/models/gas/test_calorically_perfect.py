from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from exhaust_plume.models.gas import CaloricallyPerfectGas, FrozenMixtureConfig, SpeciesMassFraction
from exhaust_plume.util.physical_constants import R_GAS_CONSTANT


def test_specific_gas_constant_is_derived_from_molar_mass() -> None:
  gas = CaloricallyPerfectGas(gamma=1.33, molar_mass_kg_per_mol=0.022)
  assert gas.specific_gas_constant_JpkgK == pytest.approx(R_GAS_CONSTANT / 0.022)
####


def test_molar_mass_changes_density_and_sound_speed_consistently() -> None:
  light = CaloricallyPerfectGas(gamma=1.4, molar_mass_kg_per_mol=0.020)
  heavy = CaloricallyPerfectGas(gamma=1.4, molar_mass_kg_per_mol=0.040)
  light_density = light.density_from_pressure_temperature(100000.0, 1000.0)
  heavy_density = heavy.density_from_pressure_temperature(100000.0, 1000.0)
  assert light_density / heavy_density == pytest.approx(heavy.specific_gas_constant_JpkgK / light.specific_gas_constant_JpkgK)
  assert light.sound_speed_mps(1000.0) > heavy.sound_speed_mps(1000.0)
####


def test_static_total_round_trip_and_velocity_equation() -> None:
  gas = CaloricallyPerfectGas(gamma=1.33, molar_mass_kg_per_mol=0.028)
  mach = 3.2
  total_temperature = 1800.0
  total_pressure = 2.5e6
  static_temperature = gas.static_temperature_from_total(mach, total_temperature)
  static_pressure = gas.static_pressure_from_total(mach, total_pressure)
  assert gas.total_temperature_from_static(mach, static_temperature) == pytest.approx(total_temperature)
  assert gas.total_pressure_from_static(mach, static_pressure) == pytest.approx(total_pressure)
  assert gas.velocity_mps(mach, static_temperature) == pytest.approx(
      mach * math.sqrt(gas.gamma * gas.specific_gas_constant_JpkgK * static_temperature)
  )
####


def test_invalid_gas_and_state_values_are_rejected() -> None:
  with pytest.raises(ValueError):
    CaloricallyPerfectGas(gamma=1.0, molar_mass_kg_per_mol=0.028)
  ####
  with pytest.raises(ValueError):
    CaloricallyPerfectGas(gamma=1.33, molar_mass_kg_per_mol=0.0)
  ####
  gas = CaloricallyPerfectGas(gamma=1.33, molar_mass_kg_per_mol=0.028)
  with pytest.raises(ValueError):
    gas.density_from_pressure_temperature(0.0, 300.0)
  ####
  with pytest.raises(ValueError):
    gas.sound_speed_mps(0.0)
  ####
  with pytest.raises(ValueError):
    gas.velocity_mps(0.0, 300.0)
  ####
####


def test_mixture_rejects_duplicates_and_non_normalized_fractions() -> None:
  with pytest.raises(ValidationError):
    FrozenMixtureConfig(species_mass_fractions=(
        SpeciesMassFraction(species='a', mass_fraction=0.5),
        SpeciesMassFraction(species='a', mass_fraction=0.5),
    ))
  ####
  with pytest.raises(ValidationError):
    FrozenMixtureConfig(species_mass_fractions=(SpeciesMassFraction(species='a', mass_fraction=0.4),))
  ####
####


def test_new_gas_objects_are_immutable() -> None:
  gas = CaloricallyPerfectGas(gamma=1.33, molar_mass_kg_per_mol=0.028)
  with pytest.raises(ValidationError):
    gas.gamma = 1.4
  ####
####
