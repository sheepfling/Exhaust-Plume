"""Independent audit for the coupled Euler/free-boundary research lane.

The model-side solver stores a conservative field and its normalized residual
channels.  This module reconstructs the curvilinear mesh, thermodynamic state,
interior Rusanov face fluxes, specified-pressure material-streamline boundary
flux, and an entropy inequality from that retained data.  Entropy production is
retained as diagnostic evidence while entropy loss remains a local failure.  It
intentionally does not promote the field: a passing audit is local evidence only
until the case ladder, external observations, and contract review are complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Any

import numpy as np

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerControlSectionCompatibility,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
  MocReflectedDomainCoupledEulerSubsonicPressureBudget,
  MocReflectedDomainCoupledEulerTransonicFrontierCompatibility,
  MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicTransitionAudit,
  MocTransonicTransitionAuditStatus,
  MocTransonicTransitionRequest,
  MocTransonicTransitionResult,
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryResult,
  measure_moc_transonic_transition,
  measure_moc_transonic_shock_geometry,
  solve_moc_transonic_shock_geometry,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceProfile,
  MocTransonicShockInterfaceResult,
  MocTransonicShockInterfaceStatus,
)
from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfile,
  MocPhysicalFieldContinuationProfileResult,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionResult,
)
from exhaust_plume.validation.moc_transonic_interface import (
  measure_moc_transonic_shock_interface,
  measure_moc_transonic_shock_interface_profile,
)
from exhaust_plume.validation.moc_field_continuation import (
  measure_moc_physical_field_continuation_profile,
)
from exhaust_plume.validation.moc_physical_field_shock_front import (
  measure_moc_physical_field_shock_front_condition,
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


def _effective_field_inlet_geometry(
  request: Any,
) -> tuple[float, float, float]:
  """Return the exact downstream-field inlet geometry for an audited request."""

  control = request.mixed_regime_request.control_section
  control_x = float(control.points_m[0][0])
  control_lower = float(control.points_m[0][1])
  control_height = float(control.points_m[-1][1] - control_lower)
  if request.inlet_boundary_mode is not (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE
  ) and request.inlet_boundary_mode is not (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
  ) and request.inlet_boundary_mode is not (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    return control_x, control_lower, control_height
  ####
  profile = request.transonic_shock_interface_profile
  if request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
  ):
    placement = request.transonic_shock_interface_field_placement
    profile = None if placement is None else placement.profile
  elif request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    condition = request.physical_field_shock_front_condition
    profile = None if condition is None else condition.coupled_inlet_profile
  ####
  if profile is None:
    raise ValueError('downstream profile mode requires a retained profile')
  ####
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(control_x), 1.0))
  if profile.cross_section_x_m <= control_x + x_tolerance:
    raise ValueError(
      'interior shock-interface profile must start strictly downstream of '
      'the upstream control section'
    )
  ####
  return (
    profile.cross_section_x_m,
    profile.lower_ordinate_m,
    profile.upper_ordinate_m - profile.lower_ordinate_m,
  )
####


def _free_boundary_pressure_targets(request: Any) -> np.ndarray:
  """Reconstruct the exact pressure target vector used by the field audit."""

  profile = request.free_boundary_pressure_profile_Pa
  if profile is None:
    return np.full(
      request.axial_cell_count,
      request.mixed_regime_request.ambient_pressure_Pa,
      dtype=float,
    )
  ####
  targets = np.asarray(profile, dtype=float)
  if targets.shape != (request.axial_cell_count,):
    raise ValueError(
      'free-boundary pressure target count does not match the audited mesh'
    )
  ####
  return targets
####


class MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus(str, Enum):
  """Outcome for the independent conservative-field audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged-local-coupled-euler-free-boundary-audit'
  )
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'coupled-euler-audit-geometry-failure'
  GEOMETRY_PROFILE_FAILURE = 'coupled-euler-audit-geometry-profile-failure'
  STATE_FAILURE = 'coupled-euler-audit-state-failure'
  THERMODYNAMIC_FAILURE = 'coupled-euler-audit-thermodynamic-failure'
  RESIDUAL_FAILURE = 'coupled-euler-audit-residual-failure'
  ENTROPY_FAILURE = 'coupled-euler-audit-entropy-failure'
  BOUNDARY_FAILURE = 'coupled-euler-audit-boundary-failure'
  PRESSURE_BUDGET_FAILURE = 'coupled-euler-audit-pressure-budget-failure'
  TRANSONIC_TRANSITION_FAILURE = 'coupled-euler-audit-transonic-transition-failure'
  TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE = (
    'coupled-euler-audit-transonic-frontier-compatibility-failure'
  )
  TRANSONIC_SHOCK_GEOMETRY_FAILURE = (
    'coupled-euler-audit-transonic-shock-geometry-failure'
  )
  TRANSONIC_SHOCK_INTERFACE_FAILURE = (
    'coupled-euler-audit-transonic-shock-interface-failure'
  )
  TRANSONIC_SHOCK_INTERFACE_PROFILE_FAILURE = (
    'coupled-euler-audit-transonic-shock-interface-profile-failure'
  )
  CONTROL_SECTION_COMPATIBILITY_FAILURE = (
    'coupled-euler-audit-control-section-compatibility-failure'
  )
  PHYSICAL_FIELD_CONTINUATION_FAILURE = (
    'coupled-euler-audit-physical-field-continuation-failure'
  )
  PHYSICAL_FIELD_INLET_SEAM_FAILURE = (
    'coupled-euler-audit-physical-field-inlet-seam-failure'
  )
  PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE = (
    'coupled-euler-audit-physical-field-shock-front-condition-failure'
  )
  INLET_CHARACTERISTIC_FAILURE = (
    'coupled-euler-audit-inlet-characteristic-failure'
  )
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
  maximum_entropy_production_fraction: float | None = None
  geometry_verified: bool = False
  state_samples_verified: bool = False
  thermodynamics_verified: bool = False
  residual_channels_recomputed: bool = False
  residual_report_verified: bool = False
  free_boundary_report_verified: bool = False
  free_boundary_geometry_profile_verified: bool = False
  pressure_budget_verified: bool = False
  transonic_transition_verified: bool = False
  transonic_frontier_compatibility_verified: bool = False
  transonic_shock_geometry_verified: bool = False
  transonic_shock_interface_verified: bool = False
  transonic_shock_interface_profile_verified: bool = False
  physical_field_continuation_profile_verified: bool = False
  physical_field_inlet_seam_verified: bool = False
  physical_field_shock_front_condition_verified: bool = False
  control_section_compatibility_verified: bool = False
  control_section_pressure_jump_Pa: float | None = None
  control_section_pressure_jump_fraction: float | None = None
  entropy_report_verified: bool = False
  entropy_production_map_verified: bool = False
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
      'control_section_pressure_jump_Pa',
      'control_section_pressure_jump_fraction',
      'maximum_entropy_transport_residual',
      'maximum_entropy_production_fraction',
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
      'free_boundary_geometry_profile_verified',
      'transonic_transition_verified',
      'transonic_frontier_compatibility_verified',
      'transonic_shock_geometry_verified',
      'transonic_shock_interface_verified',
      'transonic_shock_interface_profile_verified',
      'physical_field_continuation_profile_verified',
      'physical_field_inlet_seam_verified',
      'physical_field_shock_front_condition_verified',
      'control_section_compatibility_verified',
      'entropy_report_verified',
      'entropy_production_map_verified',
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
    profile_active = bool(
      self.candidate is not None
      and self.candidate.request is not None
      and self.candidate.request.transonic_shock_interface_profile is not None
    )
    return bool(
      self.converged
      and self.geometry_verified
      and self.state_samples_verified
      and self.thermodynamics_verified
      and self.residual_channels_recomputed
      and self.residual_report_verified
      and self.free_boundary_report_verified
      and (
        not (
          self.candidate is not None
          and self.candidate.request is not None
          and self.candidate.request.free_boundary_geometry_profile_y_m
          is not None
        )
        or self.free_boundary_geometry_profile_verified
      )
      and self.pressure_budget_verified
      and self.transonic_transition_verified
      and self.transonic_shock_geometry_verified
      and self.transonic_shock_interface_verified
      and (not profile_active or self.transonic_shock_interface_profile_verified)
      and (
        not (
          self.candidate is not None
          and self.candidate.request is not None
          and self.candidate.request.physical_field_continuation_profile
          is not None
        )
        or self.physical_field_continuation_profile_verified
      )
      and (
        not (
          self.candidate is not None
          and self.candidate.request is not None
          and self.candidate.request.physical_field_continuation_profile
          is not None
        )
        or self.physical_field_inlet_seam_verified
      )
      and (
        not (
          self.candidate is not None
          and self.candidate.request is not None
          and self.candidate.request.physical_field_shock_front_condition
          is not None
        )
        or self.physical_field_shock_front_condition_verified
      )
      and self.control_section_compatibility_verified
      and self.entropy_report_verified
      and self.entropy_production_map_verified
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
      'maximum_entropy_production_fraction': (
        self.maximum_entropy_production_fraction
      ),
      'geometry_verified': self.geometry_verified,
      'state_samples_verified': self.state_samples_verified,
      'thermodynamics_verified': self.thermodynamics_verified,
      'residual_channels_recomputed': self.residual_channels_recomputed,
      'residual_report_verified': self.residual_report_verified,
      'free_boundary_report_verified': self.free_boundary_report_verified,
      'free_boundary_geometry_profile_verified': (
        self.free_boundary_geometry_profile_verified
      ),
      'pressure_budget_verified': self.pressure_budget_verified,
      'transonic_transition_verified': self.transonic_transition_verified,
      'transonic_frontier_compatibility_verified': (
        self.transonic_frontier_compatibility_verified
      ),
      'transonic_shock_geometry_verified': self.transonic_shock_geometry_verified,
      'transonic_shock_interface_verified': self.transonic_shock_interface_verified,
      'transonic_shock_interface_profile_verified': (
        self.transonic_shock_interface_profile_verified
      ),
      'physical_field_continuation_profile_verified': (
        self.physical_field_continuation_profile_verified
      ),
      'physical_field_inlet_seam_verified': self.physical_field_inlet_seam_verified,
      'physical_field_shock_front_condition_verified': (
        self.physical_field_shock_front_condition_verified
      ),
      'control_section_compatibility_verified': (
        self.control_section_compatibility_verified
      ),
      'control_section_pressure_jump_Pa': self.control_section_pressure_jump_Pa,
      'control_section_pressure_jump_fraction': (
        self.control_section_pressure_jump_fraction
      ),
      'entropy_report_verified': self.entropy_report_verified,
      'entropy_production_map_verified': self.entropy_production_map_verified,
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
  *,
  pressure_budget_verified: bool = False,
  transonic_transition_verified: bool = False,
  transonic_frontier_compatibility_verified: bool = False,
  control_section_compatibility_verified: bool = False,
  promotion_flags_verified: bool = False,
) -> MocReflectedDomainCoupledEulerFreeBoundaryAudit:
  return MocReflectedDomainCoupledEulerFreeBoundaryAudit(
    status=status,
    candidate=candidate,
    solver_status=None if candidate is None else candidate.status.value,
    pressure_budget_verified=pressure_budget_verified,
    transonic_transition_verified=transonic_transition_verified,
    transonic_frontier_compatibility_verified=(
      transonic_frontier_compatibility_verified
    ),
    control_section_compatibility_verified=(
      control_section_compatibility_verified
    ),
    promotion_flags_verified=promotion_flags_verified,
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


def _subsonic_characteristic_inlet(
  interior_state: np.ndarray,
  reference_state: np.ndarray,
  gamma: float,
  gas_constant: float,
) -> np.ndarray:
  """Independently reconstruct the solver's subsonic inlet boundary state."""

  _density, interior_u, _velocity_v, _pressure, _temperature, interior_sound = (
    _primitive(interior_state, gamma, gas_constant)
  )
  _reference_density, reference_u, reference_v, reference_pressure, reference_temperature, reference_sound = (
    _primitive(reference_state, gamma, gas_constant)
  )
  reference_speed = sqrt(reference_u * reference_u + reference_v * reference_v)
  if reference_speed <= 1.0e-12:
    raise RuntimeError(
      'audited subsonic characteristic inlet requires a positive reference speed'
    )
  ####
  reference_mach = reference_speed / reference_sound
  if reference_mach >= 1.0:
    raise RuntimeError(
      'audited subsonic characteristic inlet requires a subsonic reference state'
    )
  ####
  beta = 0.5 * (gamma - 1.0)
  pressure_factor = 1.0 + beta * reference_mach * reference_mach
  total_temperature = reference_temperature * pressure_factor
  total_pressure = reference_pressure * pressure_factor ** (
    gamma / (gamma - 1.0)
  )
  direction_u = reference_u / reference_speed
  direction_v = reference_v / reference_speed
  outgoing_invariant = interior_u - 2.0 * interior_sound / (gamma - 1.0)

  def state_and_residual(mach: float) -> tuple[np.ndarray, float]:
    factor = 1.0 + beta * mach * mach
    temperature = total_temperature / factor
    sound_speed = sqrt(gamma * gas_constant * temperature)
    speed = mach * sound_speed
    velocity_u = speed * direction_u
    velocity_v = speed * direction_v
    pressure = total_pressure / factor ** (gamma / (gamma - 1.0))
    density = pressure / (gas_constant * temperature)
    state = np.array(
      (
        density,
        density * velocity_u,
        density * velocity_v,
        pressure / (gamma - 1.0) + 0.5 * density * speed * speed,
      ),
      dtype=float,
    )
    return state, velocity_u - 2.0 * sound_speed / (gamma - 1.0) - outgoing_invariant
  ####

  lower_mach = 1.0e-8
  upper_mach = 1.0 - 1.0e-8
  lower_state, lower_residual = state_and_residual(lower_mach)
  upper_state, upper_residual = state_and_residual(upper_mach)
  if abs(lower_residual) <= 1.0e-10:
    return lower_state
  ####
  if abs(upper_residual) <= 1.0e-10:
    return upper_state
  ####
  if lower_residual * upper_residual > 0.0:
    raise RuntimeError(
      'audited subsonic characteristic inlet has no admissible Mach root'
    )
  ####
  for _iteration in range(80):
    middle_mach = 0.5 * (lower_mach + upper_mach)
    middle_state, middle_residual = state_and_residual(middle_mach)
    if abs(middle_residual) <= 1.0e-10:
      return middle_state
    ####
    if lower_residual * middle_residual <= 0.0:
      upper_mach = middle_mach
      upper_residual = middle_residual
    else:
      lower_mach = middle_mach
      lower_residual = middle_residual
    ####
  ####
  return state_and_residual(0.5 * (lower_mach + upper_mach))[0]
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


def _audit_transonic_transition(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> bool:
  """Verify the retained scalar transition is bound to the control section."""

  request = candidate.request
  transition = candidate.transonic_transition
  transition_audit = candidate.transonic_transition_audit
  if request is None or not isinstance(transition, MocTransonicTransitionResult):
    return False
  ####
  if not isinstance(transition_audit, MocTransonicTransitionAudit):
    return False
  ####
  sample = request.mixed_regime_request.control_section.samples[-1]
  try:
    expected_request = MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=float(sample.total_pressure_Pa),
      target_downstream_static_pressure_Pa=(
        float(request.mixed_regime_request.ambient_pressure_Pa)
      ),
      gamma=float(sample.gamma),
      gas_constant_J_kgK=request.gas_constant_J_kgK,
      upstream_total_temperature_K=request.reference_total_temperature_K,
    )
  except (TypeError, ValueError):
    return False
  ####
  if transition.request != expected_request:
    return False
  ####
  expected_audit = measure_moc_transonic_transition(transition)

  def optional_close(reported: float | None, expected: float | None) -> bool:
    if reported is None or expected is None:
      return reported is None and expected is None
    ####
    return bool(np.isclose(reported, expected, rtol=3.0e-6, atol=1.0e-10))
  ####

  return bool(
    expected_audit.status is MocTransonicTransitionAuditStatus.VERIFIED
    and transition_audit.status is expected_audit.status
    and transition_audit.result_status is expected_audit.result_status
    and transition_audit.rederived == expected_audit.rederived
    and optional_close(
      transition_audit.pressure_residual_Pa,
      expected_audit.pressure_residual_Pa,
    )
    and optional_close(
      transition_audit.mach_residual,
      expected_audit.mach_residual,
    )
    and optional_close(
      transition_audit.total_pressure_residual,
      expected_audit.total_pressure_residual,
    )
    and transition_audit.shock_state_verified
    == expected_audit.shock_state_verified
    and optional_close(
      transition_audit.shock_state_mass_flux_residual,
      expected_audit.shock_state_mass_flux_residual,
    )
    and optional_close(
      transition_audit.shock_state_momentum_flux_residual,
      expected_audit.shock_state_momentum_flux_residual,
    )
    and optional_close(
      transition_audit.shock_state_energy_flux_residual,
      expected_audit.shock_state_energy_flux_residual,
    )
    and transition_audit.shock_state_conservation_verified
    == expected_audit.shock_state_conservation_verified
  )
####


def _audit_transonic_frontier_compatibility(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> bool:
  """Re-derive the scalar/global-frontier state comparison independently."""

  request = candidate.request
  transition = candidate.transonic_transition
  reported = candidate.transonic_frontier_compatibility
  if request is None or not isinstance(
    transition,
    MocTransonicTransitionResult,
  ) or not isinstance(
    reported,
    MocReflectedDomainCoupledEulerTransonicFrontierCompatibility,
  ):
    return False
  ####
  closure = request.mixed_regime_request.closure
  global_euler = closure.global_euler
  curve = None if global_euler is None else global_euler.shock_boundary
  if curve is None:
    return bool(
      reported.status
      is MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .FRONTIER_DATA_FAILURE
      and reported.frontier_sample_count == 0
      and reported.matching_sample_count == 0
      and reported.nearest_sample_index is None
    )
  ####
  points = tuple(curve.shock_points_m)
  states = tuple(curve.downstream_states)
  static_pressures = tuple(curve.downstream_static_pressure_Pa)
  total_pressures = tuple(curve.downstream_total_pressure_Pa)
  lengths = (len(points), len(states), len(static_pressures), len(total_pressures))
  if not lengths[0] or len(set(lengths)) != 1:
    return bool(
      reported.status
      is MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .FRONTIER_DATA_FAILURE
      and reported.frontier_sample_count == lengths[0]
      and reported.matching_sample_count == 0
      and reported.nearest_sample_index is None
    )
  ####
  frontier_machs = tuple(float(state.mach) for state in states)

  def close(reported_value: float | None, expected_value: float | None) -> bool:
    if reported_value is None or expected_value is None:
      return reported_value is None and expected_value is None
    ####
    return bool(np.isclose(reported_value, expected_value, rtol=3.0e-6, atol=1.0e-10))
  ####

  common = (
    reported.source == 'global-euler-shock-frontier-transonic-compatibility-v1'
    and np.isclose(reported.mach_tolerance, 1.0e-6, rtol=0.0, atol=1.0e-15)
    and np.isclose(
      reported.pressure_tolerance_fraction,
      1.0e-6,
      rtol=0.0,
      atol=1.0e-15,
    )
    and reported.frontier_sample_count == len(states)
    and close(reported.frontier_downstream_mach_min, min(frontier_machs))
    and close(reported.frontier_downstream_mach_max, max(frontier_machs))
    and reported.transition_required == transition.transition_required
    and reported.required_upstream_mach == transition.required_upstream_mach
    and reported.required_upstream_static_pressure_Pa
    == transition.upstream_static_pressure_Pa
    and close(
      reported.required_upstream_total_pressure_Pa,
      transition.request.upstream_total_pressure_Pa
      if transition.transition_required
      else None,
    )
  )
  if not common:
    return False
  ####
  if not transition.transition_required:
    return bool(
      reported.status
      is MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .NOT_REQUIRED
      and reported.matching_sample_count == 0
      and reported.nearest_sample_index is None
      and reported.nearest_sample_point_m is None
      and reported.nearest_mach_residual is None
      and reported.nearest_static_pressure_residual_fraction is None
      and reported.nearest_total_pressure_residual_fraction is None
    )
  ####
  required_mach = transition.required_upstream_mach
  required_static_pressure = transition.upstream_static_pressure_Pa
  required_total_pressure = transition.request.upstream_total_pressure_Pa
  if required_mach is None or required_static_pressure is None:
    return reported.status is (
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .FRONTIER_DATA_FAILURE
    )
  ####
  candidates: list[tuple[float, int, float, float, float]] = []
  for index, (state, static_pressure, total_pressure) in enumerate(zip(
    states,
    static_pressures,
    total_pressures,
    strict=True,
  )):
    mach_residual = abs(float(state.mach) - required_mach)
    static_residual = abs(float(static_pressure) - required_static_pressure) / max(
      abs(required_static_pressure),
      abs(float(static_pressure)),
      1.0,
    )
    total_residual = abs(float(total_pressure) - required_total_pressure) / max(
      abs(required_total_pressure),
      abs(float(total_pressure)),
      1.0,
    )
    score = max(
      mach_residual / reported.mach_tolerance,
      static_residual / reported.pressure_tolerance_fraction,
      total_residual / reported.pressure_tolerance_fraction,
    )
    candidates.append((score, index, mach_residual, static_residual, total_residual))
  ####
  _score, nearest_index, mach_residual, static_residual, total_residual = min(
    candidates,
    key=lambda candidate_value: candidate_value[0],
  )
  matching = tuple(
    candidate_value
    for candidate_value in candidates
    if candidate_value[2] <= reported.mach_tolerance
    and candidate_value[3] <= reported.pressure_tolerance_fraction
    and candidate_value[4] <= reported.pressure_tolerance_fraction
  )
  expected_status = (
    MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
    .MATCHED_FRONTIER_STATE
    if matching
    else MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
    .REQUIRED_UPSTREAM_NOT_RETAINED
  )
  return bool(
    reported.status is expected_status
    and reported.matching_sample_count == len(matching)
    and reported.nearest_sample_index == nearest_index
    and reported.nearest_sample_point_m == tuple(
      float(value) for value in points[nearest_index]
    )
    and close(reported.nearest_mach_residual, mach_residual)
    and close(reported.nearest_static_pressure_residual_fraction, static_residual)
    and close(reported.nearest_total_pressure_residual_fraction, total_residual)
  )
####


def _audit_transonic_shock_geometry(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> tuple[bool, tuple[np.ndarray, ...] | None]:
  """Re-derive the optional post-shock inlet branch and its geometry binding."""

  request = candidate.request
  if request is None:
    return False, None
  ####
  geometry_request = request.transonic_shock_geometry
  if geometry_request is None:
    return (
      candidate.transonic_shock_geometry is None
      and candidate.transonic_shock_geometry_audit is None,
      None,
    )
  ####
  reported = candidate.transonic_shock_geometry
  reported_audit = candidate.transonic_shock_geometry_audit
  if not isinstance(reported, MocTransonicShockGeometryResult):
    return False, None
  ####
  if not isinstance(reported_audit, MocTransonicShockGeometryAudit):
    return False, None
  ####
  if not isinstance(geometry_request, MocTransonicShockGeometryRequest):
    return False, None
  ####
  expected = solve_moc_transonic_shock_geometry(geometry_request)
  expected_audit = measure_moc_transonic_shock_geometry(expected)
  geometry_fields_match = bool(
    reported.status is expected.status
    and reported.request == expected.request
    and reported.shock_point_m == expected.shock_point_m
    and np.isclose(
      reported.shock_normal_angle_rad,
      expected.shock_normal_angle_rad,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.shock_tangent_angle_rad,
      expected.shock_tangent_angle_rad,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.normal_alignment_residual_rad,
      expected.normal_alignment_residual_rad,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.allclose(
      (
        reported.upstream_normal_velocity_m_s,
        reported.downstream_normal_velocity_m_s,
        reported.upstream_tangential_velocity_m_s,
        reported.downstream_tangential_velocity_m_s,
        reported.mass_flux_residual,
        reported.momentum_flux_residual,
        reported.energy_flux_residual,
      ),
      (
        expected.upstream_normal_velocity_m_s,
        expected.downstream_normal_velocity_m_s,
        expected.upstream_tangential_velocity_m_s,
        expected.downstream_tangential_velocity_m_s,
        expected.mass_flux_residual,
        expected.momentum_flux_residual,
        expected.energy_flux_residual,
      ),
      rtol=3.0e-6,
      atol=1.0e-10,
    )
  )
  audit_fields_match = bool(
    reported_audit.status is expected_audit.status
    and reported_audit.result_status is expected_audit.result_status
    and reported_audit.rederived == expected_audit.rederived
    and reported_audit.geometry_binding_verified
    == expected_audit.geometry_binding_verified
    and np.allclose(
      (
        reported_audit.point_residual_m,
        reported_audit.normal_angle_residual_rad,
        reported_audit.tangent_angle_residual_rad,
        reported_audit.mass_flux_residual,
        reported_audit.momentum_flux_residual,
        reported_audit.energy_flux_residual,
      ),
      (
        expected_audit.point_residual_m,
        expected_audit.normal_angle_residual_rad,
        expected_audit.tangent_angle_residual_rad,
        expected_audit.mass_flux_residual,
        expected_audit.momentum_flux_residual,
        expected_audit.energy_flux_residual,
      ),
      rtol=3.0e-6,
      atol=1.0e-10,
    )
  )
  if not geometry_fields_match or not audit_fields_match:
    return False, None
  ####
  state = geometry_request.shock_state
  sample = request.mixed_regime_request.control_section.samples[-1]
  pressure_scale = max(
    request.mixed_regime_request.ambient_pressure_Pa,
    state.downstream_static_pressure_Pa,
    1.0,
  )
  x_start = request.mixed_regime_request.control_section.points_m[0][0]
  lower_ordinate = request.mixed_regime_request.control_section.points_m[0][1]
  inlet_height = request.mixed_regime_request.control_section.points_m[-1][1] - lower_ordinate
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(reported.shock_point_m[0] - x_start) > x_tolerance:
    return False, None
  ####
  if not (
    lower_ordinate - y_tolerance
    <= reported.shock_point_m[1]
    <= lower_ordinate + inlet_height + y_tolerance
  ):
    return False, None
  ####
  if abs(
    state.downstream_static_pressure_Pa
    - request.mixed_regime_request.ambient_pressure_Pa
  ) > 1.0e-8 * pressure_scale:
    return False, None
  ####
  if abs(state.gamma - float(sample.gamma)) > 1.0e-10:
    return False, None
  ####
  if abs(state.gas_constant_J_kgK - request.gas_constant_J_kgK) > 1.0e-10:
    return False, None
  ####
  if abs(
    state.upstream_total_temperature_K - request.reference_total_temperature_K
  ) > 1.0e-8 * max(request.reference_total_temperature_K, 1.0):
    return False, None
  ####
  downstream_state = np.array(
    (
      state.downstream_density_kg_m3,
      state.downstream_density_kg_m3
      * state.downstream_speed_m_s
      * np.cos(state.upstream_flow_angle_rad),
      state.downstream_density_kg_m3
      * state.downstream_speed_m_s
      * np.sin(state.upstream_flow_angle_rad),
      state.downstream_static_pressure_Pa / (state.gamma - 1.0)
      + 0.5
      * state.downstream_density_kg_m3
      * state.downstream_speed_m_s**2,
    ),
    dtype=float,
  )
  return (
    True,
    tuple(downstream_state.copy() for _ in range(request.transverse_cell_count)),
  )
####


def _audit_transonic_shock_interface(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> tuple[bool, tuple[np.ndarray, ...] | None]:
  """Re-derive the audited interface inlet handoff without trusting fields."""

  request = candidate.request
  if request is None:
    return False, None
  ####
  expected = request.transonic_shock_interface
  if expected is None:
    return candidate.transonic_shock_interface is None and not (
      candidate.transonic_shock_interface_consumed
    ), None
  ####
  reported = candidate.transonic_shock_interface
  if not isinstance(reported, MocTransonicShockInterfaceResult):
    return False, None
  ####
  try:
    interface_audit = measure_moc_transonic_shock_interface(reported)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return False, None
  ####
  if not interface_audit.converged:
    return False, None
  ####
  if reported != expected:
    return False, None
  ####
  if (
    reported.status is not MocTransonicShockInterfaceStatus.CONVERGED_BOUNDED_INTERFACE
    or not reported.interface_verified
    or not candidate.transonic_shock_interface_consumed
  ):
    return False, None
  ####
  sample = reported.downstream_sample
  geometry = reported.shock_geometry
  if sample is None or geometry is None:
    return False, None
  ####
  control = request.mixed_regime_request.control_section
  x_start, lower_ordinate, inlet_height = _effective_field_inlet_geometry(
    request
  )
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(sample.point_m[0] - x_start) > x_tolerance:
    return False, None
  ####
  if not (
    lower_ordinate - y_tolerance
    <= sample.point_m[1]
    <= lower_ordinate + inlet_height + y_tolerance
  ):
    return False, None
  ####
  reference_sample = control.samples[-1]
  shock_state = geometry.request.shock_state
  if (
    abs(sample.gamma - float(reference_sample.gamma)) > 1.0e-10
    or abs(shock_state.gas_constant_J_kgK - request.gas_constant_J_kgK) > 1.0e-10
    or abs(
      shock_state.upstream_total_temperature_K
      - request.reference_total_temperature_K
    )
    > 1.0e-8 * max(request.reference_total_temperature_K, 1.0)
  ):
    return False, None
  ####
  state = _from_sample(
    sample.total_pressure_Pa,
    sample.mach,
    sample.flow_angle_rad,
    sample.gamma,
    request.reference_total_temperature_K,
    request.gas_constant_J_kgK,
  )
  density, velocity_u, velocity_v, pressure, _temperature, sound_speed = _primitive(
    state,
    float(reference_sample.gamma),
    request.gas_constant_J_kgK,
  )
  reconstructed_mach = float(
    np.hypot(velocity_u, velocity_v) / max(sound_speed, 1.0e-12)
  )
  pressure_scale = max(sample.static_pressure_Pa, pressure, 1.0)
  if (
    abs(pressure - sample.static_pressure_Pa) / pressure_scale > 1.0e-8
    or abs(reconstructed_mach - sample.mach) > 1.0e-8
    or density <= 0.0
  ):
    return False, None
  ####
  return (
    True,
    tuple(state.copy() for _ in range(request.transverse_cell_count)),
  )
####


def _audit_transonic_shock_interface_profile(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> tuple[bool, tuple[np.ndarray, ...] | None]:
  """Re-derive a spatially varying profile inlet without trusting fields."""

  request = candidate.request
  if request is None:
    return False, None
  ####
  expected = request.transonic_shock_interface_profile
  if expected is None:
    return candidate.transonic_shock_interface_profile is None and not (
      candidate.transonic_shock_interface_profile_consumed
    ), None
  ####
  reported = candidate.transonic_shock_interface_profile
  if not isinstance(reported, MocTransonicShockInterfaceProfile):
    return False, None
  ####
  try:
    profile_audit = measure_moc_transonic_shock_interface_profile(reported)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return False, None
  ####
  if not profile_audit.converged or reported != expected:
    return False, None
  ####
  if not candidate.transonic_shock_interface_profile_consumed:
    return False, None
  ####
  control = request.mixed_regime_request.control_section
  x_start, lower_ordinate, inlet_height = _effective_field_inlet_geometry(
    request
  )
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(reported.cross_section_x_m - x_start) > x_tolerance:
    return False, None
  ####
  if (
    abs(reported.lower_ordinate_m - lower_ordinate) > y_tolerance
    or abs(reported.upper_ordinate_m - (lower_ordinate + inlet_height))
    > y_tolerance
    or abs(np.sin(reported.interface_normal_angle_rad)) > 1.0e-8
  ):
    return False, None
  ####
  reference_sample = control.samples[-1]
  if abs(reported.gamma - float(reference_sample.gamma)) > 1.0e-10:
    return False, None
  ####
  ordinates = np.asarray(
    [sample.point_m[1] for sample in reported.downstream_samples],
    dtype=float,
  )
  values = {
    name: np.asarray(
      [getattr(sample, name) for sample in reported.downstream_samples],
      dtype=float,
    )
    for name in ('total_pressure_Pa', 'mach', 'flow_angle_rad')
  }
  face_width = inlet_height / request.transverse_cell_count
  override_states: list[np.ndarray] = []
  for index in range(request.transverse_cell_count):
    ordinate = lower_ordinate + (index + 0.5) * face_width
    override_states.append(
      _from_sample(
        float(np.interp(ordinate, ordinates, values['total_pressure_Pa'])),
        float(np.interp(ordinate, ordinates, values['mach'])),
        float(np.interp(ordinate, ordinates, values['flow_angle_rad'])),
        reported.gamma,
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
    )
  ####
  return True, tuple(state.copy() for state in override_states)
####


def _from_continuation_sample(
  total_pressure: float,
  mach: float,
  flow_angle: float,
  gamma: float,
  total_temperature: float,
  gas_constant: float,
) -> np.ndarray:
  pressure_factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_temperature = total_temperature / pressure_factor
  static_pressure = total_pressure / pressure_factor ** (
    gamma / (gamma - 1.0)
  )
  density = static_pressure / (gas_constant * static_temperature)
  sound_speed = sqrt(gamma * gas_constant * static_temperature)
  speed = mach * sound_speed
  return np.array(
    (
      density,
      density * speed * np.cos(flow_angle),
      density * speed * np.sin(flow_angle),
      static_pressure / (gamma - 1.0) + 0.5 * density * speed * speed,
    ),
    dtype=float,
  )
####


def _audit_physical_field_continuation(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> tuple[bool, tuple[np.ndarray, ...] | None]:
  """Re-sample the exact physical-field continuation handoff independently."""

  request = candidate.request
  if request is None:
    return False, None
  ####
  expected = request.physical_field_continuation_profile
  if expected is None:
    return (
      candidate.physical_field_continuation_profile is None
      and not candidate.physical_field_continuation_profile_consumed,
      None,
    )
  ####
  reported = candidate.physical_field_continuation_profile
  if not isinstance(reported, MocPhysicalFieldContinuationProfileResult):
    return False, None
  ####
  try:
    audit = measure_moc_physical_field_continuation_profile(reported)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return False, None
  ####
  if not audit.converged or reported != expected:
    return False, None
  ####
  if not candidate.physical_field_continuation_profile_consumed:
    return False, None
  ####
  profile = reported.profile
  if not isinstance(profile, MocPhysicalFieldContinuationProfile):
    return False, None
  ####
  coupled_profile = profile
  if request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    condition = request.physical_field_shock_front_condition
    coupled_profile = None if condition is None else condition.coupled_inlet_profile
    if not isinstance(coupled_profile, MocPhysicalFieldContinuationProfile):
      return False, None
    ####
  ####
  control = request.mixed_regime_request.control_section
  x_start, lower_ordinate, inlet_height = _effective_field_inlet_geometry(
    request
  )
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(coupled_profile.cross_section_x_m - x_start) > x_tolerance:
    return False, None
  ####
  if (
    abs(coupled_profile.lower_ordinate_m - lower_ordinate) > y_tolerance
    or abs(coupled_profile.upper_ordinate_m - (lower_ordinate + inlet_height))
    > y_tolerance
  ):
    return False, None
  ####
  reference_sample = control.samples[-1]
  if abs(coupled_profile.gamma - float(reference_sample.gamma)) > 1.0e-10:
    return False, None
  ####
  ordinates = np.asarray(
    [sample.point_m[1] for sample in coupled_profile.samples],
    dtype=float,
  )
  fields = {
    name: np.asarray(
      [getattr(sample, name) for sample in coupled_profile.samples],
      dtype=float,
    )
    for name in ('total_pressure_Pa', 'mach', 'flow_angle_rad')
  }
  face_width = inlet_height / request.transverse_cell_count
  override_states = tuple(
    _from_continuation_sample(
      float(
        np.interp(
          lower_ordinate + (index + 0.5) * face_width,
          ordinates,
          fields['total_pressure_Pa'],
        )
      ),
      float(
        np.interp(
          lower_ordinate + (index + 0.5) * face_width,
          ordinates,
          fields['mach'],
        )
      ),
      float(
        np.interp(
          lower_ordinate + (index + 0.5) * face_width,
          ordinates,
          fields['flow_angle_rad'],
        )
      ),
      coupled_profile.gamma,
      request.reference_total_temperature_K,
      request.gas_constant_J_kgK,
    )
    for index in range(request.transverse_cell_count)
  )
  return True, tuple(state.copy() for state in override_states)
####


def _audit_physical_field_shock_front_condition(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> bool:
  """Re-audit the exact front and neighboring paths consumed by continuation."""

  request = candidate.request
  if request is None:
    return False
  ####
  expected = request.physical_field_shock_front_condition
  if expected is None:
    return (
      candidate.physical_field_shock_front_condition is None
      and not candidate.physical_field_shock_front_condition_consumed
    )
  ####
  reported = candidate.physical_field_shock_front_condition
  if not isinstance(reported, MocPhysicalFieldShockFrontConditionResult):
    return False
  ####
  try:
    audit = measure_moc_physical_field_shock_front_condition(reported)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return False
  ####
  return bool(
    reported == expected
    and reported.continuation_profile
    == request.physical_field_continuation_profile
    and reported.converged
    and audit.converged
    and candidate.physical_field_shock_front_condition_consumed
  )
####


def _audit_control_section_compatibility(
  candidate: MocReflectedDomainCoupledEulerFreeBoundaryResult,
) -> tuple[bool, float | None, float | None]:
  """Recompute the control-section/free-boundary inlet seam independently."""

  request = candidate.request
  reported = candidate.control_section_compatibility
  transition = candidate.transonic_transition
  if request is None or not isinstance(
    reported,
    MocReflectedDomainCoupledEulerControlSectionCompatibility,
  ):
    return False, None, None
  ####
  if transition is None:
    return False, None, None
  ####
  sample = request.mixed_regime_request.control_section.samples[-1]
  target_pressure = float(request.mixed_regime_request.ambient_pressure_Pa)
  control_pressure = float(sample.static_pressure_Pa)
  control_total_pressure = float(sample.total_pressure_Pa)
  control_mach = float(sample.mach)
  if any(
    not isfinite(value) or value <= 0.0
    for value in (
      target_pressure,
      control_pressure,
      control_total_pressure,
      control_mach,
    )
  ):
    return False, None, None
  ####
  target_minus_control = target_pressure - control_pressure
  pressure_jump = abs(target_minus_control)
  pressure_scale = max(target_pressure, control_pressure, 1.0)
  pressure_jump_fraction = pressure_jump / pressure_scale
  tolerance = 1.0e-10 * pressure_scale
  if pressure_jump <= tolerance:
    expected_status = 'control-section-inlet-pressure-matched'
  elif target_minus_control < 0.0:
    expected_status = 'target-below-control-section-pressure'
  else:
    expected_status = 'target-above-control-section-pressure'
  ####
  control_section_is_subsonic = control_mach < 1.0 - 1.0e-10
  transition_requires_supersonic_upstream = bool(
    transition.transition_required
    and control_section_is_subsonic
    and transition.required_upstream_mach is not None
    and transition.required_upstream_mach > 1.0 + 1.0e-10
  )
  values_verified = bool(
    reported.status.value == expected_status
    and reported.scalar_transition_status.value == transition.status.value
    and reported.scalar_transition_required == transition.transition_required
    and reported.control_section_is_subsonic == control_section_is_subsonic
    and reported.transition_requires_supersonic_upstream
    == transition_requires_supersonic_upstream
    and np.isclose(
      reported.target_ambient_pressure_Pa,
      target_pressure,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.control_section_outer_static_pressure_Pa,
      control_pressure,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.control_section_outer_total_pressure_Pa,
      control_total_pressure,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.control_section_outer_mach,
      control_mach,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.target_minus_control_section_pressure_Pa,
      target_minus_control,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.absolute_pressure_jump_Pa,
      pressure_jump,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and np.isclose(
      reported.absolute_pressure_jump_fraction,
      pressure_jump_fraction,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
  )
  return values_verified, pressure_jump, pressure_jump_fraction
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
  pressure_targets = _free_boundary_pressure_targets(request)
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
  x_start, lower_ordinate, _inlet_height = _effective_field_inlet_geometry(
    request
  )
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  if abs(float(candidate.x_stations_m[0]) - x_start) > x_tolerance:
    raise ValueError('audited x stations do not start at the effective inlet')
  ####
  heights = np.asarray(
    [point[1] - lower_ordinate for point in candidate.free_boundary_points_m],
    dtype=float,
  )
  if np.any(~np.isfinite(heights)) or np.any(heights <= 0.0):
    raise ValueError('audited free-boundary heights must be positive')
  ####
  geometry_profile_verified = True
  if request.free_boundary_geometry_profile_y_m is not None:
    profile_x = np.asarray(
      request.free_boundary_geometry_profile_x_stations_m,
      dtype=float,
    )
    profile_y = np.asarray(
      request.free_boundary_geometry_profile_y_m,
      dtype=float,
    )
    candidate_x = np.asarray(candidate.x_stations_m, dtype=float)
    candidate_y = np.asarray(
      [point[1] for point in candidate.free_boundary_points_m],
      dtype=float,
    )
    geometry_profile_verified = bool(
      candidate.free_boundary_geometry_profile_consumed
      and request.free_boundary_geometry_profile_lower_ordinate_m is not None
      and np.isclose(
        request.free_boundary_geometry_profile_lower_ordinate_m,
        lower_ordinate,
        rtol=3.0e-6,
        atol=1.0e-10,
      )
      and profile_x.shape == candidate_x.shape
      and profile_y.shape == candidate_y.shape
      and np.allclose(
        candidate_x,
        profile_x,
        rtol=3.0e-6,
        atol=1.0e-10,
      )
      and np.allclose(
        candidate_y,
        profile_y,
        rtol=3.0e-6,
        atol=1.0e-10,
      )
    )
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
  transonic_shock_geometry_verified, geometry_override_states = (
    _audit_transonic_shock_geometry(candidate)
  )
  if not transonic_shock_geometry_verified:
    raise ValueError(
      'audited transonic shock geometry does not match its independent '
      'branch re-derivation'
    )
  ####
  transonic_frontier_compatibility_verified = (
    _audit_transonic_frontier_compatibility(candidate)
  )
  if not transonic_frontier_compatibility_verified:
    raise ValueError(
      'audited scalar/global-frontier transonic compatibility does not match '
      'its independent re-derivation'
    )
  ####
  transonic_shock_interface_verified, interface_override_states = (
    _audit_transonic_shock_interface(candidate)
  )
  if not transonic_shock_interface_verified:
    raise ValueError(
      'audited transonic shock interface does not match its independent '
      'handoff re-derivation'
    )
  ####
  transonic_shock_interface_profile_verified, interface_profile_override_states = (
    _audit_transonic_shock_interface_profile(candidate)
  )
  if not transonic_shock_interface_profile_verified:
    raise ValueError(
      'audited transonic shock-interface profile does not match its '
      'independent handoff re-derivation'
    )
  ####
  physical_field_continuation_profile_verified, continuation_override_states = (
    _audit_physical_field_continuation(candidate)
  )
  if not physical_field_continuation_profile_verified:
    raise ValueError(
      'audited physical-field continuation profile does not match its '
      'independent field re-sampling'
    )
  ####
  physical_field_shock_front_condition_verified = (
    _audit_physical_field_shock_front_condition(candidate)
  )
  if not physical_field_shock_front_condition_verified:
    raise ValueError(
      'audited physical-field shock-front condition does not match its '
      'independent front and neighboring-boundary remeasurement'
    )
  ####
  if sum(
    override is not None
    for override in (
      geometry_override_states,
      interface_override_states,
      interface_profile_override_states,
      continuation_override_states,
    )
  ) > 1:
    raise ValueError(
      'audited geometry, shock-interface, shock-interface-profile, and '
      'physical-field-continuation inlet branches cannot be active together'
    )
  ####
  inlet_override_states = (
    continuation_override_states
    if continuation_override_states is not None
    else interface_profile_override_states
    if interface_profile_override_states is not None
    else interface_override_states
    if interface_override_states is not None
    else geometry_override_states
  )
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
  if inlet_override_states is not None:
    inlet_entropy_states = inlet_override_states
  else:
    inlet_entropy_states = tuple(
      _interpolate_inlet(
        0.5 * (first[1] + second[1]),
        control.points_m,
        control.samples,
        gamma,
        request.reference_total_temperature_K,
        gas_constant,
      )
      for first, second in zip(control.points_m, control.points_m[1:])
    )
  ####
  for state in inlet_entropy_states:
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
            float(pressure_targets[i]),
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
          if inlet_override_states is not None:
            inlet = inlet_override_states[j]
          else:
            inlet = _interpolate_inlet(
              0.5 * (first[1] + second[1]),
              control.points_m,
              control.samples,
              gamma,
              request.reference_total_temperature_K,
              gas_constant,
            )
            if (
              request.inlet_boundary_mode
              is MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
            ):
              inlet = _subsonic_characteristic_inlet(
                state,
                inlet,
                gamma,
                gas_constant,
              )
            ####
          ####
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
  entropy_loss_residual = 0.0
  entropy_production_fraction = 0.0
  for value in entropy_values:
    if value < entropy_minimum:
      entropy_loss_residual = max(
        entropy_loss_residual,
        (entropy_minimum - value) / max(entropy_maximum, 1.0e-12),
      )
    ####
    if value > entropy_maximum:
      entropy_production_fraction = max(
        entropy_production_fraction,
        (value - entropy_maximum) / max(entropy_maximum, 1.0e-12),
      )
    ####
  ####
  entropy_production_fractions = tuple(
    max(
      0.0,
      (value - entropy_maximum) / max(entropy_maximum, 1.0e-12),
    )
    for value in entropy_values
  )
  # The candidate arrays are checked outside this helper; this return keeps the
  # independent flux reconstruction separate from report reconciliation.
  return {
    'geometry_verified': retained_vertices_verified,
    'free_boundary_geometry_profile_verified': geometry_profile_verified,
    'state_samples_verified': True,
    'thermodynamics_verified': thermodynamic_inputs_verified,
    'recomputed_channels': recomputed_channels,
    'reported_channels': original_reported_channels,
    'top_pressure': top_pressure,
    'top_normal_velocity': top_normal_velocity,
    'speeds': np.asarray(speeds, dtype=float),
    'entropy_residual': entropy_loss_residual,
    'entropy_production_fraction': entropy_production_fraction,
    'entropy_production_fractions': entropy_production_fractions,
    'entropy_verified': entropy_loss_residual <= 0.05,
    'pressure_budget': pressure_budget,
    'expected_cell_count': expected_cell_count,
    'transonic_shock_geometry_verified': transonic_shock_geometry_verified,
    'transonic_frontier_compatibility_verified': (
      transonic_frontier_compatibility_verified
    ),
    'transonic_shock_interface_verified': transonic_shock_interface_verified,
    'transonic_shock_interface_profile_verified': (
      transonic_shock_interface_profile_verified
    ),
    'physical_field_continuation_profile_verified': (
      physical_field_continuation_profile_verified
    ),
    'physical_field_continuation_inlet_states': continuation_override_states,
    'physical_field_shock_front_condition_verified': (
      physical_field_shock_front_condition_verified
    ),
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
  if candidate.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_FAILURE
  ):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_SHOCK_INTERFACE_FAILURE,
      candidate,
      candidate.message,
    )
  ####
  if candidate.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_SHOCK_INTERFACE_PROFILE_FAILURE
  ):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_SHOCK_INTERFACE_PROFILE_FAILURE,
      candidate,
      candidate.message,
    )
  ####
  if candidate.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_PHYSICAL_FIELD_CONTINUATION_FAILURE
  ):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .PHYSICAL_FIELD_CONTINUATION_FAILURE,
      candidate,
      candidate.message,
    )
  ####
  if candidate.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE
  ):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE,
      candidate,
      candidate.message,
    )
  ####
  if candidate.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus.TRANSONIC_FRONTIER_FAILURE
  ):
    if not _audit_transonic_frontier_compatibility(candidate):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
        .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE,
        candidate,
        'typed transonic-frontier stop did not retain independently '
        'reproducible frontier compatibility evidence',
      )
    ####
    transition_verified = _audit_transonic_transition(candidate)
    control_verified, _pressure_jump, _pressure_jump_fraction = (
      _audit_control_section_compatibility(candidate)
    )
    try:
      expected_budget = _rederive_subsonic_pressure_budget(candidate)
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
    except (ArithmeticError, TypeError, ValueError):
      pressure_budget_verified = False
    ####
    promotion_flags_verified = bool(
      candidate.chain_promotion_blocked
      and not candidate.production_claim_allowed
      and not candidate.canonical_euler_verified
      and not candidate.canonical_free_boundary_verified
      and not candidate.external_validation_verified
    )
    if not (
      transition_verified
      and control_verified
      and pressure_budget_verified
      and promotion_flags_verified
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
        .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE,
        candidate,
        'typed transonic-frontier stop did not retain independently '
        'reproducible transition, pressure-budget, control-seam, or '
        'promotion evidence',
      )
    ####
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE,
      candidate,
      candidate.message,
      pressure_budget_verified=True,
      transonic_transition_verified=True,
      transonic_frontier_compatibility_verified=True,
      control_section_compatibility_verified=True,
      promotion_flags_verified=True,
    )
  ####
  if not _audit_transonic_frontier_compatibility(candidate):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE,
      candidate,
      'candidate scalar/global-frontier transonic compatibility evidence does '
      'not match the retained global shock frontier',
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
  except RuntimeError as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.INLET_CHARACTERISTIC_FAILURE,
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
  transonic_transition_verified = _audit_transonic_transition(candidate)
  transonic_frontier_compatibility_verified = bool(
    raw['transonic_frontier_compatibility_verified']
  )
  transonic_shock_geometry_verified = bool(
    raw['transonic_shock_geometry_verified']
  )
  transonic_shock_interface_verified = bool(
    raw['transonic_shock_interface_verified']
  )
  transonic_shock_interface_profile_verified = bool(
    raw['transonic_shock_interface_profile_verified']
  )
  physical_field_continuation_profile_verified = bool(
    raw['physical_field_continuation_profile_verified']
  )
  physical_field_inlet_seam_verified = True
  if candidate.request.physical_field_continuation_profile is not None:
    expected_inlet = raw['physical_field_continuation_inlet_states']
    reported_inlet = np.asarray(
      candidate.inlet_boundary_conservative_states_by_face,
      dtype=float,
    )
    expected_inlet_array = np.asarray(
      () if expected_inlet is None else expected_inlet,
      dtype=float,
    )
    physical_field_inlet_seam_verified = bool(
      candidate.inlet_boundary_states_consumed
      and expected_inlet is not None
      and reported_inlet.shape == expected_inlet_array.shape
      and np.allclose(
        reported_inlet,
        expected_inlet_array,
        rtol=3.0e-6,
        atol=1.0e-10,
      )
    )
  ####
  physical_field_shock_front_condition_verified = bool(
    raw['physical_field_shock_front_condition_verified']
  )
  free_boundary_geometry_profile_verified = bool(
    raw['free_boundary_geometry_profile_verified']
  )
  (
    control_section_compatibility_verified,
    control_section_pressure_jump,
    control_section_pressure_jump_fraction,
  ) = _audit_control_section_compatibility(candidate)
  entropy_report_verified = bool(
    candidate.maximum_entropy_transport_residual is not None
    and np.isclose(
      candidate.maximum_entropy_transport_residual,
      raw['entropy_residual'],
      rtol=3.0e-6,
      atol=1.0e-10,
    )
    and candidate.maximum_entropy_production_fraction is not None
    and np.isclose(
      candidate.maximum_entropy_production_fraction,
      raw['entropy_production_fraction'],
      rtol=3.0e-6,
      atol=1.0e-10,
    )
  )
  expected_entropy_production_map = np.asarray(
    raw['entropy_production_fractions'],
    dtype=float,
  )
  reported_entropy_production_map = np.asarray(
    candidate.entropy_production_fraction_by_cell,
    dtype=float,
  )
  entropy_production_map_verified = bool(
    reported_entropy_production_map.shape
    == expected_entropy_production_map.shape
    and np.allclose(
      reported_entropy_production_map,
      expected_entropy_production_map,
      rtol=3.0e-6,
      atol=1.0e-10,
    )
  )
  maxima = tuple(float(np.max(recomputed[..., index])) for index in range(_CHANNEL_COUNT))
  residuals_verified = maxima[4] <= candidate.request.euler_residual_tolerance
  pressure = np.asarray(raw['top_pressure'], dtype=float)
  normal_velocity = np.asarray(raw['top_normal_velocity'], dtype=float)
  pressure_targets = _free_boundary_pressure_targets(candidate.request)
  pressure_residual = float(np.max(np.abs(pressure - pressure_targets)))
  maximum_speed = max(float(np.max(raw['speeds'])), 1.0e-12)
  normal_fraction = float(np.max(np.abs(normal_velocity))) / maximum_speed
  boundary_report_verified = bool(
    np.allclose(
      np.asarray(candidate.free_boundary_pressure_residuals_Pa),
      np.abs(pressure - pressure_targets),
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
  elif not free_boundary_geometry_profile_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .GEOMETRY_PROFILE_FAILURE
    )
    message = (
      'candidate retained free-boundary nodes do not reproduce the exact '
      'solver-owned geometry profile handoff'
    )
  elif not physical_field_inlet_seam_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .PHYSICAL_FIELD_INLET_SEAM_FAILURE
    )
    message = (
      'candidate consumed inlet conservative faces do not reproduce the '
      'independently rederived physical-field continuation handoff'
    )
  elif not report_verified or not residuals_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.RESIDUAL_FAILURE
    message = 'independent conservative residuals disagree or exceed tolerance'
  elif not pressure_budget_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.PRESSURE_BUDGET_FAILURE
    message = 'candidate subsonic pressure-budget diagnostic does not match the request'
  elif not transonic_transition_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.TRANSONIC_TRANSITION_FAILURE
    message = 'candidate scalar transonic transition evidence does not match the control section'
  elif not transonic_frontier_compatibility_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_FRONTIER_COMPATIBILITY_FAILURE
    )
    message = (
      'candidate scalar/global-frontier transonic compatibility evidence does '
      'not match the retained global shock frontier'
    )
  elif not transonic_shock_geometry_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_SHOCK_GEOMETRY_FAILURE
    )
    message = (
      'candidate scalar transonic shock geometry does not match its '
      'independent branch re-derivation'
    )
  elif not transonic_shock_interface_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_SHOCK_INTERFACE_FAILURE
    )
    message = (
      'candidate audited transonic shock interface does not match its '
      'independent handoff re-derivation'
    )
  elif not transonic_shock_interface_profile_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .TRANSONIC_SHOCK_INTERFACE_PROFILE_FAILURE
    )
    message = (
      'candidate audited transonic shock-interface profile does not match its '
      'independent handoff re-derivation'
    )
  elif not physical_field_continuation_profile_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .PHYSICAL_FIELD_CONTINUATION_FAILURE
    )
    message = (
      'candidate exact physical-field continuation does not match its '
      'independent field re-sampling'
    )
  elif not physical_field_shock_front_condition_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE
    )
    message = (
      'candidate exact physical-field shock-front condition does not match '
      'its independent front and neighboring-boundary remeasurement'
    )
  elif not control_section_compatibility_verified:
    status = (
      MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus
      .CONTROL_SECTION_COMPATIBILITY_FAILURE
    )
    message = (
      'candidate control-section/free-boundary inlet seam evidence does not '
      'match the bound control section'
    )
  elif not entropy_report_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.ENTROPY_FAILURE
    message = 'candidate entropy-loss and entropy-production diagnostics do not match the field'
  elif not entropy_production_map_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.ENTROPY_FAILURE
    message = 'candidate per-cell entropy-production map does not match the field'
  elif not boundary_report_verified:
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.BOUNDARY_FAILURE
    message = 'candidate free-boundary diagnostic arrays do not match the field'
  elif (
    np.any(
      np.abs(pressure - pressure_targets)
      > candidate.request.free_boundary_pressure_tolerance_fraction
      * pressure_targets
    )
    or normal_fraction
    > candidate.request.free_boundary_normal_velocity_tolerance_fraction
  ):
    status = MocReflectedDomainCoupledEulerFreeBoundaryAuditStatus.BOUNDARY_FAILURE
    message = (
      'independent free-boundary pressure target or tangency residual exceeds '
      'tolerance'
    )
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
    maximum_entropy_production_fraction=float(raw['entropy_production_fraction']),
    geometry_verified=bool(raw['geometry_verified']),
    state_samples_verified=bool(raw['state_samples_verified']),
    thermodynamics_verified=bool(raw['thermodynamics_verified']),
    residual_channels_recomputed=True,
    residual_report_verified=report_verified and residuals_verified,
    free_boundary_report_verified=boundary_report_verified,
    free_boundary_geometry_profile_verified=(
      free_boundary_geometry_profile_verified
    ),
    pressure_budget_verified=pressure_budget_verified,
    transonic_transition_verified=transonic_transition_verified,
    transonic_frontier_compatibility_verified=(
      transonic_frontier_compatibility_verified
    ),
    transonic_shock_geometry_verified=transonic_shock_geometry_verified,
    transonic_shock_interface_verified=transonic_shock_interface_verified,
    transonic_shock_interface_profile_verified=(
      transonic_shock_interface_profile_verified
    ),
    physical_field_continuation_profile_verified=(
      physical_field_continuation_profile_verified
    ),
    physical_field_inlet_seam_verified=physical_field_inlet_seam_verified,
    physical_field_shock_front_condition_verified=(
      physical_field_shock_front_condition_verified
    ),
    control_section_compatibility_verified=(
      control_section_compatibility_verified
    ),
    control_section_pressure_jump_Pa=control_section_pressure_jump,
    control_section_pressure_jump_fraction=control_section_pressure_jump_fraction,
    entropy_report_verified=entropy_report_verified,
    entropy_production_map_verified=entropy_production_map_verified,
    entropy_transport_verified=bool(raw['entropy_verified']),
    promotion_flags_verified=promotion_flags_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    physical_closure_verified=False,
    message=message,
  )
####
