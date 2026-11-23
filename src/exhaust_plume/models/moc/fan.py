"""Planar source-point Prandtl--Meyer expansion-fan foundation."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, hypot, isfinite, sin

import numpy as np

from exhaust_plume.geometry.contracts import GeometryStatus
from exhaust_plume.geometry.polygons import validate_polygon
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
  mach_angle_rad,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState

__all__ = (
  'MocExpansionFanCell',
  'MocExpansionFanResult',
  'MocExpansionFanPointSample',
  'solve_source_point_expansion_fan',
  'sample_source_point_expansion_fan',
  'solve_underexpanded_expansion_fan',
)


@dataclass(frozen=True, slots=True)
class MocExpansionFanCell:
  """One fan triangle with its state sampled at the geometric centroid."""

  cell_index: int
  vertices_xr_m: tuple[tuple[float, float], ...]
  state: CharacteristicState
  geometry_status: GeometryStatus

  def __post_init__(self) -> None:
    if len(self.vertices_xr_m) != 3:
      raise ValueError('fan cells must be triangular')
    ####
    validation = validate_polygon(np.asarray(self.vertices_xr_m, dtype=float))
    if not validation.is_valid:
      raise ValueError(f'fan cell polygon is invalid: {validation.status.value}')
    ####
    object.__setattr__(self, 'geometry_status', GeometryStatus.VALID)
  ####
####


@dataclass(frozen=True, slots=True)
class MocExpansionFanResult:
  """Structured expansion-fan result without a downstream closure claim.

  ``states`` are the discretized simple-wave states used for fan-cell
  interpolation. ``centerline_states`` are the compatibility states obtained
  by intersecting each source ``C-`` characteristic with the symmetry line.
  ``centerline_points_m`` is that averaged-characteristic compatibility grid.
  Fan-cell geometry and exact point sampling use the direct source-ray
  intersections in ``lip_ray_centerline_points_m``; retaining both traces
  makes their geometric difference explicit. ``lip_states`` retain the
  simple-wave states at the source point. ``source_point_m`` records that
  origin; the legacy ``lip_states`` name remains for reflected-boundary callers.
  """

  status: MocPrimitiveStatus
  exit_pressure_Pa: float
  ambient_pressure_Pa: float
  terminal_pressure_Pa: float | None
  terminal_pressure_residual: float | None
  terminal_turn_rad: float | None
  states: tuple[CharacteristicState, ...]
  centerline_states: tuple[CharacteristicState, ...]
  lip_states: tuple[CharacteristicState, ...]
  centerline_points_m: tuple[tuple[float, float], ...]
  lip_ray_centerline_points_m: tuple[tuple[float, float], ...]
  cells: tuple[MocExpansionFanCell, ...]
  source_point_m: tuple[float, float] | None = None
  message: str = ''
  total_pressure_Pa: float | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
  ####

  @property
  def source_states(self) -> tuple[CharacteristicState, ...]:
    """Return the source-ray states under a geometry-neutral name."""

    return self.lip_states
  ####

  def matches_source_ray_geometry(
    self,
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> bool:
    """Check that retained axis intersections and cells match source rays."""

    tolerance = float(position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    if not self.converged or self.source_point_m is None:
      return False
    try:
      source_x, source_y = (float(value) for value in self.source_point_m)
      ray_states = self.source_states
      ray_points = self.lip_ray_centerline_points_m
      axis_states = self.states
      cells = self.cells
      compatibility_points = self.centerline_points_m
      compatibility_states = self.centerline_states
    except (TypeError, ValueError):
      return False
    if (
      not isfinite(source_x)
      or not isfinite(source_y)
      or source_y <= 0.0
      or len(ray_states) < 2
      or len(ray_points) != len(ray_states)
      or len(axis_states) != len(ray_states)
      or len(cells) != len(ray_states) - 1
      or len(compatibility_points) != len(compatibility_states)
      or len(compatibility_states) != len(ray_states)
    ):
      return False
    ####
    for index, (source_state, ray_point, axis_state) in enumerate(
      zip(ray_states, ray_points, axis_states, strict=True)
    ):
      if not isinstance(source_state, CharacteristicState):
        return False
      if not isinstance(axis_state, CharacteristicState):
        return False
      if (
        abs(source_state.x_m - source_x) > tolerance
        or abs(source_state.y_m - source_y) > tolerance
      ):
        return False
      ray_angle = source_state.theta_rad - mach_angle_rad(source_state.mach)
      ray_sine = sin(ray_angle)
      if ray_sine >= -1.0e-14:
        return False
      expected_point = (
        source_x - source_y * cos(ray_angle) / ray_sine,
        0.0,
      )
      if len(ray_point) != 2 or len(compatibility_points[index]) != 2:
        return False
      if (
        abs(float(ray_point[0]) - expected_point[0]) > tolerance
        or abs(float(ray_point[1]) - expected_point[1]) > tolerance
        or abs(axis_state.x_m - float(ray_point[0])) > tolerance
        or abs(axis_state.y_m - float(ray_point[1])) > tolerance
        or abs(compatibility_states[index].x_m - compatibility_points[index][0])
        > tolerance
        or abs(compatibility_states[index].y_m - compatibility_points[index][1])
        > tolerance
      ):
        return False
      if index and ray_point[0] <= ray_points[index - 1][0] + tolerance:
        return False
    ####
    for index, cell in enumerate(cells):
      if not isinstance(cell, MocExpansionFanCell) or cell.cell_index != index:
        return False
      expected_vertices = (
        (source_x, source_y),
        ray_points[index],
        ray_points[index + 1],
      )
      if len(cell.vertices_xr_m) != len(expected_vertices) or any(
        len(actual) != 2
        or any(
          abs(float(actual_value) - expected_value) > tolerance
          for actual_value, expected_value in zip(
            actual,
            expected,
            strict=True,
          )
        )
        for actual, expected in zip(
          cell.vertices_xr_m,
          expected_vertices,
          strict=True,
        )
      ):
        return False
    ####
    return True
  ####
####


@dataclass(frozen=True, slots=True)
class MocExpansionFanPointSample:
  """Simple-wave state at one interior point of an open source fan."""

  status: MocPrimitiveStatus
  point_m: tuple[float, float]
  state: CharacteristicState | None
  total_pressure_Pa: float | None
  characteristic_ray_angle_rad: float | None
  ray_angle_residual_rad: float | None
  iterations: int
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocPrimitiveStatus):
      raise TypeError('status must be a MocPrimitiveStatus')
    point = tuple(float(value) for value in self.point_m)
    if len(point) != 2 or any(not isfinite(value) for value in point):
      raise ValueError('point_m must contain two finite coordinates')
    object.__setattr__(self, 'point_m', point)
    if (self.state is not None) != (self.status is MocPrimitiveStatus.CONVERGED):
      raise ValueError('a sampled state must be present exactly for convergence')
    if self.state is not None and not isinstance(self.state, CharacteristicState):
      raise TypeError('state must be a CharacteristicState or None')
    for name in ('total_pressure_Pa', 'characteristic_ray_angle_rad', 'ray_angle_residual_rad'):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric):
          raise ValueError(f'{name} must be finite or None')
        if name == 'total_pressure_Pa' and numeric <= 0.0:
          raise ValueError('total_pressure_Pa must be positive when supplied')
        object.__setattr__(self, name, numeric)
    if isinstance(self.iterations, bool) or not isinstance(self.iterations, int):
      raise TypeError('iterations must be an integer')
    if self.iterations < 0:
      raise ValueError('iterations must be a nonnegative integer')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
  ####
####


def _invalid(
    *,
    exit_pressure: float,
    ambient_pressure: float,
    status: MocPrimitiveStatus,
    message: str,
    source_point: tuple[float, float] | None = None,
) -> MocExpansionFanResult:
  return MocExpansionFanResult(
    status=status,
    exit_pressure_Pa=exit_pressure,
    ambient_pressure_Pa=ambient_pressure,
    terminal_pressure_Pa=None,
    terminal_pressure_residual=None,
    terminal_turn_rad=None,
    states=(),
    centerline_states=(),
    lip_states=(),
    centerline_points_m=(),
    lip_ray_centerline_points_m=(),
    cells=(),
    source_point_m=source_point,
    message=message,
  )
####


def sample_source_point_expansion_fan(
  fan: MocExpansionFanResult,
  point_m: tuple[float, float],
  *,
  position_tolerance_m: float = 1.0e-12,
  characteristic_tolerance_rad: float = 1.0e-12,
    invariant_tolerance_rad: float = 1.0e-10,
  max_iterations: int = 80,
) -> MocExpansionFanPointSample:
  """Sample the centered ``C-`` simple wave inside its open fan region.

  The fan's constant ``k_plus = theta - nu`` invariant and the ray angle
  ``theta - mu`` determine Mach at an interior point. Points on the source,
  centerline, or outside the fan are rejected; the returned state is not an
  axis/contact boundary condition or a global plume closure.
  """

  if not isinstance(fan, MocExpansionFanResult):
    raise TypeError('fan must be a MocExpansionFanResult')
  try:
    point = (float(point_m[0]), float(point_m[1]))
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('point_m must contain two coordinates') from error
  if any(not isfinite(value) for value in point):
    raise ValueError('point_m must contain finite coordinates')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('characteristic_tolerance_rad', characteristic_tolerance_rad),
      ('invariant_tolerance_rad', invariant_tolerance_rad),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(max_iterations, bool) or not isinstance(max_iterations, int) or max_iterations < 1:
    raise ValueError('max_iterations must be a positive integer')
  if (
    not fan.converged
    or fan.source_point_m is None
    or fan.total_pressure_Pa is None
    or len(fan.source_states) < 2
  ):
    return MocExpansionFanPointSample(
      status=MocPrimitiveStatus.INVALID_INPUT,
      point_m=point,
      state=None,
      total_pressure_Pa=None,
      characteristic_ray_angle_rad=None,
      ray_angle_residual_rad=None,
      iterations=0,
      message='fan must retain a converged source, total pressure, and ray states',
    )
  ####
  source_x, source_y = fan.source_point_m
  dx = point[0] - source_x
  dy = point[1] - source_y
  if (
    dx <= position_tolerance_m
    or point[1] <= position_tolerance_m
    or point[1] >= source_y - position_tolerance_m
    or hypot(dx, dy) <= position_tolerance_m
  ):
    return MocExpansionFanPointSample(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      point_m=point,
      state=None,
      total_pressure_Pa=None,
      characteristic_ray_angle_rad=None,
      ray_angle_residual_rad=None,
      iterations=0,
      message='point is not strictly inside the open upper-half fan region',
    )
  ####
  ray_angle = atan2(dy, dx)
  states = fan.source_states
  gamma = float(states[0].gamma)
  invariant = states[0].k_plus
  if any(
      abs(float(state.gamma) - gamma) > invariant_tolerance_rad
      or abs(state.k_plus - invariant) > invariant_tolerance_rad
    for state in states
  ):
    return MocExpansionFanPointSample(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      point_m=point,
      state=None,
      total_pressure_Pa=None,
      characteristic_ray_angle_rad=ray_angle,
      ray_angle_residual_rad=None,
      iterations=0,
      message='retained fan rays do not share one caloric model and k_plus invariant',
    )
  ####
  lower_mach = min(float(state.mach) for state in states)
  upper_mach = max(float(state.mach) for state in states)

  def ray_angle_for_mach(mach: float) -> float:
    return invariant + prandtl_meyer_angle_rad(mach, gamma) - mach_angle_rad(mach)
  ####

  lower_angle = ray_angle_for_mach(lower_mach)
  upper_angle = ray_angle_for_mach(upper_mach)
  if (
    ray_angle < lower_angle - characteristic_tolerance_rad
    or ray_angle > upper_angle + characteristic_tolerance_rad
  ):
    return MocExpansionFanPointSample(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      point_m=point,
      state=None,
      total_pressure_Pa=None,
      characteristic_ray_angle_rad=ray_angle,
      ray_angle_residual_rad=None,
      iterations=0,
      message='point ray angle lies outside the retained expansion fan',
    )
  ####
  low = lower_mach
  high = upper_mach
  mach = 0.5 * (low + high)
  residual = ray_angle_for_mach(mach) - ray_angle
  iterations = 0
  for iterations in range(1, max_iterations + 1):
    mach = 0.5 * (low + high)
    residual = ray_angle_for_mach(mach) - ray_angle
    if abs(residual) <= characteristic_tolerance_rad:
      break
    if residual < 0.0:
      low = mach
    else:
      high = mach
  else:
    return MocExpansionFanPointSample(
      status=MocPrimitiveStatus.MAX_ITERATIONS,
      point_m=point,
      state=None,
      total_pressure_Pa=None,
      characteristic_ray_angle_rad=ray_angle_for_mach(mach),
      ray_angle_residual_rad=abs(residual),
      iterations=max_iterations,
      message='simple-wave Mach inversion did not meet the ray-angle tolerance',
    )
  ####
  theta = invariant + prandtl_meyer_angle_rad(mach, gamma)
  sampled_state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=theta,
    mach=mach,
    gamma=gamma,
  )
  return MocExpansionFanPointSample(
    status=MocPrimitiveStatus.CONVERGED,
    point_m=point,
    state=sampled_state,
    total_pressure_Pa=fan.total_pressure_Pa,
    characteristic_ray_angle_rad=ray_angle_for_mach(mach),
    ray_angle_residual_rad=abs(residual),
    iterations=iterations,
  )
####


def solve_source_point_expansion_fan(
    source_state: CharacteristicState,
    total_pressure_Pa: float,
    ambient_pressure_Pa: float,
    *,
    characteristic_count: int = 8,
    geometric_tolerance_m: float = 1.0e-12,
    pressure_tolerance: float = 1.0e-10,
    source_static_pressure_Pa: float | None = None,
) -> MocExpansionFanResult:
  """Build an upper-half fan from an exact supersonic point state.

  The fan is deliberately returned as an open mesh. Its axis-intersection
  points are a geometric boundary of this construction only; they do not
  close an ambient contact, a full first cell, or a physical shock endpoint.
  """

  if not isinstance(source_state, CharacteristicState):
    return _invalid(
      exit_pressure=0.0,
      ambient_pressure=0.0,
      status=MocPrimitiveStatus.INVALID_INPUT,
      message='source_state must be a supersonic CharacteristicState',
    )
  ####
  if (
    isinstance(characteristic_count, bool)
    or not isinstance(characteristic_count, int)
    or characteristic_count < 2
  ):
    raise ValueError('characteristic_count must be an integer of at least two')
  ####
  if not isfinite(geometric_tolerance_m) or geometric_tolerance_m <= 0.0:
    raise ValueError('geometric_tolerance_m must be finite and positive')
  ####
  if not isfinite(pressure_tolerance) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  ####
  try:
    total_pressure = float(total_pressure_Pa)
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    return _invalid(
      exit_pressure=0.0,
      ambient_pressure=0.0,
      status=MocPrimitiveStatus.INVALID_INPUT,
      message='total and ambient pressures must be numeric',
    )
  ####
  if (
    not isfinite(total_pressure)
    or total_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
  ):
    return _invalid(
      exit_pressure=0.0,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.INVALID_INPUT,
      message='total and ambient pressures must be finite and positive',
    )
  ####
  source_point = (float(source_state.x_m), float(source_state.y_m))
  if source_state.y_m <= geometric_tolerance_m:
    return _invalid(
      exit_pressure=0.0,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.INVALID_INPUT,
      message='an upper-half source point must lie above the symmetry line',
    )
  ####
  gamma = float(source_state.gamma)
  exit_pressure = total_pressure / (
    1.0 + 0.5 * (gamma - 1.0) * source_state.mach**2
  ) ** (gamma / (gamma - 1.0))
  if source_static_pressure_Pa is not None:
    try:
      supplied_source_pressure = float(source_static_pressure_Pa)
    except (TypeError, ValueError):
      supplied_source_pressure = float('nan')
    ####
    pressure_scale = max(abs(exit_pressure), abs(supplied_source_pressure), 1.0)
    if (
      not isfinite(supplied_source_pressure)
      or supplied_source_pressure <= 0.0
      or abs(exit_pressure - supplied_source_pressure)
      > pressure_tolerance * pressure_scale
    ):
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=MocPrimitiveStatus.INVARIANT_FAILURE,
        message=(
          'source static pressure does not match its total-pressure/Mach state'
        ),
      )
    ####
  ####
  if exit_pressure <= ambient_pressure:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      message='the expansion-fan source state is not above ambient pressure',
    )
  ####
  pressure_inverse = supersonic_mach_from_stagnation_pressure_ratio(
    total_pressure / ambient_pressure,
    gamma,
  )
  if not pressure_inverse.converged or pressure_inverse.value is None:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=pressure_inverse.status,
      message=pressure_inverse.message,
    )
  ####
  terminal_mach = pressure_inverse.value
  if terminal_mach <= source_state.mach:
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      message='ambient-pressure state is not downstream of the exit state',
    )
  ####
  exit_nu = prandtl_meyer_angle_rad(source_state.mach, gamma)
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
  states: list[CharacteristicState] = []
  centerline_states: list[CharacteristicState] = []
  lip_states: list[CharacteristicState] = []
  centerline_points: list[tuple[float, float]] = []
  lip_ray_centerline_points: list[tuple[float, float]] = []
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
    ####
    mach = inversion.value
    theta = float(source_state.theta_rad) + fraction * total_turn
    mu = mach_angle_rad(mach)
    characteristic_angle = theta - mu
    lip_states.append(
      CharacteristicState(
        x_m=source_point[0],
        y_m=source_point[1],
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
    ####
    x = source_point[0] + (0.0 - source_point[1]) * cos(characteristic_angle) / vertical_component
    if not isfinite(x) or x <= source_point[0] + geometric_tolerance_m:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=MocPrimitiveStatus.GEOMETRY_FAILURE,
        message=f'fan characteristic {index} produced a non-forward centerline point',
      )
    ####
    lip_ray_centerline_points.append((x, 0.0))
    states.append(
      CharacteristicState(
        x_m=x,
        y_m=0.0,
        theta_rad=theta,
        mach=mach,
        gamma=gamma,
      )
    )
    centerline_result = centerline_characteristic_point(
      lip_states[-1],
      CharacteristicFamily.MINUS,
      position_tolerance_m=geometric_tolerance_m,
      invariant_tolerance=pressure_tolerance,
    )
    if not centerline_result.converged or centerline_result.state is None or centerline_result.point_m is None:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=centerline_result.status,
        message=(
          f'fan centerline compatibility state {index} failed: '
          f'{centerline_result.message}'
        ),
      )
    ####
    centerline_states.append(centerline_result.state)
    centerline_points.append(centerline_result.point_m)
  ####
  if any(
    right[0] - left[0] <= geometric_tolerance_m
    for points in (centerline_points, lip_ray_centerline_points)
    for left, right in zip(points, points[1:])
  ):
    return _invalid(
      exit_pressure=exit_pressure,
      ambient_pressure=ambient_pressure,
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      message='fan centerline intersections are not strictly downstream ordered',
    )
  ####
  cells: list[MocExpansionFanCell] = []
  # Fan-cell support must use the direct intersections of the retained source
  # rays.  ``centerline_points`` is an averaged-characteristic compatibility
  # grid and can extend beyond the exact simple-wave ray envelope used by the
  # point sampler.
  for index, (left_point, right_point) in enumerate(
    zip(lip_ray_centerline_points, lip_ray_centerline_points[1:])
  ):
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
    ####
    try:
      midpoint = MocExpansionFanCell(
        cell_index=index,
        vertices_xr_m=(source_point, left_point, right_point),
        state=CharacteristicState(
          x_m=(source_point[0] + left_point[0] + right_point[0]) / 3.0,
          y_m=source_point[1] / 3.0,
          theta_rad=midpoint_theta,
          mach=midpoint_inverse.value,
          gamma=gamma,
        ),
        geometry_status=GeometryStatus.VALID,
      )
    except ValueError as error:
      return _invalid(
        exit_pressure=exit_pressure,
        ambient_pressure=ambient_pressure,
        status=MocPrimitiveStatus.GEOMETRY_FAILURE,
        message=f'fan cell {index} geometry is invalid: {error}',
        source_point=source_point,
      )
    cells.append(midpoint)
  ####
  terminal_pressure = total_pressure / (
    1.0 + 0.5 * (gamma - 1.0) * terminal_mach**2
  ) ** (gamma / (gamma - 1.0))
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
    centerline_states=tuple(centerline_states),
    lip_states=tuple(lip_states),
    centerline_points_m=tuple(centerline_points),
    lip_ray_centerline_points_m=tuple(lip_ray_centerline_points),
    cells=tuple(cells),
    source_point_m=source_point,
    total_pressure_Pa=total_pressure,
    message=(
      ''
      if status is MocPrimitiveStatus.CONVERGED
      else 'ambient-pressure boundary residual exceeded tolerance'
    ),
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
  """Build the nozzle-lip fan through the point-source MOC primitive."""

  source_state = CharacteristicState(
    x_m=0.0,
    y_m=float(exit_state.radius_m),
    theta_rad=float(exit_state.flow_angle_rad),
    mach=float(exit_state.mach),
    gamma=float(exit_state.gas.gamma),
  )
  return solve_source_point_expansion_fan(
    source_state,
    float(exit_state.total_pressure_Pa),
    float(ambient.pressure_Pa),
    characteristic_count=characteristic_count,
    geometric_tolerance_m=geometric_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    source_static_pressure_Pa=float(exit_state.static_pressure_Pa),
  )
####
