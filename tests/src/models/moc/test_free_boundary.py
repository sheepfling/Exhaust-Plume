from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocAmbientAttachmentStatus,
  MocAmbientClosureStatus,
  MocChainStatus,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCharacteristicCell,
  MocFreeBoundaryShockStatus,
  MocFieldCoupledPostShockChainReference,
  MocInvariantClosureFamily,
  MocInvariantClosureStatus,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldStatus,
  MocShockCellTransitionStatus,
  MocSourceStripContinuationStatus,
  MocSourceStripRemeshStatus,
  assemble_reflected_characteristic_zone,
  solve_reflected_boundary_trace_extension,
  solve_marched_attached_shock_chain_cell_from_reflected_zone,
  solve_marched_attached_shock_chain_cell_from_reflected_zone_or_termination,
  solve_marched_attached_shock_chain_cell_from_post_shock_field,
  solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination,
  solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure,
  solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination,
  solve_marched_attached_shock_chain_cell,
  solve_marched_attached_shock_chain_cell_or_termination,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_invariant_boundary,
  solve_marched_attached_shock_from_reflected_zone,
  solve_marched_attached_shock_from_source_strip,
  solve_marched_attached_shock_with_ambient_pressure_closure,
  solve_marched_attached_shock_with_ambient_attachment_closure,
  solve_marched_ambient_attachment_shock_cell_transition,
  solve_marched_attached_shock_with_ambient_pressure_closure_from_reflected_zone,
  continue_post_shock_characteristic_chain,
  plan_ambient_pressure_field_chain,
  plan_field_coupled_post_shock_chain_reference,
  plan_post_shock_field_chain,
  solve_reflected_free_boundary,
  assemble_source_characteristic_strip,
  extend_source_characteristic_strip_constant_k_plus,
  solve_marched_attached_shock_with_constant_invariant_closure,
  solve_attached_compression_to_turn,
  prandtl_meyer_angle_rad,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
  validate_moc_mesh,
)
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit
from exhaust_plume.util.aero.shock_validity import ShockBranch


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


def _broad_bounded_field_reference() -> MocPostShockCharacteristicFieldResult:
  """Build a clearly labeled broad domain for continuation-contract tests."""

  points = ((0.5, 0.0), (0.5, 0.5), (2.0, 0.5), (2.0, 0.0))
  cell = MocCharacteristicCell(
    cell_index=0,
    cell_kind='synthetic-bounded-domain',
    vertices_xr_m=points,
    centerline_indices=(0,),
    boundary_indices=(0,),
  )
  states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in points
  )
  continuation_points = (
    (0.5, 0.0),
    (0.75, 0.15),
    (1.3, 0.35),
    (2.0, 0.5),
  )
  continuation_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )
    for point in continuation_points
  )
  return MocPostShockCharacteristicFieldResult(
    status=MocPostShockFieldStatus.CONVERGED_CLOSED,
    characteristic_layer_count=1,
    nodes=(),
    cells=(cell,),
    topology=validate_moc_mesh((cell,)),
    shock_boundary_points_m=points,
    centerline_boundary_points_m=((0.5, 0.0), (2.0, 0.0)),
    upstream_boundary_states=states,
    upstream_boundary_total_pressure_Pa=(100000.0,) * len(states),
    continuation_boundary_states=continuation_states,
    continuation_boundary_total_pressure_Pa=(90000.0,) * len(continuation_states),
    terminal_centerline_state=states[0],
    maximum_geometry_residual_m=0.0,
    maximum_absolute_invariant_residual=0.0,
    minimum_forward_margin_m=1.0,
    upstream_total_pressure_range_Pa=(100000.0, 100000.0),
    downstream_total_pressure_range_Pa=(90000.0, 90000.0),
    minimum_post_shock_total_pressure_ratio=0.9,
    maximum_post_shock_total_pressure_ratio=0.9,
    physical_closure_status='synthetic-bounded-domain-reference',
    shock_closure_status='synthetic-reference',
    maximum_shock_angle_residual_rad=0.0,
    shock_boundary_states=states,
    shock_boundary_total_pressure_Pa=(90000.0,) * len(states),
  )


