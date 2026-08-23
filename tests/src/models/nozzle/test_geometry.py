from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from exhaust_plume.models.gas import CaloricallyPerfectGas
from exhaust_plume.models.nozzle import (
  MachBranch,
  NozzleGeometry,
  ThroatConfiguration,
  derive_nozzle_exit_from_geometry,
)
from exhaust_plume.models.nozzle.area_mach import calc_area_mach_ratio, calc_mass_flow_rate

ROOT = Path(__file__).resolve().parents[4]


def _geometry(area_ratio: float, throat_area_m2: float = 1.0e-2) -> NozzleGeometry:
  return NozzleGeometry(
    geometry_id=f'circular-ratio-{area_ratio:g}',
    throat=ThroatConfiguration(area_m2=throat_area_m2),
    exit_area_m2=throat_area_m2 * area_ratio,
  )
####


@pytest.mark.parametrize('area_ratio', (2.0, 4.0, 9.0, 25.0))
@pytest.mark.parametrize('gamma', (1.2, 1.4, 1.67))
def test_geometry_derivation_round_trips_area_ratio_and_choked_mass_flow(area_ratio: float, gamma: float) -> None:
  gas = CaloricallyPerfectGas.dry_air(gamma=gamma)
  geometry = _geometry(area_ratio)
  state = derive_nozzle_exit_from_geometry(
    geometry,
    total_pressure_Pa=2.0e6,
    total_temperature_K=1000.0,
    gas=gas,
  )

  assert calc_area_mach_ratio(state.mach, gamma) == pytest.approx(area_ratio, rel=1.0e-9)
  throat_mass_flow = calc_mass_flow_rate(
    area_m2=geometry.throat.area_m2,
    mach=1.0,
    total_pressure_Pa=2.0e6,
    total_temperature_K=1000.0,
    gamma=gamma,
    specific_gas_constant_JpkgK=gas.specific_gas_constant_JpkgK,
  )
  assert state.mass_flow_rate_kgps == pytest.approx(throat_mass_flow, rel=2.0e-8)
  assert state.source_kind.value == 'derived-isentropic'
####


def test_geometry_rejects_non_supersonic_area_order_and_nonzero_turn() -> None:
  with pytest.raises(ValidationError):
    NozzleGeometry(
      throat=ThroatConfiguration(area_m2=1.0),
      exit_area_m2=1.0,
    )
  ####
  with pytest.raises(ValueError, match='zero exit flow angle'):
    derive_nozzle_exit_from_geometry(
      _geometry(4.0),
      total_pressure_Pa=2.0e6,
      total_temperature_K=1000.0,
      gas=CaloricallyPerfectGas.dry_air(),
      flow_angle_rad=0.01,
    )
  ####
  with pytest.raises(ValueError, match='supersonic branch'):
    derive_nozzle_exit_from_geometry(
      _geometry(4.0),
      total_pressure_Pa=2.0e6,
      total_temperature_K=1000.0,
      gas=CaloricallyPerfectGas.dry_air(),
      branch=MachBranch.SUBSONIC,
    )
  ####
####


def test_isentropic_reference_fixture_regresses_independent_relations() -> None:
  fixture = json.loads((ROOT / 'tests/fixtures/validity/isentropic_reference_v1.json').read_text(encoding='utf-8'))
  gas = CaloricallyPerfectGas.dry_air(gamma=fixture['gamma'])
  for reference in fixture['cases']:
    mach = derive_nozzle_exit_from_geometry(
      _geometry(reference['area_ratio']),
      total_pressure_Pa=2.0e6,
      total_temperature_K=1000.0,
      gas=gas,
    ).mach
    assert mach == pytest.approx(reference['supersonic_mach'], rel=1.0e-8)
    assert gas.static_pressure_from_total(mach, 1.0) == pytest.approx(reference['static_pressure_fraction'], rel=1.0e-8)
    assert gas.static_temperature_from_total(mach, 1.0) == pytest.approx(reference['static_temperature_fraction'], rel=1.0e-8)
  ####
####
