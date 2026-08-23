"""Immutable result contracts for validated planar geometry operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import numpy as np

__all__ = (
    "GeometryStatus",
    "ParabolaIntersectionResult",
    "ParabolaIntersectionStatus",
    "PolygonValidationResult",
    "Ray2D",
    "RayIntersectionResult",
    "RayIntersectionStatus",
)


class GeometryStatus(str, Enum):
  VALID = "valid"
  SUCCESS = "success"
  OPEN_TRANSITION = "open_transition"
  INVALID_INPUT = "invalid_input"
  DEGENERATE = "degenerate"
  PARALLEL = "parallel"
  ILL_CONDITIONED = "ill_conditioned"
  BEHIND_FIRST_RAY = "behind_first_ray"
  BEHIND_SECOND_RAY = "behind_second_ray"
  BEHIND_RAY = "behind_ray"
  NO_REAL_ROOT = "no_real_root"
  NO_FORWARD_ROOT = "no_forward_root"
  NO_FORWARD_INTERSECTION = "no_forward_intersection"
  DUPLICATE_VERTEX = "duplicate_vertex"
  SELF_INTERSECTION = "self_intersection"
  SELF_INTERSECTING = "self_intersection"
  ZERO_AREA = "zero_area"
  INVALID_WINDING = "invalid_winding"
  OUTSIDE_DOMAIN = "outside_domain"
####


class RayIntersectionStatus(str, Enum):
  SUCCESS = GeometryStatus.SUCCESS.value
  INVALID_INPUT = GeometryStatus.INVALID_INPUT.value
  DEGENERATE = GeometryStatus.DEGENERATE.value
  PARALLEL = GeometryStatus.PARALLEL.value
  ILL_CONDITIONED = GeometryStatus.ILL_CONDITIONED.value
  BEHIND_FIRST_RAY = GeometryStatus.BEHIND_FIRST_RAY.value
  BEHIND_SECOND_RAY = GeometryStatus.BEHIND_SECOND_RAY.value
  BEHIND_RAY = GeometryStatus.BEHIND_RAY.value
####


class ParabolaIntersectionStatus(str, Enum):
  SUCCESS = GeometryStatus.SUCCESS.value
  INVALID_INPUT = GeometryStatus.INVALID_INPUT.value
  DEGENERATE = GeometryStatus.DEGENERATE.value
  NO_REAL_ROOT = GeometryStatus.NO_REAL_ROOT.value
  NO_FORWARD_ROOT = GeometryStatus.NO_FORWARD_ROOT.value
####


@dataclass(frozen=True)
class Ray2D:
  """A forward ray with a finite origin and unit direction."""

  origin: np.ndarray
  direction: np.ndarray

  def __post_init__(self) -> None:
    origin = np.array(self.origin, dtype=float, copy=True)
    direction = np.array(self.direction, dtype=float, copy=True)
    if origin.shape != (2,) or direction.shape != (2,):
      raise ValueError(f"Ray origin and direction must each have shape (2,); got {origin.shape} and {direction.shape}")
    ####
    if not np.isfinite(origin).all() or not np.isfinite(direction).all():
      raise ValueError("Ray origin and direction must be finite")
    ####
    norm = float(np.linalg.norm(direction))
    if norm == 0.0:
      raise ValueError("Ray direction must be non-zero")
    ####
    direction /= norm
    origin.flags.writeable = False
    direction.flags.writeable = False
    object.__setattr__(self, "origin", origin)
    object.__setattr__(self, "direction", direction)
  ####
####


@dataclass(frozen=True)
class RayIntersectionResult:
  """Validated result for intersecting two forward rays."""

  status: RayIntersectionStatus
  point: Optional[np.ndarray]
  parameter_a: Optional[float]
  parameter_b: Optional[float]
  determinant: float
  condition_number: float
  residual: float
  message: str = ""

  def __post_init__(self) -> None:
    if self.point is not None:
      point = np.array(self.point, dtype=float, copy=True)
      point.flags.writeable = False
      object.__setattr__(self, "point", point)
    ####
  ####

  @property
  def is_success(self) -> bool:
    return self.status is RayIntersectionStatus.SUCCESS
  ####

  @property
  def t1(self) -> Optional[float]:
    return self.parameter_a
  ####

  @property
  def t2(self) -> Optional[float]:
    return self.parameter_b
  ####
####


@dataclass(frozen=True)
class ParabolaIntersectionResult:
  """Validated result for a ray and ``y = a*x**2 + b*x + c``."""

  status: ParabolaIntersectionStatus
  point: Optional[np.ndarray]
  parameter: Optional[float]
  roots: Tuple[float, ...]
  residual: float
  message: str = ""

  def __post_init__(self) -> None:
    if self.point is not None:
      point = np.array(self.point, dtype=float, copy=True)
      point.flags.writeable = False
      object.__setattr__(self, "point", point)
    ####
  ####

  @property
  def is_success(self) -> bool:
    return self.status is ParabolaIntersectionStatus.SUCCESS
  ####
####


class PolygonValidationResult:
  """Validation outcome for a finite, simple polygon."""

  __slots__ = ("status", "signed_area", "message")

  def __init__(self, status: GeometryStatus, signed_area: float, message: str = "") -> None:
    self.status = status
    self.signed_area = signed_area
    self.message = message
  ####

  @property
  def is_valid(self) -> bool:
    return self.status in (GeometryStatus.VALID, GeometryStatus.SUCCESS)
  ####

  def __repr__(self) -> str:
    return f"PolygonValidationResult(status={self.status!r}, signed_area={self.signed_area!r}, message={self.message!r})"
  ####
####
