from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocCausticBridgeSide,
  MocCausticBridgeStatus,
  MocCausticShockRemeshStatus,
  MocChainBoundarySample,
  MocChainPlannerKind,
  MocChainTerminationReason,
  MocChainContinuationPolicy,
  MocChainStatus,
  plan_caustic_shock_remesh_chain,
  plan_caustic_shock_remesh_chain_from_upstream_bridge,
  plan_caustic_remesh_downstream_field_chain,
  plan_caustic_remesh_downstream_field_invariant_chain,
  assemble_source_characteristic_strip,
  build_caustic_upstream_bridge,
  build_caustic_shock_seed,
  extend_source_characteristic_strip_centerline_reflection,
  prepare_caustic_shock_remesh,
  restart_characteristic_family_from_caustic,
  solve_caustic_shock_remesh,
  solve_caustic_shock_remesh_from_upstream_bridge,
  solve_reflected_free_boundary,
  solve_uniform_attached_shock_field,
  solve_underexpanded_expansion_fan,
)
from exhaust_plume.models.moc.compression import solve_attached_compression_to_turn
from exhaust_plume.models.moc.primitives import prandtl_meyer_angle_rad
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.validation.moc_measurements import (
  MocCausticRemeshMeasurementStatus,
  MocCausticRemeshObservation,
  measure_moc_caustic_remesh,
)


def _fixture():
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
  return seed, old_family, restart.family_band


