from __future__ import annotations

from dataclasses import replace
from math import cos, sin

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocAmbientPhysicalFieldResult,
  MocAmbientPhysicalFieldStatus,
  MocBoundedUpstreamFieldSource,
  MocChainBoundarySample,
  MocChainContinuationPolicy,
  MocChainTerminationReason,
  MocPostShockChainCellSolve,
  MocReflectedDomainRemeshRequest,
  MocReflectedDomainRemeshStatus,
  MocSolverGeneratedAmbientClosedPostShockChainReference,
  MocSourceStripContinuationStatus,
  MocTerminalReflectionPatchAmbientClosureChainReference,
  assemble_terminal_trace_centerline_patch,
  inverse_prandtl_meyer_angle_rad,
  plan_reflected_domain_remesh_ambient_closed_chain,
  plan_reflected_domain_remesh_shock_chain,
  plan_reflected_domain_remesh_shock_chain_sequence,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_reflected_domain_remesh,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.validation.moc_measurements import (
  MocReflectedDomainRemeshMeasurementStatus,
  measure_moc_reflected_domain_remesh,
)


def _canonical_field():
  upstream = CharacteristicState(
    x_m=0.5,
    y_m=0.5,
    theta_rad=-0.2,
    mach=2.0,
    gamma=1.4,
  )
  shock = solve_marched_attached_shock_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.shock_fit is not None
  first = shock.shock_fit.boundary_states[0]
  ambient_pressure = first.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (first.state.gamma - 1.0) * first.state.mach**2
  ) ** (first.state.gamma / (first.state.gamma - 1.0))
  result = solve_marched_attached_shock_with_ambient_centerline_physical_field(
    lambda point: replace(upstream, x_m=point[0], y_m=point[1]),
    lambda _point: 100000.0,
    (0.5, 0.5),
    ambient_pressure,
    0.02,
    0.12,
    sample_count=9,
  )
  assert result.field is not None
  assert result.field.physical_closure_verified
  return result.field


def _patch():
  field = _canonical_field()
  patch = assemble_terminal_trace_centerline_patch(
    field.as_open_shock_ambient_strip()
  )
  assert patch.converged
  return field, patch


def _request(*, declared_polarity=None, incoming_handoff=()):
  field, patch = _patch()
  anchor = patch.outgoing_trace_states[-1]
  total_pressure = patch.outgoing_trace_total_pressure_Pa[-1]
  centerline = []
  outer = []
  for index in range(6):
    k_plus = anchor.k_plus - 0.002 * index
    inversion = inverse_prandtl_meyer_angle_rad(-k_plus, anchor.gamma)
    assert inversion.value is not None
    axis_x = anchor.x_m + 0.015 * index
    axis_state = CharacteristicState(
      x_m=axis_x,
      y_m=0.0,
      theta_rad=0.0,
      mach=inversion.value,
      gamma=anchor.gamma,
    )
    theta = 0.06 - 0.004 * index
    outer_inversion = inverse_prandtl_meyer_angle_rad(
      theta - k_plus,
      anchor.gamma,
    )
    assert outer_inversion.value is not None
    outer_probe = CharacteristicState(
      x_m=axis_x,
      y_m=0.0,
      theta_rad=theta,
      mach=outer_inversion.value,
      gamma=anchor.gamma,
    )
    characteristic_angle = 0.5 * (
      axis_state.mu_rad
      + outer_probe.theta_rad
      + outer_probe.mu_rad
    )
    ordinate = 0.10 + 0.012 * index
    outer.append(
      CharacteristicState(
        x_m=axis_x + ordinate * cos(characteristic_angle) / sin(
          characteristic_angle
        ),
        y_m=ordinate,
        theta_rad=theta,
        mach=outer_inversion.value,
        gamma=anchor.gamma,
      )
    )
    centerline.append(axis_state)
  request = MocReflectedDomainRemeshRequest(
    reflection_patch=patch,
    centerline_source_states=tuple(centerline),
    outer_source_states=tuple(outer),
    total_pressure_Pa=total_pressure,
    incoming_handoff=tuple(incoming_handoff),
    declared_polarity=declared_polarity,
  )
  return field, patch, request


def _handoff(field):
  return tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )


