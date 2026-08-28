"""Non-accepting external observation comparisons for continued MOC chains.

The solver and geometry measurement operators remain the source of model
values.  This module only aligns a supplied, indexed external observation set
with an already measured shock-cell chain.  It never fits an axial origin,
fills a missing cell, interpolates a feature, or promotes a product claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import fsum, isfinite, sqrt
from typing import Any, Sequence

from exhaust_plume.validation.moc_measurements import (
  MocShockCellChainMeasurement,
  MocShockCellMeasurement,
)


MOC_SHOCK_CELL_EXTERNAL_COMPARISON_OPERATOR_ID = (
  'op.moc.shock-cell-external-comparison'
)


class MocExternalValidationSplit(str, Enum):
  """Role of one external observation case in the validation study."""

  CALIBRATION = 'calibration'
  VALIDATION = 'validation'
  ####


class MocShockCellExternalFeature(str, Enum):
  """Scalar shock-cell features supported by the first external adapter."""

  AXIAL_LENGTH_M = 'axial_length_m'
  MAXIMUM_RADIUS_M = 'maximum_radius_m'
  SHOCK_START_X_M = 'shock_start_x_m'
  SHOCK_END_X_M = 'shock_end_x_m'
  CENTERLINE_END_X_M = 'centerline_end_x_m'
  ####


class MocShockCellExternalComparisonStatus(str, Enum):
  """Outcome of an indexed external shock-cell comparison."""

  FULL_DOMAIN_COMPUTED = 'full-domain-computed'
  PARTIAL_DIAGNOSTIC = 'partial-diagnostic'
  BLOCKED_MODEL_MEASUREMENT = 'blocked-model-measurement'
  BLOCKED_COORDINATE_METADATA = 'blocked-coordinate-metadata'
  BLOCKED_NO_OVERLAP = 'blocked-no-overlap'
  BLOCKED_NO_COMMON_FEATURE = 'blocked-no-common-feature'
  ####


class MocExternalValidationSplitAuditStatus(str, Enum):
  """Outcome of the calibration/validation case split audit."""

  VERIFIED = 'split-verified'
  INVALID_INPUT = 'invalid_input'
  MISSING_SPLIT = 'blocked-missing-split'
  DUPLICATE_DATASET = 'blocked-duplicate-dataset'
  CASE_OVERLAP = 'blocked-case-overlap'
  ####


def _nonempty_text(name: str, value: str) -> str:
  if not isinstance(value, str) or not value.strip():
    raise ValueError(f'{name} must be a non-empty string')
  return value.strip()


def _finite_optional(
  name: str,
  value: float | None,
  *,
  nonnegative: bool = False,
) -> float | None:
  if value is None:
    return None
  resolved = float(value)
  if not isfinite(resolved):
    raise ValueError(f'{name} must be finite when supplied')
  if nonnegative and resolved < 0.0:
    raise ValueError(f'{name} must be nonnegative when supplied')
  return resolved


_FEATURE_FIELDS = tuple(feature.value for feature in MocShockCellExternalFeature)
_UNCERTAINTY_FIELDS = tuple(
  f'{feature.value.removesuffix("_m")}_uncertainty_m'
  for feature in MocShockCellExternalFeature
)


@dataclass(frozen=True, slots=True)
class MocShockCellExternalObservation:
  """Indexed external geometry for one observed shock cell.

  All coordinates and lengths use metres in the declared axial/transverse
  frame.  A record may contain any non-empty subset of the supported scalar
  features, but no feature is synthesized from another feature.
  """

  cell_index: int
  axial_length_m: float | None = None
  maximum_radius_m: float | None = None
  shock_start_x_m: float | None = None
  shock_end_x_m: float | None = None
  centerline_end_x_m: float | None = None
  axial_length_uncertainty_m: float | None = None
  maximum_radius_uncertainty_m: float | None = None
  shock_start_x_uncertainty_m: float | None = None
  shock_end_x_uncertainty_m: float | None = None
  centerline_end_x_uncertainty_m: float | None = None

  def __post_init__(self) -> None:
    if isinstance(self.cell_index, bool) or not isinstance(self.cell_index, int):
      raise TypeError('cell_index must be an integer')
    if self.cell_index < 1:
      raise ValueError('cell_index must be positive')
    for name in _FEATURE_FIELDS:
      nonnegative = name in ('axial_length_m', 'maximum_radius_m')
      object.__setattr__(
        self,
        name,
        _finite_optional(name, getattr(self, name), nonnegative=nonnegative),
      )
    for name in _UNCERTAINTY_FIELDS:
      object.__setattr__(
        self,
        name,
        _finite_optional(name, getattr(self, name), nonnegative=True),
      )
    for feature_name, uncertainty_name in zip(
      _FEATURE_FIELDS,
      _UNCERTAINTY_FIELDS,
      strict=True,
    ):
      if (
        getattr(self, feature_name) is None
        and getattr(self, uncertainty_name) is not None
      ):
        raise ValueError(
          f'{uncertainty_name} cannot be supplied without {feature_name}'
        )
    if not any(getattr(self, name) is not None for name in _FEATURE_FIELDS):
      raise ValueError('at least one external shock-cell feature is required')
    ####

  def value_for(self, feature: MocShockCellExternalFeature) -> float | None:
    """Return the supplied scalar for ``feature`` without deriving it."""

    if not isinstance(feature, MocShockCellExternalFeature):
      raise TypeError('feature must be a MocShockCellExternalFeature')
    return getattr(self, feature.value)
  ####

  def uncertainty_for(
    self,
    feature: MocShockCellExternalFeature,
  ) -> float | None:
    """Return the optional one-sigma uncertainty for ``feature``."""

    if not isinstance(feature, MocShockCellExternalFeature):
      raise TypeError('feature must be a MocShockCellExternalFeature')
    return getattr(self, f'{feature.value.removesuffix("_m")}_uncertainty_m')
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellExternalDataset:
  """One externally sourced case with an explicit calibration role."""

  dataset_id: str
  case_id: str
  split: MocExternalValidationSplit
  observations: tuple[MocShockCellExternalObservation, ...]
  source: str
  provenance: str
  coordinate_frame: str = 'axial-transverse-m'
  units: str = 'm'

  def __post_init__(self) -> None:
    object.__setattr__(self, 'dataset_id', _nonempty_text('dataset_id', self.dataset_id))
    object.__setattr__(self, 'case_id', _nonempty_text('case_id', self.case_id))
    object.__setattr__(self, 'source', _nonempty_text('source', self.source))
    object.__setattr__(
      self,
      'provenance',
      _nonempty_text('provenance', self.provenance),
    )
    object.__setattr__(
      self,
      'coordinate_frame',
      _nonempty_text('coordinate_frame', self.coordinate_frame),
    )
    object.__setattr__(self, 'units', _nonempty_text('units', self.units))
    if not isinstance(self.split, MocExternalValidationSplit):
      raise TypeError('split must be a MocExternalValidationSplit')
    observations = tuple(self.observations)
    if not observations:
      raise ValueError('observations must contain at least one external cell')
    if any(
      not isinstance(observation, MocShockCellExternalObservation)
      for observation in observations
    ):
      raise TypeError(
        'observations must contain MocShockCellExternalObservation values'
      )
    indices = tuple(observation.cell_index for observation in observations)
    if len(set(indices)) != len(indices):
      raise ValueError('observations must have unique cell indices')
    object.__setattr__(self, 'observations', observations)
    ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible external dataset manifest."""

    return {
      'dataset_id': self.dataset_id,
      'case_id': self.case_id,
      'split': self.split.value,
      'source': self.source,
      'provenance': self.provenance,
      'coordinate_frame': self.coordinate_frame,
      'units': self.units,
      'cell_indices': [observation.cell_index for observation in self.observations],
      'observations': [
        {
          feature.value: observation.value_for(feature)
          for feature in MocShockCellExternalFeature
          if observation.value_for(feature) is not None
        }
        | {
          f'{feature.value.removesuffix("_m")}_uncertainty_m': observation.uncertainty_for(feature)
          for feature in MocShockCellExternalFeature
          if observation.uncertainty_for(feature) is not None
        }
        | {'cell_index': observation.cell_index}
        for observation in self.observations
      ],
    }
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellExternalFeatureComparison:
  """Residuals for one feature over the exact overlapping cell indices."""

  feature: MocShockCellExternalFeature
  matched_cell_indices: tuple[int, ...]
  model_values_m: tuple[float, ...]
  observed_values_m: tuple[float, ...]
  observed_uncertainties_m: tuple[float | None, ...]
  residuals_m: tuple[float, ...]
  rmse_m: float
  uncertainty_weighted_rmse: float | None

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible feature comparison."""

    return {
      'feature': self.feature.value,
      'matched_cell_indices': list(self.matched_cell_indices),
      'model_values_m': list(self.model_values_m),
      'observed_values_m': list(self.observed_values_m),
      'observed_uncertainties_m': list(self.observed_uncertainties_m),
      'residuals_m': list(self.residuals_m),
      'rmse_m': self.rmse_m,
      'uncertainty_weighted_rmse': self.uncertainty_weighted_rmse,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocShockCellExternalComparison:
  """Non-accepting comparison between a measured chain and one dataset."""

  status: MocShockCellExternalComparisonStatus
  operator_id: str
  dataset_id: str
  case_id: str
  split: MocExternalValidationSplit
  model_cell_count: int
  observed_cell_count: int
  matched_cell_count: int
  model_cell_indices: tuple[int, ...]
  observed_cell_indices: tuple[int, ...]
  matched_cell_indices: tuple[int, ...]
  feature_comparisons: tuple[MocShockCellExternalFeatureComparison, ...]
  claim_status: str
  reason: str

  @property
  def computed(self) -> bool:
    """Whether at least one external feature residual was computed."""

    return bool(self.feature_comparisons)
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible comparison record."""

    model_count = self.model_cell_count
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'dataset_id': self.dataset_id,
      'case_id': self.case_id,
      'split': self.split.value,
      'cell_coverage': {
        'model_cell_count': model_count,
        'observed_cell_count': self.observed_cell_count,
        'matched_cell_count': self.matched_cell_count,
        'fraction_of_model_cells': (
          self.matched_cell_count / model_count if model_count else 0.0
        ),
        'model_cell_indices': list(self.model_cell_indices),
        'observed_cell_indices': list(self.observed_cell_indices),
        'matched_cell_indices': list(self.matched_cell_indices),
      },
      'features': [
        comparison.as_report()
        for comparison in self.feature_comparisons
      ],
      'claim_status': self.claim_status,
      'reason': self.reason,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocExternalValidationSplitAudit:
  """Audit proving that calibration and validation cases are disjoint."""

  status: MocExternalValidationSplitAuditStatus
  dataset_count: int
  calibration_case_ids: tuple[str, ...]
  validation_case_ids: tuple[str, ...]
  duplicate_dataset_ids: tuple[str, ...]
  overlapping_case_ids: tuple[str, ...]
  claim_status: str
  message: str

  @property
  def verified(self) -> bool:
    """Whether both roles exist and no case crosses the split boundary."""

    return self.status is MocExternalValidationSplitAuditStatus.VERIFIED
  ####

  def as_report(self) -> dict[str, Any]:
    """Return a JSON-compatible split audit."""

    return {
      'status': self.status.value,
      'dataset_count': self.dataset_count,
      'calibration_case_ids': list(self.calibration_case_ids),
      'validation_case_ids': list(self.validation_case_ids),
      'duplicate_dataset_ids': list(self.duplicate_dataset_ids),
      'overlapping_case_ids': list(self.overlapping_case_ids),
      'verified': self.verified,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####


def _model_feature_value(
  measurement: MocShockCellMeasurement,
  feature: MocShockCellExternalFeature,
) -> float | None:
  if feature is MocShockCellExternalFeature.AXIAL_LENGTH_M:
    return measurement.axial_length_m
  if feature is MocShockCellExternalFeature.MAXIMUM_RADIUS_M:
    return measurement.maximum_radius_m
  point: tuple[float, float] | None
  if feature is MocShockCellExternalFeature.SHOCK_START_X_M:
    point = measurement.shock_start_m
  elif feature is MocShockCellExternalFeature.SHOCK_END_X_M:
    point = measurement.shock_end_m
  else:
    point = measurement.centerline_end_m
  return None if point is None else point[0]


def _feature_comparison(
  feature: MocShockCellExternalFeature,
  measurements: dict[int, MocShockCellMeasurement],
  observations: dict[int, MocShockCellExternalObservation],
  matched_indices: Sequence[int],
) -> MocShockCellExternalFeatureComparison | None:
  pairs = []
  for cell_index in matched_indices:
    model_value = _model_feature_value(measurements[cell_index], feature)
    observed_value = observations[cell_index].value_for(feature)
    if model_value is None or observed_value is None or not isfinite(model_value):
      continue
    pairs.append((
      cell_index,
      float(model_value),
      float(observed_value),
      observations[cell_index].uncertainty_for(feature),
    ))
  if not pairs:
    return None
  indices = tuple(pair[0] for pair in pairs)
  model_values = tuple(pair[1] for pair in pairs)
  observed_values = tuple(pair[2] for pair in pairs)
  uncertainties = tuple(pair[3] for pair in pairs)
  residuals = tuple(
    model - observed
    for model, observed in zip(model_values, observed_values, strict=True)
  )
  rmse = sqrt(fsum(residual * residual for residual in residuals) / len(residuals))
  weighted_residuals = tuple(
    residual / uncertainty
    for residual, uncertainty in zip(residuals, uncertainties, strict=True)
    if uncertainty is not None and uncertainty > 0.0
  )
  weighted_rmse = (
    sqrt(fsum(value * value for value in weighted_residuals) / len(weighted_residuals))
    if weighted_residuals
    else None
  )
  return MocShockCellExternalFeatureComparison(
    feature=feature,
    matched_cell_indices=indices,
    model_values_m=model_values,
    observed_values_m=observed_values,
    observed_uncertainties_m=uncertainties,
    residuals_m=residuals,
    rmse_m=rmse,
    uncertainty_weighted_rmse=weighted_rmse,
  )


def compare_moc_shock_cell_chain_to_external(
  chain_measurement: MocShockCellChainMeasurement,
  dataset: MocShockCellExternalDataset,
) -> MocShockCellExternalComparison:
  """Compare indexed chain geometry with supplied external observations.

  Cell indices are the only association key.  Exact index coverage produces a
  full-domain diagnostic; an overlapping prefix or subset produces a partial
  diagnostic.  Missing cells, coordinate metadata mismatches, and unavailable
  model features are reported as blocked or partial rather than being filled
  by interpolation or extrapolation.
  """

  if not isinstance(chain_measurement, MocShockCellChainMeasurement):
    raise TypeError(
      'chain_measurement must be a MocShockCellChainMeasurement'
    )
  if not isinstance(dataset, MocShockCellExternalDataset):
    raise TypeError('dataset must be a MocShockCellExternalDataset')
  model_indices = tuple(sorted(cell.cell_index for cell in chain_measurement.cells))
  observed_indices = tuple(
    sorted(observation.cell_index for observation in dataset.observations)
  )
  matched_indices = tuple(sorted(set(model_indices) & set(observed_indices)))
  base = {
    'operator_id': MOC_SHOCK_CELL_EXTERNAL_COMPARISON_OPERATOR_ID,
    'dataset_id': dataset.dataset_id,
    'case_id': dataset.case_id,
    'split': dataset.split,
    'model_cell_count': len(model_indices),
    'observed_cell_count': len(observed_indices),
    'matched_cell_count': len(matched_indices),
    'model_cell_indices': model_indices,
    'observed_cell_indices': observed_indices,
    'matched_cell_indices': matched_indices,
    'feature_comparisons': (),
    'claim_status': 'not_accepted',
  }
  if not chain_measurement.converged:
    return MocShockCellExternalComparison(
      status=MocShockCellExternalComparisonStatus.BLOCKED_MODEL_MEASUREMENT,
      reason=(
        'the measured chain is not converged; external residuals were not '
        'computed from a failed or incomplete model chain'
      ),
      **base,
    )
  if dataset.coordinate_frame != 'axial-transverse-m' or dataset.units != 'm':
    return MocShockCellExternalComparison(
      status=MocShockCellExternalComparisonStatus.BLOCKED_COORDINATE_METADATA,
      reason=(
        'the external adapter accepts only axial-transverse-m coordinates and '
        'metres; no coordinate conversion or normalization is performed'
      ),
      **base,
    )
  if not matched_indices:
    return MocShockCellExternalComparison(
      status=MocShockCellExternalComparisonStatus.BLOCKED_NO_OVERLAP,
      reason=(
        'external observations do not overlap the measured chain cell indices; '
        'no cell alignment or extrapolation was attempted'
      ),
      **base,
    )
  measurements = {cell.cell_index: cell for cell in chain_measurement.cells}
  observations = {
    observation.cell_index: observation
    for observation in dataset.observations
  }
  comparisons = tuple(
    comparison
    for feature in MocShockCellExternalFeature
    if (
      comparison := _feature_comparison(
        feature,
        measurements,
        observations,
        matched_indices,
      )
    ) is not None
  )
  if not comparisons:
    return MocShockCellExternalComparison(
      status=MocShockCellExternalComparisonStatus.BLOCKED_NO_COMMON_FEATURE,
      reason=(
        'overlapping cell indices contain no feature supplied by both the '
        'model measurement and external observations; no feature was inferred'
      ),
      **base,
    )
  exact_domain = model_indices == observed_indices
  status = (
    MocShockCellExternalComparisonStatus.FULL_DOMAIN_COMPUTED
    if exact_domain
    else MocShockCellExternalComparisonStatus.PARTIAL_DIAGNOSTIC
  )
  role = (
    'calibration' if dataset.split is MocExternalValidationSplit.CALIBRATION
    else 'validation'
  )
  coverage_message = (
    'exact cell-index coverage was compared'
    if exact_domain
    else 'only overlapping cell indices were compared; missing or extra cells were not filled'
  )
  return MocShockCellExternalComparison(
    status=status,
    reason=(
      f'{coverage_message} for the declared {role} case; residuals are '
      'diagnostic evidence only and do not establish canonical reflected-MOC '
      'closure or a product validation claim'
    ),
    **{**base, 'feature_comparisons': comparisons},
  )


def _split_audit_failure(
  status: MocExternalValidationSplitAuditStatus,
  message: str,
  *,
  datasets: Sequence[MocShockCellExternalDataset] = (),
  duplicate_dataset_ids: Sequence[str] = (),
  overlapping_case_ids: Sequence[str] = (),
) -> MocExternalValidationSplitAudit:
  items = tuple(
    dataset for dataset in datasets
    if isinstance(dataset, MocShockCellExternalDataset)
  )
  calibration = tuple(
    dataset.case_id
    for dataset in items
    if dataset.split is MocExternalValidationSplit.CALIBRATION
  )
  validation = tuple(
    dataset.case_id
    for dataset in items
    if dataset.split is MocExternalValidationSplit.VALIDATION
  )
  return MocExternalValidationSplitAudit(
    status=status,
    dataset_count=len(items),
    calibration_case_ids=calibration,
    validation_case_ids=validation,
    duplicate_dataset_ids=tuple(duplicate_dataset_ids),
    overlapping_case_ids=tuple(overlapping_case_ids),
    claim_status='not_accepted',
    message=message,
  )


def audit_moc_external_validation_splits(
  datasets: Sequence[MocShockCellExternalDataset],
) -> MocExternalValidationSplitAudit:
  """Verify disjoint calibration and validation case identities.

  The audit checks governance metadata only.  A verified split does not mean
  that observations exist locally, that a comparison has been computed, or
  that any product/provider claim is accepted.
  """

  try:
    items = tuple(datasets)
  except TypeError:
    return _split_audit_failure(
      MocExternalValidationSplitAuditStatus.INVALID_INPUT,
      'datasets must be an iterable of MocShockCellExternalDataset values',
    )
  if any(not isinstance(dataset, MocShockCellExternalDataset) for dataset in items):
    return _split_audit_failure(
      MocExternalValidationSplitAuditStatus.INVALID_INPUT,
      'datasets must contain MocShockCellExternalDataset values',
    )
  dataset_ids = tuple(dataset.dataset_id for dataset in items)
  duplicate_dataset_ids = tuple(sorted({
    dataset_id
    for dataset_id in dataset_ids
    if dataset_ids.count(dataset_id) > 1
  }))
  if duplicate_dataset_ids:
    return _split_audit_failure(
      MocExternalValidationSplitAuditStatus.DUPLICATE_DATASET,
      'dataset identities must be unique before a split can be audited',
      datasets=items,
      duplicate_dataset_ids=duplicate_dataset_ids,
    )
  calibration_ids = {
    dataset.case_id
    for dataset in items
    if dataset.split is MocExternalValidationSplit.CALIBRATION
  }
  validation_ids = {
    dataset.case_id
    for dataset in items
    if dataset.split is MocExternalValidationSplit.VALIDATION
  }
  if not calibration_ids or not validation_ids:
    return _split_audit_failure(
      MocExternalValidationSplitAuditStatus.MISSING_SPLIT,
      'at least one calibration dataset and one validation dataset are required',
      datasets=items,
    )
  overlapping_case_ids = tuple(sorted(calibration_ids & validation_ids))
  if overlapping_case_ids:
    return _split_audit_failure(
      MocExternalValidationSplitAuditStatus.CASE_OVERLAP,
      'case identities must not appear in both calibration and validation splits',
      datasets=items,
      overlapping_case_ids=overlapping_case_ids,
    )
  return _split_audit_failure(
    MocExternalValidationSplitAuditStatus.VERIFIED,
    (
      'calibration and validation case identities are disjoint; this governance '
      'check does not accept an external comparison or a product claim'
    ),
    datasets=items,
  )


__all__ = (
  'MOC_SHOCK_CELL_EXTERNAL_COMPARISON_OPERATOR_ID',
  'MocExternalValidationSplit',
  'MocShockCellExternalFeature',
  'MocShockCellExternalComparisonStatus',
  'MocExternalValidationSplitAuditStatus',
  'MocShockCellExternalObservation',
  'MocShockCellExternalDataset',
  'MocShockCellExternalFeatureComparison',
  'MocShockCellExternalComparison',
  'MocExternalValidationSplitAudit',
  'compare_moc_shock_cell_chain_to_external',
  'audit_moc_external_validation_splits',
)
