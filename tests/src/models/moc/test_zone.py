from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocInterfaceStatus,
  MocReflectedZoneShockCouplingStatus,
  MocSourceStripStatus,
  MocZoneAssemblyStatus,
  assemble_reflected_characteristic_zone,
  assemble_source_characteristic_strip,
  sample_reflected_zone_along_shock_path,
  solve_reflected_free_boundary,
  solve_reflected_boundary_trace_extension,
  solve_underexpanded_expansion_fan,
  validate_fan_reflected_interface,
  validate_moc_mesh,
)
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit


def test_reflected_characteristic_zone_assembles_one_open_topological_perimeter() -> None:
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
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  reflected_boundary = solve_reflected_free_boundary(fan, exit_state, ambient)

  result = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
  )

  assert result.status is MocZoneAssemblyStatus.CONVERGED_OPEN
  assert result.converged
  assert result.characteristic_count == 8
  assert result.node_count == 45
  assert result.cell_count == 44
  assert result.topology.forms_closed_zone
  assert result.topology.boundary_edge_count == 26
  assert result.topology.nonmanifold_edge_count == 0
  assert result.coverage_area_m2 is not None
  assert result.coverage_area_residual_m2 == pytest.approx(0.0, abs=1.0e-12)
  assert result.physical_closure_status == 'open'
  assert result.physical_closure_verified is False
  assert result.chain_promotion_blocked
  assert result.shock_closure_status == 'not_assembled'
  assert result.total_pressure_Pa == pytest.approx(exit_state.total_pressure_Pa)
  assert result.state_sampling_available
  assert result.domain_x_extent_m is not None
  assert result.domain_x_extent_m[1] > result.domain_x_extent_m[0]
  assert result.domain_y_extent_m is not None
  assert result.domain_y_extent_m[0] == pytest.approx(0.0, abs=1.0e-12)
  assert result.domain_y_extent_m[1] > result.domain_y_extent_m[0]
  report = result.as_report()
  assert report['physical_closure_verified'] is False
  assert report['chain_promotion_blocked'] is True
  assert report['claim_fidelity_ceiling'] == 'open-planar-moc'
  assert report['state_sampling_available'] is True
  assert report['state_sampling_model'] == 'bounded-cell-barycentric-no-extrapolation'
  assert report['domain_x_extent_m'] == pytest.approx(result.domain_x_extent_m)
  assert report['domain_y_extent_m'] == pytest.approx(result.domain_y_extent_m)
  assert report['cell_kind_counts'] == {
    'axis-strip': 8,
    'free-boundary-strip': 8,
    'interior': 28,
  }
  assert all(node.point_result.converged for node in result.nodes)
  assert all(cell.geometry_status.value == 'valid' for cell in result.cells)
  assert sum(cell.cell_kind == 'axis-strip' for cell in result.cells) == 8
  assert sum(cell.cell_kind == 'interior' for cell in result.cells) == 28
  assert sum(cell.cell_kind == 'free-boundary-strip' for cell in result.cells) == 8


def test_reflected_zone_sampler_is_pressure_aware_and_domain_bounded() -> None:
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
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  reflected_boundary = solve_reflected_free_boundary(fan, exit_state, ambient)
  zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
  )

  cell = zone.cells[0]
  sample_point = (
    sum(point[0] for point in cell.vertices_xr_m) / len(cell.vertices_xr_m),
    sum(point[1] for point in cell.vertices_xr_m) / len(cell.vertices_xr_m),
  )
  state = zone.state_at(sample_point)

  assert state is not None
  assert state.x_m == pytest.approx(sample_point[0])
  assert state.y_m == pytest.approx(sample_point[1])
  assert state.mach > 1.0
  assert zone.static_pressure_at(sample_point) is not None
  assert zone.static_pressure_at(sample_point) > 0.0
  assert zone.state_at((1.0, 0.5)) is None
  assert zone.static_pressure_at((1.0, 0.5)) is None


def test_reflected_zone_shock_coupling_reports_first_missing_strip_sample() -> None:
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
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  reflected_boundary = solve_reflected_free_boundary(fan, exit_state, ambient)
  zone = assemble_reflected_characteristic_zone(
    fan,
    reflected_boundary,
    total_pressure_Pa=exit_state.total_pressure_Pa,
  )
  start = reflected_boundary.boundary_points_m[-1]
  pressure = zone.static_pressure_at(start)
  assert pressure is not None
  trace_extension = solve_reflected_boundary_trace_extension(
    reflected_boundary,
    pressure,
    sample_count=9,
  )

  coupling = sample_reflected_zone_along_shock_path(
    zone,
    trace_extension.shock_points_m,
  )

  assert coupling.status is MocReflectedZoneShockCouplingStatus.OUTSIDE_DOMAIN
  assert coupling.sampled_count == 1
  assert coupling.first_missing_sample_index == 1
  assert coupling.last_valid_point_m == pytest.approx(start)


def test_source_characteristic_strip_reuses_reflected_compatibility_grid() -> None:
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
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  reflected_boundary = solve_reflected_free_boundary(fan, exit_state, ambient)

  result = assemble_source_characteristic_strip(
    reflected_boundary.centerline_states,
    reflected_boundary.boundary_states,
    exit_state.total_pressure_Pa,
  )

  assert result.status is MocSourceStripStatus.CONVERGED_OPEN
  assert result.node_count == 45
  assert result.cell_count == 44
  assert result.topology.forms_closed_zone
  assert result.topology.nonmanifold_edge_count == 0
  assert result.maximum_geometry_residual_m is not None
  assert result.maximum_geometry_residual_m < 1.0e-10
  assert result.maximum_absolute_invariant_residual is not None
  assert result.maximum_absolute_invariant_residual < 1.0e-10
  sample = result.state_at((0.6, 0.1))
  assert sample is not None
  assert sample.mach > 1.0
  assert result.static_pressure_at((1.0, 0.5)) is None


def test_fan_reflected_interface_reuses_compatibility_grid_and_connects_cells() -> None:
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
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)
  reflected_boundary = solve_reflected_free_boundary(fan, exit_state, ambient)

  result = validate_fan_reflected_interface(fan, reflected_boundary)
  zone = assemble_reflected_characteristic_zone(fan, reflected_boundary)
  topology = validate_moc_mesh((*fan.cells, *zone.cells))

  assert result.status is MocInterfaceStatus.ALIGNED
  assert result.aligned
  assert result.maximum_coordinate_residual_m is not None
  assert result.maximum_coordinate_residual_m == pytest.approx(0.0, abs=1.0e-12)
  assert topology.connected
  assert topology.forms_closed_zone
  assert topology.boundary_component_count == 1
