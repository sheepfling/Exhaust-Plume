from __future__ import annotations

from math import isclose

import pytest

from exhaust_plume.validation.visual_comparisons import (
  VisualFeatureSeries,
  compare_mach_disk_pressure_relation,
  compare_visual_feature_series,
)


def test_mach_disk_comparison_requires_explicit_branch_crosswalk() -> None:
  result = compare_mach_disk_pressure_relation(
    (1.0, 2.0, 3.0),
    (0.01, 0.02, 0.03),
    (1.5, 2.5),
    (0.015, 0.025),
  )

  assert result.status == 'branch-crosswalk-required'
  assert result.position_rmse_m is None
  assert 'row order' in (result.reason or '')
####


def test_mach_disk_comparison_is_branch_aware_and_does_not_use_row_order() -> None:
  result = compare_mach_disk_pressure_relation(
    (1.0, 2.0, 3.0, 1.0, 2.0, 3.0),
    (0.01, 0.02, 0.03, 0.10, 0.20, 0.30),
    (2.5, 1.5, 3.0, 1.5),
    (0.025, 0.015, 0.03, 0.15),
    model_branch_ids=('up', 'up', 'up', 'down', 'down', 'down'),
    observed_branch_ids=('up', 'up', 'up', 'down'),
  )

  assert result.status == 'full-domain-computed'
  assert result.branch_count == 2
  assert result.matched_point_count == 4
  assert isclose(result.position_rmse_m or -1.0, 0.0, abs_tol=1.0e-15)
  assert isclose(result.position_max_abs_error_m or -1.0, 0.0, abs_tol=1.0e-15)
####


def test_mach_disk_comparison_keeps_partial_overlap_as_diagnostic() -> None:
  result = compare_mach_disk_pressure_relation(
    (2.0, 3.0, 2.0, 3.0),
    (0.02, 0.03, 0.20, 0.30),
    (1.0, 2.5, 4.0, 2.5),
    (0.01, 0.025, 0.04, 0.25),
    model_branch_ids=('up', 'up', 'down', 'down'),
    observed_branch_ids=('up', 'up', 'up', 'down'),
  )

  assert result.status == 'partial-overlap-diagnostic'
  assert result.matched_point_count == 2
  assert result.position_rmse_m is not None
  assert result.reason is not None
####


def test_mach_disk_comparison_rejects_invalid_array_shapes() -> None:
  with pytest.raises(ValueError, match='matching lengths'):
    compare_mach_disk_pressure_relation(
      (1.0, 2.0),
      (0.01,),
      (1.0, 2.0),
      (0.01, 0.02),
    )
  ####
####


def test_visual_feature_series_reports_uncertainty_and_branch_coverage() -> None:
  model = VisualFeatureSeries(
    feature_id='mach_disk_position',
    coordinate_id='operating_pressure',
    coordinate_unit='bar',
    feature_unit='m',
    coordinates=(1.0, 2.0, 3.0, 1.0, 2.0, 3.0),
    values=(0.01, 0.02, 0.03, 0.10, 0.20, 0.30),
    uncertainties=(0.001, 0.001, 0.001, 0.002, 0.002, 0.002),
    branch_ids=('up', 'up', 'up', 'down', 'down', 'down'),
    source_id='model-output',
    scenario_id='hot-wake-case-1',
    coordinate_frame_id='source-local',
    measurement_space='physical-geometry',
    operator_id='operator.model.mach-disk-feature',
    model_lane_id='shock-cell-basic-v1',
  )
  observed = VisualFeatureSeries(
    feature_id='mach_disk_position',
    coordinate_id='operating_pressure',
    coordinate_unit='bar',
    feature_unit='m',
    coordinates=(2.5, 1.5, 3.0, 1.5),
    values=(0.025, 0.015, 0.30, 0.15),
    uncertainties=(0.001, 0.001, 0.002, 0.002),
    branch_ids=('up', 'up', 'down', 'down'),
    source_id='observation-output',
    scenario_id='hot-wake-case-1',
    coordinate_frame_id='source-local',
    measurement_space='physical-geometry',
    operator_id='operator.observation.mach-disk-feature',
  )

  result = compare_visual_feature_series(model, observed)

  assert result.status == 'full-domain-computed'
  assert result.branch_count == 2
  assert result.matched_point_count == 4
  assert result.coverage_fraction == pytest.approx(1.0)
  assert result.uncertainty_coverage_fraction == pytest.approx(1.0)
  assert result.value_rmse == pytest.approx(0.0)
  assert result.uncertainty_normalized_rmse == pytest.approx(0.0)
  assert result.model_source_id == 'model-output'
  assert result.model_dump()['claim_status'] == 'diagnostic-only'
