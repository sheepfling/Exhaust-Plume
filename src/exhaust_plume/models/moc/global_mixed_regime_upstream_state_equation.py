"""Research-only upstream state-equation interface-strip solver.

The mixed-regime downstream trace is a curved, interior Cauchy frame in the
retained global physical field.  It is not an ambient pressure boundary and
must not be projected onto one.  This module provides the smallest solver
owned conservative seam for that frame: a narrow finite-volume strip is
constructed between the exact trace and a deterministic offset sampled from
the exact global field.  The trace conservative state is used on one strip
boundary and the declared entropy proxy closes its thermodynamic energy; the
global-field sample is used on the opposite boundary.

The strip is deliberately a research interface equation, not the canonical
global/free-boundary solver.  It does not rewrite the retained global field,
add an interior source, infer a pressure target, or promote a locally finite
residual to a product claim.  Its purpose is to make state/entropy equation
consumption executable and independently auditable before the full global
moving-boundary fixed point is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, log, sqrt
from typing import Any

import numpy as np

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_MODEL',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_GLOBAL_SHOCK_FRONTIER_SOURCE',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit',
  'build_reflected_domain_global_mixed_regime_upstream_state_equation_request_from_global_shock_frontier',
  'solve_reflected_domain_global_mixed_regime_upstream_state_equation',
  'audit_reflected_domain_global_mixed_regime_upstream_state_equation',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-state-equation-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_MODEL = (
  'research-global-mixed-regime-upstream-state-equation-interface-strip-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_GLOBAL_SHOCK_FRONTIER_SOURCE = (
  'research-global-mixed-regime-upstream-state-equation-global-shock-frontier-v1'
)
_FLUX_SCHEME = 'entropy-compatible-rusanov-v1'
_STATE_COMPONENT_NAMES = (
  'density',
  'streamwise_momentum',
  'transverse_momentum',
  'total_energy',
)
_RESIDUAL_CHANNEL_NAMES = (
  'mass',
  'streamwise_momentum',
  'transverse_momentum',
  'energy',
  'euler',
)


class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus(
  str,
  Enum,
):
  """Typed outcomes of one upstream interface-strip equation attempt."""

  CONVERGED_LOCAL_RESEARCH_UPSTREAM_STATE_EQUATION = (
    'converged-local-research-upstream-state-equation-interface-strip'
  )
  COMPLETED_RESEARCH_UPSTREAM_STATE_EQUATION_WITH_OPEN_RESIDUAL = (
    'completed-research-upstream-state-equation-interface-strip-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = (
    'upstream-state-equation-source-closure-failure'
  )
  TARGET_FRAME_FAILURE = 'upstream-state-equation-target-frame-failure'
  GEOMETRY_FAILURE = 'upstream-state-equation-interface-geometry-failure'
  STATE_FAILURE = 'upstream-state-equation-state-failure'
  ENTROPY_TARGET_FAILURE = 'upstream-state-equation-entropy-target-failure'
  ENTROPY_FLUX_FAILURE = 'upstream-state-equation-entropy-flux-failure'
  POSITIVITY_FAILURE = 'upstream-state-equation-positivity-failure'
  RESIDUAL_FAILURE = 'upstream-state-equation-residual-failure'
  CONSUMPTION_FAILURE = 'upstream-state-equation-consumption-failure'
####


class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the independent interface-strip replay."""

  VERIFIED_RESEARCH_INTERFACE_STRIP = (
    'verified-research-upstream-state-equation-interface-strip'
  )
  INVALID_INPUT = 'invalid_input'
  CONSUMPTION_FAILURE = 'upstream-state-equation-audit-consumption-failure'
  REPLAY_FAILURE = 'upstream-state-equation-audit-replay-failure'
####


def _state_profile(
  values: Any,
  name: str,
) -> tuple[tuple[float, float, float, float], ...]:
  profile = tuple(
    tuple(float(component) for component in state)
    for state in values
  )
  if any(
    len(state) != 4 or any(not isfinite(value) for value in state)
    for state in profile
  ):
    raise ValueError(f'{name} must contain finite four-component states')
  ####
  return profile
####


def _points(
  values: Any,
  name: str,
) -> tuple[tuple[float, float], ...]:
  points = tuple(
    tuple(float(coordinate) for coordinate in point)
    for point in values
  )
  if any(
    len(point) != 2 or any(not isfinite(value) for value in point)
    for point in points
  ):
    raise ValueError(f'{name} must contain finite two-dimensional points')
  ####
  if any(
    second[0] <= first[0]
    for first, second in zip(points, points[1:])
  ):
    raise ValueError(f'{name} must be strictly ordered in x')
  ####
  if any(
    hypot(second[0] - first[0], second[1] - first[1]) <= 0.0
    for first, second in zip(points, points[1:])
  ):
    raise ValueError(f'{name} must contain positive-length segments')
  ####
  return points
####


