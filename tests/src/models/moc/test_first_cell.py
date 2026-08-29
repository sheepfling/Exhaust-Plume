from __future__ import annotations

from dataclasses import replace
from math import atan2, sqrt

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocFirstCellCompositeStatus,
  MocFirstCellTerminalClosurePlannerResult,
  MocFirstCellTerminalClosureStatus,
  MocMixedRegimeControlSection,
  MocMixedRegimeFieldSample,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionStatus,
  MocMixedRegimePerimeterRequest,
  MocMixedRegimePlanarPotentialReference,
  MocMixedRegimePlanarFrozenProfileReference,
  MocPrescribedMixedRegimeClosureMock,
  MocSolverGeneratedMixedRegimeClosureReference,
  MocTerminalBoundaryGraphStatus,
  MocChainTerminationReason,
  assemble_ambient_shock_characteristic_strip,
  assemble_first_cell_terminal_shock_field,
  assemble_first_cell_composite,
  assemble_terminal_trace_centerline_patch,
  march_post_shock_ambient_boundary,
  plan_first_cell_terminal_closure,
  plan_prescribed_first_cell_terminal_closure_mock,
  plan_solver_generated_first_cell_terminal_closure_reference,
  plan_solver_generated_first_cell_terminal_closure_reference_from_control_section,
  plan_solver_generated_first_cell_terminal_closure_reference_from_control_section_flux,
  plan_first_cell_terminal_closure_with_planar_handoff,
  plan_first_cell_terminal_closure_with_planar_potential_reference,
  plan_first_cell_terminal_closure_with_planar_frozen_profile_reference,
  solve_mixed_regime_subsonic_field,
  solve_marched_first_cell_terminal_closure,
  solve_marched_attached_shock_field,
)
from exhaust_plume.validation.moc_measurements import (
  MocShockCellObservation,
  measure_moc_shock_cell,
)


def _first_cell_inputs():
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
  strip = assemble_ambient_shock_characteristic_strip(
    shock.shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )
  patch = assemble_terminal_trace_centerline_patch(
    strip,
    trace_position_tolerance_m=1.0e-3,
  )
  assert patch.converged
  return shock.shock_fit, strip, patch


def test_first_cell_composite_closes_physical_boundary_and_retains_downstream_trace() -> None:
  shock_fit, strip, patch = _first_cell_inputs()

  result = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )

  assert result.status is MocFirstCellCompositeStatus.CONVERGED_CLOSED_SUPERSONIC_COMPOSITE
  assert result.converged
  assert result.topology_closed
  assert result.physical_boundary_conditions_verified
  assert result.shared_terminal_seam_verified
  assert result.upstream_shock_coupling_verified
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.cell_count == strip.cell_count + patch.cell_count
  assert result.shock_boundary_points_m == tuple(
    sample.point_m for sample in shock_fit.boundary_states
  )
  assert result.ambient_boundary_points_m == strip.ambient_boundary_points_m
  assert result.centerline_boundary_points_m == patch.axis_points_m
  assert result.continuation_boundary_points_m == patch.outgoing_trace_points_m
  assert result.continuation_boundary == patch.outgoing_trace_samples
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True
  decision = result.as_chain_termination_decision()
  assert decision.physical_termination is False
  assert decision.reason.value == 'open-physical-closure'
  assert decision.diagnostics['termination_model'] == (
    'first-cell-open-physical-closure'
  )
  measurement = measure_moc_shock_cell(
    MocShockCellObservation(
      cell_index=1,
      shock_boundary_points_m=result.shock_boundary_points_m,
      centerline_boundary_points_m=result.centerline_boundary_points_m,
      cells=result.cells,
      upstream_total_pressure_Pa=tuple(
        sample.upstream_total_pressure_Pa for sample in shock_fit.boundary_states
      ),
      downstream_total_pressure_Pa=tuple(
        sample.downstream_total_pressure_Pa for sample in shock_fit.boundary_states
      ),
    )
  )
  assert measurement.converged
  assert measurement.pressure_loss_verified is True


