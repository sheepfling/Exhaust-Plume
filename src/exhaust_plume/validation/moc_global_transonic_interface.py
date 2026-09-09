"""Independent audit of the global-to-coupled transonic interface handoff.

The global coupled-downstream candidate already carries a solver-owned
cross-section profile into the downstream finite-volume field.  This module
audits the seam that connects those two lanes without treating the handoff as
canonical mixed-regime closure.  It rederives the consumed inlet states from
the retained subsonic profile, checks exact object lineage, and verifies that
the downstream mesh starts at the selected interface.

The audit is deliberately narrower than a free-boundary solver.  A passing
result proves local interface consumption only; it does not prove upstream
feedback, ambient attachment, centerline reflection, refinement, physical
shock-cell length, or production validity.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

import numpy as np

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementResult,
  MocTransonicShockInterfaceProfile,
)
from exhaust_plume.validation.moc_transonic_interface import (
  measure_moc_transonic_shock_interface_profile_build,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_INTERFACE_AUDIT_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicInterfaceAuditStatus',
  'MocReflectedDomainGlobalTransonicInterfaceAudit',
  'measure_reflected_domain_global_transonic_interface',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_INTERFACE_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-interface-audit'
)


class MocReflectedDomainGlobalTransonicInterfaceAuditStatus(str, Enum):
  """Outcome of the exact global-to-coupled interface audit."""

  CONVERGED_LOCAL_INTERFACE_HANDOFF = (
    'converged-local-global-transonic-interface-handoff'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-transonic-interface-source-closure-failure'
  PLACEMENT_FAILURE = 'global-transonic-interface-placement-failure'
  COUPLED_FIELD_REQUIRED = 'global-transonic-interface-coupled-field-required'
  LINEAGE_FAILURE = 'global-transonic-interface-lineage-failure'
  FRAME_FAILURE = 'global-transonic-interface-frame-failure'
  INTERFACE_JUMP_FAILURE = (
    'global-transonic-interface-rankine-hugoniot-jump-failure'
  )
  AMBIENT_BOUNDARY_FAILURE = (
    'global-transonic-interface-ambient-boundary-residual-failure'
  )
  INLET_SEAM_FAILURE = 'global-transonic-interface-inlet-seam-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicInterfaceAudit:
  """Independent evidence for one consumed interior interface profile."""

  status: MocReflectedDomainGlobalTransonicInterfaceAuditStatus
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult | None
  source_closure_fingerprint: str | None = None
  placement_status: str | None = None
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_INTERFACE_AUDIT_OPERATOR_ID
  )
  placement_lineage_verified: bool = False
  placement_geometry_verified: bool = False
  coupled_request_verified: bool = False
  coupled_field_present: bool = False
  placement_consumed_verified: bool = False
  interface_frame_verified: bool = False
  expected_inlet_state_count: int = 0
  inlet_state_count: int = 0
  maximum_inlet_state_residual: float | None = None
  inlet_state_seam_verified: bool = False
  interface_jump_audit_status: str | None = None
  maximum_interface_state_residual: float | None = None
  maximum_interface_pressure_residual: float | None = None
  maximum_interface_total_pressure_residual: float | None = None
  interface_jump_verified: bool = False
  ambient_boundary_pressure_residual_Pa: float | None = None
  ambient_boundary_pressure_residual_fraction: float | None = None
  ambient_boundary_normal_velocity_residual_fraction: float | None = None
  ambient_boundary_verified: bool = False
  centerline_boundary_required: bool = True
  centerline_boundary_verified: bool = False
  canonical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalTransonicInterfaceAuditStatus'
      )
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError(
        'candidate must be a '
        'MocReflectedDomainGlobalCoupledDownstreamResult or None'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    if self.source_closure_fingerprint is not None:
      fingerprint = str(self.source_closure_fingerprint)
      if len(fingerprint) != 64:
        raise ValueError('source_closure_fingerprint must be a SHA-256 digest')
      ####
      object.__setattr__(self, 'source_closure_fingerprint', fingerprint)
    ####
    if self.placement_status is not None:
      object.__setattr__(self, 'placement_status', str(self.placement_status))
    ####
    for name in ('expected_inlet_state_count', 'inlet_state_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'maximum_inlet_state_residual',
      'maximum_interface_state_residual',
      'maximum_interface_pressure_residual',
      'maximum_interface_total_pressure_residual',
      'ambient_boundary_pressure_residual_Pa',
      'ambient_boundary_pressure_residual_fraction',
      'ambient_boundary_normal_velocity_residual_fraction',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      residual = float(value)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, residual)
    ####
    if self.interface_jump_audit_status is not None:
      object.__setattr__(
        self,
        'interface_jump_audit_status',
        str(self.interface_jump_audit_status),
      )
    ####
    for name in (
      'placement_lineage_verified',
      'placement_geometry_verified',
      'coupled_request_verified',
      'coupled_field_present',
      'placement_consumed_verified',
      'interface_frame_verified',
      'inlet_state_seam_verified',
      'interface_jump_verified',
      'ambient_boundary_verified',
      'centerline_boundary_required',
      'centerline_boundary_verified',
      'canonical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_closure_verified:
      raise ValueError('this local interface audit cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('this local interface audit must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('this local interface audit cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the exact local interface handoff passed independently."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicInterfaceAuditStatus
      .CONVERGED_LOCAL_INTERFACE_HANDOFF
      and self.source_closure_fingerprint is not None
      and self.placement_lineage_verified
      and self.placement_geometry_verified
      and self.coupled_request_verified
      and self.coupled_field_present
      and self.placement_consumed_verified
      and self.interface_frame_verified
      and self.expected_inlet_state_count == self.inlet_state_count
      and self.inlet_state_seam_verified
      and self.interface_jump_verified
      and self.ambient_boundary_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """An interface handoff is not a globally closed physical field."""

    return False
  ####

  @property
  def joint_boundary_residuals_verified(self) -> bool:
    """Whether ambient and centerline boundaries are both independently closed."""

    return bool(
      self.interface_jump_verified
      and self.ambient_boundary_verified
      and (
        not self.centerline_boundary_required
        or self.centerline_boundary_verified
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'placement_status': self.placement_status,
      'placement_lineage_verified': self.placement_lineage_verified,
      'placement_geometry_verified': self.placement_geometry_verified,
      'coupled_request_verified': self.coupled_request_verified,
      'coupled_field_present': self.coupled_field_present,
      'placement_consumed_verified': self.placement_consumed_verified,
      'interface_frame_verified': self.interface_frame_verified,
      'expected_inlet_state_count': self.expected_inlet_state_count,
      'inlet_state_count': self.inlet_state_count,
      'maximum_inlet_state_residual': self.maximum_inlet_state_residual,
      'inlet_state_seam_verified': self.inlet_state_seam_verified,
      'interface_jump_audit_status': self.interface_jump_audit_status,
      'maximum_interface_state_residual': (
        self.maximum_interface_state_residual
      ),
      'maximum_interface_pressure_residual': (
        self.maximum_interface_pressure_residual
      ),
      'maximum_interface_total_pressure_residual': (
        self.maximum_interface_total_pressure_residual
      ),
      'interface_jump_verified': self.interface_jump_verified,
      'ambient_boundary_pressure_residual_Pa': (
        self.ambient_boundary_pressure_residual_Pa
      ),
      'ambient_boundary_pressure_residual_fraction': (
        self.ambient_boundary_pressure_residual_fraction
      ),
      'ambient_boundary_normal_velocity_residual_fraction': (
        self.ambient_boundary_normal_velocity_residual_fraction
      ),
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'centerline_boundary_required': self.centerline_boundary_required,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'joint_boundary_residuals_verified': (
        self.joint_boundary_residuals_verified
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_closure_verified': self.canonical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-local-transonic-interface-handoff; global feedback, '
        'mixed-regime closure, refinement, physical shock-cell length, and '
        'external validation remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalTransonicInterfaceAuditStatus,
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult | None,
  message: str,
  **kwargs: Any,
) -> MocReflectedDomainGlobalTransonicInterfaceAudit:
  fingerprint = (
    None if candidate is None else candidate.source_closure_fingerprint
  )
  placement = (
    None
    if candidate is None
    or candidate.transonic_shock_interface_field_placement is None
    else candidate.transonic_shock_interface_field_placement
  )
  return MocReflectedDomainGlobalTransonicInterfaceAudit(
    status=status,
    candidate=candidate,
    source_closure_fingerprint=fingerprint,
    placement_status=None if placement is None else placement.status.value,
    message=message,
    **kwargs,
  )
####


def _conservative_state_from_profile_sample(
  total_pressure_Pa: float,
  mach: float,
  flow_angle_rad: float,
  gamma: float,
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  pressure_factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_temperature = total_temperature_K / pressure_factor
  static_pressure = total_pressure_Pa / pressure_factor ** (
    gamma / (gamma - 1.0)
  )
  density = static_pressure / (gas_constant_J_kgK * static_temperature)
  sound_speed = np.sqrt(gamma * gas_constant_J_kgK * static_temperature)
  speed = mach * sound_speed
  return np.asarray(
    (
      density,
      density * speed * np.cos(flow_angle_rad),
      density * speed * np.sin(flow_angle_rad),
      static_pressure / (gamma - 1.0) + 0.5 * density * speed * speed,
    ),
    dtype=float,
  )
####


def _profile_inlet_states(
  profile: MocTransonicShockInterfaceProfile,
  transverse_cell_count: int,
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, ...]:
  ordinates = np.asarray(
    [sample.point_m[1] for sample in profile.downstream_samples],
    dtype=float,
  )
  fields = {
    name: np.asarray(
      [getattr(sample, name) for sample in profile.downstream_samples],
      dtype=float,
    )
    for name in ('total_pressure_Pa', 'mach', 'flow_angle_rad')
  }
  face_width = (
    profile.upper_ordinate_m - profile.lower_ordinate_m
  ) / transverse_cell_count
  return tuple(
    _conservative_state_from_profile_sample(
      float(np.interp(
        profile.lower_ordinate_m + (index + 0.5) * face_width,
        ordinates,
        fields['total_pressure_Pa'],
      )),
      float(np.interp(
        profile.lower_ordinate_m + (index + 0.5) * face_width,
        ordinates,
        fields['mach'],
      )),
      float(np.interp(
        profile.lower_ordinate_m + (index + 0.5) * face_width,
        ordinates,
        fields['flow_angle_rad'],
      )),
      profile.gamma,
      total_temperature_K,
      gas_constant_J_kgK,
    )
    for index in range(transverse_cell_count)
  )
####


def _independent_ambient_boundary_residuals(
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> tuple[bool, float | None, float | None, float | None]:
  """Recompute pressure and tangency residuals on the coupled outer edge."""

  request = candidate.coupled_request
  field = candidate.coupled_field
  if request is None or field is None:
    return False, None, None, None
  ####
  transverse_count = int(request.transverse_cell_count)
  axial_count = int(request.axial_cell_count)
  if transverse_count < 1 or axial_count < 1:
    return False, None, None, None
  ####
  target_pressures = (
    tuple(request.free_boundary_pressure_profile_Pa)
    if request.free_boundary_pressure_profile_Pa is not None
    else (float(request.mixed_regime_request.ambient_pressure_Pa),) * axial_count
  )
  if len(target_pressures) != axial_count:
    return False, None, None, None
  ####
  expected_cell_count = axial_count * transverse_count
  if (
    len(field.conservative_states_by_cell) != expected_cell_count
    or len(field.cell_vertices_by_cell_m) != expected_cell_count
  ):
    return False, None, None, None
  ####
  pressure_residuals: list[float] = []
  pressure_fraction_residuals: list[float] = []
  normal_velocity_residuals: list[float] = []
  speeds: list[float] = []
  gamma = float(
    request.mixed_regime_request.control_section.samples[0].gamma
  )
  for axial_index in range(axial_count):
    cell_index = axial_index * transverse_count + transverse_count - 1
    state = np.asarray(field.conservative_states_by_cell[cell_index], dtype=float)
    polygon = np.asarray(field.cell_vertices_by_cell_m[cell_index], dtype=float)
    if state.shape != (4,) or polygon.shape != (4, 2):
      return False, None, None, None
    ####
    density = float(state[0])
    if not isfinite(density) or density <= 0.0:
      return False, None, None, None
    ####
    velocity_u = float(state[1]) / density
    velocity_v = float(state[2]) / density
    pressure = (gamma - 1.0) * (
      float(state[3])
      - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
    )
    if not isfinite(pressure) or pressure <= 0.0:
      return False, None, None, None
    ####
    first = polygon[2]
    second = polygon[3]
    delta_x = float(second[0] - first[0])
    delta_y = float(second[1] - first[1])
    face_length = float(np.hypot(delta_x, delta_y))
    if not isfinite(face_length) or face_length <= 0.0:
      return False, None, None, None
    ####
    normal_x = delta_y / face_length
    normal_y = -delta_x / face_length
    normal_velocity = velocity_u * normal_x + velocity_v * normal_y
    speed = float(np.hypot(velocity_u, velocity_v))
    target_pressure = float(target_pressures[axial_index])
    if not isfinite(target_pressure) or target_pressure <= 0.0:
      return False, None, None, None
    ####
    pressure_residual = abs(pressure - target_pressure)
    pressure_fraction = pressure_residual / max(abs(target_pressure), 1.0e-12)
    if not all(
      isfinite(value)
      for value in (normal_velocity, speed, pressure_residual, pressure_fraction)
    ):
      return False, None, None, None
    ####
    pressure_residuals.append(pressure_residual)
    pressure_fraction_residuals.append(pressure_fraction)
    normal_velocity_residuals.append(abs(normal_velocity))
    speeds.append(speed)
  ####
  maximum_pressure_residual = max(pressure_residuals, default=float('inf'))
  maximum_pressure_fraction = max(
    pressure_fraction_residuals,
    default=float('inf'),
  )
  maximum_speed = max(max(speeds, default=0.0), 1.0e-12)
  maximum_normal_fraction = max(normal_velocity_residuals, default=float('inf')) / (
    maximum_speed
  )
  verified = bool(
    isfinite(maximum_pressure_residual)
    and isfinite(maximum_pressure_fraction)
    and isfinite(maximum_normal_fraction)
    and maximum_pressure_fraction
    <= request.free_boundary_pressure_tolerance_fraction
    and maximum_normal_fraction
    <= request.free_boundary_normal_velocity_tolerance_fraction
  )
  return (
    verified,
    maximum_pressure_residual,
    maximum_pressure_fraction,
    maximum_normal_fraction,
  )
####


def measure_reflected_domain_global_transonic_interface(
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> MocReflectedDomainGlobalTransonicInterfaceAudit:
  """Re-derive the consumed interface profile and downstream inlet seam."""

  if not isinstance(
    candidate,
    MocReflectedDomainGlobalCoupledDownstreamResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.INVALID_INPUT,
      None,
      'candidate must be a '
      'MocReflectedDomainGlobalCoupledDownstreamResult',
    )
  ####
  fingerprint = candidate.source_closure_fingerprint
  if (
    fingerprint is None
    or candidate.closure is None
    or not candidate.closure_lineage_verified
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.SOURCE_CLOSURE_FAILURE,
      candidate,
      'interface audit requires one lineage-verified global physical closure',
    )
  ####
  placement = candidate.transonic_shock_interface_field_placement
  if not isinstance(
    placement,
    MocTransonicShockInterfaceFieldPlacementResult,
  ) or not placement.converged:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.PLACEMENT_FAILURE,
      candidate,
      'interface audit requires a converged solver-owned field placement',
    )
  ####
  placement_measurement = placement.independent_measurement
  placement_geometry_verified = bool(
    getattr(placement_measurement, 'full_field_cross_section_verified', False)
  )
  exact_field = None
  if candidate.closure.global_euler is not None:
    physical_field = candidate.closure.global_euler.physical_field
    if physical_field is not None:
      exact_field = physical_field.field
    ####
  ####
  placement_lineage_verified = bool(
    exact_field is not None
    and placement.field is exact_field
    and placement.request.field is exact_field
  )
  if not placement_lineage_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.LINEAGE_FAILURE,
      candidate,
      'placement does not retain the exact global closure physical field',
      placement_lineage_verified=False,
      placement_geometry_verified=placement_geometry_verified,
    )
  ####
  if not placement_geometry_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.PLACEMENT_FAILURE,
      candidate,
      'placement did not pass its independent full-field cross-section audit',
      placement_lineage_verified=True,
      placement_geometry_verified=False,
    )
  ####
  request = candidate.coupled_request
  field = candidate.coupled_field
  if request is None or field is None:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.COUPLED_FIELD_REQUIRED,
      candidate,
      'interface audit requires a downstream coupled-Euler field result',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
    )
  ####
  coupled_request_verified = bool(
    request.inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    and request.source_closure_fingerprint == fingerprint
    and field.request is request
    and request.transonic_shock_interface_field_placement is placement
    and candidate.transonic_shock_interface_field_placement is placement
  )
  placement_consumed_verified = bool(
    field.transonic_shock_interface_field_placement is placement
    and field.transonic_shock_interface_profile is placement.profile
    and field.transonic_shock_interface_field_placement_consumed
    and field.transonic_shock_interface_profile_consumed
    and field.inlet_boundary_states_consumed
  )
  if not coupled_request_verified or not placement_consumed_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.LINEAGE_FAILURE,
      candidate,
      'coupled field did not retain and consume the exact solver-owned '
      'interface placement/profile objects',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=coupled_request_verified,
      coupled_field_present=True,
      placement_consumed_verified=placement_consumed_verified,
    )
  ####
  profile = placement.profile
  if profile is None:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.PLACEMENT_FAILURE,
      candidate,
      'converged placement retained no interface profile',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=False,
    )
  ####
  profile_result = placement.profile_result
  profile_build = (
    None if profile_result is None else profile_result.profile_build
  )
  if profile_build is None:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.INTERFACE_JUMP_FAILURE,
      candidate,
      'interface placement retained no normal-shock profile build to rederive',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=True,
    )
  ####
  try:
    interface_jump_audit = measure_moc_transonic_shock_interface_profile_build(
      profile_build
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.INTERFACE_JUMP_FAILURE,
      candidate,
      f'interface Rankine--Hugoniot rederivation raised: {error}',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=True,
    )
  ####
  interface_jump_verified = bool(interface_jump_audit.converged)
  interface_jump_kwargs = {
    'interface_jump_audit_status': interface_jump_audit.status.value,
    'maximum_interface_state_residual': (
      interface_jump_audit.maximum_state_residual
    ),
    'maximum_interface_pressure_residual': (
      interface_jump_audit.maximum_pressure_residual
    ),
    'maximum_interface_total_pressure_residual': (
      interface_jump_audit.maximum_total_pressure_residual
    ),
    'interface_jump_verified': interface_jump_verified,
  }
  if not interface_jump_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.INTERFACE_JUMP_FAILURE,
      candidate,
      'retained interface profile failed independent Rankine--Hugoniot '
      'state and pressure rederivation',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=True,
      **interface_jump_kwargs,
    )
  ####
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(profile.cross_section_x_m), 1.0))
  control_x = float(request.mixed_regime_request.control_section.points_m[0][0])
  interface_frame_verified = bool(
    profile.cross_section_x_m > control_x + x_tolerance
    and len(field.x_stations_m) > 0
    and abs(float(field.x_stations_m[0]) - profile.cross_section_x_m)
    <= x_tolerance
    and len(field.free_boundary_points_m) > 0
    and abs(float(field.free_boundary_points_m[0][0]) - profile.cross_section_x_m)
    <= x_tolerance
  )
  if not interface_frame_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.FRAME_FAILURE,
      candidate,
      'downstream coupled mesh does not start at the retained interface '
      'cross-section',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=True,
      interface_frame_verified=False,
      **interface_jump_kwargs,
    )
  ####
  expected_states = _profile_inlet_states(
    profile,
    request.transverse_cell_count,
    request.reference_total_temperature_K,
    request.gas_constant_J_kgK,
  )
  actual_states = tuple(field.inlet_boundary_conservative_states_by_face)
  expected_count = len(expected_states)
  actual_count = len(actual_states)
  maximum_residual = float('inf')
  if actual_count == expected_count:
    maximum_residual = max(
      (
        float(
          np.max(
            np.abs(np.asarray(actual) - expected)
            / np.maximum(np.abs(expected), 1.0e-12)
          )
        )
        for actual, expected in zip(actual_states, expected_states, strict=True)
      ),
      default=0.0,
    )
  ####
  inlet_state_seam_verified = bool(
    actual_count == expected_count
    and isfinite(maximum_residual)
    and maximum_residual <= max(profile.state_tolerance, 1.0e-9)
  )
  if not inlet_state_seam_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus.INLET_SEAM_FAILURE,
      candidate,
      'retained downstream inlet states do not match an independent '
      'reconstruction from the interface profile',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=True,
      interface_frame_verified=True,
      expected_inlet_state_count=expected_count,
      inlet_state_count=actual_count,
      maximum_inlet_state_residual=maximum_residual,
      inlet_state_seam_verified=False,
      **interface_jump_kwargs,
    )
  ####
  (
    ambient_boundary_verified,
    ambient_pressure_residual_Pa,
    ambient_pressure_residual_fraction,
    ambient_normal_velocity_residual_fraction,
  ) = _independent_ambient_boundary_residuals(candidate)
  ambient_kwargs = {
    'ambient_boundary_pressure_residual_Pa': ambient_pressure_residual_Pa,
    'ambient_boundary_pressure_residual_fraction': (
      ambient_pressure_residual_fraction
    ),
    'ambient_boundary_normal_velocity_residual_fraction': (
      ambient_normal_velocity_residual_fraction
    ),
    'ambient_boundary_verified': ambient_boundary_verified,
  }
  if not ambient_boundary_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus
      .AMBIENT_BOUNDARY_FAILURE,
      candidate,
      'coupled field outer-boundary pressure or tangency residual did not '
      'pass its declared tolerance',
      placement_lineage_verified=True,
      placement_geometry_verified=True,
      coupled_request_verified=True,
      coupled_field_present=True,
      placement_consumed_verified=True,
      interface_frame_verified=True,
      expected_inlet_state_count=expected_count,
      inlet_state_count=actual_count,
      maximum_inlet_state_residual=maximum_residual,
      inlet_state_seam_verified=True,
      **interface_jump_kwargs,
      **ambient_kwargs,
    )
  ####
  return MocReflectedDomainGlobalTransonicInterfaceAudit(
    status=(
      MocReflectedDomainGlobalTransonicInterfaceAuditStatus
      .CONVERGED_LOCAL_INTERFACE_HANDOFF
    ),
    candidate=candidate,
    source_closure_fingerprint=fingerprint,
    placement_status=placement.status.value,
    placement_lineage_verified=True,
    placement_geometry_verified=True,
    coupled_request_verified=True,
    coupled_field_present=True,
    placement_consumed_verified=True,
    interface_frame_verified=True,
    expected_inlet_state_count=expected_count,
    inlet_state_count=actual_count,
    maximum_inlet_state_residual=maximum_residual,
    inlet_state_seam_verified=True,
    **interface_jump_kwargs,
    **ambient_kwargs,
    centerline_boundary_required=True,
    centerline_boundary_verified=False,
    message=(
      'solver-owned transonic interface placement, downstream mesh frame, '
      'consumed inlet states, interface Rankine--Hugoniot rederivation, and '
      'outer-boundary pressure/tangency residuals passed; the downstream '
      'candidate retains no global centerline reflection closure, so mixed-'
      'regime closure remains open'
    ),
  )
####
