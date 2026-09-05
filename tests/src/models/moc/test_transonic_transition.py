from __future__ import annotations

from dataclasses import replace
from math import pi

import pytest

from exhaust_plume.models.moc import (
  MocTransonicShockGeometryAuditStatus,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryStatus,
  MocTransonicTransitionAuditStatus,
  MocTransonicTransitionRequest,
  MocTransonicTransitionStatus,
  measure_moc_transonic_shock_geometry,
  measure_moc_transonic_transition,
  solve_moc_transonic_shock_geometry,
  solve_moc_transonic_transition,
)


def test_pressure_below_sonic_bound_gets_an_explicit_normal_shock_reference() -> None:
  request = MocTransonicTransitionRequest(
    upstream_total_pressure_Pa=400_000.0,
    target_downstream_static_pressure_Pa=180_000.0,
    gamma=1.4,
  )

  result = solve_moc_transonic_transition(request)
  audit = measure_moc_transonic_transition(result)

  assert result.status is MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE
  assert result.transition_required
  assert result.converged
  assert result.required_upstream_mach is not None and result.required_upstream_mach > 1.0
  assert result.downstream_mach is not None and result.downstream_mach < 1.0
  assert result.downstream_static_pressure_Pa == pytest.approx(180_000.0, rel=1.0e-10)
  assert result.total_pressure_ratio is not None and 0.0 < result.total_pressure_ratio < 1.0
  assert result.entropy_increase_JpkgK is not None and result.entropy_increase_JpkgK > 0.0
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert audit.status is MocTransonicTransitionAuditStatus.VERIFIED
  assert audit.rederived
  assert audit.converged
  assert audit.physical_closure_verified is False
  assert audit.production_claim_allowed is False
####


def test_transition_can_emit_a_scalar_supersonic_to_subsonic_state_handoff() -> None:
  result = solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=400_000.0,
      target_downstream_static_pressure_Pa=180_000.0,
      gamma=1.4,
      upstream_total_temperature_K=1200.0,
    )
  )
  audit = measure_moc_transonic_transition(result)

  assert result.shock_state is not None
  state = result.shock_state
  assert state.upstream_supersonic
  assert state.downstream_subsonic
  assert state.upstream_static_temperature_K < state.upstream_total_temperature_K
  assert state.downstream_static_temperature_K < state.upstream_total_temperature_K
  assert state.upstream_density_kg_m3 > 0.0
  assert state.downstream_density_kg_m3 > state.upstream_density_kg_m3
  assert state.upstream_speed_m_s > state.downstream_speed_m_s
  assert state.physical_closure_verified is False
  assert state.chain_promotion_blocked
  assert state.production_claim_allowed is False
  assert audit.shock_state_verified
  assert audit.shock_state_conservation_verified
  assert audit.shock_state_mass_flux_residual == pytest.approx(0.0, abs=1.0e-12)
  assert audit.shock_state_momentum_flux_residual == pytest.approx(0.0, abs=1.0e-12)
  assert audit.shock_state_energy_flux_residual == pytest.approx(0.0, abs=1.0e-12)
####


def test_transition_audit_rejects_a_tampered_branch_state() -> None:
  result = solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=400_000.0,
      target_downstream_static_pressure_Pa=180_000.0,
      gamma=1.4,
      upstream_total_temperature_K=1200.0,
    )
  )
  assert result.shock_state is not None
  tampered_state = replace(
    result.shock_state,
    downstream_speed_m_s=result.shock_state.downstream_speed_m_s * 1.01,
  )
  tampered = replace(result, shock_state=tampered_state)

  audit = measure_moc_transonic_transition(tampered)

  assert audit.status is MocTransonicTransitionAuditStatus.RESULT_FAILURE
  assert audit.shock_state_verified is False
  assert audit.shock_state_conservation_verified is False
####


