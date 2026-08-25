"""Local ambient-pressure free-boundary primitives for planar MOC."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import cos, isfinite, sin

import numpy as np

from exhaust_plume.geometry.contracts import RayIntersectionStatus, Ray2D
from exhaust_plume.geometry.intersections import intersect_rays
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.models.moc.fan import MocExpansionFanResult
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState

__all__ = (
  'MocFreeBoundaryPointResult',
  'MocFreeBoundaryResult',
  'MocReflectedBoundaryResult',
  'solve_ambient_pressure_free_boundary_point',
  'solve_ambient_pressure_free_boundary',
  'solve_reflected_free_boundary',
)


@dataclass(frozen=True, slots=True)
class MocFreeBoundaryPointResult:
  """A characteristic intersection with a pressure-matched free boundary."""

  status: MocPrimitiveStatus
  family: CharacteristicFamily
  state: CharacteristicState | None
  point_m: tuple[float, float] | None
  pressure_residual: float | None
  tangent_residual: float | None
  geometry_residual: float | None
  iterations: int
  intersection_status: str | None = None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


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


@dataclass(frozen=True, slots=True)
class MocReflectedBoundaryResult:
  """A reflected centerline march to an ambient-pressure boundary.

  The returned boundary is an open first-cell foundation.  It contains the
  centerline compatibility states and the pressure-matched boundary points,
  but it deliberately does not infer a compression-shock endpoint or a
  closed physical cell.
  """

  status: MocPrimitiveStatus
  seed_boundary_state: CharacteristicState | None
  centerline_results: tuple[CharacteristicPointResult, ...]
  centerline_states: tuple[CharacteristicState, ...]
  point_results: tuple[MocFreeBoundaryPointResult, ...]
  boundary_states: tuple[CharacteristicState, ...]
  boundary_points_m: tuple[tuple[float, float], ...]
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


def solve_ambient_pressure_free_boundary_point(
  incoming: CharacteristicState,
  previous_boundary: CharacteristicState,
  family: CharacteristicFamily,
  *,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  position_tolerance_m: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
) -> MocFreeBoundaryPointResult:
  """March one characteristic to an ambient-pressure boundary point.

  The pressure state is fixed by ``p0/pa``.  The point is found by intersecting
  an averaged incoming characteristic ray with an averaged tangent ray from
  the previous boundary point.  The tangent residual therefore measures the
  finite-volume boundary segment, while the physical endpoint and downstream
  shock closure remain separate operations.
  """

  if abs(incoming.gamma - previous_boundary.gamma) > pressure_tolerance:
    return MocFreeBoundaryPointResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      family=family,
      state=None,
      point_m=None,
      pressure_residual=None,
      tangent_residual=None,
      geometry_residual=None,
      iterations=0,
      message='incoming and previous boundary states must use the same gamma',
    )
  if not isfinite(total_pressure_Pa) or total_pressure_Pa <= 0.0:
    raise ValueError('total_pressure_Pa must be finite and positive')
  if not isfinite(ambient_pressure_Pa) or ambient_pressure_Pa <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  if total_pressure_Pa <= ambient_pressure_Pa:
    return MocFreeBoundaryPointResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      family=family,
      state=None,
      point_m=None,
      pressure_residual=None,
      tangent_residual=None,
      geometry_residual=None,
      iterations=0,
      message='ambient-pressure boundary state is not supersonic for p0/pa <= 1',
    )
  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(pressure_tolerance) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  gamma = incoming.gamma
  terminal_inverse = supersonic_mach_from_stagnation_pressure_ratio(
    total_pressure_Pa / ambient_pressure_Pa,
    gamma,
  )
  if not terminal_inverse.converged or terminal_inverse.value is None:
    return MocFreeBoundaryPointResult(
      status=terminal_inverse.status,
      family=family,
      state=None,
      point_m=None,
      pressure_residual=None,
      tangent_residual=None,
      geometry_residual=None,
      iterations=0,
      message=terminal_inverse.message,
    )
  terminal_mach = terminal_inverse.value
  terminal_nu = prandtl_meyer_angle_rad(terminal_mach, gamma)
  boundary_theta = (
    incoming.k_plus + terminal_nu
    if family is CharacteristicFamily.PLUS
    else incoming.k_minus - terminal_nu
  )
  boundary_state = CharacteristicState(
    x_m=previous_boundary.x_m,
    y_m=previous_boundary.y_m,
    theta_rad=boundary_theta,
    mach=terminal_mach,
    gamma=gamma,
  )
  previous_point = (previous_boundary.x_m, previous_boundary.y_m)
  last_geometry_residual: float | None = None
  last_intersection_status: str | None = None
  for iteration in range(1, maximum_iterations + 1):
    incoming_angle = (
      incoming.theta_rad + incoming.mu_rad
      if family is CharacteristicFamily.PLUS
      else incoming.theta_rad - incoming.mu_rad
    )
    boundary_angle = 0.5 * (previous_boundary.theta_rad + boundary_theta)
    incoming_ray = Ray2D(
      origin=np.asarray((incoming.x_m, incoming.y_m), dtype=float),
      direction=np.asarray((cos(incoming_angle), sin(incoming_angle)), dtype=float),
    )
    boundary_ray = Ray2D(
      origin=np.asarray(previous_point, dtype=float),
      direction=np.asarray((cos(boundary_angle), sin(boundary_angle)), dtype=float),
    )
    intersection = intersect_rays(
      incoming_ray,
      boundary_ray,
      parameter_tolerance=position_tolerance_m,
    )
    last_intersection_status = intersection.status.value
    last_geometry_residual = intersection.residual
    if not intersection.is_success or intersection.point is None:
      status = (
        MocPrimitiveStatus.GEOMETRY_FAILURE
        if intersection.status is not RayIntersectionStatus.SUCCESS
        else MocPrimitiveStatus.INVALID_INPUT
      )
      return MocFreeBoundaryPointResult(
        status=status,
        family=family,
        state=None,
        point_m=None,
        pressure_residual=None,
        tangent_residual=None,
        geometry_residual=intersection.residual,
        iterations=iteration,
        intersection_status=last_intersection_status,
        message=f'free-boundary characteristic intersection failed: {last_intersection_status}',
      )
    point = (float(intersection.point[0]), float(intersection.point[1]))
    displacement = (
      (point[0] - boundary_state.x_m) ** 2
      + (point[1] - boundary_state.y_m) ** 2
    ) ** 0.5
    boundary_state = replace(boundary_state, x_m=point[0], y_m=point[1])
    if displacement <= position_tolerance_m:
      break
  else:
    return MocFreeBoundaryPointResult(
      status=MocPrimitiveStatus.MAX_ITERATIONS,
      family=family,
      state=boundary_state,
      point_m=(boundary_state.x_m, boundary_state.y_m),
      pressure_residual=None,
      tangent_residual=None,
      geometry_residual=last_geometry_residual,
      iterations=maximum_iterations,
      intersection_status=last_intersection_status,
      message='free-boundary characteristic geometry did not converge',
    )
  ####
  pressure = total_pressure_Pa / (
    1.0 + 0.5 * (gamma - 1.0) * terminal_mach**2
  ) ** (gamma / (gamma - 1.0))
  pressure_residual = (pressure - ambient_pressure_Pa) / ambient_pressure_Pa
  boundary_angle = 0.5 * (previous_boundary.theta_rad + boundary_theta)
  tangent_residual = sin(boundary_angle - 0.5 * (previous_boundary.theta_rad + boundary_theta))
  status = (
    MocPrimitiveStatus.CONVERGED
    if abs(pressure_residual) <= pressure_tolerance
    else MocPrimitiveStatus.INVARIANT_FAILURE
  )
  return MocFreeBoundaryPointResult(
    status=status,
    family=family,
    state=boundary_state,
    point_m=(boundary_state.x_m, boundary_state.y_m),
    pressure_residual=pressure_residual,
    tangent_residual=tangent_residual,
    geometry_residual=last_geometry_residual,
    iterations=iteration,
    intersection_status=last_intersection_status,
    message=(
      ''
      if status is MocPrimitiveStatus.CONVERGED
      else 'free-boundary pressure residual exceeded tolerance'
    ),
  )
####


def solve_reflected_free_boundary(
  fan: MocExpansionFanResult,
  exit_state: NozzleExitState,
  ambient: AmbientState,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
) -> MocReflectedBoundaryResult:
  """March reflected ``C+`` characteristics to an ambient-pressure boundary.

  Each source state in the open lip fan is first brought to the centerline
  with ``theta = 0``.  Its compatible reflected ``C+`` characteristic is then
  intersected with the previous pressure-matched boundary tangent.  The
  sequence is a reusable first-cell boundary foundation; no shock location or
  physical termination is inferred from the last point.
  """

  if not fan.converged:
    return MocReflectedBoundaryResult(
      status=fan.status,
      seed_boundary_state=None,
      centerline_results=(),
      centerline_states=(),
      point_results=(),
      boundary_states=(),
      boundary_points_m=(),
      message=f'lip fan is not converged: {fan.message}',
    )
  if exit_state.static_pressure_Pa <= ambient.pressure_Pa:
    return MocReflectedBoundaryResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      seed_boundary_state=None,
      centerline_results=(),
      centerline_states=(),
      point_results=(),
      boundary_states=(),
      boundary_points_m=(),
      message='reflected free-boundary march requires an underexpanded exit state',
    )
  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(invariant_tolerance) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not isfinite(pressure_tolerance) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  if not fan.states:
    return MocReflectedBoundaryResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      seed_boundary_state=None,
      centerline_results=(),
      centerline_states=(),
      point_results=(),
      boundary_states=(),
      boundary_points_m=(),
      message='lip fan contains no characteristic states',
    )
  ####
  if (
    abs(fan.exit_pressure_Pa - float(exit_state.static_pressure_Pa))
    > pressure_tolerance * max(abs(fan.exit_pressure_Pa), abs(float(exit_state.static_pressure_Pa)), 1.0)
    or abs(fan.ambient_pressure_Pa - float(ambient.pressure_Pa))
    > pressure_tolerance * max(abs(fan.ambient_pressure_Pa), abs(float(ambient.pressure_Pa)), 1.0)
  ):
    return MocReflectedBoundaryResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      seed_boundary_state=None,
      centerline_results=(),
      centerline_states=(),
      point_results=(),
      boundary_states=(),
      boundary_points_m=(),
      message='fan, exit state, and ambient pressure contracts do not match',
    )
  ####
  gamma = float(exit_state.gas.gamma)
  if any(abs(state.gamma - gamma) > invariant_tolerance for state in fan.states):
    return MocReflectedBoundaryResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      seed_boundary_state=None,
      centerline_results=(),
      centerline_states=(),
      point_results=(),
      boundary_states=(),
      boundary_points_m=(),
      message='lip fan and exit state must use the same gamma',
    )
  ####
  terminal = fan.states[-1]
  seed_boundary = CharacteristicState(
    x_m=0.0,
    y_m=float(exit_state.radius_m),
    theta_rad=terminal.theta_rad,
    mach=terminal.mach,
    gamma=gamma,
  )
  previous_boundary = seed_boundary
  centerline_results: list[CharacteristicPointResult] = []
  centerline_states: list[CharacteristicState] = []
  point_results: list[MocFreeBoundaryPointResult] = []
  boundary_states: list[CharacteristicState] = []
  boundary_points: list[tuple[float, float]] = []
  for index, source in enumerate(fan.states):
    centerline_result = centerline_characteristic_point(
      source,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    centerline_results.append(centerline_result)
    if not centerline_result.converged or centerline_result.state is None:
      return MocReflectedBoundaryResult(
        status=centerline_result.status,
        seed_boundary_state=seed_boundary,
        centerline_results=tuple(centerline_results),
        centerline_states=tuple(centerline_states),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        message=f'centerline reflection source {index} failed: {centerline_result.message}',
      )
    centerline_states.append(centerline_result.state)
    point_result = solve_ambient_pressure_free_boundary_point(
      centerline_result.state,
      previous_boundary,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=float(exit_state.total_pressure_Pa),
      ambient_pressure_Pa=float(ambient.pressure_Pa),
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    point_results.append(point_result)
    if not point_result.converged or point_result.state is None or point_result.point_m is None:
      return MocReflectedBoundaryResult(
        status=point_result.status,
        seed_boundary_state=seed_boundary,
        centerline_results=tuple(centerline_results),
        centerline_states=tuple(centerline_states),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        message=f'reflected free-boundary point {index} failed: {point_result.message}',
      )
    if point_result.point_m[0] <= previous_boundary.x_m + position_tolerance_m:
      return MocReflectedBoundaryResult(
        status=MocPrimitiveStatus.GEOMETRY_FAILURE,
        seed_boundary_state=seed_boundary,
        centerline_results=tuple(centerline_results),
        centerline_states=tuple(centerline_states),
        point_results=tuple(point_results),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        message=f'reflected free-boundary point {index} is not strictly downstream',
      )
    boundary_states.append(point_result.state)
    boundary_points.append(point_result.point_m)
    previous_boundary = point_result.state
  ####
  return MocReflectedBoundaryResult(
    status=MocPrimitiveStatus.CONVERGED,
    seed_boundary_state=seed_boundary,
    centerline_results=tuple(centerline_results),
    centerline_states=tuple(centerline_states),
    point_results=tuple(point_results),
    boundary_states=tuple(boundary_states),
    boundary_points_m=tuple(boundary_points),
  )
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
