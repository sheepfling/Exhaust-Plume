from __future__ import annotations

from math import atan2, tan

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocChainTerminationReason,
  MocEulerAmbientFirstWedgeRemeshStatus,
  MocEulerAmbientPhysicalFieldStatus,
  assemble_euler_ambient_physical_field,
  fit_euler_consistent_shock_boundary,
  plan_euler_ambient_first_wedge_remesh_mock,
  remesh_euler_ambient_first_wedge,
  solve_attached_compression_to_turn,
)
from exhaust_plume.validation import (
  MocEulerAmbientFirstWedgeRemeshRefinementCase,
  MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus,
  MocEulerAmbientPhysicalFieldAuditStatus,
  MocEulerAmbientPhysicalFieldRefinementCase,
  MocEulerAmbientPhysicalFieldRefinementStatus,
  measure_moc_euler_ambient_first_wedge_remesh,
  measure_moc_euler_ambient_first_wedge_remesh_refinement,
  measure_moc_euler_ambient_physical_field,
  measure_moc_euler_ambient_physical_field_refinement,
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


def _refined_shaped_exact_shock(sample_count: int):
  """Build a resolution family with a stable terminal shock tangent."""

  base_turns = (
    0.005,
    0.14,
    0.20,
    0.22,
    0.22,
    0.20,
    0.18,
    0.17,
    0.081637491676426,
  )
  terminal_tangent = -0.5118558424318239
  points = [
    (
      0.5 + 4.93 * distance - 3.36 * distance * distance,
      0.5 - distance,
    )
    for distance in (
      index * 0.5 / (sample_count - 1)
      for index in range(sample_count)
    )
  ]
  if sample_count != 9:
    step = 0.5 / (sample_count - 1)
    points[-1] = (
      points[-2][0] - step / tan(terminal_tangent),
      points[-1][1],
    )
  turns = []
  for index in range(sample_count):
    position = (index / (sample_count - 1)) ** 0.2 * 8.0
    lower = min(int(position), 7)
    fraction = position - lower
    turns.append(
      base_turns[lower] * (1.0 - fraction)
      + base_turns[lower + 1] * fraction
    )
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
    tuple(points),
    tuple(
      state.theta_rad - turn
      for state, turn in zip(upstream_states, turns, strict=True)
    ),
  )


def test_exact_ambient_physical_field_closes_local_mesh_but_stops_chain() -> None:
  shock = _shaped_exact_shock()
  assert shock.converged
  assert shock.local_euler_verified

  result = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )

  assert result.status is MocEulerAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
  assert result.converged
  assert result.physical_closure_verified
  assert result.state_sampling_available
  assert len(result.downstream_handoff) > 1
  assert result.entropy_lineage_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  decision = result.as_chain_termination_decision()
  assert decision.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert decision.physical_termination is False


def test_exact_ambient_physical_field_audit_exposes_cell_gate() -> None:
  shock = _shaped_exact_shock()
  result = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )

  audit = measure_moc_euler_ambient_physical_field(result)

  assert audit.status is MocEulerAmbientPhysicalFieldAuditStatus.CELL_RESIDUAL_FAILURE
  assert not audit.converged
  assert audit.shock_jump_verified
  assert not audit.cell_euler_residuals_verified
  assert audit.physical_field_verified
  assert audit.physical_closure_verified
  assert audit.chain_promotion_blocked
  assert audit.production_claim_allowed is False
  assert audit.maximum_shock_jump_mass_residual is not None
  assert audit.maximum_shock_jump_mass_residual < 1.0e-10
  assert audit.maximum_cell_euler_residual is not None
  assert audit.maximum_cell_euler_residual > 1.0e-2