def test_caustic_remesh_generates_a_bounded_new_family_field() -> None:
  original_seed, _old_family, restarted_family = _fixture()
  # The production caustic fixture reaches the symmetry line with a positive
  # pre-shock flow angle, so a positive compression cannot end at theta=0.
  # Keep the event topology and pressure evidence, but use a negative-angle
  # one-sided state to exercise the independent remesh executor on a closed
  # supersonic reference path.
  assert original_seed.edge_states[0].state is not None
  negative_state = replace(
    original_seed.edge_states[0].state,
    theta_rad=-0.2,
  )
  seed = replace(
    original_seed,
    edge_states=(replace(original_seed.edge_states[0], state=negative_state), *original_seed.edge_states[1:]),
  )
  assert seed.edge_states[1].state is not None
  target = seed.edge_states[1].state.k_plus
  prepared = prepare_caustic_shock_remesh(
    seed,
    CharacteristicFamily.PLUS,
    target,
    upstream_edge_index=0,
  )
  assert prepared.request is not None
  request = prepared.request
  assert request.local_bridge.downstream_state is not None
  assert restarted_family.anchor_point_m is not None

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(start_x_m=0.2, end_x_m=0.5)

  def upstream_state_at(point: tuple[float, float]) -> CharacteristicState:
    if point == request.event_point_m:
      return request.upstream_state
    return CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=request.upstream_state.theta_rad,
      mach=request.upstream_state.mach,
      gamma=request.upstream_state.gamma,
    )

  def invariant_law(_index: int, point: tuple[float, float]) -> float:
    desired_angle = request.local_bridge.downstream_state.theta_rad * max(
      0.0,
      min(1.0, point[1] / request.event_point_m[1]),
    )
    return desired_angle - prandtl_meyer_angle_rad(
      solve_attached_compression_to_turn(
        upstream_mach=request.upstream_state.mach,
        gamma=request.upstream_state.gamma,
        upstream_pressure_Pa=request.upstream_static_pressure_Pa,
        target_turn_rad=desired_angle - request.upstream_state.theta_rad,
      ).downstream_mach,
      request.upstream_state.gamma,
    )
  result = solve_caustic_shock_remesh(
    request,
    upstream_state_at,
    lambda _point: request.upstream_static_pressure_Pa,
    current.continuation_boundary,
    downstream_invariant_at=invariant_law,
    target_centerline_y_m=0.0,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )

  assert result.status is MocCausticShockRemeshStatus.CONVERGED_COUPLED_REMESH
  assert result.converged
  assert result.event_seam_verified
  assert result.local_bridge_state_verified
  assert result.upstream_coupling_verified
  assert result.shock_curve_verified
  assert result.downstream_field_verified
  assert result.remesh_seam_verified
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked

  measurement = measure_moc_caustic_remesh(
    MocCausticRemeshObservation(remesh_result=result),
  )
  assert measurement.status is MocCausticRemeshMeasurementStatus.CONVERGED
  assert measurement.converged
  assert measurement.bounded_remesh_verified
  assert measurement.remesh_seam_verified
  assert measurement.downstream_field_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.as_report()['field_topology']['forms_closed_zone'] is True

  assert result.shock is not None
  assert result.shock.field is not None
  assert result.bounded_downstream_field_available
  assert result.as_bounded_downstream_field() is result.shock.field
  assert result.shock.field.incoming_handoff_states == tuple(
    sample.state for sample in current.continuation_boundary
  )
  decision = result.as_chain_termination_decision()
  assert decision.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert decision.physical_termination is False

  planner = plan_caustic_shock_remesh_chain(
    current,
    request,
    upstream_state_at,
    lambda _point: request.upstream_static_pressure_Pa,
    downstream_invariant_at=invariant_law,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )
  assert planner.chain.cell_count == 1
  assert planner.chain.physical_termination is False
  assert planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.chain.diagnostics['remesh_status'] == (
    MocCausticShockRemeshStatus.CONVERGED_COUPLED_REMESH.value
  )

  with pytest.raises(ValueError, match='allow_research_continuation=True'):
    plan_caustic_remesh_downstream_field_chain(
      result,
      start_x_m=result.event_point_m[0],
      end_x_m=result.event_point_m[0] + 0.1,
      start_point_at=lambda _field, _cell, _index: (0.7, 0.05),
      downstream_flow_angle_rad=0.2,
    )

  continuation_planner = plan_caustic_remesh_downstream_field_chain(
    result,
    start_x_m=result.event_point_m[0],
    end_x_m=result.event_point_m[0] + 0.1,
    start_point_at=lambda _field, _cell, _index: (0.7, 0.05),
    downstream_flow_angle_rad=0.2,
    policy=MocChainContinuationPolicy(
      max_cells=1,
      require_state_carry=True,
    ),
    allow_research_continuation=True,
  )
  assert continuation_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert continuation_planner.production_claim_allowed is False
  assert continuation_planner.chain.status is MocChainStatus.TRUNCATED
  assert continuation_planner.chain.cell_count == 1
  assert continuation_planner.chain.resolved
  assert continuation_planner.diagnostics['seed_field_model'] == (
    'bounded-caustic-remesh-post-shock-field'
  )
  assert continuation_planner.diagnostics['research_continuation_opt_in'] is True
  assert continuation_planner.diagnostics['remesh_physical_closure_verified'] is False
  assert continuation_planner.diagnostics['remesh_chain_promotion_blocked'] is True

  invariant_continuation_planner = plan_caustic_remesh_downstream_field_invariant_chain(
    result,
    start_x_m=result.event_point_m[0],
    end_x_m=result.event_point_m[0] + 0.1,
    start_point_at=lambda _field, _cell, _index: (0.7, 0.05),
    downstream_invariant_family=CharacteristicFamily.PLUS,
    downstream_invariant_at=lambda _field, _index, _point: 0.0,
    policy=MocChainContinuationPolicy(
      max_cells=1,
      require_state_carry=True,
    ),
    allow_research_continuation=True,
  )
  assert invariant_continuation_planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert invariant_continuation_planner.chain.status is MocChainStatus.TRUNCATED
  assert invariant_continuation_planner.chain.resolved
  assert invariant_continuation_planner.diagnostics['downstream_invariant_family'] == 'C+'
  assert invariant_continuation_planner.diagnostics['remesh_chain_promotion_blocked'] is True


def test_caustic_remesh_rejects_a_changed_event_state() -> None:
  seed, _old_family, _restarted_family = _fixture()
  assert seed.edge_states[1].state is not None
  target = seed.edge_states[1].state.k_plus
  prepared = prepare_caustic_shock_remesh(
    seed,
    CharacteristicFamily.PLUS,
    target,
    upstream_edge_index=0,
  )
  assert prepared.request is not None
  request = prepared.request
  handoff = tuple(
    MocChainBoundarySample(
      state=CharacteristicState(0.5 + 0.01 * index, 0.0, 0.0, 2.0, 1.4),
      total_pressure_Pa=100000.0,
    )
    for index in range(3)
  )
  changed = CharacteristicState(
    x_m=request.upstream_state.x_m,
    y_m=request.upstream_state.y_m,
    theta_rad=request.upstream_state.theta_rad + 0.01,
    mach=request.upstream_state.mach,
    gamma=request.upstream_state.gamma,
  )
  result = solve_caustic_shock_remesh(
    request,
    lambda _point: changed,
    lambda _point: request.upstream_static_pressure_Pa,
    handoff,
  )

  assert result.status is MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE
  assert result.remesh_seam_verified is False
  assert result.as_chain_termination_decision().reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC


