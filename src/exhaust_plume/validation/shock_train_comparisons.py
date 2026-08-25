"""Diagnostic operators for reduced-order shock-train feature comparisons.

The reduced-order shock-train solver emits cell lengths, while a centerline
pressure trace exposes extrema.  This module records a deliberately narrow
same-phase spacing diagnostic between those two representations.  It does not
fit an axial origin, assign a pressure extremum to a cell center, or establish
that the reduced-order cells are physical shock cells.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from typing import Any, Sequence


SHOCK_TRAIN_PRESSURE_EXTREMA_SPACING_OPERATOR_ID = (
  'op.reduce.pressure-extrema-spacing'
)


def _finite_nonnegative(name: str, value: float) -> float:
  value = float(value)
  if not isfinite(value) or value < 0.0:
    raise ValueError(f'{name} must be finite and nonnegative')
  return value


def _finite_positive(name: str, value: float) -> float:
  value = float(value)
  if not isfinite(value) or value <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  return value


@dataclass(frozen=True, slots=True)
class PressureExtremum:
  """One pressure-trace extremum in normalized axial coordinates."""

  kind: str
  x_over_D: float
  x_uncertainty_over_D: float | None = None

  def __post_init__(self) -> None:
    if self.kind not in ('minimum', 'maximum'):
      raise ValueError("kind must be 'minimum' or 'maximum'")
    object.__setattr__(self, 'x_over_D', _finite_nonnegative('x_over_D', self.x_over_D))
    if self.x_uncertainty_over_D is not None:
      object.__setattr__(
        self,
        'x_uncertainty_over_D',
        _finite_nonnegative('x_uncertainty_over_D', self.x_uncertainty_over_D),
      )
    ####
  ####


@dataclass(frozen=True, slots=True)
class ShockTrainSpacingComparison:
  """Non-accepting spacing residuals for one pressure-extremum phase."""

  status: str
  operator_id: str
  phase_kind: str
  model_cell_count: int
  observed_extrema_count: int
  matched_spacing_count: int
  model_spacing_over_D: tuple[float, ...]
  observed_spacing_over_D: tuple[float, ...]
  spacing_residuals_over_D: tuple[float, ...]
  observed_spacing_uncertainty_over_D: tuple[float | None, ...]
  rmse_over_D: float | None
  uncertainty_weighted_rmse: float | None
  claim_status: str
  reason: str

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible audit record."""

    return {
      'status': self.status,
      'operator_id': self.operator_id,
      'phase_kind': self.phase_kind,
      'model_cell_count': self.model_cell_count,
      'observed_extrema_count': self.observed_extrema_count,
      'observed_spacing_count': len(self.observed_spacing_over_D),
      'matched_spacing_count': self.matched_spacing_count,
      'model_spacing_over_D': list(self.model_spacing_over_D),
      'observed_spacing_over_D': list(self.observed_spacing_over_D),
      'spacing_residuals_over_D': list(self.spacing_residuals_over_D),
      'observed_spacing_uncertainty_over_D': list(
        self.observed_spacing_uncertainty_over_D
      ),
      'metrics': {
        'rmse_over_D': self.rmse_over_D,
        'uncertainty_weighted_rmse': self.uncertainty_weighted_rmse,
      },
      'claim_status': self.claim_status,
      'reason': self.reason,
    }
  ####


def _extrema_for_phase(
  observed_extrema: Sequence[PressureExtremum],
  phase_kind: str,
) -> tuple[PressureExtremum, ...]:
  if phase_kind not in ('minimum', 'maximum'):
    raise ValueError("phase_kind must be 'minimum' or 'maximum'")
  selected = tuple(
    extremum for extremum in observed_extrema if extremum.kind == phase_kind
  )
  ordered = tuple(sorted(selected, key=lambda extremum: extremum.x_over_D))
  if any(
      right.x_over_D <= left.x_over_D
      for left, right in zip(ordered, ordered[1:])
  ):
    raise ValueError('observed extrema must have unique axial positions within a phase')
  return ordered


