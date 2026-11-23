"""Calorically-perfect-gas dimensionalization for characteristic MOC states.

This module is the explicit bridge from the unit-light characteristic solver
to conservative Euler quantities.  It does not solve a flow field or assert
that a fan-to-Euler interface is globally closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, isclose, isfinite, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.primitives import CharacteristicState

__all__ = (
  'MocCharacteristicEulerPrimitive',
  'dimensionalize_characteristic_state',
)


@dataclass(frozen=True, slots=True)
class MocCharacteristicEulerPrimitive:
  """One characteristic state dimensionalized under an ideal-gas model.

  The conservative tuple is ordered ``(rho, rho*u, rho*v, E)`` in SI units.
  ``entropy_proxy`` is ``p / rho**gamma``; it is an entropy consistency
  quantity, not specific thermodynamic entropy.
  """

  characteristic_state: CharacteristicState
  total_pressure_Pa: float
  total_temperature_K: float
  gas_constant_J_kgK: float
  static_pressure_Pa: float
  static_temperature_K: float
  density_kg_m3: float
  sound_speed_m_s: float
  velocity_u_m_s: float
  velocity_v_m_s: float

  def __post_init__(self) -> None:
    if not isinstance(self.characteristic_state, CharacteristicState):
      raise TypeError('characteristic_state must be a CharacteristicState')
    for name in (
      'total_pressure_Pa',
      'total_temperature_K',
      'gas_constant_J_kgK',
      'static_pressure_Pa',
      'static_temperature_K',
      'density_kg_m3',
      'sound_speed_m_s',
      'velocity_u_m_s',
      'velocity_v_m_s',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      if name not in {'velocity_u_m_s', 'velocity_v_m_s'} and value <= 0.0:
        raise ValueError(f'{name} must be positive')
      object.__setattr__(self, name, value)
    ####
    state = self.characteristic_state
    gamma = float(state.gamma)
    mach = float(state.mach)
    factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
    expected_pressure = self.total_pressure_Pa / factor ** (
      gamma / (gamma - 1.0)
    )
    expected_temperature = self.total_temperature_K / factor
    expected_density = expected_pressure / (
      self.gas_constant_J_kgK * expected_temperature
    )
    expected_sound_speed = sqrt(
      gamma * self.gas_constant_J_kgK * expected_temperature
    )
    expected_speed = mach * expected_sound_speed
    actual_speed = sqrt(self.velocity_u_m_s**2 + self.velocity_v_m_s**2)
    expected_velocity = (
      expected_speed * cos(float(state.theta_rad)),
      expected_speed * sin(float(state.theta_rad)),
    )
    comparisons = (
      ('static_pressure_Pa', self.static_pressure_Pa, expected_pressure),
      ('static_temperature_K', self.static_temperature_K, expected_temperature),
      ('density_kg_m3', self.density_kg_m3, expected_density),
      ('sound_speed_m_s', self.sound_speed_m_s, expected_sound_speed),
      ('velocity_u_m_s', self.velocity_u_m_s, expected_velocity[0]),
      ('velocity_v_m_s', self.velocity_v_m_s, expected_velocity[1]),
      ('speed_m_s', actual_speed, expected_speed),
    )
    for name, actual, expected in comparisons:
      if not isclose(actual, expected, rel_tol=2.0e-12, abs_tol=2.0e-12):
        raise ValueError(f'{name} is inconsistent with the declared gas model')
    ####
    if not isfinite(self.total_energy_density_J_m3) or self.total_energy_density_J_m3 <= 0.0:
      raise ValueError('total energy density must be finite and positive')
    if not isfinite(self.entropy_proxy) or self.entropy_proxy <= 0.0:
      raise ValueError('entropy proxy must be finite and positive')
  ####

  @property
  def conservative_state_rho_rhou_rhov_E(self) -> tuple[float, float, float, float]:
    return (
      self.density_kg_m3,
      self.density_kg_m3 * self.velocity_u_m_s,
      self.density_kg_m3 * self.velocity_v_m_s,
      self.total_energy_density_J_m3,
    )
  ####

  @property
  def total_energy_density_J_m3(self) -> float:
    gamma = float(self.characteristic_state.gamma)
    kinetic = 0.5 * self.density_kg_m3 * (
      self.velocity_u_m_s**2 + self.velocity_v_m_s**2
    )
    return self.static_pressure_Pa / (gamma - 1.0) + kinetic
  ####

  @property
  def entropy_proxy(self) -> float:
    return self.static_pressure_Pa / self.density_kg_m3 ** float(
      self.characteristic_state.gamma
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'characteristic_state': {
        'point_m': [
          self.characteristic_state.x_m,
          self.characteristic_state.y_m,
        ],
        'mach': self.characteristic_state.mach,
        'flow_angle_rad': self.characteristic_state.theta_rad,
        'gamma': self.characteristic_state.gamma,
      },
      'gas_model': 'calorically-perfect-ideal-gas',
      'total_pressure_Pa': self.total_pressure_Pa,
      'total_temperature_K': self.total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'static_pressure_Pa': self.static_pressure_Pa,
      'static_temperature_K': self.static_temperature_K,
      'density_kg_m3': self.density_kg_m3,
      'sound_speed_m_s': self.sound_speed_m_s,
      'velocity_u_m_s': self.velocity_u_m_s,
      'velocity_v_m_s': self.velocity_v_m_s,
      'conservative_state_rho_rhou_rhov_E': (
        self.conservative_state_rho_rhou_rhov_E
      ),
      'conservative_state_units': (
        'kg m^-3',
        'kg m^-2 s^-1',
        'kg m^-2 s^-1',
        'J m^-3',
      ),
      'total_energy_density_J_m3': self.total_energy_density_J_m3,
      'entropy_proxy_p_over_rho_gamma': self.entropy_proxy,
      'entropy_proxy_is_specific_entropy': False,
    }
  ####
####


def dimensionalize_characteristic_state(
  state: CharacteristicState,
  total_pressure_Pa: float,
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> MocCharacteristicEulerPrimitive:
  """Return conservative Euler variables from an isentropic MOC state.

  The total pressure and temperature are constant-state data for this
  conversion.  The equation of state is ``p = rho * R * T`` and
  ``E = p/(gamma-1) + rho*|u|^2/2``.
  """

  if not isinstance(state, CharacteristicState):
    raise TypeError('state must be a CharacteristicState')
  controls: dict[str, float] = {}
  for name, raw_value in (
    ('total_pressure_Pa', total_pressure_Pa),
    ('total_temperature_K', total_temperature_K),
    ('gas_constant_J_kgK', gas_constant_J_kgK),
  ):
    value = float(raw_value)
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    controls[name] = value
  ####
  gamma = float(state.gamma)
  mach = float(state.mach)
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  static_pressure = controls['total_pressure_Pa'] / factor ** (
    gamma / (gamma - 1.0)
  )
  static_temperature = controls['total_temperature_K'] / factor
  density = static_pressure / (
    controls['gas_constant_J_kgK'] * static_temperature
  )
  sound_speed = sqrt(
    gamma * controls['gas_constant_J_kgK'] * static_temperature
  )
  speed = mach * sound_speed
  primitive = MocCharacteristicEulerPrimitive(
    characteristic_state=state,
    total_pressure_Pa=controls['total_pressure_Pa'],
    total_temperature_K=controls['total_temperature_K'],
    gas_constant_J_kgK=controls['gas_constant_J_kgK'],
    static_pressure_Pa=static_pressure,
    static_temperature_K=static_temperature,
    density_kg_m3=density,
    sound_speed_m_s=sound_speed,
    velocity_u_m_s=speed * cos(float(state.theta_rad)),
    velocity_v_m_s=speed * sin(float(state.theta_rad)),
  )
  if any(
    not isfinite(value)
    for value in (
      *primitive.conservative_state_rho_rhou_rhov_E,
      primitive.entropy_proxy,
    )
  ):
    raise ValueError('ideal-gas dimensionalization produced a nonfinite state')
  ####
  return primitive
####
