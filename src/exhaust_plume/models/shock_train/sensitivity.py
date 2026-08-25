"""Explicit closure-parameter sensitivity sweeps for the shock-train lane."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from exhaust_plume.models.shock_cells.contracts import ShockCellSolveResult
from exhaust_plume.models.shock_train.contracts import (
  ShockTrainCalibration,
  ShockTrainStatus,
  ShockTrainTerminationPolicy,
)
from exhaust_plume.models.shock_train.train import solve_shock_train

__all__ = ('ShockTrainSensitivityPoint', 'sweep_shock_train_parameter')


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
  if not values:
    raise ValueError('values must not be empty')
  points: list[ShockTrainSensitivityPoint] = []
  for value in values:
    value = float(value)
    if not isfinite(value) or value < 0.0:
      raise ValueError('sensitivity values must be finite and nonnegative')
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
  return tuple(points)
####
