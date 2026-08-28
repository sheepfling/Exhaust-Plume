from __future__ import annotations

from dataclasses import replace
from math import cos, sin

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocChainBoundarySample,
  MocChainContinuationPolicy,
  MocChainTerminationReason,
  MocPostShockChainCellSolve,
  MocReflectedDomainRemeshRequest,
  MocReflectedDomainRemeshStatus,
  MocSourceStripContinuationStatus,
  assemble_terminal_trace_centerline_patch,
  inverse_prandtl_meyer_angle_rad,
  plan_reflected_domain_remesh_shock_chain,
  plan_reflected_domain_remesh_shock_chain_sequence,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
  solve_reflected_domain_remesh,
  solve_uniform_attached_shock_field,
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
