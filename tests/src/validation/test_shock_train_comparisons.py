from __future__ import annotations

import pytest

from exhaust_plume.validation import (
  PressureExtremum,
  compare_shock_train_pressure_extrema_spacing,
)


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
