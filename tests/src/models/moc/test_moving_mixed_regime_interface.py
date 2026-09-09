from __future__ import annotations

from dataclasses import replace
from exhaust_plume.models.moc import (
  MocMovingMixedRegimeConservativeBoundarySample,
  MocMovingMixedRegimeInterfaceAuditStatus,
  MocMovingMixedRegimeInterfaceRequest,
  MocMovingMixedRegimeInterfaceStatus,
  MocTransonicShockGeometryRequest,
  build_moc_terminal_conservative_boundary_sample,
  measure_moc_moving_mixed_regime_interface,
  prepare_moc_moving_mixed_regime_interface,
  reconstruct_moc_transonic_shock_state,
  solve_moc_transonic_shock_geometry,
)


def _geometry():
  state = reconstruct_moc_transonic_shock_state(
    upstream_total_pressure_Pa=180_000.0,
    gamma=1.4,
    gas_constant_J_kgK=287.05,
    upstream_total_temperature_K=1500.0,
    upstream_mach=3.0,
    upstream_flow_angle_rad=0.0,
  )
  return solve_moc_transonic_shock_geometry(
    MocTransonicShockGeometryRequest(
      shock_state=state,
      shock_point_m=(1.0, 0.0),
      shock_normal_angle_rad=0.0,
    )
  )


def _terminal_sample(geometry, index: int, y_m: float):
  terminal = build_moc_terminal_conservative_boundary_sample(
    geometry,
    index=index,
  )
  return MocMovingMixedRegimeConservativeBoundarySample(
    index=terminal.index,
    point_m=(terminal.point_m[0], y_m),
    conservative_state=terminal.conservative_state,
    normal_m=terminal.normal_m,
    source=terminal.source,
  )


def test_moving_interface_retains_exact_terminal_state_and_stops_on_missing_field_coverage():
  geometry = _geometry()
  request = MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=((1.0, 0.0), (1.1, 0.002)),
    boundary_samples=(_terminal_sample(geometry, 0, 0.0),),
    cross_section_x_m=1.0,
    lower_y_m=0.0,
    upper_y_m=0.08,
    sample_count=5,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.SUBSONIC_FIELD_REQUIRED
  assert result.terminal_geometry_audit.converged
  assert result.terminal_conservative_state_verified
  assert result.interface_geometry_verified
  assert result.conservative_boundary_verified
  assert result.missing_sample_indices == (1, 2, 3, 4)
  assert not result.complete_cross_section_coverage
  assert result.subsonic_field_required
  assert not result.moving_interface_solve_attempted
  assert not result.physical_closure_verified
  assert result.chain_promotion_blocked
  assert not result.production_claim_allowed

  audit = measure_moc_moving_mixed_regime_interface(result)
  assert audit.status is MocMovingMixedRegimeInterfaceAuditStatus.VERIFIED
  assert audit.converged
  assert audit.terminal_geometry_rederived
  assert audit.interface_geometry_rederived
  assert audit.conservative_boundary_rederived
  assert audit.coverage_rederived
  assert audit.claim_flags_verified


def test_moving_interface_accepts_complete_explicit_boundary_without_claiming_field_closure():
  geometry = _geometry()
  samples = tuple(
    _terminal_sample(geometry, index, 0.08 * index / 4.0)
    for index in range(5)
  )
  request = MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=((1.0, 0.0), (1.1, 0.002)),
    boundary_samples=samples,
    cross_section_x_m=1.0,
    lower_y_m=0.0,
    upper_y_m=0.08,
    sample_count=5,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.CONVERGED_BOUNDARY_SEAM
  assert result.boundary_seam_verified
  assert result.complete_cross_section_coverage
  assert result.subsonic_field_required
  assert not result.physical_closure_verified
  assert result.chain_promotion_blocked
  assert not result.production_claim_allowed
  assert measure_moc_moving_mixed_regime_interface(result).converged

  tampered = replace(result, missing_sample_indices=(2,))
  tampered_audit = measure_moc_moving_mixed_regime_interface(tampered)
  assert tampered_audit.status is MocMovingMixedRegimeInterfaceAuditStatus.COVERAGE_FAILURE
  assert not tampered_audit.converged


def test_moving_interface_requires_explicit_geometry_and_does_not_infer_a_trace():
  geometry = _geometry()
  request = MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=((1.0, 0.0),),
    boundary_samples=(_terminal_sample(geometry, 0, 0.0),),
    cross_section_x_m=1.0,
    lower_y_m=0.0,
    upper_y_m=0.08,
    sample_count=5,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.INTERFACE_GEOMETRY_REQUIRED
  assert result.interface_points_m == request.interface_points_m
  assert not result.interface_geometry_verified
  assert result.subsonic_field_required
  assert not result.moving_interface_solve_attempted
