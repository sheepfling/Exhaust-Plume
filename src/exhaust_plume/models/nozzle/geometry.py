"""Explicit quasi-one-dimensional nozzle geometry and exit-state derivation.

The active plume solver only supports an equivalent circular, calorically
perfect nozzle.  These contracts make that boundary explicit while still
allowing the throat area and throat-to-exit area ratio to vary in a controlled
study matrix.
"""

from __future__ import annotations

from enum import Enum
from math import isclose, pi, sqrt

from pydantic import BaseModel, ConfigDict, Field, model_validator

from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.nozzle.area_mach import MachBranch, calc_mass_flow_rate, solve_mach_from_area_ratio
from exhaust_plume.models.nozzle.contracts import NozzleExitInput, NozzleExitState
from exhaust_plume.models.nozzle.exit_state import derive_uniform_nozzle_exit

__all__ = (
  'NozzleGeometry',
  'NozzleGeometryFamily',
  'ThroatConfiguration',
  'ThroatShape',
  'derive_nozzle_exit_from_geometry',
)
###########################################


class ThroatShape(str, Enum):
  """Geometric families understood by the equivalent-area solver."""

  CIRCULAR = 'circular'
  ####
####


class NozzleGeometryFamily(str, Enum):
  """Supported geometry abstraction, not a resolved wall-profile model."""

  CIRCULAR_QUASI_1D = 'circular-quasi-1d'
  ####
####


class ThroatConfiguration(BaseModel):
  """One explicit sonic-throat configuration.

  ``profile_id`` is retained as provenance.  The current equations use only
  the effective area and do not resolve boundary-layer, radius, or discharge
  coefficient corrections.
  """

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  area_m2: float = Field(gt=0.0)
  shape: ThroatShape = ThroatShape.CIRCULAR
  profile_id: str = Field(default='ideal-circular-sonic-throat', min_length=1)
  ####

  @property
  def equivalent_radius_m(self) -> float:
    """Return the radius of a circular area with the configured throat area."""

    return sqrt(self.area_m2 / pi)
  ####
####


class NozzleGeometry(BaseModel):
  """Equivalent-area converging-diverging geometry for the active solver."""

  model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)

  geometry_id: str = Field(default='circular-quasi-1d', min_length=1)
  family: NozzleGeometryFamily = NozzleGeometryFamily.CIRCULAR_QUASI_1D
  throat: ThroatConfiguration
  exit_area_m2: float = Field(gt=0.0)
  exit_shape: ThroatShape = ThroatShape.CIRCULAR
  exit_profile_id: str = Field(default='ideal-circular-uniform-exit', min_length=1)

  @model_validator(mode='after')
  def validate_area_order(self) -> NozzleGeometry:
    if self.exit_area_m2 <= self.throat.area_m2:
      raise ValueError('exit_area_m2 must be greater than throat.area_m2 for a supersonic branch')
    if self.family is not NozzleGeometryFamily.CIRCULAR_QUASI_1D:
      raise ValueError(f'unsupported nozzle geometry family: {self.family.value}')
    if self.throat.shape is not ThroatShape.CIRCULAR or self.exit_shape is not ThroatShape.CIRCULAR:
      raise ValueError('the active nozzle solver supports circular equivalent-area sections only')
    return self
  ####

  @property
  def area_ratio(self) -> float:
    """Return the exit-to-throat area ratio ``A_e/A*``."""

    return self.exit_area_m2 / self.throat.area_m2
  ####

  @property
  def exit_radius_m(self) -> float:
    """Return the equivalent circular exit radius."""

    return sqrt(self.exit_area_m2 / pi)
  ####
####


def derive_nozzle_exit_from_geometry(
    geometry: NozzleGeometry,
    *,
    total_pressure_Pa: float,
    total_temperature_K: float,
    gas: CaloricallyPerfectGas,
    flow_angle_rad: float = 0.0,
    mass_flow_rate_kg_per_s: float | None = None,
    branch: MachBranch = MachBranch.SUPERSONIC,
) -> NozzleExitState:
  """Derive a uniform supersonic exit from an explicit area ratio.

  This is the one-dimensional isentropic throat/exit relation.  It checks the
  choked-throat mass-flow invariant against the derived exit state, so a
  geometry case cannot quietly use inconsistent throat and exit conditions.
  Wall contour, losses, separation, and non-circular shape corrections remain
  outside this function.
  """

  if not isclose(flow_angle_rad, 0.0, abs_tol=1.0e-12):
    raise ValueError('quasi-one-dimensional geometry derivation requires a zero exit flow angle')
  branch = MachBranch(branch)
  if branch is not MachBranch.SUPERSONIC:
    raise ValueError('the active nozzle geometry derivation requires the supersonic branch')
  mach = solve_mach_from_area_ratio(geometry.area_ratio, gas.gamma, branch)
  state = derive_uniform_nozzle_exit(
      NozzleExitInput(
          mach=mach,
          total_pressure_Pa=total_pressure_Pa,
          total_temperature_K=total_temperature_K,
          exit_radius_m=geometry.exit_radius_m,
          flow_angle_rad=flow_angle_rad,
          mass_flow_rate_kg_per_s=mass_flow_rate_kg_per_s,
          exit_profile_id=geometry.exit_profile_id,
          nozzle_solution_validated=True,
      ),
      gas,
  )
  choked_mass_flow_rate = calc_mass_flow_rate(
      area_m2=geometry.throat.area_m2,
      mach=1.0,
      total_pressure_Pa=total_pressure_Pa,
      total_temperature_K=total_temperature_K,
      gamma=gas.gamma,
      specific_gas_constant_JpkgK=gas.specific_gas_constant_JpkgK,
  )
  if not isclose(state.mass_flow_rate_kgps, choked_mass_flow_rate, rel_tol=2.0e-8, abs_tol=1.0e-12):
    raise ValueError(
        'derived exit mass flow is inconsistent with the configured choked throat: '
        f'exit={state.mass_flow_rate_kgps}, throat={choked_mass_flow_rate}'
    )
  return state
####