def _reference_seed_field():
  result = solve_uniform_attached_shock_field(
    CharacteristicState(0.5, 0.5, -0.2, 2.0, 1.4),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert result.field is not None
  return result.field


def test_reflected_domain_remesh_uses_a_new_outer_curve_after_the_single_c_minus_front():
  _field, patch, request = _request()

  result = solve_reflected_domain_remesh(request)

  assert result.status is MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD
  assert result.converged
  assert result.state_sampling_available
  assert result.incoming_trace_validation is not None
  assert result.incoming_trace_validation.converged
  assert result.incoming_trace_polarity is not None
  assert result.incoming_trace_polarity.converged
  assert result.reflection_seam_verified
  assert result.centerline_source_verified
  assert result.outer_source_verified
  assert result.source_field_verified
  assert result.source_strip is not None
  assert result.source_strip.topology.forms_closed_zone
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  continuation = result.as_source_continuation()
  assert continuation.status is MocSourceStripContinuationStatus.CONVERGED_EXTENDED
  assert continuation.strip is result.source_strip
  report = result.as_report()
  assert report['request']['incoming_trace_reused_as_outer_source'] is False
  assert report['request']['outer_source_is_new_curve'] is True
  assert report['request']['incoming_trace_family'] == 'C-'
  assert report['request']['centerline_source_family'] == 'C+'
  assert report['chain_termination_decision']['reason'] == (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
  )
  assert patch.outgoing_trace_states[-1].y_m == pytest.approx(0.0)


def test_reflected_domain_remesh_rejects_reusing_the_single_c_minus_front_as_a_curve():
  _field, patch, request = _request()
  reused = patch.outgoing_trace_states[:6]
  changed = replace(
    request,
    outer_source_states=reused,
    centerline_source_states=request.centerline_source_states,
  )

  result = solve_reflected_domain_remesh(changed)

  assert result.status is MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE
  assert result.state_sampling_available is False
  assert 'single C- front cannot be reused' in result.message
  assert result.as_chain_termination_decision().reason is (
    MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
  )


def test_reflected_domain_remesh_measurement_rechecks_raw_bounded_field_data():
  _field, _patch, request = _request()
  remesh = solve_reflected_domain_remesh(request)
  assert remesh.converged

  tampered = replace(
    remesh,
    reflection_seam_verified=False,
    centerline_source_verified=False,
    outer_source_verified=False,
    source_field_verified=False,
  )
  measurement = measure_moc_reflected_domain_remesh(tampered)

  assert measurement.status is MocReflectedDomainRemeshMeasurementStatus.CONVERGED
  assert measurement.bounded_remesh_verified
  assert measurement.incoming_trace_verified
  assert measurement.polarity_verified
  assert measurement.reflection_seam_verified
  assert measurement.centerline_source_verified
  assert measurement.outer_source_verified
  assert measurement.total_pressure_verified
  assert measurement.source_topology_verified
  assert measurement.source_sampling_verified
  assert measurement.physical_closure_verified is False
  assert measurement.chain_promotion_blocked
  assert measurement.production_claim_allowed is False


def test_reflected_domain_remesh_measurement_preserves_single_front_rejection():
  _field, patch, request = _request()
  reused = solve_reflected_domain_remesh(
    replace(
      request,
      outer_source_states=patch.outgoing_trace_states[:6],
    )
  )

  measurement = measure_moc_reflected_domain_remesh(reused)

  assert measurement.status is MocReflectedDomainRemeshMeasurementStatus.SOURCE_FAILURE
  assert measurement.converged is False
  assert measurement.outer_source_verified is False
  assert measurement.bounded_remesh_verified is False


def test_reflected_domain_remesh_rejects_a_wrong_reflection_anchor():
  _field, _patch, request = _request()
  changed_centerline = (
    replace(request.centerline_source_states[0], x_m=1.0),
    *request.centerline_source_states[1:],
  )

  result = solve_reflected_domain_remesh(
    replace(request, centerline_source_states=changed_centerline)
  )

  assert result.status is MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE
  assert result.reflection_seam_verified is False
  assert result.chain_promotion_blocked


def test_reflected_domain_remesh_records_observed_polarity_without_promoting_it():
  _field, _patch, first = _request()
  observed = solve_reflected_domain_remesh(first).incoming_trace_polarity
  assert observed is not None
  _field, _patch, request = _request(declared_polarity=observed.status)

  result = solve_reflected_domain_remesh(request)

  assert result.converged
  assert result.incoming_trace_polarity is not None
  assert result.incoming_trace_polarity.status is observed.status
  assert result.as_report()['request']['declared_polarity'] == observed.status.value


def test_reflected_domain_remesh_exposes_a_bounded_physical_solver_source():
  _field, _patch, request = _request()
  remesh = solve_reflected_domain_remesh(request)

  source = MocBoundedUpstreamFieldSource.from_reflected_domain_remesh(remesh)

  assert source.model == 'bounded-reflected-domain-cauchy-remesh'
  assert source.preferred_start_point_m == pytest.approx(
    (
      request.outer_source_states[0].x_m,
      request.outer_source_states[0].y_m,
    )
  )
  assert source.domain_x_extent_m is not None
  assert source.domain_y_extent_m is not None
  start = source.preferred_start_point_m
  assert start is not None
  state = source.state_at(start)
  pressure = source.static_pressure_at(start)
  assert state is not None
  assert state.x_m == pytest.approx(start[0])
  assert state.y_m == pytest.approx(start[1])
  assert pressure is not None
  assert pressure > 0.0
  assert source.state_at(
    (
      source.domain_x_extent_m[1] + 0.1,
      source.domain_y_extent_m[1] + 0.1,
    )
  ) is None
  report = source.as_report()
  assert report['extrapolation_allowed'] is False
  assert report['upstream_coupling_verified'] is False


def test_reflected_domain_ambient_closed_planner_connects_fresh_remeshes_to_physical_solver(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request(incoming_handoff=_handoff(seed))
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  assert initial_remesh.converged
  solver_calls = []
  remesh_calls = []

  def fake_physical_solver(
    _state_at,
    _pressure_at,
    start_point_m,
    ambient_pressure_Pa,
    _lower,
    _upper,
    **kwargs,
  ):
    incoming = tuple(kwargs['incoming_handoff'])
    solver_calls.append((start_point_m, ambient_pressure_Pa, incoming))
    field = replace(
      seed,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
    )
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      axis_closure_shoot=None,
      field=field,
      message='manufactured accepted physical-field solver result',
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )

  def remesh_at(current_field, current, next_cell_index, incoming_handoff):
    remesh_calls.append(
      (current_field, current.cell_index, next_cell_index, incoming_handoff)
    )
    _field, _patch, request = _request(incoming_handoff=incoming_handoff)
    offset = 0.001 * len(remesh_calls)
    request = replace(
      request,
      outer_source_states=tuple(
        replace(state, x_m=state.x_m + offset)
        for state in request.outer_source_states
      ),
    )
    return solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    remesh_at,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=3,
      cell_axial_length_m=0.4,
      ambient_pressure_Pa=101325.0,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert planner.resolved
  assert planner.chain.cell_count == 3
  assert planner.chain.termination_reason is (
    MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  assert planner.handoff_links_verified is True
  assert planner.production_claim_allowed is False
  assert len(solver_calls) == 2
  assert len(remesh_calls) == 1
  assert remesh_calls[0][0] is not seed
  assert planner.diagnostics['reflected_domain_remesh_attempt_count'] == 2
  assert all(
    attempt['fresh_remesh'] is True
    and attempt['fresh_source_field'] is True
    and attempt['incoming_handoff_verified'] is True
    for attempt in planner.diagnostics['reflected_domain_remesh_attempts']
  )
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['free_boundary_verified'] is False
  assert planner.diagnostics['physical_chain_promotion_allowed'] is False
  assert planner.diagnostics['external_validation_pending'] is True


def test_reflected_domain_ambient_closed_planner_rejects_mismatched_initial_handoff(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request()
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  solver_called = False

  def fake_physical_solver(*_args, **_kwargs):
    nonlocal solver_called
    solver_called = True
    raise AssertionError('physical solver must not run after a handoff failure')

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )
  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    lambda *_args: initial_remesh,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=2,
      cell_axial_length_m=0.4,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert solver_called is False
  assert planner.chain.cell_count == 1
  assert planner.chain.termination_reason is MocChainTerminationReason.STATE_NOT_CARRIED
  assert planner.steps[0].result_termination_reason is (
    MocChainTerminationReason.STATE_NOT_CARRIED
  )
  attempt = planner.diagnostics['reflected_domain_remesh_attempts'][0]
  assert attempt['role'] == 'reflected-domain-remesh-handoff-seam'
  assert attempt['incoming_handoff_verified'] is False


def test_reflected_domain_ambient_closed_planner_rejects_reused_remesh(
  monkeypatch: pytest.MonkeyPatch,
):
  seed = _canonical_field()
  _field, _patch, initial_request = _request(incoming_handoff=_handoff(seed))
  initial_remesh = solve_reflected_domain_remesh(initial_request)
  assert initial_remesh.converged
  solver_calls = 0

  def fake_physical_solver(*_args, **kwargs):
    nonlocal solver_calls
    solver_calls += 1
    incoming = tuple(kwargs['incoming_handoff'])
    field = replace(
      seed,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
    )
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
      axis_closure_shoot=None,
      field=field,
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_with_ambient_centerline_physical_field',
    fake_physical_solver,
  )
  planner = plan_reflected_domain_remesh_ambient_closed_chain(
    seed,
    initial_remesh,
    lambda *_args: initial_remesh,
    start_x_m=0.0,
    end_x_m=0.1,
    reference=MocSolverGeneratedAmbientClosedPostShockChainReference(
      total_cell_count=3,
      cell_axial_length_m=0.4,
      sample_count=9,
    ),
    policy=MocChainContinuationPolicy(max_cells=4, require_state_carry=True),
  )

  assert solver_calls == 1
  assert planner.chain.cell_count == 2
  assert planner.chain.termination_reason is MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  assert planner.steps[-1].result_termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  attempt = planner.diagnostics['reflected_domain_remesh_attempts'][-1]
  assert attempt['role'] == 'reflected-domain-remesh-freshness-gate'
  assert attempt['fresh_remesh'] is False
  assert attempt['fresh_source_field'] is False


def test_reflected_domain_one_step_planner_keeps_the_remesh_below_physical_claims():
  _field, _patch, request = _request()
  field = _reference_seed_field()
  remesh = solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_shock_chain(
    field,
    remesh,
    start_point_m=request.outer_source_states[0].x_m,
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=2, require_state_carry=True),
  )

  assert planner.production_claim_allowed is False
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['canonical_reflected_domain_closed'] is False
  assert planner.diagnostics['reflected_domain_remesh']['status'] == (
    MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD.value
  )
  assert planner.chain.physical_termination is False


