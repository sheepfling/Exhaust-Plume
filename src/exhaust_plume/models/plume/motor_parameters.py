# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, fields
from functools import cached_property

from numpy import isfinite, pi

from exhaust_plume.models.nozzle.area_mach import MachBranch, calc_choked_throat_area, solve_mach_from_area_ratio
from exhaust_plume.util.aero.ideal_gas import calcSpecificGasConstant
from exhaust_plume.util.aero.isentropic_flow import calcIsentropicStaticDensity, calcIsentropicStaticPressure, calcIsentropicStaticTemperature
from exhaust_plume.util.numeric import ATOL_DEFAULT, RTOL_DEFAULT

__all__ = (
    'calcAreaThroatGivenMassFlowRateTotalTemperaturePressure',
    'calcMachGivenAreaRatioGamma',
    'EngineParameters',
)
###########################################


def calcMachGivenAreaRatioGamma(
    area_exit: float,
    area_throat: float,
    gamma: float,
    rtol: float = RTOL_DEFAULT,
    atol: float = ATOL_DEFAULT,
    max_iter: int = 200,
) -> float:
  """Legacy supersonic wrapper around the branch-explicit area--Mach solver."""

  area_ratio = area_exit / area_throat
  return solve_mach_from_area_ratio(
      area_ratio=float(area_ratio),
      gamma=gamma,
      branch=MachBranch.SUPERSONIC,
      rtol=rtol,
      atol=atol,
      max_iter=max_iter,
  )
##


def calcAreaThroatGivenMassFlowRateTotalTemperaturePressure(
    mdot_kgps: float,
    total_pressure_Pa: float,
    total_temperature_K: float,
    gamma: float,
    molar_mass_kg: float,
) -> float:
  """Legacy wrapper for the corrected choked throat-area equation."""

  specific_gas_constant_JpkgK = calcSpecificGasConstant(molar_mass_kg=molar_mass_kg)
  return calc_choked_throat_area(
      mass_flow_rate_kgps=mdot_kgps,
      total_pressure_Pa=total_pressure_Pa,
      total_temperature_K=total_temperature_K,
      gamma=gamma,
      specific_gas_constant_JpkgK=specific_gas_constant_JpkgK,
  )
##


@dataclass(frozen=True)
class EngineParameters:
  mass_flow_rate_kgps: float
  exit_radius_m: float
  total_pressure_Pa: float
  total_temperature_K: float
  gamma: float
  molar_mass_kg: float

  def __post_init__(self) -> None:
    for f in fields(self):
      v = getattr(self, f.name)
      if v is None or v <= 0 or not isfinite(v):
        raise ValueError(f'Expected `{f.name}` to be positive. Got:{v}')
      ##
    ##
    if self.gamma <= 1.:
      raise ValueError(f'Expected `gamma` to be greater than 1. Got:{self.gamma}')
    ##
  ##

  @cached_property
  def exit_area_m2(self) -> float:
    return pi * self.exit_radius_m**2.
  ##

  @cached_property
  def throat_area_m2(self) -> float:
    return calcAreaThroatGivenMassFlowRateTotalTemperaturePressure(
        mdot_kgps=self.mass_flow_rate_kgps,
        total_pressure_Pa=self.total_pressure_Pa,
        total_temperature_K=self.total_temperature_K,
        molar_mass_kg=self.molar_mass_kg,
        gamma=self.gamma,
    )
  ##

  @cached_property
  def exit_mach(self) -> float:
    return calcMachGivenAreaRatioGamma(
        area_throat=self.throat_area_m2,
        area_exit=self.exit_area_m2,
        gamma=self.gamma,
    )
  ##

  @cached_property
  def total_density_kgpm3(self) -> float:
    specific_gas_constant_JpkgK = calcSpecificGasConstant(molar_mass_kg=self.molar_mass_kg)
    return self.total_pressure_Pa / (specific_gas_constant_JpkgK * self.total_temperature_K)
  ##

  @cached_property
  def total_density_kgps(self) -> float:
    """Compatibility alias for the old unit-inaccurate property name."""

    return self.total_density_kgpm3
  ##

  @cached_property
  def static_pressure_Pa(self) -> float:
    return calcIsentropicStaticPressure(
        mach=self.exit_mach,
        total_pressure=self.total_pressure_Pa,
        gamma=self.gamma,
    )
  ##

  @cached_property
  def static_temperature_K(self) -> float:
    return calcIsentropicStaticTemperature(
        mach=self.exit_mach,
        total_temperature=self.total_temperature_K,
        gamma=self.gamma,
    )
  ##

  @cached_property
  def static_density_kgpm3(self) -> float:
    return calcIsentropicStaticDensity(
        mach=self.exit_mach,
        total_density=self.total_density_kgpm3,
        gamma=self.gamma,
    )
  ##

  @cached_property
  def static_density_kpgs(self) -> float:
    """Compatibility alias for the old unit-inaccurate property name."""

    return self.static_density_kgpm3
  ##
##
