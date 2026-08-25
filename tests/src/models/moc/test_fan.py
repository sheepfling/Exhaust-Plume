from __future__ import annotations

from math import isclose

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import MocPrimitiveStatus, solve_underexpanded_expansion_fan
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit


def _case(*, exit_mach: float = 2.0, exit_total_pressure: float = 2000000.0):
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=exit_mach,
      total_pressure_Pa=exit_total_pressure,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  return exit_state, ambient


def test_underexpanded_fan_reaches_ambient_pressure_and_validates_cells() -> None:
  exit_state, ambient = _case()
  result = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)

  assert result.converged
  assert len(result.states) == 9
  assert len(result.centerline_states) == 9
  assert len(result.lip_states) == 9
  assert len(result.centerline_points_m) == 9
  assert len(result.lip_ray_centerline_points_m) == 9
  assert len(result.cells) == 8
  assert result.terminal_pressure_residual == pytest.approx(0.0, abs=1.0e-12)
  assert all(cell.geometry_status.value == 'valid' for cell in result.cells)
  assert all(state.x_m == pytest.approx(0.0) and state.y_m == pytest.approx(0.05) for state in result.lip_states)
  assert all(state.y_m == pytest.approx(0.0) for state in result.states)
  assert all(state.theta_rad == pytest.approx(0.0, abs=1.0e-12) for state in result.centerline_states)
  assert all(
    state.x_m == pytest.approx(point[0], abs=1.0e-12)
    for state, point in zip(result.centerline_states, result.centerline_points_m, strict=True)
  )
  assert all(
    right[0] > left[0]
    for left, right in zip(result.centerline_points_m, result.centerline_points_m[1:])
  )
  assert isclose(result.states[-1].theta_rad - result.states[0].theta_rad, result.terminal_turn_rad)
  assert result.lip_ray_centerline_points_m[-1][0] > result.centerline_points_m[-1][0]


def test_fan_rejects_matched_or_overexpanded_exit() -> None:
  exit_state, ambient = _case(exit_total_pressure=80000.0)
  result = solve_underexpanded_expansion_fan(exit_state, ambient)

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert not result.cells


def test_fan_requires_multiple_characteristics() -> None:
  exit_state, ambient = _case()
  with pytest.raises(ValueError, match='at least two'):
    solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=1)
