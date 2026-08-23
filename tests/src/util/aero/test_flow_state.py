from __future__ import annotations

import pytest

from exhaust_plume.util.aero.flow_state import FlowState


def _state() -> FlowState:
  return FlowState(
      mach=2.0,
      static_pressure=100000.0,
      static_temperature=500.0,
      static_density=100000.0 / (287.0 * 500.0),
      gamma=1.4,
  )
####


def test_specific_energy_and_enthalpy_identities() -> None:
  state = _state()
  R = state.specific_gas_constant_JpkgK
  cp = state.gamma * R / (state.gamma - 1.0)
  cv = R / (state.gamma - 1.0)
  assert state.specific_gas_work_Jpkg == pytest.approx(state.static_pressure / state.static_density)
  assert state.specific_static_internal_energy_Jpkg == pytest.approx(cv * state.static_temperature)
  assert state.specific_static_enthalpy_Jpkg == pytest.approx(cp * state.static_temperature)
  assert state.specific_total_energy_Jpkg == pytest.approx(cv * state.static_temperature + state.speed_mps**2 / 2.0)
  assert state.specific_total_enthalpy_Jpkg == pytest.approx(cp * state.total_temperature)
  assert state.specific_total_enthalpy_Jpkg == pytest.approx(
      state.specific_static_enthalpy_Jpkg + state.speed_mps**2 / 2.0
  )
####


def test_legacy_energy_alias_reports_old_meaning() -> None:
  state = _state()
  with pytest.warns(DeprecationWarning, match='historically returned'):
    legacy_value = state.legacy_specific_total_energy_Jpkg
  ####
  assert legacy_value == pytest.approx(state.total_pressure / state.total_density)
  assert legacy_value != pytest.approx(state.specific_total_energy_Jpkg)
####
