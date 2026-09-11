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

from exhaust_plume.contracts.common_v1 import canonical_digest


MACH_DISK_FEATURE_OPERATOR_ID = 'op.visual.feature-extractor'
VISUAL_FEATURE_SERIES_SCHEMA = 'exhaust-plume.visual-feature-series@1'
VISUAL_FEATURE_COMPARISON_OPERATOR_ID = 'op.visual.feature-series.no-extrapolation-v1'


def _nonempty_text(name: str, value: str) -> str:
  if not isinstance(value, str) or not value.strip():
    raise ValueError(f'{name} must be a non-empty string')
  ####
  return value.strip()
####


@dataclass(frozen=True, slots=True)
class VisualFeatureSeries:
  """One source-bound visual feature series ready for an explicit comparison.

  The series is intentionally more specific than a bare ``(x, y)`` array.
  Scenario, frame, measurement space, extraction operator, validity, and
  uncertainty metadata are part of the comparison contract.  Branch-labelled
  series may be unordered globally (for example a hysteretic feature cloud),
  but an unbranched series must declare an increasing coordinate axis.
  """

  feature_id: str
  coordinate_id: str
  coordinate_unit: str
  feature_unit: str
  coordinates: tuple[float, ...]
  values: tuple[float, ...]
  source_id: str
  scenario_id: str
  coordinate_frame_id: str
  measurement_space: str
  operator_id: str
  uncertainties: tuple[float, ...] | None = None
  validity_mask: tuple[bool, ...] | None = None
  branch_ids: tuple[str, ...] | None = None
  model_lane_id: str | None = None
  schema: str = VISUAL_FEATURE_SERIES_SCHEMA

  def __post_init__(self) -> None:
    if self.schema != VISUAL_FEATURE_SERIES_SCHEMA:
      raise ValueError(f'unsupported visual feature series schema: {self.schema!r}')
    ####
    for name in (
      'feature_id',
      'coordinate_id',
      'coordinate_unit',
      'feature_unit',
      'source_id',
      'scenario_id',
      'coordinate_frame_id',
      'measurement_space',
      'operator_id',
    ):
      object.__setattr__(self, name, _nonempty_text(name, getattr(self, name)))
    ####
    coordinates = tuple(float(value) for value in self.coordinates)
    values = tuple(float(value) for value in self.values)
    if not coordinates or len(coordinates) != len(values):
      raise ValueError('coordinates and values must be non-empty and have matching lengths')
    ####
    if any(not isfinite(value) for value in coordinates + values):
      raise ValueError('coordinates and values must be finite')
    ####
    uncertainties = self.uncertainties
    if uncertainties is not None:
      uncertainties = tuple(float(value) for value in uncertainties)
      if len(uncertainties) != len(values):
        raise ValueError('uncertainties must match the value count')
      ####
      if any(not isfinite(value) or value < 0.0 for value in uncertainties):
        raise ValueError('uncertainties must be finite and nonnegative')
      ####
    ####
    validity_mask = self.validity_mask
    if validity_mask is None:
      validity_mask = tuple(True for _ in values)
    else:
      validity_mask = tuple(bool(value) for value in validity_mask)
      if len(validity_mask) != len(values):
        raise ValueError('validity_mask must match the value count')
    ####
    branch_ids = self.branch_ids
    if branch_ids is not None:
      branch_ids = tuple(_nonempty_text('branch ID', value) for value in branch_ids)
      if len(branch_ids) != len(values):
        raise ValueError('branch_ids must match the value count')
    elif any(right <= left for left, right in zip(coordinates, coordinates[1:])):
      raise ValueError(
        'unbranched visual feature coordinates must be strictly increasing'
      )
    ####
    model_lane_id = self.model_lane_id
    if model_lane_id is not None:
      model_lane_id = _nonempty_text('model_lane_id', model_lane_id)
    ####
    object.__setattr__(self, 'coordinates', coordinates)
    object.__setattr__(self, 'values', values)
    object.__setattr__(self, 'uncertainties', uncertainties)
    object.__setattr__(self, 'validity_mask', validity_mask)
    object.__setattr__(self, 'branch_ids', branch_ids)
    object.__setattr__(self, 'model_lane_id', model_lane_id)
  ####

  def model_dump(self) -> dict[str, object]:
    """Return the portable source-bound series envelope."""

    return {
      'schema': self.schema,
      'feature_id': self.feature_id,
      'coordinate_id': self.coordinate_id,
      'coordinate_unit': self.coordinate_unit,
      'feature_unit': self.feature_unit,
      'coordinates': list(self.coordinates),
      'values': list(self.values),
      'source_id': self.source_id,
      'scenario_id': self.scenario_id,
      'coordinate_frame_id': self.coordinate_frame_id,
      'measurement_space': self.measurement_space,
      'operator_id': self.operator_id,
      'uncertainties': None if self.uncertainties is None else list(self.uncertainties),
      'validity_mask': list(self.validity_mask or ()),
      'branch_ids': None if self.branch_ids is None else list(self.branch_ids),
      'model_lane_id': self.model_lane_id,
    }
  ####

  def digest_sha256(self) -> str:
    """Return the deterministic identity of the complete feature envelope."""

    return canonical_digest(self.model_dump())
