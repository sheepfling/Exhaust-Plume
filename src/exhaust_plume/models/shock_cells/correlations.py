"""Correlation-only diagnostics for the reduced-order shock-cell lane."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt

from exhaust_plume.models.shock_cells.fully_expanded import (
  FullyExpandedJetResult,
  FullyExpandedStatus,
)

__all__ = (
  'FirstCellCorrelationStatus',
  'FirstCellCorrelationResult',
  'FirstCellComparisonResult',
  'prandtl_pack_first_cell_spacing',
  'compare_first_cell_length',
)


class FirstCellCorrelationStatus(str, Enum):
  """Outcome of a first-cell correlation comparison."""

  CONVERGED = 'converged'
  NO_FIRST_CELL_CLAIM = 'no_first_cell_claim'
  OUTSIDE_MODEL_VALIDITY = 'outside_model_validity'
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class FirstCellCorrelationResult:
  """Classical near-adapted circular-jet spacing comparison metric."""

  status: FirstCellCorrelationStatus
  coefficient: float
  fully_expanded_mach: float | None
  fully_expanded_diameter_m: float | None
  spacing_m: float | None
  message: str = ''

  @property
  def available(self) -> bool:
    return self.status is FirstCellCorrelationStatus.CONVERGED
  ####


@dataclass(frozen=True, slots=True)
class FirstCellComparisonResult:
  """Reported solver-versus-correlation error without imposing the metric."""

  status: FirstCellCorrelationStatus
  solver_length_m: float | None
  correlation_length_m: float | None
  relative_error: float | None
  message: str = ''

  @property
  def available(self) -> bool:
    return self.status is FirstCellCorrelationStatus.CONVERGED
  ####


def prandtl_pack_first_cell_spacing(
  fully_expanded: FullyExpandedJetResult,
  *,
  coefficient: float = 1.306,
) -> FirstCellCorrelationResult:
  r"""Return ``L_s = 1.306 D_j sqrt(M_j² - 1)`` as a comparison metric.

  The relation is deliberately not used to alter a solver mesh, close a
  characteristic zone, or infer a Mach disk.  Matched flow returns an explicit
  no-claim result.
  """

  if not isfinite(coefficient) or coefficient <= 0.0:
    raise ValueError('coefficient must be finite and positive')
  if fully_expanded.status is not FullyExpandedStatus.CONVERGED:
    return FirstCellCorrelationResult(
      status=FirstCellCorrelationStatus.OUTSIDE_MODEL_VALIDITY,
      coefficient=coefficient,
      fully_expanded_mach=fully_expanded.mach,
      fully_expanded_diameter_m=fully_expanded.diameter_m,
      spacing_m=None,
      message=fully_expanded.message or 'fully-expanded equivalent state is unavailable',
    )
  if not fully_expanded.first_cell_claim_allowed:
    return FirstCellCorrelationResult(
      status=FirstCellCorrelationStatus.NO_FIRST_CELL_CLAIM,
      coefficient=coefficient,
      fully_expanded_mach=fully_expanded.mach,
      fully_expanded_diameter_m=fully_expanded.diameter_m,
      spacing_m=None,
      message=fully_expanded.message or 'matched flow has no first-cell claim',
    )
  if fully_expanded.mach is None or fully_expanded.diameter_m is None:
    return FirstCellCorrelationResult(
      status=FirstCellCorrelationStatus.INVALID_INPUT,
      coefficient=coefficient,
      fully_expanded_mach=fully_expanded.mach,
      fully_expanded_diameter_m=fully_expanded.diameter_m,
      spacing_m=None,
      message='fully-expanded result is missing Mach or diameter',
    )
  ####
  radicand = fully_expanded.mach**2 - 1.0
  if radicand <= 0.0 or not isfinite(radicand):
    return FirstCellCorrelationResult(
      status=FirstCellCorrelationStatus.OUTSIDE_MODEL_VALIDITY,
      coefficient=coefficient,
      fully_expanded_mach=fully_expanded.mach,
      fully_expanded_diameter_m=fully_expanded.diameter_m,
      spacing_m=None,
      message='fully-expanded Mach number is not supersonic for the spacing correlation',
    )
  spacing_m = coefficient * fully_expanded.diameter_m * sqrt(radicand)
  if not isfinite(spacing_m) or spacing_m <= 0.0:
    return FirstCellCorrelationResult(
      status=FirstCellCorrelationStatus.INVALID_INPUT,
      coefficient=coefficient,
      fully_expanded_mach=fully_expanded.mach,
      fully_expanded_diameter_m=fully_expanded.diameter_m,
      spacing_m=None,
      message='correlation spacing is not finite and positive',
    )
  ####
  return FirstCellCorrelationResult(
    status=FirstCellCorrelationStatus.CONVERGED,
    coefficient=coefficient,
    fully_expanded_mach=fully_expanded.mach,
    fully_expanded_diameter_m=fully_expanded.diameter_m,
    spacing_m=spacing_m,
  )
####


def compare_first_cell_length(
  solver_length_m: float,
  correlation: FirstCellCorrelationResult,
) -> FirstCellComparisonResult:
  """Report relative error against a correlation without forcing agreement."""

  if not isfinite(solver_length_m) or solver_length_m <= 0.0:
    raise ValueError('solver_length_m must be finite and positive')
  if not correlation.available or correlation.spacing_m is None:
    return FirstCellComparisonResult(
      status=correlation.status,
      solver_length_m=solver_length_m,
      correlation_length_m=correlation.spacing_m,
      relative_error=None,
      message=correlation.message or 'correlation comparison is unavailable',
    )
  ####
  relative_error = (solver_length_m - correlation.spacing_m) / correlation.spacing_m
  return FirstCellComparisonResult(
    status=FirstCellCorrelationStatus.CONVERGED,
    solver_length_m=solver_length_m,
    correlation_length_m=correlation.spacing_m,
    relative_error=relative_error,
  )
####
