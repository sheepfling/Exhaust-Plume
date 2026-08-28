from __future__ import annotations

from dataclasses import replace
from math import atan2, pi, tan

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  CharacteristicFamily,
  MocAmbientBoundarySample,
  MocChainContinuationPolicy,
  MocChainPlannerKind,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCharacteristicCell,
  MocCharacteristicNode,
  MocPhysicalPostShockFieldResult,
  MocPhysicalPostShockFieldStatus,
  MocPhysicalPostShockFieldContinuationSolve,
  MocPhysicalPostShockTerminalPatchTransitionResult,
  MocPrescribedMixedRegimeClosureMock,
  MocPostShockBoundaryState,
  MocPrimitiveStatus,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
  CharacteristicPointResult,
  assemble_ambient_boundary_post_shock_field,
  assemble_ambient_boundary_post_shock_field_with_centerline_reflection,
  assemble_terminal_trace_centerline_patch,
  centerline_characteristic_point,
  continue_ambient_closed_post_shock_chain,
  march_post_shock_ambient_boundary,
  plan_ambient_closed_post_shock_chain,
  plan_ambient_closed_post_shock_chain_terminal_patch,
  plan_ambient_closed_post_shock_chain_terminal_patch_mock,
  plan_ambient_closed_post_shock_chain_terminal_patch_reference,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_ambient_closed_post_shock_chain_cell_from_physical_field_terminal_patch_or_termination,
  solve_ambient_closed_post_shock_terminal_patch_transition,
  solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination,
  validate_ambient_pressure_boundary,
  validate_moc_mesh,
)


def _shock_fit() -> MocShockBoundaryFitResult:
  points = ((0.0, 0.5), (0.2, 0.25), (0.4, 0.0))
  states = tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.0,
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    )
    for point in points
  )
  return MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=states,
    shock_angle_residuals_rad=(0.0,) * len(states),
    maximum_shock_angle_residual_rad=0.0,
  )


