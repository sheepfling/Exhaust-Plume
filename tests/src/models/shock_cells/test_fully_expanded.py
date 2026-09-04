from __future__ import annotations

from math import pi

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  FirstCellCorrelationStatus,
  FullyExpandedStatus,
  NozzleExitInput,
  compare_first_cell_length,
  derive_ambient_state,
  derive_fully_expanded_jet,
  derive_uniform_nozzle_exit,
  prandtl_pack_first_cell_spacing,
)


def _states(*, exit_pressure_ratio: float, exit_radius_m: float = 1.0):
  gas = CaloricallyPerfectGas.dry_air()
  mach = 3.0
  ambient_pressure_Pa = 100_000.0
  isentropic_factor = (1.0 + (gas.gamma - 1.0) * mach**2 / 2.0) ** (
    gas.gamma / (gas.gamma - 1.0)
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=mach,
      total_pressure_Pa=ambient_pressure_Pa * exit_pressure_ratio * isentropic_factor,
      total_temperature_K=800.0,
      exit_radius_m=exit_radius_m,
    ),
    gas,
  )
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=ambient_pressure_Pa, temperature_K=300.0),
    gas,
  )
  return exit_state, ambient
####


def test_fully_expanded_state_preserves_total_conditions() -> None:
  exit_state, ambient = _states(exit_pressure_ratio=1.25)
  result = derive_fully_expanded_jet(exit_state, ambient)

  assert result.status is FullyExpandedStatus.CONVERGED
  assert result.state is not None
  assert result.state.static_pressure_Pa == pytest.approx(ambient.pressure_Pa)
  assert result.state.total_pressure_Pa == pytest.approx(exit_state.total_pressure_Pa)
  assert result.state.total_temperature_K == pytest.approx(exit_state.total_temperature_K)
  assert result.state.gas.total_pressure_from_static(
    result.state.mach,
    result.state.static_pressure_Pa,
  ) == pytest.approx(exit_state.total_pressure_Pa, rel=1.0e-12)
  assert result.state.gas.total_temperature_from_static(
    result.state.mach,
    result.state.static_temperature_K,
  ) == pytest.approx(exit_state.total_temperature_K, rel=1.0e-12)
  assert result.diameter_m is not None and result.diameter_m > 0.0
  assert result.area_ratio_to_exit is not None and result.area_ratio_to_exit > 0.0
  assert result.state.area_m2 == pytest.approx(pi * result.radius_m**2)
####


def test_fully_expanded_diameter_and_spacing_scale_with_exit_diameter() -> None:
  small_exit, ambient = _states(exit_pressure_ratio=1.25, exit_radius_m=0.5)
  large_exit, _ = _states(exit_pressure_ratio=1.25, exit_radius_m=1.0)
  small = derive_fully_expanded_jet(small_exit, ambient)
  large = derive_fully_expanded_jet(large_exit, ambient)

  small_correlation = prandtl_pack_first_cell_spacing(small)
  large_correlation = prandtl_pack_first_cell_spacing(large)
  assert small.diameter_m is not None and large.diameter_m is not None
  assert small_correlation.spacing_m is not None and large_correlation.spacing_m is not None
  assert large.diameter_m == pytest.approx(2.0 * small.diameter_m)
  assert large_correlation.spacing_m == pytest.approx(2.0 * small_correlation.spacing_m)
####


def test_prandtl_pack_spacing_uses_equivalent_diameter_and_is_not_imposed() -> None:
  exit_state, ambient = _states(exit_pressure_ratio=1.25)
  fully_expanded = derive_fully_expanded_jet(exit_state, ambient)
  correlation = prandtl_pack_first_cell_spacing(fully_expanded)

  assert correlation.status is FirstCellCorrelationStatus.CONVERGED
  assert correlation.spacing_m == pytest.approx(
    1.306
    * fully_expanded.diameter_m
    * (fully_expanded.mach**2 - 1.0) ** 0.5,
  )
  comparison = compare_first_cell_length(10.0, correlation)
  assert comparison.relative_error is not None
  assert comparison.relative_error == pytest.approx((10.0 - correlation.spacing_m) / correlation.spacing_m)
####


def test_matched_flow_has_no_first_cell_correlation_claim() -> None:
  exit_state, ambient = _states(exit_pressure_ratio=1.0)
  fully_expanded = derive_fully_expanded_jet(exit_state, ambient)
  correlation = prandtl_pack_first_cell_spacing(fully_expanded)

  assert fully_expanded.status is FullyExpandedStatus.CONVERGED
  assert fully_expanded.first_cell_claim_allowed is False
  assert correlation.status is FirstCellCorrelationStatus.NO_FIRST_CELL_CLAIM
  assert correlation.spacing_m is None
####


def test_non_supersonic_equivalent_state_is_explicitly_outside_validity() -> None:
  exit_state, _ = _states(exit_pressure_ratio=1.0)
  ambient_pressure_Pa = exit_state.total_pressure_Pa * 1.01
  result = derive_fully_expanded_jet(exit_state, ambient_pressure_Pa)

  assert result.status is FullyExpandedStatus.OUTSIDE_MODEL_VALIDITY
  assert result.state is None
  assert 'supersonic equivalent' in result.message
####
