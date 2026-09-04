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
from exhaust_plume.radiation.lines import (
  BOLTZMANN_J_K,
  SPEED_OF_LIGHT_M_S,
  LineRadiationProfile,
  SectionedLineRadiationProfile,
  SpectralLine,
  voigt_line_shape_per_m,
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
  'BOLTZMANN_J_K',
  'SPEED_OF_LIGHT_M_S',
  'LineRadiationProfile',
  'SectionedLineRadiationProfile',
  'SpectralLine',
  'voigt_line_shape_per_m',
)
