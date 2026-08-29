from __future__ import annotations

from dataclasses import replace
from math import tan

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocEulerPostShockFieldStatus,
  MocChainTerminationReason,
  assemble_euler_post_shock_field,
  fit_euler_consistent_shock_boundary,
  plan_euler_post_shock_field_chain_mock,
  solve_attached_compression_to_turn,
)
from exhaust_plume.validation import (
  MocEulerPostShockFieldAuditStatus,
  MocEulerPostShockFieldChainAuditStatus,
  measure_moc_euler_post_shock_field,
  measure_moc_euler_post_shock_field_chain,
)


def _axis_aligned_exact_shock(sample_count: int = 6):
  compression = solve_attached_compression_to_turn(
    upstream_mach=2.0,
    gamma=1.4,
    upstream_pressure_Pa=100000.0,
    target_turn_rad=0.2,
  )
  assert compression.beta_rad is not None
  shock_angle = 0.2 - compression.beta_rad
  points = tuple(
    (
      0.5 + index * (-0.5 / (sample_count - 1) / tan(shock_angle)),
      0.5 - index * (0.5 / (sample_count - 1)),
    )
    for index in range(sample_count)
  )
  result = fit_euler_consistent_shock_boundary(
    tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=0.2,
        mach=2.0,
        gamma=1.4,
      )
      for point in points
    ),
    (100000.0,) * sample_count,
    points,
    (0.0,) * sample_count,
  )
  assert result.converged
  return result


def test_local_post_shock_field_closes_topology_and_carries_centerline_frontier() -> None:
  field = assemble_euler_post_shock_field(_axis_aligned_exact_shock())

  assert field.status is MocEulerPostShockFieldStatus.CONVERGED_LOCAL_CLOSED
  assert field.converged
  assert field.closed_topology_verified
  assert field.topology.forms_closed_zone
  assert field.topology.nonmanifold_edge_count == 0
  assert field.state_sampling_available
  assert field.terminal_mesh_completion_synthetic
  assert not field.physical_closure_verified
  assert field.chain_promotion_blocked
  assert not field.production_claim_allowed
  assert len(field.downstream_handoff) == 6
  assert field.state_at((0.85, 0.23)) is not None
  assert field.state_at((1.6, 0.2)) is None
  assert field.static_pressure_at((0.85, 0.23)) is not None
  assert field.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )

  audit = measure_moc_euler_post_shock_field(field)

  assert audit.status is MocEulerPostShockFieldAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.local_consistency_verified
  assert audit.shock_jump_verified
  assert audit.uniform_state_verified
  assert audit.centerline_geometry_verified
  assert audit.interior_geometry_verified
  assert audit.topology_verified
  assert audit.cell_euler_residuals_verified
  assert audit.fidelity_flags_verified


def test_local_post_shock_chain_reassembles_fresh_fields_and_stops_typed() -> None:
  field = assemble_euler_post_shock_field(_axis_aligned_exact_shock())
  chain = plan_euler_post_shock_field_chain_mock(field)

  assert chain.resolved
  assert chain.field_count == 3
  assert chain.continued_field_count == 2
  assert chain.handoff_links_verified
  assert chain.termination.reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert not chain.physical_closure_verified
  assert chain.chain_promotion_blocked
  assert not chain.production_claim_allowed

  extents = tuple(result.domain_x_extent_m for result in chain.fields)
  assert all(
    previous is not None
    and current is not None
    and current[0] > previous[1]
    for previous, current in zip(extents[:-1], extents[1:], strict=True)
  )

  audit = measure_moc_euler_post_shock_field_chain(chain)

  assert audit.status is MocEulerPostShockFieldChainAuditStatus.CONVERGED_LOCAL_AUDIT
  assert audit.local_consistency_verified
  assert audit.field_audits_verified
  assert audit.fresh_domains_verified
  assert audit.handoff_links_verified
  assert audit.termination_verified
  assert audit.fidelity_flags_verified


def test_local_post_shock_field_rejects_nonuniform_downstream_state() -> None:
  shock = _axis_aligned_exact_shock()
  altered = replace(
    shock.downstream_states[2],
    x_m=shock.shock_points_m[2][0],
    y_m=shock.shock_points_m[2][1],
    mach=shock.downstream_states[2].mach + 0.05,
  )
  nonuniform = replace(
    shock,
    downstream_states=tuple(
      altered if index == 2 else state
      for index, state in enumerate(shock.downstream_states)
    ),
  )

  field = assemble_euler_post_shock_field(nonuniform)

  assert field.status is MocEulerPostShockFieldStatus.NONUNIFORM_DOWNSTREAM_STATE
  assert not field.converged
  assert not field.downstream_handoff