def _spacing_uncertainty(
  left: PressureExtremum,
  right: PressureExtremum,
) -> float | None:
  if left.x_uncertainty_over_D is None or right.x_uncertainty_over_D is None:
    return None
  return sqrt(
    left.x_uncertainty_over_D ** 2 + right.x_uncertainty_over_D ** 2
  )


def compare_shock_train_pressure_extrema_spacing(
  cell_lengths_m: Sequence[float],
  exit_diameter_m: float,
  observed_extrema: Sequence[PressureExtremum],
  *,
  phase_kind: str,
) -> ShockTrainSpacingComparison:
  """Compare same-phase observed spacing with reduced-order cell lengths.

  The first observed same-phase interval is paired with the first model cell
  length, and so on.  No axial-origin fit or cell-center interpretation is
  performed.  Every result is marked ``not_accepted`` because this diagnostic
  does not identify physical shock-train cells.
  """

  diameter_m = _finite_positive('exit_diameter_m', exit_diameter_m)
  model_cells = tuple(
    _finite_positive('cell_lengths_m', length) for length in cell_lengths_m
  )
  model_spacing = tuple(length / diameter_m for length in model_cells)
  phase_extrema = _extrema_for_phase(observed_extrema, phase_kind)
  observed_spacing = tuple(
    right.x_over_D - left.x_over_D
    for left, right in zip(phase_extrema, phase_extrema[1:])
  )
  observed_uncertainty = tuple(
    _spacing_uncertainty(left, right)
    for left, right in zip(phase_extrema, phase_extrema[1:])
  )
  matched_count = min(len(model_spacing), len(observed_spacing))
  matched_model = model_spacing[:matched_count]
  matched_observed = observed_spacing[:matched_count]
  residuals = tuple(
    model - observed
    for model, observed in zip(matched_model, matched_observed)
  )
  rmse = (
    sqrt(fsum(residual * residual for residual in residuals) / matched_count)
    if matched_count
    else None
  )
  weighted_pairs = tuple(
    (residual, uncertainty)
    for residual, uncertainty in zip(
      residuals,
      observed_uncertainty[:matched_count],
    )
    if uncertainty is not None and uncertainty > 0.0
  )
  uncertainty_weighted_rmse = (
    sqrt(
      fsum((residual / uncertainty) ** 2 for residual, uncertainty in weighted_pairs)
      / len(weighted_pairs)
    )
    if weighted_pairs
    else None
  )
  if matched_count == 0:
    status = 'blocked-insufficient-extrema'
    reason = (
      f'phase {phase_kind!r} requires at least two observed extrema and one '
      'model cell length before a spacing diagnostic can be computed'
    )
  elif matched_count < len(observed_spacing) or matched_count < len(model_spacing):
    status = 'partial-diagnostic'
    reason = (
      'only the overlapping prefix of same-phase pressure-extrema spacing and '
      'reduced-order cell lengths was compared'
    )
  else:
    status = 'diagnostic-computed'
    reason = 'same-phase spacing was computed over the available model and observed ranges'
  return ShockTrainSpacingComparison(
    status=status,
    operator_id=SHOCK_TRAIN_PRESSURE_EXTREMA_SPACING_OPERATOR_ID,
    phase_kind=phase_kind,
    model_cell_count=len(model_cells),
    observed_extrema_count=len(phase_extrema),
    matched_spacing_count=matched_count,
    model_spacing_over_D=model_spacing,
    observed_spacing_over_D=observed_spacing,
    spacing_residuals_over_D=residuals,
    observed_spacing_uncertainty_over_D=observed_uncertainty,
    rmse_over_D=rmse,
    uncertainty_weighted_rmse=uncertainty_weighted_rmse,
    claim_status='not_accepted',
    reason=(
      f'{reason}; this diagnostic does not identify physical reduced-order '
      'train cells or establish a validated shock-cell measurement operator'
    ),
  )


__all__ = (
  'SHOCK_TRAIN_PRESSURE_EXTREMA_SPACING_OPERATOR_ID',
  'PressureExtremum',
  'ShockTrainSpacingComparison',
  'compare_shock_train_pressure_extrema_spacing',
)
