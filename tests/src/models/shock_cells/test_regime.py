from __future__ import annotations

from math import pow

import pytest

from exhaust_plume import (
    AmbientInput,
    CaloricallyPerfectGas,
    ExpansionRegime,
    NozzleExitInput,
    ShockCellSolveConfig,
    SolverStatus,
    TerminationReason,
    classify_expansion_regime,
    derive_ambient_state,
    derive_uniform_nozzle_exit,
    dimensionless_pressure_residual,
    solve_shock_cells,
)


def _states(exit_pressure_ratio: float):
  gas = CaloricallyPerfectGas.dry_air()
  mach = 3.0
  ambient_pressure = 100_000.0
  total_pressure = ambient_pressure * exit_pressure_ratio * pow(1.0 + (gas.gamma - 1.0) / 2.0 * mach**2, gas.gamma / (gas.gamma - 1.0))
  exit_state = derive_uniform_nozzle_exit(
      config=NozzleExitInput(mach=mach, total_pressure_Pa=total_pressure, total_temperature_K=800.0, exit_radius_m=1.0),
      gas=gas,
  )
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=ambient_pressure, temperature_K=300.0), gas)
  return exit_state, ambient


def test_classification_uses_dimensionless_residual_and_tolerance() -> None:
  exit_state, ambient = _states(1.0)
  assert dimensionless_pressure_residual(exit_state.static_pressure_Pa, ambient.pressure_Pa) == pytest.approx(0.0)
  assert classify_expansion_regime(exit_state, ambient) is ExpansionRegime.MATCHED
  assert classify_expansion_regime(exit_state, ambient, pressure_match_rtol=1.0e-6) is ExpansionRegime.MATCHED

  under, _ = _states(1.1)
  over, _ = _states(0.9)
  assert classify_expansion_regime(under, ambient) is ExpansionRegime.UNDEREXPANDED
  assert classify_expansion_regime(over, ambient) is ExpansionRegime.OVEREXPANDED
  ####


def test_matched_flow_returns_no_cells() -> None:
  exit_state, ambient = _states(1.0)
  result = solve_shock_cells(ShockCellSolveConfig(exit=exit_state, ambient=ambient, max_cells=4))

  assert result.regime is ExpansionRegime.MATCHED
  assert result.cells == ()
  assert result.status is SolverStatus.CONVERGED
  assert result.termination_reason is TerminationReason.NO_PRESSURE_MISMATCH
  ####


def test_zero_cell_safety_limit_returns_no_cells_for_mismatch() -> None:
  exit_state, ambient = _states(1.1)
  result = solve_shock_cells(ShockCellSolveConfig(exit=exit_state, ambient=ambient, max_cells=0))

  assert result.regime is ExpansionRegime.UNDEREXPANDED
  assert result.cells == ()
  assert result.termination_reason is TerminationReason.MAX_CELL_LIMIT
  ####


def test_nonmatched_foundation_result_uses_cell_index_and_finite_closed_zones() -> None:
  exit_state, ambient = _states(1.1)
  result = solve_shock_cells(ShockCellSolveConfig(exit=exit_state, ambient=ambient, max_cells=1, expansion_characteristics=2, compression_characteristics=1))

  assert result.cells
  assert result.cells[0].cell_index == 1
  assert result.zones
  assert all(zone.cell_index == 1 for zone in result.zones)
  assert all(zone.vertices_xr_m.flags.writeable is False for zone in result.zones)
  ####