def test_caustic_remesh_uses_the_bounded_old_restarted_family_bridge() -> None:
  original_seed, old_family, _restarted_family = _fixture()
  assert original_seed.edge_states[0].state is not None
  negative_state = replace(
    original_seed.edge_states[0].state,
    theta_rad=-0.2,
  )
  seed = replace(
    original_seed,
    edge_states=(
      replace(original_seed.edge_states[0], state=negative_state),
      *original_seed.edge_states[1:],
    ),
  )
  assert seed.edge_states[1].state is not None
  restart = restart_characteristic_family_from_caustic(
    seed,
    2.0e6,
    101325.0,
    anchor_edge_index=0,
    sample_count=6,
  )
  assert restart.family_band is not None
  bridge = build_caustic_upstream_bridge(
    old_family,
    restart.family_band,
    side_at=lambda _point: MocCausticBridgeSide.RESTARTED_FAMILY,
  )
  prepared = prepare_caustic_shock_remesh(
    seed,
    CharacteristicFamily.PLUS,
    seed.edge_states[1].state.k_plus,
    upstream_edge_index=0,
  )
  assert prepared.request is not None
  request = prepared.request
  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(start_x_m=0.2, end_x_m=0.5)

  result = solve_caustic_shock_remesh_from_upstream_bridge(
    request,
    bridge,
    current.continuation_boundary,
    downstream_invariant_at=lambda _index, _point: request.downstream_invariant_target,
    target_centerline_y_m=0.0,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )

  assert result.status is MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE
  assert result.upstream_bridge_verified is False
  assert result.upstream_bridge_audit is not None
  assert result.upstream_bridge_audit.status is MocCausticBridgeStatus.DOMAIN_GAP
  assert result.upstream_bridge_audit.sampled_count == 1
  assert result.upstream_bridge_audit.first_missing_sample_index == 1
  assert result.shock is not None
  assert result.shock.failed_sample_index == 1
  assert result.upstream_bridge_audit.first_missing_point_m == result.shock.failed_point_m
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked

  measurement = measure_moc_caustic_remesh(
    MocCausticRemeshObservation(
      remesh_result=result,
      upstream_bridge=bridge,
    ),
  )
  assert measurement.status is MocCausticRemeshMeasurementStatus.UPSTREAM_FAILURE
  assert measurement.upstream_bridge_verified is False
  assert measurement.first_missing_sample_index == 1
  assert measurement.first_missing_point_m == result.shock.failed_point_m

  planner = plan_caustic_shock_remesh_chain_from_upstream_bridge(
    current,
    request,
    bridge,
    downstream_invariant_at=lambda _index, _point: request.downstream_invariant_target,
    target_centerline_y_m=0.0,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )
  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.cell_count == 1
  assert planner.chain.physical_termination is False
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.diagnostics['strict_bridge_required'] is True
  assert planner.chain.diagnostics['remesh_report']['upstream_bridge_audit']['status'] == (
    MocCausticBridgeStatus.DOMAIN_GAP.value
  )


def test_caustic_remesh_planner_carries_exact_perimeter_to_typed_stop() -> None:
  seed, _old_family, _restarted_family = _fixture()
  assert seed.edge_states[1].state is not None
  prepared = prepare_caustic_shock_remesh(
    seed,
    CharacteristicFamily.PLUS,
    seed.edge_states[1].state.k_plus,
    upstream_edge_index=0,
  )
  assert prepared.request is not None
  request = prepared.request
  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(start_x_m=0.2, end_x_m=0.5)
  changed = replace(
    request.upstream_state,
    theta_rad=request.upstream_state.theta_rad + 0.01,
  )

  planner = plan_caustic_shock_remesh_chain(
    current,
    request,
    lambda _point: changed,
    lambda _point: request.upstream_static_pressure_Pa,
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.cell_count == 1
  assert planner.chain.physical_termination is False
  assert planner.chain.termination_reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  assert len(planner.steps) == 1
  assert planner.steps[0].boundary_kind.value == 'post-shock-field-perimeter'
  assert planner.steps[0].incoming_handoff_sample_count == len(
    current.continuation_boundary
  )
  assert planner.steps[0].incoming_handoff_fingerprint is not None
  assert planner.chain.diagnostics['remesh_status'] == (
    MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE.value
  )
  assert planner.chain.diagnostics['remesh_report']['status'] == (
    MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE.value
  )
  assert planner.diagnostics['one_step_domain'] is True