def test_first_cell_composite_rejects_a_changed_shared_terminal_trace() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  first = replace(
    strip.terminal_trace_states[0],
    theta_rad=strip.terminal_trace_states[0].theta_rad + 0.01,
  )
  changed_strip = replace(
    strip,
    terminal_trace_states=(first, *strip.terminal_trace_states[1:]),
  )

  result = assemble_first_cell_composite(
    shock_fit,
    changed_strip,
    patch,
    position_tolerance_m=1.0e-3,
  )

  assert result.status is MocFirstCellCompositeStatus.SEAM_FAILURE
  assert not result.converged
  assert 'terminal C+ trace' in result.message


def test_first_cell_terminal_closure_fits_a_shock_from_the_exact_outgoing_trace() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )

  result = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )

  assert result.status is MocFirstCellTerminalClosureStatus.CONVERGED_SUPERSONIC_REGION
  assert result.converged
  assert result.supersonic_region_closed
  assert result.physical_closure_verified is False
  assert result.mixed_regime_field_complete is False
  assert result.chain_promotion_blocked
  assert result.downstream_shock is not None
  assert result.downstream_shock.physical_terminal_verified
  assert result.downstream_shock.incoming_handoff == composite.continuation_boundary
  assert result.terminal_field is not None
  assert result.terminal_field.converged
  assert result.terminal_field.initial_shock_boundary_points_m == (
    composite.shock_boundary_points_m
  )
  assert result.terminal_field.terminal_shock_boundary_coverage_verified

  decision = result.as_chain_termination_decision()
  assert decision.physical_termination is False
  assert decision.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  request = result.mixed_regime_perimeter_request()
  assert request.perimeter_supplied is False
  assert request.open_supersonic_zone_is_a_perimeter is False


def test_first_cell_terminal_closure_attaches_a_separate_mixed_regime_field() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  result = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  assert result.terminal_field is not None
  request = result.mixed_regime_perimeter_request()
  terminal = request.terminal
  point = request.terminal_point_m
  points = (
    point,
    (point[0] + 0.1, point[1] + 0.1),
    (point[0] + 0.2, point[1] + 0.1),
    (point[0] + 0.2, point[1]),
    point,
  )
  samples = tuple(
    MocMixedRegimeFieldSample(
      point_m=sample_point,
      mach=request.terminal_downstream_mach,
      flow_angle_rad=request.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=request.terminal_downstream_pressure_Pa,
      total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
      gamma=terminal.upstream_state.gamma,
    )
    for sample_point in points
  )

  boundary = result.terminal_field.validate_mixed_regime_boundary(samples)
  assert boundary.converged
  condition = result.terminal_field.validate_mixed_regime_downstream_condition(
    samples,
    MocMixedRegimeDownstreamConditionKind.SLIP_WALL,
  )
  assert condition.status is MocMixedRegimeDownstreamConditionStatus.TANGENCY_FAILURE
  assert condition.chain_promotion_blocked
  outflow_condition = result.terminal_field.validate_mixed_regime_downstream_condition(
    samples,
    MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
  )
  assert outflow_condition.converged
  field = solve_mixed_regime_subsonic_field(
    boundary,
    radial_divisions=2,
    downstream_condition=outflow_condition,
  )
  assert field.converged
  assert field.physical_closure_verified

  closure = result.solve_mixed_regime_closure(lambda _request: field)
  assert closure.converged
  assert closure.field is field
  attached = result.attach_mixed_regime_closure(closure)
  assert attached.mixed_regime_field is field
  assert attached.physical_closure_verified
  assert attached.physical_termination_verified
  decision = attached.as_chain_termination_decision()
  assert decision.physical_termination
  assert decision.reason is MocChainTerminationReason.PHYSICAL_TERMINATION