def test_closed_post_shock_field_exposes_a_bounded_state_pressure_sampler() -> None:
  result = _uniform_reference(9)
  assert result.field is not None
  field = result.field

  for cell in field.cells:
    centroid = tuple(
      sum(point[index] for point in cell.vertices_xr_m) / len(cell.vertices_xr_m)
      for index in (0, 1)
    )
    state = field.state_at(centroid)
    pressure = field.static_pressure_at(centroid)
    total_pressure = field.total_pressure_at(centroid)
    assert state is not None
    assert state.x_m == pytest.approx(centroid[0])
    assert state.y_m == pytest.approx(centroid[1])
    assert state.mach > 1.0
    assert pressure is not None and pressure > 0.0
    assert total_pressure is not None and total_pressure > 0.0

  assert field.state_at((2.0, 0.2)) is None
  assert field.total_pressure_at((2.0, 0.2)) is None
  assert field.static_pressure_at((2.0, 0.2)) is None


def test_field_coupled_next_shock_returns_a_typed_terminal_without_extrapolation() -> None:
  result = _uniform_reference(17)
  assert result.field is not None
  current = result.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=0.9)
  start = (0.92, 0.05)

  decision = solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
    current,
    2,
    current.continuation_boundary,
    result.field,
    start_point_m=start,
    end_x_m=1.4,
    downstream_flow_angle_at=lambda _index, point: 0.12 * point[1] / start[1],
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  assert decision.physical_termination
  assert decision.reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert decision.diagnostics['termination_model'] == 'normal-shock-terminal'
  assert decision.diagnostics['upstream_field_model'] == (
    'bounded-post-shock-characteristic-field'
  )
  assert decision.diagnostics['upstream_sample_count'] == 8

  with pytest.raises(ValueError, match='verified subsonic normal shock'):
    solve_marched_attached_shock_chain_cell_from_post_shock_field(
      current,
      2,
      current.continuation_boundary,
      result.field,
      start_point_m=start,
      end_x_m=1.4,
      downstream_flow_angle_at=lambda _index, point: 0.12 * point[1] / start[1],
      sample_count=9,
      position_tolerance_m=1.0e-8,
    )


def test_field_coupled_next_shock_reports_the_prior_field_domain_boundary() -> None:
  result = _uniform_reference(17)
  assert result.field is not None
  current = result.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=0.9)

  decision = solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
    current,
    2,
    current.continuation_boundary,
    result.field,
    start_point_m=(1.2, 0.1),
    end_x_m=1.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  assert decision.physical_termination is False
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.diagnostics['termination_model'] == (
    'bounded-post-shock-field-boundary'
  )
  assert decision.diagnostics['first_missing_sample_index'] == 0
  assert decision.diagnostics['last_valid_point_m'] is None


