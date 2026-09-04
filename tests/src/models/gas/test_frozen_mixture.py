from __future__ import annotations

import pytest
from pydantic import ValidationError

from exhaust_plume.models.gas import (
  FrozenMixtureGas,
  SpecificHeatTable,
  SpeciesDefinition,
  SpeciesMassFraction,
  mass_fractions_to_mole_fractions,
  mole_fractions_to_mass_fractions,
)


def _constant_species() -> tuple[SpeciesDefinition, ...]:
  return (
      SpeciesDefinition(
          species='nitrogen',
          molecular_weight_kg_per_mol=0.0280134,
          cp_JpkgK=1040.0,
      ),
      SpeciesDefinition(
          species='oxygen',
          molecular_weight_kg_per_mol=0.0319988,
          cp_JpkgK=918.0,
      ),
  )
####


def _mass_fractions() -> tuple[SpeciesMassFraction, ...]:
  return (
      SpeciesMassFraction(species='nitrogen', mass_fraction=0.7),
      SpeciesMassFraction(species='oxygen', mass_fraction=0.3),
  )
####


def test_composition_conversions_round_trip_and_match_molecular_weight() -> None:
  species = _constant_species()
  mass = tuple(item.mass_fraction for item in _mass_fractions())
  mole = mass_fractions_to_mole_fractions(species, mass)
  recovered_mass = mole_fractions_to_mass_fractions(species, mole)

  expected_molecular_weight = 1.0 / sum(
      value / definition.molecular_weight_kg_per_mol
      for definition, value in zip(species, mass)
  )
  mole_basis_molecular_weight = sum(
      value * definition.molecular_weight_kg_per_mol
      for definition, value in zip(species, mole)
  )

  assert sum(mole) == pytest.approx(1.0)
  assert recovered_mass == pytest.approx(mass)
  assert mole_basis_molecular_weight == pytest.approx(expected_molecular_weight)
####


def test_constant_cp_frozen_mixture_derives_thermodynamic_state() -> None:
  mixture = FrozenMixtureGas(
      species=_constant_species(),
      species_mass_fractions=_mass_fractions(),
      valid_temperature_range_K=(250.0, 2000.0),
  )
  temperature = 1200.0
  pressure = 180000.0
  cp = 0.7 * 1040.0 + 0.3 * 918.0
  enthalpy = mixture.specific_enthalpy_Jpkg(temperature)
  state = mixture.state_at(pressure, temperature)

  assert mixture.cp_JpkgK(temperature) == pytest.approx(cp)
  assert mixture.cv_JpkgK(temperature) == pytest.approx(cp - mixture.specific_gas_constant_JpkgK)
  assert mixture.gamma(temperature) == pytest.approx(cp / (cp - mixture.specific_gas_constant_JpkgK))
  assert mixture.temperature_from_specific_enthalpy(enthalpy) == pytest.approx(temperature, abs=1.0e-7)
  assert state.density_kg_per_m3 == pytest.approx(
      pressure / (mixture.specific_gas_constant_JpkgK * temperature)
  )
  assert state.species_mole_fractions == mixture.species_mole_fractions
  assert state.specific_enthalpy_Jpkg == pytest.approx(enthalpy)
  assert state.gamma == pytest.approx(mixture.gamma(temperature))
####


def test_tabulated_cp_is_interpolated_integrated_and_invertible() -> None:
  table = SpecificHeatTable(
      temperatures_K=(300.0, 1000.0, 2000.0),
      cp_JpkgK=(900.0, 1100.0, 1500.0),
  )
  species = SpeciesDefinition(
      species='test-gas',
      molecular_weight_kg_per_mol=0.020,
      cp_table=table,
      reference_temperature_K=300.0,
  )
  mixture = FrozenMixtureGas(
      species=(species,),
      species_mass_fractions=(SpeciesMassFraction(species='test-gas', mass_fraction=1.0),),
      valid_temperature_range_K=(300.0, 2000.0),
  )
  temperature = 1400.0
  expected_enthalpy = 0.5 * (900.0 + 1100.0) * 700.0 + 0.5 * (1100.0 + 1260.0) * 400.0

  assert table.evaluate(1400.0) == pytest.approx(1260.0)
  assert mixture.cp_JpkgK(temperature) == pytest.approx(1260.0)
  assert mixture.specific_enthalpy_Jpkg(temperature) == pytest.approx(expected_enthalpy)
  assert mixture.temperature_from_specific_enthalpy(expected_enthalpy) == pytest.approx(temperature, abs=1.0e-7)
####


def test_frozen_mixture_rejects_ambiguous_or_out_of_range_inputs() -> None:
  species = _constant_species()
  with pytest.raises(ValueError, match='exactly one'):
    SpeciesDefinition(
        species='ambiguous',
        molecular_weight_kg_per_mol=0.02,
        cp_JpkgK=1000.0,
        cp_table=SpecificHeatTable(temperatures_K=(300.0, 1000.0), cp_JpkgK=(900.0, 1100.0)),
    )
  ####
  with pytest.raises(ValueError, match='must sum to one'):
    mass_fractions_to_mole_fractions(species, (0.6, 0.3))
  ####
  with pytest.raises(ValidationError, match='same species'):
    FrozenMixtureGas(
        species=species,
        species_mass_fractions=(
            SpeciesMassFraction(species='nitrogen', mass_fraction=0.7),
            SpeciesMassFraction(species='argon', mass_fraction=0.3),
        ),
    )
  ####
  mixture = FrozenMixtureGas(
      species=species,
      species_mass_fractions=_mass_fractions(),
      valid_temperature_range_K=(250.0, 2000.0),
  )
  with pytest.raises(ValueError, match='within'):
    mixture.cp_JpkgK(240.0)
  ####
  with pytest.raises(ValueError, match='outside'):
    mixture.temperature_from_specific_enthalpy(-1.0e9)
  ####
####


def test_mole_basis_constructor_retains_explicit_chem0_report() -> None:
  mixture = FrozenMixtureGas.from_mole_fractions(
      species=_constant_species(),
      species_mole_fractions=(0.5, 0.5),
      mixture_id='test-chem0-mixture',
      valid_temperature_range_K=(250.0, 2000.0),
  )
  report = mixture.as_report()

  assert mixture.mixture_id == 'test-chem0-mixture'
  assert report['thermochemistry_model'] == 'chem-0-explicit-frozen-mixture-v1'
  assert report['reactions_enabled'] is False
  assert report['production_claim_allowed'] is False
  assert tuple(item.species for item in mixture.species_mole_fractions) == ('nitrogen', 'oxygen')
  assert tuple(item.mole_fraction for item in mixture.species_mole_fractions) == pytest.approx((0.5, 0.5))
####
