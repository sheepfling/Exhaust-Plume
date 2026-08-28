from __future__ import annotations

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocCausticBridgeSide,
  MocCausticBridgeStatus,
  MocCausticFamilyBandStatus,
  MocCausticUpstreamContinuationPlannerResult,
  MocCausticUpstreamContinuationStatus,
  MocChainTerminationReason,
  build_caustic_upstream_bridge,
  extend_source_characteristic_strip_centerline_reflection,
  plan_caustic_upstream_bridge_chain,
  plan_caustic_upstream_bridge_invariant_chain,
  plan_caustic_upstream_continuation,
  restart_characteristic_family_from_caustic,
  sample_caustic_upstream_bridge,
  solve_caustic_upstream_continuation,
  solve_marched_attached_shock_from_caustic_upstream_bridge,
  solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
  assemble_source_characteristic_strip,
  build_caustic_shock_seed,
)
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)


def _caustic_bridge_fixture():
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
  fan = solve_underexpanded_expansion_fan(
    exit_state,
    ambient,
    characteristic_count=8,
  )
  reflected = solve_reflected_free_boundary(fan, exit_state, ambient)
  old_family = assemble_source_characteristic_strip(
    reflected.centerline_states,
    reflected.boundary_states,
    exit_state.total_pressure_Pa,
  )
  extension = extend_source_characteristic_strip_centerline_reflection(
    reflected.centerline_states,
    reflected.boundary_states,
    exit_state.total_pressure_Pa,
    ambient.pressure_Pa,
    additional_sample_count=1,
  )
  assert extension.remesh is not None
  assert extension.remesh.caustic_event is not None
  seed = build_caustic_shock_seed(
    extension.remesh.caustic_event,
    exit_state.total_pressure_Pa,
  )
  restart = restart_characteristic_family_from_caustic(
    seed,
    exit_state.total_pressure_Pa,
    ambient.pressure_Pa,
    anchor_edge_index=0,
    sample_count=6,
  )
  assert restart.family_band is not None
  assert restart.family_band.status is MocCausticFamilyBandStatus.CONVERGED_OPEN_BAND
  return old_family, restart.family_band, seed


def test_caustic_bridge_accepts_unique_restarted_family_coverage() -> None:
  old_family, restarted_family, _seed = _caustic_bridge_fixture()
  bridge = build_caustic_upstream_bridge(old_family, restarted_family)

  points = tuple(
    (state.x_m, state.y_m)
    for state in restarted_family.boundary_states[:4]
  )
  result = sample_caustic_upstream_bridge(bridge, points)

  assert result.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH
  assert result.converged
  assert result.sampled_count == 4
  assert result.first_missing_sample_index is None
  assert result.first_ambiguous_sample_index is None
  assert result.side_transition_indices == ()
  assert all(sample.side is MocCausticBridgeSide.RESTARTED_FAMILY for sample in result.samples)
  assert all(not sample.old_family_available for sample in result.samples)
  assert all(sample.restarted_family_available for sample in result.samples)
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked


def test_caustic_continuation_requires_an_explicit_one_sided_branch() -> None:
  old_family, _restarted_family, seed = _caustic_bridge_fixture()

  result = solve_caustic_upstream_continuation(
    old_family,
    seed,
    old_family.total_pressure_Pa,
    101325.0,
    sample_count=6,
  )

  assert result.status is MocCausticUpstreamContinuationStatus.BRANCH_SELECTION_REQUIRED
  assert result.converged is False
  assert result.seam_verified is False
  assert result.bridge is None
  assert len(result.restart_results) == 2
  assert all(restart.converged for restart in result.restart_results)
  assert all(
    restart.caustic_handoff_verified for restart in result.restart_results
  )
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  )


def test_caustic_continuation_builds_exact_selected_branch_seam() -> None:
  old_family, _restarted_family, seed = _caustic_bridge_fixture()

  result = solve_caustic_upstream_continuation(
    old_family,
    seed,
    old_family.total_pressure_Pa,
    101325.0,
    anchor_edge_index=0,
    sample_count=6,
  )

  assert result.status is (
    MocCausticUpstreamContinuationStatus.CONVERGED_BOUNDED_CONTINUATION
  )
  assert result.converged
  assert result.seam_verified
  assert result.state_sampling_available
  assert result.selected_anchor_edge_index == 0
  assert result.bridge is not None
  assert result.event_point_m is not None
  assert result.state_at(result.event_point_m) is not None
  assert result.static_pressure_at(result.event_point_m) is not None
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  )


