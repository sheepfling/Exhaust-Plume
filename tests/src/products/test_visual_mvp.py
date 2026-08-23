from __future__ import annotations

from math import pow
from pathlib import Path

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  ShockCellSolveConfig,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
  solve_shock_cells,
)
from exhaust_plume.contracts.errors import ProductOutsideApplicabilityError
from exhaust_plume.products.visual import (
  build_sectioned_tube_mesh,
  evaluate_visual_definition,
  evaluate_shock_cell_visual,
  evaluate_nozzle_geometry_visual,
  load_straight_visual_definition,
  render_visual_preview,
  visual_definition_from_shock_cells,
  write_visual_mesh_json,
  write_visual_obj,
  write_visual_result_json,
  write_straight_visual_asset,
)

ROOT = Path(__file__).resolve().parents[3]


def test_visual_mvp_exports_deterministic_mesh_and_result(tmp_path: Path) -> None:
  definition = load_straight_visual_definition(ROOT / 'fixtures/products/visual_asset_v1.json')
  result = evaluate_visual_definition(definition, maximum_section_count=5)
  mesh = build_sectioned_tube_mesh(result, radial_segments=8)

  assert mesh.section_count == 5
  assert len(mesh.vertices) == 5 * 8 + 2
  assert len(mesh.faces) == 2 * 4 * 8 + 2 * 8
  assert mesh.minimum_m[0] < 0.0
  assert mesh.maximum_m[0] > 4.0
  assert write_visual_result_json(result, tmp_path / 'result.json').is_file()
  assert write_visual_mesh_json(mesh, tmp_path / 'mesh.json').is_file()
  assert load_straight_visual_definition(write_straight_visual_asset(definition, tmp_path / 'asset.json')) == definition
  obj_path = write_visual_obj(mesh, tmp_path / 'mesh.obj')
  assert obj_path.read_text(encoding='utf-8').startswith('# plume.visual.triangle-mesh@1')
####


def test_visual_mvp_renders_preview_with_optional_plot_dependency(tmp_path: Path) -> None:
  import matplotlib
  matplotlib.use('Agg')

  definition = load_straight_visual_definition(ROOT / 'fixtures/products/visual_asset_v1.json')
  result = evaluate_visual_definition(definition)
  preview = render_visual_preview(result, tmp_path / 'preview.png')
  assert preview.read_bytes().startswith(b'\x89PNG')
####


def test_visual_mvp_adapts_simple_straight_solver_result() -> None:
  gas = CaloricallyPerfectGas.dry_air()
  mach = 3.0
  total_pressure = 100000.0 * 1.1 * pow(
    1.0 + (gas.gamma - 1.0) * mach**2 / 2.0,
    gas.gamma / (gas.gamma - 1.0),
  )
  exit_state = derive_uniform_nozzle_exit(NozzleExitInput(
    mach=mach,
    total_pressure_Pa=total_pressure,
    total_temperature_K=800.0,
    exit_radius_m=1.0,
  ), gas)
  ambient = derive_ambient_state(AmbientInput(
    pressure_Pa=100000.0,
    temperature_K=300.0,
  ), gas)
  solved = solve_shock_cells(ShockCellSolveConfig(
    exit=exit_state,
    ambient=ambient,
    max_cells=1,
    expansion_characteristics=2,
    compression_characteristics=1,
  ))

  definition = visual_definition_from_shock_cells(solved, section_count=12)
  assert len(definition.sections) == 12
  result = evaluate_shock_cell_visual(solved, section_count=12)
  assert len(result.sections) == 12
  assert result.channels['core_radius_fraction'][0] > 0.0
  assert result.metadata.claims.geometry.value == 'engineering_approximate'
  assert result.metadata.claims.derivation.value == 'adapted'
  assert result.metadata.applicability.status.value == 'marginal'
####


def test_visual_mvp_runs_explicit_geometry_path_and_rejects_near_vacuum_failure() -> None:
  from exhaust_plume import NozzleGeometry, ThroatConfiguration

  geometry = NozzleGeometry(
    geometry_id='visual-test-ratio-9',
    throat=ThroatConfiguration(area_m2=1.0e-2),
    exit_area_m2=9.0e-2,
  )
  result = evaluate_nozzle_geometry_visual(
    geometry,
    total_pressure_Pa=20.0 * 101325.0,
    total_temperature_K=800.0,
    ambient_pressure_Pa=10000.0,
    gas=CaloricallyPerfectGas.dry_air(),
    section_count=8,
  )
  assert len(result.sections) == 8
  assert result.metadata.applicability.status.value == 'marginal'

  with pytest.raises(ProductOutsideApplicabilityError):
    evaluate_nozzle_geometry_visual(
      geometry,
      total_pressure_Pa=20.0 * 101325.0,
      total_temperature_K=800.0,
      ambient_pressure_Pa=1.0,
      gas=CaloricallyPerfectGas.dry_air(),
      section_count=8,
    )
  ####
####


def test_visual_mvp_does_not_render_a_failed_or_empty_solver_result() -> None:
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(NozzleExitInput(
    mach=3.0,
    total_pressure_Pa=20.0 * 101325.0,
    total_temperature_K=800.0,
    exit_radius_m=1.0,
  ), gas)
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=1.0, temperature_K=300.0), gas)
  solved = solve_shock_cells(ShockCellSolveConfig(
    exit=exit_state,
    ambient=ambient,
    max_cells=1,
    expansion_characteristics=2,
    compression_characteristics=1,
  ))
  with pytest.raises(ProductOutsideApplicabilityError):
    evaluate_shock_cell_visual(solved, section_count=8)
  ####
####
