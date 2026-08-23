"""Immutable nozzle-exit and ambient-state contracts."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.gas.contracts import SpeciesMassFraction


class NozzleStateSourceKind(str, Enum):
  DIRECT_UNIFORM_EXIT = 'direct-uniform-exit'
  DERIVED_ISENTROPIC = 'derived-isentropic'
  CEA_FROZEN = 'cea-frozen'
  CEA_EQUILIBRIUM = 'cea-equilibrium'
  PROFILED_EXIT = 'profiled-exit'
####


class NozzleExitInput(BaseModel):
  """Total nozzle conditions plus explicit geometric and flow inputs."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  mach: float = Field(gt=1.0)
  total_pressure_Pa: float = Field(gt=0.0)
  total_temperature_K: float = Field(gt=0.0)
  exit_radius_m: float = Field(gt=0.0)
  flow_angle_rad: float = 0.0
  mass_flow_rate_kg_per_s: float | None = Field(default=None, gt=0.0)
  exit_profile_id: str | None = None
  nozzle_solution_validated: bool = False
####


class NozzleExitState(BaseModel):
  """Uniform exit state with static and total quantities in SI units."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  static_pressure_Pa: float = Field(gt=0.0)
  static_temperature_K: float = Field(gt=0.0)
  mach: float = Field(gt=1.0)
  density_kgpm3: float = Field(gt=0.0)
  axial_velocity_mps: float = Field(gt=0.0)
  flow_angle_rad: float
  radius_m: float = Field(gt=0.0)
  mass_flow_rate_kgps: float = Field(gt=0.0)
  total_pressure_Pa: float = Field(gt=0.0)
  total_temperature_K: float = Field(gt=0.0)
  gas: CaloricallyPerfectGas
  species_mass_fractions: tuple[SpeciesMassFraction, ...] = ()
  source_kind: NozzleStateSourceKind = NozzleStateSourceKind.DERIVED_ISENTROPIC

  @model_validator(mode='after')
  def validate_species(self) -> NozzleExitState:
    if self.species_mass_fractions != self.gas.species_mass_fractions:
      raise ValueError('state species_mass_fractions must match gas species_mass_fractions')
    ####
    return self
  ####

  @property
  def area_m2(self) -> float:
    """Return circular exit area."""

    from math import pi
    return pi * self.radius_m**2
  ####

  @property
  def speed_of_sound_mps(self) -> float:
    """Return local speed of sound from the explicit gas model."""

    return self.gas.sound_speed_mps(self.static_temperature_K)
  ####

  @property
  def velocity_mps(self) -> float:
    """Return velocity magnitude from Mach and local sound speed."""

    return self.gas.velocity_mps(self.mach, self.static_temperature_K)
  ####
####


class AmbientInput(BaseModel):
  """Resolved ambient inputs; altitude is metadata, not a hidden state solve."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  pressure_Pa: float = Field(gt=0.0)
  temperature_K: float = Field(gt=0.0)
  velocity_x_m_per_s: float = 0.0
  velocity_y_m_per_s: float = 0.0
  velocity_z_m_per_s: float = 0.0
  species_mass_fractions: tuple[SpeciesMassFraction, ...] = ()
  geopotential_altitude_m: float | None = None
####


class AmbientState(BaseModel):
  """Static ambient state used by the core solver."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  pressure_Pa: float = Field(gt=0.0)
  temperature_K: float = Field(gt=0.0)
  density_kgpm3: float = Field(gt=0.0)
  velocity_xyz_mps: tuple[float, float, float]
  species_mass_fractions: tuple[SpeciesMassFraction, ...] = ()
  geopotential_altitude_m: float | None = None

  @model_validator(mode='after')
  def validate_velocity(self) -> AmbientState:
    if len(self.velocity_xyz_mps) != 3:
      raise ValueError('velocity_xyz_mps must have three components')
    ####
    return self
  ####
####
