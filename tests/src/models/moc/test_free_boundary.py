from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientAttachmentStatus,
  MocAmbientClosureStatus,
  MocFreeBoundaryShockStatus,
  MocInvariantClosureFamily,
  MocInvariantClosureStatus,
  MocShockCellTransitionStatus,
  MocSourceStripContinuationStatus,
  assemble_reflected_characteristic_zone,
  solve_reflected_boundary_trace_extension,
  solve_marched_attached_shock_chain_cell_from_reflected_zone,
  solve_marched_attached_shock_chain_cell,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_from_reflected_zone,
  solve_marched_attached_shock_from_source_strip,
  solve_marched_attached_shock_with_ambient_pressure_closure,
  solve_marched_attached_shock_with_ambient_attachment_closure,
  solve_marched_ambient_attachment_shock_cell_transition,
  solve_marched_attached_shock_with_ambient_pressure_closure_from_reflected_zone,
  solve_reflected_free_boundary,
  assemble_source_characteristic_strip,
  extend_source_characteristic_strip_constant_k_plus,
  solve_marched_attached_shock_with_constant_invariant_closure,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit


def _uniform_reference(sample_count: int):
  return solve_uniform_attached_shock_field(
    CharacteristicState(
      x_m=0.5,
      y_m=0.5,
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=sample_count,
  )


def _reflected_boundary_reference():
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  return solve_reflected_free_boundary(fan, exit_state, ambient), ambient


def test_marched_attached_shock_generates_and_closes_the_field() -> None:
  result = _uniform_reference(17)

  assert result.status is MocFreeBoundaryShockStatus.CONVERGED_FIELD
  assert result.converged
  assert result.physical_closure_verified
  assert result.sample_count == 17
  assert result.endpoint_m is not None
  assert result.endpoint_m[1] == pytest.approx(0.0, abs=1.0e-12)
  assert result.maximum_shock_angle_residual_rad is not None
  assert result.maximum_shock_angle_residual_rad < 1.0e-2
  assert result.field is not None
  assert result.field.converged
  assert result.field.upstream_shock_coupling_verified
  assert result.field.topology.forms_closed_zone
  assert result.field.topology.nonmanifold_edge_count == 0
  assert result.field.shock_closure_status == 'solver-generated-marched-attached-shock'
  assert result.field.pressure_loss_verified
  assert result.field.as_chain_cell(start_x_m=0.5, end_x_m=1.0).resolved
  assert result.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=1.0).resolved


def test_marched_attached_shock_refines_endpoint_and_tangent_residual() -> None:
  coarse = _uniform_reference(9)
  medium = _uniform_reference(17)
  fine = _uniform_reference(33)

  assert coarse.converged and medium.converged and fine.converged
  assert coarse.maximum_shock_angle_residual_rad is not None
  assert medium.maximum_shock_angle_residual_rad is not None
  assert fine.maximum_shock_angle_residual_rad is not None
  assert medium.maximum_shock_angle_residual_rad < coarse.maximum_shock_angle_residual_rad
  assert fine.maximum_shock_angle_residual_rad < medium.maximum_shock_angle_residual_rad
  assert coarse.endpoint_m is not None
  assert medium.endpoint_m is not None
  assert fine.endpoint_m is not None
  assert abs(fine.endpoint_m[0] - medium.endpoint_m[0]) < abs(
    medium.endpoint_m[0] - coarse.endpoint_m[0]
  )


def test_reflected_boundary_trace_extension_is_explicitly_labeled() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()

  result = solve_reflected_boundary_trace_extension(
    reflected_boundary,
    ambient.pressure_Pa,
    sample_count=17,
  )

  assert result.converged
  assert result.field is not None
  assert result.field.shock_closure_status == 'reflected-boundary-trace-extension'
  assert result.field.physical_closure_verified
  assert result.endpoint_m is not None
  assert result.endpoint_m[1] == pytest.approx(0.0, abs=1.0e-12)