def test_first_cell_terminal_planner_mock_attaches_exact_seam_and_typed_stop() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )

  planner = plan_prescribed_first_cell_terminal_closure_mock(
    terminal,
    mock=MocPrescribedMixedRegimeClosureMock(radial_divisions=2),
  )

  assert isinstance(planner, MocFirstCellTerminalClosurePlannerResult)
  assert planner.planner_kind.value == 'prescribed-boundary-mock'
  assert planner.production_claim_allowed is False
  assert planner.resolved
  assert planner.physical_closure_verified
  assert planner.physical_termination
  assert planner.chain_promotion_blocked
  assert planner.termination is not None
  assert planner.termination.reason is MocChainTerminationReason.PHYSICAL_TERMINATION
  assert planner.mixed_regime_closure is not None
  assert planner.mixed_regime_closure.converged
  assert planner.terminal.mixed_regime_field is planner.mixed_regime_closure.field
  assert planner.mixed_regime_entropy_handoff is not None
  assert planner.mixed_regime_entropy_handoff_verified
  assert planner.diagnostics['mixed_regime_entropy_handoff_verified'] is True
  assert planner.diagnostics['mixed_regime_entropy_handoff_measurement'][
    'handoff_verified'
  ] is True
  assert planner.diagnostics['mixed_regime_closure_attached'] is True
  assert planner.diagnostics['prescribed_mixed_regime_closure_mock']['planning_only'] is True
  assert planner.diagnostics['prescribed_mixed_regime_closure_mock']['production_claim_allowed'] is False
  report = planner.as_report()
  assert report['planning_only'] is True
  assert report['production_claim_allowed'] is False
  assert report['termination']['physical_termination'] is True
  assert report['chain_promotion_blocked'] is True


def test_first_cell_terminal_planner_can_audit_an_explicit_entropy_source_map() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  request = terminal.mixed_regime_perimeter_request()
  handoff = request.entropy_handoff()
  mock = MocPrescribedMixedRegimeClosureMock(radial_divisions=2)
  field = mock.solve(request).field
  assert field is not None
  assert handoff.terminal_sample_index is not None
  terminal_arc = handoff.cumulative_arc_length_m[handoff.terminal_sample_index]

  planner = plan_first_cell_terminal_closure(
    terminal,
    mock=mock,
    mixed_regime_entropy_source_arc_length_m=(
      terminal_arc for _ in field.nodes
    ),
    mixed_regime_entropy_streamline_ids=(0 for _ in field.nodes),
  )

  assert planner.mixed_regime_entropy_transport is not None
  assert planner.mixed_regime_entropy_transport_verified
  assert planner.diagnostics['mixed_regime_entropy_transport_measurement'][
    'transport_verified'
  ] is True
  report = planner.as_report()
  assert report['mixed_regime_entropy_transport_verified'] is True
  assert report['mixed_regime_entropy_transport']['chain_promotion_blocked'] is True
  assert report['mixed_regime_entropy_transport']['production_claim_allowed'] is False


def test_first_cell_terminal_planner_preserves_open_boundary_without_solver() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )

  planner = plan_first_cell_terminal_closure(terminal)

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.resolved
  assert planner.physical_closure_verified is False
  assert planner.physical_termination is False
  assert planner.mixed_regime_closure is None
  assert planner.mixed_regime_entropy_handoff is not None
  assert planner.mixed_regime_entropy_handoff_verified
  assert planner.termination is not None
  assert planner.termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.diagnostics['mixed_regime_solver_supplied'] is False


