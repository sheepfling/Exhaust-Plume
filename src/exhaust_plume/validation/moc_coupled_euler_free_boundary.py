"""Independent audit for the coupled Euler/free-boundary research lane.

The model-side solver stores a conservative field and its normalized residual
channels.  This module reconstructs the curvilinear mesh, thermodynamic state,
interior Rusanov face fluxes, specified-pressure material-streamline boundary
flux, and entropy-proxy bounds from that retained data.  It intentionally does
not promote the field: a passing audit is local evidence only until the case
ladder, external observations, and contract review are complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Any

import numpy as np

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerSubsonicPressureBudget,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_AUDIT_OPERATOR_ID',
  'MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus',
  'MocReflectedDomainCoupledEulerFreeBoundaryAudit',
  'measure_reflected_domain_coupled_euler_free_boundary',
)


MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.coupled-euler-free-boundary-audit'
)
_CHANNEL_COUNT = 5


class MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus(str, Enum):
  """Outcome for the independent conservative-field audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged-local-coupled-euler-free-boundary-audit'
  )
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'coupled-euler-audit-geometry-failure'
  STATE_FAILURE = 'coupled-euler-audit-state-failure'
  THERMODYNAMIC_FAILURE = 'coupled-euler-audit-thermodynamic-failure'
  RESIDUAL_FAILURE = 'coupled-euler-audit-residual-failure'
  ENTROPY_FAILURE = 'coupled-euler-audit-entropy-failure'
  BOUNDARY_FAILURE = 'coupled-euler-audit-boundary-failure'
  PRESSURE_BUDGET_FAILURE = 'coupled-euler-audit-pressure-budget-failure'
  FLAG_FAILURE = 'coupled-euler-audit-promotion-flag-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerFreeBoundaryAudit:
  """Recomputed local evidence for one coupled-field result."""

  status: MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_COUPLED_EULER_FREE_BOUNDARY_AUDIT_OPERATOR_ID
  )
  solver_status: str | None = None
  cell_count: int = 0
  expected_cell_count: int = 0
  maximum_conservative_mass_residual: float | None = None
  maximum_conservative_streamwise_momentum_residual: float | None = None
  maximum_conservative_transverse_momentum_residual: float | None = None
  maximum_conservative_energy_residual: float | None = None
  maximum_conservative_euler_residual: float | None = None
  maximum_free_boundary_pressure_residual_Pa: float | None = None
  maximum_free_boundary_normal_velocity_residual_fraction: float | None = None
  maximum_entropy_transport_residual: float | None = None
  geometry_verified: bool = False
  state_samples_verified: bool = False
  thermodynamics_verified: bool = False
  residual_channels_recomputed: bool = False
  residual_report_verified: bool = False
  free_boundary_report_verified: bool = False
  pressure_budget_verified: bool = False
  entropy_transport_verified: bool = False
  promotion_flags_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  physical_closure_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus'
      )
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'candidate must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult or None'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    if self.solver_status is not None:
      object.__setattr__(self, 'solver_status', str(self.solver_status))
    ####
    for name in ('cell_count', 'expected_cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'maximum_conservative_mass_residual',
      'maximum_conservative_streamwise_momentum_residual',
      'maximum_conservative_transverse_momentum_residual',
      'maximum_conservative_energy_residual',
      'maximum_conservative_euler_residual',
      'maximum_free_boundary_pressure_residual_Pa',
      'maximum_free_boundary_normal_velocity_residual_fraction',
      'maximum_entropy_transport_residual',
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
      'geometry_verified',
      'state_samples_verified',
      'thermodynamics_verified',
      'residual_channels_recomputed',
      'residual_report_verified',
      'free_boundary_report_verified',
      'entropy_transport_verified',
      'promotion_flags_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'physical_closure_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('an independent research audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('an independent research audit must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('an independent research audit cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.geometry_verified
      and self.state_samples_verified
      and self.thermodynamics_verified
      and self.residual_channels_recomputed
      and self.residual_report_verified
      and self.free_boundary_report_verified
      and self.pressure_budget_verified
      and self.entropy_transport_verified
      and self.promotion_flags_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'cell_count': self.cell_count,
      'expected_cell_count': self.expected_cell_count,
      'maximum_conservative_mass_residual': (
        self.maximum_conservative_mass_residual
      ),
      'maximum_conservative_streamwise_momentum_residual': (
        self.maximum_conservative_streamwise_momentum_residual
      ),
      'maximum_conservative_transverse_momentum_residual': (
        self.maximum_conservative_transverse_momentum_residual
      ),
      'maximum_conservative_energy_residual': (
        self.maximum_conservative_energy_residual
      ),
      'maximum_conservative_euler_residual': (
        self.maximum_conservative_euler_residual
      ),
      'maximum_free_boundary_pressure_residual_Pa': (
        self.maximum_free_boundary_pressure_residual_Pa
      ),
      'maximum_free_boundary_normal_velocity_residual_fraction': (
        self.maximum_free_boundary_normal_velocity_residual_fraction
      ),
      'maximum_entropy_transport_residual': (
        self.maximum_entropy_transport_residual
      ),
      'geometry_verified': self.geometry_verified,
      'state_samples_verified': self.state_samples_verified,
      'thermodynamics_verified': self.thermodynamics_verified,
      'residual_channels_recomputed': self.residual_channels_recomputed,
      'residual_report_verified': self.residual_report_verified,
      'free_boundary_report_verified': self.free_boundary_report_verified,
      'pressure_budget_verified': self.pressure_budget_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
      'promotion_flags_verified': self.promotion_flags_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'message': self.message,
      'claim_status': (
        'independent-local-coupled-euler-audit-only; canonical free-boundary, '
        'external validation, and production promotion remain blocked'
      ),
    }
  ####
####


def _failure(
  status: MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus,
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult | None,
  message: str,
) -> MocReflectedDomainCoupledEulerFreeBoundaryAudit:
  return MocReflectedDomainCoupledEulerFreeBoundaryAudit(
    status=status,
    candidate=candidate,
    solver_status=None if candidate is None else candidate.status.value,
    message=message,
  )
####


def _primitive(
  state: np.ndarray,
  gamma: float,
  gas_constant: float,
) -> tuple[float, float, float, float, float, float]:
  density = float(state[0])
  if not isfinite(density) or density <= 0.0:
    raise FloatingPointError('audited density is not positive')
  ####
  velocity_u = float(state[1]) / density
  velocity_v = float(state[2]) / density
  kinetic = 0.5 * density * (
    velocity_u * velocity_u + velocity_v * velocity_v
  )
  pressure = (gamma - 1.0) * (float(state[3]) - kinetic)
  if not isfinite(pressure) or pressure <= 0.0:
    raise FloatingPointError('audited pressure is not positive')
  ####
  temperature = pressure / (density * gas_constant)
  sound_speed = sqrt(gamma * pressure / density)
  if not isfinite(temperature) or temperature <= 0.0:
    raise FloatingPointError('audited temperature is not positive')
  ####
  return density, velocity_u, velocity_v, pressure, temperature, sound_speed
####


def _from_sample(
  total_pressure: float,
  mach: float,
  flow_angle: float,
  gamma: float,
  total_temperature: float,
  gas_constant: float,
) -> np.ndarray:
  pressure_factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_pressure = total_pressure / pressure_factor ** (
    gamma / (gamma - 1.0)
  )
  static_temperature = total_temperature / pressure_factor
  density = static_pressure / (gas_constant * static_temperature)
  sound_speed = sqrt(gamma * gas_constant * static_temperature)
  speed = mach * sound_speed
  return np.array(
    (
      density,
      density * speed * np.cos(flow_angle),
      density * speed * np.sin(flow_angle),
      static_pressure / (gamma - 1.0)
      + 0.5 * density * speed * speed,
    ),
    dtype=float,
  )
####


def _interpolate_inlet(
  ordinate: float,
  points: tuple[tuple[float, float], ...],
  samples: tuple[Any, ...],
  gamma: float,
  total_temperature: float,
  gas_constant: float,
) -> np.ndarray:
  ordinates = np.asarray([point[1] for point in points], dtype=float)
  clamped = float(np.clip(ordinate, ordinates[0], ordinates[-1]))
  total_pressure = float(
    np.interp(
      clamped,
      ordinates,
      [sample.total_pressure_Pa for sample in samples],
    )
  )
  mach = float(
    np.interp(clamped, ordinates, [sample.mach for sample in samples])
  )
  angle = float(
    np.interp(
      clamped,
      ordinates,
      [sample.flow_angle_rad for sample in samples],
    )
  )
  return _from_sample(
    total_pressure,
    mach,
    angle,
    gamma,
    total_temperature,
    gas_constant,
  )
####


def _face(
  first: np.ndarray,
  second: np.ndarray,
) -> tuple[float, float, float]:
  delta = second - first
  length = float(np.hypot(delta[0], delta[1]))
  if not isfinite(length) or length <= 0.0:
    raise ValueError('audited mesh contains a zero-length face')
  ####
  return float(delta[1] / length), float(-delta[0] / length), length
####


def _flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  density, velocity_u, velocity_v, pressure, _temperature, sound_speed = (
    _primitive(state, gamma, gas_constant)
  )
  normal_velocity = velocity_u * normal_x + velocity_v * normal_y
  return (
    np.array(
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


def _rusanov(
  left: np.ndarray,
  right: np.ndarray,
  normal_x: float,
  normal_y: float,
  length: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  left_flux, left_wave = _flux(
    left,
    normal_x,
    normal_y,
    gamma,
    gas_constant,
  )
  right_flux, right_wave = _flux(
    right,
    normal_x,
    normal_y,
    gamma,
    gas_constant,
  )
  wave = max(left_wave, right_wave)
  return (
    0.5 * (left_flux + right_flux)
    - 0.5 * wave * (right - left)
  ) * length, wave
####


def _wall_flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  length: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  _density, _velocity_u, _velocity_v, pressure, _temperature, sound_speed = (
    _primitive(state, gamma, gas_constant)
  )
  return (
    np.array((0.0, pressure * normal_x, pressure * normal_y, 0.0)) * length,
    sound_speed,
  )
####


def _specified_pressure_wall_flux(
  state: np.ndarray,
  boundary_pressure: float,
  normal_x: float,
  normal_y: float,
  length: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  """Re-derive the solver's pressure-boundary flux independently."""

  _density, _velocity_u, _velocity_v, _pressure, _temperature, sound_speed = (
    _primitive(state, gamma, gas_constant)
  )
  if not isfinite(boundary_pressure) or boundary_pressure <= 0.0:
    raise ValueError('specified pressure boundary must be finite and positive')
  ####
  return (
    np.array((0.0, boundary_pressure * normal_x, boundary_pressure * normal_y, 0.0))
    * length,
    sound_speed,
  )
####


def _ambient_ghost(
  state: np.ndarray,
  ambient_pressure: float,
  gamma: float,
  gas_constant: float,
) -> np.ndarray:
  density, velocity_u, velocity_v, pressure, _temperature, _sound_speed = (
    _primitive(state, gamma, gas_constant)
  )
  entropy_proxy = pressure / density ** gamma
  ghost_density = (ambient_pressure / entropy_proxy) ** (1.0 / gamma)
  return np.array(
    (
      ghost_density,
      ghost_density * velocity_u,
      ghost_density * velocity_v,
      ambient_pressure / (gamma - 1.0)
      + 0.5 * ghost_density * (velocity_u * velocity_u + velocity_v * velocity_v),
    ),
    dtype=float,
  )
####


def _rederive_subsonic_pressure_budget(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> dict[str, Any]:
  """Recompute the pressure budget without calling the model helper."""

  request = candidate.request
  if request is None:
    raise ValueError('candidate must retain its coupled Euler request')
  ####
  sample = request.mixed_regime_request.control_section.samples[-1]
  gamma = float(sample.gamma)
  target_pressure = float(request.mixed_regime_request.ambient_pressure_Pa)
  reference_total_pressure = float(sample.total_pressure_Pa)
  if not isfinite(gamma) or gamma <= 1.0:
    raise ArithmeticError('audited control-section gamma is invalid')
  ####
  if not isfinite(target_pressure) or target_pressure <= 0.0:
    raise ArithmeticError('audited target ambient pressure is invalid')
  ####
  if not isfinite(reference_total_pressure) or reference_total_pressure <= 0.0:
    raise ArithmeticError('audited outer control-section total pressure is invalid')
  ####
  sonic_pressure_factor = (1.0 + 0.5 * (gamma - 1.0)) ** (
    gamma / (gamma - 1.0)
  )
  lower_bound = reference_total_pressure / sonic_pressure_factor
  upper_bound = reference_total_pressure
  maximum_compatible_total_pressure = target_pressure * sonic_pressure_factor
  compatibility_ratio = maximum_compatible_total_pressure / reference_total_pressure
  pressure_scale = max(target_pressure, lower_bound, upper_bound, 1.0)
  tolerance = 1.0e-10 * pressure_scale
  if target_pressure < lower_bound - tolerance:
    status = 'below-isentropic-subsonic-pressure-bounds'
  elif target_pressure > upper_bound + tolerance:
    status = 'above-isentropic-subsonic-pressure-bounds'
  else:
    status = 'within-isentropic-subsonic-pressure-bounds'
  ####
  return {
    'status': status,
    'target_static_pressure_Pa': target_pressure,
    'reference_total_pressure_Pa': reference_total_pressure,
    'subsonic_static_pressure_lower_bound_Pa': lower_bound,
    'subsonic_static_pressure_upper_bound_Pa': upper_bound,
    'maximum_total_pressure_compatible_with_target_Pa': (
      maximum_compatible_total_pressure
    ),
    'total_pressure_compatibility_ratio': compatibility_ratio,
    'minimum_additional_total_pressure_loss_fraction': max(
      0.0,
      1.0 - compatibility_ratio,
    ),
    'gamma': gamma,
    'reachable_without_additional_entropy': (
      status == 'within-isentropic-subsonic-pressure-bounds'
    ),
    'source': 'derived-outer-control-section-isentropic-pressure-budget',
  }
####


def _audit_field(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> dict[str, Any]:
  request = candidate.request
  if request is None:
    raise ValueError('candidate must retain its coupled Euler request')
  ####
  mixed = request.mixed_regime_request
  control = mixed.control_section
  axial_count = request.axial_cell_count
  transverse_count = request.transverse_cell_count
  expected_cell_count = axial_count * transverse_count
  if len(candidate.x_stations_m) != axial_count + 1:
    raise ValueError('audited x-station count does not match the request')
  ####
  if len(candidate.free_boundary_points_m) != axial_count + 1:
    raise ValueError('audited free-boundary point count does not match the request')
  ####
  for first, second in zip(candidate.x_stations_m, candidate.x_stations_m[1:]):
    if second <= first:
      raise ValueError('audited x stations must be strictly increasing')
    ####
  ####
  if any(
    abs(point[0] - x) > 1.0e-10
    for x, point in zip(candidate.x_stations_m, candidate.free_boundary_points_m)
  ):
    raise ValueError('free-boundary x coordinates do not match x stations')
  ####
  lower_ordinate = control.points_m[0][1]
  heights = np.asarray(
    [point[1] - lower_ordinate for point in candidate.free_boundary_points_m],
    dtype=float,
  )
  if np.any(~np.isfinite(heights)) or np.any(heights <= 0.0):
    raise ValueError('audited free-boundary heights must be positive')
  ####
  states = np.asarray(candidate.conservative_states_by_cell, dtype=float)
  if states.shape != (expected_cell_count, 4):
    raise ValueError('audited conservative state count does not match the mesh')
  ####
  states = states.reshape((axial_count, transverse_count, 4))
  reported_channels = np.asarray(
    candidate.residual_channels_by_cell,
    dtype=float,
  )
  if reported_channels.shape != (expected_cell_count, _CHANNEL_COUNT):
    raise ValueError('audited residual channel count does not match the mesh')
  ####
  reported_channels = reported_channels.reshape(
    (axial_count, transverse_count, _CHANNEL_COUNT)
  )
  original_reported_channels = reported_channels.copy()
  gammas = tuple(float(sample.gamma) for sample in control.samples)
  if max(gammas) - min(gammas) > 1.0e-10:
    raise ArithmeticError('audited control section has nonuniform gamma')
  ####
  gamma = gammas[0]
  pressure_budget = _rederive_subsonic_pressure_budget(candidate)
  thermodynamic_inputs_verified = True
  for sample in control.samples:
    pressure_factor = 1.0 + 0.5 * (gamma - 1.0) * sample.mach * sample.mach
    expected_static_pressure = sample.total_pressure_Pa / pressure_factor ** (
      gamma / (gamma - 1.0)
    )
    pressure_scale = max(expected_static_pressure, sample.static_pressure_Pa, 1.0)
    if (
      not isfinite(expected_static_pressure)
      or abs(expected_static_pressure - sample.static_pressure_Pa) / pressure_scale
      > 1.0e-8
    ):
      thermodynamic_inputs_verified = False
      break
    ####
  ####
  if not thermodynamic_inputs_verified:
    raise ArithmeticError(
      'audited control-section static pressure is inconsistent with its '
      'total pressure, Mach number, and gamma'
    )
  ####
  gas_constant = request.gas_constant_J_kgK
  points = np.empty((axial_count + 1, transverse_count + 1, 2), dtype=float)
  eta = np.linspace(0.0, 1.0, transverse_count + 1)
  points[:, :, 0] = np.asarray(candidate.x_stations_m)[:, None]
  points[:, :, 1] = lower_ordinate + heights[:, None] * eta[None, :]
  corners = np.empty((axial_count, transverse_count, 4, 2), dtype=float)
  areas = np.empty((axial_count, transverse_count), dtype=float)
  for i in range(axial_count):
    for j in range(transverse_count):
      cell = np.array(
        (points[i, j], points[i + 1, j], points[i + 1, j + 1], points[i, j + 1]),
        dtype=float,
      )
      corners[i, j] = cell
      areas[i, j] = 0.5 * abs(
        sum(
          cell[k, 0] * cell[(k + 1) % 4, 1]
          - cell[(k + 1) % 4, 0] * cell[k, 1]
          for k in range(4)
        )
      )
      if not isfinite(float(areas[i, j])) or areas[i, j] <= 0.0:
        raise ValueError('audited mesh contains a nonpositive cell area')
      ####
    ####
  ####
  retained_vertices_verified = True
  retained_vertices = candidate.cell_vertices_by_cell_m
  if retained_vertices:
    if len(retained_vertices) != expected_cell_count:
      raise ValueError(
        'retained cell-vertex count does not match the audited mesh'
      )
    ####
    retained_array = np.asarray(retained_vertices, dtype=float)
    if retained_array.shape != (expected_cell_count, 4, 2):
      raise ValueError('retained cell vertices must be quadrilateral mesh cells')
    ####
    retained_vertices_verified = bool(
      np.allclose(
        retained_array.reshape((axial_count, transverse_count, 4, 2)),
        corners,
        rtol=3.0e-10,
        atol=1.0e-12,
      )
    )
    if not retained_vertices_verified:
      raise ValueError('retained cell vertices do not match the request mesh')
    ####
  ####
  residual = np.zeros_like(states)
  top_pressure = np.zeros(axial_count, dtype=float)
  top_normal_velocity = np.zeros(axial_count, dtype=float)
  speeds = []
  entropy_values = []
  inlet_entropy = []
  for first, second in zip(control.points_m, control.points_m[1:]):
    state = _interpolate_inlet(
      0.5 * (first[1] + second[1]),
      control.points_m,
      control.samples,
      gamma,
      request.reference_total_temperature_K,
      gas_constant,
    )
    density, _u, _v, pressure, _temperature, _sound_speed = _primitive(
      state,
      gamma,
      gas_constant,
    )
    inlet_entropy.append(pressure / density ** gamma)
  ####
  for i in range(axial_count):
    for j in range(transverse_count):
      cell = corners[i, j]
      state = states[i, j]
      density, velocity_u, velocity_v, pressure, _temperature, sound_speed = (
        _primitive(state, gamma, gas_constant)
      )
      speeds.append(sqrt(velocity_u * velocity_u + velocity_v * velocity_v))
      entropy_values.append(pressure / density ** gamma)
      perimeter = 0.0
      for edge_index in range(4):
        first = cell[edge_index]
        second = cell[(edge_index + 1) % 4]
        normal_x, normal_y, length = _face(first, second)
        perimeter += length
        if edge_index == 0 and j == 0:
          flux, wave = _wall_flux(
            state,
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
        elif edge_index == 0:
          flux, wave = _rusanov(
            state,
            states[i, j - 1],
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
        elif edge_index == 1 and i == axial_count - 1:
          if request.outlet_static_pressure_Pa is None:
            flux, wave = _flux(
              state,
              normal_x,
              normal_y,
              gamma,
              gas_constant,
            )
            flux = flux * length
          else:
            outlet = _ambient_ghost(
              state,
              request.outlet_static_pressure_Pa,
              gamma,
              gas_constant,
            )
            flux, wave = _rusanov(
              state,
              outlet,
              normal_x,
              normal_y,
              length,
              gamma,
              gas_constant,
            )
          ####
        elif edge_index == 1:
          flux, wave = _rusanov(
            state,
            states[i + 1, j],
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
        elif edge_index == 2 and j == transverse_count - 1:
          flux, wave = _specified_pressure_wall_flux(
            state,
            mixed.ambient_pressure_Pa,
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
          top_pressure[i] = pressure
          top_normal_velocity[i] = velocity_u * normal_x + velocity_v * normal_y
        elif edge_index == 2:
          flux, wave = _rusanov(
            state,
            states[i, j + 1],
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
        elif i == 0:
          inlet = _interpolate_inlet(
            0.5 * (first[1] + second[1]),
            control.points_m,
            control.samples,
            gamma,
            request.reference_total_temperature_K,
            gas_constant,
          )
          flux, wave = _rusanov(
            state,
            inlet,
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
        else:
          flux, wave = _rusanov(
            state,
            states[i - 1, j],
            normal_x,
            normal_y,
            length,
            gamma,
            gas_constant,
          )
        ####
        residual[i, j] += flux
      ####
      mass_scale = max(density * sound_speed * perimeter, 1.0e-12)
      momentum_scale = max(
        (density * (velocity_u * velocity_u + velocity_v * velocity_v) + pressure)
        * perimeter,
        1.0e-12,
      )
      energy_scale = max((state[3] + pressure) * sound_speed * perimeter, 1.0e-12)
      residual_channels = (
        abs(residual[i, j, 0]) / mass_scale,
        abs(residual[i, j, 1]) / momentum_scale,
        abs(residual[i, j, 2]) / momentum_scale,
        abs(residual[i, j, 3]) / energy_scale,
      )
      residual[i, j] = residual[i, j]
      reported_channels[i, j, :4] = np.asarray(residual_channels)
      reported_channels[i, j, 4] = max(residual_channels)
    ####
  ####
  recomputed_channels = reported_channels.copy()
  # ``reported_channels`` now contains the recomputed values; retain a separate
  # copy comparison from the raw payload before returning through the caller.
  entropy_minimum = min(inlet_entropy)
  entropy_maximum = max(inlet_entropy)
  entropy_residual = 0.0
  for value in entropy_values:
    if value < entropy_minimum:
      entropy_residual = max(
        entropy_residual,
        (entropy_minimum - value) / max(entropy_maximum, 1.0e-12),
      )
    ####
    if value > entropy_maximum:
      entropy_residual = max(
        entropy_residual,
        (value - entropy_maximum) / max(entropy_maximum, 1.0e-12),
      )
    ####
  ####
  # The candidate arrays are checked outside this helper; this return keeps the
  # independent flux reconstruction separate from report reconciliation.
  return {
    'geometry_verified': retained_vertices_verified,
    'state_samples_verified': True,
    'thermodynamics_verified': thermodynamic_inputs_verified,
    'recomputed_channels': recomputed_channels,
    'reported_channels': original_reported_channels,
    'top_pressure': top_pressure,
    'top_normal_velocity': top_normal_velocity,
    'speeds': np.asarray(speeds, dtype=float),
    'entropy_residual': entropy_residual,
    'entropy_verified': entropy_residual <= 0.05,
    'pressure_budget': pressure_budget,
    'expected_cell_count': expected_cell_count,
  }
####


def measure_reflected_domain_coupled_euler_free_boundary(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> MocReflectedDomainCoupledEulerFreeBoundaryAudit:
  """Recompute conservative residuals and boundary evidence independently."""

  if not isinstance(
    candidate,
    MocReflectedDomainCoupledEulerFreeBoundaryResult,
  ):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.INVALID_INPUT,
      None,
      'candidate must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryResult',
    )
  ####
  try:
    raw = _audit_field(candidate)
  except ArithmeticError as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.THERMODYNAMIC_FAILURE,
      candidate,
      str(error),
    )
  except FloatingPointError as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.STATE_FAILURE,
      candidate,
      str(error),
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.GEOMETRY_FAILURE,
      candidate,
      str(error),
    )
  ####
  recomputed = np.asarray(raw['recomputed_channels'], dtype=float)
  reported = np.asarray(raw['reported_channels'], dtype=float)
  report_verified = bool(np.allclose(recomputed, reported, rtol=3.0e-6, atol=1.0e-10))
  expected_budget = raw['pressure_budget']
  reported_budget = candidate.subsonic_pressure_budget
  pressure_budget_verified = bool(
    isinstance(
      reported_budget,
      MocReflectedDomainCoupledEulerSubsonicPressureBudget,
    )
    and reported_budget.status.value == expected_budget['status']
    and reported_budget.source == expected_budget['source']
    and reported_budget.reachable_without_additional_entropy
    == expected_budget['reachable_without_additional_entropy']
    and all(
      np.isclose(
        getattr(reported_budget, name),
        expected_budget[name],
        rtol=3.0e-6,
        atol=1.0e-10,
      )
      for name in (
        'target_static_pressure_Pa',
        'reference_total_pressure_Pa',
        'subsonic_static_pressure_lower_bound_Pa',
        'subsonic_static_pressure_upper_bound_Pa',
        'maximum_total_pressure_compatible_with_target_Pa',
        'total_pressure_compatibility_ratio',
        'minimum_additional_total_pressure_loss_fraction',
        'gamma',
      )
    )
  )
  maxima = tuple(float(np.max(recomputed[..., index])) for index in range(_CHANNEL_COUNT))
  residuals_verified = maxima[4] <= candidate.request.euler_residual_tolerance
  pressure = np.asarray(raw['top_pressure'], dtype=float)
  normal_velocity = np.asarray(raw['top_normal_velocity'], dtype=float)
  ambient_pressure = candidate.request.mixed_regime_request.ambient_pressure_Pa
  pressure_residual = float(np.max(np.abs(pressure - ambient_pressure)))
  maximum_speed = max(float(np.max(raw['speeds'])), 1.0e-12)
  normal_fraction = float(np.max(np.abs(normal_velocity))) / maximum_speed
  boundary_report_verified = bool(
    np.allclose(
      np.asarray(candidate.free_boundary_pressure_residuals_Pa),
      np.abs(pressure - ambient_pressure),
      rtol=3.0e-6,
      atol=1.0e-8,
    )
    and np.allclose(
      np.asarray(candidate.free_boundary_normal_velocity_residuals_m_s),
      np.abs(normal_velocity),
      rtol=3.0e-6,
      atol=1.0e-8,
    )
    and candidate.maximum_free_boundary_pressure_residual_Pa is not None
    and abs(candidate.maximum_free_boundary_pressure_residual_Pa - pressure_residual)
    <= max(1.0e-8, 3.0e-6 * pressure_residual)
  )
  promotion_flags_verified = bool(
    candidate.chain_promotion_blocked
    and not candidate.production_claim_allowed
    and not candidate.canonical_euler_verified
    and not candidate.canonical_free_boundary_verified
    and not candidate.external_validation_verified
  )
  if not promotion_flags_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.FLAG_FAILURE
    message = 'candidate promotion flags do not retain the research-only stop'
  elif not report_verified or not residuals_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.RESIDUAL_FAILURE
    message = 'independent conservative residuals disagree or exceed tolerance'
  elif not pressure_budget_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.PRESSURE_BUDGET_FAILURE
    message = 'candidate subsonic pressure-budget diagnostic does not match the request'
  elif not boundary_report_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.BOUNDARY_FAILURE
    message = 'candidate free-boundary diagnostic arrays do not match the field'
  elif (
    pressure_residual
    > candidate.request.free_boundary_pressure_tolerance_fraction * ambient_pressure
    or normal_fraction
    > candidate.request.free_boundary_normal_velocity_tolerance_fraction
  ):
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.BOUNDARY_FAILURE
    message = 'independent ambient pressure or tangency residual exceeds tolerance'
  elif not bool(raw['entropy_verified']):
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.ENTROPY_FAILURE
    message = 'independent entropy-proxy transport bounds were not satisfied'
  else:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent conservative Euler, thermodynamic, entropy, and '
      'free-boundary checks passed; promotion remains blocked'
    )
  ####
  return MocReflectedDomainCoupledEulerFreeBoundaryAudit(
    status=status,
    candidate=candidate,
    solver_status=candidate.status.value,
    cell_count=raw['expected_cell_count'],
    expected_cell_count=raw['expected_cell_count'],
    maximum_conservative_mass_residual=maxima[0],
    maximum_conservative_streamwise_momentum_residual=maxima[1],
    maximum_conservative_transverse_momentum_residual=maxima[2],
    maximum_conservative_energy_residual=maxima[3],
    maximum_conservative_euler_residual=maxima[4],
    maximum_free_boundary_pressure_residual_Pa=pressure_residual,
    maximum_free_boundary_normal_velocity_residual_fraction=normal_fraction,
    maximum_entropy_transport_residual=float(raw['entropy_residual']),
    geometry_verified=bool(raw['geometry_verified']),
    state_samples_verified=bool(raw['state_samples_verified']),
    thermodynamics_verified=bool(raw['thermodynamics_verified']),
    residual_channels_recomputed=True,
    residual_report_verified=report_verified and residuals_verified,
    free_boundary_report_verified=boundary_report_verified,
    pressure_budget_verified=pressure_budget_verified,
    entropy_transport_verified=bool(raw['entropy_verified']),
    promotion_flags_verified=promotion_flags_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    physical_closure_verified=False,
    message=message,
  )
####