def test_coupled_post_shock_field_rejects_an_outer_boundary_without_axis_end() -> None:
  ambient_pressure = 100000.0
  mach = 2.0
  gamma = 1.4
  total_pressure = ambient_pressure * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (gamma / (gamma - 1.0))
  boundary = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=0.0,
        mach=mach,
        gamma=gamma,
      ),
      total_pressure_Pa=total_pressure,
    )
    for index in range(3)
  )

  result = assemble_ambient_boundary_post_shock_field(
    _shock_fit(),
    boundary,
    ambient_pressure,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE
  assert not result.converged
  assert 'ambient boundary must terminate' in result.message


def test_coupled_post_shock_field_requires_an_accepted_ambient_trace() -> None:
  boundary = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=pi / 4.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.8e6,
    )
    for index in range(3)
  )

  result = assemble_ambient_boundary_post_shock_field(
    _shock_fit(),
    boundary,
    100000.0,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.AMBIENT_BOUNDARY_FAILURE
  assert not result.converged
  assert result.ambient_boundary.pressure_residuals


def test_legacy_ambient_field_cannot_promote_without_family_orientation_evidence() -> None:
  boundary = tuple(
    MocAmbientBoundarySample(
      point_m=(float(index), 0.5),
      state=CharacteristicState(
        x_m=float(index),
        y_m=0.5,
        theta_rad=pi / 4.0,
        mach=2.0,
        gamma=1.4,
      ),
      total_pressure_Pa=1.8e6,
    )
    for index in range(3)
  )
  result = assemble_ambient_boundary_post_shock_field(
    _shock_fit(),
    boundary,
    100000.0,
  )
  legacy_converged = replace(
    result,
    status=MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED,
    message='synthetic legacy promotion probe',
  )

  assert legacy_converged.converged
  assert legacy_converged.physical_closure_verified is False
  with pytest.raises(ValueError, match='family orientation'):
    legacy_converged.as_chain_cell(start_x_m=0.0, end_x_m=1.0)


def test_coupled_post_shock_field_accepts_an_explicit_axis_corner_before_axis_gate() -> None:
  shock = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.converged
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  march = march_post_shock_ambient_boundary(
    shock.shock_fit,
    ambient_pressure,
  )
  assert march.converged
  last = march.boundary_samples[-1]
  axis_state = CharacteristicState(
    x_m=last.point_m[0] - last.point_m[1] / tan(0.5 * last.state.theta_rad),
    y_m=0.0,
    theta_rad=0.0,
    mach=last.state.mach,
    gamma=last.state.gamma,
  )
  axis_corner = MocAmbientBoundarySample(
    point_m=(axis_state.x_m, axis_state.y_m),
    state=axis_state,
    total_pressure_Pa=last.total_pressure_Pa,
  )

  result = assemble_ambient_boundary_post_shock_field(
    shock.shock_fit,
    (*march.boundary_samples, axis_corner),
    ambient_pressure,
    position_tolerance_m=1.0e-3,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.AXIS_FAILURE
  assert result.ambient_boundary.converged
  assert result.node_count == 45
  assert result.cell_count == 45
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.ambient_boundary_points_m[-1] == axis_corner.point_m
  assert result.centerline_boundary_points_m[-1] == axis_corner.point_m


def test_centerline_reflection_closes_each_ambient_c_minus_characteristic() -> None:
  shock = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.converged
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  march = march_post_shock_ambient_boundary(
    shock.shock_fit,
    ambient_pressure,
  )
  assert march.converged

  result = assemble_ambient_boundary_post_shock_field_with_centerline_reflection(
    shock.shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED
  assert result.converged
  assert result.physical_closure_verified
  assert result.state_sampling_available
  assert result.upstream_shock_coupling_verified
  assert result.node_count == 45
  assert result.cell_count == 53
  assert len(result.centerline_boundary_points_m) == 10
  assert all(
    abs(point[1]) <= 1.0e-10
    and abs(state.theta_rad) <= 1.0e-10
    for point, state in zip(
      result.centerline_boundary_points_m,
      result.centerline_boundary_states,
      strict=True,
    )
  )
  assert all(result.physical_closure_gates.values())


def test_centerline_reflection_does_not_accept_an_appended_axis_corner() -> None:
  shock = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.2,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  march = march_post_shock_ambient_boundary(
    shock.shock_fit,
    ambient_pressure,
  )
  assert march.converged
  last = march.boundary_samples[-1]
  axis = centerline_characteristic_point(
    last.state,
    CharacteristicFamily.MINUS,
  )
  assert axis.point_m is not None
  assert axis.state is not None
  axis_corner = MocAmbientBoundarySample(
    point_m=axis.point_m,
    state=axis.state,
    total_pressure_Pa=last.total_pressure_Pa,
  )

  result = assemble_ambient_boundary_post_shock_field_with_centerline_reflection(
    shock.shock_fit,
    (*march.boundary_samples, axis_corner),
    ambient_pressure,
  )

  assert result.status is MocPhysicalPostShockFieldStatus.INVALID_INPUT
  assert 'one physical ambient sample per fitted shock sample' in result.message


def _canonical_ambient_closed_field(*, sample_count: int = 9):
  """Return the accepted reflected field used by terminal-patch tests."""

  upstream = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )
  shock = solve_marched_attached_shock_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=sample_count,
  )
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  march = march_post_shock_ambient_boundary(
    shock.shock_fit,
    ambient_pressure,
  )
  assert march.converged
  result = solve_marched_attached_shock_with_ambient_centerline_physical_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.02,
    0.12,
    sample_count=sample_count,
  )
  assert result.field is not None
  assert result.field.physical_closure_verified
  return result.field