def test_first_cell_terminal_planner_keeps_solver_generated_free_boundary_separate_from_mock() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  assert terminal.terminal_field is not None
  assert terminal.terminal_field.terminal_normal_shock is not None

  planner = plan_solver_generated_first_cell_terminal_closure_reference(
    terminal,
    solver=MocSolverGeneratedMixedRegimeClosureReference(
      ambient_pressure_Pa=(
        0.8 * terminal.terminal_field.terminal_normal_shock.downstream_pressure_Pa
      ),
    ),
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.resolved
  assert planner.physical_closure_verified
  assert planner.physical_termination
  assert planner.chain_promotion_blocked
  assert planner.mixed_regime_closure is not None
  assert planner.mixed_regime_closure.converged
  assert planner.diagnostics['solver_generated_mixed_regime_reference']['planning_only'] is True
  free_boundary = planner.diagnostics['solver_generated_mixed_regime_result']
  assert free_boundary['converged'] is True
  assert free_boundary['production_claim_allowed'] is False


def test_first_cell_terminal_planner_accepts_only_terminal_equivalent_control_section() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  request = terminal.mixed_regime_perimeter_request()
  terminal_x, terminal_y = request.terminal_point_m
  gamma = request.terminal.upstream_state.gamma
  points = (
    (terminal_x + 0.02, terminal_y - 0.01),
    (terminal_x + 0.02, terminal_y),
    (terminal_x + 0.02, terminal_y + 0.01),
  )
  section = MocMixedRegimeControlSection(
    points_m=points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=point,
        mach=request.terminal_downstream_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=request.terminal_downstream_pressure_Pa,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
      for point in points
    ),
    normal_angle_rad=0.0,
  )

  planner = plan_solver_generated_first_cell_terminal_closure_reference_from_control_section(
    terminal,
    section,
    solver=MocSolverGeneratedMixedRegimeClosureReference(
      ambient_pressure_Pa=0.8 * request.terminal_downstream_pressure_Pa,
    ),
  )

  assert planner.resolved
  assert planner.physical_closure_verified
  assert planner.physical_termination
  assert planner.chain_promotion_blocked
  assert planner.mixed_regime_closure is not None
  assert planner.mixed_regime_closure.converged
  assert planner.diagnostics['control_section_supplied'] is True
  assert planner.diagnostics['control_section']['sample_count'] == 3
  free_boundary = planner.diagnostics['solver_generated_mixed_regime_result']
  assert free_boundary['model'] == 'solver-owned-control-section-quasi-1d-reference'
  assert free_boundary['control_section_validation']['converged'] is True

  varying_mach = request.terminal_downstream_mach + 0.01
  varying_static_pressure = request.terminal_downstream_total_pressure_Pa / (
    1.0 + 0.5 * (gamma - 1.0) * varying_mach**2
  ) ** (gamma / (gamma - 1.0))
  varying_section = replace(
    section,
    samples=tuple(
      replace(
        sample,
        mach=varying_mach,
        static_pressure_Pa=varying_static_pressure,
      )
      for sample in section.samples
    ),
  )
  flux_planner = (
    plan_solver_generated_first_cell_terminal_closure_reference_from_control_section_flux(
      terminal,
      varying_section,
      solver=MocSolverGeneratedMixedRegimeClosureReference(
        ambient_pressure_Pa=0.8 * request.terminal_downstream_pressure_Pa,
      ),
    )
  )

  assert flux_planner.resolved
  assert flux_planner.physical_closure_verified
  assert flux_planner.physical_termination
  assert flux_planner.chain_promotion_blocked
  assert flux_planner.mixed_regime_closure is not None
  assert flux_planner.mixed_regime_closure.converged
  assert flux_planner.diagnostics['control_section_flux_mode'] == (
    'integrated-flux-quasi-1d-reference'
  )
  flux_free_boundary = flux_planner.diagnostics[
    'solver_generated_mixed_regime_result'
  ]
  assert flux_free_boundary['model'] == (
    'solver-owned-control-section-flux-quasi-1d-reference'
  )
  assert flux_free_boundary['control_section_projection_verified'] is False
  assert flux_free_boundary['control_section_flux_verified'] is True


