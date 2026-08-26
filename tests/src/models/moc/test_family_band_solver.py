from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicState,
  MocCausticFamilyBandShockStatus,
  MocChainTerminationReason,
  build_caustic_shock_seed,
  extend_source_characteristic_strip_centerline_reflection,
  plan_caustic_family_band_chain,
  restart_characteristic_family_from_caustic,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination,
  solve_marched_attached_shock_from_caustic_family_band,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
  solve_uniform_attached_shock_field,
)
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)


def _caustic_band_fixtures():
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
  return exit_state, ambient, seed


def test_caustic_band_grows_open_post_shock_zone_to_typed_terminal() -> None:
  exit_state, ambient, seed = _caustic_band_fixtures()

  for anchor_edge_index in (0, 1):
    restart = restart_characteristic_family_from_caustic(
      seed,
      exit_state.total_pressure_Pa,
      ambient.pressure_Pa,
      anchor_edge_index=anchor_edge_index,
      sample_count=6,
    )
    assert restart.family_band is not None
    band = restart.family_band
    start = (
      0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
      0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
    )
    result = solve_marched_attached_shock_from_caustic_family_band(
      band,
      start,
      sample_count=9,
    )

    assert result.status is MocCausticFamilyBandShockStatus.CONVERGED_OPEN_TERMINAL_FIELD
    assert result.converged
    assert result.physical_terminal_verified
    assert result.physical_closure_verified is False
    assert result.chain_promotion_blocked is True
    assert result.shock is not None
    assert result.shock.status.value == 'subsonic_terminal_required'
    assert result.shock.sample_count == 8
    assert result.shock_fit is not None
    assert result.shock_fit.converged
    assert result.shock_fit.maximum_shock_angle_residual_rad is not None
    assert result.shock_fit.maximum_shock_angle_residual_rad <= 0.1
    assert result.continuation is not None
    assert result.continuation.converged
    assert result.first_layer is not None
    assert result.first_layer.converged
    assert result.zone is not None
    assert result.zone.converged
    assert result.zone.cell_count == 27
    assert result.zone.topology.connected
    assert result.zone.topology.forms_closed_zone
    assert result.zone.topology.nonmanifold_edge_count == 0
    assert result.zone.physical_closure_status == 'open'

    termination = result.as_chain_termination_decision()
    assert termination.physical_termination is False
    assert termination.reason.value == 'open-physical-closure'
    assert termination.diagnostics['termination_model'] == (
      'caustic-band-open-terminal-field'
    )
    mixed_boundary = result.validate_mixed_regime_boundary(())
    assert mixed_boundary.status.value == 'subsonic_field_failure'
    assert mixed_boundary.supersonic_patch_verified
    assert mixed_boundary.physical_closure_verified is False
    assert mixed_boundary.chain_promotion_blocked


def test_caustic_band_shock_solver_does_not_extrapolate_outside_input_domain() -> None:
  exit_state, ambient, seed = _caustic_band_fixtures()
  restart = restart_characteristic_family_from_caustic(
    seed,
    exit_state.total_pressure_Pa,
    ambient.pressure_Pa,
    sample_count=6,
  )
  assert restart.family_band is not None
  result = solve_marched_attached_shock_from_caustic_family_band(
    restart.family_band,
    (2.0, 0.2),
    sample_count=9,
  )
  assert result.status is MocCausticFamilyBandShockStatus.UPSTREAM_DOMAIN_FAILURE
  assert result.converged is False
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked is True


def test_caustic_band_chain_planner_carries_handoff_and_stops_at_open_mixed_regime() -> None:
  exit_state, ambient, seed = _caustic_band_fixtures()
  restart = restart_characteristic_family_from_caustic(
    seed,
    exit_state.total_pressure_Pa,
    ambient.pressure_Pa,
    sample_count=6,
  )
  assert restart.family_band is not None
  band = restart.family_band
  reference = solve_uniform_attached_shock_field(
    CharacteristicState(.5, .5, -.2, 2.0, 1.4),
    100000.0,
    (.5, .5),
    outer_downstream_flow_angle_rad=.05,
    sample_count=17,
  )
  assert reference.field is not None
  current = reference.field.as_coupled_chain_cell(
    start_x_m=.2,
    end_x_m=.8,
  )
  start = (
    0.5 * (band.input_edge_points_m[0][0] + band.input_edge_points_m[1][0]),
    0.5 * (band.input_edge_points_m[0][1] + band.input_edge_points_m[1][1]),
  )

  decision = solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination(
    current,
    2,
    current.continuation_boundary,
    band,
    start_point_m=start,
    end_x_m=1.4,
  )

  assert decision.physical_termination is False
  assert decision.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert decision.diagnostics['upstream_field_model'] == (
    'bounded-caustic-family-band'
  )
  assert decision.diagnostics['incoming_handoff_sample_count'] == len(
    current.continuation_boundary
  )
  assert decision.diagnostics['physical_terminal_verified'] is True

  planner = plan_caustic_family_band_chain(
    current,
    band,
    start_point_m=start,
    end_x_m=1.4,
  )

  assert planner.planner_kind.value == 'upstream-coupled-research'
  assert planner.production_claim_allowed is False
  assert planner.chain.status.value == 'solver-terminated'
  assert planner.chain.termination_reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert planner.chain.cell_count == 1
  assert len(planner.steps) == 1
  assert planner.steps[0].incoming_handoff_sample_count == len(
    current.continuation_boundary
  )
  assert planner.chain.diagnostics['post_shock_zone_converged'] is True

  with pytest.raises(ValueError, match='mixed-regime closure'):
    solve_marched_attached_shock_chain_cell_from_caustic_family_band(
      current,
      2,
      current.continuation_boundary,
      band,
      start_point_m=start,
      end_x_m=1.4,
    )
