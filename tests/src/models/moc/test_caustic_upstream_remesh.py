from __future__ import annotations

from dataclasses import replace
from math import cos, sin

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicState,
  MocCausticUpstreamRemeshRequest,
  MocCausticUpstreamRemeshStatus,
  MocChainContinuationPolicy,
  MocChainPlannerKind,
  MocChainStatus,
  MocChainTerminationReason,
  MocPostShockChainCellSolve,
  extend_source_characteristic_strip_centerline_reflection,
  assemble_source_characteristic_strip,
  build_caustic_shock_seed,
  inverse_prandtl_meyer_angle_rad,
  plan_caustic_upstream_remesh_shock_chain,
  plan_caustic_upstream_remesh_shock_chain_sequence,
  solve_caustic_upstream_remesh,
  solve_marched_attached_shock_from_source_strip,
  solve_reflected_free_boundary,
  solve_uniform_attached_shock_field,
  solve_underexpanded_expansion_fan,
)
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)


def _seed():
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
  assert seed.converged
  return seed, exit_state.total_pressure_Pa


def _conditioned_traces(
  seed,
  total_pressure_Pa,
  *,
  invariant_step=0.004,
  theta_step=-0.006,
):
  selected = seed.edge_states[0].state
  assert selected is not None
  event = (selected.x_m, selected.y_m)
  centerline_states = []
  outer_states = []
  for index in range(6):
    k_plus = selected.k_plus + invariant_step * index
    theta = selected.theta_rad + theta_step * index
    inverse_plus = inverse_prandtl_meyer_angle_rad(-k_plus, selected.gamma)
    inverse_outer = inverse_prandtl_meyer_angle_rad(theta - k_plus, selected.gamma)
    assert inverse_plus.value is not None
    assert inverse_outer.value is not None
    centerline_probe = CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=inverse_plus.value,
      gamma=selected.gamma,
    )
    outer_probe = CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=theta,
      mach=inverse_outer.value,
      gamma=selected.gamma,
    )
    characteristic_angle = 0.5 * (
      centerline_probe.theta_rad
      + centerline_probe.mu_rad
      + outer_probe.theta_rad
      + outer_probe.mu_rad
    )
    y = event[1] * (1.0 - 0.12 * index)
    if index == 0:
      centerline_x = event[0] - event[1] * cos(characteristic_angle) / sin(
        characteristic_angle
      )
    else:
      centerline_x = 0.5191348811250018 + 0.027 * index
    centerline_states.append(
      CharacteristicState(
        x_m=centerline_x,
        y_m=0.0,
        theta_rad=0.0,
        mach=inverse_plus.value,
        gamma=selected.gamma,
      )
    )
    if index == 0:
      outer_states.append(selected)
    else:
      distance = y / sin(characteristic_angle)
      outer_states.append(
        CharacteristicState(
          x_m=centerline_x + distance * cos(characteristic_angle),
          y_m=y,
          theta_rad=theta,
          mach=inverse_outer.value,
          gamma=selected.gamma,
        )
      )
  # Keep this helper tied to the actual source-strip primitive.  If the
  # numerical construction changes, the test should fail before the remesh
  # wrapper can hide a geometry regression.
  strip = assemble_source_characteristic_strip(
    centerline_states,
    outer_states,
    total_pressure_Pa,
  )
  assert strip.converged
  return tuple(centerline_states), tuple(outer_states)


def _request(*, invariant_step=0.004, theta_step=-0.006):
  seed, total_pressure = _seed()
  centerline, outer = _conditioned_traces(
    seed,
    total_pressure,
    invariant_step=invariant_step,
    theta_step=theta_step,
  )
  return MocCausticUpstreamRemeshRequest(
    seed=seed,
    upstream_edge_index=0,
    centerline_source_states=centerline,
    outer_source_states=outer,
    total_pressure_Pa=total_pressure,
  )


