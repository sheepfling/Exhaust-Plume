# -*- coding: utf-8 -*-
r"""
These functions calculate the total and static properties of a gas assuming isentropic expansion/compression

Modern Compressible Flow: With Historical Perspective 3rd Edition
- https://archive.org/details/5f-36b-7c-4ded-79bb-3e-90754d-0f-81682f-7a-68014be
- https://web.archive.org/web/20221006024847/https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
- https://icourse.club/uploads/files/5f36b7c4ded79bb3e90754d0f81682f7a68014be.pdf
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from functools import cached_property
from warnings import warn

from numpy import deg2rad, ndarray

from exhaust_plume.util.aero.isentropic_flow import calcIsentropicTotalDensity, calcIsentropicTotalPressure, calcIsentropicTotalTemperature
from exhaust_plume.util.aero.misc import calcMachAngle
from exhaust_plume.util.aero.speed_of_sound import calculateSpeedOfSoundInGas
from exhaust_plume.util.comparison import dataclassIsClose, dataclassIsEqual
from exhaust_plume.util.numeric import ATOL_DEFAULT, EQUAL_NAN_DEFAULT, RTOL_DEFAULT

__all__ = (
    'FlowState',
)
@dataclass(frozen=True)
class FlowState:
  mach: float  # number
  static_pressure: float  # Pascal
  static_temperature: float  # K
  static_density: float  # kg/m^3
  gamma: float

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if isinstance(v, ndarray):
        v.flags.writeable = False
      ####
    ####
  ####

  @cached_property
  def total_pressure(self) -> float:
    p_total = calcIsentropicTotalPressure(mach=self.mach, static_pressure=self.static_pressure, gamma=self.gamma)
    return p_total
  ####

  @cached_property
  def total_temperature(self) -> float:
    T_total = calcIsentropicTotalTemperature(mach=self.mach, static_temperature=self.static_temperature, gamma=self.gamma)
    return T_total
  ####

  @cached_property
  def total_density(self) -> float:
    rho_total = calcIsentropicTotalDensity(mach=self.mach, static_density=self.static_density, gamma=self.gamma)
    return rho_total
  ####

  @cached_property
  def mach_line_deg(self) -> float:
    return calcMachAngle(self.mach)
  ####

  @cached_property
  def mach_line_rad(self) -> float:
    return deg2rad(self.mach_line_deg)
  ####

  @cached_property
  def speed_of_sound_mps(self) -> float:
    return calculateSpeedOfSoundInGas(
        pressure_Pa=self.static_pressure,
        density_kgpm3=self.static_density,
        adiabatic_index=self.gamma,
    )
  ####

  @cached_property
  def speed_mps(self) -> float:
    return self.mach * self.speed_of_sound_mps
  ####

  @cached_property
  def specific_gas_constant_JpkgK(self) -> float:
    """Infer the explicit gas constant from the complete static state."""

    return self.static_pressure / (self.static_density * self.static_temperature)
  ####

  @cached_property
  def specific_gas_work_Jpkg(self) -> float:
    """Return p/rho, the ideal-gas specific work scale."""

    return self.static_pressure / self.static_density
  ####

  @cached_property
  def specific_static_internal_energy_Jpkg(self) -> float:
    """Return e = c_v T for a calorically-perfect gas."""

    cv = self.specific_gas_constant_JpkgK / (self.gamma - 1.0)
    return cv * self.static_temperature
  ####

  @cached_property
  def specific_static_enthalpy_Jpkg(self) -> float:
    """Return h = c_p T for a calorically-perfect gas."""

    cp = self.gamma * self.specific_gas_constant_JpkgK / (self.gamma - 1.0)
    return cp * self.static_temperature
  ####

  @cached_property
  def specific_total_energy_Jpkg(self) -> float:
    """Return E = c_v T + u^2/2, the corrected total specific energy."""

    return self.specific_static_internal_energy_Jpkg + self.speed_mps**2 / 2.0
  ####

  @cached_property
  def specific_total_enthalpy_Jpkg(self) -> float:
    """Return h0 = c_p T0 for a calorically-perfect gas."""

    cp = self.gamma * self.specific_gas_constant_JpkgK / (self.gamma - 1.0)
    return cp * self.total_temperature
  ####

  @property
  def legacy_specific_total_energy_Jpkg(self) -> float:
    """Return the pre-FND-B RT0 value through an explicit compatibility alias."""

    warn(
        'legacy_specific_total_energy_Jpkg historically returned p0/rho0 = R*T0; '
        'use specific_total_energy_Jpkg or specific_total_enthalpy_Jpkg instead',
        DeprecationWarning,
        stacklevel=2,
    )
    return self.total_pressure / self.total_density
  ####

  def isClose(self, other: object, rtol: float = RTOL_DEFAULT, atol: float = ATOL_DEFAULT, equal_nan: bool = EQUAL_NAN_DEFAULT) -> bool:
    return dataclassIsClose(self, other, rtol=rtol, atol=atol, equal_nan=equal_nan)
  ####

  def __eq__(self, other: object) -> bool:
    return dataclassIsEqual(self, other)
  ####

  def __hash__(self) -> int:
    tup = tuple(x.data.tobytes() if isinstance(x, ndarray) else x for x in (
        getattr(self, f.name) for f in fields(self)
    ))
    return hash(tup)
  ####
####
