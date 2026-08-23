"""Forward-ray and parameterized parabola intersection solvers."""

from __future__ import annotations

from math import hypot, isfinite
from typing import Any

import numpy as np

from exhaust_plume.geometry.contracts import (
    ParabolaIntersectionResult,
    ParabolaIntersectionStatus,
    Ray2D,
    RayIntersectionResult,
    RayIntersectionStatus,
)

__all__ = ("intersect_ray_with_parabola", "intersect_rays")
###########################################


def intersect_rays(ray_a: Ray2D, ray_b: Ray2D, *, condition_limit: float = 1.0e10, parameter_tolerance: float = 1.0e-10) -> RayIntersectionResult:
  """Intersect two rays using a direct 2-by-2 solve.

  The returned parameters satisfy ``a.origin + t1*a.direction`` and
  ``b.origin + t2*b.direction``.  A successful result is forward on both
  rays; least-squares or pseudoinverse points are never returned as success.
  """

  if not isfinite(condition_limit) or condition_limit <= 1.0:
    raise ValueError("condition_limit must be finite and greater than one")
  if not isfinite(parameter_tolerance) or parameter_tolerance < 0.0:
    raise ValueError("parameter_tolerance must be finite and non-negative")
  matrix = np.column_stack((ray_a.direction, -ray_b.direction))
  right_hand_side = ray_b.origin - ray_a.origin
  determinant = float(np.linalg.det(matrix))
  if determinant == 0.0:
    return RayIntersectionResult(RayIntersectionStatus.PARALLEL, None, None, None, determinant, float("inf"), float("inf"), "Ray directions are parallel")
  condition_number = float(np.linalg.cond(matrix))
  if not isfinite(condition_number):
    return RayIntersectionResult(RayIntersectionStatus.PARALLEL, None, None, None, determinant, condition_number, float("inf"), "Ray directions are parallel")
  if condition_number > condition_limit:
    return RayIntersectionResult(RayIntersectionStatus.ILL_CONDITIONED, None, None, None, determinant, condition_number, float("inf"), "Ray intersection is ill-conditioned")
  parameters = np.linalg.solve(matrix, right_hand_side)
  parameter_a = float(parameters[0])
  parameter_b = float(parameters[1])
  point_a = ray_a.origin + parameter_a * ray_a.direction
  point_b = ray_b.origin + parameter_b * ray_b.direction
  residual = float(np.linalg.norm(point_a - point_b))
  scale = max(1.0, float(np.linalg.norm(ray_a.origin)), float(np.linalg.norm(ray_b.origin)))
  if parameter_a < -parameter_tolerance and parameter_b < -parameter_tolerance:
    status = RayIntersectionStatus.BEHIND_RAY
    message = "Intersection is behind both rays"
  elif parameter_a < -parameter_tolerance:
    status = RayIntersectionStatus.BEHIND_FIRST_RAY
    message = "Intersection is behind the first ray"
  elif parameter_b < -parameter_tolerance:
    status = RayIntersectionStatus.BEHIND_SECOND_RAY
    message = "Intersection is behind the second ray"
  else:
    status = RayIntersectionStatus.SUCCESS
    message = ""
  point = (point_a + point_b) / 2.0
  return RayIntersectionResult(status, point if status is RayIntersectionStatus.SUCCESS else None, parameter_a, parameter_b, determinant, condition_number, residual / scale, message)
  ####


def intersect_ray_with_parabola(ray: Ray2D, parabola_coeff: Any, *, parameter_tolerance: float = 1.0e-10) -> ParabolaIntersectionResult:
  """Intersect a ray with ``y = a*x**2 + b*x + c``.

  Roots are solved in the ray parameter ``t`` and the smallest forward root
  is selected.  This avoids selecting a mathematically valid point behind the
  ray origin.
  """

  coefficients = np.asarray(parabola_coeff, dtype=float)
  if coefficients.shape != (3,) or not np.isfinite(coefficients).all():
    raise ValueError("parabola_coeff must contain three finite coefficients")
  if not isfinite(parameter_tolerance) or parameter_tolerance < 0.0:
    raise ValueError("parameter_tolerance must be finite and non-negative")
  a, b, c = (float(value) for value in coefficients)
  x0, y0 = (float(value) for value in ray.origin)
  dx, dy = (float(value) for value in ray.direction)
  # y0 + t*dy = a*(x0 + t*dx)^2 + b*(x0+t*dx)+c
  quadratic = -a * dx**2
  linear = dy - 2.0 * a * x0 * dx - b * dx
  constant = y0 - a * x0**2 - b * x0 - c
  if abs(quadratic) <= 1.0e-15:
    if abs(linear) <= 1.0e-15:
      return ParabolaIntersectionResult(ParabolaIntersectionStatus.DEGENERATE, None, None, tuple(), float("inf"), "Ray is coincident with or does not cross the parabola")
    roots = (-constant / linear,)
  else:
    roots_array = np.roots(np.asarray([quadratic, linear, constant], dtype=float))
    if not np.isreal(roots_array).all():
      return ParabolaIntersectionResult(ParabolaIntersectionStatus.NO_REAL_ROOT, None, None, tuple(), float("inf"), "Ray has no real parabola intersection")
    roots = tuple(float(root.real) for root in roots_array)
  ordered_roots = tuple(sorted(roots))
  forward_roots = tuple(root for root in ordered_roots if root >= -parameter_tolerance)
  if not forward_roots:
    return ParabolaIntersectionResult(ParabolaIntersectionStatus.NO_FORWARD_ROOT, None, None, ordered_roots, float("inf"), "All parabola intersections are behind the ray")
  parameter = max(0.0, forward_roots[0])
  point = ray.origin + parameter * ray.direction
  x, y = (float(value) for value in point)
  residual = abs(y - (a * x**2 + b * x + c)) / max(1.0, hypot(x, y))
  return ParabolaIntersectionResult(ParabolaIntersectionStatus.SUCCESS, point, parameter, ordered_roots, residual)
  ####
