"""Validation operators for sectioned-tube visual feature comparisons.

The Mach-disk relation in the recovered corpus is an unordered, hysteretic
point cloud.  This module therefore requires an explicit branch identifier
from both model and observation records before it computes a pressure-to-
feature residual.  It never infers branches from row order, run names, or
pixel-cluster labels, and it never extrapolates outside a model branch's
pressure domain.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import fsum, isfinite, sqrt
from typing import Sequence


MACH_DISK_FEATURE_OPERATOR_ID = 'op.visual.feature-extractor'


@dataclass(frozen=True, slots=True)
class MachDiskPressureComparison:
  """Branch-aware pressure/feature residual and coverage diagnostics."""

  status: str
  model_point_count: int
  observed_point_count: int
  branch_count: int
  matched_point_count: int
  model_pressure_domain_bar: tuple[float, float] | None
  observed_pressure_domain_bar: tuple[float, float] | None
  position_rmse_m: float | None
  position_max_abs_error_m: float | None
  reason: str | None = None


def _axis(values: Sequence[float], field_name: str) -> tuple[float, ...]:
  axis = tuple(float(value) for value in values)
  if not axis or any(not isfinite(value) or value <= 0.0 for value in axis):
    raise ValueError(f'{field_name} must contain finite positive values')
  return axis


def _positions(values: Sequence[float], field_name: str) -> tuple[float, ...]:
  positions = tuple(float(value) for value in values)
  if not positions or any(not isfinite(value) or value < 0.0 for value in positions):
    raise ValueError(f'{field_name} must contain finite nonnegative values')
  return positions


def _branches(
    values: Sequence[str] | None,
    *,
    count: int,
    field_name: str,
) -> tuple[str, ...] | None:
  if values is None:
    return None
  branches = tuple(str(value) for value in values)
  if len(branches) != count or any(not value for value in branches):
    raise ValueError(f'{field_name} must contain one non-empty ID per point')
  return branches


def _domain(values: tuple[float, ...]) -> tuple[float, float]:
  return min(values), max(values)


def _blocked(
    *,
    status: str,
    model_point_count: int,
    observed_point_count: int,
    model_pressure_domain_bar: tuple[float, float] | None,
    observed_pressure_domain_bar: tuple[float, float] | None,
    reason: str,
    branch_count: int = 0,
    matched_point_count: int = 0,
) -> MachDiskPressureComparison:
  return MachDiskPressureComparison(
    status=status,
    model_point_count=model_point_count,
    observed_point_count=observed_point_count,
    branch_count=branch_count,
    matched_point_count=matched_point_count,
    model_pressure_domain_bar=model_pressure_domain_bar,
    observed_pressure_domain_bar=observed_pressure_domain_bar,
    position_rmse_m=None,
    position_max_abs_error_m=None,
    reason=reason,
  )


def _interpolate(
    pressure_bar: float,
    model_pressures: tuple[float, ...],
    model_positions: tuple[float, ...],
) -> float:
  if pressure_bar < model_pressures[0] or pressure_bar > model_pressures[-1]:
    raise ValueError('pressure is outside the model branch domain')
  if pressure_bar == model_pressures[0]:
    return model_positions[0]
  if pressure_bar == model_pressures[-1]:
    return model_positions[-1]
  upper = bisect_right(model_pressures, pressure_bar)
  lower = upper - 1
  fraction = (pressure_bar - model_pressures[lower]) / (
    model_pressures[upper] - model_pressures[lower]
  )
  return model_positions[lower] + fraction * (
    model_positions[upper] - model_positions[lower]
  )


def compare_mach_disk_pressure_relation(
    model_pressure_bar: Sequence[float],
    model_position_m: Sequence[float],
    observed_pressure_bar: Sequence[float],
    observed_position_m: Sequence[float],
    *,
    model_branch_ids: Sequence[str] | None = None,
    observed_branch_ids: Sequence[str] | None = None,
) -> MachDiskPressureComparison:
  """Compare a model feature against an explicitly branch-labeled point cloud.

  The returned ``partial-overlap-diagnostic`` status is not a full validation
  metric.  It is used when some observed branch points lie outside the model
  pressure domain.  A full metric is returned only when every observed point
  is interpolable within the matching model branch.
  """

  model_pressures = _axis(model_pressure_bar, 'model_pressure_bar')
  model_positions = _positions(model_position_m, 'model_position_m')
  observed_pressures = _axis(observed_pressure_bar, 'observed_pressure_bar')
  observed_positions = _positions(observed_position_m, 'observed_position_m')
  if len(model_pressures) != len(model_positions):
    raise ValueError('model pressure and position arrays must have matching lengths')
  if len(observed_pressures) != len(observed_positions):
    raise ValueError('observed pressure and position arrays must have matching lengths')
  model_domain = _domain(model_pressures)
  observed_domain = _domain(observed_pressures)
  model_branches = _branches(
    model_branch_ids,
    count=len(model_pressures),
    field_name='model_branch_ids',
  )
  observed_branches = _branches(
    observed_branch_ids,
    count=len(observed_pressures),
    field_name='observed_branch_ids',
  )
  if model_branches is None or observed_branches is None:
    return _blocked(
      status='branch-crosswalk-required',
      model_point_count=len(model_pressures),
      observed_point_count=len(observed_pressures),
      model_pressure_domain_bar=model_domain,
      observed_pressure_domain_bar=observed_domain,
      reason=(
        'unordered hysteretic feature data requires explicit model and observation '
        'branch IDs; row order, run ID, and pixel-cluster labels are not inferred'
      ),
    )
  model_by_branch: dict[str, list[tuple[float, float]]] = {}
  observed_by_branch: dict[str, list[tuple[float, float]]] = {}
  for pressure, position, branch in zip(model_pressures, model_positions, model_branches, strict=True):
    model_by_branch.setdefault(branch, []).append((pressure, position))
  for pressure, position, branch in zip(observed_pressures, observed_positions, observed_branches, strict=True):
    observed_by_branch.setdefault(branch, []).append((pressure, position))
  if set(model_by_branch) != set(observed_by_branch):
    return _blocked(
      status='branch-set-mismatch',
      model_point_count=len(model_pressures),
      observed_point_count=len(observed_pressures),
      model_pressure_domain_bar=model_domain,
      observed_pressure_domain_bar=observed_domain,
      branch_count=len(set(model_by_branch) & set(observed_by_branch)),
      reason='model and observation branch IDs do not have the same set',
    )
  residuals: list[float] = []
  matched_point_count = 0
  has_out_of_domain_observation = False
  for branch in sorted(model_by_branch):
    model_points = sorted(model_by_branch[branch])
    observed_points = observed_by_branch[branch]
    model_branch_pressures = tuple(point[0] for point in model_points)
    model_branch_positions = tuple(point[1] for point in model_points)
    if len(model_branch_pressures) < 2:
      return _blocked(
        status='insufficient-model-branch-samples',
        model_point_count=len(model_pressures),
        observed_point_count=len(observed_pressures),
        model_pressure_domain_bar=model_domain,
        observed_pressure_domain_bar=observed_domain,
        branch_count=len(model_by_branch),
        matched_point_count=matched_point_count,
        reason=f'model branch {branch!r} has fewer than two pressure samples',
      )
    if any(right <= left for left, right in zip(model_branch_pressures, model_branch_pressures[1:])):
      return _blocked(
        status='ambiguous-model-branch-pressure',
        model_point_count=len(model_pressures),
        observed_point_count=len(observed_pressures),
        model_pressure_domain_bar=model_domain,
        observed_pressure_domain_bar=observed_domain,
        branch_count=len(model_by_branch),
        matched_point_count=matched_point_count,
        reason=f'model branch {branch!r} contains duplicate pressure samples',
      )
    for pressure, observed_position in observed_points:
      if pressure < model_branch_pressures[0] or pressure > model_branch_pressures[-1]:
        has_out_of_domain_observation = True
        continue
      predicted_position = _interpolate(
        pressure,
        model_branch_pressures,
        model_branch_positions,
      )
      residuals.append(predicted_position - observed_position)
      matched_point_count += 1
  if not residuals:
    return _blocked(
      status='no-overlap',
      model_point_count=len(model_pressures),
      observed_point_count=len(observed_pressures),
      model_pressure_domain_bar=model_domain,
      observed_pressure_domain_bar=observed_domain,
      branch_count=len(model_by_branch),
      reason='no observed branch point lies inside its model pressure domain',
    )
  status = 'partial-overlap-diagnostic' if has_out_of_domain_observation else 'full-domain-computed'
  return MachDiskPressureComparison(
    status=status,
    model_point_count=len(model_pressures),
    observed_point_count=len(observed_pressures),
    branch_count=len(model_by_branch),
    matched_point_count=matched_point_count,
    model_pressure_domain_bar=model_domain,
    observed_pressure_domain_bar=observed_domain,
    position_rmse_m=sqrt(fsum(residual * residual for residual in residuals) / len(residuals)),
    position_max_abs_error_m=max(abs(residual) for residual in residuals),
    reason=(
      'some observed branch points lie outside the model pressure domain'
      if has_out_of_domain_observation else None
    ),
  )


__all__ = (
  'MACH_DISK_FEATURE_OPERATOR_ID',
  'MachDiskPressureComparison',
  'compare_mach_disk_pressure_relation',
)
