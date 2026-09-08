"""Pressure-conditioned conservative consumption of a global frontier target.

This operator is the next research step after target-guided candidate
selection.  It binds the exact global-frontier request to a retained physical
field, consumes the requested static-pressure profile in the ambient-face
Euler flux, and independently audits the resulting residuals.

The mesh and shock placement are still fixed by the retained field.  Geometry,
transonic placement, free-boundary motion, canonical global coupling, and
production shock-cell promotion therefore remain explicit hard gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfileRequest,
  build_moc_physical_field_continuation_profile,
)
from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
  MocPhysicalFieldEulerReconciliationRequest,
  MocPhysicalFieldEulerReconciliationResult,
  compose_moc_physical_field_euler_boundary_pressure_target,
  solve_moc_physical_field_euler_reconciliation,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionRequest,
  MocPhysicalFieldShockFrontConditionResult,
  build_moc_physical_field_shock_front_condition,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementRequest,
  build_moc_transonic_shock_interface_profile_from_field_placement,
)
from exhaust_plume.validation.moc_physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerReconciliationAudit,
  measure_moc_physical_field_euler_reconciliation,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_PRESSURE_RECONCILIATION_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus',
  'MocReflectedDomainGlobalFrontierTargetPressureReconciliationResult',
  'run_reflected_domain_global_frontier_target_pressure_reconciliation',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_PRESSURE_RECONCILIATION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-target-pressure-reconciliation'
)


class MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus(str, Enum):
  """Outcome of consuming one exact target pressure profile."""

  CONVERGED_LOCAL_TARGET_PRESSURE_RECONCILIATION = (
    'converged-local-global-frontier-target-pressure-reconciliation'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-frontier-target-pressure-source-failure'
  CANDIDATE_CLOSURE_FAILURE = (
    'global-frontier-target-pressure-candidate-failure'
  )
  TARGET_LINEAGE_FAILURE = 'global-frontier-target-pressure-lineage-failure'
  TARGET_COMPOSITION_FAILURE = (
    'global-frontier-target-pressure-composition-failure'
  )
  FRONT_CONDITION_FAILURE = 'global-frontier-target-pressure-front-failure'
  TARGET_COVERAGE_FAILURE = 'global-frontier-target-pressure-coverage-failure'
  SOLVER_FAILURE = 'global-frontier-target-pressure-solver-failure'
  AUDIT_FAILURE = 'global-frontier-target-pressure-audit-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierTargetPressureReconciliationResult:
  """Research result for one exact target-pressure consumer."""

  status: MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  candidate_closure_fingerprint: str | None = None
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  consumed_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  front_condition: MocPhysicalFieldShockFrontConditionResult | None = None
  reconciliation: MocPhysicalFieldEulerReconciliationResult | None = None
  audit: MocPhysicalFieldEulerReconciliationAudit | None = None
  target_lineage_verified: bool = False
  target_composition_verified: bool = False
  target_coverage_verified: bool = False
  target_consumption_verified: bool = False
  independent_audit_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus,
    ):
      raise TypeError('status must be a typed target-pressure status')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError('request must be a global-frontier reconciliation request')
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a global physical closure result')
    ####
    if self.candidate_closure_fingerprint is not None:
      candidate_fingerprint = str(self.candidate_closure_fingerprint)
      if len(candidate_fingerprint) != 64 or any(
        character not in '0123456789abcdef'
        for character in candidate_fingerprint
      ):
        raise ValueError(
          'candidate_closure_fingerprint must be a lowercase SHA-256 digest'
        )
      ####
      object.__setattr__(
        self,
        'candidate_closure_fingerprint',
        candidate_fingerprint,
      )
    ####
    if self.target is not None and not isinstance(
      self.target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError('target must be a typed pressure target or None')
    ####
    if self.consumed_target is not None and not isinstance(
      self.consumed_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError('consumed_target must be a typed pressure target or None')
    ####
    if self.front_condition is not None and not isinstance(
      self.front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError('front_condition must be a typed front condition or None')
    ####
    if self.reconciliation is not None and not isinstance(
      self.reconciliation,
      MocPhysicalFieldEulerReconciliationResult,
    ):
      raise TypeError('reconciliation must be a typed reconciliation or None')
    ####
    if self.audit is not None and not isinstance(
      self.audit,
      MocPhysicalFieldEulerReconciliationAudit,
    ):
      raise TypeError('audit must be a typed reconciliation audit or None')
    ####
    for name in (
      'target_lineage_verified',
      'target_composition_verified',
      'target_coverage_verified',
      'target_consumption_verified',
      'independent_audit_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'fixed-front target-pressure reconciliation cannot claim global closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'fixed-front target-pressure reconciliation must remain blocked'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged_research_reconciliation(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .CONVERGED_LOCAL_TARGET_PRESSURE_RECONCILIATION
      and self.target_lineage_verified
      and self.target_composition_verified
      and self.target_coverage_verified
      and self.target_consumption_verified
      and self.independent_audit_verified
      and self.reconciliation is not None
      and self.reconciliation.converged
      and self.audit is not None
      and self.audit.converged
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_PRESSURE_RECONCILIATION_OPERATOR_ID,
      'status': self.status.value,
      'converged_research_reconciliation': self.converged_research_reconciliation,
      'target_lineage_verified': self.target_lineage_verified,
      'target_composition_verified': self.target_composition_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': self.downstream_boundary_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'candidate_closure_fingerprint': self.candidate_closure_fingerprint,
      'source_proposal_fingerprint': (
        moc_reflected_domain_global_frontier_proposal_fingerprint(
          self.request.proposal
        )
      ),
      'target': None if self.target is None else self.target.as_report(),
      'consumed_target': (
        None
        if self.consumed_target is None
        else self.consumed_target.as_report()
      ),
      'front_condition': (
        None if self.front_condition is None else self.front_condition.as_report()
      ),
      'reconciliation': (
        None if self.reconciliation is None else self.reconciliation.as_report()
      ),
      'audit': None if self.audit is None else self.audit.as_report(),
      'request': self.request.as_report(),
      'claim_status': (
        'research-only-fixed-front-target-pressure-consumption; shock placement, '
        'free-boundary geometry, global feedback, refinement, external validation, '
        'and production gates remain open'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  candidate_closure_fingerprint: str | None = None,
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None,
  consumed_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None,
  front_condition: MocPhysicalFieldShockFrontConditionResult | None = None,
  reconciliation: MocPhysicalFieldEulerReconciliationResult | None = None,
  audit: MocPhysicalFieldEulerReconciliationAudit | None = None,
  target_lineage_verified: bool = False,
  target_composition_verified: bool = False,
  target_coverage_verified: bool = False,
  target_consumption_verified: bool = False,
  independent_audit_verified: bool = False,
  message: str,
) -> MocReflectedDomainGlobalFrontierTargetPressureReconciliationResult:
  return MocReflectedDomainGlobalFrontierTargetPressureReconciliationResult(
    status=status,
    request=request,
    source_closure=source_closure,
    candidate_closure_fingerprint=candidate_closure_fingerprint,
    target=target,
    consumed_target=consumed_target,
    front_condition=front_condition,
    reconciliation=reconciliation,
    audit=audit,
    target_lineage_verified=target_lineage_verified,
    target_composition_verified=target_composition_verified,
    target_coverage_verified=target_coverage_verified,
    target_consumption_verified=target_consumption_verified,
    independent_audit_verified=independent_audit_verified,
    message=message,
  )
####


def _build_front_condition(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> MocPhysicalFieldShockFrontConditionResult:
  if closure.global_euler is None or closure.global_euler.physical_field is None:
    raise ValueError('source closure retained no global physical field')
  ####
  field = closure.global_euler.physical_field.field
  if field is None or not field.physical_closure_verified:
    raise ValueError('source closure retained no verified physical field')
  ####
  placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      boundary_margin_fraction=0.0,
    )
  )
  if not placement.converged:
    raise ValueError(f'physical-field placement did not converge: {placement.message}')
  ####
  continuation = build_moc_physical_field_continuation_profile(
    MocPhysicalFieldContinuationProfileRequest(
      field=field,
      sample_points_m=placement.sample_points_m,
    )
  )
  if not continuation.converged:
    raise ValueError(
      f'physical-field continuation did not converge: {continuation.message}'
    )
  ####
  condition = build_moc_physical_field_shock_front_condition(
    MocPhysicalFieldShockFrontConditionRequest(
      continuation_profile=continuation,
      condition_id='solver-owned-global-frontier-target-pressure-v1',
    )
  )
  if not condition.converged:
    raise ValueError(
      f'shock-front condition did not converge: {condition.message}'
    )
  ####
  return condition
####


def run_reflected_domain_global_frontier_target_pressure_reconciliation(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  candidate_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  reference_total_temperature_K: float = 1500.0,
  request_options: Mapping[str, Any] | None = None,
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None,
  target_composition_seam_pressure_tolerance_fraction: float = 0.25,
) -> MocReflectedDomainGlobalFrontierTargetPressureReconciliationResult:
  """Consume an exact frontier target in a fixed-front conservative solve.

  ``source_closure`` owns the proposal lineage.  ``candidate_closure`` is an
  optional fresh global candidate whose retained physical field supplies the
  fixed mesh and shock-front condition consumed by the conservative solver.
  Keeping those identities separate prevents a fresh candidate from being
  mistaken for the closure that produced the target packet.  When
  ``base_target`` is supplied, it owns the full candidate station frame and
  the exact frontier target is consumed only as an explicit bounded overlay;
  the resulting profile is retained separately as ``consumed_target``.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  resolved_candidate = source_closure if candidate_closure is None else candidate_closure
  if not isinstance(
    resolved_candidate,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'candidate_closure must be a MocReflectedDomainGlobalPhysicalClosureResult '
      'or None'
    )
  ####
  candidate_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    resolved_candidate
  )
  lineage_verified = bool(
    request.lineage_verified
    and request.source_closure_fingerprint
    == moc_reflected_domain_global_physical_closure_fingerprint(source_closure)
    and request.source_proposal_fingerprint
    == moc_reflected_domain_global_frontier_proposal_fingerprint(
      request.proposal
    )
  )
  if not lineage_verified:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .TARGET_LINEAGE_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      message='global frontier request does not match the exact source closure or proposal',
    )
  ####
  if not source_closure.converged or not source_closure.physical_closure_verified:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target_lineage_verified=True,
      message='target-pressure consumption requires a locally verified source closure',
    )
  ####
  if (
    not resolved_candidate.converged
    or not resolved_candidate.physical_closure_verified
  ):
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .CANDIDATE_CLOSURE_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target_lineage_verified=True,
      message=(
        'target-pressure consumption requires a locally verified fresh '
        'candidate closure'
      ),
    )
  ####
  try:
    target = MocPhysicalFieldEulerBoundaryPressureTarget(
      x_stations_m=request.target_x_stations_m,
      static_pressure_Pa=request.target_static_pressure_Pa,
      boundary_points_m=request.target_boundary_points_m,
      tangent_rad=request.target_tangent_rad,
      source_id=request.consumer_id,
      source_closure_fingerprint=request.source_closure_fingerprint,
      source_proposal_fingerprint=request.source_proposal_fingerprint,
    )
  except (ArithmeticError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .TARGET_LINEAGE_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target_lineage_verified=True,
      message=f'frontier target could not become a typed pressure profile: {error}',
    )
  ####
  consumed_target = target
  target_composition_verified = True
  if base_target is not None:
    try:
      consumed_target = compose_moc_physical_field_euler_boundary_pressure_target(
        base_target,
        target,
        source_id=f'{request.consumer_id}:explicit-overlay',
        seam_pressure_tolerance_fraction=(
          target_composition_seam_pressure_tolerance_fraction
        ),
      )
    except (ArithmeticError, TypeError, ValueError) as error:
      return _result(
        MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
        .TARGET_COMPOSITION_FAILURE,
        request,
        source_closure,
        candidate_closure_fingerprint=candidate_fingerprint,
        target=target,
        target_lineage_verified=True,
        message=f'frontier target overlay composition failed: {error}',
      )
    ####
  ####
  try:
    condition = _build_front_condition(resolved_candidate)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .FRONT_CONDITION_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target=target,
      consumed_target=consumed_target,
      target_lineage_verified=True,
      target_composition_verified=target_composition_verified,
      message=f'source field could not produce a typed front condition: {error}',
    )
  ####
  options = {} if request_options is None else dict(request_options)
  if 'ambient_pressure_target' in options:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .INVALID_INPUT,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target=target,
      consumed_target=consumed_target,
      front_condition=condition,
      target_lineage_verified=True,
      target_composition_verified=target_composition_verified,
      message='request_options cannot replace the exact frontier pressure target',
    )
  ####
  try:
    solver_request = MocPhysicalFieldEulerReconciliationRequest(
      shock_front_condition=condition,
      reference_total_temperature_K=reference_total_temperature_K,
      ambient_pressure_target=consumed_target,
      **options,
    )
    reconciliation = solve_moc_physical_field_euler_reconciliation(
      solver_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .SOLVER_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target=target,
      consumed_target=consumed_target,
      front_condition=condition,
      target_lineage_verified=True,
      target_composition_verified=target_composition_verified,
      message=f'target-pressure conservative solve raised: {error}',
    )
  ####
  target_coverage_verified = bool(
    reconciliation.ambient_pressure_target_coverage_verified
  )
  if not target_coverage_verified:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .TARGET_COVERAGE_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target=target,
      consumed_target=consumed_target,
      front_condition=condition,
      reconciliation=reconciliation,
      target_lineage_verified=True,
      target_composition_verified=target_composition_verified,
      message=(
        'exact frontier target did not cover the fixed-field ambient path; '
        'no extrapolation or endpoint hold was attempted'
      ),
    )
  ####
  audit = measure_moc_physical_field_euler_reconciliation(reconciliation)
  target_consumed = bool(
    reconciliation.ambient_pressure_target_consumed
    and audit.ambient_pressure_target_consumption_verified
    and audit.ambient_pressure_target_residual_report_verified
  )
  independent_audit_verified = bool(audit.converged)
  if not reconciliation.converged:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .SOLVER_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target=target,
      consumed_target=consumed_target,
      front_condition=condition,
      reconciliation=reconciliation,
      audit=audit,
      target_lineage_verified=True,
      target_composition_verified=target_composition_verified,
      target_coverage_verified=target_coverage_verified,
      target_consumption_verified=target_consumed,
      independent_audit_verified=independent_audit_verified,
      message=f'target-pressure conservative solve did not converge: {reconciliation.message}',
    )
  ####
  if not independent_audit_verified or not target_consumed:
    return _result(
      MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
      .AUDIT_FAILURE,
      request,
      source_closure,
      candidate_closure_fingerprint=candidate_fingerprint,
      target=target,
      consumed_target=consumed_target,
      front_condition=condition,
      reconciliation=reconciliation,
      audit=audit,
      target_lineage_verified=True,
      target_composition_verified=target_composition_verified,
      target_coverage_verified=target_coverage_verified,
      target_consumption_verified=target_consumed,
      independent_audit_verified=independent_audit_verified,
      message=(
        'target-pressure conservative solve completed, but independent '
        'target-consumption or residual audit did not pass'
      ),
    )
  ####
  return _result(
    MocReflectedDomainGlobalFrontierTargetPressureReconciliationStatus
    .CONVERGED_LOCAL_TARGET_PRESSURE_RECONCILIATION,
    request,
    source_closure,
    candidate_closure_fingerprint=candidate_fingerprint,
    target=target,
    consumed_target=consumed_target,
    front_condition=condition,
    reconciliation=reconciliation,
    audit=audit,
    target_lineage_verified=True,
    target_composition_verified=target_composition_verified,
    target_coverage_verified=True,
    target_consumption_verified=True,
    independent_audit_verified=True,
    message=(
      'exact global-frontier pressure target was consumed in the fixed-front '
      'conservative field of the retained candidate and independently audited; '
      'global geometry and free-boundary closure remain open'
    ),
  )
####
