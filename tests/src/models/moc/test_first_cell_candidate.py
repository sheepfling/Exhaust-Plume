from __future__ import annotations

from dataclasses import replace

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocBoundedUpstreamFieldSource,
  MocFirstCellCandidateStatus,
  solve_marched_attached_shock_field,
  solve_first_cell_geometry_owned_candidate,
)
from exhaust_plume.validation import (
  MOC_FIRST_CELL_CANDIDATE_OPERATOR_ID,
  MocFirstCellCandidateMeasurementStatus,
  measure_first_cell_geometry_owned_candidate,
)


def _candidate_inputs() -> tuple[
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
    model='uniform-test-source',
    domain_x_extent_m=(0.0, 10.0),
    domain_y_extent_m=(0.0, 0.5),
    upstream_coupling_verified=True,
  )
  seed = solve_marched_attached_shock_field(
    source.state_at,
    source.static_pressure_at,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
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


def test_geometry_owned_candidate_closes_local_field_without_angle_callback() -> None:
  source, shock_points, ambient_pressure = _candidate_inputs()

  result = solve_first_cell_geometry_owned_candidate(
    source,
    shock_points,
    ambient_pressure,
  )

  assert result.status is MocFirstCellCandidateStatus.CONVERGED_LOCAL_PHYSICAL_FIELD
  assert result.converged
  assert result.local_physical_closure_verified
  assert result.physical_closure_verified
  assert result.field is not None
  assert result.field.physical_closure_verified
  assert result.field.state_sampling_available
  assert result.field.upstream_shock_coupling_verified
  assert result.centerline_flow_angle_residual_rad is not None
  assert abs(result.centerline_flow_angle_residual_rad) <= 1.0e-8
  assert result.canonical_free_boundary_verified is False
  assert result.canonical_euler_verified is False
  assert result.external_validation_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  chain_decision = result.as_chain_termination_decision()
  assert chain_decision.physical_termination is False
  assert chain_decision.reason.value == 'fidelity-not-allowed'
  assert chain_decision.diagnostics['chain_promotion_blocked'] is True

  measurement = measure_first_cell_geometry_owned_candidate(result)

  assert measurement.status is MocFirstCellCandidateMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.physical_closure_verified
  assert measurement.as_report()['operator_id'] == MOC_FIRST_CELL_CANDIDATE_OPERATOR_ID
  assert measurement.shock_fit_verified
  assert measurement.shock_rankine_hugoniot_verified
  assert measurement.shock_pressure_loss_verified
  assert measurement.attachment_pressure_verified
  assert measurement.ambient_boundary_verified
  assert measurement.field_topology_verified
  assert measurement.field_state_sampling_verified
  assert measurement.upstream_shock_coupling_verified
  assert measurement.canonical_free_boundary_verified is False
  assert measurement.canonical_euler_verified is False
  assert measurement.external_validation_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_geometry_owned_candidate_stops_at_bounded_source_boundary() -> None:
  source, shock_points, ambient_pressure = _candidate_inputs()
  bounded_source = replace(
    source,
    state_at=lambda point: (
      None if point[0] > 0.8 else source.state_at(point)
    ),
    static_pressure_at=lambda point: (
      None if point[0] > 0.8 else source.static_pressure_at(point)
    ),
    domain_x_extent_m=(0.0, 0.8),
  )

  result = solve_first_cell_geometry_owned_candidate(
    bounded_source,
    shock_points,
    ambient_pressure,
  )

  assert result.status is MocFirstCellCandidateStatus.UPSTREAM_FIELD_FAILURE
  assert result.converged is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.production_claim_allowed is False
  assert 'upstream source returned no' in result.message
  assert result.as_chain_termination_decision().reason.value == (
    'upstream-field-boundary'
  )


def test_geometry_owned_candidate_rejects_ambient_below_upstream_pressure() -> None:
  source, shock_points, _ambient_pressure = _candidate_inputs()

  result = solve_first_cell_geometry_owned_candidate(
    source,
    shock_points,
    50000.0,
  )

  assert result.status is MocFirstCellCandidateStatus.ATTACHMENT_FAILURE
  assert result.converged is False
  assert result.physical_closure_verified is False
  assert result.start_attachment_pressure_residual is not None
  assert result.start_attachment_pressure_residual > 0.0
  assert 'cannot reduce' in result.message