def test_first_cell_terminal_closure_uses_the_explicit_perimeter_solver_seam() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  result = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  request = result.mixed_regime_perimeter_request()
  point = request.terminal_point_m
  specification = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      point,
      (point[0] + 0.05, point[1] + 0.05),
      (point[0] + 0.1, point[1] + 0.05),
      (point[0] + 0.1, point[1]),
      point,
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
  )

  closure = result.solve_mixed_regime_downstream_perimeter(
    specification,
    lambda received, _index, sample_point: MocMixedRegimeFieldSample(
      point_m=sample_point,
      mach=received.terminal_downstream_mach,
      flow_angle_rad=received.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=received.terminal_downstream_pressure_Pa,
      total_pressure_Pa=received.terminal_downstream_total_pressure_Pa,
      gamma=received.terminal.upstream_state.gamma,
    ),
    radial_divisions=2,
  )

  assert closure.converged
  assert closure.physical_closure_verified
  assert closure.perimeter_spec is specification
  assert closure.downstream_condition is not None
  assert closure.downstream_condition.converged


def test_first_cell_planner_records_planar_handoff_without_promoting_it() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal_closure = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  request = terminal_closure.mixed_regime_perimeter_request()
  point = request.terminal_point_m
  specification = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      point,
      (point[0] + 0.05, point[1] + 0.05),
      (point[0] + 0.1, point[1] + 0.05),
      (point[0] + 0.1, point[1]),
      point,
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
  )
  section_points = (
    (point[0] + 0.02, point[1] - 0.01),
    (point[0] + 0.02, point[1]),
    (point[0] + 0.02, point[1] + 0.01),
  )
  gamma = request.terminal.upstream_state.gamma
  varying_mach = request.terminal_downstream_mach + 0.01
  varying_static_pressure = request.terminal_downstream_total_pressure_Pa / (
    1.0 + 0.5 * (gamma - 1.0) * varying_mach * varying_mach
  ) ** (gamma / (gamma - 1.0))
  section = MocMixedRegimeControlSection(
    points_m=section_points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=sample_point,
        mach=varying_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=varying_static_pressure,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
      for sample_point in section_points
    ),
    normal_angle_rad=0.0,
  )

  def sample_at(
    received: MocMixedRegimePerimeterRequest,
    _index: int,
    sample_point: tuple[float, float],
  ) -> MocMixedRegimeFieldSample:
    return MocMixedRegimeFieldSample(
      point_m=sample_point,
      mach=received.terminal_downstream_mach,
      flow_angle_rad=received.terminal_downstream_flow_angle_rad,
      static_pressure_Pa=received.terminal_downstream_pressure_Pa,
      total_pressure_Pa=received.terminal_downstream_total_pressure_Pa,
      gamma=received.terminal.upstream_state.gamma,
    )

  scalar_closure = terminal_closure.solve_mixed_regime_downstream_perimeter(
    specification,
    sample_at,
    radial_divisions=2,
  )
  assert scalar_closure.field is not None
  assert scalar_closure.field.physical_closure_verified

  planner = plan_first_cell_terminal_closure_with_planar_handoff(
    terminal_closure,
    section,
    specification,
    lambda _request, received_section, _specification: replace(
      scalar_closure.field,
      control_section=received_section,
    ),
  )

  assert planner.resolved
  assert planner.physical_closure_verified is False
  assert planner.physical_termination is False
  assert planner.chain_promotion_blocked
  assert planner.termination is not None
  assert planner.termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.terminal.mixed_regime_field is None
  assert planner.mixed_regime_planar_handoff is not None
  assert planner.mixed_regime_planar_handoff.converged
  assert planner.mixed_regime_planar_handoff.section_is_varying
  assert planner.mixed_regime_planar_handoff.field_physical_closure_verified
  assert planner.mixed_regime_planar_handoff.physical_closure_verified is False
  assert planner.diagnostics['mixed_regime_planar_handoff_attached'] is False
  assert planner.diagnostics['mixed_regime_planar_handoff_verified'] is True


