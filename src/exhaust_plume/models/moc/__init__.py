"""Standalone planar method-of-characteristics primitives.

The MOC namespace is intentionally separate from the compatibility-backed
shock-cell solver.  Nothing in this package changes the claim ceiling or
provider selection of the basic visual lane.
"""

from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  ScalarRootResult,
  centerline_characteristic_point,
  characteristic_invariants,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
  mach_angle_rad,
  maximum_prandtl_meyer_angle_rad,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.models.moc.fan import (
  MocExpansionFanCell,
  MocExpansionFanResult,
  solve_underexpanded_expansion_fan,
)
from exhaust_plume.models.moc.compression import (
  MocCompressionResult,
  solve_attached_compression_to_pressure,
)
from exhaust_plume.models.moc.topology import (
  MocTopologyResult,
  MocTopologyStatus,
  validate_moc_mesh,
)

__all__ = (
  'CharacteristicFamily',
  'CharacteristicPointResult',
  'CharacteristicState',
  'MocPrimitiveStatus',
  'MocExpansionFanCell',
  'MocExpansionFanResult',
  'MocCompressionResult',
  'MocTopologyResult',
  'MocTopologyStatus',
  'ScalarRootResult',
  'centerline_characteristic_point',
  'characteristic_invariants',
  'interior_characteristic_point',
  'inverse_prandtl_meyer_angle_rad',
  'mach_angle_rad',
  'maximum_prandtl_meyer_angle_rad',
  'prandtl_meyer_angle_rad',
  'supersonic_mach_from_stagnation_pressure_ratio',
  'solve_underexpanded_expansion_fan',
  'solve_attached_compression_to_pressure',
  'validate_moc_mesh',
)
