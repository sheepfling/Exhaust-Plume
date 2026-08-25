"""Planar attached-compression primitives for the isolated MOC lane."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isfinite, sin, sqrt, tan

from exhaust_plume.models.moc.primitives import CharacteristicState, MocPrimitiveStatus
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.util.aero.shock_validity import (
  ShockBranch,
  ShockSolveStatus,
  calculate_oblique_shock_pressure_ratio,
  solve_shock_angle,
  solve_shock_to_pressure,
)

__all__ = (
  'MocCompressionResult',
  'MocLipShockResult',
  'MocTurnCompressionResult',
  'MocShockToCenterlineResult',
  'solve_overexpanded_lip_shock',
  'solve_attached_compression_to_pressure',
  'solve_attached_compression_to_turn',
  'solve_attached_shock_to_centerline',
)


def _isentropic_total_pressure(*, static_pressure_Pa: float, mach: float, gamma: float) -> float:
  """Recover total pressure from a calorically-perfect static state."""

  factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  return static_pressure_Pa * factor**(gamma / (gamma - 1.0))
####


@dataclass(frozen=True, slots=True)
class MocCompressionResult:
  """Attached-shock pressure inversion with a supersonic downstream check."""

  status: MocPrimitiveStatus
  shock_status: ShockSolveStatus
  branch: ShockBranch
  upstream_mach: float
  upstream_pressure_Pa: float
  target_pressure_Pa: float
  pressure_ratio: float
  pressure_residual: float | None
  theta_rad: float | None
  beta_rad: float | None
  downstream_mach: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


@dataclass(frozen=True, slots=True)
class MocLipShockResult:
  """An overexpanded lip shock and its first centerline intersection."""

  status: MocPrimitiveStatus
  shock: MocCompressionResult | None
  shock_start_m: tuple[float, float] | None
  centerline_point_m: tuple[float, float] | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


@dataclass(frozen=True, slots=True)
class MocTurnCompressionResult:
  """Attached compression state for a prescribed flow turn.

  This is the state-side primitive needed before a physical recompression
  segment can be placed in a first-cell mesh.  ``target_turn_rad`` is the
  positive turn added by the shock.  No shock location or mesh closure is
  inferred here.
  """

  status: MocPrimitiveStatus
  shock_status: ShockSolveStatus
  branch: ShockBranch
  upstream_mach: float
  upstream_pressure_Pa: float
  target_turn_rad: float
  downstream_flow_angle_rad: float | None
  pressure_ratio: float | None
  turn_residual: float | None
  beta_rad: float | None
  downstream_mach: float | None
  downstream_pressure_Pa: float | None
  message: str = ''
  upstream_total_pressure_Pa: float | None = None
  downstream_total_pressure_Pa: float | None = None
  total_pressure_ratio: float | None = None

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
####


@dataclass(frozen=True, slots=True)
class MocShockToCenterlineResult:
  """Boundary-side attached-shock segment reaching a target symmetry line.

  This result closes only the shock segment geometry and downstream state. It
  is intentionally not a complete first-cell assembly: neighboring
  characteristic zones and their topology remain separate acceptance gates.
  """

  status: MocPrimitiveStatus
  shock_status: ShockSolveStatus | None
  compression: MocTurnCompressionResult | None
  upstream_mach: float
  upstream_pressure_Pa: float
  target_centerline_y_m: float
  target_centerline_flow_angle_rad: float
  shock_start_m: tuple[float, float] | None
  shock_end_m: tuple[float, float] | None
  shock_angle_rad: float | None
  geometry_residual_m: float | None
  downstream_mach: float | None
  downstream_pressure_Pa: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocPrimitiveStatus.CONVERGED
  ####

  @property
  def downstream_total_pressure_Pa(self) -> float | None:
    """Return the candidate post-shock total pressure, when available."""

    return None if self.compression is None else self.compression.downstream_total_pressure_Pa
  ####

  @property
  def total_pressure_ratio(self) -> float | None:
    """Return ``p0,downstream / p0,upstream`` for the candidate shock."""

    return None if self.compression is None else self.compression.total_pressure_ratio
  ####


def solve_overexpanded_lip_shock(
  exit_state: NozzleExitState,
  ambient: AmbientState,
  *,
  branch: ShockBranch = ShockBranch.WEAK,
) -> MocLipShockResult:
  """Solve a mild attached overexpanded lip shock to ambient pressure.

  The shock is only marched from the nozzle lip to its first centerline
  intersection.  Downstream characteristic continuation, separation, and
  shock-train closure remain separate operations.
  """

  if exit_state.static_pressure_Pa >= ambient.pressure_Pa:
    return MocLipShockResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      shock=None,
      shock_start_m=None,
      centerline_point_m=None,
      message='lip-shock primitive requires an overexpanded exit state',
    )
  shock = solve_attached_compression_to_pressure(
    upstream_mach=exit_state.mach,
    gamma=exit_state.gas.gamma,
    upstream_pressure_Pa=exit_state.static_pressure_Pa,
    target_pressure_Pa=ambient.pressure_Pa,
    branch=branch,
  )
  if not shock.converged or shock.beta_rad is None:
    return MocLipShockResult(
      status=shock.status,
      shock=shock,
      shock_start_m=None,
      centerline_point_m=None,
      message=shock.message,
    )
  beta = shock.beta_rad
  tangent = tan(beta)
  if not isfinite(tangent) or tangent <= 0.0:
    return MocLipShockResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      shock=shock,
      shock_start_m=None,
      centerline_point_m=None,
      message='attached lip shock has no finite forward centerline intersection',
    )
  centerline_x = float(exit_state.radius_m) / tangent
  if not isfinite(centerline_x) or centerline_x <= 0.0:
    return MocLipShockResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      shock=shock,
      shock_start_m=None,
      centerline_point_m=None,
      message='attached lip shock centerline intersection is not forward',
    )
  return MocLipShockResult(
    status=MocPrimitiveStatus.CONVERGED,
    shock=shock,
    shock_start_m=(0.0, float(exit_state.radius_m)),
    centerline_point_m=(centerline_x, 0.0),
  )
####


def solve_attached_compression_to_turn(
  *,
  upstream_mach: float,
  gamma: float,
  upstream_pressure_Pa: float,
  target_turn_rad: float,
  branch: ShockBranch = ShockBranch.WEAK,
) -> MocTurnCompressionResult:
  """Solve an attached shock for a prescribed positive flow turn.

  Unlike :func:`solve_attached_compression_to_pressure`, this operation does
  not force a pressure target.  It preserves the theta--beta--Mach branch
  status, reconstructs the downstream supersonic state, and reports the
  pressure rise produced by the turn.  This separation is required for a
  recompression boundary: the shock geometry may be fixed by a flow-turn
  condition while the downstream pressure is a diagnostic.
  """

  if not isfinite(float(upstream_mach)) or upstream_mach <= 1.0:
    raise ValueError('upstream_mach must be finite and greater than one')
  if not isfinite(float(gamma)) or gamma <= 1.0:
    raise ValueError('gamma must be finite and greater than one')
  if not isfinite(float(upstream_pressure_Pa)) or upstream_pressure_Pa <= 0.0:
    raise ValueError('upstream_pressure_Pa must be finite and positive')
  if not isfinite(float(target_turn_rad)) or target_turn_rad < 0.0:
    raise ValueError('target_turn_rad must be finite and non-negative')
  if not isinstance(branch, ShockBranch):
    raise ValueError('branch must be a ShockBranch')
  ####
  upstream_total_pressure = _isentropic_total_pressure(
    static_pressure_Pa=float(upstream_pressure_Pa),
    mach=float(upstream_mach),
    gamma=float(gamma),
  )
  solution = solve_shock_angle(
    theta_rad=float(target_turn_rad),
    mach=float(upstream_mach),
    gamma=float(gamma),
    branch=branch,
  )
  if solution.status is not ShockSolveStatus.ATTACHED or solution.beta_rad is None:
    return MocTurnCompressionResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      shock_status=solution.status,
      branch=solution.branch,
      upstream_mach=float(upstream_mach),
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_turn_rad=float(target_turn_rad),
      downstream_flow_angle_rad=None,
      pressure_ratio=None,
      turn_residual=solution.residual,
      beta_rad=solution.beta_rad,
      downstream_mach=None,
      downstream_pressure_Pa=None,
      upstream_total_pressure_Pa=upstream_total_pressure,
      downstream_total_pressure_Pa=None,
      total_pressure_ratio=None,
      message=solution.message,
    )
  ####
  beta = float(solution.beta_rad)
  theta = float(target_turn_rad)
  normal_mach_upstream = float(upstream_mach) * sin(beta)
  normal_mach_downstream_squared = (
    1.0 + 0.5 * (float(gamma) - 1.0) * normal_mach_upstream**2
  ) / (
    float(gamma) * normal_mach_upstream**2 - 0.5 * (float(gamma) - 1.0)
  )
  denominator = sin(beta - theta)
  downstream_mach = sqrt(normal_mach_downstream_squared) / denominator
  pressure_ratio = calculate_oblique_shock_pressure_ratio(
    mach=float(upstream_mach),
    beta_rad=beta,
    gamma=float(gamma),
  )
  turn_residual = solution.residual
  downstream_pressure = float(upstream_pressure_Pa) * pressure_ratio
  downstream_total_pressure = (
    _isentropic_total_pressure(
      static_pressure_Pa=downstream_pressure,
      mach=downstream_mach,
      gamma=float(gamma),
    )
    if isfinite(downstream_mach) and downstream_mach > 0.0
    else None
  )
  total_pressure_ratio = (
    downstream_total_pressure / upstream_total_pressure
    if downstream_total_pressure is not None
    else None
  )
  if (
    not isfinite(downstream_mach)
    or downstream_mach <= 1.0
    or turn_residual is None
    or abs(turn_residual) > 1.0e-10
  ):
    return MocTurnCompressionResult(
      status=(
        MocPrimitiveStatus.OUTSIDE_DOMAIN
        if not isfinite(downstream_mach) or downstream_mach <= 1.0
        else MocPrimitiveStatus.INVARIANT_FAILURE
      ),
      shock_status=solution.status,
      branch=solution.branch,
      upstream_mach=float(upstream_mach),
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_turn_rad=theta,
      downstream_flow_angle_rad=theta,
      pressure_ratio=pressure_ratio,
      turn_residual=turn_residual,
      beta_rad=beta,
      downstream_mach=downstream_mach,
      downstream_pressure_Pa=downstream_pressure,
      upstream_total_pressure_Pa=upstream_total_pressure,
      downstream_total_pressure_Pa=downstream_total_pressure,
      total_pressure_ratio=total_pressure_ratio,
      message=(
        'attached compression state is not supersonic downstream'
        if not isfinite(downstream_mach) or downstream_mach <= 1.0
        else 'attached compression theta-beta-Mach residual exceeded tolerance'
      ),
    )
  return MocTurnCompressionResult(
    status=MocPrimitiveStatus.CONVERGED,
    shock_status=solution.status,
    branch=solution.branch,
    upstream_mach=float(upstream_mach),
    upstream_pressure_Pa=float(upstream_pressure_Pa),
    target_turn_rad=theta,
    downstream_flow_angle_rad=theta,
    pressure_ratio=pressure_ratio,
    turn_residual=turn_residual,
    beta_rad=beta,
    downstream_mach=downstream_mach,
    downstream_pressure_Pa=downstream_pressure,
    upstream_total_pressure_Pa=upstream_total_pressure,
    downstream_total_pressure_Pa=downstream_total_pressure,
    total_pressure_ratio=total_pressure_ratio,
  )
####


def solve_attached_shock_to_centerline(
  upstream: CharacteristicState,
  *,
  upstream_pressure_Pa: float,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  branch: ShockBranch = ShockBranch.WEAK,
) -> MocShockToCenterlineResult:
  """Construct an attached compression segment from a boundary to symmetry.

  The required compression turn is taken from the upstream flow angle to the
  target centerline flow angle.  The weak/strong attached branch is solved
  first; the shock line is then selected on the downstream-forward side that
  reaches the target ``y`` coordinate.  No neighboring MOC cell is inferred.
  """

  if not isfinite(upstream_pressure_Pa) or upstream_pressure_Pa <= 0.0:
    raise ValueError('upstream_pressure_Pa must be finite and positive')
  if not isfinite(target_centerline_y_m):
    raise ValueError('target_centerline_y_m must be finite')
  if not isfinite(target_centerline_flow_angle_rad):
    raise ValueError('target_centerline_flow_angle_rad must be finite')
  if target_centerline_y_m >= upstream.y_m:
    return MocShockToCenterlineResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      shock_status=None,
      compression=None,
      upstream_mach=upstream.mach,
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_centerline_y_m=float(target_centerline_y_m),
      target_centerline_flow_angle_rad=float(target_centerline_flow_angle_rad),
      shock_start_m=None,
      shock_end_m=None,
      shock_angle_rad=None,
      geometry_residual_m=None,
      downstream_mach=None,
      downstream_pressure_Pa=None,
      message='target symmetry line must be below the upstream boundary point',
    )
  ####
  target_turn = float(target_centerline_flow_angle_rad) - upstream.theta_rad
  if target_turn <= 0.0:
    return MocShockToCenterlineResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      shock_status=None,
      compression=None,
      upstream_mach=upstream.mach,
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_centerline_y_m=float(target_centerline_y_m),
      target_centerline_flow_angle_rad=float(target_centerline_flow_angle_rad),
      shock_start_m=None,
      shock_end_m=None,
      shock_angle_rad=None,
      geometry_residual_m=None,
      downstream_mach=None,
      downstream_pressure_Pa=None,
      message='target symmetry flow angle does not require a positive compression turn',
    )
  ####
  compression = solve_attached_compression_to_turn(
    upstream_mach=upstream.mach,
    gamma=upstream.gamma,
    upstream_pressure_Pa=float(upstream_pressure_Pa),
    target_turn_rad=target_turn,
    branch=branch,
  )
  if not compression.converged or compression.beta_rad is None:
    return MocShockToCenterlineResult(
      status=compression.status,
      shock_status=compression.shock_status,
      compression=compression,
      upstream_mach=upstream.mach,
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_centerline_y_m=float(target_centerline_y_m),
      target_centerline_flow_angle_rad=float(target_centerline_flow_angle_rad),
      shock_start_m=None,
      shock_end_m=None,
      shock_angle_rad=None,
      geometry_residual_m=None,
      downstream_mach=compression.downstream_mach,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      message=compression.message,
    )
  ####
  shock_angle = upstream.theta_rad - compression.beta_rad
  shock_sine = sin(shock_angle)
  if shock_sine >= 0.0:
    return MocShockToCenterlineResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      shock_status=compression.shock_status,
      compression=compression,
      upstream_mach=upstream.mach,
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_centerline_y_m=float(target_centerline_y_m),
      target_centerline_flow_angle_rad=float(target_centerline_flow_angle_rad),
      shock_start_m=(upstream.x_m, upstream.y_m),
      shock_end_m=None,
      shock_angle_rad=shock_angle,
      geometry_residual_m=None,
      downstream_mach=compression.downstream_mach,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      message='attached shock orientation does not reach the target symmetry line downstream',
    )
  shock_parameter = (float(target_centerline_y_m) - upstream.y_m) / shock_sine
  shock_end = (
    upstream.x_m + shock_parameter * cos(shock_angle),
    upstream.y_m + shock_parameter * shock_sine,
  )
  geometry_residual = shock_end[1] - float(target_centerline_y_m)
  if (
    not isfinite(shock_parameter)
    or shock_parameter <= 0.0
    or not all(isfinite(value) for value in shock_end)
    or shock_end[0] <= upstream.x_m
  ):
    return MocShockToCenterlineResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      shock_status=compression.shock_status,
      compression=compression,
      upstream_mach=upstream.mach,
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_centerline_y_m=float(target_centerline_y_m),
      target_centerline_flow_angle_rad=float(target_centerline_flow_angle_rad),
      shock_start_m=(upstream.x_m, upstream.y_m),
      shock_end_m=shock_end,
      shock_angle_rad=shock_angle,
      geometry_residual_m=geometry_residual,
      downstream_mach=compression.downstream_mach,
      downstream_pressure_Pa=compression.downstream_pressure_Pa,
      message='attached shock segment does not reach a forward finite endpoint',
    )
  return MocShockToCenterlineResult(
    status=MocPrimitiveStatus.CONVERGED,
    shock_status=compression.shock_status,
    compression=compression,
    upstream_mach=upstream.mach,
    upstream_pressure_Pa=float(upstream_pressure_Pa),
    target_centerline_y_m=float(target_centerline_y_m),
    target_centerline_flow_angle_rad=float(target_centerline_flow_angle_rad),
    shock_start_m=(upstream.x_m, upstream.y_m),
    shock_end_m=shock_end,
    shock_angle_rad=shock_angle,
    geometry_residual_m=geometry_residual,
    downstream_mach=compression.downstream_mach,
    downstream_pressure_Pa=compression.downstream_pressure_Pa,
  )
####


def solve_attached_compression_to_pressure(
  *,
  upstream_mach: float,
  gamma: float,
  upstream_pressure_Pa: float,
  target_pressure_Pa: float,
  branch: ShockBranch = ShockBranch.WEAK,
) -> MocCompressionResult:
  """Invert an attached compression shock to a target static pressure.

  The result is a state primitive only.  It does not choose a shock location,
  close a plume mesh, or infer a Mach-disk endpoint.  A weak-branch request
  that needs a strong or detached shock is returned as outside the MOC lane's
  current supersonic closure domain, with the aerodynamic status preserved.
  """

  if not isfinite(float(upstream_mach)) or upstream_mach <= 1.0:
    raise ValueError('upstream_mach must be finite and greater than one')
  if not isfinite(float(gamma)) or gamma <= 1.0:
    raise ValueError('gamma must be finite and greater than one')
  if not isfinite(float(upstream_pressure_Pa)) or upstream_pressure_Pa <= 0.0:
    raise ValueError('upstream_pressure_Pa must be finite and positive')
  if not isfinite(float(target_pressure_Pa)) or target_pressure_Pa <= 0.0:
    raise ValueError('target_pressure_Pa must be finite and positive')
  if not isinstance(branch, ShockBranch):
    raise ValueError('branch must be a ShockBranch')
  ####
  solution = solve_shock_to_pressure(
    mach=float(upstream_mach),
    gamma=float(gamma),
    upstream_pressure_Pa=float(upstream_pressure_Pa),
    target_pressure_Pa=float(target_pressure_Pa),
    branch=branch,
  )
  if solution.status is not ShockSolveStatus.ATTACHED or solution.beta_rad is None or solution.theta_rad is None:
    return MocCompressionResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      shock_status=solution.status,
      branch=solution.branch,
      upstream_mach=float(upstream_mach),
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_pressure_Pa=float(target_pressure_Pa),
      pressure_ratio=solution.pressure_ratio,
      pressure_residual=None,
      theta_rad=None,
      beta_rad=solution.beta_rad,
      downstream_mach=None,
      message=solution.message,
    )
  ####
  beta = float(solution.beta_rad)
  theta = float(solution.theta_rad)
  if abs(theta) <= 1.0e-14:
    theta = 0.0
  normal_mach_upstream = float(upstream_mach) * sin(beta)
  normal_mach_downstream_squared = (
    1.0 + 0.5 * (float(gamma) - 1.0) * normal_mach_upstream**2
  ) / (
    float(gamma) * normal_mach_upstream**2 - 0.5 * (float(gamma) - 1.0)
  )
  downstream_mach = sqrt(normal_mach_downstream_squared) / sin(beta - theta)
  reconstructed_ratio = calculate_oblique_shock_pressure_ratio(
    mach=float(upstream_mach),
    beta_rad=beta,
    gamma=float(gamma),
  )
  pressure_residual = (
    float(upstream_pressure_Pa) * reconstructed_ratio - float(target_pressure_Pa)
  ) / float(target_pressure_Pa)
  if not isfinite(downstream_mach) or downstream_mach <= 1.0:
    return MocCompressionResult(
      status=MocPrimitiveStatus.OUTSIDE_DOMAIN,
      shock_status=solution.status,
      branch=solution.branch,
      upstream_mach=float(upstream_mach),
      upstream_pressure_Pa=float(upstream_pressure_Pa),
      target_pressure_Pa=float(target_pressure_Pa),
      pressure_ratio=solution.pressure_ratio,
      pressure_residual=pressure_residual,
      theta_rad=theta,
      beta_rad=beta,
      downstream_mach=downstream_mach,
      message='attached compression state is not supersonic downstream',
    )
  return MocCompressionResult(
    status=(
      MocPrimitiveStatus.CONVERGED
      if abs(pressure_residual) <= 1.0e-10
      else MocPrimitiveStatus.INVARIANT_FAILURE
    ),
    shock_status=solution.status,
    branch=solution.branch,
    upstream_mach=float(upstream_mach),
    upstream_pressure_Pa=float(upstream_pressure_Pa),
    target_pressure_Pa=float(target_pressure_Pa),
    pressure_ratio=solution.pressure_ratio,
    pressure_residual=pressure_residual,
    theta_rad=theta,
    beta_rad=beta,
    downstream_mach=downstream_mach,
    message=(
      ''
      if abs(pressure_residual) <= 1.0e-10
      else 'attached compression pressure residual exceeded tolerance'
    ),
  )
####
