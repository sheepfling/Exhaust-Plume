from __future__ import annotations

from math import asin, pi

import pytest

from exhaust_plume.util.aero.oblique_shock import ObliqueShockState
from exhaust_plume.util.aero.flow_state import FlowState
from exhaust_plume.util.aero.shock_validity import (
    ShockBranch,
    ShockSolveStatus,
    calculate_max_attached_turn,
    calculate_oblique_shock_pressure_ratio,
    solve_shock_angle,
    solve_shock_to_pressure,
    theta_beta_mach_residual,
)


def test_zero_turn_uses_branch_specific_limits() -> None:
  weak = solve_shock_angle(theta_rad=0.0, mach=3.0, gamma=1.4, branch=ShockBranch.WEAK)
  strong = solve_shock_angle(theta_rad=0.0, mach=3.0, gamma=1.4, branch=ShockBranch.STRONG)

  assert weak.status is ShockSolveStatus.ATTACHED
  assert strong.status is ShockSolveStatus.ATTACHED
  assert weak.beta_rad == pytest.approx(asin(1.0 / 3.0))
  assert strong.beta_rad == pytest.approx(pi / 2.0)
####


def test_theta_beta_mach_residual_and_branch_ordering() -> None:
  weak = solve_shock_angle(theta_rad=0.2, mach=3.0, gamma=1.4, branch=ShockBranch.WEAK)
  strong = solve_shock_angle(theta_rad=0.2, mach=3.0, gamma=1.4, branch=ShockBranch.STRONG)

  assert weak.beta_rad is not None
  assert strong.beta_rad is not None
  assert weak.beta_rad < strong.beta_rad
  assert weak.residual == pytest.approx(0.0, abs=1.0e-12)
  assert strong.residual == pytest.approx(0.0, abs=1.0e-12)
  assert theta_beta_mach_residual(theta_rad=0.2, beta_rad=weak.beta_rad, mach=3.0, gamma=1.4) == pytest.approx(0.0, abs=1.0e-12)
####


def test_maximum_attached_turn_is_a_local_maximum() -> None:
  mach = 3.0
  gamma = 1.4
  theta_max = calculate_max_attached_turn(mach=mach, gamma=gamma)
  delta = 1.0e-4
  peak = solve_shock_angle(theta_rad=theta_max, mach=mach, gamma=gamma, branch=ShockBranch.WEAK)
  below = solve_shock_angle(theta_rad=theta_max - delta, mach=mach, gamma=gamma, branch=ShockBranch.WEAK)

  assert peak.status is ShockSolveStatus.ATTACHED
  assert below.status is ShockSolveStatus.ATTACHED
  assert theta_max > below.theta_max_rad - 1.0e-12
  assert peak.beta_rad is not None
  assert below.beta_rad is not None
  assert below.beta_rad < peak.beta_rad
####


def test_turn_above_attached_limit_is_structured_detached_result() -> None:
  theta_max = calculate_max_attached_turn(mach=3.0, gamma=1.4)
  result = solve_shock_angle(theta_rad=theta_max + 1.0e-3, mach=3.0, gamma=1.4, branch=ShockBranch.WEAK)

  assert result.status is ShockSolveStatus.DETACHED_SHOCK_REQUIRED
  assert result.beta_rad is None
####


def test_target_pressure_inversion_uses_normal_mach_and_beta() -> None:
  mach = 4.13
  gamma = 1.33
  upstream_pressure = 31713.7
  target_pressure = 54479.2
  result = solve_shock_to_pressure(
      mach=mach,
      gamma=gamma,
      upstream_pressure_Pa=upstream_pressure,
      target_pressure_Pa=target_pressure,
  )

  assert result.status is ShockSolveStatus.ATTACHED
  assert result.branch is ShockBranch.WEAK
  assert result.beta_rad == pytest.approx(18.0 * pi / 180.0, abs=1.0e-5)
  assert result.theta_rad is not None
  assert result.beta_rad is not None
  assert result.residual == pytest.approx(0.0, abs=1.0e-12)
  assert calculate_oblique_shock_pressure_ratio(mach=mach, beta_rad=result.beta_rad, gamma=gamma) == pytest.approx(result.pressure_ratio)
####


def test_pressure_validity_and_weak_only_policy() -> None:
  mach = 3.0
  gamma = 1.4
  upstream_pressure = 100.0
  theta_max = calculate_max_attached_turn(mach=mach, gamma=gamma)
  del theta_max
  weak_result = solve_shock_to_pressure(
      mach=mach,
      gamma=gamma,
      upstream_pressure_Pa=upstream_pressure,
      target_pressure_Pa=upstream_pressure * 1.2,
  )
  assert weak_result.status is ShockSolveStatus.ATTACHED
  assert weak_result.branch is ShockBranch.WEAK
  assert solve_shock_to_pressure(
      mach=mach,
      gamma=gamma,
      upstream_pressure_Pa=upstream_pressure,
      target_pressure_Pa=upstream_pressure * 0.9,
  ).status is ShockSolveStatus.PRESSURE_BELOW_UPSTREAM

  max_ratio = 1.0 + (2.0 * gamma / (gamma + 1.0)) * (mach**2 - 1.0)
  above = solve_shock_to_pressure(
      mach=mach,
      gamma=gamma,
      upstream_pressure_Pa=upstream_pressure,
      target_pressure_Pa=upstream_pressure * (max_ratio + 0.1),
  )
  assert above.status is ShockSolveStatus.PRESSURE_ABOVE_NORMAL_SHOCK_LIMIT

  strong_pressure = upstream_pressure * calculate_oblique_shock_pressure_ratio(mach=mach, beta_rad=1.2, gamma=gamma)
  weak_only = solve_shock_to_pressure(
      mach=mach,
      gamma=gamma,
      upstream_pressure_Pa=upstream_pressure,
      target_pressure_Pa=strong_pressure,
      weak_only=True,
  )
  assert weak_only.status is ShockSolveStatus.STRONG_BRANCH_REQUIRED
####


def test_downstream_state_conserves_total_temperature_and_loses_total_pressure() -> None:
  upstream = FlowState(
      mach=3.0,
      static_pressure=100_000.0,
      static_temperature=300.0,
      static_density=100_000.0 / (287.05 * 300.0),
      gamma=1.4,
  )
  downstream = ObliqueShockState.fromUpstreamState(upstream, oblique_angle_deg=10.0)

  assert downstream.total_temperature == pytest.approx(upstream.total_temperature, rel=1.0e-10)
  assert downstream.total_pressure < upstream.total_pressure
  assert downstream.static_pressure > upstream.static_pressure
####
