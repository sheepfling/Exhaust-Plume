"""CHEM-0 frozen-mixture properties with explicit species provenance."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exhaust_plume.models.gas.contracts import GasModelKind, SpeciesMassFraction
from exhaust_plume.util.physical_constants import R_GAS_CONSTANT


class SpecificHeatTable(BaseModel):
  """Piecewise-linear positive ``c_p(T)`` data for one species."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  temperatures_K: tuple[float, ...] = Field(min_length=2)
  cp_JpkgK: tuple[float, ...] = Field(min_length=2)

  @model_validator(mode='after')
  def validate_table(self) -> SpecificHeatTable:
    if len(self.temperatures_K) != len(self.cp_JpkgK):
      raise ValueError('temperatures_K and cp_JpkgK must have matching lengths')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in self.temperatures_K):
      raise ValueError('temperatures_K must be finite and positive')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in self.cp_JpkgK):
      raise ValueError('cp_JpkgK must be finite and positive')
    ####
    if any(next_value <= value for value, next_value in zip(self.temperatures_K, self.temperatures_K[1:])):
      raise ValueError('temperatures_K must be strictly increasing')
    ####
    return self
  ####

  @property
  def temperature_range_K(self) -> tuple[float, float]:
    """Return the closed temperature interval covered by the table."""

    return self.temperatures_K[0], self.temperatures_K[-1]
  ####

  def evaluate(self, temperature_K: float) -> float:
    """Linearly interpolate ``c_p`` without extrapolating beyond the table."""

    _require_finite_positive('temperature_K', temperature_K)
    lower, upper = self.temperature_range_K
    if temperature_K < lower or temperature_K > upper:
      raise ValueError(f'temperature_K must be within [{lower}, {upper}]')
    ####
    for index, (left, right) in enumerate(zip(self.temperatures_K, self.temperatures_K[1:])):
      if temperature_K <= right:
        fraction = (temperature_K - left) / (right - left)
        return self.cp_JpkgK[index] + fraction * (self.cp_JpkgK[index + 1] - self.cp_JpkgK[index])
      ####
    ####
    return self.cp_JpkgK[-1]
  ####

  def enthalpy_increment_Jpkg(self, temperature_K: float, reference_temperature_K: float) -> float:
    """Integrate the tabulated heat capacity from a reference temperature."""

    _require_finite_positive('temperature_K', temperature_K)
    _require_finite_positive('reference_temperature_K', reference_temperature_K)
    lower, upper = self.temperature_range_K
    if not lower <= reference_temperature_K <= upper:
      raise ValueError(f'reference_temperature_K must be within [{lower}, {upper}]')
    ####
    if not lower <= temperature_K <= upper:
      raise ValueError(f'temperature_K must be within [{lower}, {upper}]')
    ####
    if temperature_K == reference_temperature_K:
      return 0.0
    ####
    sign = 1.0 if temperature_K > reference_temperature_K else -1.0
    start, end = sorted((temperature_K, reference_temperature_K))
    integral = 0.0
    for left, right in zip(self.temperatures_K, self.temperatures_K[1:]):
      segment_start = max(start, left)
      segment_end = min(end, right)
      if segment_end <= segment_start:
        continue
      ####
      cp_start = self.evaluate(segment_start)
      cp_end = self.evaluate(segment_end)
      integral += 0.5 * (cp_start + cp_end) * (segment_end - segment_start)
    ####
    return sign * integral
  ####
####


