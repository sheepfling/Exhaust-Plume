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
    if self.maximum_inlet_state_residual is not None:
      residual = float(self.maximum_inlet_state_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'maximum_inlet_state_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'maximum_inlet_state_residual', residual)
    ####
    for name in (
      'placement_lineage_verified',
      'placement_geometry_verified',
      'coupled_request_verified',
      'coupled_field_present',
      'placement_consumed_verified',
      'interface_frame_verified',
      'inlet_state_seam_verified',
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
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """An interface handoff is not a globally closed physical field."""

    return False
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
    message=(
      'solver-owned transonic interface placement, downstream mesh frame, '
      'and consumed inlet states passed independent seam checks; global '
      'mixed-regime closure remains open'
    ),
  )
####
