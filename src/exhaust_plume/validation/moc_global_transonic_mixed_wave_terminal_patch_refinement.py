"""Resolution and disjoint-case evidence for the terminal-patch field lane.

The reflected-turn terminal-patch operator admits one locally audited field.
That result is not enough to establish stability across a resolution ladder or
transfer across independent mixed-wave source cases.  This module executes
fresh terminal-patch field solves for caller-owned typed interface/probe
sources and records those two evidence surfaces without opening global,
external-validation, or production claims.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_global_transonic_mixed_wave_interface import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_terminal_patch_physical_field import (
  MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult,
  solve_reflected_domain_global_transonic_mixed_wave_terminal_patch_physical_field,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_terminal_probe import (
  MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_CROSS_CASE_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStep',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementMeasurement',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseMeasurement',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCase',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseRun',
  'run_reflected_domain_global_transonic_mixed_wave_terminal_patch_refinement',
  'run_reflected_domain_global_transonic_mixed_wave_terminal_patch_cross_case_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-patch-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_CROSS_CASE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-patch-cross-case-refinement'
)


class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus(
  str,
  Enum,
):
  """Typed outcome of local ladder and disjoint-case evidence."""

  CONVERGED_RESEARCH_LADDER = (
    'converged-research-global-transonic-mixed-wave-terminal-patch-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'global-transonic-mixed-wave-terminal-patch-refinement-source-failure'
  FIELD_FAILURE = 'global-transonic-mixed-wave-terminal-patch-refinement-field-failure'
  AUDIT_FAILURE = 'global-transonic-mixed-wave-terminal-patch-refinement-audit-failure'
  RESOLUTION_FAILURE = 'global-transonic-mixed-wave-terminal-patch-refinement-resolution-failure'
  CONVERGED_RESEARCH_CROSS_CASE = (
    'converged-research-global-transonic-mixed-wave-terminal-patch-cross-case'
  )
  CROSS_CASE_FAILURE = (
    'global-transonic-mixed-wave-terminal-patch-cross-case-failure'
  )
####


def _configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
  serialized = json.dumps(
    dict(configuration),
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _sample_counts(values: Sequence[int]) -> tuple[int, ...]:
  resolved = tuple(values)
  if len(resolved) < 2:
    raise ValueError('sample_counts must contain at least two resolutions')
  ####
  if any(
    isinstance(value, bool) or not isinstance(value, int) or value < 3
    for value in resolved
  ):
    raise ValueError('sample_counts must contain integers >= 3')
  ####
  if any(right <= left for left, right in zip(resolved, resolved[1:])):
    raise ValueError('sample_counts must be strictly increasing')
  ####
  return resolved
####


def _source_fingerprint(
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  terminal_probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
) -> str:
  return _configuration_fingerprint(
    {
      'interface': interface.as_report(),
      'terminal_probe': terminal_probe.as_report(),
    }
  )
####


def _audit_maximum_residual(
  audit: Any,
) -> float:
  values = (
    *tuple(audit.shock_jump_mass_residuals),
    *tuple(audit.shock_jump_momentum_residuals),
    *tuple(audit.shock_jump_energy_residuals),
    *tuple(audit.cell_euler_residuals),
  )
  if not values or not all(isfinite(float(value)) for value in values):
    return float('inf')
  ####
  return max(float(value) for value in values)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStep:
  """One fresh terminal-patch physical-field solve."""

  sample_count: int
  source_fingerprint: str
  result: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult | None
  fresh_solver_invocation_verified: bool = False
  source_lineage_verified: bool = False
  terminal_patch_lineage_verified: bool = False
  reflected_turn_law_verified: bool = False
  audit_verified: bool = False
  audit_residuals_finite: bool = False
  sample_count_verified: bool = False
  global_promotion_blocked: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer >= 3')
    ####
    if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint:
      raise ValueError('source_fingerprint must be non-empty')
    ####
    if self.result is not None and not isinstance(
      self.result,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult,
    ):
      raise TypeError('result must be a typed terminal-patch field result or None')
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'source_lineage_verified',
      'terminal_patch_lineage_verified',
      'reflected_turn_law_verified',
      'audit_verified',
      'audit_residuals_finite',
      'sample_count_verified',
      'global_promotion_blocked',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.global_promotion_blocked:
      raise ValueError('terminal-patch refinement must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.result is not None
      and self.result.converged
      and self.fresh_solver_invocation_verified
      and self.source_lineage_verified
      and self.terminal_patch_lineage_verified
      and self.reflected_turn_law_verified
      and self.audit_verified
      and self.audit_residuals_finite
      and self.sample_count_verified
      and self.global_promotion_blocked
      and not self.result.global_coupling_verified
      and not self.result.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_count': self.sample_count,
      'source_fingerprint': self.source_fingerprint,
      'converged': self.converged,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'terminal_patch_lineage_verified': self.terminal_patch_lineage_verified,
      'reflected_turn_law_verified': self.reflected_turn_law_verified,
      'audit_verified': self.audit_verified,
      'audit_residuals_finite': self.audit_residuals_finite,
      'sample_count_verified': self.sample_count_verified,
      'global_promotion_blocked': self.global_promotion_blocked,
      'result': None if self.result is None else self.result.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementMeasurement:
  """Independent aggregate evidence for one resolution ladder."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
  source_fingerprint: str
  requested_sample_counts: tuple[int, ...]
  steps: tuple[MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStep, ...] = ()
  resolution_order_verified: bool = False
  fresh_solves_verified: bool = False
  local_audits_verified: bool = False
  residual_trend_verified: bool = False
  source_lineage_verified: bool = False
  reflected_turn_law_verified: bool = False
  global_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus,
    ):
      raise TypeError('status must be a typed terminal-patch refinement status')
    ####
    if not isinstance(self.source_fingerprint, str) or not self.source_fingerprint:
      raise ValueError('source_fingerprint must be non-empty')
    ####
    counts = tuple(self.requested_sample_counts)
    if counts != _sample_counts(counts):
      raise ValueError('requested_sample_counts must be strictly increasing')
    ####
    steps = tuple(self.steps)
    if len(counts) != len(steps):
      raise ValueError('requested_sample_counts and steps must align')
    ####
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed terminal-patch refinement steps')
    ####
    for name in (
      'resolution_order_verified',
      'fresh_solves_verified',
      'local_audits_verified',
      'residual_trend_verified',
      'source_lineage_verified',
      'reflected_turn_law_verified',
      'global_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.global_promotion_blocked or self.production_claim_allowed:
      raise ValueError('terminal-patch refinement cannot open promotion')
    ####
    if not self.external_validation_required:
      raise ValueError('terminal-patch refinement must retain external validation')
    ####
    object.__setattr__(self, 'requested_sample_counts', counts)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
      .CONVERGED_RESEARCH_LADDER
      and len(self.steps) >= 2
      and self.resolution_order_verified
      and self.fresh_solves_verified
      and self.local_audits_verified
      and self.residual_trend_verified
      and self.source_lineage_verified
      and self.reflected_turn_law_verified
      and self.global_promotion_blocked
      and not self.production_claim_allowed
      and self.external_validation_required
      and all(step.converged for step in self.steps)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'source_fingerprint': self.source_fingerprint,
      'requested_sample_counts': self.requested_sample_counts,
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'fresh_solves_verified': self.fresh_solves_verified,
        'local_audits_verified': self.local_audits_verified,
        'residual_trend_verified': self.residual_trend_verified,
        'source_lineage_verified': self.source_lineage_verified,
        'reflected_turn_law_verified': self.reflected_turn_law_verified,
        'global_promotion_blocked': self.global_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'external_validation_required': self.external_validation_required,
      },
      'steps': tuple(step.as_report() for step in self.steps),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase:
  """Caller-owned source binding for one independent resolution ladder."""

  case_id: str
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult
  terminal_probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult
  outer_flow_angle_bracket: tuple[float, float]
  sample_counts: tuple[int, ...]

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.interface,
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
    ):
      raise TypeError('interface must be a typed mixed-wave interface result')
    ####
    if not isinstance(
      self.terminal_probe,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult,
    ):
      raise TypeError('terminal_probe must be a typed terminal-probe result')
    ####
    bracket = tuple(float(value) for value in self.outer_flow_angle_bracket)
    if len(bracket) != 2 or not all(isfinite(value) for value in bracket):
      raise ValueError('outer_flow_angle_bracket must contain two finite values')
    ####
    if bracket[0] >= bracket[1]:
      raise ValueError('outer_flow_angle_bracket must be strictly ordered')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'outer_flow_angle_bracket', bracket)
    object.__setattr__(self, 'sample_counts', _sample_counts(self.sample_counts))
  ####

  @property
  def source_fingerprint(self) -> str:
    return _source_fingerprint(self.interface, self.terminal_probe)
  ####

  @property
  def source_lineage_verified(self) -> bool:
    return bool(
      self.interface.local_interface_verified
      and self.terminal_probe.converged
      and self.terminal_probe.interface is self.interface
      and self.terminal_probe.reflection_patch_verified
      and self.terminal_probe.terminal_reference_verified
    )
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun:
  """Execution record for one fresh terminal-patch resolution ladder."""

  case: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase
  measurement: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.case,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase,
    ):
      raise TypeError('case must be a typed terminal-patch refinement case')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementMeasurement,
    ):
      raise TypeError('measurement must be a typed terminal-patch measurement')
    ####
    configuration = dict(self.configuration)
    if self.configuration_fingerprint != _configuration_fingerprint(configuration):
      raise ValueError('configuration_fingerprint does not match configuration')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_REFINEMENT_OPERATOR_ID,
      'case_id': self.case.case_id,
      'converged': self.converged,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_transonic_mixed_wave_terminal_patch_refinement(
  case: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase,
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  euler_shock_residual_tolerance: float = 1.0e-2,
  euler_cell_residual_tolerance: float = 1.0e-2,
  residual_trend_tolerance: float = 1.0e-12,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun:
  """Freshly execute and audit one terminal-patch resolution ladder."""

  if not isinstance(
    case,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase,
  ):
    raise TypeError('case must be a typed terminal-patch refinement case')
  ####
  if not isinstance(branch, ShockBranch):
    raise ValueError('branch must be a ShockBranch')
  ####
  numeric = (
    position_tolerance_m,
    invariant_tolerance,
    attachment_pressure_tolerance,
    pressure_tolerance,
    tangent_tolerance,
    shock_angle_tolerance_rad,
    euler_shock_residual_tolerance,
    euler_cell_residual_tolerance,
    residual_trend_tolerance,
  )
  resolved_numeric = tuple(float(value) for value in numeric)
  if not all(isfinite(value) and value > 0.0 for value in resolved_numeric):
    raise ValueError('refinement tolerances must be finite and positive')
  ####
  for name, value in (
    ('maximum_segment_iterations', maximum_segment_iterations),
    ('maximum_boundary_iterations', maximum_boundary_iterations),
    ('maximum_shooting_iterations', maximum_shooting_iterations),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      raise ValueError(f'{name} must be a positive integer')
    ####
  ####

  source_fingerprint = case.source_fingerprint
  source_lineage_verified = case.source_lineage_verified
  steps: list[MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStep] = []
  for sample_count in case.sample_counts:
    result: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchPhysicalFieldResult | None = None
    error_message = ''
    try:
      result = solve_reflected_domain_global_transonic_mixed_wave_terminal_patch_physical_field(
        case.interface,
        case.terminal_probe,
        outer_flow_angle_bracket=case.outer_flow_angle_bracket,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=resolved_numeric[0],
        invariant_tolerance=resolved_numeric[1],
        attachment_pressure_tolerance=resolved_numeric[2],
        pressure_tolerance=resolved_numeric[3],
        tangent_tolerance=resolved_numeric[4],
        shock_angle_tolerance_rad=resolved_numeric[5],
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        euler_shock_residual_tolerance=resolved_numeric[6],
        euler_cell_residual_tolerance=resolved_numeric[7],
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      error_message = f'terminal-patch refinement solve raised: {error}'
    ####
    field = None if result is None else result.physical_field
    audit = None if result is None else result.audit
    source_ok = bool(
      result is not None
      and result.interface is case.interface
      and result.terminal_probe is case.terminal_probe
      and result.interface_consumed
      and result.source_field_consumed
      and result.frontier_consumed
      and result.terminal_probe_consumed
    )
    patch_ok = bool(
      field is not None
      and field.patch is case.terminal_probe.reflection_patch
      and field.continuation_law == 'reflected-negative-turn'
    )
    audit_values = () if audit is None else (
      *tuple(audit.shock_jump_mass_residuals),
      *tuple(audit.shock_jump_momentum_residuals),
      *tuple(audit.shock_jump_energy_residuals),
      *tuple(audit.cell_euler_residuals),
    )
    audit_finite = bool(
      audit is not None
      and audit_values
      and all(isfinite(float(value)) for value in audit_values)
    )
    sample_verified = bool(
      result is not None
      and result.sample_count == sample_count
      and audit is not None
      and len(audit.shock_jump_mass_residuals) == sample_count
    )
    steps.append(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStep(
        sample_count=sample_count,
        source_fingerprint=source_fingerprint,
        result=result,
        fresh_solver_invocation_verified=result is not None,
        source_lineage_verified=source_lineage_verified and source_ok,
        terminal_patch_lineage_verified=patch_ok,
        reflected_turn_law_verified=patch_ok,
        audit_verified=bool(result is not None and result.audit is not None and result.audit.converged),
        audit_residuals_finite=audit_finite,
        sample_count_verified=sample_verified,
        global_promotion_blocked=bool(
          result is None
          or (result.chain_promotion_blocked and not result.global_coupling_verified)
        ),
        message=error_message if error_message else (
          '' if result is None else result.message
        ),
      )
    )
  ####

  results = tuple(step.result for step in steps if step.result is not None)
  resolution_order_verified = bool(
    tuple(step.sample_count for step in steps) == case.sample_counts
  )
  fresh_solves_verified = bool(
    len(results) == len(case.sample_counts)
    and len({id(result) for result in results}) == len(results)
    and len({id(result.physical_field) for result in results}) == len(results)
  )
  local_audits_verified = bool(steps and all(step.audit_verified for step in steps))
  source_verified = bool(steps and all(step.source_lineage_verified for step in steps))
  turn_verified = bool(steps and all(step.reflected_turn_law_verified for step in steps))
  residuals = tuple(
    _audit_maximum_residual(step.result.audit)
    for step in steps
    if step.result is not None and step.result.audit is not None
  )
  residual_trend_verified = bool(
    len(residuals) == len(steps)
    and all(
      right <= left + resolved_numeric[8]
      for left, right in zip(residuals, residuals[1:])
    )
  )
  aggregate = bool(
    resolution_order_verified
    and fresh_solves_verified
    and local_audits_verified
    and residual_trend_verified
    and source_verified
    and turn_verified
    and steps
    and all(step.converged for step in steps)
  )
  status = (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
    .CONVERGED_RESEARCH_LADDER
    if aggregate
    else MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
    .RESOLUTION_FAILURE
  )
  configuration: dict[str, Any] = {
    'source_fingerprint': source_fingerprint,
    'sample_counts': case.sample_counts,
    'outer_flow_angle_bracket': case.outer_flow_angle_bracket,
    'branch': branch.value,
    'position_tolerance_m': resolved_numeric[0],
    'invariant_tolerance': resolved_numeric[1],
    'euler_shock_residual_tolerance': resolved_numeric[6],
    'euler_cell_residual_tolerance': resolved_numeric[7],
    'residual_trend_tolerance': resolved_numeric[8],
    'policy': 'fresh-reflected-negative-turn-audit-ladder-v1',
  }
  message = (
    'terminal-patch reflected-turn resolution ladder passed fresh local Euler '
    'audits and non-increasing residual checks; global closure remains blocked'
    if aggregate
    else 'terminal-patch resolution ladder did not pass source, audit, freshness, '
    'or residual-trend checks'
  )
  measurement = MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementMeasurement(
    status=status,
    source_fingerprint=source_fingerprint,
    requested_sample_counts=case.sample_counts,
    steps=tuple(steps),
    resolution_order_verified=resolution_order_verified,
    fresh_solves_verified=fresh_solves_verified,
    local_audits_verified=local_audits_verified,
    residual_trend_verified=residual_trend_verified,
    source_lineage_verified=source_verified,
    reflected_turn_law_verified=turn_verified,
    message=message,
  )
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun(
    case=case,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    fresh_solver_invocation_verified=fresh_solves_verified,
    fidelity_isolation_verified=bool(
      all(
        step.global_promotion_blocked
        and step.result is not None
        and not step.result.production_claim_allowed
        for step in steps
      )
    ),
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseMeasurement:
  """Independent aggregate evidence for disjoint terminal-patch cases."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
  case_ids: tuple[str, ...]
  source_fingerprints: tuple[str, ...]
  results: tuple[MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun, ...] = ()
  case_bindings_verified: bool = False
  distinct_sources_verified: bool = False
  resolution_ladders_verified: bool = False
  fresh_solves_verified: bool = False
  residual_trends_verified: bool = False
  global_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_CROSS_CASE_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus,
    ):
      raise TypeError('status must be a typed terminal-patch status')
    ####
    ids = tuple(str(value) for value in self.case_ids)
    fingerprints = tuple(str(value) for value in self.source_fingerprints)
    results = tuple(self.results)
    if len(ids) != len(fingerprints) or len(ids) != len(results):
      raise ValueError('case IDs, fingerprints, and results must align')
    ####
    if len(set(ids)) != len(ids):
      raise ValueError('case IDs must be unique')
    ####
    if len(set(fingerprints)) != len(fingerprints):
      raise ValueError('source fingerprints must be distinct')
    ####
    if any(
      not isinstance(
        result,
        MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun,
      )
      for result in results
    ):
      raise TypeError('results must contain typed terminal-patch runs')
    ####
    for name in (
      'case_bindings_verified',
      'distinct_sources_verified',
      'resolution_ladders_verified',
      'fresh_solves_verified',
      'residual_trends_verified',
      'global_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.global_promotion_blocked or self.production_claim_allowed:
      raise ValueError('cross-case terminal-patch evidence cannot open promotion')
    ####
    if not self.external_validation_required:
      raise ValueError('cross-case terminal-patch evidence must retain validation')
    ####
    object.__setattr__(self, 'case_ids', ids)
    object.__setattr__(self, 'source_fingerprints', fingerprints)
    object.__setattr__(self, 'results', results)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      and len(self.results) >= 2
      and self.case_bindings_verified
      and self.distinct_sources_verified
      and self.resolution_ladders_verified
      and self.fresh_solves_verified
      and self.residual_trends_verified
      and self.global_promotion_blocked
      and not self.production_claim_allowed
      and self.external_validation_required
      and all(result.converged for result in self.results)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'source_fingerprints': self.source_fingerprints,
      'checks': {
        'case_bindings_verified': self.case_bindings_verified,
        'distinct_sources_verified': self.distinct_sources_verified,
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'fresh_solves_verified': self.fresh_solves_verified,
        'residual_trends_verified': self.residual_trends_verified,
        'global_promotion_blocked': self.global_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'external_validation_required': self.external_validation_required,
      },
      'results': tuple(result.as_report() for result in self.results),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCase:
  """One independently sourced terminal-patch refinement binding."""

  case_id: str
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult
  terminal_probe: MocReflectedDomainGlobalTransonicMixedWaveTerminalProbeResult
  outer_flow_angle_bracket: tuple[float, float]
  sample_counts: tuple[int, ...]

  def __post_init__(self) -> None:
    # Reuse the single-case validator so cross-case bindings cannot bypass
    # source type, bracket, or strictly increasing resolution checks.
    self.as_case()
  ####

  def as_case(self) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase:
    return MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementCase(
      case_id=self.case_id,
      interface=self.interface,
      terminal_probe=self.terminal_probe,
      outer_flow_angle_bracket=self.outer_flow_angle_bracket,
      sample_counts=self.sample_counts,
    )
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseRun:
  """Execution record for disjoint terminal-patch ladders."""

  cases: tuple[MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCase, ...]
  results: tuple[MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun, ...]
  measurement: MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    results = tuple(self.results)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed terminal-patch cross-case bindings')
    ####
    if any(
      not isinstance(
        result,
        MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementRun,
      )
      for result in results
    ):
      raise TypeError('results must contain typed terminal-patch refinement runs')
    ####
    if len(cases) != len(results) or len(cases) != len(self.measurement.results):
      raise ValueError('cases, results, and measurement results must align')
    ####
    configuration = dict(self.configuration)
    if self.configuration_fingerprint != _configuration_fingerprint(configuration):
      raise ValueError('configuration_fingerprint does not match configuration')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'results', results)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_PATCH_CROSS_CASE_REFINEMENT_OPERATOR_ID,
      'converged': self.converged,
      'case_ids': tuple(case.case_id for case in self.cases),
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'results': tuple(result.as_report() for result in self.results),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_transonic_mixed_wave_terminal_patch_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCase],
  **kwargs: Any,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseRun:
  """Freshly execute at least two independently fingerprinted ladders."""

  resolved_cases = tuple(cases)
  if len(resolved_cases) < 2:
    raise ValueError('cross-case refinement requires at least two cases')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCase,
    )
    for case in resolved_cases
  ):
    raise TypeError('cases must contain typed terminal-patch cross-case bindings')
  ####
  bindings = tuple(case.as_case() for case in resolved_cases)
  case_ids = tuple(case.case_id for case in bindings)
  fingerprints = tuple(case.source_fingerprint for case in bindings)
  case_bindings = bool(
    len(set(case_ids)) == len(case_ids)
    and all(case.source_lineage_verified for case in bindings)
  )
  distinct_sources = len(set(fingerprints)) == len(fingerprints)
  results = tuple(
    run_reflected_domain_global_transonic_mixed_wave_terminal_patch_refinement(
      case,
      **kwargs,
    )
    for case in bindings
  )
  ladders_verified = bool(results and all(result.measurement.converged for result in results))
  fresh_solves = bool(results and all(result.fresh_solver_invocation_verified for result in results))
  residual_trends = bool(results and all(result.measurement.residual_trend_verified for result in results))
  aggregate = bool(
    case_bindings
    and distinct_sources
    and ladders_verified
    and fresh_solves
    and residual_trends
  )
  status = (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
    .CONVERGED_RESEARCH_CROSS_CASE
    if aggregate
    else MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchRefinementStatus
    .CROSS_CASE_FAILURE
  )
  message = (
    'disjoint terminal-patch ladders passed source, fresh-audit, resolution, '
    'and residual-trend checks; global closure remains blocked'
    if aggregate
    else 'cross-case terminal-patch refinement did not pass distinct-source, '
    'lineage, ladder, or residual-trend checks'
  )
  measurement = MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseMeasurement(
    status=status,
    case_ids=case_ids,
    source_fingerprints=fingerprints,
    results=results,
    case_bindings_verified=case_bindings,
    distinct_sources_verified=distinct_sources,
    resolution_ladders_verified=ladders_verified,
    fresh_solves_verified=fresh_solves,
    residual_trends_verified=residual_trends,
    message=message,
  )
  configuration = {
    'case_ids': case_ids,
    'source_fingerprints': fingerprints,
    'case_sample_counts': tuple(case.sample_counts for case in bindings),
    'policy': 'distinct-source-fingerprint-fresh-reflected-negative-turn-ladders-v1',
    'kwargs': dict(kwargs),
  }
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalPatchCrossCaseRun(
    cases=resolved_cases,
    results=results,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    fresh_solver_invocation_verified=fresh_solves,
    fidelity_isolation_verified=bool(
      all(result.fidelity_isolation_verified for result in results)
    ),
    message=message,
  )
####
