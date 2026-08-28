from __future__ import annotations

from dataclasses import replace

import pytest

from exhaust_plume.models.moc import MocCharacteristicCell
from exhaust_plume.validation import (
  MocExternalValidationSplit,
  MocShockCellExternalComparisonStatus,
  MocShockCellExternalDataset,
  MocShockCellExternalFeature,
  MocShockCellExternalObservation,
  MocShockCellObservation,
  MocExternalValidationSplitAuditStatus,
  audit_moc_external_validation_splits,
  compare_moc_shock_cell_chain_to_external,
  measure_moc_shock_cell_chain,
)


def _observation(
  cell_index: int,
  shock_start_x_m: float,
) -> MocShockCellObservation:
  shock = (
    (shock_start_x_m, 1.0),
    (shock_start_x_m + 1.0, 0.5),
    (shock_start_x_m + 2.0, 0.0),
  )
  centerline = (
    (shock_start_x_m + 2.0, 0.0),
    (shock_start_x_m + 3.0, 0.0),
  )
  return MocShockCellObservation(
    cell_index=cell_index,
    shock_boundary_points_m=shock,
    centerline_boundary_points_m=centerline,
    cells=(
      MocCharacteristicCell(
        cell_index=0,
        cell_kind='external-comparison-fixture',
        vertices_xr_m=(shock[0], shock[1], shock[2], centerline[-1]),
        centerline_indices=(0,),
        boundary_indices=(0, 1),
      ),
    ),
    upstream_total_pressure_Pa=(2.0e6,) * len(shock),
    downstream_total_pressure_Pa=(1.8e6,) * len(shock),
  )


def _chain():
  result = measure_moc_shock_cell_chain(
    (_observation(1, 0.0), _observation(2, 4.0)),
  )
  assert result.converged
  return result


def _dataset(
  *,
  dataset_id: str = 'dataset-1',
  case_id: str = 'case-1',
  split: MocExternalValidationSplit = MocExternalValidationSplit.VALIDATION,
  observations: tuple[MocShockCellExternalObservation, ...] | None = None,
  **metadata: str,
) -> MocShockCellExternalDataset:
  if observations is None:
    observations = (
      MocShockCellExternalObservation(
        cell_index=1,
        axial_length_m=3.0,
        maximum_radius_m=1.0,
        shock_start_x_m=0.0,
        shock_end_x_m=2.0,
        centerline_end_x_m=3.0,
        axial_length_uncertainty_m=0.1,
        maximum_radius_uncertainty_m=0.1,
        shock_start_x_uncertainty_m=0.1,
        shock_end_x_uncertainty_m=0.1,
        centerline_end_x_uncertainty_m=0.1,
      ),
      MocShockCellExternalObservation(
        cell_index=2,
        axial_length_m=3.0,
        maximum_radius_m=1.0,
        shock_start_x_m=4.0,
        shock_end_x_m=6.0,
        centerline_end_x_m=7.0,
        axial_length_uncertainty_m=0.1,
        maximum_radius_uncertainty_m=0.1,
        shock_start_x_uncertainty_m=0.1,
        shock_end_x_uncertainty_m=0.1,
        centerline_end_x_uncertainty_m=0.1,
      ),
    )
  return MocShockCellExternalDataset(
    dataset_id=dataset_id,
    case_id=case_id,
    split=split,
    observations=observations,
    source=metadata.get('source', 'test observation source'),
    provenance=metadata.get('provenance', 'controlled unit-test fixture'),
    coordinate_frame=metadata.get('coordinate_frame', 'axial-transverse-m'),
    units=metadata.get('units', 'm'),
  )


def test_external_comparison_uses_exact_cell_indices_and_uncertainties() -> None:
  result = compare_moc_shock_cell_chain_to_external(_chain(), _dataset())

  assert result.status is MocShockCellExternalComparisonStatus.FULL_DOMAIN_COMPUTED
  assert result.computed
  assert result.matched_cell_indices == (1, 2)
  assert len(result.feature_comparisons) == len(MocShockCellExternalFeature)
  assert all(
    comparison.rmse_m == pytest.approx(0.0)
    and comparison.uncertainty_weighted_rmse == pytest.approx(0.0)
    for comparison in result.feature_comparisons
  )
  assert result.claim_status == 'not_accepted'
  assert 'canonical reflected-MOC closure' in result.reason


def test_external_comparison_reports_partial_coverage_without_extrapolation() -> None:
  result = compare_moc_shock_cell_chain_to_external(
    _chain(),
    _dataset(
      observations=(
        MocShockCellExternalObservation(
          cell_index=1,
          axial_length_m=3.1,
        ),
      ),
    ),
  )

  assert result.status is MocShockCellExternalComparisonStatus.PARTIAL_DIAGNOSTIC
  assert result.model_cell_indices == (1, 2)
  assert result.observed_cell_indices == (1,)
  assert result.matched_cell_indices == (1,)
  assert result.feature_comparisons[0].feature is MocShockCellExternalFeature.AXIAL_LENGTH_M
  assert result.feature_comparisons[0].matched_cell_indices == (1,)
  assert 'not filled' in result.reason


def test_external_comparison_blocks_unsupported_coordinate_metadata() -> None:
  result = compare_moc_shock_cell_chain_to_external(
    _chain(),
    _dataset(units='normalized-exit-diameter'),
  )

  assert result.status is MocShockCellExternalComparisonStatus.BLOCKED_COORDINATE_METADATA
  assert not result.computed
  assert 'no coordinate conversion' in result.reason


def test_external_split_audit_requires_disjoint_calibration_and_validation_cases() -> None:
  calibration = _dataset(
    dataset_id='calibration-dataset',
    case_id='calibration-case',
    split=MocExternalValidationSplit.CALIBRATION,
  )
  validation = _dataset(
    dataset_id='validation-dataset',
    case_id='validation-case',
  )

  verified = audit_moc_external_validation_splits((calibration, validation))
  assert verified.status is MocExternalValidationSplitAuditStatus.VERIFIED
  assert verified.verified

  overlap = audit_moc_external_validation_splits(
    (calibration, replace(validation, case_id='calibration-case')),
  )
  assert overlap.status is MocExternalValidationSplitAuditStatus.CASE_OVERLAP
  assert overlap.overlapping_case_ids == ('calibration-case',)
  assert not overlap.verified

  missing = audit_moc_external_validation_splits((validation,))
  assert missing.status is MocExternalValidationSplitAuditStatus.MISSING_SPLIT


def test_external_observation_rejects_empty_feature_records() -> None:
  with pytest.raises(ValueError, match='at least one external shock-cell feature'):
    MocShockCellExternalObservation(cell_index=1)

  with pytest.raises(ValueError, match='cannot be supplied without'):
    MocShockCellExternalObservation(
      cell_index=1,
      axial_length_uncertainty_m=0.1,
    )