def test_accepted_physical_field_projects_to_a_valid_terminal_source_strip() -> None:
  field = _canonical_ambient_closed_field()

  strip = field.as_open_shock_ambient_strip()
  assert strip.status.value == 'converged_open_shock_ambient_strip'
  assert strip.converged
  assert strip.chain_promotion_blocked
  assert strip.node_count == 45
  assert strip.cell_count == 44
  assert strip.topology.connected
  assert strip.topology.forms_closed_zone
  assert strip.topology.nonmanifold_edge_count == 0
  assert strip.terminal_trace_validation.converged
  assert strip.terminal_trace_position_tolerance_m == pytest.approx(1.0e-3)

  patch = assemble_terminal_trace_centerline_patch(strip)
  assert patch.converged
  assert len(patch.axis_points_m) == len(field.centerline_boundary_points_m)
  assert all(
    point[0] == pytest.approx(expected[0], abs=3.0e-3)
    and point[1] == pytest.approx(expected[1], abs=3.0e-3)
    and state.mach == pytest.approx(expected_state.mach, abs=1.0e-8)
    and pressure == pytest.approx(expected_pressure, rel=1.0e-8)
    for point, state, pressure, expected, expected_state, expected_pressure in zip(
      patch.axis_points_m,
      patch.axis_states,
      patch.axis_total_pressure_Pa,
      field.centerline_boundary_points_m,
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )


def test_physical_field_terminal_patch_transition_reaches_typed_normal_shock_stop() -> None:
  field = _canonical_ambient_closed_field()
  current = field.as_coupled_chain_cell(
    start_x_m=0.5,
    end_x_m=field.ambient_boundary_points_m[-1][0],
    cell_index=1,
  )

  decision = solve_ambient_closed_post_shock_chain_cell_from_physical_field_terminal_patch_or_termination(
    current,
    2,
    current.continuation_boundary,
    field,
    end_x_m=2.2,
    sample_count=9,
    trace_position_tolerance_m=1.0e-3,
    position_tolerance_m=1.0e-3,
  )

  assert isinstance(decision, MocChainTerminationDecision)
  assert decision.physical_termination
  assert decision.reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert decision.diagnostics['centerline_seam_verified'] is True
  assert decision.diagnostics['source_strip_report']['cell_count'] == 44
  assert decision.diagnostics['reflection_patch_report']['converged'] is True
  downstream_report = decision.diagnostics['downstream_shock_report']
  assert downstream_report['physical_terminal_verified'] is True
  assert downstream_report['shock']['status'] == 'subsonic_terminal_required'
  assert decision.diagnostics['chain_cell_promotion'] == (
    'blocked-at-mixed-regime-boundary'
  )


def test_physical_field_terminal_patch_transition_retains_mixed_regime_seam() -> None:
  field = _canonical_ambient_closed_field()
  current = field.as_coupled_chain_cell(
    start_x_m=0.5,
    end_x_m=field.ambient_boundary_points_m[-1][0],
    cell_index=1,
  )

  transition = solve_ambient_closed_post_shock_terminal_patch_transition(
    current,
    2,
    current.continuation_boundary,
    field,
    end_x_m=2.2,
    sample_count=9,
    trace_position_tolerance_m=1.0e-3,
    position_tolerance_m=1.0e-3,
  )

  assert isinstance(
    transition,
    MocPhysicalPostShockTerminalPatchTransitionResult,
  )
  assert transition.converged
  assert transition.physical_terminal_verified
  assert transition.physical_closure_verified is False
  assert transition.chain_promotion_blocked
  assert transition.source_strip is not None
  assert transition.reflection_patch is not None
  assert transition.downstream_shock is not None
  assert transition.terminal_field is not None
  assert transition.terminal_field.supersonic_region_closed
  assert transition.mixed_regime_seam_available
  request = transition.as_mixed_regime_perimeter_request()
  assert request.perimeter_supplied is False
  assert request.open_supersonic_zone_is_a_perimeter is False
  assert transition.as_report()['mixed_regime_request']['terminal_point_m'] == (
    request.terminal_point_m
  )


def test_terminal_patch_planner_mock_consumes_exact_retained_seam() -> None:
  field = _canonical_ambient_closed_field()
  planner = plan_ambient_closed_post_shock_chain_terminal_patch_mock(
    field,
    start_x_m=0.5,
    end_x_m=field.ambient_boundary_points_m[-1][0],
    terminal_end_x_m=2.2,
    mock=MocPrescribedMixedRegimeClosureMock(
      streamwise_length_m=0.02,
      transverse_length_m=0.01,
      radial_divisions=2,
    ),
    sample_count=9,
    trace_position_tolerance_m=1.0e-3,
    position_tolerance_m=1.0e-3,
    policy=MocChainContinuationPolicy(
      max_cells=2,
      require_state_carry=True,
    ),
  )

  assert planner.planner_kind is MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK
  assert planner.resolved
  assert planner.physical_termination
  assert planner.physical_closure_verified is False
  assert planner.mixed_regime_closure is not None
  assert planner.mixed_regime_closure.converged
  assert planner.mixed_regime_model_closure_verified
  assert planner.chain_promotion_blocked
  assert planner.transition is not None
  assert planner.transition.mixed_regime_request is not None
  assert planner.mixed_regime_closure.request == (
    planner.transition.mixed_regime_request
  )
  assert planner.diagnostics['mixed_regime_closure_attached'] is False
  assert planner.diagnostics['mixed_regime_model_closure_verified'] is True
  assert planner.as_report()['production_claim_allowed'] is False


def test_terminal_patch_planner_reference_keeps_scalar_result_separate() -> None:
  field = _canonical_ambient_closed_field()
  planner = plan_ambient_closed_post_shock_chain_terminal_patch_reference(
    field,
    start_x_m=0.5,
    end_x_m=field.ambient_boundary_points_m[-1][0],
    terminal_end_x_m=2.2,
    sample_count=9,
    trace_position_tolerance_m=1.0e-3,
    position_tolerance_m=1.0e-3,
    policy=MocChainContinuationPolicy(
      max_cells=2,
      require_state_carry=True,
    ),
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.physical_termination
  assert planner.physical_closure_verified is False
  assert planner.mixed_regime_reference is not None
  assert planner.mixed_regime_reference.converged
  assert planner.mixed_regime_model_closure_verified
  assert planner.chain_promotion_blocked
  assert planner.diagnostics['mixed_regime_closure_attached'] is False


def test_terminal_patch_planner_records_one_seed_and_physical_stop() -> None:
  field = _canonical_ambient_closed_field()
  planner = plan_ambient_closed_post_shock_chain_terminal_patch(
    field,
    start_x_m=0.5,
    end_x_m=field.ambient_boundary_points_m[-1][0],
    terminal_end_x_m=2.2,
    sample_count=9,
    trace_position_tolerance_m=1.0e-3,
    position_tolerance_m=1.0e-3,
    policy=MocChainContinuationPolicy(
      max_cells=2,
      require_state_carry=True,
    ),
  )

  assert planner.production_claim_allowed is False
  assert planner.chain.resolved
  assert planner.chain.physical_termination
  assert planner.chain.termination_reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert planner.chain.cell_count == 1
  assert len(planner.steps) == 1
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.steps[0].result_termination_reason is (
    MocChainTerminationReason.PHYSICAL_TERMINATION
  )
  assert planner.diagnostics['terminal_patch_planner_depth'] == 1
  assert planner.diagnostics['physical_cell_promotion'] == (
    'blocked-at-mixed-regime-boundary'
  )


def test_terminal_patch_transition_rejects_backward_source_interface() -> None:
  field = _canonical_ambient_closed_field()
  current = field.as_coupled_chain_cell(
    start_x_m=0.5,
    end_x_m=field.centerline_boundary_points_m[-1][0],
    cell_index=1,
  )

  decision = solve_ambient_closed_post_shock_chain_cell_from_physical_field_terminal_patch_or_termination(
    current,
    2,
    current.continuation_boundary,
    field,
    end_x_m=2.2,
    sample_count=9,
    trace_position_tolerance_m=1.0e-3,
    position_tolerance_m=1.0e-3,
  )

  assert decision.physical_termination is False
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.diagnostics['centerline_seam_verified'] is True
  assert decision.diagnostics['first_outgoing_trace_point_m'][0] < current.end_x_m


def _manufactured_closed_physical_field(
  incoming_handoff: tuple = (),
  *,
  x_offset_m: float = 0.0,
):
  """Build a small accepted field to exercise the physical chain adapter.

  The characteristic-cell assembler is tested independently above.  This
  manufactured result keeps the chain test focused on its handoff contract;
  it is never used by a product provider or validation report.
  """

  ambient_pressure = 100000.0
  gamma = 1.4
  mach = 2.0
  total_pressure = ambient_pressure * (
    1.0 + 0.5 * (gamma - 1.0) * mach * mach
  ) ** (gamma / (gamma - 1.0))
  centerline_points = tuple(
    (x_m + x_offset_m, y_m)
    for x_m, y_m in ((1.0, 0.0), (1.5, 0.0), (2.0, 0.0))
  )
  centerline_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=0.0,
      mach=mach,
      gamma=gamma,
    )
    for point in centerline_points
  )
  shock_points = tuple(
    (x_m + x_offset_m, y_m)
    for x_m, y_m in ((0.0, 1.0), (0.5, 0.5), (1.0, 0.0))
  )
  upstream_states = tuple(
    CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.1,
      mach=mach,
      gamma=gamma,
    )
    for point in shock_points
  )
  ambient_points = tuple(
    (x_m + x_offset_m, y_m)
    for x_m, y_m in ((0.0, 1.0), (1.0, 0.5), (2.0, 0.0))
  )
  ambient_angle = atan2(-0.5, 1.0)
  ambient_samples = tuple(
    MocAmbientBoundarySample(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=ambient_angle,
        mach=mach,
        gamma=gamma,
      ),
      total_pressure_Pa=total_pressure,
    )
    for point in ambient_points
  )
  ambient_boundary = validate_ambient_pressure_boundary(
    ambient_samples,
    ambient_pressure,
  )
  assert ambient_boundary.converged
  cells = (
    MocCharacteristicCell(
      cell_index=0,
      cell_kind='manufactured-physical-chain-test-cell',
      vertices_xr_m=(shock_points[0], shock_points[1], ambient_points[1]),
      centerline_indices=(0,),
      boundary_indices=(0, 1),
    ),
    MocCharacteristicCell(
      cell_index=1,
      cell_kind='manufactured-physical-chain-test-cell',
      vertices_xr_m=(shock_points[1], shock_points[2], ambient_points[1]),
      centerline_indices=(0,),
      boundary_indices=(0, 1),
    ),
    MocCharacteristicCell(
      cell_index=2,
      cell_kind='manufactured-physical-chain-test-cell',
      vertices_xr_m=(shock_points[2], centerline_points[1], ambient_points[1]),
      centerline_indices=(1, 2),
      boundary_indices=(1, 2),
    ),
    MocCharacteristicCell(
      cell_index=3,
      cell_kind='manufactured-physical-chain-test-cell',
      vertices_xr_m=(centerline_points[1], centerline_points[2], ambient_points[1]),
      centerline_indices=(1, 2),
      boundary_indices=(1, 2),
    ),
  )
  node_point = ambient_points[1]
  node_state = CharacteristicState(
    x_m=node_point[0],
    y_m=node_point[1],
    theta_rad=ambient_angle,
    mach=mach,
    gamma=gamma,
  )
  node_result = CharacteristicPointResult(
    status=MocPrimitiveStatus.CONVERGED,
    state=node_state,
    point_m=node_point,
    invariant_residual_plus=0.0,
    invariant_residual_minus=0.0,
    geometry_residual=0.0,
    iterations=0,
  )
  nodes = (
    MocCharacteristicNode(
      centerline_index=1,
      boundary_index=1,
      point_m=node_point,
      state=node_state,
      point_result=node_result,
      total_pressure_Pa=total_pressure,
    ),
  )
  return MocPhysicalPostShockFieldResult(
    status=MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED,
    characteristic_layer_count=2,
    nodes=nodes,
    cells=cells,
    topology=validate_moc_mesh(cells),
    shock_boundary_points_m=shock_points,
    ambient_boundary_points_m=tuple(sample.point_m for sample in ambient_samples),
    centerline_boundary_points_m=centerline_points,
    centerline_boundary_states=centerline_states,
    centerline_boundary_total_pressure_Pa=(total_pressure, total_pressure, total_pressure),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=0.0,
    maximum_absolute_invariant_residual=0.0,
    minimum_post_shock_total_pressure_ratio=0.8,
    maximum_post_shock_total_pressure_ratio=0.9,
    characteristic_family_orientation_verified=True,
    incoming_handoff_states=tuple(sample.state for sample in incoming_handoff),
    incoming_handoff_total_pressure_Pa=tuple(
      sample.total_pressure_Pa for sample in incoming_handoff
    ),
    upstream_shock_boundary_states=upstream_states,
    upstream_shock_boundary_total_pressure_Pa=(200000.0, 200000.0, 200000.0),
    post_shock_boundary_states=tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.0,
        mach=mach,
        gamma=gamma,
      )
      for point in shock_points
    ),
    post_shock_boundary_total_pressure_Pa=(1.8e6, 1.8e6, 1.8e6),
  )


