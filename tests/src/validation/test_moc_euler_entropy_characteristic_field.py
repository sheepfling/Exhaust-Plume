from __future__ import annotations

from dataclasses import replace
from math import atan2

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocChainTerminationReason,
  MocChainTerminationDecision,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock,
  MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus,
  MocEulerAmbientFirstWedgeEntropyCarryStatus,
  assemble_euler_ambient_physical_field,
  plan_euler_ambient_first_wedge_entropy_characteristic_field,
  plan_euler_ambient_first_wedge_entropy_characteristic_field_chain,
  plan_euler_ambient_first_wedge_entropy_characteristic_field_chain_mock,
  plan_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_probe,
  plan_euler_ambient_first_wedge_entropy_characteristic_free_boundary_probe,
  plan_euler_ambient_first_wedge_entropy_characteristic_continuation_probe,
  plan_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_probe,
  plan_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh_probe,
  plan_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary_probe,
  refine_euler_ambient_first_wedge_entropy_characteristic_continuation,
  remesh_euler_ambient_first_wedge_entropy_characteristic_continuation,
  solve_euler_ambient_first_wedge_characteristic_remesh,
  solve_euler_ambient_first_wedge_entropy_carry,
  solve_euler_ambient_first_wedge_entropy_characteristic_field,
  solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling,
  solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary,
  solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary,
  solve_euler_ambient_first_wedge_entropy_characteristic_continuation,
  solve_attached_compression_to_turn,
  fit_euler_consistent_shock_boundary,
)
from exhaust_plume.validation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field_chain,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_shock_coupling,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_free_boundary,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_ladder,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary,
)


def _shaped_exact_shock():
  sample_count = 9
  points = tuple(
    (
      0.5 + 4.93 * distance - 3.36 * distance * distance,
      0.5 - distance,
    )
    for distance in (
      index * 0.5 / (sample_count - 1)
      for index in range(sample_count)
    )
  )
  turns = (0.005, 0.14, 0.20, 0.22, 0.22, 0.20, 0.18, 0.17, 0.081637491676426)
  tangent_angles = tuple(
    atan2(second[1] - first[1], second[0] - first[0])
    for first, second in (
      (points[0], points[1]),
      *zip(points[:-2], points[2:]),
      (points[-2], points[-1]),
    )
  )
  upstream_states = []
  for point, turn, tangent_angle in zip(
    points,
    turns,
    tangent_angles,
    strict=True,
  ):
    compression = solve_attached_compression_to_turn(
      upstream_mach=2.0,
      gamma=1.4,
      upstream_pressure_Pa=100000.0,
      target_turn_rad=turn,
    )
    assert compression.beta_rad is not None
    upstream_states.append(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=tangent_angle + compression.beta_rad,
        mach=2.0,
        gamma=1.4,
      )
    )
  return fit_euler_consistent_shock_boundary(
    tuple(upstream_states),
    (100000.0,) * sample_count,
    points,
    tuple(
      state.theta_rad - turn
      for state, turn in zip(upstream_states, turns, strict=True)
    ),
  )


def _internal_field():
  shock = _shaped_exact_shock()
  physical_field = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )
  candidate = solve_euler_ambient_first_wedge_characteristic_remesh(
    physical_field,
  )
  entropy_trial = solve_euler_ambient_first_wedge_entropy_carry(candidate)
  return entropy_trial, solve_euler_ambient_first_wedge_entropy_characteristic_field(
    entropy_trial,
  )


def test_internal_entropy_characteristic_field_closes_local_subcells() -> None:
  entropy_trial, result = _internal_field()

  assert entropy_trial.status is MocEulerAmbientFirstWedgeEntropyCarryStatus.EULER_RESIDUAL_FAILURE
  assert result.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus
    .CONVERGED_INTERNAL_CHARACTERISTIC_FIELD
  )
  assert result.converged
  assert result.local_consistency_verified
  assert result.node_count == 6
  assert result.cell_count == 4
  assert len(result.characteristic_edges) == 6
  assert result.continuation_boundary_node_indices == (1, 4, 2)
  assert len(result.continuation_boundary) == 3
  assert result.continuation_boundary_verified
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.pressure_lineage_verified
  assert result.characteristic_geometry_verified
  assert result.variable_entropy_compatibility_verified
  assert result.cell_euler_residuals_verified
  assert result.internal_characteristic_closure_verified
  assert result.maximum_entropy_compatibility_residual is not None
  assert result.maximum_entropy_compatibility_residual < 1.0e-8
  assert result.maximum_cell_euler_residual is not None
  assert result.maximum_cell_euler_residual < 1.0e-2
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False