def test_terminal_reflection_reference_report_keeps_chain_promotion_blocked():
  report = MocTerminalReflectionPatchAmbientClosureChainReference().as_report()

  assert report['planning_only'] is True
  assert report['production_claim_allowed'] is False
  assert report['physical_chain_promotion_allowed'] is False


def test_reflected_domain_sequence_requires_exact_handoff_for_each_new_remesh(
  monkeypatch: pytest.MonkeyPatch,
):
  _field, _patch, first_request = _request(incoming_handoff=_handoff(_canonical_field()))
  field = _reference_seed_field()
  first = solve_reflected_domain_remesh(first_request)
  assert first.converged
  calls = []

  def fake_source_solver(
    current,
    _next_cell_index,
    incoming_handoff,
    _source_strip,
    **kwargs,
  ):
    del kwargs
    next_field_result = solve_uniform_attached_shock_field(
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
    assert next_field_result.field is not None
    next_field = next_field_result.field
    incoming = tuple(incoming_handoff)
    field_with_handoff = replace(
      next_field,
      incoming_handoff_states=tuple(sample.state for sample in incoming),
      incoming_handoff_total_pressure_Pa=tuple(
        sample.total_pressure_Pa for sample in incoming
      ),
      upstream_boundary_total_pressure_Pa=(
        min(sample.total_pressure_Pa for sample in incoming),
      ) * len(next_field.upstream_boundary_states),
    )
    return MocPostShockChainCellSolve(
      field=field_with_handoff,
      end_x_m=current.end_x_m + 0.2,
    )

  monkeypatch.setattr(
    'exhaust_plume.models.moc.planner.solve_marched_attached_shock_chain_cell_from_source_strip_or_termination',
    fake_source_solver,
  )

  def remesh_at(current, next_cell_index, incoming_handoff):
    calls.append((current.cell_index, next_cell_index, incoming_handoff))
    _field, _patch, request = _request(incoming_handoff=incoming_handoff)
    return solve_reflected_domain_remesh(request)

  planner = plan_reflected_domain_remesh_shock_chain_sequence(
    field,
    first,
    remesh_at,
    start_point_at=lambda _current, _index, candidate: (
      candidate.request.outer_source_states[0].x_m,
      candidate.request.outer_source_states[0].y_m,
    ),
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )

  assert calls
  assert planner.production_claim_allowed is False
  assert planner.diagnostics['reflected_domain_remesh_attempt_count'] >= 2
  assert planner.diagnostics['reflected_domain_reuse_policy'] == (
    'fresh-reflected-domain-remesh-required-per-cell'
  )
  assert planner.chain.physical_termination is False

  missing_provenance = plan_reflected_domain_remesh_shock_chain_sequence(
    field,
    first,
    lambda _current, _index, _handoff: first,
    start_point_at=lambda _current, _index, candidate: (
      candidate.request.outer_source_states[0].x_m,
      candidate.request.outer_source_states[0].y_m,
    ),
    start_x_m=2.0,
    end_x_m=2.4,
    downstream_flow_angle_rad=0.05,
    sample_count=9,
    policy=MocChainContinuationPolicy(max_cells=3, require_state_carry=True),
  )
  assert missing_provenance.chain.termination_reason is (
    MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
  )
  assert missing_provenance.diagnostics['reflected_domain_remesh_attempts'][0][
    'role'
  ] == 'initial-reflected-domain-remesh'
