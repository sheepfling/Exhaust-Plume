from __future__ import annotations

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  CharacteristicFamily,
  CharacteristicState,
  MocPrimitiveStatus,
  solve_ambient_pressure_free_boundary,
  solve_ambient_pressure_free_boundary_point,
  solve_reflected_free_boundary,
  solve_underexpanded_expansion_fan,
)
from exhaust_plume.models.nozzle.exit_state import derive_ambient_state, derive_uniform_nozzle_exit


def _states(*, total_pressure_Pa: float = 2.0e6):
  gas = CaloricallyPerfectGas.dry_air()
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=2.0,
      total_pressure_Pa=total_pressure_Pa,
      total_temperature_K=900.0,
      exit_radius_m=0.05,
    ),
    gas,
  )
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=101325.0, temperature_K=300.0), gas)
  return exit_state, ambient


def test_free_boundary_has_ambient_pressure_and_tangent_residuals() -> None:
  exit_state, ambient = _states()

  result = solve_ambient_pressure_free_boundary(exit_state, ambient, extent_m=0.2)

  assert result.converged
  assert result.terminal_mach is not None
  assert result.terminal_flow_angle_rad is not None
  assert result.points_m[0] == (0.0, 0.05)
  assert result.points_m[1][0] > result.points_m[0][0]
  assert result.pressure_residual == 0.0 or abs(result.pressure_residual) < 1.0e-10
  assert result.tangent_residual == 0.0


def test_free_boundary_does_not_accept_overexpanded_exit() -> None:
  exit_state, ambient = _states(total_pressure_Pa=80000.0)

  result = solve_ambient_pressure_free_boundary(exit_state, ambient)

  assert result.status is MocPrimitiveStatus.OUTSIDE_DOMAIN
  assert not result.points_m


def test_free_boundary_point_marches_a_characteristic_with_pressure_matching() -> None:
  incoming = CharacteristicState(
    x_m=0.0,
    y_m=0.0,
    theta_rad=0.0,
    mach=2.0,
    gamma=1.4,
  )
  previous_boundary = CharacteristicState(
    x_m=0.0,
    y_m=0.05,
    theta_rad=0.0,
    mach=2.0,
    gamma=1.4,
  )

  result = solve_ambient_pressure_free_boundary_point(
    incoming,
    previous_boundary,
    CharacteristicFamily.PLUS,
    total_pressure_Pa=2.0e6,
    ambient_pressure_Pa=101325.0,
  )

  assert result.converged
  assert result.state is not None
  assert result.point_m is not None
  assert result.point_m[0] > incoming.x_m
  assert result.pressure_residual == pytest.approx(0.0, abs=1.0e-12)
  assert result.tangent_residual == pytest.approx(0.0, abs=1.0e-12)


def test_reflected_free_boundary_march_preserves_centerline_and_boundary_contracts() -> None:
  exit_state, ambient = _states()
  fan = solve_underexpanded_expansion_fan(exit_state, ambient, characteristic_count=8)

  result = solve_reflected_free_boundary(fan, exit_state, ambient)

  assert result.converged
  assert result.seed_boundary_state is not None
  assert len(result.centerline_results) == 9
  assert len(result.centerline_states) == 9
  assert len(result.point_results) == 9
  assert len(result.boundary_states) == 9
  assert len(result.boundary_points_m) == 9
  assert all(state.theta_rad == pytest.approx(0.0, abs=1.0e-12) for state in result.centerline_states)
  assert all(point.converged for point in result.point_results)
  assert all(
    right[0] > left[0]
    for left, right in zip(result.boundary_points_m, result.boundary_points_m[1:])
  )
  assert all(point.pressure_residual == pytest.approx(0.0, abs=1.0e-12) for point in result.point_results)
  assert all(point.tangent_residual == pytest.approx(0.0, abs=1.0e-12) for point in result.point_results)
