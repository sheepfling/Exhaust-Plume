"""Calorically-perfect gas equations backed by explicit immutable properties."""

from __future__ import annotations

from math import sqrt

from pydantic import ConfigDict

from exhaust_plume.models.gas.contracts import GasModelKind, GasPropertiesConfig, SpeciesMassFraction
from exhaust_plume.util.atmosphere.constants import MOLAR_MASS_DRY_AIR_kg
from exhaust_plume.util.physical_constants import R_GAS_CONSTANT


class CaloricallyPerfectGas(GasPropertiesConfig):
  """Constant-gamma gas with a canonical specific-gas-constant derivation."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  @classmethod
  def dry_air(cls, *, gamma: float = 1.4) -> CaloricallyPerfectGas:
    """Construct the explicit legacy dry-air compatibility gas."""

    return cls(
        gamma=gamma,
        molar_mass_kg_per_mol=MOLAR_MASS_DRY_AIR_kg,
        species_mass_fractions=(SpeciesMassFraction(species='dry-air', mass_fraction=1.0),),
        model_kind=GasModelKind.CALORICALLY_PERFECT,
    )
  ####

  @property
  def specific_gas_constant_JpkgK(self) -> float:
    """Return R = R_u / molecular mass in J/(kg K)."""

    return R_GAS_CONSTANT / self.molar_mass_kg_per_mol
  ####

  @property
  def specific_heat_pressure_JpkgK(self) -> float:
    """Return c_p = gamma R / (gamma - 1)."""

    return self.gamma * self.specific_gas_constant_JpkgK / (self.gamma - 1.0)
  ####

  @property
  def specific_heat_volume_JpkgK(self) -> float:
    """Return c_v = R / (gamma - 1)."""

    return self.specific_gas_constant_JpkgK / (self.gamma - 1.0)
  ####

  def density_from_pressure_temperature(self, pressure_Pa: float, temperature_K: float) -> float:
    """Evaluate rho = p/(R T) for a positive static state."""

    if pressure_Pa <= 0.0 or temperature_K <= 0.0:
      raise ValueError('pressure_Pa and temperature_K must be positive')
    return pressure_Pa / (self.specific_gas_constant_JpkgK * temperature_K)
  ####

  def sound_speed_mps(self, temperature_K: float) -> float:
    """Evaluate a = sqrt(gamma R T)."""

    if temperature_K <= 0.0:
      raise ValueError('temperature_K must be positive')
    return sqrt(self.gamma * self.specific_gas_constant_JpkgK * temperature_K)
  ####

  def velocity_mps(self, mach: float, temperature_K: float) -> float:
    """Evaluate u = M sqrt(gamma R T)."""

    if mach <= 0.0:
      raise ValueError('mach must be positive')
    return mach * self.sound_speed_mps(temperature_K)
  ####

  def static_temperature_from_total(self, mach: float, total_temperature_K: float) -> float:
    """Evaluate the constant-gamma stagnation-temperature relation."""

    if mach < 0.0 or total_temperature_K <= 0.0:
      raise ValueError('mach must be nonnegative and total_temperature_K positive')
    return total_temperature_K / (1.0 + (self.gamma - 1.0) * mach**2 / 2.0)
  ####

  def total_temperature_from_static(self, mach: float, static_temperature_K: float) -> float:
    """Recover total temperature from a static state."""

    if mach < 0.0 or static_temperature_K <= 0.0:
      raise ValueError('mach must be nonnegative and static_temperature_K positive')
    return static_temperature_K * (1.0 + (self.gamma - 1.0) * mach**2 / 2.0)
  ####

  def static_pressure_from_total(self, mach: float, total_pressure_Pa: float) -> float:
    """Evaluate the constant-gamma stagnation-pressure relation."""

    if mach < 0.0 or total_pressure_Pa <= 0.0:
      raise ValueError('mach must be nonnegative and total_pressure_Pa positive')
    factor = 1.0 + (self.gamma - 1.0) * mach**2 / 2.0
    return total_pressure_Pa / factor**(self.gamma / (self.gamma - 1.0))
  ####

  def total_pressure_from_static(self, mach: float, static_pressure_Pa: float) -> float:
    """Recover total pressure from a static state."""

    if mach < 0.0 or static_pressure_Pa <= 0.0:
      raise ValueError('mach must be nonnegative and static_pressure_Pa positive')
    factor = 1.0 + (self.gamma - 1.0) * mach**2 / 2.0
    return static_pressure_Pa * factor**(self.gamma / (self.gamma - 1.0))
  ####
####