def test_field_coupled_planner_audits_the_resolved_field_handoff() -> None:
  result = _uniform_reference(17)
  assert result.field is not None
  seen: list[tuple[bool, int, int]] = []
  start = (0.92, 0.05)

  def start_point_at(field, current, cell_index):
    seen.append((field is result.field, current.cell_index, cell_index))
    return start

  planner = plan_post_shock_field_chain(
    result.field,
    start_x_m=0.5,
    end_x_m=0.9,
    start_point_at=start_point_at,
    downstream_flow_angle_at=lambda _index, point: 0.12 * point[1] / start[1],
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.physical_termination
  assert planner.chain.cell_count == 1
  assert len(planner.steps) == 1
  assert planner.steps[0].boundary_kind.value == 'post-shock-field-perimeter'
  assert planner.steps[0].incoming_handoff_sample_count == len(
    result.field.continuation_boundary_states
  )
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.steps[0].result_status == 'physical-termination'
  assert planner.steps[0].result_termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert planner.steps[0].result_physical_termination is True
  assert seen == [(True, 1, 2)]


def test_field_coupled_planner_re_solves_a_cell_then_stops_at_field_boundary() -> None:
  seed = _broad_bounded_field_reference()
  reference = MocFieldCoupledPostShockChainReference(
    cell_axial_length_m=0.1,
    shock_start_offset_m=0.05,
    shock_start_y_m=0.25,
    downstream_flow_angle_scale_rad_per_m=0.2,
  )

  planner = plan_field_coupled_post_shock_chain_reference(
    seed,
    start_x_m=0.5,
    end_x_m=0.6,
    reference=reference,
  )

  assert planner.chain.status is MocChainStatus.SOLVER_TERMINATED
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.chain.physical_termination is False
  assert planner.chain.cell_count == 2
  assert planner.steps[0].result_kind == 'field-solve-returned'
  assert planner.steps[0].result_status == 'converged_closed'
  assert planner.steps[1].result_kind == 'termination-returned'
  assert planner.steps[1].result_termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.handoff_links_verified is True
  assert planner.diagnostics['field_coupled_chain_reference']['cell_axial_length_m'] == 0.1
  assert planner.diagnostics['field_coupled_chain_reference']['upstream_pressure_model'] == (
    'bounded-previous-post-shock-field'
  )


def test_ambient_pressure_field_chain_adapter_reports_bounded_upstream_stop() -> None:
  result = _uniform_reference(17)
  assert result.field is not None
  current = result.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=0.9)

  decision = solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination(
    current,
    2,
    current.continuation_boundary,
    result.field.state_at,
    result.field.static_pressure_at,
    (1.2, 0.1),
    1.4,
    100000.0,
    0.0,
    0.1,
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  assert decision.physical_termination is False
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.diagnostics['termination_model'] == (
    'ambient-pressure-field-coupled-chain'
  )
  assert decision.diagnostics['upstream_field_model'] == (
    'caller-bounded-state-pressure-field'
  )
  assert decision.diagnostics['ambient_closure_status'] == (
    'ambient_closure_field_failure'
  )
  assert decision.diagnostics['sampled_count'] == 0
  assert decision.diagnostics['first_missing_sample_index'] == 0
  assert decision.diagnostics['last_valid_point_m'] is None

  with pytest.raises(ValueError, match='left the bounded upstream field'):
    solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure(
      current,
      2,
      current.continuation_boundary,
      result.field.state_at,
      result.field.static_pressure_at,
      (1.2, 0.1),
      1.4,
      100000.0,
      0.0,
      0.1,
      sample_count=9,
      position_tolerance_m=1.0e-8,
    )


def test_ambient_pressure_field_chain_planner_preserves_field_on_typed_stop() -> None:
  result = _uniform_reference(17)
  assert result.field is not None
  seen: list[tuple[bool, int, int]] = []

  def start_point_at(field, current, cell_index):
    seen.append((field is result.field, current.cell_index, cell_index))
    return (1.2, 0.1)

  planner = plan_ambient_pressure_field_chain(
    result.field,
    start_x_m=0.5,
    end_x_m=0.9,
    start_point_at=start_point_at,
    ambient_pressure_Pa=100000.0,
    outer_downstream_flow_angle_lower_rad=0.0,
    outer_downstream_flow_angle_upper_rad=0.1,
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.cell_count == 1
  assert planner.chain.physical_termination is False
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert len(planner.steps) == 1
  assert planner.steps[0].boundary_kind.value == 'post-shock-field-perimeter'
  assert planner.steps[0].incoming_handoff_sample_count == len(
    result.field.continuation_boundary_states
  )
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.steps[0].result_termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert seen == [(True, 1, 2)]


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
  assert result.terminal_field is not None
  assert result.terminal_field.converged
  assert result.terminal_field.supersonic_region_closed
  assert result.terminal_field.characteristic_field_evidence_verified
  assert result.terminal_field.mixed_regime_field_complete is False
  assert result.terminal_field.physical_closure_verified is False
  assert result.terminal_field.chain_promotion_blocked is True
  assert result.terminal_field.topology.forms_closed_zone
  assert result.terminal_field.topology.connected
  assert result.terminal_field.node_count == len(result.terminal_field.nodes)
  assert result.terminal_field.node_count > 0
  assert all(
    any(
      node.point_m == pytest.approx(vertex)
      for cell in result.terminal_field.cells
      for vertex in cell.vertices_xr_m
    )
    for node in result.terminal_field.nodes
  )
  assert result.terminal_field.clipped_patch_cell_count > 0
  assert len(result.terminal_field.terminal_shock_upstream_states) == len(
    result.terminal_field.terminal_shock_boundary_points_m
  )
  assert len(result.terminal_field.terminal_shock_upstream_pressure_Pa) == len(
    result.terminal_field.terminal_shock_boundary_points_m
  )
  assert len(result.terminal_field.terminal_shock_supersonic_downstream_states) == (
    len(result.terminal_field.terminal_shock_boundary_points_m) - 1
  )
  assert all(
    sample.state.mach > 1.0
    for sample in result.terminal_field.terminal_shock_supersonic_downstream_states
  )
  assert result.terminal_field.terminal_shock_supersonic_downstream_maximum_angle_residual_rad is not None
  assert result.terminal_field.terminal_shock_supersonic_downstream_maximum_angle_residual_rad <= 1.0e-2
  assert result.terminal_field.terminal_supersonic_downstream_patch_converged
  assert result.terminal_field.terminal_shock_supersonic_downstream_continuation is not None
  assert result.terminal_field.terminal_shock_supersonic_downstream_continuation.status.value == 'converged_open_boundary'
  assert result.terminal_field.terminal_shock_supersonic_downstream_first_layer is not None
  assert result.terminal_field.terminal_shock_supersonic_downstream_first_layer.converged
  assert result.terminal_field.terminal_shock_supersonic_downstream_zone is not None
  assert result.terminal_field.terminal_shock_supersonic_downstream_zone.converged
  assert result.terminal_field.terminal_shock_supersonic_downstream_zone.physical_closure_status == 'open'
  assert result.terminal_field.terminal_shock_supersonic_downstream_zone.cell_count == 119
  assert result.terminal_field.terminal_shock_boundary_edge_count > 0
  assert result.terminal_field.terminal_shock_boundary_coverage_verified
  assert result.terminal_field.terminal_shock_boundary_maximum_geometry_residual_m is not None
  assert result.terminal_field.terminal_shock_boundary_maximum_geometry_residual_m <= 1.0e-8
  mixed_boundary = result.terminal_field.validate_mixed_regime_boundary(())
  assert mixed_boundary.status.value == 'subsonic_field_failure'
  assert mixed_boundary.supersonic_patch_verified
  assert mixed_boundary.physical_closure_verified is False
  assert mixed_boundary.chain_promotion_blocked
  perimeter_request = result.terminal_field.mixed_regime_perimeter_request()
  assert perimeter_request.perimeter_supplied is False
  assert perimeter_request.open_supersonic_zone_is_a_perimeter is False
  assert perimeter_request.terminal_point_m == pytest.approx(
    result.terminal_field.terminal_normal_shock.shock_point_m,
  )
  assert perimeter_request.supersonic_patch == result.terminal_field.terminal_shock_supersonic_downstream_states
  assert perimeter_request.as_report()['status'] == 'mixed-regime-perimeter-required'
  assert perimeter_request.as_report()['supersonic_patch_sample_count'] == 16
  terminal_field_decision = result.terminal_field.as_chain_termination_decision()
  assert terminal_field_decision.physical_termination is False
  assert terminal_field_decision.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert terminal_field_decision.diagnostics['termination_model'] == (
    'terminal-supersonic-region-open-mixed-regime'
  )
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

  decision = solve_marched_attached_shock_chain_cell_from_reflected_zone_or_termination(
    current,
    2,
    current.continuation_boundary,
    zone,
    start_point_m=(1.1, 0.1),
    end_x_m=1.5,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
  )

  assert decision.physical_termination is False
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.diagnostics['termination_model'] == (
    'reflected-zone-upstream-field-boundary'
  )
  assert decision.diagnostics['coupling_status'] == 'outside_reflected_zone_domain'
  assert decision.diagnostics['first_missing_sample_index'] == 0


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


def test_invariant_boundary_march_solves_local_turns_before_field_assembly() -> None:
  def upstream(point: tuple[float, float]) -> CharacteristicState:
    return CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    )

  def invariant_target(_index: int, point: tuple[float, float]) -> float:
    downstream_angle = 0.05 * point[1] / 0.5
    compression = solve_attached_compression_to_turn(
      upstream_mach=2.0,
      gamma=1.4,
      upstream_pressure_Pa=100000.0,
      target_turn_rad=downstream_angle + 0.2,
    )
    assert compression.downstream_mach is not None
    return downstream_angle - prandtl_meyer_angle_rad(
      compression.downstream_mach,
      1.4,
    )

  result = solve_marched_attached_shock_with_invariant_boundary(
    upstream,
    lambda _point: 100000.0,
    (0.5, 0.5),
    CharacteristicFamily.PLUS,
    invariant_target,
    sample_count=9,
    shock_angle_tolerance_rad=0.1,
  )

  assert result.status is MocFreeBoundaryShockStatus.CONVERGED_FIELD
  assert result.converged
  assert result.shock_fit is not None and result.shock_fit.converged
  assert result.field is not None and result.field.converged
  assert result.upstream_states
  assert result.downstream_flow_angles_rad[-1] == pytest.approx(0.0, abs=1.0e-8)


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


def test_source_continuation_retains_caustic_bounded_prefix_on_full_strip_failure() -> None:
  reflected_boundary, ambient = _reflected_boundary_reference()

  result = extend_source_characteristic_strip_constant_k_plus(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    2.0e6,
    ambient.pressure_Pa,
    additional_sample_count=25,
    axis_step_m=0.03,
  )

  assert result.status is MocSourceStripContinuationStatus.STRIP_FAILURE
  assert not result.converged
  assert result.added_sample_count == 25
  assert result.last_converged_strip is not None
  assert result.last_converged_strip.converged
  assert result.last_converged_strip.source_window_count == 23
  assert result.frontier is not None
  assert result.frontier.source_index == 23
  assert result.frontier.valid_index_ranges == ((0, 23),)
  assert result.remesh is not None
  assert result.remesh.status is MocSourceStripRemeshStatus.CAUSTIC_REQUIRES_NEW_FAMILY
  assert result.remesh.failed_boundary_index == 0
  assert result.remesh.caustic_event is not None
  assert result.remesh.caustic_event.detected
  assert result.remesh.chain_termination_available
  assert result.remesh.as_chain_termination_decision().physical_termination is False


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


def test_zero_turn_above_symmetry_line_is_not_classified_as_a_terminal() -> None:
  result = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(point[0], point[1], 0.0, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda index, _point: 0.1 if index == 0 else 0.0,
    sample_count=5,
  )

  assert result.status is MocFreeBoundaryShockStatus.COMPRESSION_FAILURE
  assert result.subsonic_terminal_required is False
  assert result.normal_shock_terminal is None
  assert result.sample_count == 1
  assert 'does not require a positive compression turn' in result.message


def test_zero_turn_is_terminal_only_at_the_requested_symmetry_ordinate() -> None:
  result = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(point[0], point[1], 0.0, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda index, _point: 0.1 * (1.0 - index / 4.0),
    sample_count=5,
  )

  assert result.status is MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
  assert result.terminal_model_verified
  assert result.normal_shock_terminal is not None
  assert result.normal_shock_terminal.shock_point_m is not None
  assert result.normal_shock_terminal.shock_point_m[1] == pytest.approx(0.0)


def test_strong_branch_retains_subsonic_boundary_without_fabricating_moc_state() -> None:
  result = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(point[0], point[1], -0.2, 2.0, 1.4),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_rad=0.0,
    branch=ShockBranch.STRONG,
    sample_count=5,
  )

  assert result.status is MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
  assert result.subsonic_boundary_verified
  assert result.subsonic_shock_boundary is not None
  assert result.subsonic_shock_boundary.branch is ShockBranch.STRONG
  assert result.subsonic_shock_boundary.subsonic
  assert result.normal_shock_terminal is None
  assert result.field is None
  assert result.as_report()['subsonic_boundary_verified'] is True


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