def test_first_cell_planner_records_builtin_planar_potential_reference_without_promotion() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal_closure = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  request = terminal_closure.mixed_regime_perimeter_request()
  point = request.terminal_point_m
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      point,
      (point[0] + 0.05, point[1] + 0.05),
      (point[0] + 0.1, point[1] + 0.05),
      (point[0] + 0.1, point[1]),
      point,
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )
  section_points = (
    (point[0] + 0.02, point[1] - 0.01),
    (point[0] + 0.02, point[1]),
    (point[0] + 0.02, point[1] + 0.01),
  )
  section = MocMixedRegimeControlSection(
    points_m=section_points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=section_point,
        mach=request.terminal_downstream_mach,
        flow_angle_rad=request.terminal_downstream_flow_angle_rad,
        static_pressure_Pa=request.terminal_downstream_pressure_Pa,
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=request.terminal.upstream_state.gamma,
      )
      for section_point in section_points
    ),
    normal_angle_rad=0.0,
  )

  planner = plan_first_cell_terminal_closure_with_planar_potential_reference(
    terminal_closure,
    section,
    perimeter_spec,
    reference=MocMixedRegimePlanarPotentialReference(radial_divisions=2),
  )

  assert planner.resolved
  assert planner.physical_closure_verified is False
  assert planner.physical_termination is False
  assert planner.chain_promotion_blocked
  assert planner.terminal.mixed_regime_field is None
  assert planner.mixed_regime_planar_handoff is not None
  assert planner.mixed_regime_planar_handoff.converged
  assert planner.mixed_regime_planar_handoff.control_section_projection_verified
  assert planner.mixed_regime_planar_handoff.field is not None
  assert planner.mixed_regime_planar_handoff.field.model == (
    'compressible-isentropic-potential-reference'
  )
  assert planner.diagnostics['mixed_regime_planar_handoff_attached'] is False
  assert planner.diagnostics['mixed_regime_planar_projection_verified'] is True


def test_first_cell_planner_records_non_affine_planar_reference_without_promotion() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  terminal_closure = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  request = terminal_closure.mixed_regime_perimeter_request()
  point = request.terminal_point_m
  gamma = request.terminal.upstream_state.gamma
  sonic_factor = 0.5 * (gamma - 1.0)
  terminal_speed = request.terminal_downstream_mach / sqrt(
    1.0 + sonic_factor * request.terminal_downstream_mach ** 2
  )
  section_points = (
    (point[0] + 0.02, point[1] - 0.01),
    (point[0] + 0.02, point[1]),
    (point[0] + 0.02, point[1] + 0.01),
  )
  section = MocMixedRegimeControlSection(
    points_m=section_points,
    samples=tuple(
      MocMixedRegimeFieldSample(
        point_m=section_point,
        mach=(
          (terminal_speed ** 2 + tangential_speed ** 2)
          / (
            1.0
            - sonic_factor * (terminal_speed ** 2 + tangential_speed ** 2)
          )
        ) ** 0.5,
        flow_angle_rad=atan2(tangential_speed, terminal_speed),
        static_pressure_Pa=(
          request.terminal_downstream_total_pressure_Pa
          / (
            1.0
            + sonic_factor * (
              (terminal_speed ** 2 + tangential_speed ** 2)
              / (
                1.0
                - sonic_factor * (
                  terminal_speed ** 2 + tangential_speed ** 2
                )
              )
            )
          ) ** (gamma / (gamma - 1.0))
        ),
        total_pressure_Pa=request.terminal_downstream_total_pressure_Pa,
        gamma=gamma,
      )
      for section_point, tangential_speed in zip(
        section_points,
        (0.002, 0.0, 0.002),
        strict=True,
      )
    ),
    normal_angle_rad=0.0,
  )
  perimeter_spec = MocMixedRegimeDownstreamPerimeterSpec(
    perimeter_points_m=(
      point,
      (point[0] + 0.1, point[1]),
      (point[0] + 0.1, point[1] + 0.01),
      (point[0], point[1] + 0.01),
      point,
    ),
    condition_kind=MocMixedRegimeDownstreamConditionKind.PRESSURE_OUTFLOW_SECTION,
    ambient_pressure_Pa=request.terminal_downstream_pressure_Pa,
    condition_edge_indices=(0,),
    condition_sample_indices=(0, 1),
  )

  planner = plan_first_cell_terminal_closure_with_planar_frozen_profile_reference(
    terminal_closure,
    section,
    perimeter_spec,
    reference=MocMixedRegimePlanarFrozenProfileReference(radial_divisions=2),
  )

  assert planner.resolved
  assert planner.physical_closure_verified is False
  assert planner.physical_termination is False
  assert planner.chain_promotion_blocked
  assert planner.terminal.mixed_regime_field is None
  assert planner.mixed_regime_planar_handoff is not None
  assert planner.mixed_regime_planar_handoff.converged
  assert planner.mixed_regime_planar_handoff.section_is_varying
  assert planner.mixed_regime_planar_handoff.projection_model == (
    'piecewise-linear-frozen-transverse-profile'
  )
  assert planner.diagnostics['mixed_regime_planar_handoff_attached'] is False
  assert planner.diagnostics['mixed_regime_planar_projection_verified'] is True
  assert planner.diagnostics[
    'mixed_regime_planar_frozen_profile_reference'
  ]['extrapolation_allowed'] is False


