from __future__ import annotations

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocSourceStripCausticStatus,
  MocSourceStripFrontierStatus,
  MocSourceStripRemeshStatus,
  MocSourceStripContinuationStatus,
  extend_source_characteristic_strip_centerline_reflection,
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
