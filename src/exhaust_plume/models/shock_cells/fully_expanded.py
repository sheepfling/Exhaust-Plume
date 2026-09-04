"""Equivalent fully-expanded jet properties for the reduced-order lane.

The equivalent state is an isentropic comparison state, not a downstream
shock-cell solution.  It is kept in its own module so a correlation check
cannot silently change the fidelity or topology of the basic straight solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, pi, sqrt

from exhaust_plume.models.nozzle.area_mach import calc_area_mach_ratio
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState, NozzleStateSourceKind

__all__ = (
  'FullyExpandedStatus',
  'FullyExpandedJetResult',
  'derive_fully_expanded_jet',
)


class FullyExpandedStatus(str, Enum):
  """Status of the isentropic equivalent fully-expanded construction."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  OUTSIDE_MODEL_VALIDITY = 'outside_model_validity'
####


@dataclass(frozen=True, slots=True)
class FullyExpandedJetResult:
  """Equivalent jet state at ``p_j = p_a``.

  ``first_cell_claim_allowed`` is false for matched flow.  A matched flow can
  still have a valid equivalent state, but it has no pressure mismatch that
  justifies a shock-cell correlation claim.
  """

  status: FullyExpandedStatus
  exit_state: NozzleExitState
  ambient_pressure_Pa: float
  mach: float | None
  static_pressure_Pa: float | None
  static_temperature_K: float | None
  density_kgpm3: float | None
  radius_m: float | None
  diameter_m: float | None
  area_ratio_to_exit: float | None
  state: NozzleExitState | None
  exit_pressure_residual: float | None
  first_cell_claim_allowed: bool
  message: str = ''

  @property
  def converged(self) -> bool:
    """Return whether the equivalent state was constructed."""

    return self.status is FullyExpandedStatus.CONVERGED
  ####
####


def _ambient_pressure(ambient: AmbientState | float) -> float:
  if isinstance(ambient, AmbientState):
    return float(ambient.pressure_Pa)
  ####
  return float(ambient)
####


def _failure(
  *,
  status: FullyExpandedStatus,
  exit_state: NozzleExitState,
  ambient_pressure_Pa: float,
  message: str,
) -> FullyExpandedJetResult:
  return FullyExpandedJetResult(
    status=status,
    exit_state=exit_state,
    ambient_pressure_Pa=ambient_pressure_Pa,
    mach=None,
    static_pressure_Pa=None,
    static_temperature_K=None,
    density_kgpm3=None,
    radius_m=None,
    diameter_m=None,
    area_ratio_to_exit=None,
    state=None,
    exit_pressure_residual=None,
    first_cell_claim_allowed=False,
    message=message,
  )
####


