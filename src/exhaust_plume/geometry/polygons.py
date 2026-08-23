"""Polygon area and simple-polygon validation helpers."""

from __future__ import annotations

from typing import Sequence

import numpy as np

from exhaust_plume.geometry.contracts import GeometryStatus, PolygonValidationResult

__all__ = ("has_self_intersection", "polygon_signed_area", "validate_polygon")


def polygon_signed_area(vertices: Sequence[Sequence[float]] | np.ndarray) -> float:
  """Return the signed shoelace area of a 2-D polygon."""

  points = np.asarray(vertices, dtype=float)
  if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
    raise ValueError("A polygon must have at least three vertices of shape (2,)")
  ####
  if not np.isfinite(points).all():
    raise ValueError("Polygon vertices must be finite")
  ####
  return float(0.5 * np.sum(points[:, 0] * np.roll(points[:, 1], -1) - points[:, 1] * np.roll(points[:, 0], -1)))
####


def _orientation(a: np.ndarray, b: np.ndarray, c: np.ndarray, tolerance: float) -> int:
  ab = b - a
  ac = c - a
  value = float(ab[0] * ac[1] - ab[1] * ac[0])
  if abs(value) <= tolerance:
    return 0
  ####
  return 1 if value > 0.0 else -1
####


def _on_segment(a: np.ndarray, b: np.ndarray, point: np.ndarray, tolerance: float) -> bool:
  return bool(np.all(point >= np.minimum(a, b) - tolerance) and np.all(point <= np.maximum(a, b) + tolerance))
####


def _segments_intersect(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray, tolerance: float) -> bool:
  first = (_orientation(a, b, c, tolerance), _orientation(a, b, d, tolerance))
  second = (_orientation(c, d, a, tolerance), _orientation(c, d, b, tolerance))
  if first[0] == 0 and _on_segment(a, b, c, tolerance):
    return True
  ####
  if first[1] == 0 and _on_segment(a, b, d, tolerance):
    return True
  ####
  if second[0] == 0 and _on_segment(c, d, a, tolerance):
    return True
  ####
  if second[1] == 0 and _on_segment(c, d, b, tolerance):
    return True
  ####
  return first[0] != first[1] and second[0] != second[1]
####


def has_self_intersection(vertices: Sequence[Sequence[float]] | np.ndarray, *, tolerance: float = 1.0e-12) -> bool:
  points = np.asarray(vertices, dtype=float)
  if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
    raise ValueError("A polygon must have at least three vertices of shape (2,)")
  ####
  for first_index in range(len(points)):
    first_end = (first_index + 1) % len(points)
    for second_index in range(first_index + 1, len(points)):
      second_end = (second_index + 1) % len(points)
      if first_index == second_end or first_end == second_index:
        continue
      ####
      if _segments_intersect(points[first_index], points[first_end], points[second_index], points[second_end], tolerance):
        return True
      ####
    ####
  ####
  return False
####


def validate_polygon(vertices: Sequence[Sequence[float]] | np.ndarray, *, tolerance: float = 1.0e-12) -> PolygonValidationResult:
  """Return structured validity for a finite, non-degenerate, simple polygon."""

  points = np.asarray(vertices, dtype=float)
  if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3:
    return PolygonValidationResult(GeometryStatus.INVALID_INPUT, float("nan"), "A polygon needs at least three (x, y) vertices")
  ####
  if not np.isfinite(points).all():
    return PolygonValidationResult(GeometryStatus.INVALID_INPUT, float("nan"), "Polygon vertices must be finite")
  ####
  for index in range(len(points)):
    if np.linalg.norm(points[index] - points[(index + 1) % len(points)]) <= tolerance:
      return PolygonValidationResult(GeometryStatus.DUPLICATE_VERTEX, 0.0, "Polygon contains a duplicate adjacent vertex")
    ####
  ####
  for first_index in range(len(points)):
    for second_index in range(first_index + 1, len(points)):
      if np.linalg.norm(points[first_index] - points[second_index]) <= tolerance:
        return PolygonValidationResult(GeometryStatus.DUPLICATE_VERTEX, 0.0, "Polygon contains a duplicate vertex")
      ####
    ####
  ####
  area = polygon_signed_area(points)
  if has_self_intersection(points, tolerance=tolerance):
    return PolygonValidationResult(GeometryStatus.SELF_INTERSECTION, area, "Polygon edges self-intersect")
  ####
  if abs(area) <= tolerance:
    return PolygonValidationResult(GeometryStatus.ZERO_AREA, area, "Polygon has zero signed area")
  ####
  return PolygonValidationResult(GeometryStatus.VALID, area)
####
