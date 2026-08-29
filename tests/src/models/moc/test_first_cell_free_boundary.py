from __future__ import annotations

from dataclasses import replace

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocBoundedUpstreamFieldSource,
  MocChainTerminationReason,
  MocFirstCellFreeBoundaryCorrectionStatus,
  plan_first_cell_free_boundary_correction,
  solve_first_cell_free_boundary_correction,
  solve_marched_attached_shock_field,
)
from exhaust_plume.validation import (
  MocFirstCellFreeBoundaryCorrectionMeasurementStatus,
  MocFirstCellFreeBoundaryCorrectionRefinementMeasurementStatus,
  measure_first_cell_free_boundary_correction,
  measure_first_cell_free_boundary_correction_refinement,
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
