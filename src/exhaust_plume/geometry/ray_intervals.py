"""Forward-ray intervals through straight and sectioned-tube supports.

The straight, constant-radius case is an exact finite-cylinder intersection.
General sectioned supports are represented as a union of constant-radius
capsules between adjacent section centers.  A varying section radius uses the
larger radius for that segment and is therefore a conservative support
approximation; the approximation is explicit in the support descriptor and
does not advertise ray-transfer physics by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from typing import Sequence

import numpy as np

Vector3 = tuple[float, float, float]

__all__ = (
  'RayInterval',
  'SectionedTubeSupport',
  'intersect_sectioned_tube',
)


def _vector3(value: Sequence[float], field_name: str) -> Vector3:
  if len(value) != 3 or not all(isfinite(float(component)) for component in value):
    raise ValueError(f'{field_name} must be a finite three-vector')
  ####
  return tuple(float(component) for component in value)  # type: ignore[return-value]
####


@dataclass(frozen=True, slots=True)
class RayInterval:
  """One positive-length interval along a unit forward ray."""

  t_enter_m: float
  t_exit_m: float
  support_segment_index: int | None = None

  def __post_init__(self) -> None:
    if not (
        isfinite(self.t_enter_m)
        and isfinite(self.t_exit_m)
        and 0.0 <= self.t_enter_m < self.t_exit_m
    ):
      raise ValueError('ray interval must satisfy 0 <= t_enter_m < t_exit_m')
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class SectionedTubeSupport:
  """A connected circular sectioned support in one Cartesian frame."""

  frame_id: str
  centers_m: tuple[Vector3, ...]
  radii_m: tuple[float, ...]
  radius_policy: str = 'constant-or-segment-maximum'

  def __post_init__(self) -> None:
    if not self.frame_id:
      raise ValueError('support frame_id must not be empty')
    ####
    if len(self.centers_m) < 2:
      raise ValueError('sectioned support requires at least two centers')
    ####
    if len(self.centers_m) != len(self.radii_m):
      raise ValueError('support centers and radii must have matching lengths')
    ####
    centers = tuple(_vector3(center, 'support center') for center in self.centers_m)
    radii = tuple(float(radius) for radius in self.radii_m)
    if not all(isfinite(radius) and radius > 0.0 for radius in radii):
      raise ValueError('support radii must be finite and positive')
    ####
    for first, second in zip(centers, centers[1:]):
      if np.linalg.norm(np.subtract(second, first)) <= 1.0e-14:
        raise ValueError('adjacent support centers must be distinct')
      ####
    ####
    if self.radius_policy != 'constant-or-segment-maximum':
      raise ValueError('unsupported sectioned-support radius policy')
    ####
    object.__setattr__(self, 'centers_m', centers)
    object.__setattr__(self, 'radii_m', radii)
  ####

  @property
  def is_constant_radius(self) -> bool:
    return all(abs(radius - self.radii_m[0]) <= 1.0e-12 * max(1.0, self.radii_m[0]) for radius in self.radii_m)
  ####

  @property
  def is_straight(self) -> bool:
    axis = np.subtract(self.centers_m[-1], self.centers_m[0])
    axis_norm = float(np.linalg.norm(axis))
    if axis_norm == 0.0:
      return False
    ####
    axis /= axis_norm
    for center in self.centers_m[1:-1]:
      displacement = np.subtract(center, self.centers_m[0])
      if float(np.linalg.norm(displacement - np.dot(displacement, axis) * axis)) > 1.0e-10 * max(1.0, axis_norm):
        return False
      ####
    ####
    return True
  ####
####


def _clip_interval(
    interval: tuple[float, float] | None,
    t_min_m: float,
    t_max_m: float,
    *,
    tolerance: float,
) -> tuple[float, float] | None:
  if interval is None:
    return None
  ####
  enter = max(interval[0], t_min_m)
  exit = min(interval[1], t_max_m)
  if exit - enter <= tolerance:
    return None
  ####
  return enter, exit
####


def _intersect_sphere(
    origin: np.ndarray,
    direction: np.ndarray,
    center: np.ndarray,
    radius: float,
    t_min_m: float,
    t_max_m: float,
    *,
    tolerance: float,
) -> tuple[float, float] | None:
  offset = origin - center
  linear = float(np.dot(direction, offset))
  constant = float(np.dot(offset, offset) - radius * radius)
  discriminant = linear * linear - constant
  if discriminant <= tolerance * tolerance:
    return None
  ####
  root = sqrt(discriminant)
  return _clip_interval((-linear - root, -linear + root), t_min_m, t_max_m, tolerance=tolerance)
####


def _intersect_finite_cylinder(
    origin: np.ndarray,
    direction: np.ndarray,
    start: np.ndarray,
    end: np.ndarray,
    radius: float,
    t_min_m: float,
    t_max_m: float,
    *,
    tolerance: float,
) -> tuple[float, float] | None:
  axis_vector = end - start
  length = float(np.linalg.norm(axis_vector))
  axis = axis_vector / length
  offset = origin - start
  direction_parallel = float(np.dot(direction, axis))
  offset_parallel = float(np.dot(offset, axis))
  direction_perpendicular = direction - direction_parallel * axis
  offset_perpendicular = offset - offset_parallel * axis

  quadratic = float(np.dot(direction_perpendicular, direction_perpendicular))
  linear = 2.0 * float(np.dot(direction_perpendicular, offset_perpendicular))
  constant = float(np.dot(offset_perpendicular, offset_perpendicular) - radius * radius)
  radial_tolerance = tolerance * max(1.0, radius * radius)
  if quadratic <= tolerance * tolerance:
    if constant > radial_tolerance:
      return None
    ####
    side_interval: tuple[float, float] | None = (-float('inf'), float('inf'))
  else:
    discriminant = linear * linear - 4.0 * quadratic * constant
    if discriminant <= radial_tolerance:
      return None
    ####
    root = sqrt(discriminant)
    side_interval = (
      (-linear - root) / (2.0 * quadratic),
      (-linear + root) / (2.0 * quadratic),
    )
  ####

  if abs(direction_parallel) <= tolerance:
    if offset_parallel < -tolerance or offset_parallel > length + tolerance:
      return None
    ####
    axial_interval: tuple[float, float] | None = (-float('inf'), float('inf'))
  else:
    first = (0.0 - offset_parallel) / direction_parallel
    second = (length - offset_parallel) / direction_parallel
    axial_interval = (min(first, second), max(first, second))
  ####
  enter = max(side_interval[0], axial_interval[0], t_min_m)
  exit = min(side_interval[1], axial_interval[1], t_max_m)
  if exit - enter <= tolerance:
    return None
  ####
  return enter, exit
####


def _merge_intervals(
    intervals: list[tuple[float, float, int | None]],
    *,
    tolerance: float,
) -> tuple[RayInterval, ...]:
  if not intervals:
    return ()
  ####
  intervals.sort(key=lambda item: (item[0], item[1]))
  merged: list[tuple[float, float, int | None]] = []
  for enter, exit, segment_index in intervals:
    if merged and enter <= float(merged[-1][1]) + tolerance:
      previous_enter, previous_exit, previous_segment_index = merged[-1]
      merged[-1] = (
        previous_enter,
        max(previous_exit, exit),
        previous_segment_index if previous_segment_index == segment_index else None,
      )
      continue
    ####
    merged.append((enter, exit, segment_index))
  ####
  return tuple(RayInterval(enter, exit, segment_index) for enter, exit, segment_index in merged)
####


def intersect_sectioned_tube(
    origin_m: Sequence[float],
    direction: Sequence[float],
    support: SectionedTubeSupport,
    *,
    t_min_m: float = 0.0,
    t_max_m: float = float('inf'),
    tolerance: float = 1.0e-10,
) -> tuple[RayInterval, ...]:
  """Return ordered positive-length intersections through ``support``.

  The ray direction must be unit length because the interval parameter is a
  distance in metres.  Tangencies have zero path length and are returned as a
  miss.  For a straight constant-radius support the result is the exact
  finite-cylinder chord; otherwise the result is the ordered union of
  piecewise capsule intervals.
  """

  if not isfinite(t_min_m) or t_min_m < 0.0:
    raise ValueError('t_min_m must be finite and nonnegative')
  ####
  if (not isfinite(t_max_m) and t_max_m != float('inf')) or t_max_m <= t_min_m:
    raise ValueError('t_max_m must be finite and greater than t_min_m')
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('tolerance must be finite and positive')
  ####
  origin = np.asarray(_vector3(origin_m, 'origin'), dtype=float)
  ray_direction = np.asarray(_vector3(direction, 'direction'), dtype=float)
  direction_norm = float(np.linalg.norm(ray_direction))
  if abs(direction_norm - 1.0) > 1.0e-7:
    raise ValueError('direction must be unit length')
  ####
  centers = tuple(np.asarray(center, dtype=float) for center in support.centers_m)
  if support.is_straight and support.is_constant_radius:
    interval = _intersect_finite_cylinder(
      origin,
      ray_direction,
      centers[0],
      centers[-1],
      support.radii_m[0],
      t_min_m,
      t_max_m,
      tolerance=tolerance,
    )
    return () if interval is None else (RayInterval(*interval, support_segment_index=0),)
  ####

  raw_intervals: list[tuple[float, float, int | None]] = []
  for segment_index, (start, end, first_radius, second_radius) in enumerate(
      zip(centers, centers[1:], support.radii_m, support.radii_m[1:]),
  ):
    radius = max(first_radius, second_radius)
    cylinder_interval = _intersect_finite_cylinder(
      origin,
      ray_direction,
      start,
      end,
      radius,
      t_min_m,
      t_max_m,
      tolerance=tolerance,
    )
    if cylinder_interval is not None:
      raw_intervals.append((*cylinder_interval, segment_index))
    ####
    for center in (start, end):
      sphere_interval = _intersect_sphere(
        origin,
        ray_direction,
        center,
        radius,
        t_min_m,
        t_max_m,
        tolerance=tolerance,
      )
      if sphere_interval is not None:
        raw_intervals.append((*sphere_interval, segment_index))
      ####
    ####
  ####
  return _merge_intervals(raw_intervals, tolerance=tolerance)
####
