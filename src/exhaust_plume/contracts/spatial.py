"""Spatial capability result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import numpy as np

from exhaust_plume.contracts.capability import CapabilityId
from exhaust_plume.geometry.contracts import GeometryStatus


@dataclass(frozen=True, slots=True)
class SpatialSupport:
  """Conservative axis-aligned support in the plume-local frame."""

  plume_frame_aabb_min_m: tuple[float, float, float]
  plume_frame_aabb_max_m: tuple[float, float, float]
  characteristic_extent_m: float
  support_definition: str
  is_conservative: bool
  capability_id: CapabilityId = CapabilityId.SPATIAL_SUPPORT
  major_version: int = 1

  def __post_init__(self) -> None:
    minimum = tuple(float(value) for value in self.plume_frame_aabb_min_m)
    maximum = tuple(float(value) for value in self.plume_frame_aabb_max_m)
    if len(minimum) != 3 or len(maximum) != 3:
      raise ValueError('spatial support bounds must contain three coordinates')
    if any(not isfinite(value) for value in (*minimum, *maximum)):
      raise ValueError('spatial support bounds must be finite')
    if any(lower > upper for lower, upper in zip(minimum, maximum)):
      raise ValueError('spatial support minimum must not exceed maximum')
    if not isfinite(self.characteristic_extent_m) or self.characteristic_extent_m <= 0:
      raise ValueError('characteristic_extent_m must be positive and finite')
    if not self.support_definition:
      raise ValueError('support_definition must not be empty')
    object.__setattr__(self, 'plume_frame_aabb_min_m', minimum)
    object.__setattr__(self, 'plume_frame_aabb_max_m', maximum)
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class AxisymmetricZone:
  """Provider-neutral finite zone in the axial/radial ``(x, r)`` plane."""

  zone_id: str
  polygon_xr_m: np.ndarray
  static_pressure_Pa: float
  static_temperature_K: float
  density_kgpm3: float
  mach: float
  phase: str
  cell_index: int
  geometry_status: GeometryStatus = GeometryStatus.VALID

  def __post_init__(self) -> None:
    polygon = np.array(self.polygon_xr_m, dtype=float, copy=True)
    if not self.zone_id or polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3 or not np.isfinite(polygon).all():
      raise ValueError('axisymmetric zone requires a non-empty ID and finite polygon shape (N, 2)')
    if self.geometry_status is not GeometryStatus.VALID:
      raise ValueError('axisymmetric zone geometry must be valid')
    from exhaust_plume.geometry.polygons import validate_polygon
    if not validate_polygon(polygon).is_valid:
      raise ValueError('axisymmetric zone polygon must be simple and non-degenerate')
    for name, value in (
        ('static_pressure_Pa', self.static_pressure_Pa),
        ('static_temperature_K', self.static_temperature_K),
        ('density_kgpm3', self.density_kgpm3),
        ('mach', self.mach),
    ):
      if not isfinite(value) or (name != 'mach' and value <= 0.0):
        raise ValueError(f'{name} must be finite and positive')
    if self.mach < 0.0:
      raise ValueError('mach must be finite and non-negative')
    if self.cell_index < 0:
      raise ValueError('cell_index must be non-negative')
    polygon.flags.writeable = False
    object.__setattr__(self, 'polygon_xr_m', polygon)
  ####


@dataclass(frozen=True, slots=True)
class AxisymmetricZoneField:
  """Finite neutral zone-field capability for a straight analytical provider."""

  zones: tuple[AxisymmetricZone, ...]
  axis_definition: str = 'x-axis; r is non-negative radial distance'
  capability_id: CapabilityId = CapabilityId.AXISYMMETRIC_ZONE_FIELD
  major_version: int = 1

  def __post_init__(self) -> None:
    object.__setattr__(self, 'zones', tuple(self.zones))
    if not self.axis_definition:
      raise ValueError('axis_definition must not be empty')
  ####


@dataclass(frozen=True, slots=True)
class ProjectedAreaCapability:
  """Reference projected area metadata for the current straight field."""

  reference_area_m2: float
  closed_zone_count: int
  capability_id: CapabilityId = CapabilityId.PROJECTED_AREA
  major_version: int = 1

  def __post_init__(self) -> None:
    if not isfinite(self.reference_area_m2) or self.reference_area_m2 <= 0.0:
      raise ValueError('reference_area_m2 must be finite and positive')
    if self.closed_zone_count < 0:
      raise ValueError('closed_zone_count must be non-negative')
  ####
