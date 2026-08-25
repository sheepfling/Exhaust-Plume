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
  MocLipShockResult,
  MocShockToCenterlineResult,
  MocTurnCompressionResult,
  solve_overexpanded_lip_shock,
  solve_attached_compression_to_pressure,
  solve_attached_compression_to_turn,
  solve_attached_shock_to_centerline,
)
from exhaust_plume.models.moc.boundary import (
  MocFreeBoundaryPointResult,
  MocFreeBoundaryResult,
  MocReflectedBoundaryResult,
  solve_ambient_pressure_free_boundary_point,
  solve_ambient_pressure_free_boundary,
  solve_reflected_free_boundary,
)
from exhaust_plume.models.moc.topology import (
  MocTopologyResult,
  MocTopologyStatus,
  validate_moc_mesh,
)
from exhaust_plume.models.moc.zone import (
  MocCharacteristicCell,
  MocCharacteristicNode,
  MocFanReflectedInterfaceResult,
  MocInterfaceStatus,
  MocReflectedCharacteristicZoneResult,
  MocZoneAssemblyStatus,
  assemble_reflected_characteristic_zone,
  validate_fan_reflected_interface,
)

__all__ = (
  'CharacteristicFamily',
  'CharacteristicPointResult',
  'CharacteristicState',
  'MocPrimitiveStatus',
  'MocExpansionFanCell',
  'MocExpansionFanResult',
  'MocCompressionResult',
  'MocLipShockResult',
  'MocShockToCenterlineResult',
  'MocTurnCompressionResult',
  'MocFreeBoundaryResult',
  'MocFreeBoundaryPointResult',
  'MocReflectedBoundaryResult',
  'MocTopologyResult',
  'MocTopologyStatus',
  'MocCharacteristicCell',
  'MocCharacteristicNode',
  'MocFanReflectedInterfaceResult',
  'MocInterfaceStatus',
  'MocReflectedCharacteristicZoneResult',
  'MocZoneAssemblyStatus',
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
  'solve_attached_compression_to_turn',
  'solve_attached_shock_to_centerline',
  'solve_overexpanded_lip_shock',
  'solve_ambient_pressure_free_boundary',
  'solve_ambient_pressure_free_boundary_point',
  'solve_reflected_free_boundary',
  'assemble_reflected_characteristic_zone',
  'validate_fan_reflected_interface',
  'validate_moc_mesh',
)
