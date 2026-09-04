from __future__ import annotations

import math

import numpy as np
import pytest

from exhaust_plume.geometry import SectionedTubeSupport, intersect_sectioned_tube


def _cylinder() -> SectionedTubeSupport:
  return SectionedTubeSupport(
    frame_id='plume',
    centers_m=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)),
    radii_m=(1.0, 1.0),
  )
####


def test_straight_cylinder_center_chord_is_exact() -> None:
  interval = intersect_sectioned_tube(
    (-2.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    _cylinder(),
    t_max_m=20.0,
  )

  assert len(interval) == 1
  assert interval[0].t_enter_m == pytest.approx(2.0)
  assert interval[0].t_exit_m == pytest.approx(12.0)
####


def test_straight_cylinder_transverse_chord_and_miss() -> None:
  transverse = intersect_sectioned_tube(
    (5.0, -2.0, 0.0),
    (0.0, 1.0, 0.0),
    _cylinder(),
    t_max_m=10.0,
  )
  miss = intersect_sectioned_tube(
    (5.0, -2.0, 2.0),
    (0.0, 1.0, 0.0),
    _cylinder(),
    t_max_m=10.0,
  )

  assert transverse[0].t_enter_m == pytest.approx(1.0)
  assert transverse[0].t_exit_m == pytest.approx(3.0)
  assert miss == ()
####


def test_tangent_has_no_positive_path_length() -> None:
  tangent = intersect_sectioned_tube(
    (5.0, 1.0, -2.0),
    (0.0, 0.0, 1.0),
    _cylinder(),
    t_max_m=10.0,
  )

  assert tangent == ()
####


def test_curved_capsule_support_returns_ordered_non_overlapping_intervals() -> None:
  support = SectionedTubeSupport(
    frame_id='plume',
    centers_m=((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (2.0, 2.0, 0.0)),
    radii_m=(0.25, 0.25, 0.25),
  )
  intervals = intersect_sectioned_tube(
    (-1.0, 0.0, 0.0),
    (1.0, 0.0, 0.0),
    support,
    t_max_m=10.0,
  )

  assert intervals
  assert all(first.t_exit_m < second.t_enter_m for first, second in zip(intervals, intervals[1:]))
  assert all(interval.t_exit_m > interval.t_enter_m for interval in intervals)
####


def test_rigid_transform_preserves_chord_length() -> None:
  angle = 0.63
  rotation = np.array((
    (math.cos(angle), -math.sin(angle), 0.0),
    (math.sin(angle), math.cos(angle), 0.0),
    (0.0, 0.0, 1.0),
  ))
  translation = np.array((3.0, -4.0, 1.25))
  base_origin = np.array((-2.0, 0.2, 0.0))
  base_direction = np.array((1.0, 0.0, 0.0))
  transformed = SectionedTubeSupport(
    frame_id='transformed',
    centers_m=tuple(tuple(rotation @ np.asarray(center) + translation) for center in _cylinder().centers_m),
    radii_m=_cylinder().radii_m,
  )
  interval = intersect_sectioned_tube(
    base_origin,
    base_direction,
    _cylinder(),
    t_max_m=20.0,
  )
  transformed_interval = intersect_sectioned_tube(
    tuple(rotation @ base_origin + translation),
    tuple(rotation @ base_direction),
    transformed,
    t_max_m=20.0,
  )

  assert transformed_interval[0].t_exit_m - transformed_interval[0].t_enter_m == pytest.approx(
    interval[0].t_exit_m - interval[0].t_enter_m,
  )
####


def test_curved_support_refinement_is_stable_for_a_quarter_arc() -> None:
  def support(section_count: int) -> SectionedTubeSupport:
    centers = tuple(
      (
        5.0 * math.cos(index * math.pi / (2.0 * (section_count - 1))),
        5.0 * math.sin(index * math.pi / (2.0 * (section_count - 1))),
        0.0,
      )
      for index in range(section_count)
    )
    return SectionedTubeSupport(frame_id='plume', centers_m=centers, radii_m=(0.4,) * section_count)
  ####

  lengths = []
  for section_count in (3, 5, 9, 17):
    intervals = intersect_sectioned_tube(
      (-1.0, 2.5, 0.0),
      (1.0, 0.0, 0.0),
      support(section_count),
      t_max_m=12.0,
    )
    lengths.append(sum(interval.t_exit_m - interval.t_enter_m for interval in intervals))
  ####

  assert all(length > 0.0 for length in lengths)
  assert abs(lengths[-1] - lengths[-2]) < abs(lengths[1] - lengths[0])
####