def test_reflected_zone_shock_solver_keeps_upstream_coverage_domain_bounded() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
  )
  start = reflected_boundary.boundary_points_m[-1]

  result = solve_marched_attached_shock_from_reflected_zone(
    zone,
    start,
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start[1]),
    ),
    sample_count=9,
  )

  assert result.shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  assert not result.converged
  assert not result.upstream_coupling_verified
  assert result.coupling.status.value == 'outside_reflected_zone_domain'
  assert result.coupling.sampled_count == 1
  assert result.coupling.first_missing_sample_index == 1
  assert result.as_report()['downstream_condition_status'] == 'caller-supplied'


def test_ambient_pressure_closure_rejects_a_non_straddling_outer_angle_bracket() -> None:
  state = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )

  result = solve_marched_attached_shock_with_ambient_pressure_closure(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=state.theta_rad,
      mach=state.mach,
      gamma=state.gamma,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    100000.0,
    -0.05,
    0.05,
    sample_count=17,
  )

  assert result.status is MocAmbientClosureStatus.BOUNDARY_BRACKET_FAILURE
  assert not result.converged
  assert result.ambient_boundary is not None
  assert result.ambient_boundary.status.value == 'pressure_failure'
  assert 'does not straddle' in result.message


def test_ambient_pressure_closure_does_not_promote_a_pressure_root_without_tangency() -> None:
  state = CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4)

  result = solve_marched_attached_shock_with_ambient_pressure_closure(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=state.theta_rad,
      mach=state.mach,
      gamma=state.gamma,
    ),
    lambda _point: 55000.0,
    (0.5, 0.5),
    100000.0,
    -0.05,
    0.02,
    sample_count=17,
    closure_tolerance=1.0e-4,
    maximum_shooting_iterations=8,
  )

  assert result.status is MocAmbientClosureStatus.AMBIENT_BOUNDARY_FAILURE
  assert not result.converged
  assert result.ambient_boundary is not None
  assert result.ambient_boundary.maximum_absolute_tangent_residual is not None
  assert result.ambient_boundary.maximum_absolute_tangent_residual > 1.0e-2
  assert not result.physical_closure_verified


def test_ambient_attachment_closure_matches_shock_attachment_and_keeps_strip_open() -> None:
  reference = _uniform_reference(17)
  assert reference.shock_fit is not None
  first = reference.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))

  result = solve_marched_attached_shock_with_ambient_attachment_closure(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.0,
    0.1,
    sample_count=17,
  )

  assert result.status is MocAmbientAttachmentStatus.CONVERGED_OPEN_STRIP
  assert result.converged
  assert result.outer_downstream_flow_angle_rad == pytest.approx(0.05, abs=1.0e-10)
  assert result.attachment_pressure_residual == pytest.approx(0.0, abs=1.0e-10)
  assert result.shock is not None and result.shock.converged
  assert result.ambient_march is not None and result.ambient_march.converged
  assert result.strip is not None and result.strip.converged
  assert result.strip.physical_closure_verified is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True


