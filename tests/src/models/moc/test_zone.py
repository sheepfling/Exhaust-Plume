from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocZoneAssemblyStatus,
  assemble_reflected_characteristic_zone,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
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

  result = assemble_reflected_characteristic_zone(fan, reflected_boundary)

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
  assert result.shock_closure_status == 'not_assembled'
  assert all(node.point_result.converged for node in result.nodes)
  assert all(cell.geometry_status.value == 'valid' for cell in result.cells)
  assert sum(cell.cell_kind == 'axis-strip' for cell in result.cells) == 8
  assert sum(cell.cell_kind == 'interior' for cell in result.cells) == 28
  assert sum(cell.cell_kind == 'free-boundary-strip' for cell in result.cells) == 8
