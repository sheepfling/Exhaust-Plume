from __future__ import annotations

import pytest

from exhaust_plume.validation import (
  PressureExtremum,
  ShockTrainCalibrationValidationSplitAuditStatus,
  audit_shock_train_calibration_validation_split,
  compare_shock_train_pressure_extrema_spacing,
)
from exhaust_plume.models.shock_train import ShockTrainCalibrationValidationSplit


def test_same_phase_spacing_is_computed_without_accepting_a_physical_claim() -> None:
  result = compare_shock_train_pressure_extrema_spacing(
    (0.7, 0.6, 0.5),
    1.0,
    (
      PressureExtremum('minimum', 0.2, 0.03),
      PressureExtremum('maximum', 0.5, 0.03),
      PressureExtremum('minimum', 0.9, 0.03),
    ),
    phase_kind='minimum',
  )

  assert result.status == 'partial-diagnostic'
  assert result.matched_spacing_count == 1
  assert result.rmse_over_D == pytest.approx(0.0)
  assert result.uncertainty_weighted_rmse == pytest.approx(0.0)
  assert result.claim_status == 'not_accepted'
  assert 'does not identify physical' in result.reason
####


def test_spacing_operator_reports_partial_overlap_without_extrapolation() -> None:
  result = compare_shock_train_pressure_extrema_spacing(
    (0.7,),
    1.0,
    (
      PressureExtremum('minimum', 0.0),
      PressureExtremum('minimum', 0.7),
      PressureExtremum('minimum', 1.4),
    ),
    phase_kind='minimum',
  )

  assert result.status == 'partial-diagnostic'
  assert result.model_cell_count == 1
  assert result.observed_extrema_count == 3
  assert result.matched_spacing_count == 1
  assert result.observed_spacing_over_D == pytest.approx((0.7, 0.7))
  assert result.uncertainty_weighted_rmse is None
####


def test_spacing_operator_blocks_when_a_phase_has_no_interval() -> None:
  result = compare_shock_train_pressure_extrema_spacing(
    (0.7,),
    1.0,
    (PressureExtremum('minimum', 0.2),),
    phase_kind='minimum',
  )

  assert result.status == 'blocked-insufficient-extrema'
  assert result.matched_spacing_count == 0
  assert result.rmse_over_D is None
  assert result.claim_status == 'not_accepted'
####


def test_spacing_operator_rejects_duplicate_same_phase_positions() -> None:
  with pytest.raises(ValueError, match='unique axial positions'):
    compare_shock_train_pressure_extrema_spacing(
      (0.7,),
      1.0,
      (
        PressureExtremum('maximum', 0.2),
        PressureExtremum('maximum', 0.2),
      ),
      phase_kind='maximum',
    )
  ####
####


def test_shock_train_split_audit_verifies_roles_without_accepting_physics() -> None:
  audit = audit_shock_train_calibration_validation_split(
    ShockTrainCalibrationValidationSplit(
      calibration_case_ids=('calibration-001',),
      validation_case_ids=('validation-001',),
      unassigned_case_ids=('candidate-001',),
    ),
    ('calibration-001', 'validation-001', 'candidate-001'),
  )

  assert audit.status is ShockTrainCalibrationValidationSplitAuditStatus.VERIFIED
  assert audit.verified
  assert audit.accepted is False
  assert audit.claim_status == 'not_accepted'
  assert audit.as_report()['operator_id'] == (
    'op.reduce.shock-train-calibration-validation-split'
  )
####


def test_shock_train_split_audit_keeps_single_case_unassigned() -> None:
  audit = audit_shock_train_calibration_validation_split(
    ShockTrainCalibrationValidationSplit(
      unassigned_case_ids=('CJ-UEJ-001',),
    ),
    ('CJ-UEJ-001',),
  )

  assert audit.status is (
    ShockTrainCalibrationValidationSplitAuditStatus.MISSING_SPLIT
  )
  assert audit.verified is False
  assert audit.unassigned_case_ids == ('CJ-UEJ-001',)
  assert audit.as_report()['accepted'] is False
####


def test_shock_train_split_audit_rejects_unknown_and_duplicate_inventory_ids() -> None:
  unknown = audit_shock_train_calibration_validation_split(
    ShockTrainCalibrationValidationSplit(
      calibration_case_ids=('calibration-001',),
      validation_case_ids=('validation-001',),
    ),
    ('calibration-001', 'validation-001', 'other-001'),
  )
  assert unknown.status is (
    ShockTrainCalibrationValidationSplitAuditStatus.UNASSIGNED_CASES
  )
  assert unknown.unassigned_available_case_ids == ('other-001',)

  duplicate = audit_shock_train_calibration_validation_split(
    ShockTrainCalibrationValidationSplit(
      calibration_case_ids=('calibration-001',),
      validation_case_ids=('validation-001',),
    ),
    ('calibration-001', 'validation-001', 'validation-001'),
  )
  assert duplicate.status is (
    ShockTrainCalibrationValidationSplitAuditStatus.DUPLICATE_CASE_IDS
  )
  assert duplicate.duplicate_case_ids == ('validation-001',)
####