####


@dataclass(frozen=True, slots=True)
class VisualFeatureComparison:
  """Non-promoting residual and coverage report for two feature series."""

  schema: str
  operator_id: str
  status: str
  feature_id: str
  coordinate_id: str
  model_source_id: str
  observed_source_id: str
  scenario_id: str
  coordinate_frame_id: str
  measurement_space: str
  model_point_count: int
  observed_point_count: int
  branch_count: int
  matched_point_count: int
  model_domain: tuple[float, float] | None
  observed_domain: tuple[float, float] | None
  coverage_fraction: float
  value_rmse: float | None
  value_max_abs_error: float | None
  uncertainty_coverage_fraction: float
  uncertainty_normalized_rmse: float | None
  uncertainty_max_normalized_error: float | None
  reason: str | None = None

  def model_dump(self) -> dict[str, object]:
    return {
      'schema': self.schema,
      'operator_id': self.operator_id,
      'status': self.status,
      'feature_id': self.feature_id,
      'coordinate_id': self.coordinate_id,
      'model_source_id': self.model_source_id,
      'observed_source_id': self.observed_source_id,
      'scenario_id': self.scenario_id,
      'coordinate_frame_id': self.coordinate_frame_id,
      'measurement_space': self.measurement_space,
      'model_point_count': self.model_point_count,
      'observed_point_count': self.observed_point_count,
      'branch_count': self.branch_count,
      'matched_point_count': self.matched_point_count,
      'model_domain': self.model_domain,
      'observed_domain': self.observed_domain,
      'coverage_fraction': self.coverage_fraction,
      'value_rmse': self.value_rmse,
      'value_max_abs_error': self.value_max_abs_error,
      'uncertainty_coverage_fraction': self.uncertainty_coverage_fraction,
      'uncertainty_normalized_rmse': self.uncertainty_normalized_rmse,
      'uncertainty_max_normalized_error': self.uncertainty_max_normalized_error,
      'reason': self.reason,
      'claim_status': 'diagnostic-only',
      'guardrails': [
        'no-extrapolation',
        'no-implicit-frame-transform',
        'no-row-order-or-branch-inference',
        'comparison-is-not-external-validation-evidence',
      ],
    }
####


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
####


def _axis(values: Sequence[float], field_name: str) -> tuple[float, ...]:
  axis = tuple(float(value) for value in values)
  if not axis or any(not isfinite(value) or value <= 0.0 for value in axis):
    raise ValueError(f'{field_name} must contain finite positive values')
  ####
  return axis
####


def _positions(values: Sequence[float], field_name: str) -> tuple[float, ...]:
  positions = tuple(float(value) for value in values)
  if not positions or any(not isfinite(value) or value < 0.0 for value in positions):
    raise ValueError(f'{field_name} must contain finite nonnegative values')
  ####
  return positions
####


def _branches(
    values: Sequence[str] | None,
    *,
    count: int,
    field_name: str,
) -> tuple[str, ...] | None:
  if values is None:
    return None
  ####
  branches = tuple(str(value) for value in values)
  if len(branches) != count or any(not value for value in branches):
    raise ValueError(f'{field_name} must contain one non-empty ID per point')
  ####
  return branches
