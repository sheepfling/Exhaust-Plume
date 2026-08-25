from __future__ import annotations

import pytest

from exhaust_plume.models.moc import (
  MocPrimitiveStatus,
  solve_attached_compression_to_pressure,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch, ShockSolveStatus


def test_attached_weak_compression_reconstructs_target_pressure() -> None:
  result = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=180000.0,
  )

  assert result.converged
  assert result.shock_status is ShockSolveStatus.ATTACHED
  assert result.branch is ShockBranch.WEAK
  assert result.theta_rad == pytest.approx(0.19285624909427315)
  assert result.beta_rad == pytest.approx(0.7064997155064409)
  assert result.downstream_mach == pytest.approx(1.6012815380508714)
  assert result.pressure_residual == pytest.approx(0.0, abs=1.0e-12)


def test_compression_preserves_reason_for_unsupported_pressure_branch() -> None:
  result = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=400000.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is ShockSolveStatus.STRONG_BRANCH_REQUIRED
  assert result.beta_rad is not None
  assert result.theta_rad is None


def test_compression_rejects_pressure_drop() -> None:
  result = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=90000.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is ShockSolveStatus.PRESSURE_BELOW_UPSTREAM


def test_compression_reports_pressure_above_normal_shock_limit() -> None:
  result = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=500000.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is ShockSolveStatus.PRESSURE_ABOVE_NORMAL_SHOCK_LIMIT
