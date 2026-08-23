"""Immutable configuration contracts for calorically-perfect gases."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GasModelKind(str, Enum):
  CALORICALLY_PERFECT = 'calorically-perfect'
  ####


class SpeciesMassFraction(BaseModel):
  """One explicitly named frozen species mass fraction."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  species: str = Field(min_length=1)
  mass_fraction: float = Field(ge=0.0, le=1.0)
  ####


class FrozenMixtureConfig(BaseModel):
  """Frozen species fractions; invalid sums are rejected, not normalized."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  species_mass_fractions: tuple[SpeciesMassFraction, ...] = ()
  normalization_tolerance: float = Field(default=1.0e-10, gt=0.0)

  @model_validator(mode='after')
  def validate_species(self) -> FrozenMixtureConfig:
    names = tuple(item.species for item in self.species_mass_fractions)
    if len(names) != len(set(names)):
      raise ValueError('species_mass_fractions must not contain duplicate species')
    if self.species_mass_fractions:
      total = sum(item.mass_fraction for item in self.species_mass_fractions)
      if abs(total - 1.0) > self.normalization_tolerance:
        raise ValueError(f'species mass fractions must sum to one; got {total}')
    return self
  ####
####


class GasPropertiesConfig(BaseModel):
  """Serialized gas configuration with no implicit dry-air values."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  gamma: float = Field(gt=1.0)
  molar_mass_kg_per_mol: float = Field(gt=0.0)
  species_mass_fractions: tuple[SpeciesMassFraction, ...] = ()
  model_kind: GasModelKind = GasModelKind.CALORICALLY_PERFECT

  @model_validator(mode='after')
  def validate_species(self) -> GasPropertiesConfig:
    FrozenMixtureConfig(species_mass_fractions=self.species_mass_fractions)
    return self
  ####
####


GasProperties = GasPropertiesConfig
####
