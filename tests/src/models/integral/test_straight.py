from __future__ import annotations

from math import pow

import pytest

from exhaust_plume import (
    AmbientInput,
    CaloricallyPerfectGas,
    IntegralStraightConfiguration,
    NozzleExitInput,
    PlumeFluxSection,
    TerminationReason,
    continue_straight_plume,
    derive_ambient_state,
    derive_uniform_nozzle_exit,
)


def _matched_inputs() -> tuple[CaloricallyPerfectGas, PlumeFluxSection, object]:
  gas = CaloricallyPerfectGas.dry_air()
  mach = 3.0
  ambient_pressure = 100_000.0
  total_pressure = ambient_pressure * pow(1.0 + (gas.gamma - 1.0) / 2.0 * mach**2, gas.gamma / (gas.gamma - 1.0))
  exit_state = derive_uniform_nozzle_exit(NozzleExitInput(mach=mach, total_pressure_Pa=total_pressure, total_temperature_K=800.0, exit_radius_m=1.0), gas)
  ambient = derive_ambient_state(AmbientInput(pressure_Pa=ambient_pressure, temperature_K=300.0), gas)
  return gas, PlumeFluxSection.from_nozzle_exit(exit_state, ambient_pressure_Pa=ambient_pressure), ambient
####


def test_pressure_matched_zero_entrainment_preserves_conserved_state() -> None:
  gas, handoff, ambient = _matched_inputs()
  result = continue_straight_plume(
      handoff=handoff,
      ambient=ambient,
      gas=gas,
      config=IntegralStraightConfiguration(max_axial_distance_m=10.0, step_m=1.0, entrainment_coefficient=0.0),
  )

  assert result.termination_reason is TerminationReason.SPATIAL_DOMAIN_LIMIT
  assert len(result.states) == 11
  assert result.states[-1].mass_flow_rate_kg_s == pytest.approx(result.states[0].mass_flow_rate_kg_s)
  assert result.states[-1].velocity_mps == pytest.approx(result.states[0].velocity_mps)
  assert result.conservation_residuals["momentum_relative"] == pytest.approx(0.0)
  assert result.conservation_residuals["total_enthalpy_relative"] == pytest.approx(0.0)
####


def test_entrainment_increases_mass_and_reduces_velocity() -> None:
  gas, handoff, ambient = _matched_inputs()
  result = continue_straight_plume(
      handoff=handoff,
      ambient=ambient,
      gas=gas,
      config=IntegralStraightConfiguration(max_axial_distance_m=10.0, step_m=0.5, entrainment_coefficient=0.02),
  )

  assert result.states[-1].mass_flow_rate_kg_s > result.states[0].mass_flow_rate_kg_s
  assert result.states[-1].velocity_mps < result.states[0].velocity_mps
  assert abs(result.conservation_residuals["momentum_relative"]) < 1.0e-12
  assert abs(result.conservation_residuals["total_enthalpy_relative"]) < 1.0e-12
####


def test_integral_continuation_rejects_pressure_mismatch() -> None:
  gas, handoff, ambient = _matched_inputs()
  mismatched = PlumeFluxSection(
      center_plume_m=handoff.center_plume_m,
      normal_plume=handoff.normal_plume,
      area_m2=handoff.area_m2,
      mass_flow_kg_s=handoff.mass_flow_kg_s,
      momentum_flux_plume_n=handoff.momentum_flux_plume_n,
      total_enthalpy_flux_w=handoff.total_enthalpy_flux_w,
      species_mass_flow_rates_kg_s=handoff.species_mass_flow_rates_kg_s,
      pressure_Pa=handoff.pressure_Pa * 1.1,
      characteristic_radius_m=handoff.characteristic_radius_m,
  )
  with pytest.raises(ValueError):
    continue_straight_plume(
        handoff=mismatched,
        ambient=ambient,
        gas=gas,
        config=IntegralStraightConfiguration(max_axial_distance_m=1.0, step_m=1.0),
    )
  ####
####