def test_internal_entropy_characteristic_field_exposes_bounded_sampler() -> None:
  _, field = _internal_field()

  for sample in field.cell_samples:
    centroid = tuple(
      sum(point[index] for point in sample.vertices_xr_m) / 3.0
      for index in (0, 1)
    )
    state = field.state_at(centroid)
    pressure = field.static_pressure_at(centroid)
    total_pressure = field.total_pressure_at(centroid)
    assert state is not None
    assert state.x_m == centroid[0]
    assert state.y_m == centroid[1]
    assert state.mach > 1.0
    assert pressure is not None and pressure > 0.0
    assert total_pressure is not None and total_pressure > 0.0

  assert field.state_sampling_available
  assert field.state_at((2.0, 0.2)) is None
  assert field.static_pressure_at((2.0, 0.2)) is None
  assert field.total_pressure_at((2.0, 0.2)) is None


def test_internal_entropy_characteristic_shock_coupling_stops_at_bounded_field() -> None:
  _, field = _internal_field()
  handoff = field.continuation_boundary

  coupling = solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling(
    field,
    handoff,
    handoff[0].point_m,
    downstream_flow_angle_rad=0.2,
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  assert coupling.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
    .UPSTREAM_FIELD_BOUNDARY
  )
  assert coupling.shock is not None
  assert coupling.converged is False
  assert coupling.path_coverage_verified is False
  assert coupling.first_missing_sample_index is not None
  decision = coupling.as_chain_termination_decision()
  assert decision.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert decision.physical_termination is False
  assert decision.diagnostics['path_coverage_verified'] is False
  assert decision.diagnostics['required_next_gate'] == (
    'reflected-free-boundary-coupling-and-independent-euler-validation-'
    'before-continued-shock-cell-chain'
  )


def test_internal_entropy_characteristic_chain_probe_records_bounded_shock_attempt() -> None:
  _, field = _internal_field()

  planner = (
    plan_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_probe(
      field,
      downstream_flow_angle_rad=0.2,
      sample_count=9,
      position_tolerance_m=1.0e-8,
    )
  )

  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.termination.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.termination.physical_termination is False
  assert planner.diagnostics['shock_coupling_attempt_count'] == 1
  attempt = planner.diagnostics['shock_coupling_attempts'][0]
  assert attempt['status'] == (
    MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
    .UPSTREAM_FIELD_BOUNDARY.value
  )
  assert planner.diagnostics['synthetic_downstream_field_created'] is False


def test_internal_entropy_characteristic_shock_coupling_has_independent_audit() -> None:
  _, field = _internal_field()
  coupling = solve_euler_ambient_first_wedge_entropy_characteristic_shock_coupling(
    field,
    field.continuation_boundary,
    field.continuation_boundary[0].point_m,
    downstream_flow_angle_rad=0.2,
    sample_count=9,
    position_tolerance_m=1.0e-8,
  )

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_shock_coupling(
    coupling,
    position_tolerance_m=1.0e-8,
  )

  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
    .CONVERGED_LOCAL_BOUNDARY_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.incoming_handoff_verified
  assert audit.path_coverage_verified is False
  assert audit.status_consistent
  assert audit.fidelity_flags_verified
  assert audit.field_audit is not None
  assert audit.field_audit.local_consistency_verified
  assert audit.termination_reason == (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY.value
  )


