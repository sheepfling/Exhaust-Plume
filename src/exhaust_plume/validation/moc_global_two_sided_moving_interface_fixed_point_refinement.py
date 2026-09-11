"""Strict fixed-point refinement evidence for the global moving-interface seam.

The ordinary global moving-interface refinement audit measures a research
response trend.  It deliberately does not require a terminal front fixed
point, because the current interior-probe response is not a physical closure.
This operator is the stricter admission surface for a future solver-owned
mixed-regime/free-boundary consumer: every case must request conservative
fluxes and a terminal fixed point, retain an independently remeasured exact
response chain, and pass the same policy on an ordered case/resolution
ladder.

The result is still research evidence.  Passing this operator cannot promote
the field, a shock-cell fit, Signature, or FPA claim without the separate
canonical, external-validation, and product gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
)
from exhaust_plume.validation.moc_euler_two_sided_moving_interface_fixed_point import (
  MocEulerTwoSidedMovingInterfaceFixedPointAudit,
  measure_moc_euler_two_sided_moving_interface_fixed_point,
)
from exhaust_plume.validation.moc_global_two_sided_moving_interface_refinement import (
  MocGlobalTwoSidedMovingInterfaceRefinementCase,
)

__all__ = (
  'MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_FIXED_POINT_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus',
  'MocGlobalTwoSidedMovingInterfaceFixedPointRefinementMeasurement',
  'measure_moc_global_two_sided_moving_interface_fixed_point_refinement',
)


MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_FIXED_POINT_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.global-two-sided-moving-interface-fixed-point-refinement-audit-v1'
)


class MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus(str, Enum):
  """Typed outcomes of the strict global fixed-point ladder."""

  CONVERGED_LOCAL_STRICT_FIXED_POINT = (
    'converged-global-two-sided-moving-interface-local-strict-fixed-point'
  )
  CONVERGED_CROSS_CASE_STRICT_FIXED_POINT = (
    'converged-global-two-sided-moving-interface-cross-case-strict-fixed-point'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = (
    'global-two-sided-moving-interface-fixed-point-refinement-case-failure'
  )
  MODE_FAILURE = (
    'global-two-sided-moving-interface-fixed-point-refinement-mode-failure'
  )
  RESOLUTION_ORDER_FAILURE = (
    'global-two-sided-moving-interface-fixed-point-refinement-resolution-order-failure'
  )
  LINEAGE_FAILURE = (
    'global-two-sided-moving-interface-fixed-point-refinement-lineage-failure'
  )
  FIXED_POINT_FAILURE = (
    'global-two-sided-moving-interface-fixed-point-refinement-fixed-point-failure'
  )
  PROMOTION_FAILURE = (
    'global-two-sided-moving-interface-fixed-point-refinement-promotion-failure'
  )


@dataclass(frozen=True, slots=True)
class MocGlobalTwoSidedMovingInterfaceFixedPointRefinementMeasurement:
  """Strict terminal fixed-point evidence below the production ceiling."""

  status: MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus
  cases: tuple[MocGlobalTwoSidedMovingInterfaceRefinementCase, ...]
  fixed_point_audits: tuple[MocEulerTwoSidedMovingInterfaceFixedPointAudit, ...]
  case_ids: tuple[str, ...] = ()
  resolution_sample_counts: tuple[int, ...] = ()
  source_closure_fingerprints: tuple[str | None, ...] = ()
  maximum_final_normal_updates_m: tuple[float, ...] = ()
  maximum_normal_momentum_residuals_Pa: tuple[float, ...] = ()
  case_audits_verified: bool = False
  strict_mode_verified: bool = False
  resolution_order_verified: bool = False
  closure_lineage_verified: bool = False
  terminal_fixed_point_verified: bool = False
  cross_case_verified: bool = False
  fidelity_flags_verified: bool = False
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  refinement_tolerance: float = 1.0e-8
  message: str = ''
  operator_id: str = (
    MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_FIXED_POINT_REFINEMENT_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus,
    ):
      raise TypeError('status must be a strict fixed-point refinement status')
    ####
    cases = tuple(self.cases)
    audits = tuple(self.fixed_point_audits)
    if len(cases) != len(audits):
      raise ValueError('cases and fixed_point_audits must have equal lengths')
    ####
    if any(
      not isinstance(case, MocGlobalTwoSidedMovingInterfaceRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed global moving-interface cases')
    ####
    if any(
      not isinstance(audit, MocEulerTwoSidedMovingInterfaceFixedPointAudit)
      for audit in audits
    ):
      raise TypeError(
        'fixed_point_audits must contain typed fixed-point audit values'
      )
    ####
    case_ids = tuple(
      str(case.case_id) for case in cases
    ) if not self.case_ids else tuple(str(value) for value in self.case_ids)
    resolutions = tuple(
      case.resolution_sample_count for case in cases
    ) if not self.resolution_sample_counts else tuple(
      self.resolution_sample_counts
    )
    fingerprints = tuple(
      case.result.source_closure_fingerprint for case in cases
    ) if not self.source_closure_fingerprints else tuple(
      self.source_closure_fingerprints
    )
    final_updates = tuple(
      float(audit.maximum_final_normal_update_m) for audit in audits
    ) if not self.maximum_final_normal_updates_m else tuple(
      float(value) for value in self.maximum_final_normal_updates_m
    )
    momentum = tuple(
      _maximum_terminal_momentum_residual(case.result)
      for case in cases
    ) if not self.maximum_normal_momentum_residuals_Pa else tuple(
      float(value) for value in self.maximum_normal_momentum_residuals_Pa
    )
    if not (
      len(cases)
      == len(case_ids)
      == len(resolutions)
      == len(fingerprints)
      == len(final_updates)
      == len(momentum)
    ):
      raise ValueError('strict refinement summaries must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in resolutions
    ):
      raise ValueError('resolution sample counts must be nonnegative integers')
    ####
    for name, values in (
      ('maximum_final_normal_updates_m', final_updates),
      ('maximum_normal_momentum_residuals_Pa', momentum),
    ):
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
    ####
    for name in (
      'case_audits_verified',
      'strict_mode_verified',
      'resolution_order_verified',
      'closure_lineage_verified',
      'terminal_fixed_point_verified',
      'cross_case_verified',
      'fidelity_flags_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.canonical_free_boundary_verified or self.canonical_euler_verified:
      raise ValueError('strict fixed-point refinement cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'strict fixed-point refinement must remain promotion-blocked'
      )
    ####
    tolerance = float(self.refinement_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('refinement_tolerance must be finite and positive')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'fixed_point_audits', audits)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'maximum_final_normal_updates_m', final_updates)
    object.__setattr__(self, 'maximum_normal_momentum_residuals_Pa', momentum)
    object.__setattr__(self, 'refinement_tolerance', tolerance)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in (
        MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus
        .CONVERGED_LOCAL_STRICT_FIXED_POINT,
        MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus
        .CONVERGED_CROSS_CASE_STRICT_FIXED_POINT,
      )
      and self.case_audits_verified
      and self.strict_mode_verified
      and self.resolution_order_verified
      and self.closure_lineage_verified
      and self.terminal_fixed_point_verified
      and self.fidelity_flags_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'resolution_sample_counts': self.resolution_sample_counts,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'maximum_final_normal_updates_m': self.maximum_final_normal_updates_m,
      'maximum_normal_momentum_residuals_Pa': (
        self.maximum_normal_momentum_residuals_Pa
      ),
      'case_audits_verified': self.case_audits_verified,
      'strict_mode_verified': self.strict_mode_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'closure_lineage_verified': self.closure_lineage_verified,
      'terminal_fixed_point_verified': self.terminal_fixed_point_verified,
      'cross_case_verified': self.cross_case_verified,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'refinement_tolerance': self.refinement_tolerance,
      'cases': tuple(case.result.as_report() for case in self.cases),
      'fixed_point_audits': tuple(
        audit.as_report() for audit in self.fixed_point_audits
      ),
      'message': self.message,
    }


def _maximum_terminal_momentum_residual(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
) -> float:
  moving = result.moving_result
  if moving is None or not moving.records:
    return 0.0
  response = moving.records[-1].response
  if response is None:
    return 0.0
  return max(response.normal_momentum_residuals_Pa, default=0.0)


def _failure(
  status: MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocGlobalTwoSidedMovingInterfaceRefinementCase] = (),
  fixed_point_audits: Sequence[MocEulerTwoSidedMovingInterfaceFixedPointAudit] = (),
  **kwargs: object,
) -> MocGlobalTwoSidedMovingInterfaceFixedPointRefinementMeasurement:
  case_values = tuple(cases)
  audit_values = tuple(fixed_point_audits)
  return MocGlobalTwoSidedMovingInterfaceFixedPointRefinementMeasurement(
    status=status,
    cases=case_values,
    fixed_point_audits=audit_values,
    case_audits_verified=bool(kwargs.get('case_audits_verified', False)),
    strict_mode_verified=bool(kwargs.get('strict_mode_verified', False)),
    resolution_order_verified=bool(
      kwargs.get('resolution_order_verified', False)
    ),
    closure_lineage_verified=bool(kwargs.get('closure_lineage_verified', False)),
    terminal_fixed_point_verified=bool(
      kwargs.get('terminal_fixed_point_verified', False)
    ),
    cross_case_verified=bool(kwargs.get('cross_case_verified', False)),
    fidelity_flags_verified=bool(kwargs.get('fidelity_flags_verified', False)),
    maximum_final_normal_updates_m=tuple(
      float(value) for value in kwargs.get('final_updates', ())
    ),
    maximum_normal_momentum_residuals_Pa=tuple(
      float(value) for value in kwargs.get('momentum', ())
    ),
    refinement_tolerance=float(kwargs.get('refinement_tolerance', 1.0e-8)),
    message=message,
  )


def measure_moc_global_two_sided_moving_interface_fixed_point_refinement(
  cases: Sequence[MocGlobalTwoSidedMovingInterfaceRefinementCase],
  *,
  refinement_tolerance: float = 1.0e-8,
) -> MocGlobalTwoSidedMovingInterfaceFixedPointRefinementMeasurement:
  """Audit strict terminal fixed-point evidence across a case ladder."""

  try:
    tolerance = float(refinement_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.INVALID_INPUT,
      'refinement_tolerance must be numeric',
    )
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    return _failure(
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.INVALID_INPUT,
      'refinement_tolerance must be finite and positive',
      refinement_tolerance=tolerance,
    )
  ####
  case_values = tuple(cases)
  if len(case_values) < 2:
    return _failure(
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.INVALID_INPUT,
      'strict fixed-point refinement requires at least two cases',
      refinement_tolerance=tolerance,
    )
  ####
  if any(
    not isinstance(case, MocGlobalTwoSidedMovingInterfaceRefinementCase)
    for case in case_values
  ):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.INVALID_INPUT,
      'cases must contain typed global moving-interface refinement cases',
      refinement_tolerance=tolerance,
    )
  ####
  try:
    audits = tuple(
      measure_moc_euler_two_sided_moving_interface_fixed_point(
        case.result.moving_result
      )
      for case in case_values
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.CASE_FAILURE,
      f'independent strict fixed-point audit raised: {error}',
      cases=case_values,
      refinement_tolerance=tolerance,
    )
  ####
  if any(case.result.moving_result is None for case in case_values):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.CASE_FAILURE,
      'every case must retain a moving-interface result',
      cases=case_values,
      fixed_point_audits=audits,
      refinement_tolerance=tolerance,
    )
  ####
  case_ids = tuple(case.case_id for case in case_values)
  fingerprints = tuple(
    case.result.source_closure_fingerprint for case in case_values
  )
  grouped_indices: dict[str, list[int]] = {}
  for index, case_id in enumerate(case_ids):
    grouped_indices.setdefault(case_id, []).append(index)
  ####
  case_audits_verified = bool(
    all(case.result.converged for case in case_values)
    and all(audit.request_verified and audit.record_count > 0 for audit in audits)
  )
  strict_mode_verified = bool(
    all(
      case.result.request is not None
      and case.result.request.require_conservative_flux_closure
      and case.result.request.require_terminal_fixed_point
      for case in case_values
    )
    and len({
      (
        case.result.request.require_interface_motion,
        case.result.request.downstream_probe_fraction,
        case.result.request.allow_stationary_equilibrium,
      )
      for case in case_values
      if case.result.request is not None
    }) == 1
  )
  resolution_order_verified = bool(
    all(
      len(indices) >= 2
      and all(
        case_values[right].resolution_sample_count
        > case_values[left].resolution_sample_count
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped_indices.values()
    )
  )
  closure_lineage_verified = bool(
    all(fingerprint for fingerprint in fingerprints)
    and all(
      len({fingerprints[index] for index in indices}) == len(indices)
      for indices in grouped_indices.values()
    )
  )
  terminal_fixed_point_verified = bool(
    strict_mode_verified
    and all(
      audit.fixed_point_verified
      and audit.local_consistency_verified
      and case.result.moving_result is not None
      and case.result.moving_result.terminal_fixed_point_verified
      and case.result.moving_result.conservative_flux_closure_verified
      for case, audit in zip(case_values, audits, strict=True)
    )
  )
  fidelity_flags_verified = bool(
    all(case.result.chain_promotion_blocked for case in case_values)
    and all(not case.result.production_claim_allowed for case in case_values)
    and all(not case.result.physical_closure_verified for case in case_values)
    and all(audit.chain_promotion_blocked for audit in audits)
    and all(not audit.production_claim_allowed for audit in audits)
  )
  cross_case_verified = bool(
    len(grouped_indices) >= 2
    and all(len(indices) >= 2 for indices in grouped_indices.values())
    and len({
      tuple(fingerprints[index] for index in indices)
      for indices in grouped_indices.values()
    }) == len(grouped_indices)
  )
  final_updates = tuple(
    audit.maximum_final_normal_update_m for audit in audits
  )
  momentum = tuple(
    _maximum_terminal_momentum_residual(case.result)
    for case in case_values
  )
  common = dict(
    cases=case_values,
    fixed_point_audits=audits,
    case_audits_verified=case_audits_verified,
    strict_mode_verified=strict_mode_verified,
    resolution_order_verified=resolution_order_verified,
    closure_lineage_verified=closure_lineage_verified,
    terminal_fixed_point_verified=terminal_fixed_point_verified,
    cross_case_verified=cross_case_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    final_updates=final_updates,
    momentum=momentum,
    refinement_tolerance=tolerance,
  )
  ####
  if not case_audits_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.CASE_FAILURE
    )
    message = 'one or more global cases failed its independent moving-interface audit'
  elif not strict_mode_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.MODE_FAILURE
    )
    message = (
      'every fixed-point refinement case must request strict conservative '
      'fluxes and a terminal fixed point with one consistent response mode'
    )
  elif not resolution_order_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus
      .RESOLUTION_ORDER_FAILURE
    )
    message = 'strict fixed-point cases are not ordered by increasing resolution'
  elif not closure_lineage_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.LINEAGE_FAILURE
    )
    message = 'strict fixed-point cases do not retain unique source closure lineage'
  elif not terminal_fixed_point_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.FIXED_POINT_FAILURE
    )
    message = (
      'one or more strict cases did not independently reach a terminal '
      'zero-update conservative fixed point'
    )
  elif not fidelity_flags_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus.PROMOTION_FAILURE
    )
    message = 'strict fixed-point evidence weakened its promotion boundary'
  elif cross_case_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus
      .CONVERGED_CROSS_CASE_STRICT_FIXED_POINT
    )
    message = (
      'independent strict terminal fixed-point evidence passed across distinct '
      'global case and resolution ladders; canonical closure and production '
      'gates remain open'
    )
  else:
    status = (
      MocGlobalTwoSidedMovingInterfaceFixedPointRefinementStatus
      .CONVERGED_LOCAL_STRICT_FIXED_POINT
    )
    message = (
      'independent strict terminal fixed-point evidence passed on an ordered '
      'global resolution ladder; cross-case and production gates remain open'
    )
  ####
  return _failure(status, message, **common)
