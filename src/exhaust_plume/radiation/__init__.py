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
from exhaust_plume.radiation.planck import (
  PLANCK_C1_W_M2,
  PLANCK_C2_M_K,
  planck_spectral_radiance_W_m2_sr_m,
)

__all__ = (
  'GrayTransferResult',
  'HomogeneousSegment',
  'compose_homogeneous_segments',
  'FarFieldRayIntegration',
  'far_field_from_rays',
  'homogeneous_segment_transfer',
  'PLANCK_C1_W_M2',
  'PLANCK_C2_M_K',
  'planck_spectral_radiance_W_m2_sr_m',
)
