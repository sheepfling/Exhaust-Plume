from __future__ import annotations

import json
from pathlib import Path

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  ExpansionRegime,
  NozzleExitInput,
  ShockCellSolveConfig,
  SolverStatus,
  classify_expansion_regime,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
  solve_shock_cells,
)

ROOT = Path(__file__).resolve().parents[4]


def _fixture() -> dict:
  return json.loads((ROOT / 'tests/fixtures/physics/first_mvp_regression_v1.json').read_text(encoding='utf-8'))
####


def _states(total_pressure_Pa: float) -> tuple:
  values = _fixture()['gas']
  gas = CaloricallyPerfectGas.dry_air(gamma=values['gamma'])
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=values['mach'],
      total_pressure_Pa=total_pressure_Pa,
      total_temperature_K=values['total_temperature_K'],
      exit_radius_m=values['exit_radius_m'],
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(
      pressure_Pa=values['ambient_pressure_Pa'],
      temperature_K=values['ambient_temperature_K'],
    ),
    gas,
  )
  return exit_state, ambient
####


def test_first_mvp_pressure_ratio_fixture_classifies_from_static_exit_pressure() -> None:
  values = _fixture()
  gas = CaloricallyPerfectGas.dry_air(gamma=values['gas']['gamma'])
  factor = 1.0 + (gas.gamma - 1.0) * values['gas']['mach']**2 / 2.0
  total_to_ambient = factor**(gas.gamma / (gas.gamma - 1.0))
  assert total_to_ambient == pytest.approx(220.45, rel=2.0e-3)
  for case in values['pressure_ratio_cases']:
    total_pressure = values['gas']['ambient_pressure_Pa'] * case['exit_to_ambient_pressure_ratio'] * total_to_ambient
    exit_state, ambient = _states(total_pressure)
    assert classify_expansion_regime(exit_state, ambient).value == case['expected_regime']
  ####
####


def test_first_mvp_strong_overexpanded_case_returns_structured_failure() -> None:
  values = _fixture()
  gas = CaloricallyPerfectGas.dry_air(gamma=values['gas']['gamma'])
  factor = 1.0 + (gas.gamma - 1.0) * values['gas']['mach']**2 / 2.0
  total_pressure = values['gas']['ambient_pressure_Pa'] * 0.1 * factor**(gas.gamma / (gas.gamma - 1.0))
  exit_state, ambient = _states(total_pressure)
  result = solve_shock_cells(ShockCellSolveConfig(exit=exit_state, ambient=ambient, max_cells=1))
  assert result.regime is ExpansionRegime.OVEREXPANDED
  assert result.status is SolverStatus.NUMERICAL_FAILURE
  assert result.details['solver_diagnostics_v1']['status'] == 'numerical_failure'
####


def test_legacy_total_pressure_anchors_are_regression_only_and_not_relabelled() -> None:
  values = _fixture()
  for case in values['legacy_total_pressure_anchors']:
    exit_state, ambient = _states(case['total_pressure_atm'] * 101325.0)
    assert classify_expansion_regime(exit_state, ambient) is ExpansionRegime.OVEREXPANDED
    assert case['regression_only'] is True
  ####
####
