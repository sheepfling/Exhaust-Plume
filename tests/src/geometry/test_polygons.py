from __future__ import annotations

import numpy as np

from exhaust_plume.geometry import has_self_intersection, polygon_signed_area, validate_polygon
from exhaust_plume.geometry.contracts import GeometryStatus


def test_signed_area_and_winding() -> None:
  square = np.asarray([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]])
  assert polygon_signed_area(square) == 1.0
  assert polygon_signed_area(square[::-1]) == -1.0
  assert validate_polygon(square).status is GeometryStatus.VALID
  ####


def test_duplicate_and_self_intersecting_vertices_are_rejected() -> None:
  duplicate = validate_polygon([[0.0, 0.0], [1.0, 0.0], [1.0, 0.0], [0.0, 1.0]])
  assert duplicate.status is GeometryStatus.DUPLICATE_VERTEX

  bowtie = np.asarray([[0.0, 0.0], [1.0, 1.0], [0.0, 1.0], [1.0, 0.0]])
  assert has_self_intersection(bowtie)
  assert validate_polygon(bowtie).status is GeometryStatus.SELF_INTERSECTION
  ####


def test_nonfinite_and_zero_area_polygons_are_rejected() -> None:
  assert validate_polygon([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]).status is GeometryStatus.ZERO_AREA
  assert validate_polygon([[0.0, 0.0], [1.0, 0.0], [np.nan, 1.0]]).status is GeometryStatus.INVALID_INPUT
  ####
