"""Conservative handoff quantities between straight plume providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, isfinite, pi, sin, sqrt
from types import MappingProxyType
from typing import Mapping

from exhaust_plume.models.nozzle.contracts import NozzleExitState

__all__ = ("PlumeFluxSection",)


@dataclass(frozen=True, slots=True)
class PlumeFluxSection:
  """Area-averaged conservative section state for a downstream handoff."""

  center_plume_m: tuple[float, float, float]
  normal_plume: tuple[float, float, float]
  area_m2: float
  mass_flow_kg_s: float
  momentum_flux_plume_n: tuple[float, float, float]
  total_enthalpy_flux_w: float
  species_mass_flow_rates_kg_s: tuple[tuple[str, float], ...]
  pressure_Pa: float
  characteristic_radius_m: float
  provider_metadata: Mapping[str, object] = field(default_factory=dict)

  def __post_init__(self) -> None:
    center = tuple(float(value) for value in self.center_plume_m)
    normal = tuple(float(value) for value in self.normal_plume)
    momentum = tuple(float(value) for value in self.momentum_flux_plume_n)
    if len(center) != 3 or len(normal) != 3 or len(momentum) != 3:
      raise ValueError("center, normal, and momentum vectors must have three components")
    ####
    if any(not isfinite(value) for value in (*center, *normal, *momentum)):
      raise ValueError("handoff vectors must be finite")
    ####
    normal_norm = sqrt(sum(value**2 for value in normal))
    if not isfinite(normal_norm) or normal_norm <= 0.0 or abs(normal_norm - 1.0) > 1.0e-8:
      raise ValueError("normal_plume must be a finite unit vector")
    ####
    for name, value in (
        ("area_m2", self.area_m2),
        ("mass_flow_kg_s", self.mass_flow_kg_s),
        ("total_enthalpy_flux_w", self.total_enthalpy_flux_w),
        ("pressure_Pa", self.pressure_Pa),
        ("characteristic_radius_m", self.characteristic_radius_m),
    ):
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
      ####
    ####
    species = tuple((str(name), float(rate)) for name, rate in self.species_mass_flow_rates_kg_s)
    if any(not name or not isfinite(rate) or rate < 0.0 for name, rate in species):
      raise ValueError("species mass-flow rates must be finite and non-negative")
    ####
    object.__setattr__(self, "center_plume_m", center)
    object.__setattr__(self, "normal_plume", normal)
    object.__setattr__(self, "momentum_flux_plume_n", momentum)
    object.__setattr__(self, "species_mass_flow_rates_kg_s", species)
    object.__setattr__(self, "provider_metadata", MappingProxyType(dict(self.provider_metadata)))
  ####

  @property
  def species_mass_flow_kg_s(self) -> tuple[tuple[str, float], ...]:
    return self.species_mass_flow_rates_kg_s
  ####

  @classmethod
  def from_nozzle_exit(cls, exit_state: NozzleExitState, *, ambient_pressure_Pa: float) -> PlumeFluxSection:
    """Build a pressure-aware handoff from a uniform explicit exit state."""

    if not isfinite(ambient_pressure_Pa) or ambient_pressure_Pa <= 0.0:
      raise ValueError("ambient_pressure_Pa must be finite and positive")
    ####
    gas = exit_state.gas
    area = pi * exit_state.radius_m**2
    speed = exit_state.velocity_mps
    flow_angle = exit_state.flow_angle_rad
    normal = (cos(flow_angle), sin(flow_angle), 0.0)
    velocity = (speed * normal[0], speed * normal[1], 0.0)
    momentum = (
        exit_state.mass_flow_rate_kgps * velocity[0] + (exit_state.static_pressure_Pa - ambient_pressure_Pa) * area * normal[0],
        exit_state.mass_flow_rate_kgps * velocity[1] + (exit_state.static_pressure_Pa - ambient_pressure_Pa) * area * normal[1],
        exit_state.mass_flow_rate_kgps * velocity[2] + (exit_state.static_pressure_Pa - ambient_pressure_Pa) * area * normal[2],
    )
    species = tuple((item.species, exit_state.mass_flow_rate_kgps * item.mass_fraction) for item in gas.species_mass_fractions)
    return cls(
        center_plume_m=(0.0, 0.0, 0.0),
        normal_plume=normal,
        area_m2=area,
        mass_flow_kg_s=exit_state.mass_flow_rate_kgps,
        momentum_flux_plume_n=momentum,
        total_enthalpy_flux_w=exit_state.mass_flow_rate_kgps * gas.specific_heat_pressure_JpkgK * exit_state.total_temperature_K,
        species_mass_flow_rates_kg_s=species,
        pressure_Pa=exit_state.static_pressure_Pa,
        characteristic_radius_m=exit_state.radius_m,
        provider_metadata={"source": "uniform-nozzle-exit", "gamma": str(gas.gamma)},
    )
  ####
####