def test_ambient_closed_physical_field_sampling_is_bounded_and_state_carrying() -> None:
  field = _manufactured_closed_physical_field()

  assert field.state_sampling_available
  state = field.state_at((0.4, 0.6))
  assert state is not None
  assert state.x_m == pytest.approx(0.4)
  assert state.y_m == pytest.approx(0.6)
  assert state.mach > 1.0
  assert field.total_pressure_at((0.4, 0.6)) == pytest.approx(1.8e6)
  assert field.static_pressure_at((0.4, 0.6)) is not None
  assert field.state_at((2.5, 0.1)) is None
  assert field.total_pressure_at((2.5, 0.1)) is None


def test_physical_field_next_shock_returns_bounded_upstream_stop_without_extrapolation() -> None:
  field = _manufactured_closed_physical_field()
  current = field.as_coupled_chain_cell(
    start_x_m=0.0,
    end_x_m=2.0,
    cell_index=1,
  )
  ambient_boundary = tuple(
    MocAmbientBoundarySample(
      point_m=point,
      state=state,
      total_pressure_Pa=pressure,
    )
    for point, state, pressure in zip(
      field.ambient_boundary.points_m,
      field.ambient_boundary.states,
      field.ambient_boundary.total_pressure_Pa,
      strict=True,
    )
  )

  decision = solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination(
    current,
    2,
    current.continuation_boundary,
    field,
    shock_points_m=((2.5, 0.4), (2.7, 0.2), (2.9, 0.0)),
    downstream_flow_angles_rad=(0.1, 0.1, 0.1),
    ambient_boundary=ambient_boundary,
    ambient_pressure_Pa=100000.0,
    end_x_m=3.0,
  )

  assert isinstance(decision, MocChainTerminationDecision)
  assert not decision.physical_termination
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.diagnostics['first_missing_sample_index'] == 0
  assert decision.diagnostics['sampled_count'] == 0