def test_scalar_shock_state_binds_to_caller_owned_normal_geometry() -> None:
  result = solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=400_000.0,
      target_downstream_static_pressure_Pa=180_000.0,
      gamma=1.4,
      upstream_total_temperature_K=1200.0,
      upstream_flow_angle_rad=0.2,
    )
  )
  assert result.shock_state is not None
  geometry = solve_moc_transonic_shock_geometry(
    MocTransonicShockGeometryRequest(
      shock_state=result.shock_state,
      shock_point_m=(1.25, 0.15),
      shock_normal_angle_rad=0.2,
    )
  )
  audit = measure_moc_transonic_shock_geometry(geometry)

  assert geometry.status is MocTransonicShockGeometryStatus.VERIFIED
  assert geometry.geometry_verified
  assert geometry.shock_tangent_angle_rad == pytest.approx(0.2 + 0.5 * pi)
  assert geometry.upstream_tangential_velocity_m_s == pytest.approx(0.0, abs=1.0e-10)
  assert geometry.downstream_tangential_velocity_m_s == pytest.approx(0.0, abs=1.0e-10)
  assert audit.status is MocTransonicShockGeometryAuditStatus.VERIFIED
  assert audit.geometry_binding_verified
  assert geometry.physical_closure_verified is False
  assert geometry.chain_promotion_blocked
  assert geometry.production_claim_allowed is False
####


def test_scalar_shock_geometry_rejects_misaligned_or_tampered_binding() -> None:
  result = solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=400_000.0,
      target_downstream_static_pressure_Pa=180_000.0,
      gamma=1.4,
      upstream_total_temperature_K=1200.0,
    )
  )
  assert result.shock_state is not None
  misaligned = solve_moc_transonic_shock_geometry(
    MocTransonicShockGeometryRequest(
      shock_state=result.shock_state,
      shock_point_m=(1.25, 0.15),
      shock_normal_angle_rad=0.01,
    )
  )
  assert misaligned.status is MocTransonicShockGeometryStatus.FLOW_ALIGNMENT_FAILURE
  assert not measure_moc_transonic_shock_geometry(misaligned).converged

  verified = solve_moc_transonic_shock_geometry(
    MocTransonicShockGeometryRequest(
      shock_state=result.shock_state,
      shock_point_m=(1.25, 0.15),
      shock_normal_angle_rad=0.0,
    )
  )
  tampered = replace(
    verified,
    mass_flux_residual=verified.mass_flux_residual + 1.0e-3,
  )
  tampered_audit = measure_moc_transonic_shock_geometry(tampered)
  assert tampered_audit.status is MocTransonicShockGeometryAuditStatus.RESULT_FAILURE
  assert not tampered_audit.geometry_binding_verified
####


def test_pressure_inside_subsonic_bound_does_not_require_a_transition() -> None:
  request = MocTransonicTransitionRequest(
    upstream_total_pressure_Pa=400_000.0,
    target_downstream_static_pressure_Pa=300_000.0,
    gamma=1.4,
  )

  result = solve_moc_transonic_transition(request)
  audit = measure_moc_transonic_transition(result)

  assert result.status is MocTransonicTransitionStatus.TARGET_REACHABLE_WITHOUT_SHOCK
  assert result.converged
  assert result.transition_required is False
  assert result.required_upstream_mach is None
  assert audit.status is MocTransonicTransitionAuditStatus.VERIFIED
  assert audit.converged
  assert audit.shock_state_verified
####


def test_transition_reference_rejects_target_above_total_pressure() -> None:
  result = solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=400_000.0,
      target_downstream_static_pressure_Pa=450_000.0,
      gamma=1.4,
    )
  )

  assert result.status is MocTransonicTransitionStatus.TARGET_ABOVE_TOTAL_PRESSURE
  assert result.converged is False
  assert result.transition_required is False
  assert measure_moc_transonic_transition(result).status is MocTransonicTransitionAuditStatus.RESULT_FAILURE
####


def test_transition_audit_detects_a_tampered_scalar_result() -> None:
  result = solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=400_000.0,
      target_downstream_static_pressure_Pa=180_000.0,
      gamma=1.4,
    )
  )
  tampered = replace(
    result,
    downstream_total_pressure_Pa=result.downstream_total_pressure_Pa * 1.01,  # type: ignore[operator]
  )

  audit = measure_moc_transonic_transition(tampered)

  assert audit.status is MocTransonicTransitionAuditStatus.RESULT_FAILURE
  assert audit.rederived
  assert audit.production_claim_allowed is False
####
