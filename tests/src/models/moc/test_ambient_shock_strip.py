from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  CharacteristicFamily,
  MocChainBoundaryKind,
  MocChainPlannerKind,
  MocChainTerminationDecision,
  MocAmbientShockBoundaryMarchStatus,
  MocAmbientShockStripStatus,
  MocFreeBoundaryShockStatus,
  MocTerminalPatchShockCouplingStatus,
  MocTerminalCompressionStatus,
  MocTerminalReflectionPatchStatus,
  assemble_ambient_shock_characteristic_strip,
  assemble_terminal_trace_centerline_patch,
  march_post_shock_ambient_boundary,
  plan_terminal_reflection_patch_chain,
  solve_terminal_compression_candidate,
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch,
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination,
  solve_marched_attached_shock_from_terminal_reflection_patch,
  solve_marched_attached_shock_field,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch


def _shock_reference():
  result = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.1,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 2.0e6,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert result.converged
  assert result.shock_fit is not None
  return result.shock_fit


def _ambient_pressure(shock_fit) -> float:
  sample = shock_fit.boundary_states[0]
  state = sample.state
  return sample.downstream_total_pressure_Pa / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))


def test_shock_sourced_ambient_march_closes_the_boundary_conditions() -> None:
  shock_fit = _shock_reference()
  result = march_post_shock_ambient_boundary(
    shock_fit,
    _ambient_pressure(shock_fit),
  )

  assert result.status is MocAmbientShockBoundaryMarchStatus.CONVERGED
  assert result.converged
  assert len(result.boundary_samples) == 9
  assert result.ambient_boundary.converged
  assert result.maximum_absolute_pressure_residual is not None
  assert result.maximum_absolute_pressure_residual < 1.0e-8
  assert result.maximum_absolute_invariant_residual is not None
  assert result.maximum_absolute_invariant_residual < 1.0e-8


def test_shock_and_ambient_characteristic_strip_keeps_terminal_trace_open() -> None:
  shock_fit = _shock_reference()
  march = march_post_shock_ambient_boundary(
    shock_fit,
    _ambient_pressure(shock_fit),
  )
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    _ambient_pressure(shock_fit),
  )

  assert strip.status is MocAmbientShockStripStatus.CONVERGED_OPEN
  assert strip.converged
  assert strip.node_count == 45
  assert strip.cell_count == 44
  assert strip.topology.connected
  assert strip.topology.forms_closed_zone
  assert strip.topology.nonmanifold_edge_count == 0
  assert strip.physical_closure_verified is False
  assert strip.chain_promotion_blocked is True
  assert len(strip.terminal_trace_points_m) == 10
  assert strip.as_report()['source_families'] == {'shock': 'C+', 'ambient': 'C-'}
  trace_validation = strip.terminal_trace_validation
  assert trace_validation.family is CharacteristicFamily.PLUS
  assert trace_validation.sample_count == 10
  assert trace_validation.maximum_absolute_invariant_residual is not None
  assert trace_validation.maximum_absolute_invariant_residual < 1.0e-8
  assert trace_validation.maximum_geometry_residual_m is not None
  assert not trace_validation.converged


def test_terminal_compression_candidate_is_explicitly_not_a_closed_cell() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )

  result = solve_terminal_compression_candidate(
    strip,
    ambient_pressure_Pa=ambient_pressure,
    # The diagonal terminal trace is a coarse polyline approximation. Keep
    # the strict validator above, and make this research tolerance explicit.
    trace_position_tolerance_m=1.0e-3,
  )

  assert result.status is MocTerminalCompressionStatus.CONVERGED_LOCAL_COMPRESSION_CANDIDATE
  assert result.converged
  assert result.compression is not None
  assert result.compression.shock_start_m == strip.terminal_trace_points_m[-1]
  assert result.compression.shock_end_m is not None
  assert result.compression.shock_end_m[1] == pytest.approx(0.0, abs=1.0e-12)
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True
  assert result.accepted_for_chain is False


def test_terminal_compression_candidate_keeps_strict_trace_failure_visible() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )

  result = solve_terminal_compression_candidate(
    strip,
    ambient_pressure_Pa=ambient_pressure,
  )

  assert result.status is MocTerminalCompressionStatus.TRACE_FAILURE
  assert result.compression is None
  assert result.terminal_trace_validation is not None
  assert result.terminal_trace_validation.converged is False
  assert result.chain_promotion_blocked is True


