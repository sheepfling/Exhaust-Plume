"""Radiative-transfer kernels used by bounded optical providers."""

from exhaust_plume.radiation.gray import (
  GrayTransferResult,
  HomogeneousSegment,
  compose_homogeneous_segments,
  homogeneous_segment_transfer,
)

__all__ = (
  'GrayTransferResult',
  'HomogeneousSegment',
  'compose_homogeneous_segments',
  'homogeneous_segment_transfer',
)
