from __future__ import annotations

from dataclasses import replace
from math import atan2

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocMovingMixedRegimeConservativeBoundarySample,
  MocMovingMixedRegimeInterfaceAuditStatus,
  MocMovingMixedRegimeInterfaceRequest,
  MocMovingMixedRegimeInterfaceStatus,
  MocTransonicShockGeometryRequest,
  build_moc_terminal_conservative_boundary_sample,
  fit_euler_consistent_shock_boundary,
  measure_moc_moving_mixed_regime_interface,
  prepare_moc_moving_mixed_regime_interface,
  reconstruct_moc_transonic_shock_state,
  solve_euler_ambient_companion_boundary_reference,
  solve_attached_compression_to_turn,
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


def _two_sided_shock_boundary(geometry):
  points = ((0.0, 0.4), (0.5, 0.2), (1.0, 0.0))
  tangent_angle = atan2(points[1][1] - points[0][1], points[1][0] - points[0][0])
  turn = 0.12
  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100_000.0,
    target_turn_rad=turn,
  )
  assert compression.beta_rad is not None
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=tangent_angle + compression.beta_rad,
      mach=2.0,
      gamma=geometry.request.shock_state.gamma,
    )
    for point in points
  )
  return fit_euler_consistent_shock_boundary(
    upstream_states,
    (100_000.0,) * len(points),
    points,
    (tangent_angle + compression.beta_rad - turn,) * len(points),
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


def test_moving_interface_rejects_supersonic_boundary_profile():
  geometry = _geometry()
  samples = tuple(
    _terminal_sample(geometry, index, 0.08 * index / 4.0)
    for index in range(5)
  )
  supersonic_state = (
    1.0,
    1000.0,
    0.0,
    1000.0 / (1.4 - 1.0) + 0.5 * 1000.0**2,
  )
  request = MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=((1.0, 0.0), (1.1, 0.002)),
    boundary_samples=(
      samples[0],
      replace(samples[1], conservative_state=supersonic_state),
      *samples[2:],
    ),
    cross_section_x_m=1.0,
    lower_y_m=0.0,
    upper_y_m=0.08,
    sample_count=5,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.SUBSONIC_BOUNDARY_REQUIRED
  assert result.maximum_boundary_mach is not None
  assert result.maximum_boundary_mach > 1.0
  assert not result.subsonic_boundary_verified
  assert result.chain_promotion_blocked
  audit = measure_moc_moving_mixed_regime_interface(result)
  assert audit.converged
  assert audit.subsonic_boundary_rederived


def test_moving_interface_remeasures_optional_two_sided_euler_boundary():
  geometry = _geometry()
  boundary = _two_sided_shock_boundary(geometry)
  assert boundary.local_euler_verified
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
    two_sided_shock_boundary=boundary,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.CONVERGED_BOUNDARY_SEAM
  assert result.two_sided_shock_boundary is boundary
  assert result.two_sided_shock_boundary_verified
  assert result.maximum_two_sided_jump_residual is not None
  assert result.maximum_two_sided_jump_residual < 1.0e-8
  audit = measure_moc_moving_mixed_regime_interface(result)
  assert audit.converged
  assert audit.two_sided_shock_boundary_rederived
  assert audit.maximum_two_sided_jump_residual == (
    result.maximum_two_sided_jump_residual
  )
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False


def test_moving_interface_retains_and_remeasures_open_two_sided_companion_field():
  geometry = _geometry()
  boundary = _two_sided_shock_boundary(geometry)
  companion = solve_euler_ambient_companion_boundary_reference(
    boundary,
    100_000.0,
    separation_m=0.5,
  )
  assert companion.converged
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
    two_sided_shock_boundary=boundary,
    two_sided_companion_boundary=companion.samples,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.CONVERGED_BOUNDARY_SEAM
  assert result.two_sided_companion_field is not None
  assert result.two_sided_companion_field.converged
  assert result.two_sided_companion_field_verified
  audit = measure_moc_moving_mixed_regime_interface(result)
  assert audit.converged
  assert audit.two_sided_companion_field_rederived
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False


def test_moving_interface_rejects_tampered_two_sided_companion_field():
  geometry = _geometry()
  boundary = _two_sided_shock_boundary(geometry)
  companion = solve_euler_ambient_companion_boundary_reference(
    boundary,
    100_000.0,
    separation_m=0.5,
  )
  assert companion.converged
  tampered_sample = replace(
    companion.samples[1],
    total_pressure_Pa=companion.samples[1].total_pressure_Pa + 1.0,
  )
  request = MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=((1.0, 0.0), (1.1, 0.002)),
    boundary_samples=tuple(
      _terminal_sample(geometry, index, 0.08 * index / 4.0)
      for index in range(5)
    ),
    cross_section_x_m=1.0,
    lower_y_m=0.0,
    upper_y_m=0.08,
    sample_count=5,
    two_sided_shock_boundary=boundary,
    two_sided_companion_boundary=(
      companion.samples[0],
      tampered_sample,
      *companion.samples[2:],
    ),
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.TWO_SIDED_COMPANION_FIELD_FAILURE
  assert not result.two_sided_companion_field_verified
  assert result.chain_promotion_blocked
  assert not result.production_claim_allowed
  audit = measure_moc_moving_mixed_regime_interface(result)
  assert audit.converged
  assert audit.two_sided_companion_field_rederived


def test_moving_interface_requires_shock_boundary_for_companion_field():
  geometry = _geometry()
  companion = solve_euler_ambient_companion_boundary_reference(
    _two_sided_shock_boundary(geometry),
    100_000.0,
  )
  with pytest.raises(ValueError, match='two_sided_companion_boundary'):
    MocMovingMixedRegimeInterfaceRequest(
      terminal_geometry=geometry,
      interface_points_m=((1.0, 0.0), (1.1, 0.002)),
      boundary_samples=(_terminal_sample(geometry, 0, 0.0),),
      cross_section_x_m=1.0,
      lower_y_m=0.0,
      upper_y_m=0.08,
      sample_count=5,
      two_sided_companion_boundary=companion.samples,
    )


def test_moving_interface_rejects_tampered_two_sided_euler_boundary():
  geometry = _geometry()
  boundary = _two_sided_shock_boundary(geometry)
  samples = tuple(
    _terminal_sample(geometry, index, 0.08 * index / 4.0)
    for index in range(5)
  )
  tampered_boundary = replace(
    boundary,
    downstream_states=(
      replace(boundary.downstream_states[0], mach=boundary.downstream_states[0].mach + 0.01),
      *boundary.downstream_states[1:],
    ),
  )
  request = MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=((1.0, 0.0), (1.1, 0.002)),
    boundary_samples=samples,
    cross_section_x_m=1.0,
    lower_y_m=0.0,
    upper_y_m=0.08,
    sample_count=5,
    two_sided_shock_boundary=tampered_boundary,
  )

  result = prepare_moc_moving_mixed_regime_interface(request)

  assert result.status is MocMovingMixedRegimeInterfaceStatus.TWO_SIDED_SHOCK_BOUNDARY_FAILURE
  assert not result.two_sided_shock_boundary_verified
  assert result.chain_promotion_blocked
  audit = measure_moc_moving_mixed_regime_interface(result)
  assert audit.converged
  assert audit.two_sided_shock_boundary_rederived


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
