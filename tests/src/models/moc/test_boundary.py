from __future__ import annotations

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput
from exhaust_plume.models.moc import (
  MocPrimitiveStatus,
  solve_ambient_pressure_free_boundary,
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
