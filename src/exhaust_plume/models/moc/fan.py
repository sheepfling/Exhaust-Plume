"""Planar underexpanded expansion-fan mesh foundation."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, sin

import numpy as np

from exhaust_plume.geometry.contracts import GeometryStatus
from exhaust_plume.geometry.polygons import validate_polygon
from exhaust_plume.models.moc.primitives import (
  CharacteristicState,
  MocPrimitiveStatus,
  inverse_prandtl_meyer_angle_rad,
  mach_angle_rad,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState

__all__ = (
  'MocExpansionFanCell',
  'MocExpansionFanResult',
  'solve_underexpanded_expansion_fan',
)


@dataclass(frozen=True, slots=True)
class MocExpansionFanCell:
  """One finite triangular sector of the discretized lip fan."""

  cell_index: int
  vertices_xr_m: tuple[tuple[float, float], ...]
  state: CharacteristicState
  geometry_status: GeometryStatus

  def __post_init__(self) -> None:
    if len(self.vertices_xr_m) != 3:
      raise ValueError('fan cells must be triangular')
    validation = validate_polygon(np.asarray(self.vertices_xr_m, dtype=float))
    if not validation.is_valid:
      raise ValueError(f'fan cell polygon is invalid: {validation.status.value}')
    object.__setattr__(self, 'geometry_status', GeometryStatus.VALID)
  ####


@dataclass(frozen=True, slots=True)
class MocExpansionFanResult:
  """Structured expansion-fan result without a downstream closure claim.

  ``states`` are the centerline-compatible states at the recorded axis
  intersections. ``lip_states`` retain the same simple-wave states at the
  nozzle-lip source point so reflected characteristic marches have explicit
  source geometry.
  """

  status: MocPrimitiveStatus
  exit_pressure_Pa: float
  ambient_pressure_Pa: float
  terminal_pressure_Pa: float | None
  terminal_pressure_residual: float | None
  terminal_turn_rad: float | None
  states: tuple[CharacteristicState, ...]
  lip_states: tuple[CharacteristicState, ...]
  centerline_points_m: tuple[tuple[float, float], ...]
  cells: tuple[MocExpansionFanCell, ...]
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


def _invalid(
    *,
    exit_pressure: float,
    ambient_pressure: float,
    status: MocPrimitiveStatus,
    message: str,
) -> MocExpansionFanResult:
  return MocExpansionFanResult(
    status=status,
    exit_pressure_Pa=exit_pressure,
    ambient_pressure_Pa=ambient_pressure,
    terminal_pressure_Pa=None,
    terminal_pressure_residual=None,
    terminal_turn_rad=None,
    states=(),
    lip_states=(),
    centerline_points_m=(),
    cells=(),
    message=message,
  )
####


def solve_underexpanded_expansion_fan(
    exit_state: NozzleExitState,
    ambient: AmbientState,
    *,
    characteristic_count: int = 8,
    geometric_tolerance_m: float = 1.0e-12,
    pressure_tolerance: float = 1.0e-10,
) -> MocExpansionFanResult:
  """Build the upper-half lip fan to the ambient-pressure state.

  The fan is deliberately returned as an open mesh.  Its axis-intersection
  points are a geometric boundary of this fan construction only; they are not
  a centerline symmetry state, a full first-cell closure, or a physical
  shock/Mach-disk endpoint.
  """

  exit_pressure = float(exit_state.static_pressure_Pa)
  ambient_pressure = float(ambient.pressure_Pa)
  if exit_pressure <= ambient_pressure:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      message='the expansion-fan foundation requires an underexpanded exit state',
    )
  if (
    isinstance(characteristic_count, bool)
    or not isinstance(characteristic_count, int)
    or characteristic_count < 2
  ):
    raise ValueError('characteristic_count must be an integer of at least two')
  if not isfinite(geometric_tolerance_m) or geometric_tolerance_m <= 0.0:
    raise ValueError('geometric_tolerance_m must be finite and positive')
  if not isfinite(pressure_tolerance) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  ####
  gamma = float(exit_state.gas.gamma)
  pressure_inverse = supersonic_mach_from_stagnation_pressure_ratio(
    exit_state.total_pressure_Pa / ambient_pressure,
    gamma,
  )
  if not pressure_inverse.converged or pressure_inverse.value is None:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=pressure_inverse.status,
      message=pressure_inverse.message,
    )
  terminal_mach = pressure_inverse.value
  if terminal_mach <= exit_state.mach:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      message='ambient-pressure state is not downstream of the exit state',
    )
  ####
  exit_nu = prandtl_meyer_angle_rad(exit_state.mach, gamma)
  terminal_nu = prandtl_meyer_angle_rad(terminal_mach, gamma)
  total_turn = terminal_nu - exit_nu
  if total_turn <= 0.0:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      message='ambient-pressure state requires no positive expansion turn',
    )
  ####
  lip = (0.0, float(exit_state.radius_m))
  states: list[CharacteristicState] = []
  lip_states: list[CharacteristicState] = []
  centerline_points: list[tuple[float, float]] = []
  for index in range(characteristic_count + 1):
    fraction = index / characteristic_count
    nu = exit_nu + fraction * total_turn
    inversion = inverse_prandtl_meyer_angle_rad(nu, gamma)
    if not inversion.converged or inversion.value is None:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=inversion.status,
        message=f'fan state {index} could not invert Prandtl-Meyer angle: {inversion.message}',
      )
    mach = inversion.value
    theta = float(exit_state.flow_angle_rad) + fraction * total_turn
    mu = mach_angle_rad(mach)
    characteristic_angle = theta - mu
    lip_states.append(
      CharacteristicState(
        x_m=lip[0],
        y_m=lip[1],
        theta_rad=theta,
        mach=mach,
        gamma=gamma,
      )
    )
    vertical_component = sin(characteristic_angle)
    # This sign check is dimensionless.  Keep the metre-valued tolerance
    # reserved for coordinate comparisons below.
    if vertical_component >= -1.0e-12:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
        message=f'fan characteristic {index} does not travel toward the centerline',
      )
    x = lip[0] + (0.0 - lip[1]) * cos(characteristic_angle) / vertical_component
    if not isfinite(x) or x <= 0.0:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=MocPrimitiveStatus.GEOMETRY_FAILURE,
        message=f'fan characteristic {index} produced a non-forward centerline point',
      )
    states.append(
      CharacteristicState(
        x_m=x,
        y_m=0.0,
        theta_rad=theta,
        mach=mach,
        gamma=gamma,
      )
    )
    centerline_points.append((x, 0.0))
  ####
  if any(right[0] - left[0] <= geometric_tolerance_m for left, right in zip(centerline_points, centerline_points[1:])):
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      message='fan centerline intersections are not strictly downstream ordered',
    )
  ####
  cells: list[MocExpansionFanCell] = []
  for index, (left_point, right_point) in enumerate(zip(centerline_points, centerline_points[1:])):
    left_state = states[index]
    right_state = states[index + 1]
    midpoint_nu = 0.5 * (left_state.nu_rad + right_state.nu_rad)
    midpoint_theta = 0.5 * (left_state.theta_rad + right_state.theta_rad)
    midpoint_inverse = inverse_prandtl_meyer_angle_rad(midpoint_nu, gamma)
    if not midpoint_inverse.converged or midpoint_inverse.value is None:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=midpoint_inverse.status,
        message=f'fan cell {index} midpoint state failed inversion',
      )
    midpoint = MocExpansionFanCell(
      cell_index=index,
      vertices_xr_m=(lip, left_point, right_point),
      state=CharacteristicState(
        x_m=(left_point[0] + right_point[0]) / 3.0,
        y_m=lip[1] / 3.0,
        theta_rad=midpoint_theta,
        mach=midpoint_inverse.value,
        gamma=gamma,
      ),
      geometry_status=GeometryStatus.VALID,
    )
    cells.append(midpoint)
  ####
  terminal_pressure = exit_state.gas.static_pressure_from_total(
    terminal_mach,
    exit_state.total_pressure_Pa,
  )
  pressure_residual = (terminal_pressure - ambient_pressure) / ambient_pressure
  status = (
    MocPrimitiveStatus.CONVERGED
    if abs(pressure_residual) <= pressure_tolerance
    else MocPrimitiveStatus.INVARIANT_FAILURE
  )
  return MocExpansionFanResult(
    status=status,
    exit_pressure_Pa=exit_pressure,
    ambient_pressure_Pa=ambient_pressure,
    terminal_pressure_Pa=terminal_pressure,
    terminal_pressure_residual=pressure_residual,
    terminal_turn_rad=total_turn,
    states=tuple(states),
    lip_states=tuple(lip_states),
    centerline_points_m=tuple(centerline_points),
    cells=tuple(cells),
    message=(
      ''
      if status is MocPrimitiveStatus.CONVERGED
      else 'ambient-pressure boundary residual exceeded tolerance'
    ),
  )
####
