from __future__ import annotations

from unittest import TestCase

from numpy import deg2rad, isclose, sin, sqrt
from numpy.testing import assert_allclose

from exhaust_plume.util.aero.ideal_gas import calcSpecificGasConstant
from exhaust_plume.util.aero.isentropic_flow import (
    calcIsentropicStaticDensity,
    calcIsentropicStaticPressure,
    calcIsentropicStaticTemperature,
    calcIsentropicTotalDensity,
    calcIsentropicTotalPressure,
    calcIsentropicTotalTemperature,
)
from exhaust_plume.util.aero.normal_shock import (
    calcNormalShockMach,
    calcNormalShockStaticDensity,
    calcNormalShockStaticPressure,
    calcNormalShockStaticTemperature,
)
from exhaust_plume.util.aero.oblique_shock import ObliqueShockState
from exhaust_plume.util.atmosphere.constants import MOLAR_MASS_DRY_AIR_kg


class TestConservation(TestCase):
  gamma = 1.4
  R = calcSpecificGasConstant(molar_mass_kg=MOLAR_MASS_DRY_AIR_kg)

  def test_isentropic_round_trip_preserves_static_and_total_properties(self) -> None:
    mach = 3.
    total_pressure = 500.e3
    total_temperature = 1200.
    total_density = total_pressure / (self.R * total_temperature)

    static_pressure = calcIsentropicStaticPressure(mach=mach, total_pressure=total_pressure, gamma=self.gamma)
    static_temperature = calcIsentropicStaticTemperature(mach=mach, total_temperature=total_temperature, gamma=self.gamma)
    static_density = calcIsentropicStaticDensity(mach=mach, total_density=total_density, gamma=self.gamma)

    assert_allclose(calcIsentropicTotalPressure(mach=mach, static_pressure=static_pressure, gamma=self.gamma), total_pressure, rtol=1.e-12)
    assert_allclose(calcIsentropicTotalTemperature(mach=mach, static_temperature=static_temperature, gamma=self.gamma), total_temperature, rtol=1.e-12)
    assert_allclose(calcIsentropicTotalDensity(mach=mach, static_density=static_density, gamma=self.gamma), total_density, rtol=1.e-12)

  def test_normal_shock_conserves_mass_momentum_and_energy(self) -> None:
    mach1 = 3.
    pressure1 = 100.e3
    temperature1 = 300.
    density1 = pressure1 / (self.R * temperature1)
    sound_speed1 = sqrt(self.gamma * self.R * temperature1)
    speed1 = mach1 * sound_speed1

    mach2 = calcNormalShockMach(mach=mach1, gamma=self.gamma)
    pressure2 = calcNormalShockStaticPressure(mach=mach1, static_pressure=pressure1, gamma=self.gamma)
    temperature2 = calcNormalShockStaticTemperature(mach=mach1, static_temperature=temperature1, gamma=self.gamma)
    density2 = calcNormalShockStaticDensity(mach=mach1, static_density=density1, gamma=self.gamma)
    sound_speed2 = sqrt(self.gamma * self.R * temperature2)
    speed2 = mach2 * sound_speed2
    cp = self.gamma * self.R / (self.gamma - 1.)

    assert_allclose(density1 * speed1, density2 * speed2, rtol=1.e-12)
    assert_allclose(pressure1 + density1 * speed1**2, pressure2 + density2 * speed2**2, rtol=1.e-12)
    assert_allclose(cp * temperature1 + speed1**2 / 2., cp * temperature2 + speed2**2 / 2., rtol=1.e-12)

  def test_oblique_shock_conserves_normal_mass_flux_and_total_enthalpy(self) -> None:
    mach1 = 3.
    theta_deg = 15.
    pressure1 = 100.e3
    temperature1 = 300.
    density1 = pressure1 / (self.R * temperature1)
    upstream = ObliqueShockState(
        mach=mach1,
        oblique_angle_deg=theta_deg,
        shock_angle_deg=float('nan'),
        static_pressure=pressure1,
        static_temperature=temperature1,
        static_density=density1,
        gamma=self.gamma,
    )
    downstream = ObliqueShockState.fromUpstreamState(upstream, oblique_angle_deg=theta_deg)

    speed1 = mach1 * sqrt(self.gamma * self.R * temperature1)
    speed2 = downstream.mach * sqrt(self.gamma * self.R * downstream.static_temperature)
    normal_speed1 = speed1 * sin(deg2rad(downstream.shock_angle_deg))
    normal_speed2 = speed2 * sin(deg2rad(downstream.shock_angle_deg - theta_deg))
    cp = self.gamma * self.R / (self.gamma - 1.)

    assert_allclose(density1 * normal_speed1, downstream.static_density * normal_speed2, rtol=1.e-12)
    assert_allclose(
        pressure1 + density1 * normal_speed1**2,
        downstream.static_pressure + downstream.static_density * normal_speed2**2,
        rtol=1.e-12,
    )
    assert_allclose(cp * temperature1 + speed1**2 / 2., cp * downstream.static_temperature + speed2**2 / 2., rtol=1.e-12)
    self.assertTrue(isclose(downstream.shock_angle_deg, 32.2404, rtol=1.e-4))
    self.assertTrue(isclose(downstream.static_pressure, pressure1 * 2.82156, rtol=1.e-4))
