from __future__ import annotations

from math import exp

import pytest

from exhaust_plume.radiation import (
  HomogeneousSegment,
  compose_homogeneous_segments,
  homogeneous_segment_transfer,
)


def test_homogeneous_slab_matches_closed_form() -> None:
  result = homogeneous_segment_transfer((2.0,), (0.5,), 3.0)

  assert result.source_radiance_w_sr_m == pytest.approx((2.0 * (1.0 - exp(-1.5)),))
  assert result.background_transmittance == pytest.approx((exp(-1.5),))
  assert result.optical_depth == pytest.approx((1.5,))


def test_zero_opacity_has_zero_source_and_unit_transmission() -> None:
  result = homogeneous_segment_transfer((2.0, 3.0), (0.0, 0.0), 10.0)

  assert result.source_radiance_w_sr_m == (0.0, 0.0)
  assert result.background_transmittance == (1.0, 1.0)


def test_layer_ordering_keeps_near_source_in_front() -> None:
  near = HomogeneousSegment((1.0,), (1.0,), 1.0)
  far = HomogeneousSegment((3.0,), (1.0,), 1.0)
  result = compose_homogeneous_segments((near, far))

  expected_transmission = exp(-2.0)
  expected_source = (1.0 - exp(-1.0)) + 3.0 * (1.0 - exp(-1.0)) * exp(-1.0)
  assert result.background_transmittance == pytest.approx((expected_transmission,))
  assert result.source_radiance_w_sr_m == pytest.approx((expected_source,))


def test_optically_thin_and_thick_limits_are_bounded() -> None:
  thin = homogeneous_segment_transfer((4.0,), (1.0e-8,), 1.0)
  thick = homogeneous_segment_transfer((4.0,), (100.0,), 1.0)

  assert thin.source_radiance_w_sr_m[0] == pytest.approx(4.0e-8, rel=1.0e-5)
  assert thick.background_transmittance[0] == pytest.approx(0.0, abs=1.0e-12)
  assert thick.source_radiance_w_sr_m[0] == pytest.approx(4.0, rel=1.0e-12)
