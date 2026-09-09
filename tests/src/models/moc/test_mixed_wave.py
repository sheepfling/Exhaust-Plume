from __future__ import annotations

import pytest

from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocMixedWavePathStatus,
  MocMixedWaveRegime,
  MocMixedWaveStatus,
  solve_mixed_wave_path,
  solve_mixed_wave_sample,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch


def _state(*, x_m: float = 0.5, theta_rad: float = 0.0) -> CharacteristicState:
  return CharacteristicState(
    x_m=x_m,
    y_m=0.2,
    theta_rad=theta_rad,
    mach=2.0,
    gamma=1.4,
  )
####


def test_signed_compression_uses_attached_shock_and_loses_total_pressure() -> None:
  result = solve_mixed_wave_sample(
    _state(),
    upstream_pressure_Pa=100000.0,
    target_flow_angle_rad=0.1,
  )

  assert result.converged
  assert result.regime is MocMixedWaveRegime.COMPRESSION_SHOCK
  assert result.downstream_state is not None
  assert result.downstream_state.mach > 1.0
  assert result.downstream_pressure_Pa is not None
  assert result.downstream_pressure_Pa > result.upstream_pressure_Pa
  assert result.total_pressure_ratio is not None
  assert 0.0 < result.total_pressure_ratio < 1.0
  assert result.beta_rad is not None
  assert result.turn_residual == pytest.approx(0.0, abs=1.0e-10)
  assert result.pressure_direction_verified
  assert result.entropy_direction_verified
  assert result.chain_promotion_blocked
  assert not result.production_claim_allowed
####


def test_signed_expansion_uses_c_minus_and_preserves_total_pressure() -> None:
  upstream = _state()
  result = solve_mixed_wave_sample(
    upstream,
    upstream_pressure_Pa=100000.0,
    target_flow_angle_rad=-0.1,
  )

  assert result.converged
  assert result.regime is MocMixedWaveRegime.ISENTROPIC_EXPANSION
  assert result.characteristic_family is CharacteristicFamily.MINUS
  assert result.downstream_state is not None
  assert result.downstream_state.mach > upstream.mach
  assert result.downstream_pressure_Pa is not None
  assert result.downstream_pressure_Pa < result.upstream_pressure_Pa
  assert result.total_pressure_ratio == pytest.approx(1.0, abs=1.0e-12)
  assert result.upstream_total_pressure_Pa == pytest.approx(
    result.downstream_total_pressure_Pa,
    rel=1.0e-12,
  )
  assert result.compatibility_residual == pytest.approx(0.0, abs=1.0e-10)
  assert result.pressure_direction_verified
  assert result.entropy_direction_verified
####


def test_zero_strength_wave_is_retained_as_mach_wave() -> None:
  result = solve_mixed_wave_sample(
    _state(),
    upstream_pressure_Pa=100000.0,
    target_flow_angle_rad=0.0,
  )

  assert result.converged
  assert result.regime is MocMixedWaveRegime.MACH_WAVE
  assert result.downstream_state is result.upstream_state
  assert result.pressure_ratio == pytest.approx(1.0)
  assert result.total_pressure_ratio == pytest.approx(1.0)
  assert result.beta_rad == pytest.approx(result.upstream_state.mu_rad)
####


def test_compression_and_expansion_fail_closed_outside_their_domains() -> None:
  detached = solve_mixed_wave_sample(
    _state(),
    upstream_pressure_Pa=100000.0,
    target_flow_angle_rad=0.6,
    branch=ShockBranch.WEAK,
  )
  outside_expansion = solve_mixed_wave_sample(
    _state(),
    upstream_pressure_Pa=100000.0,
    target_flow_angle_rad=-2.0,
  )

  assert detached.status is MocMixedWaveStatus.COMPRESSION_FAILURE
  assert detached.regime is MocMixedWaveRegime.COMPRESSION_SHOCK
  assert not detached.converged
  assert outside_expansion.status is MocMixedWaveStatus.EXPANSION_OUTSIDE_DOMAIN
  assert outside_expansion.regime is MocMixedWaveRegime.ISENTROPIC_EXPANSION
  assert not outside_expansion.converged
####


def test_ordered_path_keeps_compression_expansion_and_mach_lanes_separate() -> None:
  result = solve_mixed_wave_path(
    (_state(x_m=0.5), _state(x_m=1.0), _state(x_m=1.5)),
    (100000.0, 100000.0, 100000.0),
    (0.1, -0.1, 0.0),
  )

  assert result.status is MocMixedWavePathStatus.CONVERGED
  assert result.converged
  assert [sample.regime for sample in result.samples] == [
    MocMixedWaveRegime.COMPRESSION_SHOCK,
    MocMixedWaveRegime.ISENTROPIC_EXPANSION,
    MocMixedWaveRegime.MACH_WAVE,
  ]
  assert dict(result.regime_counts) == {
    'compression_shock': 1,
    'isentropic_expansion': 1,
    'mach_wave': 1,
  }
  assert result.minimum_total_pressure_ratio is not None
  assert result.minimum_total_pressure_ratio < 1.0
  assert result.chain_promotion_blocked
  assert not result.production_claim_allowed
####


def test_path_rejects_non_downstream_source_geometry() -> None:
  result = solve_mixed_wave_path(
    (_state(x_m=1.0), _state(x_m=0.5)),
    (100000.0, 100000.0),
    (0.0, 0.0),
  )

  assert result.status is MocMixedWavePathStatus.INVALID_INPUT
  assert not result.path_geometry_verified
  assert not result.converged
####
