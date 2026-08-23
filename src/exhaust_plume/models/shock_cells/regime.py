"""Explicit exit-to-ambient pressure-regime classification."""

from __future__ import annotations

from enum import Enum
from math import isfinite
from typing import Union

from exhaust_plume.models.nozzle.contracts import AmbientState, NozzleExitState
from exhaust_plume.util.aero.flow_state import FlowState

__all__ = ("ExpansionRegime", "classify_expansion_regime", "dimensionless_pressure_residual")
###########################################


class ExpansionRegime(str, Enum):
  MATCHED = "matched"
  UNDEREXPANDED = "underexpanded"
  OVEREXPANDED = "overexpanded"
  INVALID_EXIT_STATE = "invalid_exit_state"
  ####


def _pressure(value: Union[float, FlowState, NozzleExitState, AmbientState]) -> float:
  if isinstance(value, FlowState):
    return float(value.static_pressure)
  if isinstance(value, NozzleExitState):
    return float(value.static_pressure_Pa)
  if isinstance(value, AmbientState):
    return float(value.pressure_Pa)
  return float(value)
  ####


def dimensionless_pressure_residual(exit_pressure: float, ambient_pressure: float) -> float:
  """Return ``(p_exit - p_ambient) / p_ambient``."""

  exit_value = float(exit_pressure)
  ambient_value = float(ambient_pressure)
  if not isfinite(exit_value) or exit_value <= 0.0:
    raise ValueError("exit_pressure must be finite and positive")
  if not isfinite(ambient_value) or ambient_value <= 0.0:
    raise ValueError("ambient_pressure must be finite and positive")
  return (exit_value - ambient_value) / ambient_value
  ####


def classify_expansion_regime(exit_state: Union[FlowState, NozzleExitState, float], ambient: Union[AmbientState, float], *, pressure_match_rtol: float = 1.0e-4) -> ExpansionRegime:
  """Classify the exit pressure relative to the resolved ambient pressure."""

  if not isfinite(pressure_match_rtol) or pressure_match_rtol <= 0.0:
    raise ValueError("pressure_match_rtol must be finite and positive")
  try:
    residual = dimensionless_pressure_residual(_pressure(exit_state), _pressure(ambient))
  except (TypeError, ValueError):
    return ExpansionRegime.INVALID_EXIT_STATE
  if abs(residual) <= pressure_match_rtol:
    return ExpansionRegime.MATCHED
  if residual > 0.0:
    return ExpansionRegime.UNDEREXPANDED
  return ExpansionRegime.OVEREXPANDED
  ####