def test_internal_entropy_characteristic_free_boundary_stops_at_bounded_field() -> None:
  _, field = _internal_field()
  handoff = field.continuation_boundary
  start = handoff[0]
  ambient_pressure = field.static_pressure_at(start.point_m)
  assert ambient_pressure is not None
  attempt = solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
    field,
    handoff,
    start.point_m,
    ambient_pressure,
    start.state.theta_rad - 1.0e-6,
    start.state.theta_rad + 1.0e-6,
    sample_count=9,
    position_tolerance_m=1.0e-8,
    allow_zero_strength_attachment=True,
  )

  assert attempt.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .UPSTREAM_FIELD_BOUNDARY
  )
  assert attempt.physical_field is not None
  assert attempt.physical_field.ambient_attachment is not None
  assert attempt.shock is not None
  assert attempt.shock.status.value == 'upstream_field_failure'
  assert attempt.shock_sample_count == 1
  assert attempt.covered_sample_count == 1
  assert attempt.first_missing_sample_index == 1
  assert attempt.path_coverage_verified is False
  assert attempt.reflected_free_boundary_verified is False
  assert attempt.physical_closure_verified is False
  assert attempt.chain_promotion_blocked
  assert attempt.production_claim_allowed is False
  assert attempt.as_chain_termination_decision().reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )


def test_internal_entropy_characteristic_free_boundary_planner_and_audit_keep_stop_typed() -> None:
  _, field = _internal_field()
  start = field.continuation_boundary[0]
  ambient_pressure = field.static_pressure_at(start.point_m)
  assert ambient_pressure is not None
  planner = plan_euler_ambient_first_wedge_entropy_characteristic_free_boundary_probe(
    field,
    ambient_pressure_Pa=ambient_pressure,
    outer_downstream_flow_angle_lower_rad=start.state.theta_rad - 1.0e-6,
    outer_downstream_flow_angle_upper_rad=start.state.theta_rad + 1.0e-6,
    sample_count=9,
    position_tolerance_m=1.0e-8,
    allow_zero_strength_attachment=True,
  )
  attempt = solve_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
    field,
    field.continuation_boundary,
    start.point_m,
    ambient_pressure,
    start.state.theta_rad - 1.0e-6,
    start.state.theta_rad + 1.0e-6,
    sample_count=9,
    position_tolerance_m=1.0e-8,
    allow_zero_strength_attachment=True,
  )
  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
    attempt,
    position_tolerance_m=1.0e-8,
  )

  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.termination.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.termination.physical_termination is False
  assert planner.diagnostics['reflected_free_boundary_attempt_count'] == 1
  assert planner.diagnostics['external_validation_required'] is True
  assert planner.diagnostics['synthetic_downstream_field_created'] is False
  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
    .CONVERGED_LOCAL_BOUNDARY_AUDIT
  )
  assert audit.local_consistency_verified
  assert audit.incoming_handoff_verified
  assert audit.path_coverage_verified is False
  assert audit.status_consistent
  assert audit.external_validation_required
  assert audit.fidelity_flags_verified
  assert audit.shock_sample_count == 1
  assert audit.covered_sample_count == 1
  assert audit.first_missing_sample_index == 1
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_continuation_builds_bounded_cell_band() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None

  result = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    ambient_pressure,
    cycle_count=4,
  )

  assert result.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
    .CONVERGED_BOUNDED_CONTINUATION
  )
  assert result.converged
  assert result.local_consistency_verified
  assert result.state_sampling_available
  assert result.ambient_pressure_Pa == ambient_pressure
  assert len(result.centerline_states) == 4
  assert len(result.outer_states) == 4
  assert len(result.centerline_segments) == 4
  assert len(result.outer_segments) == 4
  assert result.terminal_segment is not None
  assert len(result.cells) == 7
  assert len(result.cell_samples) == 7
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.continuation_boundary_verified
  assert len(result.continuation_boundary) == 2
  assert result.cell_euler_residuals_finite
  assert result.maximum_cell_euler_residual is not None
  assert result.maximum_cell_euler_residual > 1.0e-2
  assert result.cell_euler_residuals_verified is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False

  for sample in result.cell_samples:
    centroid = tuple(
      sum(point[index] for point in sample.vertices_xr_m) / 3.0
      for index in (0, 1)
    )
    assert result.state_at(centroid) is not None
    assert result.total_pressure_at(centroid) is not None
    assert result.static_pressure_at(centroid) is not None
  assert result.state_at((2.0, 0.2)) is None


