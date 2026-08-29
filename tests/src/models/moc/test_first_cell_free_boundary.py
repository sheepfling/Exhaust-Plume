from __future__ import annotations

from dataclasses import replace

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientBoundarySample,
  MocAmbientClosedPostShockChainCandidate,
  MocBoundedUpstreamFieldSource,
  MocChainTerminationReason,
  MocFirstCellFreeBoundaryCorrectionStatus,
  MocFirstCellResearchChainPlannerResult,
  MocPrescribedAmbientClosedPostShockChainMock,
  MocTerminalReflectionPatchAmbientClosureChainReference,
  MocChainContinuationPolicy,
  plan_first_cell_free_boundary_correction,
  plan_first_cell_geometry_owned_research_chain,
  solve_first_cell_free_boundary_correction,
  solve_first_cell_geometry_owned_candidate,
  solve_marched_attached_shock_field,
)
from exhaust_plume.validation import (
  MocFirstCellFreeBoundaryCorrectionMeasurementStatus,
  MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus,
  MocFirstCellResearchChainMeasurementStatus,
  MocFirstCellResearchChainRefinementCase,
  MocFirstCellResearchChainRefinementMeasurementStatus,
  measure_first_cell_free_boundary_correction,
  measure_first_cell_free_boundary_correction_refinement,
  measure_first_cell_geometry_owned_research_chain_refinement,
)


def _correction_inputs(sample_count: int = 9) -> tuple[
  MocBoundedUpstreamFieldSource,
  tuple[tuple[float, float], ...],
  float,
]:
  upstream = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )
  source = MocBoundedUpstreamFieldSource(
    state_at=lambda point: replace(
      upstream,
      x_m=point[0],
      y_m=point[1],
    ),
    static_pressure_at=lambda _point: 100000.0,
    model='uniform-correction-test-source',
    domain_x_extent_m=(0.0, 10.0),
    domain_y_extent_m=(0.0, 0.5),
    upstream_coupling_verified=True,
  )
  seed = solve_marched_attached_shock_field(
    source.state_at,
    source.static_pressure_at,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=sample_count,
  )
  assert seed.shock_fit is not None
  shock_points = tuple(
    sample.point_m for sample in seed.shock_fit.boundary_states
  )
  first = seed.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  return source, shock_points, ambient_pressure