def test_caustic_upstream_remesh_assembles_an_explicit_bounded_cauchy_field():
  request = _request()

  result = solve_caustic_upstream_remesh(request)

  assert result.status is MocCausticUpstreamRemeshStatus.CONVERGED_BOUNDED_FIELD
  assert result.converged
  assert result.state_sampling_available
  assert result.event_seam_verified
  assert result.centerline_trace_verified
  assert result.outer_trace_verified
  assert result.source_field_verified
  assert result.strip is not None
  assert result.strip.converged
  assert result.strip.state_at(request.event_point_m) is not None
  assert result.strip.static_pressure_at(request.event_point_m) == pytest.approx(
    request.seed.edge_states[0].static_pressure_Pa
  )
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  report = result.as_report()
  assert report['strip']['topology_forms_closed_zone'] is True
  assert report['physical_closure_verified'] is False
  assert report['request']['outer_trace_generation'] == (
    'caller-supplied-coupled-remesher-data'
  )
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  )


def test_caustic_upstream_remesh_rejects_an_event_trace_that_does_not_seam():
  request = _request()
  assert request.outer_source_states[0].x_m > 0.0
  changed_outer = (
    replace(request.outer_source_states[0], x_m=request.outer_source_states[0].x_m + 1.0e-3),
    *request.outer_source_states[1:],
  )
  changed_request = replace(
    request,
    outer_source_states=changed_outer,
  )

  result = solve_caustic_upstream_remesh(changed_request)

  assert result.status is MocCausticUpstreamRemeshStatus.EVENT_SEAM_FAILURE
  assert result.converged is False
  assert result.event_seam_verified is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  )


def test_caustic_upstream_remesh_rejects_centerline_data_after_the_event():
  request = _request()
  changed_centerline = (
    *request.centerline_source_states[:-1],
    replace(
      request.centerline_source_states[-1],
      x_m=request.outer_source_states[0].x_m + 1.0e-3,
    ),
  )
  changed_request = replace(
    request,
    centerline_source_states=changed_centerline,
  )

  result = solve_caustic_upstream_remesh(changed_request)

  assert result.status is MocCausticUpstreamRemeshStatus.CENTERLINE_TRACE_FAILURE
  assert result.event_seam_verified
  assert result.centerline_trace_verified is False
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )


