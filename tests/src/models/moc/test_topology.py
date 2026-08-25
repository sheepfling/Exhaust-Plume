from __future__ import annotations

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocTopologyStatus,
  solve_underexpanded_expansion_fan,
  validate_moc_mesh,
)
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit


def test_open_fan_topology_reports_boundary_without_nonmanifold_edges() -> None:
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
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=101325.0, temperature_K=300.0), gas)
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)

  topology = validate_moc_mesh(fan.cells)

  assert topology.status is MocTopologyStatus.OPEN
  assert topology.cell_count == 8
  assert topology.edge_count == 17
  assert topology.boundary_edge_count == 10
  assert topology.boundary_component_count == 1
  assert topology.boundary_is_closed_cycle
  assert topology.forms_closed_zone
  assert topology.nonmanifold_edge_count == 0
  assert topology.connected


def test_two_triangles_can_form_a_closed_mesh() -> None:
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
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=101325.0, temperature_K=300.0), gas)
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=2)
  first = fan.cells[0]
  second = type(first)(
    cell_index=1,
    vertices_xr_m=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
    state=first.state,
    geometry_status=first.geometry_status,
  )
  first_closed = type(first)(
    cell_index=0,
    vertices_xr_m=((0.0, 0.0), (1.0, 1.0), (0.0, 1.0)),
    state=first.state,
    geometry_status=first.geometry_status,
  )

  topology = validate_moc_mesh((first_closed, second))

  assert topology.status is MocTopologyStatus.OPEN
  assert topology.boundary_edge_count == 4
  assert topology.boundary_component_count == 1
  assert topology.forms_closed_zone
  assert topology.connected