####


def _domain(values: tuple[float, ...]) -> tuple[float, float]:
  return min(values), max(values)
####


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
####


def _interpolate(
  pressure_bar: float,
  model_pressures: tuple[float, ...],
  model_positions: tuple[float, ...],
) -> float:
  if pressure_bar < model_pressures[0] or pressure_bar > model_pressures[-1]:
    raise ValueError('pressure is outside the model branch domain')
  ####
  if pressure_bar == model_pressures[0]:
    return model_positions[0]
  ####
  if pressure_bar == model_pressures[-1]:
    return model_positions[-1]
  ####
  upper = bisect_right(model_pressures, pressure_bar)
  lower = upper - 1
  fraction = (pressure_bar - model_pressures[lower]) / (
    model_pressures[upper] - model_pressures[lower]
  )
  return model_positions[lower] + fraction * (
    model_positions[upper] - model_positions[lower]
  )
####


def _series_domain(series: VisualFeatureSeries) -> tuple[float, float] | None:
  valid_coordinates = tuple(
    coordinate
    for coordinate, valid in zip(series.coordinates, series.validity_mask or (), strict=True)
    if valid
  )
  return None if not valid_coordinates else (min(valid_coordinates), max(valid_coordinates))
####


def _feature_blocked(
  model: VisualFeatureSeries,
  observed: VisualFeatureSeries,
  *,
  status: str,
  reason: str,
  matched_point_count: int = 0,
  model_domain: tuple[float, float] | None = None,
  observed_domain: tuple[float, float] | None = None,
  branch_count: int = 0,
) -> VisualFeatureComparison:
  return VisualFeatureComparison(
    schema=VISUAL_FEATURE_SERIES_SCHEMA,
    operator_id=VISUAL_FEATURE_COMPARISON_OPERATOR_ID,
    status=status,
    feature_id=model.feature_id,
    coordinate_id=model.coordinate_id,
    model_source_id=model.source_id,
    observed_source_id=observed.source_id,
    scenario_id=model.scenario_id,
    coordinate_frame_id=model.coordinate_frame_id,
    measurement_space=model.measurement_space,
    model_point_count=len(model.coordinates),
    observed_point_count=len(observed.coordinates),
    branch_count=branch_count,
    matched_point_count=matched_point_count,
    model_domain=model_domain,
    observed_domain=observed_domain,
    coverage_fraction=0.0,
    value_rmse=None,
    value_max_abs_error=None,
    uncertainty_coverage_fraction=0.0,
    uncertainty_normalized_rmse=None,
    uncertainty_max_normalized_error=None,
    reason=reason,
  )
####