def test_terminal_trace_centerline_patch_emits_a_typed_open_c_minus_front() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )

  result = assemble_terminal_trace_centerline_patch(
    strip,
    trace_position_tolerance_m=1.0e-3,
  )

  assert result.status is MocTerminalReflectionPatchStatus.CONVERGED_OPEN
  assert result.converged
  assert result.node_count == 55
  assert result.cell_count == 45
  assert result.topology.connected
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.combined_topology.connected
  assert result.combined_topology.forms_closed_zone
  assert result.combined_topology.nonmanifold_edge_count == 0
  assert len(result.axis_points_m) == 10
  assert result.axis_points_m[-1][1] == pytest.approx(0.0, abs=1.0e-12)
  assert len(result.outgoing_trace_points_m) == 10
  assert result.outgoing_trace_validation is not None
  assert result.outgoing_trace_validation.family is CharacteristicFamily.MINUS
  assert result.outgoing_trace_validation.converged
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True


def test_terminal_reflection_patch_is_domain_bounded_and_reaches_typed_mixed_regime_gate() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )
  patch = assemble_terminal_trace_centerline_patch(
    strip,
    trace_position_tolerance_m=1.0e-3,
  )
  assert patch.converged
  start = patch.outgoing_trace_points_m[0]
  assert patch.state_at(start, position_tolerance_m=1.0e-3) is not None
  assert patch.static_pressure_at(start, position_tolerance_m=1.0e-3) is not None
  assert patch.state_at((patch.axis_points_m[-1][0] + 0.5, 0.1)) is None

  result = solve_marched_attached_shock_from_terminal_reflection_patch(
    patch,
    start,
    downstream_flow_angle_rad=0.0,
    sample_count=len(patch.outgoing_trace_points_m),
    position_tolerance_m=1.0e-3,
  )

  assert result.shock.status is MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
  assert result.shock.normal_shock_terminal is not None
  assert result.shock.normal_shock_terminal.converged
  assert result.coupling.status is MocTerminalPatchShockCouplingStatus.CONVERGED
  assert result.coupling.sampled_count == result.shock.sample_count
  assert result.upstream_coupling_verified is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True
  assert result.physical_terminal_verified is True
  decision = result.as_physical_termination_decision()
  assert decision.physical_termination is True
  assert decision.message.startswith('supersonic terminal-patch march')
  assert decision.as_report()['diagnostics']['termination_model'] == 'normal-shock-terminal'


def test_terminal_reflection_patch_retains_a_strong_subsonic_branch_seam() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  strip = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )
  patch = assemble_terminal_trace_centerline_patch(
    strip,
    trace_position_tolerance_m=1.0e-3,
  )
  assert patch.converged

  result = solve_marched_attached_shock_from_terminal_reflection_patch(
    patch,
    patch.outgoing_trace_points_m[0],
    downstream_flow_angle_rad=0.0,
    branch=ShockBranch.STRONG,
    sample_count=len(patch.outgoing_trace_points_m),
    position_tolerance_m=1.0e-3,
  )

  assert result.shock_branch is ShockBranch.STRONG
  assert result.shock.status is MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
  assert result.shock.subsonic_boundary_verified
  assert result.shock.subsonic_shock_boundary is not None
  assert result.shock.subsonic_shock_boundary.branch is ShockBranch.STRONG
  assert result.physical_terminal_verified is False
  assert result.chain_promotion_blocked is True
  assert result.as_report()['shock_branch'] == 'strong'


