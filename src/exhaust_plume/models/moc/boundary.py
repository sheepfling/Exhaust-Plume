"""Local ambient-pressure free-boundary primitives for planar MOC."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, sin

from exhaust_plume.models.moc.primitives import (
  MocPrimitiveStatus,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState

__all__ = (
  'MocFreeBoundaryResult',
  'solve_ambient_pressure_free_boundary',
)


@dataclass(frozen=True, slots=True)
class MocFreeBoundaryResult:
  """A finite tangent segment at an ambient-pressure characteristic state."""

  status: MocPrimitiveStatus
  exit_pressure_Pa: float
  ambient_pressure_Pa: float
  terminal_mach: float | None
  terminal_flow_angle_rad: float | None
  pressure_residual: float | None
  tangent_residual: float | None
  points_m: tuple[tuple[float, float], ...]
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


def solve_ambient_pressure_free_boundary(
  exit_state: NozzleExitState,
  ambient: AmbientState,
  *,
  extent_m: float = 0.1,
  pressure_tolerance: float = 1.0e-10,
) -> MocFreeBoundaryResult:
  """Construct a local ambient-pressure tangent segment from a nozzle lip.

  The segment uses the isentropic total-pressure ratio to determine the
  terminal Mach number and the Prandtl--Meyer turn from the uniform exit
  state.  Its extent is explicit input: no downstream shock, centerline
  reflection, or physical plume endpoint is inferred.
  """

  exit_pressure = float(exit_state.static_pressure_Pa)
  ambient_pressure = float(ambient.pressure_Pa)
  if not isfinite(extent_m) or extent_m <= 0.0:
    raise ValueError('extent_m must be finite and positive')
  if not isfinite(pressure_tolerance) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if exit_pressure <= ambient_pressure:
    return MocFreeBoundaryResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      exit_pressure_Pa=exit_pressure,
      ambient_pressure_Pa=ambient_pressure,
      terminal_mach=None,
      terminal_flow_angle_rad=None,
      pressure_residual=None,
      tangent_residual=None,
      points_m=(),
      message='the local Prandtl-Meyer free-boundary primitive requires an underexpanded exit state',
    )
  ####
  gamma = float(exit_state.gas.gamma)
  terminal_inverse = supersonic_mach_from_stagnation_pressure_ratio(
    exit_state.total_pressure_Pa / ambient_pressure,
    gamma,
  )
  if not terminal_inverse.converged or terminal_inverse.value is None:
    return MocFreeBoundaryResult(
      status=terminal_inverse.status,
      exit_pressure_Pa=exit_pressure,
      ambient_pressure_Pa=ambient_pressure,
      terminal_mach=None,
      terminal_flow_angle_rad=None,
      pressure_residual=None,
      tangent_residual=None,
      points_m=(),
      message=terminal_inverse.message,
    )
  terminal_mach = terminal_inverse.value
  terminal_angle = float(exit_state.flow_angle_rad) + (
    prandtl_meyer_angle_rad(terminal_mach, gamma)
    - prandtl_meyer_angle_rad(exit_state.mach, gamma)
  )
  terminal_pressure = exit_state.gas.static_pressure_from_total(
    terminal_mach,
    exit_state.total_pressure_Pa,
  )
  pressure_residual = (terminal_pressure - ambient_pressure) / ambient_pressure
  direction = (cos(terminal_angle), sin(terminal_angle))
  lip = (0.0, float(exit_state.radius_m))
  endpoint = (
    lip[0] + extent_m * direction[0],
    lip[1] + extent_m * direction[1],
  )
  # The segment is parameterized by its own tangent, so the geometric tangent
  # residual is exactly zero unless the endpoint becomes non-finite.
  tangent_residual = 0.0 if all(isfinite(value) for value in endpoint) else float('inf')
  status = (
    MocPrimitiveStatus.CONVERGED
    if abs(pressure_residual) <= pressure_tolerance and isfinite(tangent_residual)
    else MocPrimitiveStatus.INVARIANT_FAILURE
  )
  return MocFreeBoundaryResult(
    status=status,
    exit_pressure_Pa=exit_pressure,
    ambient_pressure_Pa=ambient_pressure,
    terminal_mach=terminal_mach,
    terminal_flow_angle_rad=terminal_angle,
    pressure_residual=pressure_residual,
    tangent_residual=tangent_residual,
    points_m=(lip, endpoint),
    message=(
      ''
      if status is MocPrimitiveStatus.CONVERGED
      else 'ambient-pressure free-boundary residual exceeded tolerance'
    ),
  )
####