####


def test_visual_feature_series_never_extrapolates_or_fills_uncertainty() -> None:
  model = VisualFeatureSeries(
    feature_id='shock-endpoint',
    coordinate_id='axial_position',
    coordinate_unit='m',
    feature_unit='m',
    coordinates=(1.0, 2.0, 3.0),
    values=(0.10, 0.20, 0.30),
    uncertainties=(0.01, 0.01, 0.01),
    source_id='model-output',
    scenario_id='case-1',
    coordinate_frame_id='source-local',
    measurement_space='physical-geometry',
    operator_id='operator.model.endpoint',
  )
  observed = VisualFeatureSeries(
    feature_id='shock-endpoint',
    coordinate_id='axial_position',
    coordinate_unit='m',
    feature_unit='m',
    coordinates=(0.0, 1.5, 2.5, 4.0),
    values=(0.0, 0.15, 0.25, 0.40),
    source_id='observation-output',
    scenario_id='case-1',
    coordinate_frame_id='source-local',
    measurement_space='physical-geometry',
    operator_id='operator.observation.endpoint',
  )

  result = compare_visual_feature_series(model, observed)

  assert result.status == 'partial-overlap-diagnostic'
  assert result.matched_point_count == 2
  assert result.coverage_fraction == pytest.approx(0.5)
  assert result.uncertainty_coverage_fraction == pytest.approx(0.0)
  assert result.uncertainty_normalized_rmse is None
  assert 'outside the model coordinate domain' in (result.reason or '')
####


def test_visual_feature_series_blocks_frame_and_scenario_mismatch() -> None:
  common = dict(
    feature_id='region-length',
    coordinate_id='time',
    coordinate_unit='s',
    feature_unit='m',
    coordinates=(0.0, 1.0),
    values=(1.0, 2.0),
    source_id='source',
    scenario_id='case-1',
    coordinate_frame_id='source-local',
    measurement_space='physical-geometry',
    operator_id='operator.feature',
  )
  model = VisualFeatureSeries(**common)
  observed = VisualFeatureSeries(
    **{
      **common,
      'source_id': 'observation',
      'scenario_id': 'case-2',
      'coordinate_frame_id': 'observer-frame',
    },
  )

  result = compare_visual_feature_series(model, observed)

  assert result.status == 'blocked-incompatible-contract'
  assert result.value_rmse is None
  assert 'scenario_id differs' in (result.reason or '')
  assert 'coordinate_frame_id differs' in (result.reason or '')
####


def test_visual_feature_series_rejects_unordered_unbranched_axis() -> None:
  with pytest.raises(ValueError, match='strictly increasing'):
    VisualFeatureSeries(
      feature_id='feature',
      coordinate_id='pressure',
      coordinate_unit='bar',
      feature_unit='m',
      coordinates=(1.0, 3.0, 2.0),
      values=(0.1, 0.3, 0.2),
      source_id='source',
      scenario_id='case-1',
      coordinate_frame_id='source-local',
      measurement_space='physical-geometry',
      operator_id='operator.feature',
    )
  ####
####