def test_exact_ambient_physical_field_refinement_requires_first_wedge_remesh() -> None:
  cases = tuple(
    MocEulerAmbientPhysicalFieldRefinementCase(
      resolution=resolution,
      result=(
        assemble_euler_ambient_physical_field(
          shock := _refined_shaped_exact_shock(resolution),
          shock.downstream_static_pressure_Pa[0],
        )
      ),
    )
    for resolution in (9, 17, 33)
  )

  measurement = measure_moc_euler_ambient_physical_field_refinement(
    cases,
    expected_resolutions=(9, 17, 33),
  )

  assert (
    measurement.status
    is MocEulerAmbientPhysicalFieldRefinementStatus.FIRST_WEDGE_REFINEMENT_FAILURE
  )
  assert measurement.resolution_order_verified
  assert measurement.candidate_fields_verified
  assert measurement.shock_jumps_verified
  assert measurement.first_wedge_cell_counts == (1, 1, 1)
  assert not measurement.first_wedge_subdivision_verified
  assert not measurement.refinement_convergence_verified
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_first_wedge_remesh_is_bounded_but_not_a_physical_chain_cell() -> None:
  shock = _shaped_exact_shock()
  physical_field = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )

  remesh = remesh_euler_ambient_first_wedge(
    physical_field,
    subdivision_level=1,
  )
  assert remesh.status is (
    MocEulerAmbientFirstWedgeRemeshStatus.CONVERGED_DIAGNOSTIC_SUBDIVISION
  )
  assert remesh.converged
  assert remesh.cell_count == 4
  assert remesh.state_sample_count == 6
  assert remesh.topology.connected
  assert remesh.topology.forms_closed_zone
  assert remesh.topology.nonmanifold_edge_count == 0
  assert remesh.state_projection_verified
  assert remesh.pressure_lineage_carried
  assert remesh.physical_closure_verified is False
  assert remesh.chain_promotion_blocked
  assert remesh.production_claim_allowed is False
  decision = remesh.as_chain_termination_decision()
  assert decision.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert decision.physical_termination is False
  assert decision.diagnostics['required_next_gate'] == (
    'solver-owned-terminal-wedge-characteristic-remesh-with-'
    'conservative-euler-cell-closure'
  )

  audit = measure_moc_euler_ambient_first_wedge_remesh(remesh)
  assert audit.status.value == (
    'euler_ambient_first_wedge_remesh_cell_residual_failure'
  )
  assert audit.topology_verified
  assert audit.state_projection_verified
  assert audit.pressure_lineage_carried
  assert audit.cell_euler_residuals_finite
  assert not audit.cell_euler_residuals_verified
  assert audit.maximum_cell_euler_residual is not None
  assert audit.maximum_cell_euler_residual > 1.0e-2


def test_first_wedge_remesh_refinement_reduces_residual_without_promotion() -> None:
  shock = _shaped_exact_shock()
  physical_field = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )
  cases = tuple(
    MocEulerAmbientFirstWedgeRemeshRefinementCase(
      subdivision_level=level,
      result=remesh_euler_ambient_first_wedge(
        physical_field,
        subdivision_level=level,
      ),
    )
    for level in (1, 2, 3)
  )

  measurement = measure_moc_euler_ambient_first_wedge_remesh_refinement(
    cases,
    expected_subdivision_levels=(1, 2, 3),
  )

  assert measurement.status is (
    MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus
    .CELL_RESIDUAL_FAILURE
  )
  assert measurement.subdivision_levels == (1, 2, 3)
  assert measurement.subdivision_side_counts == (2, 4, 8)
  assert measurement.cell_counts == (4, 16, 64)
  assert measurement.state_sample_counts == (6, 15, 45)
  assert measurement.topology_verified
  assert measurement.state_projection_verified
  assert measurement.pressure_lineage_verified
  assert measurement.cell_residuals_finite
  assert not measurement.cell_residuals_verified
  assert measurement.subdivision_growth_verified
  assert measurement.residual_nonincreasing_verified
  assert not measurement.refinement_convergence_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False
  assert all(
    right < left
    for left, right in zip(
      measurement.maximum_cell_euler_residuals,
      measurement.maximum_cell_euler_residuals[1:],
    )
  )


def test_first_wedge_remesh_planner_records_ladder_and_stops_before_chain() -> None:
  shock = _shaped_exact_shock()
  physical_field = assemble_euler_ambient_physical_field(
    shock,
    shock.downstream_static_pressure_Pa[0],
  )

  planner = plan_euler_ambient_first_wedge_remesh_mock(physical_field)

  assert planner.resolved
  assert planner.remesh_count == 3
  assert planner.first_wedge_subdivision_verified
  assert [step.result_cell_count for step in planner.steps] == [4, 16, 64]
  assert all(
    step.result_kind == 'diagnostic-remesh-returned'
    and step.result_converged
    and step.result_topology_verified
    and step.result_state_projection_verified
    and step.result_pressure_lineage_carried
    and step.result_physical_closure_verified is False
    and step.result_chain_promotion_blocked
    and step.result_production_claim_allowed is False
    for step in planner.steps
  )
  assert planner.termination.reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
  assert planner.termination.physical_termination is False
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  report = planner.as_report()
  assert report['planning_only'] is True
  assert report['diagnostics']['independent_audit_required'] is True
  assert report['termination']['diagnostics']['required_next_gate'] == (
    'independent-remesh-euler-audit-and-solver-owned-terminal-wedge-'
    'characteristic-closure'
  )
