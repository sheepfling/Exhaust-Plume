from __future__ import annotations

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocPrimitiveStatus,
  solve_attached_subsonic_compression_to_turn,
  solve_overexpanded_lip_shock,
  solve_attached_compression_to_pressure,
  solve_attached_compression_to_turn,
  solve_attached_shock_to_centerline,
  solve_normal_shock_terminal,
)
from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit
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
####


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
####


def test_compression_rejects_pressure_drop() -> None:
  result = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=90000.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is ShockSolveStatus.PRESSURE_BELOW_UPSTREAM
####


def test_compression_reports_pressure_above_normal_shock_limit() -> None:
  result = solve_attached_compression_to_pressure(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_pressure_Pa=500000.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is ShockSolveStatus.PRESSURE_ABOVE_NORMAL_SHOCK_LIMIT
####


def test_attached_turn_compression_reconstructs_supersonic_downstream_state() -> None:
  result = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.1,
  )

  assert result.converged
  assert result.shock_status is ShockSolveStatus.ATTACHED
  assert result.branch is ShockBranch.WEAK
  assert result.downstream_flow_angle_rad == pytest.approx(0.1)
  assert result.beta_rad is not None
  assert result.downstream_mach is not None and result.downstream_mach > 1.0
  assert result.downstream_pressure_Pa is not None and result.downstream_pressure_Pa > 100000.0
  assert result.pressure_ratio is not None and result.pressure_ratio > 1.0
  assert result.turn_residual == pytest.approx(0.0, abs=1.0e-12)
  assert result.upstream_total_pressure_Pa is not None
  assert result.downstream_total_pressure_Pa is not None
  assert result.total_pressure_ratio is not None
  assert result.upstream_total_pressure_Pa > result.upstream_pressure_Pa
  assert result.downstream_total_pressure_Pa < result.upstream_total_pressure_Pa
  assert result.total_pressure_ratio == pytest.approx(
    result.downstream_total_pressure_Pa / result.upstream_total_pressure_Pa,
  )
####


def test_strong_attached_compression_is_retained_as_a_typed_subsonic_boundary() -> None:
  upstream = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=0.0,
    mach=2.0,
    gamma=1.4,
  )

  result = solve_attached_subsonic_compression_to_turn(
    upstream,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.05,
    branch=ShockBranch.STRONG,
    shock_point_m=(0.75, 0.25),
  )

  assert result.converged
  assert result.subsonic
  assert result.branch is ShockBranch.STRONG
  assert result.shock_point_m == (0.75, 0.25)
  assert result.downstream_mach is not None and result.downstream_mach < 1.0
  assert result.downstream_pressure_Pa is not None
  assert result.as_report()['branch'] == 'strong'
####


def test_subsonic_boundary_adapter_does_not_promote_a_weak_supersonic_state() -> None:
  result = solve_attached_subsonic_compression_to_turn(
    CharacteristicState(0.5, 0.5, 0.0, 2.0, 1.4),
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.05,
    branch=ShockBranch.WEAK,
  )

  assert result.status is MocPrimitiveStatus.INVARIANT_FAILURE
  assert not result.converged
  assert not result.subsonic
  assert result.downstream_mach is not None and result.downstream_mach > 1.0
####


def test_normal_shock_terminal_returns_explicit_subsonic_state() -> None:
  upstream = CharacteristicState(
    x_m=1.25,
    y_m=0.0,
    theta_rad=0.1,
    mach=2.0,
    gamma=1.4,
  )

  result = solve_normal_shock_terminal(
    upstream,
    upstream_pressure_Pa=100000.0,
    shock_point_m=(1.25, 0.0),
  )

  assert result.converged
  assert result.subsonic
  assert result.shock_point_m == (1.25, 0.0)
  assert result.downstream_flow_angle_rad == pytest.approx(0.1)
  assert result.downstream_mach == pytest.approx(0.5773502691896257)
  assert result.static_pressure_ratio == pytest.approx(4.5)
  assert result.downstream_pressure_Pa == pytest.approx(450000.0)
  assert result.total_pressure_ratio == pytest.approx(0.7208738614847455)
  assert result.upstream_total_pressure_Pa is not None
  assert result.downstream_total_pressure_Pa is not None
  assert result.downstream_total_pressure_Pa < result.upstream_total_pressure_Pa
  assert result.as_report()['subsonic'] is True
