from __future__ import annotations

from math import isclose

import pytest

from exhaust_plume.validation.visual_comparisons import (
  compare_mach_disk_pressure_relation,
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