def test_caustic_continuation_planner_audits_and_retains_nonphysical_stop() -> None:
  old_family, _restarted_family, seed = _caustic_bridge_fixture()

  planner = plan_caustic_upstream_continuation(
    old_family,
    seed,
    old_family.total_pressure_Pa,
    101325.0,
    anchor_edge_index=0,
    sample_count=6,
  )

  assert isinstance(planner, MocCausticUpstreamContinuationPlannerResult)
  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.branch_audit_verified
  assert planner.branch_audit.status is (
    MocCausticUpstreamContinuationStatus.BRANCH_SELECTION_REQUIRED
  )
  assert planner.resolved
  assert planner.continuation.selected_anchor_edge_index == 0
  assert planner.continuation.seam_verified
  assert planner.termination.reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  assert planner.termination.physical_termination is False
  assert planner.physical_closure_verified is False
  assert planner.chain_promotion_blocked
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['chain_cell_appended'] is False
  assert planner.as_report()['branch_audit_verified'] is True


def test_caustic_continuation_planner_requires_branch_before_bridge() -> None:
  old_family, _restarted_family, seed = _caustic_bridge_fixture()

  planner = plan_caustic_upstream_continuation(
    old_family,
    seed,
    old_family.total_pressure_Pa,
    101325.0,
    sample_count=6,
  )

  assert planner.continuation is planner.branch_audit
  assert planner.branch_audit_verified
  assert planner.resolved is False
  assert planner.continuation.bridge is None
  assert planner.termination.reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  assert planner.diagnostics['selected_anchor_edge_index'] is None


def test_caustic_continuation_does_not_hide_an_invalid_side_selector() -> None:
  old_family, _restarted_family, seed = _caustic_bridge_fixture()

  result = solve_caustic_upstream_continuation(
    old_family,
    seed,
    old_family.total_pressure_Pa,
    101325.0,
    anchor_edge_index=0,
    sample_count=6,
    side_at=lambda _point: MocCausticBridgeSide.OLD_FAMILY,
  )

  assert result.status is MocCausticUpstreamContinuationStatus.SEAM_FAILURE
  assert result.converged is False
  assert result.seam_verified is False
  assert result.bridge is not None
  assert result.state_sampling_available is False
  assert result.chain_promotion_blocked


def test_caustic_bridge_preserves_a_gap_between_one_sided_fields() -> None:
  old_family, restarted_family, _seed = _caustic_bridge_fixture()
  bridge = build_caustic_upstream_bridge(old_family, restarted_family)
  assert restarted_family.anchor_point_m is not None

  result = sample_caustic_upstream_bridge(
    bridge,
    (
      restarted_family.anchor_point_m,
      (0.675, 0.052),
      (0.680, 0.050),
    ),
  )

  assert result.status is MocCausticBridgeStatus.DOMAIN_GAP
  assert result.converged is False
  assert result.sampled_count == 2
  assert result.first_missing_sample_index == 2
  assert result.last_valid_point_m == (0.675, 0.052)
  assert 'extrapolation' in result.message


def test_caustic_bridge_selected_side_never_falls_back() -> None:
  old_family, restarted_family, _seed = _caustic_bridge_fixture()
  bridge = build_caustic_upstream_bridge(
    old_family,
    restarted_family,
    side_at=lambda _point: MocCausticBridgeSide.OLD_FAMILY,
  )
  assert restarted_family.anchor_point_m is not None

  result = sample_caustic_upstream_bridge(
    bridge,
    (restarted_family.anchor_point_m,),
  )

  assert result.status is MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP
  assert result.first_missing_sample_index == 0
  assert result.sampled_count == 0
  assert bridge.state_at(restarted_family.anchor_point_m) is None


