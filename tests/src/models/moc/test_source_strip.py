from __future__ import annotations

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocChainTerminationReason,
  MocCausticFamilyRestartStatus,
  MocCausticShockResolutionStatus,
  MocSourceStripCausticStatus,
  MocSourceStripCausticSeedStatus,
  MocSourceStripFrontierStatus,
  MocSourceStripRemeshStatus,
  MocSourceStripContinuationStatus,
  extend_source_characteristic_strip_centerline_reflection,
  build_caustic_shock_seed,
  resolve_caustic_shock_seed,
  restart_characteristic_family_from_caustic,
  solve_underexpanded_expansion_fan,
  solve_reflected_free_boundary,
)
from exhaust_plume.models.nozzle.exit_state import (
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)


def _reflected_boundary_fixture():
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
  assert reflected.converged
  return exit_state, ambient, reflected


def test_centerline_reflection_extension_carries_a_physical_boundary_law() -> None:
  exit_state, ambient, reflected = _reflected_boundary_fixture()

  result = extend_source_characteristic_strip_centerline_reflection(
    reflected.centerline_states,
    reflected.boundary_states,
    exit_state.total_pressure_Pa,
    ambient.pressure_Pa,
    additional_sample_count=1,
  )

  assert result.status in (
    MocSourceStripContinuationStatus.CONVERGED_CENTERLINE_REFLECTION,
    MocSourceStripContinuationStatus.STRIP_FAILURE,
  )
  assert result.continuation_law == (
    'centerline-c-minus-reflection-plus-ambient-pressure'
  )
  assert result.added_sample_count == 1
  assert len(result.plus_source_states) == 10
  assert len(result.minus_source_states) == 10
  assert result.plus_source_states[-1].y_m == 0.0
  assert result.plus_source_states[-1].x_m > result.plus_source_states[-2].x_m
  assert result.minus_source_states[-1].x_m > result.minus_source_states[-2].x_m
  assert result.converged is (
    result.status is MocSourceStripContinuationStatus.CONVERGED_CENTERLINE_REFLECTION
  )
  if result.status is MocSourceStripContinuationStatus.STRIP_FAILURE:
    assert result.frontier is not None
    assert result.frontier.status is MocSourceStripFrontierStatus.CONVERGED
    assert result.frontier.valid_index_ranges == ((0, 2), (8, 9))
    assert result.frontier.first_invalid_index == 3
    assert result.frontier.has_disjoint_ranges is True
    assert result.remesh is not None
    assert result.remesh.status is MocSourceStripRemeshStatus.CAUSTIC_REQUIRES_NEW_FAMILY
    assert result.remesh.failed_boundary_index == 0
    assert result.remesh.patch_cell_count == 2
    assert result.remesh.failed_boundary_indices == (0, 1)
    assert result.remesh.caustic_event is not None
    assert result.remesh.caustic_event.status is MocSourceStripCausticStatus.DETECTED
    assert result.remesh.caustic_event.boundary_interval == 0
    assert result.remesh.caustic_event.caustic_point_m is not None
    assert result.remesh.caustic_event.requires_new_characteristic_family
    assert result.remesh.caustic_event.crossing_edge_indices == ((1, 3),)
    assert len(result.remesh.caustic_event.crossing_edge_states) == 2
    assert all(len(edge) == 2 for edge in result.remesh.caustic_event.crossing_edge_states)
    assert result.remesh.caustic_event.crossing_edge_states[0][0].gamma == 1.4
    seed = build_caustic_shock_seed(
      result.remesh.caustic_event,
      exit_state.total_pressure_Pa,
    )
    assert seed.status is MocSourceStripCausticSeedStatus.CONVERGED_ONE_SIDED_SEED
    assert seed.converged is True
    assert seed.shock_state_solved is False
    assert seed.physical_closure_verified is False
    assert seed.chain_promotion_blocked is True
    assert len(seed.edge_states) == 2
    assert all(edge.family.value == 'C-' for edge in seed.edge_states)
    assert seed.flow_angle_jump_rad is not None and seed.flow_angle_jump_rad > 0.0
    shock_resolution = resolve_caustic_shock_seed(seed)
    assert shock_resolution.status is MocCausticShockResolutionStatus.NO_ENTROPY_ADMISSIBLE_CANDIDATE
    assert shock_resolution.converged is False
    assert shock_resolution.shock_state_solved is False
    assert shock_resolution.physical_closure_verified is False
    assert shock_resolution.chain_promotion_blocked is True
    assert len(shock_resolution.candidates) == 2
    assert shock_resolution.candidates[0].compression is not None
    assert shock_resolution.candidates[0].compression.converged is True
    assert shock_resolution.candidates[0].mach_residual_relative is not None
    assert shock_resolution.candidates[0].mach_residual_relative < -0.06
    assert shock_resolution.candidates[1].flow_turn_rad is not None
    assert shock_resolution.candidates[1].flow_turn_rad < 0.0
    assert result.remesh.chain_termination_available is True
    termination = result.remesh.as_chain_termination_decision()
    assert termination.physical_termination is False
    assert termination.reason is MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    assert termination.diagnostics['termination_model'] == (
      'unresolved-characteristic-caustic'
    )
    restart = restart_characteristic_family_from_caustic(
      seed,
      exit_state.total_pressure_Pa,
      ambient.pressure_Pa,
      anchor_edge_index=0,
      sample_count=6,
    )
    assert restart.status is MocCausticFamilyRestartStatus.CONVERGED_OPEN_BOUNDARY
    assert restart.converged
    assert restart.physical_closure_verified is False
    assert restart.chain_promotion_blocked is True
    assert restart.anchor_edge_index == 0
    assert restart.boundary_sample_count == 6
    assert restart.minimum_forward_progress_m is not None
    assert restart.minimum_forward_progress_m > 0.0
    assert restart.maximum_absolute_pressure_residual is not None
    assert restart.maximum_absolute_pressure_residual <= 1.0e-10
  assert restart.maximum_absolute_tangent_residual is not None
  assert restart.maximum_absolute_tangent_residual <= 1.0e-10
  assert restart.source_strip is not None
  assert restart.source_strip.converged is False
  assert restart.family_band is not None
  assert restart.family_band.converged
  assert restart.family_band.cell_count == 10
  assert restart.family_band.step_count == 5
  assert restart.family_band.topology.connected
  assert restart.family_band.topology.forms_closed_zone
  assert restart.family_band.physical_closure_verified is False
  assert restart.family_band.chain_promotion_blocked is True
  band_termination = restart.family_band.as_chain_termination_decision()
  assert band_termination.physical_termination is False
  assert band_termination.reason is MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
  assert band_termination.diagnostics['termination_model'] == (
    'caustic-family-open-band'
  )
  first_triangle = restart.family_band.cells[0].vertices_xr_m
  centroid = tuple(sum(vertex[index] for vertex in first_triangle) / 3.0 for index in (0, 1))
  assert restart.family_band.state_at(centroid) is not None
  assert restart.family_band.static_pressure_at(centroid) is not None
  assert restart.family_band.state_at((2.0, 0.2)) is None