class SpeciesDefinition(BaseModel):
  """Explicit CHEM-0 species metadata and a constant or tabulated ``c_p``."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  species: str = Field(min_length=1)
  molecular_weight_kg_per_mol: float = Field(gt=0.0)
  cp_JpkgK: float | None = Field(default=None, gt=0.0)
  cp_table: SpecificHeatTable | None = None
  reference_temperature_K: float = Field(default=298.15, gt=0.0)
  formation_enthalpy_Jpkg: float = 0.0

  @model_validator(mode='after')
  def validate_heat_capacity(self) -> SpeciesDefinition:
    if (self.cp_JpkgK is None) == (self.cp_table is None):
      raise ValueError('provide exactly one of cp_JpkgK or cp_table')
    ####
    if self.cp_table is not None:
      lower, upper = self.cp_table.temperature_range_K
      if not lower <= self.reference_temperature_K <= upper:
        raise ValueError('reference_temperature_K must be covered by cp_table')
      ####
    ####
    return self
  ####

  def heat_capacity_JpkgK(self, temperature_K: float) -> float:
    """Evaluate this species' explicit heat-capacity model."""

    _require_finite_positive('temperature_K', temperature_K)
    if self.cp_table is not None:
      return self.cp_table.evaluate(temperature_K)
    ####
    assert self.cp_JpkgK is not None
    return self.cp_JpkgK
  ####

  def enthalpy_Jpkg(self, temperature_K: float) -> float:
    """Return formation plus sensible enthalpy relative to the reference."""

    _require_finite_positive('temperature_K', temperature_K)
    if self.cp_table is not None:
      sensible = self.cp_table.enthalpy_increment_Jpkg(temperature_K, self.reference_temperature_K)
    else:
      assert self.cp_JpkgK is not None
      sensible = self.cp_JpkgK * (temperature_K - self.reference_temperature_K)
    ####
    return self.formation_enthalpy_Jpkg + sensible
  ####
####


class SpeciesMoleFraction(BaseModel):
  """One explicitly named frozen species mole fraction."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  species: str = Field(min_length=1)
  mole_fraction: float = Field(ge=0.0, le=1.0)
####


def _require_finite_positive(name: str, value: float) -> None:
  if not isfinite(value) or value <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
####


def _validate_aligned_fractions(
    species: Sequence[SpeciesDefinition],
    fractions: Sequence[float],
    *,
    basis: str,
    normalization_tolerance: float,
) -> tuple[float, ...]:
  if not isfinite(normalization_tolerance) or normalization_tolerance <= 0.0:
    raise ValueError('normalization_tolerance must be finite and positive')
  ####
  if len(species) != len(fractions) or not species:
    raise ValueError(f'species and {basis} fractions must have matching nonzero lengths')
  ####
  values = tuple(float(value) for value in fractions)
  if any(not isfinite(value) or value < 0.0 for value in values):
    raise ValueError(f'{basis} fractions must be finite and nonnegative')
  ####
  total = sum(values)
  if abs(total - 1.0) > normalization_tolerance:
    raise ValueError(f'{basis} fractions must sum to one; got {total}')
  ####
  return values
####


def mass_fractions_to_mole_fractions(
    species: Sequence[SpeciesDefinition],
    mass_fractions: Sequence[float],
    *,
    normalization_tolerance: float = 1.0e-10,
) -> tuple[float, ...]:
  """Convert an aligned, normalized mass-fraction vector to mole fractions."""

  values = _validate_aligned_fractions(
      species,
      mass_fractions,
      basis='mass',
      normalization_tolerance=normalization_tolerance,
  )
  molar_amounts = tuple(value / item.molecular_weight_kg_per_mol for item, value in zip(species, values))
  total = sum(molar_amounts)
  return tuple(value / total for value in molar_amounts)
####


def mole_fractions_to_mass_fractions(
    species: Sequence[SpeciesDefinition],
    mole_fractions: Sequence[float],
    *,
    normalization_tolerance: float = 1.0e-10,
) -> tuple[float, ...]:
  """Convert an aligned, normalized mole-fraction vector to mass fractions."""

  values = _validate_aligned_fractions(
      species,
      mole_fractions,
      basis='mole',
      normalization_tolerance=normalization_tolerance,
  )
  mass_amounts = tuple(value * item.molecular_weight_kg_per_mol for item, value in zip(species, values))
  total = sum(mass_amounts)
  return tuple(value / total for value in mass_amounts)
####


class FrozenMixtureState(BaseModel):
  """A derived CHEM-0 state that retains the composition used to form it."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  mixture_id: str = Field(min_length=1)
  temperature_K: float = Field(gt=0.0)
  pressure_Pa: float = Field(gt=0.0)
  density_kg_per_m3: float = Field(gt=0.0)
  species_mass_fractions: tuple[SpeciesMassFraction, ...] = Field(min_length=1)
  species_mole_fractions: tuple[SpeciesMoleFraction, ...] = Field(min_length=1)
  molecular_weight_kg_per_mol: float = Field(gt=0.0)
  specific_gas_constant_JpkgK: float = Field(gt=0.0)
  cp_JpkgK: float = Field(gt=0.0)
  cv_JpkgK: float = Field(gt=0.0)
  gamma: float = Field(gt=1.0)
  specific_enthalpy_Jpkg: float
