from __future__ import annotations

from math import pow

import pytest

from exhaust_plume import AmbientInput, CaloricallyPerfectGas, NozzleExitInput, derive_ambient_state, derive_uniform_nozzle_exit
from exhaust_plume.contracts import CapabilityId, ProviderClosedError, TerminationReason, UnsupportedCapabilityError
from exhaust_plume.providers import (
    ShockCellAnalyticalConfiguration,
    ShockCellAnalyticalDefinition,
    ShockCellAnalyticalOperatingState,
    ShockCellAnalyticalProvider,
)


def _operating_state(exit_pressure_ratio: float = 1.1) -> ShockCellAnalyticalOperatingState:
  gas = CaloricallyPerfectGas.dry_air()
  mach = 3.0
  ambient_pressure = 100_000.0
  total_pressure = ambient_pressure * exit_pressure_ratio * pow(1.0 + (gas.gamma - 1.0) / 2.0 * mach**2, gas.gamma / (gas.gamma - 1.0))
  exit_state = derive_uniform_nozzle_exit(NozzleExitInput(mach=mach, total_pressure_Pa=total_pressure, total_temperature_K=800.0, exit_radius_m=1.0), gas)
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=ambient_pressure, temperature_K=300.0), gas)
  return ShockCellAnalyticalOperatingState(nozzle_exit=exit_state, ambient=ambient)


def test_provider_descriptor_advertises_only_straight_spatial_capabilities() -> None:
  provider = ShockCellAnalyticalProvider()
  assert provider.descriptor.morphology.value == "straight"
  assert set(provider.descriptor.capability_versions) == {
      CapabilityId.SPATIAL_SUPPORT,
      CapabilityId.AXISYMMETRIC_ZONE_FIELD,
      CapabilityId.PROJECTED_AREA,
  }
  assert CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY not in provider.descriptor.capability_versions
  ####


def test_provider_snapshot_matches_direct_straight_solver_and_has_finite_zones() -> None:
  provider = ShockCellAnalyticalProvider()
  session = provider.create_session(
      ShockCellAnalyticalDefinition(nozzle_radius_m=1.0),
      ShockCellAnalyticalConfiguration(maximum_construction_passes=1),
  )
  snapshot = session.snapshot(_operating_state())
  field = snapshot.get_capability(CapabilityId.AXISYMMETRIC_ZONE_FIELD, 1)
  assert field.zones
  assert all(zone.polygon_xr_m.flags.writeable is False for zone in field.zones)
  assert snapshot.termination is not None
  assert snapshot.termination.reason is TerminationReason.REQUESTED_CONSTRUCTION_LIMIT
  assert snapshot.termination.is_physical is False
  assert snapshot.provenance.metadata["regime"] == "underexpanded"
  with pytest.raises(UnsupportedCapabilityError):
    snapshot.get_capability(CapabilityId.DIRECTIONAL_SPECTRAL_INTENSITY, 1)
  ####


def test_provider_matched_state_has_no_cells_and_close_is_enforced() -> None:
  state = _operating_state(1.0)
  provider = ShockCellAnalyticalProvider()
  session = provider.create_session(ShockCellAnalyticalDefinition(nozzle_radius_m=1.0), ShockCellAnalyticalConfiguration())
  snapshot = session.snapshot(state)
  field = snapshot.get_capability(CapabilityId.AXISYMMETRIC_ZONE_FIELD, 1)
  assert field.zones == ()
  assert snapshot.termination is not None
  assert snapshot.termination.reason is TerminationReason.NO_PRESSURE_MISMATCH
  session.close()
  with pytest.raises(ProviderClosedError):
    session.snapshot(state)
  ####
