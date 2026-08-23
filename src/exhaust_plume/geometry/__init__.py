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

__all__ = (
    "GeometryStatus",
    "ParabolaIntersectionResult",
    "ParabolaIntersectionStatus",
    "PolygonValidationResult",
    "Ray2D",
    "RayIntersectionResult",
    "RayIntersectionStatus",
    "has_self_intersection",
    "intersect_ray_with_parabola",
    "intersect_rays",
    "polygon_signed_area",
    "validate_polygon",
)