def test_internal_entropy_characteristic_continuation_audit_keeps_euler_gate_separate() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None
  result = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    ambient_pressure,
    cycle_count=4,
  )

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
    result,
  )

  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
    .CONVERGED_LOCAL_CONTINUATION_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.field_audit is not None
  assert audit.field_audit.local_consistency_verified
  assert audit.incoming_handoff_verified
  assert audit.segment_links_verified
  assert audit.reflection_anchor_verified
  assert audit.alternating_seams_verified
  assert audit.pressure_lineage_verified
  assert audit.ambient_boundary_verified
  assert audit.continuation_boundary_verified
  assert audit.topology_verified
  assert audit.cell_samples_verified
  assert audit.cell_euler_residuals_finite
  assert audit.cell_euler_residuals_verified is False
  assert audit.status_consistent
  assert audit.fidelity_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_continuation_planner_records_typed_stop() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None

  planner = plan_euler_ambient_first_wedge_entropy_characteristic_continuation_probe(
    field,
    ambient_pressure_Pa=ambient_pressure,
    cycle_count=4,
  )

  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.termination.physical_termination is False
  assert planner.diagnostics['continuation_attempt_count'] == 1
  assert planner.diagnostics['continuation_attempts'][0]['cell_count'] == 7
  assert planner.diagnostics['external_validation_required'] is True
  assert planner.diagnostics['synthetic_downstream_field_created'] is False
  assert planner.physical_chain_cell_count == 0
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False


def test_internal_entropy_characteristic_continuation_refinement_keeps_gate_and_planner_separate() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None
  continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    ambient_pressure,
    cycle_count=4,
  )

  refinement = refine_euler_ambient_first_wedge_entropy_characteristic_continuation(
    continuation,
    subdivision_side_count=12,
  )
  assert refinement.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
    .CONVERGED_DIAGNOSTIC_REFINEMENT
  )
  assert refinement.converged
  assert refinement.local_projection_verified
  assert refinement.cell_count == 1008
  assert refinement.state_sample_count > 0
  assert refinement.state_sample_count < refinement.cell_count
  assert refinement.maximum_cell_euler_residual is not None
  assert refinement.maximum_cell_euler_residual < 1.0e-2
  assert refinement.topology.connected
  assert refinement.topology.forms_closed_zone
  assert refinement.topology.nonmanifold_edge_count == 0
  assert refinement.continuation_boundary_verified
  assert refinement.cell_euler_residuals_finite
  assert refinement.cell_euler_residuals_verified
  assert refinement.physical_closure_verified is False
  assert refinement.chain_promotion_blocked
  assert refinement.production_claim_allowed is False

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement(
    refinement,
  )
  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
    .CONVERGED_LOCAL_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.structural_consistency_verified
  assert audit.source_continuation_gates_verified
  assert audit.topology_verified
  assert audit.state_projection_verified
  assert audit.pressure_lineage_carried
  assert audit.continuation_boundary_verified
  assert audit.cell_euler_residuals_verified
  assert audit.solver_status_consistent
  assert audit.external_validation_required
  assert audit.fidelity_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False

  planner = plan_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_probe(
    field,
    ambient_pressure_Pa=ambient_pressure,
    cycle_count=4,
  )
  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.termination.physical_termination is False
  assert planner.physical_chain_cell_count == 0
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['refinement_side_counts'] == (1, 4, 12, 16)
  assert len(planner.diagnostics['refinement_ladder']) == 4
  assert planner.diagnostics['refinement_consumed_as_chain_cell'] is False


