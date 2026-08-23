from __future__ import annotations

import pytest

from exhaust_plume.models.nozzle.area_mach import (
    MachBranch,
    calc_area_mach_ratio,
    calc_choked_throat_area,
    calc_mass_flow_rate,
    solve_mach_from_area_ratio,
)


def test_sonic_area_ratio_is_one() -> None:
  assert calc_area_mach_ratio(1.0, 1.4) == pytest.approx(1.0)
  assert solve_mach_from_area_ratio(1.0, 1.4, MachBranch.SUBSONIC) == 1.0
  assert solve_mach_from_area_ratio(1.0, 1.4, MachBranch.SUPERSONIC) == 1.0
  ####
####


@pytest.mark.parametrize('mach', (0.3, 0.7, 1.5, 2.5, 4.0))
def test_area_mach_round_trip_on_both_branches(mach: float) -> None:
  area_ratio = calc_area_mach_ratio(mach, 1.4)
  branch = MachBranch.SUBSONIC if mach < 1.0 else MachBranch.SUPERSONIC
  recovered = solve_mach_from_area_ratio(area_ratio, 1.4, branch)
  assert recovered == pytest.approx(mach, rel=1.0e-8, abs=1.0e-10)
  ####
####


def test_area_ratio_requires_explicitly_valid_branch_domain() -> None:
  with pytest.raises(ValueError):
    solve_mach_from_area_ratio(0.99, 1.4, MachBranch.SUPERSONIC)
  with pytest.raises(ValueError):
    calc_area_mach_ratio(0.0, 1.4)
  ####
####


def test_choked_area_and_mass_flow_are_inverses() -> None:
  gamma = 1.33
  R = 377.93
  mass_flow = 4.5
  pressure = 3.2e6
  temperature = 1400.0
  throat_area = calc_choked_throat_area(
      mass_flow_rate_kgps=mass_flow,
      total_pressure_Pa=pressure,
      total_temperature_K=temperature,
      gamma=gamma,
      specific_gas_constant_JpkgK=R,
  )
  reconstructed = calc_mass_flow_rate(
      area_m2=throat_area,
      mach=1.0,
      total_pressure_Pa=pressure,
      total_temperature_K=temperature,
      gamma=gamma,
      specific_gas_constant_JpkgK=R,
  )
  assert reconstructed == pytest.approx(mass_flow, rel=1.0e-12)
  ####
####