def test_marched_chain_cell_adapter_returns_a_typed_physical_terminal() -> None:
  seed = _uniform_reference(17)
  assert seed.field is not None
  seed_cell = seed.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=1.0)

  terminal = solve_marched_attached_shock_chain_cell_or_termination(
    seed_cell,
    2,
    seed_cell.continuation_boundary,
    start_point_m=(1.2, 0.5),
    end_x_m=1.8,
    upstream_state_at=lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2 * point[1] / 0.5,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_pressure_at=lambda _point: 100000.0,
    downstream_flow_angle_rad=0.0,
    sample_count=9,
  )

  assert terminal.physical_termination
  assert terminal.reason.value == 'physical-termination'
  assert terminal.diagnostics['termination_model'] == 'normal-shock-terminal'
  assert terminal.diagnostics['upstream_sample_count'] == 8


def test_generated_chain_continues_cells_with_exact_state_pressure_handoff() -> None:
  seed = _uniform_reference(17)
  assert seed.field is not None
  observations: list[tuple[int, int, float]] = []

  def solve_next(current, cell_index, handoff):
    observations.append((cell_index, len(handoff), max(
      sample.total_pressure_Pa for sample in handoff
    )))
    if cell_index >= 3:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message='generated chain test exhausted its two-cell fixture',
      )
    upstream_mach = 2.0
    upstream_gamma = 1.4
    pressure_ratio = (1.0 + 0.2 * upstream_mach * upstream_mach) ** (
      upstream_gamma / (upstream_gamma - 1.0)
    )
    upstream_pressure = max(sample.total_pressure_Pa for sample in handoff) / pressure_ratio
    return solve_marched_attached_shock_chain_cell(
      current,
      cell_index,
      handoff,
      start_point_m=(current.end_x_m + 0.2, 0.5),
      end_x_m=current.end_x_m + 0.8,
      upstream_state_at=lambda point: CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.2,
        mach=upstream_mach,
        gamma=upstream_gamma,
      ),
      upstream_pressure_at=lambda _point: upstream_pressure,
      downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
      sample_count=9,
    )

  result = continue_post_shock_characteristic_chain(
    seed.field,
    solve_next,
    start_x_m=0.5,
    end_x_m=1.0,
    require_upstream_shock_coupling=True,
  )

  assert result.status.value == 'solver-terminated'
  assert result.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert result.physical_termination is False
  assert result.cell_count == 2
  assert result.resolved
  assert all(cell.carries_state for cell in result.cells)
  assert result.as_report()['continuation_boundary_maxima_nonincreasing'] is True
  assert [item[0] for item in observations] == [2, 3]
  assert observations[0][1] == len(result.cells[0].continuation_boundary)
  assert observations[1][1] == len(result.cells[1].continuation_boundary)
