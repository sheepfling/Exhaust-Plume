from __future__ import annotations

import numpy as np
import pytest

from exhaust_plume.geometry import Ray2D, intersect_ray_with_parabola, intersect_rays
from exhaust_plume.geometry.contracts import ParabolaIntersectionStatus, RayIntersectionStatus


def test_orthogonal_forward_rays_and_common_origin() -> None:
  result = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
      Ray2D(origin=[2.0, -1.0], direction=[0.0, 1.0]),
  )
  assert result.status is RayIntersectionStatus.SUCCESS
  assert result.point is not None
  np.testing.assert_allclose(result.point, [2.0, 0.0])
  assert result.parameter_a == pytest.approx(2.0)
  assert result.parameter_b == pytest.approx(1.0)

  origin = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
      Ray2D(origin=[0.0, 0.0], direction=[0.0, 1.0]),
  )
  assert origin.status is RayIntersectionStatus.SUCCESS
  assert origin.parameter_a == pytest.approx(0.0)
  assert origin.parameter_b == pytest.approx(0.0)
####


def test_parallel_and_ill_conditioned_rays_are_not_finite_successes() -> None:
  parallel = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
      Ray2D(origin=[0.0, 1.0], direction=[2.0, 0.0]),
  )
  assert parallel.status is RayIntersectionStatus.PARALLEL
  assert parallel.point is None

  near_parallel = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
      Ray2D(origin=[0.0, 1.0], direction=[1.0, 1.0e-12]),
  )
  assert near_parallel.status is RayIntersectionStatus.ILL_CONDITIONED
  assert near_parallel.point is None
####


def test_intersection_behind_each_ray_is_reported() -> None:
  behind_first = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
      Ray2D(origin=[-1.0, 1.0], direction=[0.0, -1.0]),
  )
  assert behind_first.status is RayIntersectionStatus.BEHIND_FIRST_RAY

  behind_second = intersect_rays(
      Ray2D(origin=[-1.0, 1.0], direction=[0.0, -1.0]),
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
  )
  assert behind_second.status is RayIntersectionStatus.BEHIND_SECOND_RAY
####


def test_intersection_scales_with_geometry() -> None:
  base = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1.0, 0.0]),
      Ray2D(origin=[2.0, -1.0], direction=[0.0, 1.0]),
  )
  scaled = intersect_rays(
      Ray2D(origin=[0.0, 0.0], direction=[1000.0, 0.0]),
      Ray2D(origin=[2000.0, -1000.0], direction=[0.0, 1000.0]),
  )
  assert base.status is RayIntersectionStatus.SUCCESS
  assert scaled.status is RayIntersectionStatus.SUCCESS
  assert scaled.point is not None
  assert base.point is not None
  np.testing.assert_allclose(scaled.point, base.point * 1000.0)
  assert scaled.condition_number == pytest.approx(base.condition_number)
####


def test_parabola_selects_smallest_forward_parameter() -> None:
  result = intersect_ray_with_parabola(
      Ray2D(origin=[-3.0, 4.0], direction=[1.0, 0.0]),
      [1.0, 0.0, 0.0],
  )
  assert result.status is ParabolaIntersectionStatus.SUCCESS
  assert result.parameter == pytest.approx(1.0)
  assert result.point is not None
  np.testing.assert_allclose(result.point, [-2.0, 4.0])
  assert result.residual < 1.0e-12
####