def compare_visual_feature_series(
  model: VisualFeatureSeries,
  observed: VisualFeatureSeries,
) -> VisualFeatureComparison:
  """Compare one model feature series with one observation series.

  Both series must already occupy the same scenario, frame, coordinate
  semantics, units, and measurement space.  Model values are linearly
  interpolated only inside each explicitly declared model branch; no global
  row-order, branch, frame, or endpoint inference is performed.  The result
  is always a diagnostic and cannot by itself create a validation claim.
  """

  if not isinstance(model, VisualFeatureSeries) or not isinstance(observed, VisualFeatureSeries):
    raise TypeError('model and observed must be VisualFeatureSeries values')
  ####
  contract_pairs = (
    ('feature_id', model.feature_id, observed.feature_id),
    ('coordinate_id', model.coordinate_id, observed.coordinate_id),
    ('coordinate_unit', model.coordinate_unit, observed.coordinate_unit),
    ('feature_unit', model.feature_unit, observed.feature_unit),
    ('scenario_id', model.scenario_id, observed.scenario_id),
    ('coordinate_frame_id', model.coordinate_frame_id, observed.coordinate_frame_id),
    ('measurement_space', model.measurement_space, observed.measurement_space),
  )
  mismatches = tuple(
    f'{field_name} differs ({left!r} != {right!r})'
    for field_name, left, right in contract_pairs
    if left != right
  )
  model_domain = _series_domain(model)
  observed_domain = _series_domain(observed)
  if mismatches:
    return _feature_blocked(
      model,
      observed,
      status='blocked-incompatible-contract',
      reason='; '.join(mismatches) + '; an explicit operator or frame transform is required',
      model_domain=model_domain,
      observed_domain=observed_domain,
    )
  ####
  if model.branch_ids is None or observed.branch_ids is None:
    if model.branch_ids != observed.branch_ids:
      return _feature_blocked(
        model,
        observed,
        status='branch-crosswalk-required',
        reason=(
          'unordered or hysteretic visual feature data requires explicit branch IDs '
          'on both model and observation series; row order is not inferred'
        ),
        model_domain=model_domain,
        observed_domain=observed_domain,
      )
    ####
    model_branch_ids = tuple('default' for _ in model.coordinates)
    observed_branch_ids = tuple('default' for _ in observed.coordinates)
  else:
    model_branch_ids = model.branch_ids
    observed_branch_ids = observed.branch_ids
  ####
  model_by_branch: dict[str, list[tuple[float, float, float | None]]] = {}
  observed_by_branch: dict[str, list[tuple[float, float, float | None]]] = {}
  model_uncertainties = model.uncertainties
  observed_uncertainties = observed.uncertainties
  for index, (coordinate, value, branch, valid) in enumerate(zip(
    model.coordinates,
    model.values,
    model_branch_ids,
    model.validity_mask or (),
    strict=True,
  )):
    if valid:
      model_by_branch.setdefault(branch, []).append((
        coordinate,
        value,
        None if model_uncertainties is None else model_uncertainties[index],
      ))
    ####
  ####
  for index, (coordinate, value, branch, valid) in enumerate(zip(
    observed.coordinates,
    observed.values,
    observed_branch_ids,
    observed.validity_mask or (),
    strict=True,
  )):
    if valid:
      observed_by_branch.setdefault(branch, []).append((
        coordinate,
        value,
        None if observed_uncertainties is None else observed_uncertainties[index],
      ))
    ####
  ####
  if set(model_by_branch) != set(observed_by_branch):
    return _feature_blocked(
      model,
      observed,
      status='branch-set-mismatch',
      reason='model and observation branch IDs do not have the same set',
      model_domain=model_domain,
      observed_domain=observed_domain,
      branch_count=len(set(model_by_branch) & set(observed_by_branch)),
    )
  ####
  residuals: list[float] = []
  normalized_residuals: list[float] = []
  matched_point_count = 0
  observed_valid_count = sum(len(points) for points in observed_by_branch.values())
  has_out_of_domain_observation = False
  for branch in sorted(model_by_branch):
    model_points = sorted(model_by_branch[branch])
    observed_points = observed_by_branch[branch]
    model_coordinates = tuple(point[0] for point in model_points)
    model_values = tuple(point[1] for point in model_points)
    model_branch_uncertainties = tuple(point[2] for point in model_points)
    if len(model_coordinates) < 2:
      return _feature_blocked(
        model,
        observed,
        status='insufficient-model-branch-samples',
        reason=f'model branch {branch!r} has fewer than two valid coordinate samples',
        matched_point_count=matched_point_count,
        model_domain=model_domain,
        observed_domain=observed_domain,
        branch_count=len(model_by_branch),
      )
    ####
    if any(right <= left for left, right in zip(model_coordinates, model_coordinates[1:])):
      return _feature_blocked(
        model,
        observed,
        status='ambiguous-model-branch-coordinate',
        reason=f'model branch {branch!r} contains duplicate or unordered coordinates',
        matched_point_count=matched_point_count,
        model_domain=model_domain,
        observed_domain=observed_domain,
        branch_count=len(model_by_branch),
      )
    ####
    for coordinate, observed_value, observed_uncertainty in observed_points:
      if coordinate < model_coordinates[0] or coordinate > model_coordinates[-1]:
        has_out_of_domain_observation = True
        continue
      ####
      predicted_value = _interpolate(coordinate, model_coordinates, model_values)
      residual = predicted_value - observed_value
      residuals.append(residual)
      matched_point_count += 1
      non_null_model_uncertainties = tuple(
        value for value in model_branch_uncertainties if value is not None
      )
      model_uncertainty = (
        _interpolate(coordinate, model_coordinates, non_null_model_uncertainties)
        if len(non_null_model_uncertainties) == len(model_branch_uncertainties)
        else None
      )
      if model_uncertainty is not None and observed_uncertainty is not None:
        combined_uncertainty = sqrt(
          model_uncertainty * model_uncertainty
          + observed_uncertainty * observed_uncertainty
        )
        if combined_uncertainty > 0.0:
          normalized_residuals.append(abs(residual) / combined_uncertainty)
        ####
      ####
    ####
  ####
  if not residuals:
    return _feature_blocked(
      model,
      observed,
      status='no-overlap',
      reason='no valid observed branch point lies inside its model coordinate domain',
      model_domain=model_domain,
      observed_domain=observed_domain,
      branch_count=len(model_by_branch),
    )
  ####
  return VisualFeatureComparison(
    schema=VISUAL_FEATURE_SERIES_SCHEMA,
    operator_id=VISUAL_FEATURE_COMPARISON_OPERATOR_ID,
    status='partial-overlap-diagnostic' if has_out_of_domain_observation else 'full-domain-computed',
    feature_id=model.feature_id,
    coordinate_id=model.coordinate_id,
    model_source_id=model.source_id,
    observed_source_id=observed.source_id,
    scenario_id=model.scenario_id,
    coordinate_frame_id=model.coordinate_frame_id,
    measurement_space=model.measurement_space,
    model_point_count=len(model.coordinates),
    observed_point_count=len(observed.coordinates),
    branch_count=len(model_by_branch),
    matched_point_count=matched_point_count,
    model_domain=model_domain,
    observed_domain=observed_domain,
    coverage_fraction=(matched_point_count / observed_valid_count) if observed_valid_count else 0.0,
    value_rmse=sqrt(fsum(residual * residual for residual in residuals) / len(residuals)),
    value_max_abs_error=max(abs(residual) for residual in residuals),
    uncertainty_coverage_fraction=(len(normalized_residuals) / matched_point_count),
    uncertainty_normalized_rmse=(
      sqrt(fsum(value * value for value in normalized_residuals) / len(normalized_residuals))
      if normalized_residuals else None
    ),
    uncertainty_max_normalized_error=max(normalized_residuals) if normalized_residuals else None,
    reason=(
      'some valid observed branch points lie outside the model coordinate domain'
      if has_out_of_domain_observation else None
    ),
  )