def test_free_boundary_correction_records_explicit_no_bracket_and_audit() -> None:
  source, shock_points, ambient_pressure = _correction_inputs()

  result = solve_first_cell_free_boundary_correction(
    source,
    shock_points,
    ambient_pressure,
  )

  assert result.status is MocFirstCellFreeBoundaryCorrectionStatus.NO_BRACKET
  assert result.converged is False
  assert result.scalar_axis_pressure_verified is False
  assert result.physical_closure_verified is False
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert len(result.trials) == 3
  assert all(trial.residual is not None for trial in result.trials)
  assert result.trials[0].residual is not None
  assert result.trials[1].residual is not None
  assert result.trials[0].residual * result.trials[1].residual > 0.0

  decision = result.as_chain_termination_decision()
  assert decision.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert decision.physical_termination is False

  measurement = measure_first_cell_free_boundary_correction(result)

  assert measurement.status is (
    MocFirstCellFreeBoundaryCorrectionMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.shape_family_verified
  assert measurement.trial_residuals_verified
  assert measurement.selected_trial_verified
  assert measurement.scalar_root_verified
  assert measurement.axis_boundary_verified is False
  assert measurement.selected_field_audit_verified
  assert measurement.selected_field_measurement is not None
  assert measurement.selected_field_measurement.converged
  assert measurement.physical_closure_verified is False
  assert measurement.fidelity_isolation_verified

  planner = plan_first_cell_free_boundary_correction(result)
  assert planner.correction is result
  assert planner.termination == decision
  assert planner.resolved is False
  assert planner.physical_termination is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.as_report()['diagnostics']['continued_cell_callback_invoked'] is False


def test_free_boundary_correction_retains_bounded_source_failure() -> None:
  source, shock_points, ambient_pressure = _correction_inputs()
  bounded_source = replace(
    source,
    state_at=lambda point: (
      None if point[0] > 0.6 else source.state_at(point)
    ),
    static_pressure_at=lambda point: (
      None if point[0] > 0.6 else source.static_pressure_at(point)
    ),
    domain_x_extent_m=(0.0, 0.6),
  )

  result = solve_first_cell_free_boundary_correction(
    bounded_source,
    shock_points,
    ambient_pressure,
  )

  assert result.status is MocFirstCellFreeBoundaryCorrectionStatus.UPSTREAM_FIELD_FAILURE
  assert result.converged is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  measurement = measure_first_cell_free_boundary_correction(result)
  assert measurement.status is (
    MocFirstCellFreeBoundaryCorrectionMeasurementStatus.CONVERGED
  )
  assert measurement.fidelity_isolation_verified
  assert measurement.physical_closure_verified is False


def test_free_boundary_correction_rejects_shape_bracket_without_seed() -> None:
  source, shock_points, ambient_pressure = _correction_inputs()

  result = solve_first_cell_free_boundary_correction(
    source,
    shock_points,
    ambient_pressure,
    shape_scale_lower=1.1,
    shape_scale_upper=1.2,
  )

  assert result.status is MocFirstCellFreeBoundaryCorrectionStatus.INVALID_INPUT
  assert result.converged is False
  assert result.trials == ()


def test_free_boundary_correction_refinement_is_independently_audited() -> None:
  corrections = []
  for sample_count in (5, 9, 17):
    source, shock_points, ambient_pressure = _correction_inputs(sample_count)
    corrections.append(
      solve_first_cell_free_boundary_correction(
        source,
        shock_points,
        ambient_pressure,
        shape_scale_lower=0.95,
        shape_scale_upper=1.05,
      )
    )

  measurement = measure_first_cell_free_boundary_correction_refinement(
    corrections,
    expected_sample_counts=(5, 9, 17),
    expected_status=MocFirstCellFreeBoundaryCorrectionStatus.NO_BRACKET,
  )

  assert measurement.status is (
    MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.sample_counts == (5, 9, 17)
  assert measurement.sample_count_order_verified
  assert measurement.expected_sample_counts_verified
  assert measurement.shape_family_verified
  assert measurement.shape_bracket_verified
  assert measurement.outcome_consistency_verified
  assert measurement.residuals_verified
  assert measurement.residual_spread is not None
  assert measurement.fidelity_isolation_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_geometry_owned_candidate_can_seed_reflected_research_chain_without_promotion() -> None:
  source, shock_points, ambient_pressure = _correction_inputs()
  candidate = solve_first_cell_geometry_owned_candidate(
    source,
    shock_points,
    ambient_pressure,
  )

  planner = plan_first_cell_geometry_owned_research_chain(
    candidate,
    start_x_m=0.5,
    end_x_m=8.0,
    reference=MocTerminalReflectionPatchAmbientClosureChainReference(
      total_cell_count=3,
    ),
    policy=MocChainContinuationPolicy(
      max_cells=4,
      require_state_carry=True,
    ),
  )

  assert isinstance(planner, MocFirstCellResearchChainPlannerResult)
  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.chain_planner is not None
  assert planner.chain_planner.chain.resolved
  assert planner.cell_count == 3
  assert planner.continued_cell_count == 2
  assert planner.resolved
  assert planner.first_cell_handoff_verified
  assert planner.continued_chain_audit_verified
  assert planner.research_audit_accepted
  assert planner.handoff_links_verified is True
  assert planner.physical_closure_verified
  assert planner.physical_fields[0] is candidate.field
  assert len(planner.physical_fields) == planner.cell_count
  assert planner.research_chain_measurement is not None
  assert planner.research_chain_measurement.status is (
    MocFirstCellResearchChainMeasurementStatus.CONVERGED
  )
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.canonical_free_boundary_verified is False
  assert planner.canonical_euler_verified is False
  assert planner.external_validation_verified is False
  assert planner.termination.reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  report = planner.as_report()
  assert report['research_audit_accepted'] is True
  assert report['physical_field_count'] == 3
  assert report['diagnostics']['first_cell_field_identity_verified'] is True
  assert report['diagnostics']['continued_cell_callback_invoked'] is True


def test_geometry_owned_research_chain_is_deterministic_over_resolution() -> None:
  source, _, ambient_pressure = _correction_inputs()
  cases = []
  for sample_count in (5, 9, 17):
    seed = solve_marched_attached_shock_field(
      source.state_at,
      source.static_pressure_at,
      (0.5, 0.5),
      downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
      sample_count=sample_count,
    )
    assert seed.shock_fit is not None
    candidate = solve_first_cell_geometry_owned_candidate(
      source,
      tuple(sample.point_m for sample in seed.shock_fit.boundary_states),
      ambient_pressure,
    )

    def run_chain() -> MocFirstCellResearchChainPlannerResult:
      result = plan_first_cell_geometry_owned_research_chain(
        candidate,
        start_x_m=0.5,
        end_x_m=8.0,
        reference=MocTerminalReflectionPatchAmbientClosureChainReference(
          total_cell_count=3,
          sample_count=sample_count,
        ),
        policy=MocChainContinuationPolicy(
          max_cells=4,
          require_state_carry=True,
        ),
      )
      assert isinstance(result, MocFirstCellResearchChainPlannerResult)
      return result

    cases.append(
      MocFirstCellResearchChainRefinementCase(
        sample_count=sample_count,
        planner=run_chain(),
        repeat_planner=run_chain(),
      )
    )

  measurement = measure_first_cell_geometry_owned_research_chain_refinement(
    cases,
    expected_sample_counts=(5, 9, 17),
    expected_cell_count=3,
  )

  assert measurement.status is (
    MocFirstCellResearchChainRefinementMeasurementStatus.CONVERGED
  )
  assert measurement.converged
  assert measurement.sample_counts == (5, 9, 17)
  assert measurement.cell_count == 3
  assert measurement.sample_count_order_verified
  assert measurement.expected_sample_counts_verified
  assert measurement.cell_count_consistent
  assert measurement.planner_kind_consistent
  assert measurement.termination_consistency_verified
  assert measurement.geometry_shape_verified
  assert measurement.deterministic_repeats_verified
  assert measurement.handoff_links_verified is True
  assert measurement.physical_closure_verified
  assert measurement.fidelity_isolation_verified
  assert measurement.refinement_convergence_verified
  report = measurement.as_report()
  assert report['operator_id'] == (
    'op.moc.first-cell-geometry-owned-research-chain-refinement'
  )
  assert report['chain_promotion_blocked'] is True
  assert report['production_claim_allowed'] is False
  assert report['canonical_free_boundary_verified'] is False
  assert report['canonical_euler_verified'] is False
  assert report['external_validation_verified'] is False


def test_geometry_owned_candidate_mock_keeps_bounded_source_stop_typed() -> None:
  source, shock_points, ambient_pressure = _correction_inputs()
  candidate = solve_first_cell_geometry_owned_candidate(
    source,
    shock_points,
    ambient_pressure,
  )
  assert candidate.field is not None
  state = source.state_at((2.0, 0.5))
  assert state is not None
  ambient_sample = MocAmbientBoundarySample(
    point_m=(2.0, 0.5),
    state=state,
    total_pressure_Pa=100000.0,
  )
  candidate_mock = MocPrescribedAmbientClosedPostShockChainMock(
    candidates=(
      MocAmbientClosedPostShockChainCandidate(
        shock_points_m=((2.0, 0.5), (2.1, 0.25), (2.2, 0.0)),
        downstream_flow_angles_rad=(0.0, 0.0, 0.0),
        ambient_boundary=(
          ambient_sample,
          MocAmbientBoundarySample(
            point_m=(2.1, 0.25),
            state=state,
            total_pressure_Pa=100000.0,
          ),
          MocAmbientBoundarySample(
            point_m=(2.2, 0.0),
            state=state,
            total_pressure_Pa=100000.0,
          ),
        ),
        ambient_pressure_Pa=ambient_pressure,
        end_x_m=3.0,
      ),
    ),
  )

  planner = plan_first_cell_geometry_owned_research_chain(
    candidate,
    start_x_m=0.5,
    end_x_m=1.0,
    mock=candidate_mock,
    policy=MocChainContinuationPolicy(
      max_cells=2,
      require_state_carry=True,
    ),
  )

  assert planner.planner_kind.value == 'prescribed-boundary-mock'
  assert planner.chain_planner is not None
  assert planner.chain_planner.chain.cell_count == 1
  assert planner.termination.reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.termination.physical_termination is False
  assert planner.first_cell_handoff_verified
  assert planner.resolved is False
  assert planner.research_audit_accepted is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.as_report()['diagnostics']['continued_cell_callback_invoked'] is False