def _terminal_patch_chain_fixture():
  shock = solve_marched_attached_shock_field(
    lambda point: CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=-0.1,
      mach=2.0,
      gamma=1.4,
    ),
    lambda _point: 2.0e6,
    (0.5, 0.5),
    downstream_flow_angle_at=lambda _index, point: 0.05 * point[1] / 0.5,
    sample_count=9,
  )
  assert shock.converged
  assert shock.field is not None
  assert shock.shock_fit is not None
  ambient_pressure = _ambient_pressure(shock.shock_fit)
  march = march_post_shock_ambient_boundary(shock.shock_fit, ambient_pressure)
  strip = assemble_ambient_shock_characteristic_strip(
    shock.shock_fit,
    march.boundary_samples,
    ambient_pressure,
  )
  patch = assemble_terminal_trace_centerline_patch(
    strip,
    trace_position_tolerance_m=1.0e-3,
  )
  assert patch.converged
  current = shock.field.as_coupled_chain_cell(start_x_m=0.5, end_x_m=1.0)
  current = replace(
    current,
    continuation_boundary=patch.outgoing_trace_samples,
    continuation_boundary_kind=MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE,
  )
  return current, patch


def test_terminal_patch_chain_adapter_consumes_exact_handoff_and_stops_at_typed_terminal() -> None:
  current, patch = _terminal_patch_chain_fixture()
  handoff = current.continuation_boundary

  result = solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination(
    current,
    2,
    handoff,
    patch,
    start_point_m=patch.outgoing_trace_points_m[0],
    end_x_m=2.0,
    downstream_flow_angle_rad=0.0,
    sample_count=len(handoff),
    position_tolerance_m=1.0e-3,
  )

  assert isinstance(result, MocChainTerminationDecision)
  assert result.physical_termination
  assert result.diagnostics['termination_model'] == 'normal-shock-terminal'


def test_terminal_patch_planner_audits_one_step_handoff_and_typed_stop() -> None:
  current, patch = _terminal_patch_chain_fixture()

  result = plan_terminal_reflection_patch_chain(
    current,
    patch,
    start_point_m=patch.outgoing_trace_points_m[0],
    end_x_m=2.0,
    downstream_flow_angle_rad=0.0,
    sample_count=len(current.continuation_boundary),
    position_tolerance_m=1.0e-3,
  )

  assert result.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert result.production_claim_allowed is False
  assert result.chain.physical_termination
  assert result.chain.cell_count == 1
  assert len(result.steps) == 1
  assert result.steps[0].boundary_kind is MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE
  assert result.steps[0].incoming_handoff_sample_count == len(
    current.continuation_boundary
  )
  assert result.as_report()['planning_only'] is True


def test_terminal_patch_chain_adapter_rejects_mismatched_handoff_before_solving() -> None:
  current, patch = _terminal_patch_chain_fixture()
  changed = replace(
    current.continuation_boundary[0].state,
    theta_rad=current.continuation_boundary[0].state.theta_rad + 0.01,
  )
  bad_handoff = (
    replace(current.continuation_boundary[0], state=changed),
    *current.continuation_boundary[1:],
  )

  with pytest.raises(ValueError, match='exactly match the current cell boundary'):
    solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch(
      current,
      2,
      bad_handoff,
      patch,
      start_point_m=patch.outgoing_trace_points_m[0],
      end_x_m=2.0,
      downstream_flow_angle_rad=0.0,
      sample_count=len(current.continuation_boundary),
      position_tolerance_m=1.0e-3,
    )


def test_ambient_strip_rejects_a_boundary_trace_with_wrong_family_geometry() -> None:
  shock_fit = _shock_reference()
  ambient_pressure = _ambient_pressure(shock_fit)
  march = march_post_shock_ambient_boundary(shock_fit, ambient_pressure)
  assert march.converged
  samples = list(march.boundary_samples)
  samples[3] = replace(
    samples[3],
    state=replace(samples[3].state, theta_rad=samples[3].state.theta_rad + 0.02),
  )

  result = assemble_ambient_shock_characteristic_strip(
    shock_fit,
    tuple(samples),
    ambient_pressure,
  )

  assert result.status is not MocAmbientShockStripStatus.CONVERGED_OPEN
  assert not result.converged
  assert 'ambient boundary' in result.message


def test_ambient_boundary_march_requires_a_compatible_attachment_state() -> None:
  shock_fit = _shock_reference()
  first = shock_fit.boundary_states[0].state
  result = march_post_shock_ambient_boundary(
    shock_fit,
    _ambient_pressure(shock_fit),
    seed_boundary_state=replace(first, theta_rad=first.theta_rad + 0.01),
  )

  assert result.status is MocAmbientShockBoundaryMarchStatus.SEED_FAILURE
  assert not result.converged
  assert 'attachment state' in result.message