def test_internal_entropy_characteristic_continuation_refinement_ladder_audits_resolution_trend() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None
  continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    ambient_pressure,
    cycle_count=4,
  )
  cases = tuple(
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase(
      subdivision_side_count=side_count,
      result=refine_euler_ambient_first_wedge_entropy_characteristic_continuation(
        continuation,
        subdivision_side_count=side_count,
      ),
    )
    for side_count in (1, 4, 12, 16)
  )
  measurement = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_ladder(
    cases,
    expected_subdivision_side_counts=(1, 4, 12, 16),
  )
  assert measurement.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
    .CONVERGED_LOCAL_REFINEMENT
  )
  assert measurement.converged
  assert measurement.local_consistency_verified
  assert measurement.subdivision_side_counts == (1, 4, 12, 16)
  assert measurement.cell_counts == (7, 112, 1008, 1792)
  assert measurement.levels_verified
  assert measurement.audits_verified
  assert measurement.topology_verified
  assert measurement.state_projection_verified
  assert measurement.pressure_lineage_verified
  assert measurement.continuation_boundary_verified
  assert measurement.cell_euler_residuals_finite
  assert measurement.final_cell_euler_residual_verified
  assert measurement.residual_nonincreasing_verified
  assert measurement.residual_reduction_verified
  assert measurement.maximum_cell_euler_residuals[-1] < 1.0e-2
  assert measurement.audits[0].status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
    .EULER_RESIDUAL_FAILURE
  )
  assert measurement.audits[0].structural_consistency_verified
  assert measurement.audits[0].local_consistency_verified is False
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_internal_entropy_characteristic_continuation_remesh_solves_shared_edges_but_keeps_euler_gate_separate() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None
  continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    ambient_pressure,
    cycle_count=4,
  )

  remesh = remesh_euler_ambient_first_wedge_entropy_characteristic_continuation(
    continuation,
    subdivision_side_count=2,
  )
  assert remesh.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
    .CONVERGED_LOCAL_CHARACTERISTIC_REMESH
  )
  assert remesh.converged
  assert remesh.local_characteristic_remesh_verified
  assert remesh.cell_count == 28
  assert remesh.state_sample_count == 24
  assert len(remesh.characteristic_edges) == 8
  assert remesh.maximum_geometry_residual is not None
  assert remesh.maximum_geometry_residual <= 1.0e-6
  assert remesh.maximum_compatibility_residual is not None
  assert remesh.maximum_compatibility_residual <= 1.0e-6
  assert remesh.maximum_pressure_residual is not None
  assert remesh.maximum_pressure_residual <= 1.0e-8
  assert remesh.topology.connected
  assert remesh.topology.forms_closed_zone
  assert remesh.topology.nonmanifold_edge_count == 0
  assert remesh.continuation_boundary_verified
  assert remesh.cell_euler_residuals_finite
  assert remesh.maximum_cell_euler_residual is not None
  assert remesh.maximum_cell_euler_residual > 1.0e-2
  assert remesh.cell_euler_residuals_verified is False
  assert remesh.physical_closure_verified is False
  assert remesh.chain_promotion_blocked
  assert remesh.production_claim_allowed is False

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh(
    remesh,
  )
  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus
    .CONVERGED_LOCAL_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.structural_consistency_verified
  assert audit.source_continuation_gates_verified
  assert audit.topology_verified
  assert audit.cell_samples_verified
  assert audit.edge_points_covered
  assert audit.edge_traces_verified
  assert audit.characteristic_geometry_verified
  assert audit.variable_entropy_compatibility_verified
  assert audit.pressure_lineage_carried
  assert audit.continuation_boundary_verified
  assert audit.cell_euler_residuals_finite
  assert audit.cell_euler_residuals_verified is False
  assert audit.solver_status_consistent
  assert audit.external_validation_required
  assert audit.fidelity_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_continuation_remesh_solves_interior_rows_without_physical_promotion() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None
  continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    ambient_pressure,
    cycle_count=4,
  )

  remesh = remesh_euler_ambient_first_wedge_entropy_characteristic_continuation(
    continuation,
    subdivision_side_count=4,
  )
  assert remesh.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
    .CONVERGED_LOCAL_CHARACTERISTIC_REMESH
  )
  assert remesh.converged
  assert remesh.local_characteristic_remesh_verified
  assert remesh.cell_count == 112
  assert remesh.state_sample_count == 75
  assert len(remesh.characteristic_edges) == 8
  assert all(len(edge.points_xr_m) == 5 for edge in remesh.characteristic_edges)
  assert len(remesh.interior_characteristic_intersections) == 21
  assert remesh.interior_characteristic_rows_required
  assert remesh.interior_characteristic_intersections_verified
  assert remesh.maximum_intersection_geometry_residual is not None
  assert remesh.maximum_intersection_geometry_residual <= 1.0e-6
  assert remesh.maximum_intersection_compatibility_residual is not None
  assert remesh.maximum_intersection_compatibility_residual <= 1.0e-6
  assert remesh.maximum_intersection_pressure_residual is not None
  assert remesh.maximum_intersection_pressure_residual <= 1.0e-8
  assert all(
    intersection.forward_verified
    for intersection in remesh.interior_characteristic_intersections
  )
  assert remesh.topology.connected
  assert remesh.topology.forms_closed_zone
  assert remesh.topology.nonmanifold_edge_count == 0
  assert remesh.cell_euler_residuals_finite
  assert remesh.maximum_cell_euler_residual is not None
  assert remesh.maximum_cell_euler_residual > 1.0e-2
  assert remesh.cell_euler_residuals_verified is False
  assert remesh.interior_characteristic_closure_verified is False
  assert remesh.physical_closure_verified is False
  assert remesh.chain_promotion_blocked
  assert remesh.production_claim_allowed is False

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh(
    remesh,
  )
  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus
    .CONVERGED_LOCAL_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.structural_consistency_verified
  assert audit.interior_characteristic_intersection_count == 21
  assert audit.interior_characteristic_rows_required
  assert audit.interior_characteristic_intersections_verified
  assert audit.maximum_intersection_geometry_residual is not None
  assert audit.maximum_intersection_geometry_residual <= 1.0e-6
  assert audit.maximum_intersection_compatibility_residual is not None
  assert audit.maximum_intersection_compatibility_residual <= 1.0e-6
  assert audit.maximum_intersection_pressure_residual is not None
  assert audit.maximum_intersection_pressure_residual <= 1.0e-8
  assert audit.cell_euler_residuals_verified is False
  assert audit.external_validation_required
  assert audit.fidelity_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_continuation_remesh_planner_records_ladder_without_consuming_cells() -> None:
  _, field = _internal_field()
  ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert ambient_pressure is not None
  planner = plan_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh_probe(
    field,
    ambient_pressure_Pa=ambient_pressure,
    cycle_count=4,
  )
  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.termination.physical_termination is False
  assert planner.physical_chain_cell_count == 0
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['remesh_side_counts'] == (1, 2, 4)
  assert len(planner.diagnostics['remesh_ladder']) == 3
  assert [
    entry['cell_count'] for entry in planner.diagnostics['remesh_ladder']
  ] == [7, 28, 112]
  assert all(
    entry['local_characteristic_remesh_verified']
    for entry in planner.diagnostics['remesh_ladder']
  )
  assert planner.diagnostics['remesh_ladder'][-1][
    'interior_characteristic_intersection_count'
  ] == 21
  assert planner.diagnostics['remesh_ladder'][-1][
    'interior_characteristic_intersections_verified'
  ]
  assert planner.diagnostics['remesh_consumed_as_chain_cell'] is False
  assert planner.diagnostics['external_validation_required'] is True