def test_caustic_upstream_remesh_is_a_bounded_source_for_one_chain_attempt():
  request = _request()
  remesh = solve_caustic_upstream_remesh(request)
  assert remesh.strip is not None

  direct = solve_marched_attached_shock_from_source_strip(
    remesh.strip,
    request.event_point_m,
    downstream_flow_angle_rad=0.2,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
  )
  assert direct.sample_count == 4
  assert direct.failed_sample_index == 4
  assert direct.status.value == 'upstream_field_failure'

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert reference.field is not None
  planner = plan_caustic_upstream_remesh_shock_chain(
    reference.field,
    remesh,
    start_point_m=request.event_point_m,
    start_x_m=0.2,
    end_x_m=0.6,
    downstream_flow_angle_rad=0.2,
    sample_count=9,
    shock_angle_tolerance_rad=0.2,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.status is MocChainStatus.SOLVER_TERMINATED
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  assert planner.chain.physical_termination is False
  assert len(planner.steps) == 1
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.steps[0].result_termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['caustic_upstream_remesh']['status'] == (
    MocCausticUpstreamRemeshStatus.CONVERGED_BOUNDED_FIELD.value
  )


def test_caustic_upstream_remesh_sequence_requires_fresh_domains_per_cell(
  monkeypatch: pytest.MonkeyPatch,
):
  initial = solve_caustic_upstream_remesh(_request())
  replacement = solve_caustic_upstream_remesh(
    _request(invariant_step=0.005, theta_step=-0.005)
  )
  assert initial.converged and initial.strip is not None
  assert replacement.converged and replacement.strip is not None
  assert initial.strip is not replacement.strip

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert reference.field is not None
  source_strips = []

  def fake_source_solver(
    current,
    _next_cell_index,
    incoming_handoff,
    source_strip,
    **kwargs,
  ):
    del kwargs
    source_strips.append(source_strip)
    incoming = tuple(incoming_handoff)
    next_field = solve_uniform_attached_shock_field(
      CharacteristicState(
        current.end_x_m + 0.01,
        0.25,
        -0.2,
        2.0,
        1.4,
      ),
      100000.0,
      (current.end_x_m + 0.01, 0.25),
      outer_downstream_flow_angle_rad=0.05,
      sample_count=9,
    )
    assert next_field.field is not None
    field = replace(
      next_field.field,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
      upstream_boundary_total_pressure_Pa=(
        min(sample.total_pressure_Pa for sample in incoming),
      ) * len(next_field.field.upstream_boundary_states),
    )
    return MocPostShockChainCellSolve(
      field=field,
      end_x_m=current.end_x_m + 0.02,
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_chain_cell_from_source_strip_or_termination',
    fake_source_solver,
  )

  provider_calls = []

  def remesh_for_handoff(incoming_handoff):
    assert replacement.request is not None
    return replace(
      replacement,
      request=replace(
        replacement.request,
        incoming_handoff=tuple(incoming_handoff),
      ),
    )

  def remesh_at(current, next_cell_index, incoming_handoff):
    provider_calls.append((current.cell_index, next_cell_index, incoming_handoff))
    # Return a new result object each time, but deliberately retain the same
    # source strip.  The first call is valid only because it records the exact
    # prior handoff; the second call must still be rejected as source reuse.
    return remesh_for_handoff(incoming_handoff)

  planner = plan_caustic_upstream_remesh_shock_chain_sequence(
    reference.field,
    initial,
    remesh_at,
    start_point_at=lambda current, _index, _remesh: (
      current.end_x_m + 0.01,
      0.25,
    ),
    start_x_m=0.5,
    end_x_m=0.6,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.chain.physical_termination is False
  assert planner.handoff_links_verified is True
  assert source_strips == [initial.strip, replacement.strip]
  assert len(provider_calls) == 2
  assert provider_calls[0][2] == planner.chain.cells[1].continuation_boundary
  assert provider_calls[1][2] == planner.chain.cells[2].continuation_boundary
  assert planner.diagnostics['one_step_domain'] is False
  assert planner.diagnostics['upstream_remesh_domain_count'] == 2
  assert planner.diagnostics['upstream_remesh_domain_attempt_count'] == 3
  assert planner.diagnostics['upstream_remesh_reuse_policy'] == (
    'fresh-bounded-caustic-remesh-required-per-cell'
  )
  reused_attempt = planner.diagnostics['upstream_remesh_domain_attempts'][2]
  first_provider_attempt = planner.diagnostics['upstream_remesh_domain_attempts'][1]
  assert first_provider_attempt['incoming_handoff_verified'] is True
  assert reused_attempt['fresh_remesh'] is False
  assert reused_attempt['fresh_strip'] is False
  assert planner.chain.diagnostics['remesh_reuse_policy'] == (
    'reject-reused-caustic-remesh-or-source-strip'
  )

  missing_provenance = plan_caustic_upstream_remesh_shock_chain_sequence(
    reference.field,
    initial,
    lambda _current, _next_cell_index, _incoming_handoff: replacement,
    start_point_at=lambda current, _index, _remesh: (
      current.end_x_m + 0.01,
      0.25,
    ),
    start_x_m=0.5,
    end_x_m=0.6,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )
  assert missing_provenance.chain.cell_count == 2
  assert missing_provenance.chain.termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  handoff_attempt = missing_provenance.diagnostics[
    'upstream_remesh_domain_attempts'
  ][1]
  assert handoff_attempt['role'] == 'remesh-provider-handoff-seam'
  assert handoff_attempt['incoming_handoff_verified'] is False
  assert missing_provenance.chain.diagnostics['remesh_reuse_policy'] == (
    'require-exact-incoming-handoff-provenance'
  )
