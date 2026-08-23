"""Stable semantic capability identifiers and their major versions."""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping


class CapabilityId(str, Enum):
  """Semantic products that a plume provider may advertise."""

  SPATIAL_SUPPORT = 'spatial-support'
  AXISYMMETRIC_ZONE_FIELD = 'axisymmetric-zone-field'
  CENTERLINE_TUBE_FIELD = 'centerline-tube-field'
  LOCAL_FLOW_STATE = 'local-flow-state'
  PROJECTED_AREA = 'projected-area'
  DIRECTIONAL_SPECTRAL_INTENSITY = 'directional-spectral-intensity'
  SPECTRAL_RAY_TRANSFER = 'spectral-ray-transfer'
  OPTICAL_MEDIUM = 'optical-medium'
  SCENE_RADIANCE_RENDERER = 'scene-radiance-renderer'
  UNCERTAINTY = 'uncertainty'
  ####


CAPABILITY_MAJOR_VERSIONS: Mapping[CapabilityId, int] = MappingProxyType({
    capability_id: 1 for capability_id in CapabilityId
})
####