def test_ambient_physical_chain_rejects_an_appended_axis_corner_source() -> None:
  field = _manufactured_closed_physical_field()
  current = field.as_coupled_chain_cell(
    start_x_m=0.0,
    end_x_m=2.0,
    cell_index=1,
  )
  ambient_boundary = tuple(
    MocAmbientBoundarySample(
      point_m=point,
      state=state,
      total_pressure_Pa=pressure,
    )
    for point, state, pressure in zip(
      field.ambient_boundary.points_m,
      field.ambient_boundary.states,
      field.ambient_boundary.total_pressure_Pa,
      strict=True,
    )
  )

  decision = solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination(
    current,
    2,
    current.continuation_boundary,
    field,
    shock_points_m=((2.5, 0.4), (2.7, 0.2), (2.9, 0.0)),
    downstream_flow_angles_rad=(0.1, 0.1, 0.1),
    ambient_boundary=(*ambient_boundary, ambient_boundary[-1]),
    ambient_pressure_Pa=100000.0,
    end_x_m=3.0,
  )

  assert isinstance(decision, MocChainTerminationDecision)
  assert decision.reason is MocChainTerminationReason.INVALID_INPUT
  assert 'explicit axis corner is not a C- source' in decision.message


def test_ambient_closed_physical_chain_requires_exact_incoming_handoff() -> None:
  seed = _manufactured_closed_physical_field()

  def solve_next(current, _next_index, _incoming):
    wrong_handoff = tuple(
      replace(sample, total_pressure_Pa=sample.total_pressure_Pa + 1.0)
      for sample in current.continuation_boundary
    )
    return MocPhysicalPostShockFieldContinuationSolve(
      field=_manufactured_closed_physical_field(wrong_handoff),
      end_x_m=current.end_x_m + 1.0,
    )

  result = continue_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=0.0,
    end_x_m=1.0,
    policy=MocChainContinuationPolicy(max_cells=2),
  )

  assert result.status.value == 'solver-failure'
  assert result.termination_reason is MocChainTerminationReason.SOLVER_ERROR
  assert result.cell_count == 1
  assert 'changed consumed total pressure sample' in result.message