def test_internal_entropy_characteristic_remesh_free_boundary_probe_stops_at_remesh_boundary() -> None:
  _, field = _internal_field()
  continuation_ambient_pressure = field.static_pressure_at(
    field.continuation_boundary[0].point_m,
  )
  assert continuation_ambient_pressure is not None
  continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
    field,
    field.continuation_boundary,
    continuation_ambient_pressure,
    cycle_count=4,
  )
  remesh = remesh_euler_ambient_first_wedge_entropy_characteristic_continuation(
    continuation,
    subdivision_side_count=4,
  )
  handoff = remesh.continuation_boundary
  ambient_pressure = remesh.diagnostic_static_pressure_at(handoff[0].point_m)
  assert ambient_pressure is not None

  attempt = solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary(
    remesh,
    handoff,
    handoff[0].point_m,
    ambient_pressure,
    handoff[0].state.theta_rad - 1.0e-6,
    handoff[0].state.theta_rad + 1.0e-6,
    sample_count=9,
    position_tolerance_m=1.0e-8,
    allow_zero_strength_attachment=True,
  )

  assert attempt.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .UPSTREAM_REMESH_BOUNDARY
  )
  assert attempt.shock is not None
  assert attempt.shock.status.value == 'upstream_field_failure'
  assert attempt.shock_sample_count == 1
  assert attempt.covered_sample_count == 1
  assert attempt.first_missing_sample_index == 1
  assert attempt.source_remesh_verified
  assert attempt.source_cell_euler_residuals_verified is False
  assert attempt.reflected_free_boundary_verified is False
  assert attempt.physical_closure_verified is False
  assert attempt.chain_promotion_blocked
  assert attempt.production_claim_allowed is False
  assert attempt.as_chain_termination_decision().reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary(
    attempt,
    position_tolerance_m=1.0e-8,
  )
  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
    .CONVERGED_LOCAL_BOUNDARY_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.source_remesh_verified
  assert audit.source_cell_euler_residuals_verified is False
  assert audit.source_cell_euler_residuals_flag_consistent
  assert audit.path_coverage_verified is False
  assert audit.status_consistent
  assert audit.external_validation_required
  assert audit.fidelity_flags_verified
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_remesh_free_boundary_planner_keeps_boundary_typed() -> None:
  _, field = _internal_field()
  start = field.continuation_boundary[0]
  ambient_pressure = field.static_pressure_at(start.point_m)
  assert ambient_pressure is not None
  planner = plan_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary_probe(
    field,
    ambient_pressure_Pa=ambient_pressure,
    outer_downstream_flow_angle_lower_rad=start.state.theta_rad - 1.0e-6,
    outer_downstream_flow_angle_upper_rad=start.state.theta_rad + 1.0e-6,
    sample_count=9,
    position_tolerance_m=1.0e-8,
    allow_zero_strength_attachment=True,
  )

  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.termination.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.termination.physical_termination is False
  assert planner.physical_chain_cell_count == 0
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['remesh_free_boundary_attempt_count'] == 1
  attempt = planner.diagnostics['remesh_free_boundary_attempts'][0]
  assert attempt['status'] == (
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .UPSTREAM_REMESH_BOUNDARY.value
  )
  assert attempt['first_missing_sample_index'] == 1
  assert planner.diagnostics['remesh_free_boundary_consumed_as_chain_cell'] is False
  assert planner.diagnostics['external_validation_required'] is True
  assert planner.diagnostics['synthetic_downstream_field_created'] is False


