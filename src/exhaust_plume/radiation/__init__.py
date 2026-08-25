"""Radiative-transfer kernels used by bounded optical providers."""

from exhaust_plume.radiation.gray import (
  GrayTransferResult,
  HomogeneousSegment,
  compose_homogeneous_segments,
  homogeneous_segment_transfer,
)
from exhaust_plume.radiation.far_field import (
  FarFieldRayIntegration,
  far_field_from_rays,
)

__all__ = (
  'GrayTransferResult',
  'HomogeneousSegment',
  'compose_homogeneous_segments',
  'FarFieldRayIntegration',
  'far_field_from_rays',
  'homogeneous_segment_transfer',
)
