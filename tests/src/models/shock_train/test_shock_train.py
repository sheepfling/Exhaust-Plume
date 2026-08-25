from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume import (
  AmbientInput,
  CaloricallyPerfectGas,
  NozzleExitInput,
  derive_ambient_state,
  derive_uniform_nozzle_exit,
)
from exhaust_plume.contracts.termination import TerminationReason
from exhaust_plume.models.shock_cells import ShockCellSolveConfig, solve_shock_cells
from exhaust_plume.models.shock_train import (
  GeometryFidelity,
  ShockTrainCalibration,
  ShockTrainStatus,
  ShockTrainTerminationPolicy,
  propagate_shock_train_covariance,
  sweep_shock_train_parameter,
  solve_shock_train,
)


def _first_cell():
  gas = CaloricallyPerfectGas.dry_air()
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=1.000001,
      total_pressure_Pa=2.27 * ambient.pressure_Pa,
      total_temperature_K=300.0,
      exit_radius_m=0.019,
    ),
    gas,
  )
  return solve_shock_cells(ShockCellSolveConfig(exit=exit_state, ambient=ambient, max_cells=1))
####


def _calibration(
    *,
    mixing_layer_growth_rate: float = 0.01,
    pressure_amplitude_decay_coefficient: float = 0.3,
    total_pressure_loss_coefficient: float = 0.02,
) -> ShockTrainCalibration:
  return ShockTrainCalibration(
    calibration_id='test-shock-train-v1',
    source_description='unit-test closure; not external calibration',
    applicable_mach_range=(1.0, 2.0),
    applicable_pressure_ratio_range=(1.0, 10.0),
    applicable_temperature_ratio_range=(0.1, 10.0),
    mixing_layer_growth_rate=mixing_layer_growth_rate,
    pressure_amplitude_decay_coefficient=pressure_amplitude_decay_coefficient,
    cell_spacing_coefficient=1.306,
    finite_shear_layer_spacing_correction=0.5,
    total_pressure_loss_coefficient=total_pressure_loss_coefficient,
    mean_pressure_relaxation_coefficient=0.2,
    parameter_covariance=((1.0, -0.1), (-0.1, 1.0)),
    covariance_parameter_names=(
      'mixing_layer_growth_rate',
      'pressure_amplitude_decay_coefficient',
    ),
  )
####


def test_physical_termination_is_not_a_cell_limit() -> None:
  result = solve_shock_train(
    _first_cell(),
    _calibration(),
    ShockTrainTerminationPolicy(max_cells=100, max_axial_distance_m=10.0),
  )

  assert result.status is ShockTrainStatus.PHYSICALLY_TERMINATED
  assert result.termination.is_physical
  assert result.termination_reason is TerminationReason.CORE_BECAME_SUBSONIC
  assert result.cell_count > 1
  assert result.supersonic_core_end_x_m == result.shock_train_end_x_m
  assert result.uncertainty['status'] == 'calibration-covariance-retained; response-propagation-explicit-diagnostic'
  assert result.cells[0].metrics.geometry_fidelity is GeometryFidelity.RESOLVED_FIRST_CELL
  assert all(
    cell.metrics.geometry_fidelity is GeometryFidelity.SCALED_REDUCED_ORDER
    for cell in result.cells[1:]
  )
  assert result.diagnostics['geometry_fidelity_counts']['scaled-reduced-order'] == result.cell_count - 1
####


def test_max_cell_limit_is_reported_as_truncation_and_not_physical() -> None:
  result = solve_shock_train(
    _first_cell(),
    _calibration(),
    ShockTrainTerminationPolicy(max_cells=3, max_axial_distance_m=10.0),
  )

  assert result.status is ShockTrainStatus.TRUNCATED
  assert result.termination_reason is TerminationReason.MAX_CELL_LIMIT
  assert not result.termination.is_physical
  assert not result.was_domain_truncated
  assert result.cell_count == 3
####


def test_domain_limit_is_distinct_from_max_cell_limit() -> None:
  seed = _first_cell()
  result = solve_shock_train(
    seed,
    _calibration(),
    ShockTrainTerminationPolicy(max_cells=100, max_axial_distance_m=0.04),
  )

  assert result.status is ShockTrainStatus.TRUNCATED
  assert result.termination_reason is TerminationReason.SPATIAL_DOMAIN_LIMIT
  assert result.was_domain_truncated
  assert not result.termination.is_physical
####


def test_zero_growth_keeps_core_diameter_constant_until_other_termination() -> None:
  result = solve_shock_train(
    _first_cell(),
    _calibration(mixing_layer_growth_rate=0.0, total_pressure_loss_coefficient=0.0),
    ShockTrainTerminationPolicy(max_cells=4, max_axial_distance_m=10.0),
  )

  diameters = [cell.metrics.effective_core_diameter_m for cell in result.cells]
  assert result.termination_reason is TerminationReason.MAX_CELL_LIMIT
  assert diameters == [diameters[0]] * len(diameters)