####


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
  ####
  if len(observed_pressures) != len(observed_positions):
    raise ValueError('observed pressure and position arrays must have matching lengths')
  ####
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
  ####
  model_by_branch: dict[str, list[tuple[float, float]]] = {}
  observed_by_branch: dict[str, list[tuple[float, float]]] = {}
  for pressure, position, branch in zip(model_pressures, model_positions, model_branches, strict=True):
    model_by_branch.setdefault(branch, []).append((pressure, position))
  ####
  for pressure, position, branch in zip(observed_pressures, observed_positions, observed_branches, strict=True):
    observed_by_branch.setdefault(branch, []).append((pressure, position))
  ####
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
  ####
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
    ####
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
    ####
    for pressure, observed_position in observed_points:
      if pressure < model_branch_pressures[0] or pressure > model_branch_pressures[-1]:
        has_out_of_domain_observation = True
        continue
      ####
      predicted_position = _interpolate(
        pressure,
        model_branch_pressures,
        model_branch_positions,
      )
      residuals.append(predicted_position - observed_position)
      matched_point_count += 1
    ####
  ####
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
  ####
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
####


__all__ = (
  'MACH_DISK_FEATURE_OPERATOR_ID',
  'MachDiskPressureComparison',
  'VISUAL_FEATURE_COMPARISON_OPERATOR_ID',
  'VISUAL_FEATURE_SERIES_SCHEMA',
  'VisualFeatureComparison',
  'VisualFeatureSeries',
  'compare_mach_disk_pressure_relation',
  'compare_visual_feature_series',
)