def test_caustic_bridge_shock_and_planner_keep_open_seam_nonpromotable() -> None:
  old_family, restarted_family, _seed = _caustic_bridge_fixture()
  bridge = build_caustic_upstream_bridge(old_family, restarted_family)
  start = (
    0.5 * (restarted_family.input_edge_points_m[0][0] + restarted_family.input_edge_points_m[1][0]),
    0.5 * (restarted_family.input_edge_points_m[0][1] + restarted_family.input_edge_points_m[1][1]),
  )
  shock = solve_marched_attached_shock_from_caustic_upstream_bridge(
    bridge,
    start,
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start[1]),
    ),
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )

  assert shock.shock.subsonic_terminal_required
  assert shock.coupling.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH
  assert shock.upstream_coupling_verified
  assert shock.physical_closure_verified is False
  assert shock.chain_promotion_blocked

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=17,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(start_x_m=0.2, end_x_m=0.8)
  planner = plan_caustic_upstream_bridge_chain(
    current,
    bridge,
    start_point_m=start,
    end_x_m=1.4,
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start[1]),
    ),
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.status.value == 'solver-terminated'
  assert planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.chain.physical_termination is False
  assert planner.chain.cell_count == 1
  assert len(planner.steps) == 1
  assert planner.steps[0].incoming_handoff_sample_count == len(
    current.continuation_boundary
  )
  assert planner.chain.diagnostics['bridge_status'] == (
    MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH.value
  )
  assert planner.chain.diagnostics['physical_closure_verified'] is False


def test_caustic_bridge_reports_the_first_candidate_point_beyond_the_seam() -> None:
  old_family, restarted_family, _seed = _caustic_bridge_fixture()
  bridge = build_caustic_upstream_bridge(old_family, restarted_family)
  start = old_family.minus_source_states[-1]

  result = solve_marched_attached_shock_from_caustic_upstream_bridge(
    bridge,
    (start.x_m, start.y_m),
    downstream_flow_angle_at=lambda _index, point: 0.05 * max(
      0.0,
      min(1.0, point[1] / start.y_m),
    ),
    sample_count=17,
    shock_angle_tolerance_rad=0.2,
  )

  assert result.shock.status.value == 'upstream_field_failure'
  assert result.shock.sample_count == 1
  assert result.shock.failed_sample_index == 1
  assert result.shock.failed_point_m is not None
  assert result.coupling.status is MocCausticBridgeStatus.DOMAIN_GAP
  assert result.coupling.sampled_count == 1
  assert result.coupling.first_missing_sample_index == 1
  assert result.coupling.first_missing_point_m == result.shock.failed_point_m
  assert result.coupling.first_missing_point_m is not None
  assert result.coupling.first_missing_point_m[0] > start.x_m
  assert result.coupling.first_missing_point_m[1] < start.y_m
  assert result.upstream_coupling_verified is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked


def test_caustic_bridge_invariant_api_preserves_bounded_stop_and_handoff() -> None:
  old_family, restarted_family, seed = _caustic_bridge_fixture()
  bridge = build_caustic_upstream_bridge(old_family, restarted_family)
  assert restarted_family.anchor_point_m is not None
  assert seed.edge_states[1].state is not None
  target_invariant = seed.edge_states[1].state.k_plus

  shock = solve_marched_attached_shock_from_caustic_upstream_bridge_with_invariant_boundary(
    bridge,
    restarted_family.anchor_point_m,
    CharacteristicFamily.PLUS,
    lambda _index, _point: target_invariant,
    sample_count=9,
  )

  assert shock.shock.status.value == 'upstream_field_failure'
  assert shock.coupling.status is MocCausticBridgeStatus.DOMAIN_GAP
  assert shock.coupling.first_missing_sample_index == 4
  assert shock.upstream_coupling_verified is False
  assert shock.physical_closure_verified is False
  assert shock.chain_promotion_blocked

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=17,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(start_x_m=0.2, end_x_m=0.5)
  planner = plan_caustic_upstream_bridge_invariant_chain(
    current,
    bridge,
    start_point_m=restarted_family.anchor_point_m,
    end_x_m=1.4,
    downstream_invariant_family=CharacteristicFamily.PLUS,
    downstream_invariant_at=lambda _index, _point: target_invariant,
    sample_count=9,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.chain.cell_count == 1
  assert len(planner.steps) == 1
  assert planner.steps[0].incoming_handoff_sample_count == len(
    current.continuation_boundary
  )
  assert planner.chain.diagnostics['bridge_status'] == (
    MocCausticBridgeStatus.DOMAIN_GAP.value
  )