####


def test_normal_shock_terminal_rejects_invalid_pressure_without_fabricating_state() -> None:
  result = solve_normal_shock_terminal(
    CharacteristicState(x_m=0.0, y_m=0.0, theta_rad=0.0, mach=2.0, gamma=1.4),
    upstream_pressure_Pa=0.0,
  )

  assert result.status is MocPrimitiveStatus.INVALID_INPUT
  assert not result.converged
  assert result.downstream_mach is None
  assert result.downstream_pressure_Pa is None
####


def test_turn_compression_rejects_a_detached_turn() -> None:
  result = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=1.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is ShockSolveStatus.DETACHED_SHOCK_REQUIRED
  assert result.beta_rad is None
  assert result.downstream_pressure_Pa is None
####


def test_attached_shock_to_centerline_returns_forward_candidate_segment() -> None:
  result = solve_attached_shock_to_centerline(
    CharacteristicState(
      x_m=0.78,
      y_m=0.13,
      theta_rad=-0.2,
      mach=2.6,
      gamma=1.4,
    ),
    upstream_pressure_Pa=101325.0,
  )

  assert result.converged
  assert result.shock_status is ShockSolveStatus.ATTACHED
  assert result.shock_start_m == (0.78, 0.13)
  assert result.shock_end_m is not None
  assert result.shock_end_m[0] > result.shock_start_m[0]
  assert result.shock_end_m[1] == pytest.approx(0.0, abs=1.0e-12)
  assert result.compression is not None
  assert result.compression.downstream_flow_angle_rad == pytest.approx(0.2)
  assert -0.2 + result.compression.downstream_flow_angle_rad == pytest.approx(
    result.target_centerline_flow_angle_rad,
  )
  assert result.geometry_residual_m == pytest.approx(0.0, abs=1.0e-12)
  assert result.downstream_mach is not None and result.downstream_mach > 1.0
  assert result.downstream_pressure_Pa is not None and result.downstream_pressure_Pa > 101325.0
  assert result.downstream_state is not None
  assert result.downstream_state.x_m == pytest.approx(result.shock_end_m[0])
  assert result.downstream_state.y_m == pytest.approx(result.shock_end_m[1], abs=1.0e-12)
  assert result.downstream_state.theta_rad == pytest.approx(0.0)
  assert result.downstream_state.mach == pytest.approx(result.downstream_mach)
  assert result.compression is not None
  assert result.compression.upstream_total_pressure_Pa is not None
  assert result.downstream_total_pressure_Pa is not None
  assert result.total_pressure_ratio is not None and result.total_pressure_ratio < 1.0
  assert result.downstream_total_pressure_Pa < result.compression.upstream_total_pressure_Pa
####


def test_shock_to_centerline_rejects_noncompressive_target() -> None:
  result = solve_attached_shock_to_centerline(
    CharacteristicState(x_m=0.0, y_m=0.1, theta_rad=0.1, mach=2.0, gamma=1.4),
    upstream_pressure_Pa=101325.0,
  )

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock_status is None
  assert result.shock_end_m is None
####


def test_mild_overexpanded_lip_shock_reaches_the_centerline() -> None:
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=300000.0,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )

  result = solve_overexpanded_lip_shock(exit_state, ambient)

  assert result.converged
  assert result.shock_start_m == (0.0, 0.05)
  assert result.centerline_point_m is not None
  assert result.centerline_point_m[0] > 0.0
  assert result.shock is not None
  assert result.shock.downstream_mach is not None
  assert result.shock.downstream_mach > 1.0
####


def test_lip_shock_rejects_an_underexpanded_exit() -> None:
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2000000.0,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )

  result = solve_overexpanded_lip_shock(exit_state, ambient)

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert result.shock is None
####
