from __future__ import annotations

import pytest

from exhaust_plume.models.moc import (
  CharacteristicState,
  MocPostShockBoundaryState,
  MocPostShockContinuationStatus,
  continue_post_shock_characteristics_to_centerline,
)


def _prescribed_boundary() -> tuple[MocPostShockBoundaryState, ...]:
  points = (
    (0.76, 0.165),
    (0.78, 0.110),
    (0.80, 0.055),
    (0.82, 0.0),
  )
  return tuple(
    MocPostShockBoundaryState(
      point_m=point,
      state=CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=-0.1 * (3 - index),
        mach=2.0,
        gamma=1.4,
      ),
      upstream_total_pressure_Pa=2.0e6,
      downstream_total_pressure_Pa=1.8e6,
    )
    for index, point in enumerate(points)
  )


def test_prescribed_post_shock_c_minus_traces_reach_centerline() -> None:
  result = continue_post_shock_characteristics_to_centerline(_prescribed_boundary())

  assert result.status is MocPostShockContinuationStatus.CONVERGED_PRESCRIBED_BOUNDARY
  assert result.converged
  assert len(result.segments) == 4
  assert len(result.centerline_states) == 4
  assert result.maximum_geometry_residual_m == pytest.approx(0.0, abs=1.0e-12)
  assert result.maximum_absolute_invariant_residual is not None
  assert result.maximum_absolute_invariant_residual < 1.0e-10
  assert result.segments[-1].centerline_point_m == pytest.approx((0.82, 0.0))
  assert all(segment.centerline_state.theta_rad == pytest.approx(0.0) for segment in result.segments)
  assert 'shock fitting' in result.message


def test_post_shock_continuation_requires_total_pressure_loss() -> None:
  samples = list(_prescribed_boundary())
  samples[-1] = MocPostShockBoundaryState(
    point_m=samples[-1].point_m,
    state=samples[-1].state,
    upstream_total_pressure_Pa=1.8e6,
    downstream_total_pressure_Pa=1.8e6,
  )

  result = continue_post_shock_characteristics_to_centerline(samples)

  assert result.status is MocPostShockContinuationStatus.INVALID_INPUT
  assert 'strict total-pressure loss' in result.message


def test_post_shock_continuation_requires_centerline_terminal_sample() -> None:
  samples = list(_prescribed_boundary())
  samples[-1] = MocPostShockBoundaryState(
    point_m=(0.82, 0.01),
    state=CharacteristicState(
      x_m=0.82,
      y_m=0.01,
      theta_rad=0.0,
      mach=2.0,
      gamma=1.4,
    ),
    upstream_total_pressure_Pa=2.0e6,
    downstream_total_pressure_Pa=1.8e6,
  )

  result = continue_post_shock_characteristics_to_centerline(samples)

  assert result.status is MocPostShockContinuationStatus.INVALID_INPUT
  assert 'final post-shock boundary sample must lie on the symmetry line' in result.message