def test_first_cell_terminal_closure_rejects_a_changed_outgoing_handoff() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  solved = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  assert solved.downstream_shock is not None

  changed = replace(solved.downstream_shock, incoming_handoff=())
  result = assemble_first_cell_terminal_shock_field(composite, changed)

  assert result.status is MocFirstCellTerminalClosureStatus.SEAM_FAILURE
  assert not result.converged
  assert 'exact first-cell outgoing' in result.message


def test_terminal_boundary_graph_keeps_downstream_geometry_separate_from_closure() -> None:
  shock_fit, strip, patch = _first_cell_inputs()
  composite = assemble_first_cell_composite(
    shock_fit,
    strip,
    patch,
    position_tolerance_m=1.0e-3,
  )
  result = solve_marched_first_cell_terminal_closure(
    composite,
    downstream_flow_angle_rad=0.0,
    sample_count=17,
    shock_position_tolerance_m=2.0e-4,
  )
  assert result.terminal_field is not None
  field = result.terminal_field
  terminal = field.terminal_normal_shock
  assert terminal is not None
  assert terminal.shock_point_m is not None

  graph = field.boundary_graph()
  assert graph.status is MocTerminalBoundaryGraphStatus.CONVERGED_UPSTREAM_GRAPH
  assert graph.converged
  assert graph.upstream_graph_closed
  assert graph.maximum_upstream_join_residual_m == 0.0
  assert graph.downstream_boundary_geometry_supplied is False
  assert graph.downstream_boundary_geometry_verified is False
  assert graph.physical_closure_verified is False
  assert graph.chain_promotion_blocked
  assert field.as_report()['terminal_boundary_graph']['upstream_graph_closed'] is True

  point = terminal.shock_point_m
  explicit_path = (
    point,
    (point[0] + 0.1, point[1] + 0.1),
    (point[0] + 0.2, point[1] + 0.12),
    point,
  )
  explicit = field.boundary_graph(downstream_boundary_points_m=explicit_path)
  assert explicit.status is MocTerminalBoundaryGraphStatus.CONVERGED_EXPLICIT_DOWNSTREAM_GEOMETRY
  assert explicit.converged
  assert explicit.upstream_graph_closed
  assert explicit.downstream_boundary_geometry_verified
  assert explicit.physical_downstream_condition_supplied is False
  assert explicit.physical_closure_verified is False
  assert explicit.chain_promotion_blocked

  malformed = field.boundary_graph(
    downstream_boundary_points_m=(point, (point[0] + 0.1, point[1] + 0.1), point),
  )
  assert malformed.status is MocTerminalBoundaryGraphStatus.DOWNSTREAM_BOUNDARY_FAILURE
  assert not malformed.converged
  assert malformed.upstream_graph_closed
  assert malformed.downstream_boundary_geometry_supplied
  assert not malformed.downstream_boundary_geometry_verified
