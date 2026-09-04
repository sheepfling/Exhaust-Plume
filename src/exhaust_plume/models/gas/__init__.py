"""Explicit gas-property contracts for plume state construction."""

from __future__ import annotations

from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.gas.contracts import (
  FrozenMixtureConfig,
  GasModelKind,
  GasProperties,
  GasPropertiesConfig,
  SpeciesMassFraction,
)
from exhaust_plume.models.gas.frozen_mixture import (
  FrozenMixtureGas,
  FrozenMixtureState,
  SpecificHeatTable,
  SpeciesDefinition,
  SpeciesMoleFraction,
  mass_fractions_to_mole_fractions,
  mole_fractions_to_mass_fractions,
)

__all__ = (
  'CaloricallyPerfectGas',
  'FrozenMixtureConfig',
  'FrozenMixtureGas',
  'FrozenMixtureState',
  'GasModelKind',
  'GasProperties',
  'GasPropertiesConfig',
  'SpecificHeatTable',
  'SpeciesDefinition',
  'SpeciesMassFraction',
  'SpeciesMoleFraction',
  'mass_fractions_to_mole_fractions',
  'mole_fractions_to_mass_fractions',
)
