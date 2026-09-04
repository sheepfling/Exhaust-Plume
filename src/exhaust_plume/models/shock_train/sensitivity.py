"""Explicit closure-parameter sensitivity sweeps for the shock-train lane."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from typing import Any

from exhaust_plume.models.shock_cells.contracts import ShockCellSolveResult
from exhaust_plume.models.shock_train.contracts import (
  SHOCK_TRAIN_CALIBRATION_PARAMETER_NAMES,
  ShockTrainCalibration,
  ShockTrainStatus,
  ShockTrainTerminationPolicy,
)
from exhaust_plume.models.shock_train.train import solve_shock_train

__all__ = (
  'ShockTrainSensitivityPoint',
  'propagate_shock_train_covariance',
  'sweep_shock_train_parameter',
)


_PROPAGATED_OUTPUT_NAMES = (
  'shock_train_end_x_m',
  'first_cell_length_m',
  'last_pressure_amplitude',
)


@dataclass(frozen=True, slots=True)
class ShockTrainSensitivityPoint:
  """One reproducible closure perturbation and its train response."""

  parameter_name: str
  parameter_value: float
  status: ShockTrainStatus
  termination_reason: str
  cell_count: int
  shock_train_end_x_m: float | None
  pressure_amplitude_final: float | None
####


def _result_outputs(result: Any) -> tuple[float | None, float | None, float | None]:
  amplitudes = result.diagnostics.get('pressure_amplitude_history', ())
  return (
    result.shock_train_end_x_m,
    result.cells[0].metrics.length_m if result.cells else None,
    float(amplitudes[-1]) if amplitudes else None,
  )
####


def _covariance_product(
    jacobian: tuple[tuple[float, ...], ...],
    covariance: tuple[tuple[float, ...], ...],
) -> tuple[tuple[float, ...], ...]:
  return tuple(
    tuple(
      sum(
        jacobian[row][left]
        * covariance[left][right]
        * jacobian[column][right]
        for left in range(len(covariance))
        for right in range(len(covariance))
      )
      for column in range(len(jacobian))
    )
    for row in range(len(jacobian))
  )
####


def propagate_shock_train_covariance(
    first_cell: ShockCellSolveResult,
    calibration: ShockTrainCalibration,
    policy: ShockTrainTerminationPolicy,
    *,
    relative_step: float = 1.0e-4,
    absolute_step: float = 1.0e-8,
) -> dict[str, Any]:
  """Propagate a declared calibration covariance by local finite differences.

  The result is a diagnostic, not a validation claim.  The covariance must
  carry an explicit parameter order, and discrete cell count is reported for
  each perturbation rather than differentiated as if it were continuous.
  Perturbations that leave the model domain are retained as failed samples.
  """

  if not isfinite(relative_step) or relative_step <= 0.0:
    raise ValueError('relative_step must be finite and positive')
  ####
  if not isfinite(absolute_step) or absolute_step <= 0.0:
    raise ValueError('absolute_step must be finite and positive')
  ####
  if calibration.parameter_covariance is None:
    return {
      'status': 'not-available-no-calibration-covariance',
      'parameter_names': [],
      'output_names': list(_PROPAGATED_OUTPUT_NAMES),
      'reason': 'the calibration does not provide a parameter covariance matrix',
    }
  ####
  names = calibration.covariance_parameter_names
  if names is None:
    raise ValueError('calibration covariance parameter order is required')
  ####
  covariance = calibration.parameter_covariance
  if len(names) != len(covariance):
    raise ValueError('covariance parameter order does not match the covariance matrix')
  ####
  if any(name not in SHOCK_TRAIN_CALIBRATION_PARAMETER_NAMES for name in names):
    raise ValueError('covariance parameter order contains an unsupported parameter')
  ####

  baseline_result = solve_shock_train(first_cell, calibration, policy)
  baseline_outputs = _result_outputs(baseline_result)
  perturbations: list[dict[str, Any]] = []
  derivatives: list[list[float | None]] = [
    [] for _ in _PROPAGATED_OUTPUT_NAMES
  ]
  for parameter_name in names:
    nominal = float(getattr(calibration, parameter_name))
    step = max(abs(nominal) * relative_step, absolute_step)
    lower_value = nominal - step
    use_forward = lower_value < 0.0 or (
      parameter_name == 'cell_spacing_coefficient' and lower_value <= 0.0
    )
    plus_calibration = replace(calibration, **{parameter_name: nominal + step})
    plus_result = solve_shock_train(first_cell, plus_calibration, policy)
    plus_outputs = _result_outputs(plus_result)
    minus_result = None
    minus_outputs: tuple[float | None, ...] | None = None
    if not use_forward:
      minus_calibration = replace(calibration, **{parameter_name: lower_value})
      minus_result = solve_shock_train(first_cell, minus_calibration, policy)
      minus_outputs = _result_outputs(minus_result)
    ####
    perturbations.append({
      'parameter_name': parameter_name,
      'nominal_value': nominal,
      'step': step,
      'difference_scheme': 'forward' if use_forward else 'central',
      'plus': {
        'value': nominal + step,
        'status': plus_result.status.value,
        'termination_reason': plus_result.termination_reason.value,
        'cell_count': plus_result.cell_count,
        'outputs': plus_outputs,
      },
      'minus': None if minus_result is None else {
        'value': lower_value,
        'status': minus_result.status.value,
        'termination_reason': minus_result.termination_reason.value,
        'cell_count': minus_result.cell_count,
        'outputs': minus_outputs,
      },
    })
    for output_index, (plus, baseline) in enumerate(zip(plus_outputs, baseline_outputs, strict=True)):
      if plus is None or baseline is None:
        derivatives[output_index].append(None)
      elif use_forward:
        derivatives[output_index].append((plus - baseline) / step)
      elif minus_outputs is None or minus_outputs[output_index] is None:
        derivatives[output_index].append(None)
      else:
        minus = minus_outputs[output_index]
        assert minus is not None
        derivatives[output_index].append(
          (plus - minus) / (2.0 * step)
        )
      ####
    ####
  ####

  complete = all(
    value is not None
    for row in derivatives
    for value in row
  )
  jacobian_rows: list[tuple[float, ...]] = []
  for row in derivatives:
    if not all(value is not None for value in row):
      continue
    ####
    finite_row: list[float] = []
    for value in row:
      assert value is not None
      finite_row.append(float(value))
    ####
    jacobian_rows.append(tuple(finite_row))
  ####
  jacobian = tuple(jacobian_rows)
  output_covariance = (
    _covariance_product(jacobian, covariance)
    if complete else None
  )
  return {
    'status': 'linearized-propagation' if complete else 'partial-propagation',
    'parameter_names': list(names),
    'output_names': list(_PROPAGATED_OUTPUT_NAMES),
    'baseline_outputs': list(baseline_outputs),
    'baseline_status': baseline_result.status.value,
    'baseline_termination_reason': baseline_result.termination_reason.value,
    'baseline_cell_count': baseline_result.cell_count,
    'relative_step': relative_step,
    'absolute_step': absolute_step,
    'jacobian': [list(row) for row in derivatives],
    'input_covariance': [list(row) for row in covariance],
    'output_covariance': (
      [list(row) for row in output_covariance]
      if output_covariance is not None else None
    ),
    'output_standard_deviation': (
      [
        (max(0.0, output_covariance[index][index]) ** 0.5)
        for index in range(len(_PROPAGATED_OUTPUT_NAMES))
      ]
      if output_covariance is not None else None
    ),
    'perturbations': perturbations,
    'discrete_cell_count_is_not_differentiated': True,
  }
####


def sweep_shock_train_parameter(
    first_cell: ShockCellSolveResult,
    calibration: ShockTrainCalibration,
    policy: ShockTrainTerminationPolicy,
    *,
    parameter_name: str,
    values: tuple[float, ...],
) -> tuple[ShockTrainSensitivityPoint, ...]:
  """Run an explicit one-parameter sensitivity sweep.

  Only closure coefficients are accepted.  The first-cell solver and the
  product/provider fidelity boundaries are never mutated by this helper.
  """

  allowed = {
    'mixing_layer_growth_rate',
    'pressure_amplitude_decay_coefficient',
    'cell_spacing_coefficient',
    'finite_shear_layer_spacing_correction',
    'total_pressure_loss_coefficient',
    'mean_pressure_relaxation_coefficient',
  }
  if parameter_name not in allowed:
    raise ValueError(f'unsupported shock-train sensitivity parameter: {parameter_name}')
  ####
  if not values:
    raise ValueError('values must not be empty')
  ####
  points: list[ShockTrainSensitivityPoint] = []
  for value in values:
    value = float(value)
    if not isfinite(value) or value < 0.0:
      raise ValueError('sensitivity values must be finite and nonnegative')
    ####
    varied = replace(calibration, **{parameter_name: value})
    result = solve_shock_train(first_cell, varied, policy)
    amplitudes = result.diagnostics.get('pressure_amplitude_history', ())
    points.append(ShockTrainSensitivityPoint(
      parameter_name=parameter_name,
      parameter_value=value,
      status=result.status,
      termination_reason=result.termination_reason.value,
      cell_count=result.cell_count,
      shock_train_end_x_m=result.shock_train_end_x_m,
      pressure_amplitude_final=(float(amplitudes[-1]) if amplitudes else None),
    ))
  ####
  return tuple(points)
####