def derive_fully_expanded_jet(
  exit_state: NozzleExitState,
  ambient: AmbientState | float,
  *,
  pressure_match_rtol: float = 1.0e-4,
) -> FullyExpandedJetResult:
  r"""Construct the isentropic equivalent state with ``p_j = p_a``.

  The construction uses

  ``M_j² = 2/(gamma-1) * ((p0/pa)**((gamma-1)/gamma) - 1)``

  and the area--Mach ratio to obtain the equivalent diameter.  It requires a
  supersonic equivalent state (``M_j > 1``); cases that would require a
  subsonic or sonic equivalent state are reported outside the model validity
  envelope rather than being forced through ``NozzleExitState``.
  """

  ambient_pressure_Pa = _ambient_pressure(ambient)
  if not isfinite(ambient_pressure_Pa) or ambient_pressure_Pa <= 0.0:
    return _failure(
      status=FullyExpandedStatus.INVALID_INPUT,
      exit_state=exit_state,
      ambient_pressure_Pa=ambient_pressure_Pa,
      message='ambient pressure must be finite and positive',
    )
  ####
  if not isfinite(pressure_match_rtol) or pressure_match_rtol <= 0.0:
    raise ValueError('pressure_match_rtol must be finite and positive')
  ####

  gamma = float(exit_state.gas.gamma)
  total_pressure_ratio = float(exit_state.total_pressure_Pa) / ambient_pressure_Pa
  if total_pressure_ratio <= 1.0:
    return _failure(
      status=FullyExpandedStatus.OUTSIDE_MODEL_VALIDITY,
      exit_state=exit_state,
      ambient_pressure_Pa=ambient_pressure_Pa,
      message='total-to-ambient pressure ratio does not define a supersonic equivalent state',
    )
  ####

  mach_squared = 2.0 / (gamma - 1.0) * (
    total_pressure_ratio**((gamma - 1.0) / gamma) - 1.0
  )
  if not isfinite(mach_squared) or mach_squared <= 1.0:
    return _failure(
      status=FullyExpandedStatus.OUTSIDE_MODEL_VALIDITY,
      exit_state=exit_state,
      ambient_pressure_Pa=ambient_pressure_Pa,
      message='equivalent fully-expanded Mach number is not supersonic',
    )
  ####

  mach = sqrt(mach_squared)
  try:
    exit_area_ratio = calc_area_mach_ratio(float(exit_state.mach), gamma)
    equivalent_area_ratio = calc_area_mach_ratio(mach, gamma)
  except ValueError as error:
    return _failure(
      status=FullyExpandedStatus.INVALID_INPUT,
      exit_state=exit_state,
      ambient_pressure_Pa=ambient_pressure_Pa,
      message=str(error),
    )
  ####
  area_ratio_to_exit = equivalent_area_ratio / exit_area_ratio
  if not isfinite(area_ratio_to_exit) or area_ratio_to_exit <= 0.0:
    return _failure(
      status=FullyExpandedStatus.OUTSIDE_MODEL_VALIDITY,
      exit_state=exit_state,
      ambient_pressure_Pa=ambient_pressure_Pa,
      message='equivalent area ratio is not finite and positive',
    )
  ####

  static_temperature_K = exit_state.gas.static_temperature_from_total(
    mach,
    exit_state.total_temperature_K,
  )
  static_pressure_Pa = ambient_pressure_Pa
  density_kgpm3 = exit_state.gas.density_from_pressure_temperature(
    static_pressure_Pa,
    static_temperature_K,
  )
  radius_m = exit_state.radius_m * sqrt(area_ratio_to_exit)
  diameter_m = 2.0 * radius_m
  axial_velocity_mps = (
    exit_state.gas.velocity_mps(mach, static_temperature_K)
    * cos(exit_state.flow_angle_rad)
  )
  if not isfinite(axial_velocity_mps) or axial_velocity_mps <= 0.0:
    return _failure(
      status=FullyExpandedStatus.OUTSIDE_MODEL_VALIDITY,
      exit_state=exit_state,
      ambient_pressure_Pa=ambient_pressure_Pa,
      message='equivalent axial velocity is not finite and positive',
    )
  ####
  state = NozzleExitState(
    static_pressure_Pa=static_pressure_Pa,
    static_temperature_K=static_temperature_K,
    mach=mach,
    density_kgpm3=density_kgpm3,
    axial_velocity_mps=axial_velocity_mps,
    flow_angle_rad=exit_state.flow_angle_rad,
    radius_m=radius_m,
    mass_flow_rate_kgps=density_kgpm3 * axial_velocity_mps * pi * radius_m**2,
    total_pressure_Pa=exit_state.total_pressure_Pa,
    total_temperature_K=exit_state.total_temperature_K,
    gas=exit_state.gas,
    species_mass_fractions=exit_state.gas.species_mass_fractions,
    source_kind=NozzleStateSourceKind.DERIVED_ISENTROPIC,
  )
  exit_pressure_residual = (
    float(exit_state.static_pressure_Pa) - ambient_pressure_Pa
  ) / ambient_pressure_Pa
  first_cell_claim_allowed = abs(exit_pressure_residual) > pressure_match_rtol
  message = '' if first_cell_claim_allowed else 'matched exit and ambient pressure: no first-cell claim'
  return FullyExpandedJetResult(
    status=FullyExpandedStatus.CONVERGED,
    exit_state=exit_state,
    ambient_pressure_Pa=ambient_pressure_Pa,
    mach=mach,
    static_pressure_Pa=static_pressure_Pa,
    static_temperature_K=static_temperature_K,
    density_kgpm3=density_kgpm3,
    radius_m=radius_m,
    diameter_m=diameter_m,
    area_ratio_to_exit=area_ratio_to_exit,
    state=state,
    exit_pressure_residual=exit_pressure_residual,
    first_cell_claim_allowed=first_cell_claim_allowed,
    message=message,
  )
####
