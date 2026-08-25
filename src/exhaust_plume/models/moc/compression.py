"""Planar attached-compression primitives for the isolated MOC lane."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sin, sqrt, tan

from exhaust_plume.models.moc.primitives import MocPrimitiveStatus
from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.util.aero.shock_validity import (
  ShockBranch,
  ShockSolveStatus,
  calculate_oblique_shock_pressure_ratio,
  solve_shock_to_pressure,
)

__all__ = (
  'MocCompressionResult',
  'MocLipShockResult',
  'solve_overexpanded_lip_shock',
  'solve_attached_compression_to_pressure',
)


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