def test_internal_entropy_characteristic_field_has_independent_audit() -> None:
  _, result = _internal_field()

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
    result,
  )

  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus
    .CONVERGED_LOCAL_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.source_trial_gates_verified
  assert audit.topology_verified
  assert audit.state_samples_finite
  assert audit.continuation_boundary_verified
  assert audit.pressure_lineage_verified
  assert audit.characteristic_geometry_verified
  assert audit.variable_entropy_compatibility_verified
  assert audit.cell_euler_residuals_finite
  assert audit.cell_euler_residuals_verified
  assert audit.internal_characteristic_closure_verified
  assert audit.solver_status_consistent
  assert audit.physical_closure_verified is False
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_audit_rejects_tampered_node() -> None:
  _, result = _internal_field()
  node = result.nodes[3]
  tampered_state = replace(node.state, theta_rad=node.state.theta_rad + 0.01)
  tampered_node = replace(node, state=tampered_state)
  tampered = replace(
    result,
    nodes=(result.nodes[0], result.nodes[1], result.nodes[2], tampered_node, *result.nodes[4:]),
  )

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
    tampered,
  )

  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.STATE_FAILURE
  )
  assert not audit.converged
  assert not audit.local_consistency_verified


def test_internal_entropy_characteristic_audit_rejects_weakened_cached_flag() -> None:
  _, result = _internal_field()
  tampered = replace(result, internal_characteristic_closure_verified=False)

  audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
    tampered,
  )

  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.FLAG_FAILURE
  )
  assert audit.internal_characteristic_closure_verified
  assert not audit.solver_status_consistent
  assert not audit.local_consistency_verified


