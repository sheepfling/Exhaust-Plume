from __future__ import annotations

from dataclasses import replace

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocFirstCellCompositeStatus,
  MocFirstCellTerminalClosureStatus,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionStatus,
  MocMixedRegimeFieldSample,
  MocTerminalBoundaryGraphStatus,
  MocChainTerminationReason,
  assemble_ambient_shock_characteristic_strip,
  assemble_first_cell_terminal_shock_field,
  assemble_first_cell_composite,
  assemble_terminal_trace_centerline_patch,
  march_post_shock_ambient_boundary,
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

  attached = result.with_mixed_regime_field(field)
  assert attached.mixed_regime_field is field
  assert attached.physical_closure_verified
  assert attached.physical_termination_verified
  decision = attached.as_chain_termination_decision()
  assert decision.physical_termination
  assert decision.reason is MocChainTerminationReason.PHYSICAL_TERMINATION


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
