"""Validated two-dimensional geometry primitives for plume construction."""

from __future__ import annotations

from exhaust_plume.geometry.contracts import (
    GeometryStatus,
    ParabolaIntersectionResult,
    ParabolaIntersectionStatus,
    PolygonValidationResult,
    Ray2D,
    RayIntersectionResult,
    RayIntersectionStatus,
)
from exhaust_plume.geometry.intersections import intersect_ray_with_parabola, intersect_rays
from exhaust_plume.geometry.polygons import has_self_intersection, polygon_signed_area, validate_polygon
from exhaust_plume.geometry.ray_intervals import RayInterval, SectionedTubeSupport, intersect_sectioned_tube

__all__ = (
    "GeometryStatus",
    "ParabolaIntersectionResult",
    "ParabolaIntersectionStatus",
    "PolygonValidationResult",
    "Ray2D",
    "RayIntersectionResult",
    "RayIntersectionStatus",
    "RayInterval",
    "SectionedTubeSupport",
    "has_self_intersection",
    "intersect_ray_with_parabola",
    "intersect_rays",
    "intersect_sectioned_tube",
    "polygon_signed_area",
    "validate_polygon",
)
