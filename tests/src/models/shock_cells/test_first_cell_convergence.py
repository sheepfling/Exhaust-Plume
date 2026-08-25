from __future__ import annotations

from math import fabs

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.models.moc import (
  MocZoneAssemblyStatus,
  assemble_reflected_characteristic_zone,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
)


def _open_lattice_metrics(characteristic_count: int) -> dict[str, float | int | str]:
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
    characteristic_count=characteristic_count,
  )
  boundary = solve_reflected_free_boundary(fan, exit_state, ambient)
  zone = assemble_reflected_characteristic_zone(fan, boundary)
  assert zone.status is MocZoneAssemblyStatus.CONVERGED_OPEN
  assert zone.coverage_area_m2 is not None
  assert zone.coverage_area_residual_m2 is not None
  assert boundary.centerline_states
  assert boundary.boundary_points_m
  max_invariant_residual = max(
    max(
      fabs(node.point_result.invariant_residual_plus or 0.0),
      fabs(node.point_result.invariant_residual_minus or 0.0),
    )
    for node in zone.nodes
  )
  return {
    'characteristic_count': characteristic_count,
    'node_count': zone.node_count,
    'cell_count': zone.cell_count,
    'coverage_area_m2': zone.coverage_area_m2,
    'coverage_area_residual_m2': zone.coverage_area_residual_m2,
    'maximum_radius_m': max(point[1] for point in boundary.boundary_points_m),
    'open_extent_x_m': max(
      max(node.point_m[0] for node in zone.nodes),
      max(point[0] for point in boundary.boundary_points_m),
    ),
    'centerline_endpoint_x_m': boundary.centerline_states[-1].x_m,
    'maximum_pressure_residual': max(
      fabs(point.pressure_residual or 0.0) for point in boundary.point_results
    ),
    'maximum_tangent_residual': max(
      fabs(point.tangent_residual or 0.0) for point in boundary.point_results
    ),
    'maximum_invariant_residual': max_invariant_residual,
    'physical_closure_status': zone.physical_closure_status,
    'shock_closure_status': zone.shock_closure_status,
  }


def test_open_reflected_lattice_refinement_is_monotone_but_not_a_physical_first_cell() -> None:
  coarse = _open_lattice_metrics(4)
  medium = _open_lattice_metrics(8)
  fine = _open_lattice_metrics(16)

  assert [coarse['node_count'], medium['node_count'], fine['node_count']] == [15, 45, 153]
  assert [coarse['cell_count'], medium['cell_count'], fine['cell_count']] == [14, 44, 152]
  assert coarse['coverage_area_m2'] < medium['coverage_area_m2'] < fine['coverage_area_m2']
  assert coarse['maximum_radius_m'] > medium['maximum_radius_m'] > fine['maximum_radius_m']
  assert coarse['open_extent_x_m'] > medium['open_extent_x_m'] > fine['open_extent_x_m']
  assert (
    medium['coverage_area_m2'] - coarse['coverage_area_m2']
    > fine['coverage_area_m2'] - medium['coverage_area_m2']
  )
  assert (
    coarse['maximum_radius_m'] - medium['maximum_radius_m']
    > medium['maximum_radius_m'] - fine['maximum_radius_m']
  )
  assert all(
    metric['coverage_area_residual_m2'] == pytest.approx(0.0, abs=1.0e-12)
    and metric['maximum_pressure_residual'] <= 1.0e-12
    and metric['maximum_tangent_residual'] <= 1.0e-12
    and metric['maximum_invariant_residual'] <= 2.0e-12
    for metric in (coarse, medium, fine)
  )
  assert coarse['centerline_endpoint_x_m'] == pytest.approx(
    medium['centerline_endpoint_x_m'],
    abs=1.0e-12,
  )
  assert medium['centerline_endpoint_x_m'] == pytest.approx(
    fine['centerline_endpoint_x_m'],
    abs=1.0e-12,
  )
  assert all(metric['physical_closure_status'] == 'open' for metric in (coarse, medium, fine))
  assert all(metric['shock_closure_status'] == 'not_assembled' for metric in (coarse, medium, fine))
  ####