def _positive_float(value: Any, name: str) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _primitive(
  state: np.ndarray,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[float, float, float, float, float]:
  density = float(state[0])
  if not isfinite(density) or density <= 0.0:
    raise FloatingPointError('interface-strip density is not positive')
  ####
  velocity_u = float(state[1]) / density
  velocity_v = float(state[2]) / density
  pressure = (gamma - 1.0) * (
    float(state[3])
    - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise FloatingPointError('interface-strip pressure is not positive')
  ####
  temperature = pressure / (density * gas_constant_J_kgK)
  if not isfinite(temperature) or temperature <= 0.0:
    raise FloatingPointError('interface-strip temperature is not positive')
  ####
  sound_speed = sqrt(gamma * pressure / density)
  return density, velocity_u, velocity_v, pressure, sound_speed
####


def _entropy_proxy(
  state: np.ndarray,
  gamma: float,
  gas_constant_J_kgK: float,
) -> float:
  density, _u, _v, pressure, _sound_speed = _primitive(
    state,
    gamma,
    gas_constant_J_kgK,
  )
  value = pressure / density**gamma
  if not isfinite(value) or value <= 0.0:
    raise FloatingPointError('interface-strip entropy proxy is not positive')
  ####
  return value
####


def _validate_target_entropy_closure(
  profile: tuple[tuple[float, float, float, float], ...],
  entropy_profile: tuple[float, ...],
  gamma: float,
  gas_constant_J_kgK: float,
  tolerance: float,
) -> tuple[tuple[tuple[float, float, float, float], ...], tuple[float, ...]]:
  """Close target energy from the declared entropy proxy without projection."""

  closed: list[tuple[float, float, float, float]] = []
  consistency_logs: list[float] = []
  for state, entropy_target in zip(profile, entropy_profile, strict=True):
    density, momentum_x, momentum_y, supplied_energy = state
    if density <= 0.0 or supplied_energy <= 0.0:
      raise ValueError('target state density and energy must be positive')
    ####
    kinetic = 0.5 * (momentum_x * momentum_x + momentum_y * momentum_y) / density
    supplied_pressure = (gamma - 1.0) * (supplied_energy - kinetic)
    if not isfinite(supplied_pressure) or supplied_pressure <= 0.0:
      raise ValueError('target state has non-positive thermodynamic pressure')
    ####
    entropy_from_state = supplied_pressure / density**gamma
    consistency_log = log(entropy_from_state / entropy_target)
    if abs(consistency_log) > tolerance:
      raise ValueError(
        'declared target entropy is not thermodynamically consistent with '
        f'the target conservative state: |log(K/K_target)|={abs(consistency_log)} '
        f'> {tolerance}'
      )
    ####
    closed_pressure = entropy_target * density**gamma
    closed_energy = closed_pressure / (gamma - 1.0) + kinetic
    if not isfinite(closed_energy) or closed_energy <= 0.0:
      raise ValueError('entropy-closed target energy is not positive')
    ####
    closed.append((density, momentum_x, momentum_y, closed_energy))
    consistency_logs.append(consistency_log)
  ####
  return tuple(closed), tuple(consistency_logs)
####


def _segment_average_profile(
  profile: tuple[tuple[float, float, float, float], ...],
) -> tuple[tuple[float, float, float, float], ...]:
  """Evaluate a declared piecewise-linear trace at each segment midpoint."""

  return tuple(
    tuple(
      0.5 * (first[component] + second[component])
      for component in range(4)
    )
    for first, second in zip(profile, profile[1:])
  )
####


def _segment_average_scalars(
  values: tuple[float, ...],
) -> tuple[float, ...]:
  return tuple(
    0.5 * (first + second)
    for first, second in zip(values, values[1:])
  )
####


def _conservative_from_characteristic(
  state: Any,
  total_pressure_Pa: float,
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  gamma = float(state.gamma)
  mach = float(state.mach)
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_pressure = total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
  static_temperature = total_temperature_K / factor
  density = static_pressure / (gas_constant_J_kgK * static_temperature)
  sound_speed = sqrt(gamma * gas_constant_J_kgK * static_temperature)
  speed = mach * sound_speed
  return np.asarray(
    (
      density,
      density * speed * np.cos(float(state.theta_rad)),
      density * speed * np.sin(float(state.theta_rad)),
      static_pressure / (gamma - 1.0) + 0.5 * density * speed * speed,
    ),
    dtype=float,
  )
####


def _euler_flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float]:
  density, velocity_u, velocity_v, pressure, sound_speed = _primitive(
    state,
    gamma,
    gas_constant_J_kgK,
  )
  normal_velocity = velocity_u * normal_x + velocity_v * normal_y
  return (
    np.asarray(
      (
        density * normal_velocity,
        density * velocity_u * normal_velocity + pressure * normal_x,
        density * velocity_v * normal_velocity + pressure * normal_y,
        (state[3] + pressure) * normal_velocity,
      ),
      dtype=float,
    ),
    abs(normal_velocity) + sound_speed,
  )
####


def _entropy_variables(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float]:
  density, velocity_u, velocity_v, pressure, _sound_speed = _primitive(
    state,
    gamma,
    gas_constant_J_kgK,
  )
  specific_entropy = log(pressure) - gamma * log(density)
  beta = density / (2.0 * pressure)
  variables = np.asarray(
    (
      (gamma - specific_entropy) / (gamma - 1.0)
      - beta * (velocity_u * velocity_u + velocity_v * velocity_v),
      2.0 * beta * velocity_u,
      2.0 * beta * velocity_v,
      -2.0 * beta,
    ),
    dtype=float,
  )
  potential = density * (velocity_u * normal_x + velocity_v * normal_y)
  if not np.all(np.isfinite(variables)) or not isfinite(potential):
    raise FloatingPointError('interface-strip entropy variables are non-finite')
  ####
  return variables, float(potential)
####


def _entropy_compatible_rusanov_flux(
  left: np.ndarray,
  right: np.ndarray,
  normal_x: float,
  normal_y: float,
  face_length: float,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float, float]:
  """Return an entropy-compatible Rusanov flux and its defect."""

  left_flux, left_wave = _euler_flux(
    left,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  right_flux, right_wave = _euler_flux(
    right,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  left_variables, left_potential = _entropy_variables(
    left,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  right_variables, right_potential = _entropy_variables(
    right,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  state_jump = right - left
  variable_jump = right_variables - left_variables
  central_flux = 0.5 * (left_flux + right_flux)
  central_defect = float(
    np.dot(variable_jump, central_flux)
    - (right_potential - left_potential)
  )
  convexity = float(np.dot(variable_jump, state_jump))
  if not isfinite(central_defect) or not isfinite(convexity):
    raise FloatingPointError('interface-strip entropy defect is non-finite')
  ####
  wave = max(left_wave, right_wave)
  if central_defect > 0.0:
    if convexity <= 0.0:
      raise FloatingPointError(
        'interface-strip entropy compatibility has non-positive convexity'
      )
    ####
    wave = max(wave, 2.0 * central_defect / convexity)
  ####
  flux_density = central_flux - 0.5 * wave * state_jump
  defect = float(
    np.dot(variable_jump, flux_density)
    - (right_potential - left_potential)
  )
  scale = max(
    abs(float(np.dot(variable_jump, flux_density))),
    abs(right_potential - left_potential),
    1.0,
  )
  if defect > 1.0e-12 * scale:
    if convexity <= 0.0:
      raise FloatingPointError(
        'interface-strip entropy compatibility cannot be enforced'
      )
    ####
    wave = max(wave, 2.0 * central_defect / convexity * (1.0 + 1.0e-12))
    flux_density = central_flux - 0.5 * wave * state_jump
    defect = float(
      np.dot(variable_jump, flux_density)
      - (right_potential - left_potential)
    )
    if defect > 1.0e-12 * scale:
      raise FloatingPointError(
        'interface-strip entropy-compatible Rusanov flux retained a positive defect'
      )
    ####
  ####
  return flux_density * face_length, wave, defect
####


def _signed_area(
  polygon: tuple[tuple[float, float], ...],
) -> float:
  return 0.5 * sum(
    polygon[index][0] * polygon[(index + 1) % len(polygon)][1]
    - polygon[(index + 1) % len(polygon)][0] * polygon[index][1]
    for index in range(len(polygon))
  )
####


def _face_geometry(
  first: tuple[float, float],
  second: tuple[float, float],
  signed_area: float,
) -> tuple[float, float, float]:
  delta_x = second[0] - first[0]
  delta_y = second[1] - first[1]
  length = hypot(delta_x, delta_y)
  if not isfinite(length) or length <= 0.0:
    raise ValueError('interface-strip geometry contains a zero-length edge')
  ####
  if signed_area > 0.0:
    return delta_y / length, -delta_x / length, length
  ####
  return -delta_y / length, delta_x / length, length
####


def _path_normals(
  points: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
  normals: list[tuple[float, float]] = []
  for index in range(len(points)):
    if index == 0:
      first, second = points[0], points[1]
    elif index == len(points) - 1:
      first, second = points[-2], points[-1]
    else:
      first, second = points[index - 1], points[index + 1]
    ####
    tangent_x = second[0] - first[0]
    tangent_y = second[1] - first[1]
    length = hypot(tangent_x, tangent_y)
    if length <= 0.0 or not isfinite(length):
      raise ValueError('interface-strip target tangent is not valid')
    ####
    normals.append((-tangent_y / length, tangent_x / length))
  ####
  return tuple(normals)
####


def _build_strip_geometry(
  target_points: tuple[tuple[float, float], ...],
  normal_offset_m: float,
  offset_side: float,
) -> tuple[
  tuple[tuple[float, float], ...],
  tuple[tuple[tuple[float, float], ...], ...],
]:
  normals = _path_normals(target_points)
  source_points = tuple(
    (
      point[0] + offset_side * normal_offset_m * normal[0],
      point[1] + offset_side * normal_offset_m * normal[1],
    )
    for point, normal in zip(target_points, normals, strict=True)
  )
  cells = tuple(
    (
      target_points[index],
      target_points[index + 1],
      source_points[index + 1],
      source_points[index],
    )
    for index in range(len(target_points) - 1)
  )
  if any(abs(_signed_area(cell)) <= 1.0e-16 for cell in cells):
    raise ValueError('interface-strip geometry contains a degenerate cell')
  ####
  return source_points, cells
####


def _normalise_residuals(
  states: np.ndarray,
  residual: np.ndarray,
  cells: tuple[tuple[tuple[float, float], ...], ...],
  gamma: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  output = np.empty((len(cells), 5), dtype=float)
  for index, polygon in enumerate(cells):
    density, velocity_u, velocity_v, pressure, sound_speed = _primitive(
      states[index],
      gamma,
      gas_constant_J_kgK,
    )
    perimeter = sum(
      hypot(
        polygon[(edge_index + 1) % len(polygon)][0] - polygon[edge_index][0],
        polygon[(edge_index + 1) % len(polygon)][1] - polygon[edge_index][1],
      )
      for edge_index in range(len(polygon))
    )
    mass_scale = max(density * sound_speed * perimeter, 1.0e-12)
    momentum_scale = max(
      (density * (velocity_u * velocity_u + velocity_v * velocity_v) + pressure)
      * perimeter,
      1.0e-12,
    )
    energy_scale = max(
      (states[index, 3] + pressure) * sound_speed * perimeter,
      1.0e-12,
    )
    output[index, :4] = (
      abs(residual[index, 0]) / mass_scale,
      abs(residual[index, 1]) / momentum_scale,
      abs(residual[index, 2]) / momentum_scale,
      abs(residual[index, 3]) / energy_scale,
    )
    output[index, 4] = float(np.max(output[index, :4]))
  ####
  return output
####


def _residuals(
  states: np.ndarray,
  cells: tuple[tuple[tuple[float, float], ...], ...],
  target_states: tuple[tuple[float, float, float, float], ...],
  source_states: np.ndarray,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[
  np.ndarray,
  np.ndarray,
  tuple[tuple[float, float, float, float], ...],
  tuple[tuple[float, float, float, float], ...],
  tuple[float, ...],
]:
  residual = np.zeros_like(states)
  wave_sums = np.zeros(len(cells), dtype=float)
  target_fluxes: list[tuple[float, float, float, float]] = []
  source_fluxes: list[tuple[float, float, float, float]] = []
  entropy_defects: list[float] = []
  for index, cell in enumerate(cells):
    signed_area = _signed_area(cell)
    target_first, target_second = cell[0], cell[1]
    source_first, source_second = cell[2], cell[3]
    target_normal_x, target_normal_y, target_length = _face_geometry(
      target_first,
      target_second,
      signed_area,
    )
    source_normal_x, source_normal_y, source_length = _face_geometry(
      source_first,
      source_second,
      signed_area,
    )
    target_flux, target_wave, target_defect = _entropy_compatible_rusanov_flux(
      states[index],
      np.asarray(target_states[index], dtype=float),
      target_normal_x,
      target_normal_y,
      target_length,
      gamma,
      gas_constant_J_kgK,
    )
    source_flux, source_wave, source_defect = _entropy_compatible_rusanov_flux(
      states[index],
      source_states[index],
      source_normal_x,
      source_normal_y,
      source_length,
      gamma,
      gas_constant_J_kgK,
    )
    residual[index] += target_flux + source_flux
    wave_sums[index] += (
      target_wave * target_length + source_wave * source_length
    )
    target_fluxes.append(tuple(float(value) for value in target_flux))
    source_fluxes.append(tuple(float(value) for value in source_flux))
    entropy_defects.extend((max(0.0, target_defect), max(0.0, source_defect)))
    if index > 0:
      left_first, left_second = cells[index - 1][1], cells[index - 1][2]
      side_normal_x, side_normal_y, side_length = _face_geometry(
        left_first,
        left_second,
        signed_area,
      )
      side_flux, side_wave, side_defect = _entropy_compatible_rusanov_flux(
        states[index],
        states[index - 1],
        side_normal_x,
        side_normal_y,
        side_length,
        gamma,
        gas_constant_J_kgK,
      )
      residual[index] += side_flux
      residual[index - 1] -= side_flux
      wave_sums[index] += side_wave * side_length
      wave_sums[index - 1] += side_wave * side_length
      entropy_defects.append(max(0.0, side_defect))
    ####
    if index == 0:
      terminal_first, terminal_second = cell[3], cell[0]
      terminal_normal_x, terminal_normal_y, terminal_length = _face_geometry(
        terminal_first,
        terminal_second,
        signed_area,
      )
      terminal_flux, terminal_wave = _euler_flux(
        states[index],
        terminal_normal_x,
        terminal_normal_y,
        gamma,
        gas_constant_J_kgK,
      )
      residual[index] += terminal_flux * terminal_length
      wave_sums[index] += terminal_wave * terminal_length
    ####
    if index == len(cells) - 1:
      terminal_first, terminal_second = cell[1], cell[2]
      terminal_normal_x, terminal_normal_y, terminal_length = _face_geometry(
        terminal_first,
        terminal_second,
        signed_area,
      )
      terminal_flux, terminal_wave = _euler_flux(
        states[index],
        terminal_normal_x,
        terminal_normal_y,
        gamma,
        gas_constant_J_kgK,
      )
      residual[index] += terminal_flux * terminal_length
      wave_sums[index] += terminal_wave * terminal_length
    ####
  ####
  return (
    residual,
    wave_sums,
    tuple(target_fluxes),
    tuple(source_fluxes),
    tuple(entropy_defects),
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest:
  """Controls for one exact-target interface-strip Euler equation."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  target_points_m: tuple[tuple[float, float], ...]
  target_conservative_state_profile: tuple[tuple[float, float, float, float], ...]
  target_entropy_proxy_profile: tuple[float, ...]
  target_gamma: float
  reference_total_temperature_K: float
  gas_constant_J_kgK: float = 287.05
  normal_offset_m: float = 0.01
  offset_side: float = -1.0
  cfl_number: float = 0.45
  max_pseudo_iterations: int = 80
  euler_residual_tolerance: float = 5.0e-4
  target_entropy_consistency_tolerance: float = 1.0e-5
  target_state_tolerance: float = 1.0e-8
  relaxation: float = 0.65
  position_tolerance_m: float = 1.0e-8
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_MODEL
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    points = _points(self.target_points_m, 'target_points_m')
    profile = _state_profile(
      self.target_conservative_state_profile,
      'target_conservative_state_profile',
    )
    entropy = tuple(float(value) for value in self.target_entropy_proxy_profile)
    if any(not isfinite(value) or value <= 0.0 for value in entropy):
      raise ValueError('target_entropy_proxy_profile must contain positive values')
    ####
    if not (len(points) == len(profile) == len(entropy)) or len(points) < 2:
      raise ValueError(
        'target points, conservative state, and entropy profiles must align '
        'and contain at least two samples'
      )
    ####
    gamma = _positive_float(self.target_gamma, 'target_gamma')
    if gamma <= 1.0:
      raise ValueError('target_gamma must be greater than one')
    ####
    for name in (
      'reference_total_temperature_K',
      'gas_constant_J_kgK',
      'normal_offset_m',
      'euler_residual_tolerance',
      'target_entropy_consistency_tolerance',
      'target_state_tolerance',
      'position_tolerance_m',
    ):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    offset_side = float(self.offset_side)
    if not isfinite(offset_side) or abs(abs(offset_side) - 1.0) > 1.0e-12:
      raise ValueError('offset_side must be either -1 or +1')
    ####
    cfl = _positive_float(self.cfl_number, 'cfl_number')
    if cfl >= 1.0:
      raise ValueError('cfl_number must be less than one')
    ####
    relaxation = _positive_float(self.relaxation, 'relaxation')
    if relaxation > 1.0:
      raise ValueError('relaxation must be no greater than one')
    ####
    if (
      isinstance(self.max_pseudo_iterations, bool)
      or not isinstance(self.max_pseudo_iterations, int)
      or self.max_pseudo_iterations < 1
    ):
      raise ValueError('max_pseudo_iterations must be a positive integer')
    ####
    object.__setattr__(self, 'target_points_m', points)
    object.__setattr__(self, 'target_conservative_state_profile', profile)
    object.__setattr__(self, 'target_entropy_proxy_profile', entropy)
    object.__setattr__(self, 'target_gamma', gamma)
    object.__setattr__(self, 'offset_side', offset_side)
    object.__setattr__(self, 'cfl_number', cfl)
    object.__setattr__(self, 'relaxation', relaxation)
    object.__setattr__(self, 'source', str(self.source))
    if not self.source:
      raise ValueError('source must be non-empty')
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_MODEL,
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(self.closure)
      ),
      'target_points_m': self.target_points_m,
      'target_conservative_state_profile': self.target_conservative_state_profile,
      'target_entropy_proxy_profile': self.target_entropy_proxy_profile,
      'target_gamma': self.target_gamma,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'normal_offset_m': self.normal_offset_m,
      'offset_side': self.offset_side,
      'cfl_number': self.cfl_number,
      'max_pseudo_iterations': self.max_pseudo_iterations,
      'euler_residual_tolerance': self.euler_residual_tolerance,
      'target_entropy_consistency_tolerance': (
        self.target_entropy_consistency_tolerance
      ),
      'target_state_tolerance': self.target_state_tolerance,
      'relaxation': self.relaxation,
      'position_tolerance_m': self.position_tolerance_m,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


def build_reflected_domain_global_mixed_regime_upstream_state_equation_request_from_global_shock_frontier(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  gas_constant_J_kgK: float = 287.05,
  sample_start_index: int = 1,
  normal_offset_m: float = 1.0e-3,
  offset_side: float = 1.0,
  max_pseudo_iterations: int = 400,
  target_entropy_consistency_tolerance: float = 1.0e-4,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest:
  """Bind the exact global shock frontier to a conservative target frame.

  The coupled downstream free-boundary trace is not guaranteed to be
  supersonic.  This builder instead consumes the solver-owned upstream states
  and total pressures retained by the verified global Euler shock curve.  The
  first shock sample is excluded by default because it is the attachment
  singularity; the retained downstream shock span is the exact field-backed
  frontier used for the research interface-strip handoff.

  Thermodynamic dimensionalization is explicit through the supplied total
  temperature and gas constant.  The returned request remains a research
  equation target; it does not promote the shock curve to a canonical global
  free boundary.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    raise ValueError(
      'global shock-frontier state binding requires a locally verified global '
      'physical closure'
    )
  ####
  if (
    closure.global_euler is None
    or closure.global_euler.shock_boundary is None
  ):
    raise ValueError(
      'global physical closure must retain an exact Euler shock boundary'
    )
  ####
  if (
    isinstance(sample_start_index, bool)
    or not isinstance(sample_start_index, int)
    or sample_start_index < 0
  ):
    raise ValueError('sample_start_index must be a nonnegative integer')
  ####
  shock = closure.global_euler.shock_boundary
  points = tuple(shock.shock_points_m[sample_start_index:])
  states = tuple(shock.upstream_states[sample_start_index:])
  total_pressures = tuple(
    float(value)
    for value in shock.upstream_total_pressure_Pa[sample_start_index:]
  )
  if len(points) < 2 or not (
    len(points) == len(states) == len(total_pressures)
  ):
    raise ValueError(
      'global shock frontier must retain at least two aligned upstream '
      'states, points, and total pressures after the attachment sample'
    )
  ####
  if any(
    second[0] <= first[0]
    for first, second in zip(points, points[1:])
  ):
    raise ValueError('global shock frontier points must be strictly ordered in x')
  ####
  gamma = float(states[0].gamma)
  if any(abs(float(state.gamma) - gamma) > 1.0e-12 for state in states):
    raise ValueError('global shock frontier gamma must be constant')
  ####
  conservative_profile = tuple(
    tuple(
      float(value)
      for value in _conservative_from_characteristic(
        state,
        total_pressure,
        reference_total_temperature_K,
        gas_constant_J_kgK,
      )
    )
    for state, total_pressure in zip(states, total_pressures, strict=True)
  )
  entropy_profile = tuple(
    _entropy_proxy(
      np.asarray(state, dtype=float),
      gamma,
      gas_constant_J_kgK,
    )
    for state in conservative_profile
  )
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest(
    closure=closure,
    target_points_m=points,
    target_conservative_state_profile=conservative_profile,
    target_entropy_proxy_profile=entropy_profile,
    target_gamma=gamma,
    reference_total_temperature_K=reference_total_temperature_K,
    gas_constant_J_kgK=gas_constant_J_kgK,
    normal_offset_m=normal_offset_m,
    offset_side=offset_side,
    max_pseudo_iterations=max_pseudo_iterations,
    target_entropy_consistency_tolerance=(
      target_entropy_consistency_tolerance
    ),
    source=(
      MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_GLOBAL_SHOCK_FRONTIER_SOURCE
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult:
  """Retained state/entropy equation evidence for one interface strip."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_points_m: tuple[tuple[float, float], ...] = ()
  cell_vertices_by_cell_m: tuple[tuple[tuple[float, float], ...], ...] = ()
  source_conservative_state_profile: tuple[tuple[float, float, float, float], ...] = ()
  entropy_closed_target_profile: tuple[tuple[float, float, float, float], ...] = ()
  entropy_consistency_log_residuals: tuple[float, ...] = ()
  final_conservative_states_by_cell: tuple[tuple[float, float, float, float], ...] = ()
  residual_channels_by_cell: tuple[tuple[float, float, float, float, float], ...] = ()
  residual_history: tuple[float, ...] = ()
  target_boundary_fluxes: tuple[tuple[float, float, float, float], ...] = ()
  source_boundary_fluxes: tuple[tuple[float, float, float, float], ...] = ()
  target_boundary_entropy_log_residuals: tuple[float, ...] = ()
  entropy_flux_defects: tuple[float, ...] = ()
  pseudo_iteration_count: int = 0
  maximum_conservative_euler_residual: float | None = None
  maximum_target_boundary_entropy_log_residual: float | None = None
  maximum_entropy_flux_defect: float | None = None
  target_frame_verified: bool = False
  source_field_lineage_verified: bool = False
  global_field_sampled: bool = False
  target_conservative_state_consumed: bool = False
  entropy_target_consumed: bool = False
  upstream_state_equation_consumed: bool = False
  conservative_residuals_measured: bool = False
  conservative_residuals_verified: bool = False
  entropy_flux_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus,
    ):
      raise TypeError('status must be a typed upstream state-equation status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
    ):
      raise TypeError('request must be a typed upstream state-equation request')
    ####
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed global physical closure')
    ####
    points = (
      _points(self.source_points_m, 'source_points_m')
      if self.source_points_m
      else ()
    )
    cells = tuple(
      tuple((float(point[0]), float(point[1])) for point in polygon)
      for polygon in self.cell_vertices_by_cell_m
    )
    if any(
      len(polygon) != 4
      or any(not all(isfinite(value) for value in point) for point in polygon)
      or abs(_signed_area(polygon)) <= 0.0
      for polygon in cells
    ):
      raise ValueError('cell_vertices_by_cell_m must contain finite nondegenerate quadrilaterals')
    ####
    source_states = _state_profile(
      self.source_conservative_state_profile,
      'source_conservative_state_profile',
    )
    target_states = _state_profile(
      self.entropy_closed_target_profile,
      'entropy_closed_target_profile',
    )
    final_states = _state_profile(
      self.final_conservative_states_by_cell,
      'final_conservative_states_by_cell',
    )
    residuals = tuple(
      tuple(float(value) for value in residual)
      for residual in self.residual_channels_by_cell
    )
    if any(
      len(residual) != 5 or any(not isfinite(value) for value in residual)
      for residual in residuals
    ):
      raise ValueError('residual_channels_by_cell must contain finite five-tuples')
    ####
    if len(cells) != len(final_states) or len(cells) != len(residuals):
      raise ValueError('cell geometry, final states, and residuals must align')
    ####
    if len(source_states) not in (0, len(cells)):
      raise ValueError('source state profile must align with strip cells')
    ####
    if len(points) not in (0, len(cells) + 1):
      raise ValueError('source points must align with strip vertices')
    ####
    if len(target_states) not in (0, len(cells)):
      raise ValueError('target state profile must align with strip cells')
    ####
    for name in (
      'entropy_consistency_log_residuals',
      'target_boundary_entropy_log_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) for value in values):
        raise ValueError(f'{name} must contain finite values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'entropy_flux_defects',
      'residual_history',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'target_boundary_fluxes',
      'source_boundary_fluxes',
    ):
      values = tuple(
        tuple(float(component) for component in flux)
        for flux in getattr(self, name)
      )
      if any(
        len(flux) != 4 or any(not isfinite(value) for value in flux)
        for flux in values
      ):
        raise ValueError(f'{name} must contain finite four-component fluxes')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'pseudo_iteration_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'maximum_conservative_euler_residual',
      'maximum_target_boundary_entropy_log_residual',
      'maximum_entropy_flux_defect',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'target_frame_verified',
      'source_field_lineage_verified',
      'global_field_sampled',
      'target_conservative_state_consumed',
      'entropy_target_consumed',
      'upstream_state_equation_consumed',
      'conservative_residuals_measured',
      'conservative_residuals_verified',
      'entropy_flux_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('upstream state-equation strip cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('upstream state-equation strip must remain promotion-blocked')
    ####
    object.__setattr__(self, 'source_points_m', points)
    object.__setattr__(self, 'cell_vertices_by_cell_m', cells)
    object.__setattr__(self, 'source_conservative_state_profile', source_states)
    object.__setattr__(self, 'entropy_closed_target_profile', target_states)
    object.__setattr__(self, 'final_conservative_states_by_cell', final_states)
    object.__setattr__(self, 'residual_channels_by_cell', residuals)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_state_equation_consumed(self) -> bool:
    """Whether the exact conservative/entropy target entered strip fluxes."""

    return bool(
      self.upstream_state_equation_consumed
      and self.target_frame_verified
      and self.source_field_lineage_verified
      and self.global_field_sampled
      and self.target_conservative_state_consumed
      and self.entropy_target_consumed
      and self.conservative_residuals_measured
      and self.entropy_flux_verified
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
      .CONVERGED_LOCAL_RESEARCH_UPSTREAM_STATE_EQUATION
      and self.research_state_equation_consumed
      and self.conservative_residuals_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'research_state_equation_consumed': self.research_state_equation_consumed,
      'source_closure_fingerprint': (
        None
        if self.source_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'source_points_m': self.source_points_m,
      'cell_vertices_by_cell_m': self.cell_vertices_by_cell_m,
      'source_conservative_state_profile': self.source_conservative_state_profile,
      'entropy_closed_target_profile': self.entropy_closed_target_profile,
      'entropy_consistency_log_residuals': self.entropy_consistency_log_residuals,
      'final_conservative_states_by_cell': self.final_conservative_states_by_cell,
      'residual_channels_by_cell': self.residual_channels_by_cell,
      'residual_channel_names': _RESIDUAL_CHANNEL_NAMES,
      'residual_history': self.residual_history,
      'target_boundary_fluxes': self.target_boundary_fluxes,
      'source_boundary_fluxes': self.source_boundary_fluxes,
      'target_boundary_entropy_log_residuals': (
        self.target_boundary_entropy_log_residuals
      ),
      'entropy_flux_defects': self.entropy_flux_defects,
      'flux_scheme': _FLUX_SCHEME,
      'pseudo_iteration_count': self.pseudo_iteration_count,
      'maximum_conservative_euler_residual': (
        self.maximum_conservative_euler_residual
      ),
      'maximum_target_boundary_entropy_log_residual': (
        self.maximum_target_boundary_entropy_log_residual
      ),
      'maximum_entropy_flux_defect': self.maximum_entropy_flux_defect,
      'target_frame_verified': self.target_frame_verified,
      'source_field_lineage_verified': self.source_field_lineage_verified,
      'global_field_sampled': self.global_field_sampled,
      'target_conservative_state_consumed': self.target_conservative_state_consumed,
      'entropy_target_consumed': self.entropy_target_consumed,
      'upstream_state_equation_consumed': self.upstream_state_equation_consumed,
      'conservative_residuals_measured': self.conservative_residuals_measured,
      'conservative_residuals_verified': self.conservative_residuals_verified,
      'entropy_flux_verified': self.entropy_flux_verified,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only conservative/entropy upstream interface-strip equation; '
        'canonical moving global/free-boundary closure, independent refinement, '
        'physical validation, and product promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest | None = None,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  source_points_m: tuple[tuple[float, float], ...] = (),
  cell_vertices_by_cell_m: tuple[tuple[tuple[float, float], ...], ...] = (),
  source_conservative_state_profile: tuple[tuple[float, float, float, float], ...] = (),
  entropy_closed_target_profile: tuple[tuple[float, float, float, float], ...] = (),
  entropy_consistency_log_residuals: tuple[float, ...] = (),
  target_frame_verified: bool = False,
  source_field_lineage_verified: bool = False,
  global_field_sampled: bool = False,
  target_conservative_state_consumed: bool = False,
  entropy_target_consumed: bool = False,
  upstream_state_equation_consumed: bool = False,
  message_prefix: str = '',
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult:
  # A typed failure may be returned after strip geometry was built but before
  # any cell state/residual arrays exist.  Do not construct an internally
  # inconsistent partial result that raises from ``__post_init__`` and hides
  # the original state/geometry failure.
  if cell_vertices_by_cell_m and not (
    values.get('final_conservative_states_by_cell')
    or values.get('residual_channels_by_cell')
  ):
    source_points_m = ()
    cell_vertices_by_cell_m = ()
    entropy_closed_target_profile = ()
    entropy_consistency_log_residuals = ()
  ####
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult(
    status=status,
    request=request,
    source_closure=source_closure,
    source_points_m=source_points_m,
    cell_vertices_by_cell_m=cell_vertices_by_cell_m,
    source_conservative_state_profile=source_conservative_state_profile,
    entropy_closed_target_profile=entropy_closed_target_profile,
    entropy_consistency_log_residuals=entropy_consistency_log_residuals,
    target_frame_verified=target_frame_verified,
    source_field_lineage_verified=source_field_lineage_verified,
    global_field_sampled=global_field_sampled,
    target_conservative_state_consumed=target_conservative_state_consumed,
    entropy_target_consumed=entropy_target_consumed,
    upstream_state_equation_consumed=upstream_state_equation_consumed,
    message=f'{message_prefix}{message}',
    **values,
  )
####


def _sample_source_field(
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  source_points: tuple[tuple[float, float], ...],
) -> np.ndarray:
  closure = request.closure
  if closure.global_euler is None or closure.global_euler.physical_field is None:
    raise ValueError('closure retained no exact global physical field')
  ####
  physical = closure.global_euler.physical_field
  field = physical.field
  if (
    not physical.physical_field_verified
    or field is None
    or not field.physical_closure_verified
    or not field.state_sampling_available
  ):
    raise ValueError(
      'closure global physical field is not ready for exact source sampling'
    )
  ####
  sampled: list[np.ndarray] = []
  for point in source_points:
    characteristic = field.state_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    total_pressure = field.total_pressure_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    if characteristic is None or total_pressure is None:
      raise ValueError(
        f'exact global physical field does not cover offset point {point!r}'
      )
    ####
    if abs(float(characteristic.gamma) - request.target_gamma) > request.target_state_tolerance:
      raise ValueError(
        'target gamma does not match the exact global field gamma at offset '
        f'point {point!r}'
      )
    ####
    sampled.append(
      _conservative_from_characteristic(
        characteristic,
        float(total_pressure),
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
    )
  ####
  return np.asarray(sampled, dtype=float)
####


def solve_reflected_domain_global_mixed_regime_upstream_state_equation(
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult:
  """Consume a complete target in a solver-owned research interface strip."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.INVALID_INPUT,
      'request must be a typed upstream state-equation request',
    )
  ####
  if not request.closure.converged or not request.closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.SOURCE_CLOSURE_FAILURE,
      'upstream state-equation strip requires a locally verified global closure',
      request=request,
      source_closure=request.closure,
    )
  ####
  try:
    _validate_target_entropy_closure(
      request.target_conservative_state_profile,
      request.target_entropy_proxy_profile,
      request.target_gamma,
      request.gas_constant_J_kgK,
      request.target_entropy_consistency_tolerance,
    )
    target_segment_entropy_profile = _segment_average_scalars(
      request.target_entropy_proxy_profile
    )
    target_segment_profile, consistency_logs = _validate_target_entropy_closure(
      _segment_average_profile(request.target_conservative_state_profile),
      target_segment_entropy_profile,
      request.target_gamma,
      request.gas_constant_J_kgK,
      request.target_entropy_consistency_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.ENTROPY_TARGET_FAILURE,
      f'target conservative/entropy closure failed: {error}',
      request=request,
      source_closure=request.closure,
      target_frame_verified=True,
      entropy_consistency_log_residuals=(),
    )
  ####
  try:
    source_points, cells = _build_strip_geometry(
      request.target_points_m,
      request.normal_offset_m,
      request.offset_side,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.GEOMETRY_FAILURE,
      f'upstream interface-strip geometry failed: {error}',
      request=request,
      source_closure=request.closure,
      entropy_closed_target_profile=target_segment_profile,
      entropy_consistency_log_residuals=consistency_logs,
      target_frame_verified=True,
    )
  ####
  if len(cells) != len(target_segment_profile):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.TARGET_FRAME_FAILURE,
      'interface-strip cell count does not match the exact target segment frame',
      request=request,
      source_closure=request.closure,
      source_points_m=source_points,
      cell_vertices_by_cell_m=cells,
      entropy_closed_target_profile=target_segment_profile,
      entropy_consistency_log_residuals=consistency_logs,
      target_frame_verified=False,
    )
  ####
  try:
    source_vertex_samples = _sample_source_field(request, source_points)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.STATE_FAILURE,
      f'exact global offset-field sampling failed: {error}',
      request=request,
      source_closure=request.closure,
      source_points_m=source_points,
      cell_vertices_by_cell_m=cells,
      source_conservative_state_profile=(),
      entropy_closed_target_profile=target_segment_profile,
      entropy_consistency_log_residuals=consistency_logs,
      target_frame_verified=True,
      source_field_lineage_verified=False,
    )
  ####
  if len(source_vertex_samples) != len(cells) + 1:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.STATE_FAILURE,
      'exact global offset-field sampling did not cover every strip cell',
      request=request,
      source_closure=request.closure,
      source_points_m=source_points,
      cell_vertices_by_cell_m=cells,
      entropy_closed_target_profile=target_segment_profile,
      entropy_consistency_log_residuals=consistency_logs,
      target_frame_verified=True,
      source_field_lineage_verified=False,
    )
  ####
  source_segment_samples = 0.5 * (
    source_vertex_samples[:-1] + source_vertex_samples[1:]
  )
  source_profile = tuple(
    tuple(float(value) for value in state)
    for state in source_segment_samples
  )
  states = 0.5 * (
    np.asarray(target_segment_profile, dtype=float)
    + source_segment_samples
  )
  residual_history: list[float] = []
  final_residual: np.ndarray | None = None
  final_normalised: np.ndarray | None = None
  final_target_fluxes: tuple[tuple[float, float, float, float], ...] = ()
  final_source_fluxes: tuple[tuple[float, float, float, float], ...] = ()
  final_entropy_defects: tuple[float, ...] = ()
  pseudo_iteration_count = 0
  positivity_failure = False
  try:
    for iteration in range(request.max_pseudo_iterations):
      (
        residual,
        wave_sums,
        target_fluxes,
        source_fluxes,
        entropy_defects,
      ) = _residuals(
        states,
        cells,
        target_segment_profile,
        source_segment_samples,
        request.target_gamma,
        request.gas_constant_J_kgK,
      )
      normalised = _normalise_residuals(
        states,
        residual,
        cells,
        request.target_gamma,
        request.gas_constant_J_kgK,
      )
      maximum = float(np.max(normalised[:, 4]))
      if not isfinite(maximum):
        raise FloatingPointError('interface-strip residual is non-finite')
      ####
      residual_history.append(maximum)
      final_residual = residual
      final_normalised = normalised
      final_target_fluxes = target_fluxes
      final_source_fluxes = source_fluxes
      final_entropy_defects = entropy_defects
      pseudo_iteration_count = iteration + 1
      if maximum <= request.euler_residual_tolerance:
        break
      ####
      candidate = states.copy()
      for index, cell in enumerate(cells):
        area = abs(_signed_area(cell))
        timestep = request.cfl_number * area / max(wave_sums[index], 1.0e-12)
        delta = -timestep / area * residual[index]
        relaxation = request.relaxation
        accepted = False
        while relaxation >= 1.0e-4:
          trial = states[index] + relaxation * delta
          try:
            _primitive(
              trial,
              request.target_gamma,
              request.gas_constant_J_kgK,
            )
          except (FloatingPointError, ValueError):
            relaxation *= 0.5
            continue
          ####
          candidate[index] = trial
          accepted = True
          break
        ####
        if not accepted:
          positivity_failure = True
          break
        ####
      ####
      if positivity_failure:
        break
      ####
      states = candidate
    ####
    (
      final_residual,
      _final_wave_sums,
      final_target_fluxes,
      final_source_fluxes,
      final_entropy_defects,
    ) = _residuals(
      states,
      cells,
      target_segment_profile,
      source_segment_samples,
      request.target_gamma,
      request.gas_constant_J_kgK,
    )
    final_normalised = _normalise_residuals(
      states,
      final_residual,
      cells,
      request.target_gamma,
      request.gas_constant_J_kgK,
    )
    final_maximum = float(np.max(final_normalised[:, 4]))
    if not residual_history or abs(residual_history[-1] - final_maximum) > 0.0:
      residual_history.append(final_maximum)
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.ENTROPY_FLUX_FAILURE,
      f'upstream interface-strip entropy-compatible flux assembly failed: {error}',
      request=request,
      source_closure=request.closure,
      source_points_m=source_points,
      cell_vertices_by_cell_m=cells,
      source_conservative_state_profile=source_profile,
      entropy_closed_target_profile=target_segment_profile,
      entropy_consistency_log_residuals=consistency_logs,
      target_frame_verified=True,
      source_field_lineage_verified=True,
      global_field_sampled=True,
      target_conservative_state_consumed=True,
      entropy_target_consumed=True,
      upstream_state_equation_consumed=True,
      residual_history=tuple(residual_history),
      pseudo_iteration_count=pseudo_iteration_count,
    )
  ####
  if final_residual is None or final_normalised is None:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.RESIDUAL_FAILURE,
      'upstream interface-strip solver produced no residual sample',
      request=request,
      source_closure=request.closure,
      source_points_m=source_points,
      cell_vertices_by_cell_m=cells,
      source_conservative_state_profile=source_profile,
      entropy_closed_target_profile=target_segment_profile,
      entropy_consistency_log_residuals=consistency_logs,
      target_frame_verified=True,
      source_field_lineage_verified=True,
      global_field_sampled=True,
      target_conservative_state_consumed=True,
      entropy_target_consumed=True,
      upstream_state_equation_consumed=True,
    )
  ####
  target_entropy_logs = tuple(
    log(
      _entropy_proxy(
        states[index],
        request.target_gamma,
        request.gas_constant_J_kgK,
      )
      / target_segment_entropy_profile[index]
    )
    for index in range(len(cells))
  )
  maximum_residual = float(np.max(final_normalised[:, 4]))
  maximum_target_entropy = max(
    (abs(value) for value in target_entropy_logs),
    default=0.0,
  )
  maximum_entropy_defect = max(
    (abs(value) for value in final_entropy_defects),
    default=0.0,
  )
  residual_verified = maximum_residual <= request.euler_residual_tolerance
  entropy_flux_verified = bool(
    final_entropy_defects
    and all(isfinite(value) and value <= 1.0e-8 for value in final_entropy_defects)
  )
  if positivity_failure:
    status = (
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
      .POSITIVITY_FAILURE
    )
    message = 'upstream interface-strip pseudo-time update could not retain positivity'
  elif not entropy_flux_verified:
    status = (
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
      .ENTROPY_FLUX_FAILURE
    )
    message = 'upstream interface-strip entropy flux inequality remained open'
  elif residual_verified:
    status = (
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
      .CONVERGED_LOCAL_RESEARCH_UPSTREAM_STATE_EQUATION
    )
    message = (
      'exact conservative state and entropy target entered the solver-owned '
      'interface-strip Euler equations and the local residual gate closed; '
      'canonical global/free-boundary coupling remains blocked'
    )
  else:
    status = (
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
      .COMPLETED_RESEARCH_UPSTREAM_STATE_EQUATION_WITH_OPEN_RESIDUAL
    )
    message = (
      'exact conservative state and entropy target entered the solver-owned '
      'interface-strip Euler equations, but the local residual gate remains '
      'open; no global or production claim is made'
    )
  ####
  target_consumed = bool(
    len(final_target_fluxes) == len(target_segment_profile)
    and len(final_source_fluxes) == len(source_profile)
    and len(final_entropy_defects) >= 2 * len(target_segment_profile)
  )
  equation_consumed = bool(target_consumed)
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult(
    status=status if target_consumed else (
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus.CONSUMPTION_FAILURE
    ),
    request=request,
    source_closure=request.closure,
    source_points_m=source_points,
    cell_vertices_by_cell_m=cells,
    source_conservative_state_profile=source_profile,
    entropy_closed_target_profile=target_segment_profile,
    entropy_consistency_log_residuals=consistency_logs,
    final_conservative_states_by_cell=tuple(
      tuple(float(value) for value in state) for state in states
    ),
    residual_channels_by_cell=tuple(
      tuple(float(value) for value in row) for row in final_normalised
    ),
    residual_history=tuple(residual_history),
    target_boundary_fluxes=final_target_fluxes,
    source_boundary_fluxes=final_source_fluxes,
    target_boundary_entropy_log_residuals=target_entropy_logs,
    entropy_flux_defects=final_entropy_defects,
    pseudo_iteration_count=pseudo_iteration_count,
    maximum_conservative_euler_residual=maximum_residual,
    maximum_target_boundary_entropy_log_residual=maximum_target_entropy,
    maximum_entropy_flux_defect=maximum_entropy_defect,
    target_frame_verified=True,
    source_field_lineage_verified=True,
    global_field_sampled=True,
    target_conservative_state_consumed=target_consumed,
    entropy_target_consumed=bool(target_consumed),
    upstream_state_equation_consumed=equation_consumed,
    conservative_residuals_measured=True,
    conservative_residuals_verified=residual_verified,
    entropy_flux_verified=entropy_flux_verified,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit:
  """Independent replay of the retained strip equation channels."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
  result: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None
  residual_channels_recomputed: tuple[tuple[float, float, float, float, float], ...] = ()
  maximum_recomputed_residual: float | None = None
  target_boundary_replayed: bool = False
  source_boundary_replayed: bool = False
  entropy_target_replayed: bool = False
  residual_report_verified: bool = False
  independent_research_equation_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus,
    ):
      raise TypeError('status must be a typed upstream state-equation audit status')
    ####
    if self.result is not None and not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
    ):
      raise TypeError('result must be a typed upstream state-equation result')
    ####
    residuals = tuple(
      tuple(float(value) for value in residual)
      for residual in self.residual_channels_recomputed
    )
    if any(
      len(residual) != 5 or any(not isfinite(value) for value in residual)
      for residual in residuals
    ):
      raise ValueError('recomputed residuals must contain finite five-tuples')
    ####
    if self.maximum_recomputed_residual is not None:
      maximum = float(self.maximum_recomputed_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError('maximum_recomputed_residual must be finite and nonnegative')
      ####
      object.__setattr__(self, 'maximum_recomputed_residual', maximum)
    ####
    for name in (
      'target_boundary_replayed',
      'source_boundary_replayed',
      'entropy_target_replayed',
      'residual_report_verified',
      'independent_research_equation_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('upstream state-equation audit cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('upstream state-equation audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'residual_channels_recomputed', residuals)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
      .VERIFIED_RESEARCH_INTERFACE_STRIP
      and self.independent_research_equation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_OPERATOR_ID
        + '-audit'
      ),
      'status': self.status.value,
      'converged': self.converged,
      'residual_channels_recomputed': self.residual_channels_recomputed,
      'maximum_recomputed_residual': self.maximum_recomputed_residual,
      'target_boundary_replayed': self.target_boundary_replayed,
      'source_boundary_replayed': self.source_boundary_replayed,
      'entropy_target_replayed': self.entropy_target_replayed,
      'residual_report_verified': self.residual_report_verified,
      'independent_research_equation_verified': (
        self.independent_research_equation_verified
      ),
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'message': self.message,
    }
  ####
####


def audit_reflected_domain_global_mixed_regime_upstream_state_equation(
  result: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit:
  """Replay target/source flux equations without reusing the report values."""

  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit(
      status=MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
      .INVALID_INPUT,
      result=None,
      message='result must be a typed upstream state-equation result',
    )
  ####
  if not result.research_state_equation_consumed or result.request is None:
    return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit(
      status=MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
      .CONSUMPTION_FAILURE,
      result=result,
      message=(
        'independent replay requires the result to retain exact target/source '
        'equation-consumption evidence'
      ),
    )
  ####
  try:
    states = np.asarray(result.final_conservative_states_by_cell, dtype=float)
    target_states = tuple(result.entropy_closed_target_profile)
    source_states = np.asarray(result.source_conservative_state_profile, dtype=float)
    (
      residual,
      _wave_sums,
      target_fluxes,
      source_fluxes,
      _entropy_defects,
    ) = _residuals(
      states,
      result.cell_vertices_by_cell_m,
      target_states,
      source_states,
      result.request.target_gamma,
      result.request.gas_constant_J_kgK,
    )
    recomputed = _normalise_residuals(
      states,
      residual,
      result.cell_vertices_by_cell_m,
      result.request.target_gamma,
      result.request.gas_constant_J_kgK,
    )
    recomputed_rows = tuple(
      tuple(float(value) for value in row) for row in recomputed
    )
    maximum = float(np.max(recomputed[:, 4]))
    target_replayed = target_fluxes == result.target_boundary_fluxes
    source_replayed = source_fluxes == result.source_boundary_fluxes
    entropy_replayed = bool(
      len(result.entropy_consistency_log_residuals)
      == len(result.entropy_closed_target_profile)
      and all(
        abs(value) <= result.request.target_entropy_consistency_tolerance
        for value in result.entropy_consistency_log_residuals
      )
    )
    residual_report_verified = bool(
      len(recomputed_rows) == len(result.residual_channels_by_cell)
      and all(
        abs(actual - expected) <= 1.0e-12 * max(1.0, abs(expected), abs(actual))
        for actual_row, expected_row in zip(
          recomputed_rows,
          result.residual_channels_by_cell,
          strict=True,
        )
        for actual, expected in zip(actual_row, expected_row, strict=True)
      )
    )
    independent = bool(
      target_replayed
      and source_replayed
      and entropy_replayed
      and residual_report_verified
      and result.target_conservative_state_consumed
      and result.entropy_target_consumed
      and result.source_field_lineage_verified
      and result.global_field_sampled
    )
    return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit(
      status=(
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
        .VERIFIED_RESEARCH_INTERFACE_STRIP
        if independent
        else MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
        .REPLAY_FAILURE
      ),
      result=result,
      residual_channels_recomputed=recomputed_rows,
      maximum_recomputed_residual=maximum,
      target_boundary_replayed=target_replayed,
      source_boundary_replayed=source_replayed,
      entropy_target_replayed=entropy_replayed,
      residual_report_verified=residual_report_verified,
      independent_research_equation_verified=independent,
      message=(
        'independent replay reproduced the exact target/source entropy-compatible '
        'finite-volume boundary equations'
        if independent
        else 'independent replay did not reproduce the retained equation report'
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit(
      status=(
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAuditStatus
        .REPLAY_FAILURE
      ),
      result=result,
      message=f'independent upstream state-equation replay failed: {error}',
    )
  ####
####