def test_ambient_attachment_closure_rejects_a_non_straddling_pressure_bracket() -> None:
  result = solve_marched_attached_shock_with_ambient_attachment_closure(
    lambda point: CharacteristicState(point[0], point[1], -0.2, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    300000.0,
    0.0,
    0.05,
    sample_count=9,
  )

  assert result.status is MocAmbientAttachmentStatus.BOUNDARY_BRACKET_FAILURE
  assert not result.converged
  assert result.chain_promotion_blocked is True
  assert 'does not straddle' in result.message


def test_ambient_attachment_transition_carries_a_next_shock_handoff_to_terminal() -> None:
  reference = _uniform_reference(17)
  assert reference.shock_fit is not None
  first = reference.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))

  result = solve_marched_ambient_attachment_shock_cell_transition(
    lambda point: CharacteristicState(point[0], point[1], -0.2, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.0,
    0.1,
    sample_count=17,
  )

  assert result.status is MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
  assert result.converged
  assert result.physical_termination
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True
  assert result.reflection_patch is not None
  assert result.reflection_patch.converged
  assert len(result.next_shock_handoff) >= 3
  assert result.downstream_shock is not None
  assert result.downstream_shock.physical_terminal_verified
  decision = result.as_physical_termination_decision()
  assert decision.physical_termination
  assert decision.diagnostics['termination_model'] == 'normal-shock-terminal'
  report = result.as_report()
  assert report['downstream_condition_status'] == 'centerline-normal-shock-reference'
  assert report['next_shock_handoff_sample_count'] == len(result.next_shock_handoff)
  assert report['physical_closure_verified'] is False


def test_reflected_zone_ambient_closure_keeps_upstream_coverage_domain_bounded() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
  )
  start = reflected_boundary.boundary_points_m[-1]

  result = solve_marched_attached_shock_with_ambient_pressure_closure_from_reflected_zone(
    zone,
    start,
    ambient.pressure_Pa,
    -0.05,
    0.02,
    sample_count=9,
  )

  assert not result.converged
  assert not result.upstream_coupling_verified
  assert result.coupling.status.value == 'outside_reflected_zone_domain'
  assert result.coupling.sampled_count == 1
  assert result.coupling.first_missing_sample_index == 1
  assert result.closure.status is MocAmbientClosureStatus.FIELD_FAILURE
  assert result.closure.upstream_coupling_verified is False
  assert result.as_report()['physical_closure_verified'] is False
  with pytest.raises(ValueError, match='ambient closure'):
    result.as_chain_cell(start_x_m=start[0], end_x_m=start[0] + 0.5)
  with pytest.raises(ValueError, match='ambient closure'):
    result.closure.as_coupled_chain_cell(
      start_x_m=start[0],
      end_x_m=start[0] + 0.5,
    )


def test_reflected_zone_chain_adapter_rejects_a_shock_outside_the_solved_zone() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=2.0e6,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
  )
  seed = _uniform_reference(17)
  assert seed.field is not None
  current = seed.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=1.0)

  with pytest.raises(ValueError, match='did not converge'):
    solve_marched_attached_shock_chain_cell_from_reflected_zone(
      current,
      2,
      current.continuation_boundary,
      zone,
      start_point_m=(1.1, 0.1),
      end_x_m=1.5,
      downstream_flow_angle_rad=0.05,
      sample_count=9,
    )


def test_source_strip_march_stops_at_the_first_missing_upstream_sample() -> None:
  reflected_boundary, _ambient = _reflected_boundary_reference()
  assert reflected_boundary.centerline_states
  strip = assemble_source_characteristic_strip(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    2.0e6,
  )
  assert strip.converged

  result = solve_marched_attached_shock_from_source_strip(
    strip,
    reflected_boundary.boundary_points_m[-1],
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / reflected_boundary.boundary_points_m[-1][1]),
    ),
    sample_count=9,
  )

  assert result.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  assert result.sample_count == 1
  assert result.endpoint_m == pytest.approx(reflected_boundary.boundary_points_m[-1])


def test_constant_k_plus_source_strip_extension_advances_the_shock_probe() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()
  result = extend_source_characteristic_strip_constant_k_plus(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    2.0e6,
    ambient.pressure_Pa,
    additional_sample_count=12,
    axis_step_m=0.03,
  )

  assert result.status is MocSourceStripContinuationStatus.CONVERGED_EXTENDED
  assert result.converged
  assert result.added_sample_count == 12
  assert result.strip is not None
  assert result.strip.converged
  assert result.strip.node_count == 231
  assert result.strip.cell_count == 230
  assert result.strip.minus_source_states[-1].x_m > reflected_boundary.boundary_points_m[-1][0]

  probe = solve_marched_attached_shock_from_source_strip(
    result.strip,
    reflected_boundary.boundary_points_m[-1],
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / reflected_boundary.boundary_points_m[-1][1]),
    ),
    sample_count=17,
  )

  assert probe.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  assert probe.sample_count > 1
  assert probe.endpoint_m is not None
  assert probe.endpoint_m[0] > reflected_boundary.boundary_points_m[-1][0]