def test_internal_entropy_characteristic_planner_stops_before_chain_promotion() -> None:
  entropy_trial, _ = _internal_field()
  planner = plan_euler_ambient_first_wedge_entropy_characteristic_field(
    entropy_trial,
  )

  assert planner.attempted
  assert planner.resolved
  assert planner.field is not None
  assert planner.step is not None
  assert planner.step.result_internal_characteristic_closure_verified
  assert planner.step.result_continuation_boundary_sample_count == 3
  assert planner.step.result_continuation_boundary_verified
  assert planner.physical_chain_cell_count == 0
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert planner.termination.physical_termination is False
  assert planner.termination.diagnostics['required_next_gate'] == (
    'reflected-free-boundary-coupling-and-external-validation-before-'
    'continued-shock-cell-chain'
  )


def test_internal_entropy_characteristic_chain_has_typed_nonphysical_stop() -> None:
  _, field = _internal_field()

  planner = plan_euler_ambient_first_wedge_entropy_characteristic_field_chain_mock(
    field,
  )
  audit = (
    measure_moc_euler_ambient_first_wedge_entropy_characteristic_field_chain(
      planner,
    )
  )

  assert planner.resolved
  assert planner.local_sequence_verified
  assert planner.field_count == 1
  assert planner.continued_field_count == 0
  assert planner.handoff_links_verified is True
  assert planner.physical_chain_cell_count == 0
  assert planner.termination.reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.termination.physical_termination is False
  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus
    .CONVERGED_LOCAL_CHAIN_AUDIT
  )
  assert audit.converged
  assert audit.local_consistency_verified
  assert audit.handoff_links_verified
  assert audit.fresh_domains_verified
  assert audit.termination_verified
  assert audit.planner_resolved_consistent
  assert audit.physical_chain_cell_count == 0
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False


def test_internal_entropy_characteristic_chain_downgrades_physical_stop() -> None:
  _, field = _internal_field()

  def physical_stop(current, next_field_index, incoming_handoff):
    assert incoming_handoff == current.continuation_boundary
    return MocChainTerminationDecision(
      physical_termination=True,
      reason=MocChainTerminationReason.PHYSICAL_TERMINATION,
      message='fixture attempted a physical stop',
    )

  planner = plan_euler_ambient_first_wedge_entropy_characteristic_field_chain(
    field,
    physical_stop,
    total_field_count=1,
  )

  assert planner.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert planner.termination.physical_termination is False
  assert planner.field_count == 1
  assert planner.physical_chain_cell_count == 0
  assert planner.chain_promotion_blocked
  assert planner.steps[-1].result_termination_reason is (
    MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  )


def test_internal_entropy_characteristic_chain_rejects_replayed_seed() -> None:
  _, field = _internal_field()

  planner = plan_euler_ambient_first_wedge_entropy_characteristic_field_chain_mock(
    field,
    mock=MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainMock(
      next_fields=(field,),
    ),
  )

  assert planner.field_count == 1
  assert planner.termination.reason is MocChainTerminationReason.STATE_NOT_CARRIED
  assert planner.steps[-1].result_kind == 'field-reuse-rejected'
  assert planner.physical_chain_cell_count == 0


def test_internal_entropy_characteristic_chain_audit_rejects_tampered_link() -> None:
  _, field = _internal_field()
  planner = plan_euler_ambient_first_wedge_entropy_characteristic_field_chain_mock(
    field,
  )
  tampered_step = replace(
    planner.steps[0],
    incoming_handoff_fingerprint='tampered',
  )
  tampered = replace(planner, steps=(tampered_step,))

  audit = (
    measure_moc_euler_ambient_first_wedge_entropy_characteristic_field_chain(
      tampered,
    )
  )

  assert audit.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus
    .HANDOFF_FAILURE
  )
  assert not audit.converged
  assert not audit.local_consistency_verified
