"""Scalar transonic handoff from the audited mixed-wave terminal probe.

The terminal-reflection probe retains an in-domain normal-shock reference, but
its upstream MOC state intentionally carries no dimensional temperature or gas
constant.  This module supplies those two explicit thermodynamic anchors and
reconstructs the existing scalar transonic state/geometry binding at the
retained terminal point.

The handoff is a research seam only.  It does not move the point onto a
coupled-field inlet, solve a neighboring subsonic field, close a free
boundary, fit a shock cell, or authorize a production claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, cos, isfinite, isclose, sin
from typing import Any

from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryResult,
  MocTransonicShockState,
  measure_moc_transonic_shock_geometry,
  reconstruct_moc_transonic_shock_state,
  solve_moc_transonic_shock_geometry,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_terminal_probe import (
  MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit,
  MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
  measure_reflected_domain_global_transonic_mixed_wave_terminal_probe,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_HANDOFF_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_HANDOFF_AUDIT_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit',
  'build_reflected_domain_global_transonic_mixed_wave_terminal_handoff',
  'measure_reflected_domain_global_transonic_mixed_wave_terminal_handoff',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_HANDOFF_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-transonic-handoff'
)
MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_HANDOFF_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-transonic-handoff-audit'
)
DEFAULT_SCALAR_TOLERANCE_FRACTION = 1.0e-8
DEFAULT_NORMAL_ALIGNMENT_TOLERANCE_RAD = 1.0e-8
DEFAULT_FLUX_TOLERANCE = 1.0e-8


class MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus(
  str,
  Enum,
):
  """Typed outcomes of the scalar terminal handoff."""

  VERIFIED_SCALAR_GEOMETRY_HANDOFF = (
    'verified-global-transonic-mixed-wave-terminal-scalar-geometry-handoff'
  )
  INVALID_INPUT = 'invalid_input'
  TERMINAL_PROBE_AUDIT_REQUIRED = (
    'global-transonic-mixed-wave-terminal-probe-audit-required'
  )
  TERMINAL_REFERENCE_REQUIRED = (
    'global-transonic-mixed-wave-terminal-reference-required'
  )
  SHOCK_STATE_RECONSTRUCTION_FAILURE = (
    'global-transonic-mixed-wave-terminal-shock-state-reconstruction-failure'
  )
  TERMINAL_STATE_MISMATCH = (
    'global-transonic-mixed-wave-terminal-state-mismatch'
  )
  GEOMETRY_BINDING_FAILURE = (
    'global-transonic-mixed-wave-terminal-geometry-binding-failure'
  )


class MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the retained scalar handoff audit."""

  VERIFIED = 'verified-global-transonic-mixed-wave-terminal-scalar-handoff'
  INVALID_INPUT = 'invalid_input'
  CANDIDATE_REQUIRED = (
    'global-transonic-mixed-wave-terminal-scalar-handoff-required'
  )
  PROBE_FAILURE = (
    'global-transonic-mixed-wave-terminal-scalar-handoff-probe-failure'
  )
  SHOCK_STATE_FAILURE = (
    'global-transonic-mixed-wave-terminal-scalar-handoff-shock-state-failure'
  )
  LINEAGE_FAILURE = (
    'global-transonic-mixed-wave-terminal-scalar-handoff-lineage-failure'
  )
  GEOMETRY_FAILURE = (
    'global-transonic-mixed-wave-terminal-scalar-handoff-geometry-failure'
  )
  CLAIM_FLAG_FAILURE = (
    'global-transonic-mixed-wave-terminal-scalar-handoff-claim-flag-failure'
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest:
  """Explicit dimensional anchors for one audited terminal probe."""

  probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult
  upstream_total_temperature_K: float
  gas_constant_J_kgK: float = 287.05
  scalar_tolerance_fraction: float = DEFAULT_SCALAR_TOLERANCE_FRACTION
  normal_alignment_tolerance_rad: float = (
    DEFAULT_NORMAL_ALIGNMENT_TOLERANCE_RAD
  )
  flux_tolerance: float = DEFAULT_FLUX_TOLERANCE

  def __post_init__(self) -> None:
    if not isinstance(
      self.probe,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
    ):
      raise TypeError('probe must be a typed terminal-probe result')
    ####
    for name in (
      'upstream_total_temperature_K',
      'gas_constant_J_kgK',
      'scalar_tolerance_fraction',
      'normal_alignment_tolerance_rad',
      'flux_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'probe_status': self.probe.status.value,
      'upstream_total_temperature_K': self.upstream_total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'scalar_tolerance_fraction': self.scalar_tolerance_fraction,
      'normal_alignment_tolerance_rad': self.normal_alignment_tolerance_rad,
      'flux_tolerance': self.flux_tolerance,
      'model': (
        'research-global-transonic-mixed-wave-terminal-scalar-handoff-v1'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult:
  """Audited scalar state and geometry bound at the retained terminal point."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest
  terminal_probe_audit: (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit | None
  )
  shock_state: MocTransonicShockState | None = None
  geometry: MocTransonicShockGeometryResult | None = None
  geometry_audit: MocTransonicShockGeometryAudit | None = None
  maximum_state_residual: float | None = None
  maximum_pressure_residual_Pa: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus,
    ):
      raise TypeError('status must be a terminal-handoff status')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest,
    ):
      raise TypeError('request must be a terminal-handoff request')
    ####
    if self.terminal_probe_audit is not None and not isinstance(
      self.terminal_probe_audit,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit,
    ):
      raise TypeError('terminal_probe_audit must be a typed probe audit or None')
    ####
    if self.shock_state is not None and not isinstance(
      self.shock_state,
      MocTransonicShockState,
    ):
      raise TypeError('shock_state must be a typed scalar shock state or None')
    ####
    if self.geometry is not None and not isinstance(
      self.geometry,
      MocTransonicShockGeometryResult,
    ):
      raise TypeError('geometry must be a typed geometry result or None')
    ####
    if self.geometry_audit is not None and not isinstance(
      self.geometry_audit,
      MocTransonicShockGeometryAudit,
    ):
      raise TypeError('geometry_audit must be a typed geometry audit or None')
    ####
    for name in ('maximum_state_residual', 'maximum_pressure_residual_Pa'):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def handoff_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .VERIFIED_SCALAR_GEOMETRY_HANDOFF
      and self.terminal_probe_audit is not None
      and self.terminal_probe_audit.converged
      and self.shock_state is not None
      and self.geometry is not None
      and self.geometry.geometry_verified
      and self.geometry_audit is not None
      and self.geometry_audit.converged
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_HANDOFF_OPERATOR_ID
      ),
      'status': self.status.value,
      'handoff_verified': self.handoff_verified,
      'request': self.request.as_report(),
      'terminal_probe_audit': (
        None
        if self.terminal_probe_audit is None
        else self.terminal_probe_audit.as_report()
      ),
      'shock_state': (
        None if self.shock_state is None else self.shock_state.as_report()
      ),
      'geometry': None if self.geometry is None else self.geometry.as_report(),
      'geometry_audit': (
        None
        if self.geometry_audit is None
        else self.geometry_audit.as_report()
      ),
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
      'claim_status': (
        'research-only-scalar-terminal-geometry-handoff; terminal point is '
        'not promoted to a closed two-dimensional field or production shock '
        'cell'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit:
  """Independent remeasurement of one retained scalar terminal handoff."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
  candidate: (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult | None
  )
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_HANDOFF_AUDIT_OPERATOR_ID
  )
  terminal_probe_verified: bool = False
  shock_state_rederived: bool = False
  state_lineage_verified: bool = False
  geometry_rederived: bool = False
  geometry_binding_verified: bool = False
  claim_flags_verified: bool = False
  maximum_state_residual: float | None = None
  maximum_pressure_residual_Pa: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus,
    ):
      raise TypeError('status must be a terminal-handoff audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
    ):
      raise TypeError('candidate must be a typed terminal-handoff result or None')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    for name in (
      'terminal_probe_verified',
      'shock_state_rederived',
      'state_lineage_verified',
      'geometry_rederived',
      'geometry_binding_verified',
      'claim_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('maximum_state_residual', 'maximum_pressure_residual_Pa'):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .VERIFIED
      and self.terminal_probe_verified
      and self.shock_state_rederived
      and self.state_lineage_verified
      and self.geometry_rederived
      and self.geometry_binding_verified
      and self.claim_flags_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'terminal_probe_verified': self.terminal_probe_verified,
      'shock_state_rederived': self.shock_state_rederived,
      'state_lineage_verified': self.state_lineage_verified,
      'geometry_rederived': self.geometry_rederived,
      'geometry_binding_verified': self.geometry_binding_verified,
      'claim_flags_verified': self.claim_flags_verified,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'message': self.message,
    }
  ####


def _wrapped_angle_residual(first_angle_rad: float, second_angle_rad: float) -> float:
  return abs(
    atan2(
      sin(first_angle_rad - second_angle_rad),
      cos(first_angle_rad - second_angle_rad),
    )
  )


def _scalar_residual(actual: float, expected: float) -> float:
  return abs(float(actual) - float(expected)) / max(1.0, abs(float(expected)))


def _pressure_residual(actual: float, expected: float) -> float:
  return abs(float(actual) - float(expected))


def _terminal_from_probe(candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult):
  if candidate.terminal_patch_shock_probe is None:
    return None
  return candidate.terminal_patch_shock_probe.shock.normal_shock_terminal


def _state_residuals(
  state: MocTransonicShockState,
  terminal: Any,
) -> tuple[float, float]:
  upstream = terminal.upstream_state
  assert upstream is not None
  scalar_residuals = (
    _scalar_residual(state.upstream_mach, upstream.mach),
    _scalar_residual(state.downstream_mach, terminal.downstream_mach),
    _scalar_residual(state.gamma, upstream.gamma),
    _wrapped_angle_residual(state.upstream_flow_angle_rad, upstream.theta_rad),
  )
  pressure_residuals = (
    _pressure_residual(
      state.upstream_total_pressure_Pa,
      terminal.upstream_total_pressure_Pa,
    ),
    _pressure_residual(
      state.downstream_total_pressure_Pa,
      terminal.downstream_total_pressure_Pa,
    ),
    _pressure_residual(
      state.upstream_static_pressure_Pa,
      terminal.upstream_pressure_Pa,
    ),
    _pressure_residual(
      state.downstream_static_pressure_Pa,
      terminal.downstream_pressure_Pa,
    ),
    _pressure_residual(
      state.total_pressure_ratio,
      terminal.total_pressure_ratio,
    ),
  )
  return max(scalar_residuals), max(pressure_residuals)


def _shock_state_from_terminal(
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest,
  terminal: Any,
) -> MocTransonicShockState:
  upstream = terminal.upstream_state
  assert upstream is not None
  assert terminal.upstream_total_pressure_Pa is not None
  return reconstruct_moc_transonic_shock_state(
    upstream_total_pressure_Pa=float(terminal.upstream_total_pressure_Pa),
    gamma=float(upstream.gamma),
    gas_constant_J_kgK=request.gas_constant_J_kgK,
    upstream_total_temperature_K=request.upstream_total_temperature_K,
    upstream_mach=float(upstream.mach),
    upstream_flow_angle_rad=float(upstream.theta_rad),
  )


def _geometry_request(
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest,
  terminal: Any,
  state: MocTransonicShockState,
) -> MocTransonicShockGeometryRequest:
  assert terminal.shock_point_m is not None
  return MocTransonicShockGeometryRequest(
    shock_state=state,
    shock_point_m=terminal.shock_point_m,
    # The geometry binder expects the normal direction, not the tangent angle
    # retained by the normal-shock terminal diagnostic.
    shock_normal_angle_rad=state.upstream_flow_angle_rad,
    normal_alignment_tolerance_rad=request.normal_alignment_tolerance_rad,
    flux_tolerance=request.flux_tolerance,
  )


def _invalid_result(
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest,
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus,
  *,
  terminal_probe_audit: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeAudit | None,
  shock_state: MocTransonicShockState | None = None,
  geometry: MocTransonicShockGeometryResult | None = None,
  geometry_audit: MocTransonicShockGeometryAudit | None = None,
  maximum_state_residual: float | None = None,
  maximum_pressure_residual_Pa: float | None = None,
  message: str,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult(
    status=status,
    request=request,
    terminal_probe_audit=terminal_probe_audit,
    shock_state=shock_state,
    geometry=geometry,
    geometry_audit=geometry_audit,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual_Pa=maximum_pressure_residual_Pa,
    message=message,
  )


def build_reflected_domain_global_transonic_mixed_wave_terminal_handoff(
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult:
  """Reconstruct and bind the audited terminal's scalar shock state.

  The two dimensional location is not selected here: the retained terminal
  point is copied exactly, and the shock normal is derived from the retained
  upstream flow direction.  A caller that needs a coupled-field inlet must
  still prove that this point is the actual inlet section; the coupled solver
  is expected to reject an interior or shifted point.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffRequest,
  ):
    raise TypeError('request must be a terminal-handoff request')
  ####
  probe_audit = measure_reflected_domain_global_transonic_mixed_wave_terminal_probe(
    request.probe
  )
  if not probe_audit.converged:
    return _invalid_result(
      request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .TERMINAL_PROBE_AUDIT_REQUIRED,
      terminal_probe_audit=probe_audit,
      message=(
        'terminal scalar handoff requires a currently verified retained '
        'terminal probe'
      ),
    )
  ####
  terminal = _terminal_from_probe(request.probe)
  if (
    terminal is None
    or not terminal.converged
    or not terminal.subsonic
    or terminal.upstream_state is None
    or terminal.upstream_pressure_Pa is None
    or terminal.downstream_pressure_Pa is None
    or terminal.upstream_total_pressure_Pa is None
    or terminal.downstream_total_pressure_Pa is None
    or terminal.total_pressure_ratio is None
    or terminal.shock_point_m is None
  ):
    return _invalid_result(
      request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .TERMINAL_REFERENCE_REQUIRED,
      terminal_probe_audit=probe_audit,
      message=(
        'verified terminal probe retained no complete subsonic normal-shock '
        'reference for scalar reconstruction'
      ),
    )
  ####
  try:
    shock_state = _shock_state_from_terminal(request, terminal)
  except (ArithmeticError, TypeError, ValueError, ZeroDivisionError) as error:
    return _invalid_result(
      request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .SHOCK_STATE_RECONSTRUCTION_FAILURE,
      terminal_probe_audit=probe_audit,
      message=(
        'explicit thermodynamic anchors could not reconstruct a scalar '
        f'normal-shock state: {error}'
      ),
    )
  ####
  maximum_state_residual, maximum_pressure_residual = _state_residuals(
    shock_state,
    terminal,
  )
  pressure_scale = max(
    1.0,
    abs(float(terminal.upstream_total_pressure_Pa)),
    abs(float(terminal.downstream_total_pressure_Pa)),
    abs(float(terminal.upstream_pressure_Pa)),
    abs(float(terminal.downstream_pressure_Pa)),
  )
  if (
    maximum_state_residual > request.scalar_tolerance_fraction
    or maximum_pressure_residual > request.scalar_tolerance_fraction * pressure_scale
  ):
    return _invalid_result(
      request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .TERMINAL_STATE_MISMATCH,
      terminal_probe_audit=probe_audit,
      shock_state=shock_state,
      maximum_state_residual=maximum_state_residual,
      maximum_pressure_residual_Pa=maximum_pressure_residual,
      message=(
        'reconstructed scalar state does not match the retained terminal '
        f'(state residual={maximum_state_residual:.3e}, '
        f'pressure residual={maximum_pressure_residual:.3e} Pa)'
      ),
    )
  ####
  geometry_request = _geometry_request(request, terminal, shock_state)
  geometry = solve_moc_transonic_shock_geometry(geometry_request)
  geometry_audit = measure_moc_transonic_shock_geometry(geometry)
  if not geometry.geometry_verified or not geometry_audit.converged:
    return _invalid_result(
      request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .GEOMETRY_BINDING_FAILURE,
      terminal_probe_audit=probe_audit,
      shock_state=shock_state,
      geometry=geometry,
      geometry_audit=geometry_audit,
      maximum_state_residual=maximum_state_residual,
      maximum_pressure_residual_Pa=maximum_pressure_residual,
      message=(
        'retained terminal scalar state could not pass the independent '
        'normal-shock geometry audit'
      ),
    )
  ####
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult(
    status=(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
      .VERIFIED_SCALAR_GEOMETRY_HANDOFF
    ),
    request=request,
    terminal_probe_audit=probe_audit,
    shock_state=shock_state,
    geometry=geometry,
    geometry_audit=geometry_audit,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual_Pa=maximum_pressure_residual,
    message=(
      'explicit thermodynamic anchors reproduce the retained terminal scalar '
      'normal shock and bind it to the exact retained point; two-dimensional '
      'field closure and coupled-inlet placement remain open'
    ),
  )


def _shock_state_matches(
  reported: MocTransonicShockState,
  expected: MocTransonicShockState,
) -> bool:
  for name in (
    'upstream_total_pressure_Pa',
    'upstream_total_temperature_K',
    'downstream_total_pressure_Pa',
    'total_pressure_ratio',
    'gamma',
    'gas_constant_J_kgK',
    'upstream_mach',
    'downstream_mach',
    'upstream_static_pressure_Pa',
    'downstream_static_pressure_Pa',
    'upstream_static_temperature_K',
    'downstream_static_temperature_K',
    'upstream_density_kg_m3',
    'downstream_density_kg_m3',
    'upstream_sound_speed_m_s',
    'downstream_sound_speed_m_s',
    'upstream_speed_m_s',
    'downstream_speed_m_s',
    'entropy_increase_JpkgK',
    'upstream_flow_angle_rad',
  ):
    if not isclose(
      float(getattr(reported, name)),
      float(getattr(expected, name)),
      rel_tol=1.0e-8,
      abs_tol=1.0e-10,
    ):
      return False
    ####
  ####
  return reported.source == expected.source


def _geometry_matches(
  reported: MocTransonicShockGeometryResult,
  expected: MocTransonicShockGeometryResult,
) -> bool:
  if reported.status is not expected.status:
    return False
  ####
  for name in (
    'shock_normal_angle_rad',
    'shock_tangent_angle_rad',
    'normal_alignment_residual_rad',
    'upstream_normal_velocity_m_s',
    'downstream_normal_velocity_m_s',
    'upstream_tangential_velocity_m_s',
    'downstream_tangential_velocity_m_s',
    'mass_flux_residual',
    'momentum_flux_residual',
    'energy_flux_residual',
  ):
    if not isclose(
      float(getattr(reported, name)),
      float(getattr(expected, name)),
      rel_tol=1.0e-8,
      abs_tol=1.0e-10,
    ):
      return False
    ####
  ####
  return all(
    isclose(reported_value, expected_value, rel_tol=0.0, abs_tol=1.0e-12)
    for reported_value, expected_value in zip(
      reported.shock_point_m,
      expected.shock_point_m,
      strict=True,
    )
  )


def _audit_failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus,
  *,
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult | None,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit(
    status=status,
    candidate=candidate,
    message=message,
    **kwargs,
  )


def measure_reflected_domain_global_transonic_mixed_wave_terminal_handoff(
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit:
  """Remeasure the scalar terminal handoff without trusting retained values."""

  if not isinstance(
    candidate,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
  ):
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .INVALID_INPUT,
      candidate=None,
      message='candidate must be a typed terminal-handoff result',
    )
  ####
  if candidate.status is not (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffStatus
    .VERIFIED_SCALAR_GEOMETRY_HANDOFF
  ):
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .CANDIDATE_REQUIRED,
      candidate=candidate,
      message='candidate must retain a verified scalar terminal handoff',
    )
  ####
  expected_probe_audit = (
    measure_reflected_domain_global_transonic_mixed_wave_terminal_probe(
      candidate.request.probe
    )
  )
  terminal_probe_verified = expected_probe_audit.converged
  if not terminal_probe_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .PROBE_FAILURE,
      candidate=candidate,
      terminal_probe_verified=False,
      message='retained terminal probe no longer passes its independent audit',
    )
  ####
  terminal = _terminal_from_probe(candidate.request.probe)
  if (
    terminal is None
    or terminal.upstream_state is None
    or terminal.upstream_total_pressure_Pa is None
    or terminal.downstream_pressure_Pa is None
    or terminal.shock_point_m is None
  ):
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .PROBE_FAILURE,
      candidate=candidate,
      terminal_probe_verified=True,
      message='retained terminal probe no longer contains scalar handoff inputs',
    )
  ####
  try:
    expected_shock_state = _shock_state_from_terminal(candidate.request, terminal)
  except (ArithmeticError, TypeError, ValueError, ZeroDivisionError) as error:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .SHOCK_STATE_FAILURE,
      candidate=candidate,
      terminal_probe_verified=True,
      shock_state_rederived=False,
      message=f'scalar shock state could not be rederived: {error}',
    )
  ####
  state_residual, pressure_residual = _state_residuals(
    expected_shock_state,
    terminal,
  )
  pressure_scale = max(
    1.0,
    abs(float(terminal.upstream_total_pressure_Pa)),
    abs(float(terminal.downstream_total_pressure_Pa or 0.0)),
    abs(float(terminal.upstream_pressure_Pa or 0.0)),
    abs(float(terminal.downstream_pressure_Pa or 0.0)),
  )
  state_lineage_verified = bool(
    candidate.shock_state is not None
    and _shock_state_matches(candidate.shock_state, expected_shock_state)
    and state_residual <= candidate.request.scalar_tolerance_fraction
    and pressure_residual
    <= candidate.request.scalar_tolerance_fraction * pressure_scale
  )
  if not state_lineage_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .LINEAGE_FAILURE,
      candidate=candidate,
      terminal_probe_verified=True,
      shock_state_rederived=True,
      state_lineage_verified=False,
      maximum_state_residual=state_residual,
      maximum_pressure_residual_Pa=pressure_residual,
      message='retained scalar shock state does not match fresh reconstruction',
    )
  ####
  expected_geometry_request = _geometry_request(
    candidate.request,
    terminal,
    expected_shock_state,
  )
  expected_geometry = solve_moc_transonic_shock_geometry(
    expected_geometry_request
  )
  expected_geometry_audit = measure_moc_transonic_shock_geometry(expected_geometry)
  geometry_rederived = bool(
    expected_geometry.geometry_verified and expected_geometry_audit.converged
  )
  geometry_binding_verified = bool(
    geometry_rederived
    and candidate.geometry is not None
    and _geometry_matches(candidate.geometry, expected_geometry)
    and candidate.geometry_audit is not None
    and candidate.geometry_audit.converged
  )
  if not geometry_binding_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .GEOMETRY_FAILURE,
      candidate=candidate,
      terminal_probe_verified=True,
      shock_state_rederived=True,
      state_lineage_verified=True,
      geometry_rederived=geometry_rederived,
      geometry_binding_verified=False,
      maximum_state_residual=state_residual,
      maximum_pressure_residual_Pa=pressure_residual,
      message='retained scalar geometry does not match fresh terminal binding',
    )
  ####
  claim_flags_verified = bool(
    candidate.handoff_verified
    and candidate.physical_closure_verified is False
    and candidate.chain_promotion_blocked
    and candidate.production_claim_allowed is False
    and expected_geometry.physical_closure_verified is False
    and expected_geometry.chain_promotion_blocked
    and expected_geometry.production_claim_allowed is False
  )
  if not claim_flags_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .CLAIM_FLAG_FAILURE,
      candidate=candidate,
      terminal_probe_verified=True,
      shock_state_rederived=True,
      state_lineage_verified=True,
      geometry_rederived=True,
      geometry_binding_verified=True,
      claim_flags_verified=False,
      maximum_state_residual=state_residual,
      maximum_pressure_residual_Pa=pressure_residual,
      message='scalar handoff claim flags were weakened or inconsistent',
    )
  ####
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit(
    status=(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAuditStatus
      .VERIFIED
    ),
    candidate=candidate,
    terminal_probe_verified=True,
    shock_state_rederived=True,
    state_lineage_verified=True,
    geometry_rederived=True,
    geometry_binding_verified=True,
    claim_flags_verified=True,
    maximum_state_residual=state_residual,
    maximum_pressure_residual_Pa=pressure_residual,
    message=(
      'independent reconstruction verified the scalar terminal state and '
      'exact retained geometry; two-dimensional closure remains open'
    ),
  )