def test_physical_field_promotion_rechecks_mesh_and_declared_boundary_paths() -> None:
  seed = _manufactured_closed_physical_field()
  tampered = replace(
    seed,
    ambient_boundary_points_m=((0.0, 1.0), (1.0, 0.75), (2.0, 0.0)),
  )

  assert seed.physical_closure_verified
  assert all(seed.physical_closure_gates.values())
  assert tampered.physical_closure_verified is False
  assert tampered.physical_closure_gates['physical_boundary_paths_verified'] is False
  with pytest.raises(ValueError, match='ambient-closed post-shock field'):
    tampered.as_chain_cell(start_x_m=0.0, end_x_m=1.0)


def test_ambient_closed_physical_chain_and_planner_carry_multiple_cells() -> None:
  seed = _manufactured_closed_physical_field()

  def solve_next(current, next_index, incoming_handoff):
    if next_index > 3:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message='manufactured physical-field test chain exhausted',
      )
    return MocPhysicalPostShockFieldContinuationSolve(
      field=_manufactured_closed_physical_field(
        incoming_handoff,
        x_offset_m=current.end_x_m,
      ),
      end_x_m=current.end_x_m + 1.0,
    )

  planner = plan_ambient_closed_post_shock_chain(
    seed,
    solve_next,
    start_x_m=0.0,
    end_x_m=1.0,
    policy=MocChainContinuationPolicy(max_cells=8),
  )
  report = planner.as_report()

  assert planner.production_claim_allowed is False
  assert planner.handoff_links_verified is True
  assert planner.chain.resolved is True
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  assert [step.result_kind for step in planner.steps] == [
    'physical-field-solve-returned',
    'physical-field-solve-returned',
    'termination-returned',
  ]
  assert report['steps'][1]['incoming_handoff_link_verified'] is True


def test_ambient_closed_physical_chain_rejects_open_seed_before_callback() -> None:
  seed = _manufactured_closed_physical_field()
  open_seed = replace(seed, characteristic_family_orientation_verified=False)
  called = False

  def solve_next(_current, _next_index, _incoming):
    nonlocal called
    called = True
    return None

  result = continue_ambient_closed_post_shock_chain(
    open_seed,
    solve_next,
    start_x_m=0.0,
    end_x_m=1.0,
  )

  assert result.status.value == 'open-cell'
  assert result.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert called is False