####


class FrozenMixtureGas(BaseModel):
  """CHEM-0 ideal-gas mixture with frozen composition and no reactions."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  mixture_id: str = Field(default='chem-0-explicit-frozen-mixture-v1', min_length=1)
  model_kind: GasModelKind = GasModelKind.FROZEN_MIXTURE
  species: tuple[SpeciesDefinition, ...] = Field(min_length=1)
  species_mass_fractions: tuple[SpeciesMassFraction, ...] = Field(min_length=1)
  valid_temperature_range_K: tuple[float, float] = (200.0, 6000.0)
  normalization_tolerance: float = Field(default=1.0e-10, gt=0.0)

  @model_validator(mode='after')
  def validate_mixture(self) -> FrozenMixtureGas:
    names = tuple(item.species for item in self.species)
    if len(names) != len(set(names)):
      raise ValueError('species definitions must not contain duplicate species')
    ####
    fraction_names = tuple(item.species for item in self.species_mass_fractions)
    if len(fraction_names) != len(set(fraction_names)):
      raise ValueError('species_mass_fractions must not contain duplicate species')
    ####
    if set(names) != set(fraction_names):
      raise ValueError('species definitions and mass fractions must name the same species')
    ####
    fraction_by_species = {
        item.species: item.mass_fraction
        for item in self.species_mass_fractions
    }
    values = tuple(fraction_by_species[item.species] for item in self.species)
    _validate_aligned_fractions(
        self.species,
        values,
        basis='mass',
        normalization_tolerance=self.normalization_tolerance,
    )
    lower, upper = self.valid_temperature_range_K
    if not isfinite(lower) or not isfinite(upper) or lower <= 0.0 or upper <= lower:
      raise ValueError('valid_temperature_range_K must be finite, positive, and increasing')
    ####
    for definition in self.species:
      if definition.cp_table is not None:
        table_lower, table_upper = definition.cp_table.temperature_range_K
        if lower < table_lower or upper > table_upper:
          raise ValueError('valid_temperature_range_K must be covered by every cp_table')
        ####
      ####
    ####
    return self
  ####

  @classmethod
  def from_mole_fractions(
      cls,
      *,
      species: Sequence[SpeciesDefinition],
      species_mole_fractions: Sequence[float],
      mixture_id: str = 'chem-0-explicit-frozen-mixture-v1',
      valid_temperature_range_K: tuple[float, float] = (200.0, 6000.0),
      normalization_tolerance: float = 1.0e-10,
  ) -> FrozenMixtureGas:
    """Construct the same explicit mixture from an aligned mole basis."""

    mass_fractions = mole_fractions_to_mass_fractions(
        species,
        species_mole_fractions,
        normalization_tolerance=normalization_tolerance,
    )
    return cls(
        mixture_id=mixture_id,
        model_kind=GasModelKind.FROZEN_MIXTURE,
        species=tuple(species),
        species_mass_fractions=tuple(
            SpeciesMassFraction(species=item.species, mass_fraction=value)
            for item, value in zip(species, mass_fractions)
        ),
        valid_temperature_range_K=valid_temperature_range_K,
        normalization_tolerance=normalization_tolerance,
    )
  ####

  @property
  def _mass_fraction_by_species(self) -> dict[str, float]:
    return {item.species: item.mass_fraction for item in self.species_mass_fractions}
  ####

  @property
  def molecular_weight_kg_per_mol(self) -> float:
    """Return the mixture molecular weight from the mass basis."""

    mass_fraction_by_species = self._mass_fraction_by_species
    reciprocal = sum(
        mass_fraction_by_species[item.species] / item.molecular_weight_kg_per_mol
        for item in self.species
    )
    return 1.0 / reciprocal
  ####

  @property
  def specific_gas_constant_JpkgK(self) -> float:
    """Return ``R_u / W̄`` in SI units."""

    return R_GAS_CONSTANT / self.molecular_weight_kg_per_mol
  ####

  @property
  def species_mole_fractions(self) -> tuple[SpeciesMoleFraction, ...]:
    """Return frozen mole fractions in the declared species order."""

    mass_fraction_by_species = self._mass_fraction_by_species
    values = mass_fractions_to_mole_fractions(
        self.species,
        tuple(mass_fraction_by_species[item.species] for item in self.species),
        normalization_tolerance=self.normalization_tolerance,
    )
    return tuple(
        SpeciesMoleFraction(species=item.species, mole_fraction=value)
        for item, value in zip(self.species, values)
    )
  ####

  def _check_temperature(self, temperature_K: float) -> None:
    _require_finite_positive('temperature_K', temperature_K)
    lower, upper = self.valid_temperature_range_K
    if temperature_K < lower or temperature_K > upper:
      raise ValueError(f'temperature_K must be within [{lower}, {upper}]')
    ####
  ####

  def cp_JpkgK(self, temperature_K: float) -> float:
    """Return mass-fraction-weighted ``c_p(T)``."""

    self._check_temperature(temperature_K)
    mass_fraction_by_species = self._mass_fraction_by_species
    return sum(
        mass_fraction_by_species[item.species] * item.heat_capacity_JpkgK(temperature_K)
        for item in self.species
    )
  ####

  def cv_JpkgK(self, temperature_K: float) -> float:
    """Return ``c_v = c_p - R`` and reject an invalid thermodynamic state."""

    value = self.cp_JpkgK(temperature_K) - self.specific_gas_constant_JpkgK
    if value <= 0.0:
      raise ValueError('mixture c_v must be positive')
    ####
    return value
  ####

  def gamma(self, temperature_K: float) -> float:
    """Return the temperature-dependent ``gamma = c_p / c_v``."""

    cp = self.cp_JpkgK(temperature_K)
    cv = self.cv_JpkgK(temperature_K)
    return cp / cv
  ####

  def specific_enthalpy_Jpkg(self, temperature_K: float) -> float:
    """Return the frozen-mixture mass-specific enthalpy."""

    self._check_temperature(temperature_K)
    mass_fraction_by_species = self._mass_fraction_by_species
    return sum(
        mass_fraction_by_species[item.species] * item.enthalpy_Jpkg(temperature_K)
        for item in self.species
    )
  ####

  def temperature_from_specific_enthalpy(
      self,
      specific_enthalpy_Jpkg: float,
      *,
      temperature_tolerance_K: float = 1.0e-8,
      max_iterations: int = 128,
  ) -> float:
    """Invert monotone frozen-mixture enthalpy by bounded bisection."""

    if not isfinite(specific_enthalpy_Jpkg):
      raise ValueError('specific_enthalpy_Jpkg must be finite')
    ####
    if not isfinite(temperature_tolerance_K) or temperature_tolerance_K <= 0.0:
      raise ValueError('temperature_tolerance_K must be finite and positive')
    ####
    if max_iterations < 1:
      raise ValueError('max_iterations must be positive')
    ####
    lower, upper = self.valid_temperature_range_K
    lower_enthalpy = self.specific_enthalpy_Jpkg(lower)
    upper_enthalpy = self.specific_enthalpy_Jpkg(upper)
    if specific_enthalpy_Jpkg < lower_enthalpy or specific_enthalpy_Jpkg > upper_enthalpy:
      raise ValueError('specific_enthalpy_Jpkg lies outside the valid temperature range')
    ####
    for _ in range(max_iterations):
      midpoint = 0.5 * (lower + upper)
      if upper - lower <= temperature_tolerance_K:
        return midpoint
      ####
      if self.specific_enthalpy_Jpkg(midpoint) < specific_enthalpy_Jpkg:
        lower = midpoint
      else:
        upper = midpoint
      ####
    ####
    return 0.5 * (lower + upper)
  ####

  def density_from_pressure_temperature(self, pressure_Pa: float, temperature_K: float) -> float:
    """Return ideal-gas density for a positive pressure and valid temperature."""

    _require_finite_positive('pressure_Pa', pressure_Pa)
    self._check_temperature(temperature_K)
    return pressure_Pa / (self.specific_gas_constant_JpkgK * temperature_K)
  ####

  def sound_speed_mps(self, temperature_K: float) -> float:
    """Return ``sqrt(gamma(T) R T)`` for the frozen mixture."""

    self._check_temperature(temperature_K)
    return (self.gamma(temperature_K) * self.specific_gas_constant_JpkgK * temperature_K) ** 0.5
  ####

  def state_at(self, pressure_Pa: float, temperature_K: float) -> FrozenMixtureState:
    """Derive and retain one complete CHEM-0 thermodynamic state."""

    density = self.density_from_pressure_temperature(pressure_Pa, temperature_K)
    cp = self.cp_JpkgK(temperature_K)
    cv = self.cv_JpkgK(temperature_K)
    return FrozenMixtureState(
        mixture_id=self.mixture_id,
        temperature_K=temperature_K,
        pressure_Pa=pressure_Pa,
        density_kg_per_m3=density,
        species_mass_fractions=self.species_mass_fractions,
        species_mole_fractions=self.species_mole_fractions,
        molecular_weight_kg_per_mol=self.molecular_weight_kg_per_mol,
        specific_gas_constant_JpkgK=self.specific_gas_constant_JpkgK,
        cp_JpkgK=cp,
        cv_JpkgK=cv,
        gamma=cp / cv,
        specific_enthalpy_Jpkg=self.specific_enthalpy_Jpkg(temperature_K),
    )
  ####

  def as_report(self) -> dict[str, object]:
    """Return explicit provenance and claim-ceiling metadata."""

    return {
        'mixture_id': self.mixture_id,
        'model_kind': self.model_kind.value,
        'thermochemistry_model': 'chem-0-explicit-frozen-mixture-v1',
        'reactions_enabled': False,
        'species': tuple(item.species for item in self.species),
        'species_mass_fractions': tuple(
            (item.species, item.mass_fraction) for item in self.species_mass_fractions
        ),
        'species_mole_fractions': tuple(
            (item.species, item.mole_fraction) for item in self.species_mole_fractions
        ),
        'molecular_weight_kg_per_mol': self.molecular_weight_kg_per_mol,
        'valid_temperature_range_K': self.valid_temperature_range_K,
        'claim_ceiling': 'research-only thermochemical source primitive; no reactions or external validation',
        'production_claim_allowed': False,
    }
  ####
####


__all__ = (
    'FrozenMixtureGas',
    'FrozenMixtureState',
    'SpecificHeatTable',
    'SpeciesDefinition',
    'SpeciesMoleFraction',
    'mass_fractions_to_mole_fractions',
    'mole_fractions_to_mass_fractions',
)
