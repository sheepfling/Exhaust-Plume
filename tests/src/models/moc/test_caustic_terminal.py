from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocCausticSimpleWaveTerminalStatus,
  MocCausticSimpleWaveTraceStatus,
  MocChainPlannerKind,
  MocChainTerminationReason,
  build_caustic_shock_seed,
  build_caustic_simple_wave_trace,
  extend_source_characteristic_strip_centerline_reflection,
  plan_caustic_simple_wave_terminal_chain,
  prepare_caustic_shock_remesh,
  solve_caustic_simple_wave_terminal_remesh,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
  validate_moc_mesh,
)
from exhaust_plume.models.moc.compression import solve_normal_shock_terminal
from exhaust_plume.models.moc.post_shock import fit_attached_shock_boundary
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
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
  assert seed.edge_states[1].state is not None
  prepared = prepare_caustic_shock_remesh(
    seed,
    CharacteristicFamily.PLUS,
    seed.edge_states[1].state.k_plus,
    upstream_edge_index=0,
  )
  assert prepared.request is not None

  reference = solve_uniform_attached_shock_field(
    CharacteristicState(
      0.5,
      0.5,
      -0.2,
      2.0,
      1.4,
    ),
    100000.0,
    (0.5, 0.5),
    outer_downstream_flow_angle_rad=0.05,
    sample_count=9,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(
    start_x_m=0.2,
    end_x_m=0.5,
  )
  return prepared.request, current


def test_solver_owned_simple_wave_reaches_open_typed_terminal() -> None:
  request, current = _fixture()
  trace = build_caustic_simple_wave_trace(request)

  assert trace.status is MocCausticSimpleWaveTraceStatus.CONVERGED_TRACE
  assert trace.converged
  assert trace.event_point_m == request.event_point_m
  assert trace.event_state == request.upstream_state
  assert trace.static_pressure_at(request.event_point_m) == pytest.approx(
    request.upstream_static_pressure_Pa,
  )
  assert trace.state_at((request.event_point_m[0] - 1.0e-3, request.event_point_m[1])) is None
  assert trace.state_at((request.event_point_m[0] + 1.0e-3, -1.0e-4)) is None

  interior = trace.state_at(
    (request.event_point_m[0] + 0.01, 0.5 * request.event_point_m[1]),
  )
  assert interior is not None
  assert interior.k_minus == pytest.approx(trace.invariant_value)

  result = solve_caustic_simple_wave_terminal_remesh(
    request,
    current.continuation_boundary,
  )

  assert result.status is MocCausticSimpleWaveTerminalStatus.CONVERGED_OPEN_TERMINAL_FIELD
  assert result.converged
  assert result.event_seam_verified
  assert result.local_bridge_state_verified
  assert result.upstream_coupling_verified
  assert result.shock_prefix_verified
  assert result.downstream_zone_verified
  assert result.terminal_verified
  assert result.physical_terminal_verified
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.shock is not None
  assert result.shock.status.value == 'subsonic_terminal_required'
  assert result.shock_fit is not None
  assert result.shock_fit.converged
  assert result.continuation is not None
  assert result.continuation.converged
  assert result.first_layer is not None
  assert result.first_layer.converged
  assert result.zone is not None
  assert result.zone.converged
  assert result.zone.state_sampling_available
  assert result.zone.topology.forms_closed_zone
  assert result.zone.physical_closure_status == 'open'
  assert result.terminal is not None
  assert result.terminal.subsonic
  assert result.terminal.downstream_mach is not None
  assert result.terminal.downstream_mach < 1.0
  assert result.incoming_handoff_states == tuple(
    sample.state for sample in current.continuation_boundary
  )
  assert result.incoming_handoff_total_pressure_Pa == tuple(
    sample.total_pressure_Pa for sample in current.continuation_boundary
  )

  assert result.shock is not None
  independent_fit = fit_attached_shock_boundary(
    result.shock.upstream_states,
    result.shock.upstream_pressure_Pa,
    result.shock.shock_points_m,
    result.shock.downstream_flow_angles_rad,
    shock_angle_tolerance_rad=0.2,
  )
  assert independent_fit.converged
  assert independent_fit.maximum_shock_angle_residual_rad == pytest.approx(
    result.shock_fit.maximum_shock_angle_residual_rad,
  )
  assert result.zone is not None
  independent_topology = validate_moc_mesh(result.zone.cells)
  assert independent_topology.connected
  assert independent_topology.forms_closed_zone
  assert independent_topology.nonmanifold_edge_count == 0
  assert result.shock_fit is not None
  independent_pressure_ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in independent_fit.boundary_states
  )
  assert all(0.0 < ratio < 1.0 for ratio in independent_pressure_ratios)
  assert min(independent_pressure_ratios) == pytest.approx(
    result.zone.minimum_post_shock_total_pressure_ratio,
  )
  assert result.terminal is not None
  assert result.terminal.upstream_state is not None
  assert result.terminal.upstream_pressure_Pa is not None
  independent_terminal = solve_normal_shock_terminal(
    result.terminal.upstream_state,
    upstream_pressure_Pa=result.terminal.upstream_pressure_Pa,
    shock_point_m=result.terminal.shock_point_m,
  )
  assert independent_terminal.converged
  assert independent_terminal.subsonic
  assert independent_terminal.downstream_mach == pytest.approx(
    result.terminal.downstream_mach,
  )
  report = result.as_report()
  assert report['trace']['model'] == 'solver-owned-constant-invariant-simple-wave-trace'
  assert report['chain_termination_decision']['reason'] == (
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE.value
  )


def test_simple_wave_terminal_planner_records_one_step_without_promotion() -> None:
  request, current = _fixture()

  planner = plan_caustic_simple_wave_terminal_chain(
    current,
    request,
  )

  assert planner.planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH
  assert planner.production_claim_allowed is False
  assert planner.chain.cell_count == 1
  assert planner.chain.resolved
  assert planner.chain.status.value == 'solver-terminated'
  assert planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.chain.physical_termination is False
  assert len(planner.steps) == 1
  assert planner.steps[0].incoming_handoff_sample_count == len(
    current.continuation_boundary
  )
  assert planner.steps[0].result_kind == 'termination-returned'
  assert planner.diagnostics['one_step_domain'] is True
  assert planner.diagnostics['upstream_field_model'] == (
    'solver-owned-constant-invariant-simple-wave-trace'
  )
  assert planner.chain.diagnostics['terminal_verified'] is True
  assert planner.chain.diagnostics['chain_promotion_blocked'] is True
