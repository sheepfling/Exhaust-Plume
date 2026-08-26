from __future__ import annotations

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocCausticFamilyBandShockStatus,
  build_caustic_shock_seed,
  extend_source_characteristic_strip_centerline_reflection,
  restart_characteristic_family_from_caustic,
  solve_marched_attached_shock_from_caustic_family_band,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
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