####


def test_zero_amplitude_decay_preserves_amplitude_until_safety_limit() -> None:
  result = solve_shock_train(
    _first_cell(),
    _calibration(pressure_amplitude_decay_coefficient=0.0, total_pressure_loss_coefficient=0.0),
    ShockTrainTerminationPolicy(max_cells=4, max_axial_distance_m=10.0),
  )

  amplitudes = result.diagnostics['pressure_amplitude_history']
  assert result.termination_reason is TerminationReason.MAX_CELL_LIMIT
  assert amplitudes == [amplitudes[0]] * len(amplitudes)


def test_sensitivity_sweep_is_explicit_and_does_not_change_first_cell() -> None:
  first_cell = _first_cell()
  policy = ShockTrainTerminationPolicy(max_cells=100, max_axial_distance_m=10.0)
  points = sweep_shock_train_parameter(
    first_cell,
    _calibration(),
    policy,
    parameter_name='mixing_layer_growth_rate',
    values=(0.0, 0.01, 0.02),
  )

  assert [point.parameter_value for point in points] == [0.0, 0.01, 0.02]
  # Higher mixing growth shortens the physical axial extent, while the
  # closure's cell spacing also changes the number of discrete cells.  The
  # sensitivity contract records both; cell count alone is not monotone.
  assert points[0].shock_train_end_x_m > points[-1].shock_train_end_x_m
  assert points[0].cell_count != points[-1].cell_count
  assert first_cell.exit_state.mach == 1.000001


def test_matched_exit_has_no_train_and_reports_no_pressure_mismatch() -> None:
  gas = CaloricallyPerfectGas.dry_air()
  ambient = derive_ambient_state(
    AmbientInput(pressure_Pa=101325.0, temperature_K=300.0),
    gas,
  )
  pressure_factor = 1.0 + (gas.gamma - 1.0) * 1.000001**2 / 2.0
  exit_state = derive_uniform_nozzle_exit(
    NozzleExitInput(
      mach=1.000001,
      total_pressure_Pa=ambient.pressure_Pa * pressure_factor ** (gas.gamma / (gas.gamma - 1.0)),
      total_temperature_K=300.0,
      exit_radius_m=0.019,
    ),
    gas,
  )
  first_cell = solve_shock_cells(ShockCellSolveConfig(exit=exit_state, ambient=ambient, max_cells=1))
  result = solve_shock_train(
    first_cell,
    _calibration(),
    ShockTrainTerminationPolicy(max_cells=4, max_axial_distance_m=10.0),
  )
  assert result.cells == ()
  assert result.status is ShockTrainStatus.PHYSICALLY_TERMINATED
  assert result.termination_reason is TerminationReason.NO_PRESSURE_MISMATCH


def test_covariance_propagation_preserves_parameter_order_and_reports_output_uncertainty() -> None:
  first_cell = _first_cell()
  result = propagate_shock_train_covariance(
    first_cell,
    _calibration(),
    ShockTrainTerminationPolicy(max_cells=12, max_axial_distance_m=10.0),
  )

  assert result['status'] == 'linearized-propagation'
  assert result['parameter_names'] == [
    'mixing_layer_growth_rate',
    'pressure_amplitude_decay_coefficient',
  ]
  assert result['output_names'] == [
    'shock_train_end_x_m',
    'first_cell_length_m',
    'last_pressure_amplitude',
  ]
  assert len(result['jacobian']) == 3
  assert len(result['jacobian'][0]) == 2
  assert result['output_covariance'] is not None
  assert all(value >= 0.0 for value in result['output_standard_deviation'])
  assert result['discrete_cell_count_is_not_differentiated'] is True
  assert {item['difference_scheme'] for item in result['perturbations']} == {'central'}


def test_covariance_propagation_without_covariance_is_explicitly_unavailable() -> None:
  first_cell = _first_cell()
  calibration = _calibration().__class__(
    calibration_id='test-shock-train-no-covariance-v1',
    source_description='unit-test closure without covariance',
    applicable_mach_range=(1.0, 2.0),
    applicable_pressure_ratio_range=(1.0, 10.0),
    applicable_temperature_ratio_range=(0.1, 10.0),
    mixing_layer_growth_rate=0.01,
    pressure_amplitude_decay_coefficient=0.3,
    cell_spacing_coefficient=1.306,
    finite_shear_layer_spacing_correction=0.5,
    total_pressure_loss_coefficient=0.02,
    mean_pressure_relaxation_coefficient=0.2,
  )
  result = propagate_shock_train_covariance(
    first_cell,
    calibration,
    ShockTrainTerminationPolicy(max_cells=4, max_axial_distance_m=10.0),
  )

  assert result['status'] == 'not-available-no-calibration-covariance'


def test_covariance_requires_explicit_parameter_order() -> None:
  with pytest.raises(ValueError, match='covariance_parameter_names'):
    replace(_calibration(), covariance_parameter_names=None)