def test_source_continuation_can_select_an_explicit_terminal_window() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()

  result = extend_source_characteristic_strip_constant_k_plus(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    2.0e6,
    ambient.pressure_Pa,
    additional_sample_count=12,
    axis_step_m=0.03,
    source_window_start_index=2,
  )

  assert result.status is MocSourceStripContinuationStatus.CONVERGED_TERMINAL_WINDOW
  assert result.converged
  assert result.full_strip is not None and result.full_strip.converged
  assert result.strip is not None
  assert result.strip.is_terminal_source_window
  assert result.strip.source_window_start_index == 2
  assert result.strip.source_window_total_count == 21
  assert result.strip.node_count < result.full_strip.node_count


def test_invariant_closure_rejects_a_non_bracket_before_marching() -> None:
  reflected_boundary, _ambient = _reflected_boundary_reference()
  strip = assemble_source_characteristic_strip(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    2.0e6,
  )
  start = reflected_boundary.boundary_points_m[-1]

  result = solve_marched_attached_shock_with_constant_invariant_closure(
    strip,
    start,
    MocInvariantClosureFamily.K_PLUS,
    invariant_target_lower=-0.7,
    invariant_target_upper=-0.8,
  )

  assert result.status is MocInvariantClosureStatus.INVALID_INPUT
  assert not result.converged
  assert 'lower target' in result.message


def test_uniform_constant_turn_rejects_zero_area_field() -> None:
  result = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.0,
    sample_count=9,
  )

  assert result.status is MocFreeBoundaryShockStatus.FIELD_FAILURE
  assert not result.converged
  assert result.field is not None
  assert 'zero_area' in result.message


def test_zero_turn_symmetry_endpoint_reports_subsonic_terminal_boundary() -> None:
  result = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(point[0], point[1], 0.0, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_rad=0.0,
    sample_count=5,
  )

  assert result.status is MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
  assert result.subsonic_terminal_required
  assert not result.converged
  assert 'subsonic terminal model' in result.message
  assert result.normal_shock_terminal is not None
  assert result.normal_shock_terminal.converged
  assert result.normal_shock_terminal.subsonic
  assert result.terminal_model_verified
  assert result.normal_shock_terminal.shock_point_m is not None


def test_marched_shock_rejects_an_upstream_state_not_at_the_shock_point() -> None:
  result = solve_marched_attached_shock_field(
    lambda _point: CharacteristicState(0.0, 0.5, -0.2, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_rad=0.0,
    sample_count=5,
  )

  assert result.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  assert not result.converged
  assert 'does not lie' in result.message


def test_marched_chain_cell_consumes_the_prior_terminal_trace() -> None:
  seed = _uniform_reference(17)
  assert seed.field is not None
  seed_cell = seed.field.as_chain_cell(start_x_m=0.5, end_x_m=1.0)

  upstream = CharacteristicState(0.0, 0.5, -0.2, 2.0, 1.4)
  continued = solve_marched_attached_shock_chain_cell(
    seed_cell,
    2,
    seed_cell.continuation_boundary,
    start_point_m=(1.2, 0.5),
    end_x_m=1.8,
    upstream_state_at=lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=upstream.theta_rad,
      mach=upstream.mach,
      gamma=upstream.gamma,
    ),
    upstream_pressure_at=lambda _point: 100000.0,
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )

  assert continued.field.converged
  assert continued.end_x_m == pytest.approx(1.8)
  assert continued.field.carries_incoming_handoff
  assert continued.field.incoming_handoff_states == tuple(
    sample.state for sample in seed_cell.continuation_boundary
  )
  assert continued.field.incoming_handoff_total_pressure_Pa == tuple(
    sample.total_pressure_Pa for sample in seed_cell.continuation_boundary
  )
