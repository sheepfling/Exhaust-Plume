"""Conservative straight top-hat continuation with explicit domain termination."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, pi, sqrt
from types import MappingProxyType
from typing import Mapping

from exhaust_plume.contracts.handoff import PlumeFluxSection
from exhaust_plume.models.gas.calorically_perfect import CaloricallyPerfectGas
from exhaust_plume.models.nozzle.contracts import AmbientState
from exhaust_plume.contracts.snapshot import TerminationReason

__all__ = (
    "IntegralStraightConfiguration",
    "IntegralStraightResult",
    "IntegralStraightState",
    "continue_straight_plume",
)
###########################################


@dataclass(frozen=True, slots=True)
class IntegralStraightConfiguration:
  max_axial_distance_m: float
  step_m: float
  entrainment_coefficient: float = 0.0
  pressure_match_rtol: float = 1.0e-4
  max_steps: int = 10_000

  def __post_init__(self) -> None:
    for name, value in (
        ("max_axial_distance_m", self.max_axial_distance_m),
        ("step_m", self.step_m),
        ("pressure_match_rtol", self.pressure_match_rtol),
    ):
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    if not isfinite(self.entrainment_coefficient) or self.entrainment_coefficient < 0.0:
      raise ValueError("entrainment_coefficient must be finite and non-negative")
    if isinstance(self.max_steps, bool) or self.max_steps < 1:
      raise ValueError("max_steps must be an integer >= 1")
  ####


@dataclass(frozen=True, slots=True)
class IntegralStraightState:
  x_m: float
  mass_flow_rate_kg_s: float
  momentum_flux_N: float
  total_enthalpy_flux_W: float
  velocity_mps: float
  temperature_K: float
  pressure_Pa: float
  density_kgpm3: float
  radius_m: float
  species_mass_fractions: tuple[tuple[str, float], ...]

  def __post_init__(self) -> None:
    for name, value in (
        ("x_m", self.x_m),
        ("mass_flow_rate_kg_s", self.mass_flow_rate_kg_s),
        ("momentum_flux_N", self.momentum_flux_N),
        ("total_enthalpy_flux_W", self.total_enthalpy_flux_W),
        ("velocity_mps", self.velocity_mps),
        ("temperature_K", self.temperature_K),
        ("pressure_Pa", self.pressure_Pa),
        ("density_kgpm3", self.density_kgpm3),
        ("radius_m", self.radius_m),
    ):
      if not isfinite(value) or (name != "x_m" and value <= 0.0) or (name == "x_m" and value < 0.0):
        raise ValueError(f"{name} must be finite and positive")
    species = tuple((str(name), float(value)) for name, value in self.species_mass_fractions)
    if any(not name or not isfinite(value) or value < 0.0 for name, value in species):
      raise ValueError("species mass fractions must be finite and non-negative")
    total = sum(value for _, value in species)
    if species and abs(total - 1.0) > 1.0e-8:
      raise ValueError("species mass fractions must sum to one")
    object.__setattr__(self, "species_mass_fractions", species)
  ####


@dataclass(frozen=True, slots=True)
class IntegralStraightResult:
  states: tuple[IntegralStraightState, ...]
  termination_reason: TerminationReason
  termination_x_m: float
  termination_is_physical: bool
  conservation_residuals: Mapping[str, float]

  def __post_init__(self) -> None:
    if not self.states:
      raise ValueError("IntegralStraightResult requires at least one valid state")
    object.__setattr__(self, "states", tuple(self.states))
    object.__setattr__(self, "conservation_residuals", MappingProxyType(dict(self.conservation_residuals)))
  ####


def _species_fractions(mass_rates: Mapping[str, float], mass_flow: float) -> tuple[tuple[str, float], ...]:
  if not mass_rates:
    return ()
  return tuple(sorted((name, rate / mass_flow) for name, rate in mass_rates.items() if rate > 0.0))
  ####


def continue_straight_plume(*, handoff: PlumeFluxSection, ambient: AmbientState, gas: CaloricallyPerfectGas, config: IntegralStraightConfiguration) -> IntegralStraightResult:
  """Continue a pressure-matched handoff with a frozen top-hat closure.

  Momentum flux is held constant, ambient mass/enthalpy are entrained, and
  pressure remains equal to the ambient pressure.  The finite axial domain is
  a requested truncation, not a physical plume endpoint.
  """

  pressure_residual = abs(handoff.pressure_Pa - ambient.pressure_Pa) / ambient.pressure_Pa
  if pressure_residual > config.pressure_match_rtol:
    raise ValueError("straight integral continuation requires a pressure-matched handoff")
  if handoff.normal_plume[0] <= 0.0:
    raise ValueError("straight integral continuation requires a forward axial handoff")
  mass = handoff.mass_flow_kg_s
  momentum = float(handoff.momentum_flux_plume_n[0])
  enthalpy = handoff.total_enthalpy_flux_w
  ambient_velocity = float(ambient.velocity_xyz_mps[0])
  ambient_h0 = gas.specific_heat_pressure_JpkgK * ambient.temperature_K + ambient_velocity**2 / 2.0
  mass_rates = {name: rate for name, rate in handoff.species_mass_flow_rates_kg_s}
  ambient_fractions = {item.species: item.mass_fraction for item in ambient.species_mass_fractions}
  if not mass_rates and ambient_fractions:
    mass_rates = {name: 0.0 for name in ambient_fractions}

  def make_state(x_m: float, mass_flow: float, momentum_flux: float, enthalpy_flux: float, species_rates: Mapping[str, float]) -> IntegralStraightState:
    velocity = momentum_flux / mass_flow
    total_enthalpy = enthalpy_flux / mass_flow
    temperature = (total_enthalpy - velocity**2 / 2.0) / gas.specific_heat_pressure_JpkgK
    if not isfinite(temperature) or temperature <= 0.0:
      raise ValueError("integral continuation produced a non-positive temperature")
    density = ambient.pressure_Pa / (gas.specific_gas_constant_JpkgK * temperature)
    area = mass_flow / (density * velocity)
    if not isfinite(area) or area <= 0.0:
      raise ValueError("integral continuation produced a non-positive area")
    radius = sqrt(area / pi)
    return IntegralStraightState(
        x_m=x_m,
        mass_flow_rate_kg_s=mass_flow,
        momentum_flux_N=momentum_flux,
        total_enthalpy_flux_W=enthalpy_flux,
        velocity_mps=velocity,
        temperature_K=temperature,
        pressure_Pa=ambient.pressure_Pa,
        density_kgpm3=density,
        radius_m=radius,
        species_mass_fractions=_species_fractions(species_rates, mass_flow),
    )

  states = [make_state(0.0, mass, momentum, enthalpy, mass_rates)]
  x = 0.0
  steps = 0
  try:
    while x < config.max_axial_distance_m and steps < config.max_steps:
      state = states[-1]
      distance = min(config.step_m, config.max_axial_distance_m - x)
      entrainment_rate = 2.0 * pi * state.radius_m * ambient.density_kgpm3 * config.entrainment_coefficient * abs(state.velocity_mps - ambient_velocity)
      entrained_mass = max(0.0, entrainment_rate * distance)
      mass += entrained_mass
      enthalpy += ambient_h0 * entrained_mass
      for name, fraction in ambient_fractions.items():
        mass_rates[name] = mass_rates.get(name, 0.0) + fraction * entrained_mass
      x += distance
      states.append(make_state(x, mass, momentum, enthalpy, mass_rates))
      steps += 1
  except ValueError:
    residuals = {"momentum_relative": 0.0, "total_enthalpy_relative": 0.0}
    return IntegralStraightResult(tuple(states), TerminationReason.PROVIDER_FAILURE, x, False, residuals)
  reason = TerminationReason.SPATIAL_DOMAIN_LIMIT if x >= config.max_axial_distance_m else TerminationReason.REQUESTED_CONSTRUCTION_LIMIT
  expected_enthalpy = states[0].total_enthalpy_flux_W + ambient_h0 * (states[-1].mass_flow_rate_kg_s - states[0].mass_flow_rate_kg_s)
  residuals = {
      "momentum_relative": (states[-1].momentum_flux_N - states[0].momentum_flux_N) / max(1.0, abs(states[0].momentum_flux_N)),
      "total_enthalpy_relative": (states[-1].total_enthalpy_flux_W - expected_enthalpy) / max(1.0, abs(expected_enthalpy)),
  }
  return IntegralStraightResult(tuple(states), reason, x, False, residuals)
  ####
