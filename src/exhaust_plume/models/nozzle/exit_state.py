"""Canonical derivation of uniform nozzle-exit and ambient states."""

from __future__ import annotations

from math import cos, isclose

from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.nozzle.contracts import AmbientInput, AmbientState, NozzleExitInput, NozzleExitState


def derive_uniform_nozzle_exit(config: NozzleExitInput, gas: CaloricallyPerfectGas) -> NozzleExitState:
  """Derive a uniform supersonic exit state from total conditions.

  The equations are the calorically-perfect stagnation relations and
  ``rho = p/(R*T)``. Inputs are SI units and ``flow_angle_rad`` is radians.
  """

  static_temperature_K = gas.static_temperature_from_total(config.mach, config.total_temperature_K)
  static_pressure_Pa = gas.static_pressure_from_total(config.mach, config.total_pressure_Pa)
  density_kgpm3 = gas.density_from_pressure_temperature(static_pressure_Pa, static_temperature_K)
  velocity_mps = gas.velocity_mps(config.mach, static_temperature_K)
  axial_velocity_mps = velocity_mps * cos(config.flow_angle_rad)
  if axial_velocity_mps <= 0.0:
    raise ValueError('flow_angle_rad must produce positive axial velocity')
  ####
  mass_flow_rate_kgps = density_kgpm3 * axial_velocity_mps * (3.141592653589793 * config.exit_radius_m**2)
  if config.mass_flow_rate_kg_per_s is not None and not isclose(
      config.mass_flow_rate_kg_per_s,
      mass_flow_rate_kgps,
      rel_tol=1.0e-8,
      abs_tol=1.0e-12,
  ):
    raise ValueError(
        f'supplied mass flow {config.mass_flow_rate_kg_per_s} does not match derived mass flow {mass_flow_rate_kgps}'
    )
  ####
  return NozzleExitState(
      static_pressure_Pa=static_pressure_Pa,
      static_temperature_K=static_temperature_K,
      mach=config.mach,
      density_kgpm3=density_kgpm3,
      axial_velocity_mps=axial_velocity_mps,
      flow_angle_rad=config.flow_angle_rad,
      radius_m=config.exit_radius_m,
      mass_flow_rate_kgps=mass_flow_rate_kgps,
      total_pressure_Pa=config.total_pressure_Pa,
      total_temperature_K=config.total_temperature_K,
      gas=gas,
      species_mass_fractions=gas.species_mass_fractions,
  )
####


def derive_ambient_state(config: AmbientInput, gas: CaloricallyPerfectGas) -> AmbientState:
  """Resolve ambient density from explicit pressure, temperature, and gas."""

  density_kgpm3 = gas.density_from_pressure_temperature(config.pressure_Pa, config.temperature_K)
  species = config.species_mass_fractions or gas.species_mass_fractions
  return AmbientState(
      pressure_Pa=config.pressure_Pa,
      temperature_K=config.temperature_K,
      density_kgpm3=density_kgpm3,
      velocity_xyz_mps=(config.velocity_x_m_per_s, config.velocity_y_m_per_s, config.velocity_z_m_per_s),
      species_mass_fractions=species,
      geopotential_altitude_m=config.geopotential_altitude_m,
  )
####
