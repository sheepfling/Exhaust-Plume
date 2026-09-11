"""Cross-resolution entropy-advection audit for the two-sided Euler lane.

The variable-entropy lineage audit proves that the shock loss is retained at
the physical-field perimeter and its characteristic source nodes.  This
operator adds the next independent check: it measures normalized
``u · grad(log(p0))`` over the retained physical cells and requires the
residual to remain bounded and decrease across fresh resolutions.

The result is still a research-lane acceptance.  It does not solve the
reflected mixed-regime free boundary, fit a production shock-cell length, or
authorize downstream product claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.validation.moc_euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationAudit,
  measure_moc_euler_two_sided_field_iteration,
)
from exhaust_plume.validation.moc_euler_two_sided_field_refinement import (
  MocEulerTwoSidedFieldIterationRefinementCase,
)
from exhaust_plume.validation.moc_euler_variable_entropy_lineage import (
  MocEulerVariableEntropyLineageAudit,
  measure_moc_euler_variable_entropy_lineage,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_ENTROPY_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedEntropyRefinementAuditStatus',
  'MocEulerTwoSidedEntropyRefinementMeasurement',
  'measure_moc_euler_two_sided_entropy_refinement',
)


MOC_EULER_TWO_SIDED_ENTROPY_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-entropy-refinement-audit'
)


class MocEulerTwoSidedEntropyRefinementAuditStatus(str, Enum):
  """Typed outcomes for the cross-resolution entropy audit."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged_two_sided_entropy_transport_local_refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'two_sided_entropy_refinement_case_failure'
  RESOLUTION_ORDER_FAILURE = 'two_sided_entropy_refinement_resolution_order_failure'
  RESIDUAL_FAILURE = 'two_sided_entropy_refinement_residual_failure'
  FLAG_FAILURE = 'two_sided_entropy_refinement_flag_failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedEntropyRefinementMeasurement:
  """Independent entropy-advection evidence below canonical promotion."""

  status: MocEulerTwoSidedEntropyRefinementAuditStatus
  cases: tuple[MocEulerTwoSidedFieldIterationRefinementCase, ...]
  iteration_audits: tuple[MocEulerTwoSidedFieldIterationAudit, ...]
  entropy_audits: tuple[MocEulerVariableEntropyLineageAudit, ...]
  resolution_sample_counts: tuple[int, ...]
  maximum_entropy_advection_residuals: tuple[float, ...]
  case_audits_verified: bool
  resolution_order_verified: bool
  residuals_finite: bool
  residuals_verified: bool
  residual_nonincreasing_verified: bool
  residual_reduction_verified: bool
  variable_entropy_lineage_verified: bool
  entropy_transport_convergence_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  refinement_tolerance: float = 1.0e-8
  entropy_advection_tolerance: float = 1.0e-3
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_ENTROPY_REFINEMENT_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedEntropyRefinementAuditStatus):
      raise TypeError('status must be a two-sided entropy refinement status')
    ####
    cases = tuple(self.cases)
    iteration_audits = tuple(self.iteration_audits)
    entropy_audits = tuple(self.entropy_audits)
    if not (
      len(cases) == len(iteration_audits) == len(entropy_audits)
    ):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(case, MocEulerTwoSidedFieldIterationRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed two-sided refinement cases')
    ####
    if any(
      not isinstance(audit, MocEulerTwoSidedFieldIterationAudit)
      for audit in iteration_audits
    ):
      raise TypeError('iteration_audits must contain typed iteration audits')
    ####
    if any(
      not isinstance(audit, MocEulerVariableEntropyLineageAudit)
      for audit in entropy_audits
    ):
      raise TypeError('entropy_audits must contain typed entropy audits')
    ####
    resolutions = tuple(self.resolution_sample_counts)
    residuals = tuple(
      float(value) for value in self.maximum_entropy_advection_residuals
    )
    if len(cases) != len(resolutions) or len(cases) != len(residuals):
      raise ValueError('resolution summaries must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in resolutions
    ):
      raise ValueError('resolution sample counts must be nonnegative integers')
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'maximum_entropy_advection_residuals must be finite and nonnegative'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'iteration_audits', iteration_audits)
    object.__setattr__(self, 'entropy_audits', entropy_audits)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(
      self,
      'maximum_entropy_advection_residuals',
      residuals,
    )
    for name in (
      'case_audits_verified',
      'resolution_order_verified',
      'residuals_finite',
      'residuals_verified',
      'residual_nonincreasing_verified',
      'residual_reduction_verified',
      'variable_entropy_lineage_verified',
      'entropy_transport_convergence_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in ('refinement_tolerance', 'entropy_advection_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    ####
    if self.physical_closure_verified:
      raise ValueError('entropy refinement cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError('entropy refinement must block promotion')
    if self.production_claim_allowed:
      raise ValueError('entropy refinement cannot claim production validity')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedEntropyRefinementAuditStatus.CONVERGED_LOCAL_REFINEMENT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.case_audits_verified
      and self.resolution_order_verified
      and self.residuals_finite
      and self.residuals_verified
      and self.residual_nonincreasing_verified
      and self.residual_reduction_verified
      and self.variable_entropy_lineage_verified
      and self.entropy_transport_convergence_verified
      and self.fidelity_flags_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolution_sample_counts': list(self.resolution_sample_counts),
      'maximum_entropy_advection_residuals': list(
        self.maximum_entropy_advection_residuals
      ),
      'case_audits_verified': self.case_audits_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'residuals_finite': self.residuals_finite,
      'residuals_verified': self.residuals_verified,
      'residual_nonincreasing_verified': self.residual_nonincreasing_verified,
      'residual_reduction_verified': self.residual_reduction_verified,
      'variable_entropy_lineage_verified': self.variable_entropy_lineage_verified,
      'entropy_transport_convergence_verified': self.entropy_transport_convergence_verified,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'iteration_audits': [audit.as_report() for audit in self.iteration_audits],
      'entropy_audits': [audit.as_report() for audit in self.entropy_audits],
      'refinement_tolerance': self.refinement_tolerance,
      'entropy_advection_tolerance': self.entropy_advection_tolerance,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedEntropyRefinementAuditStatus,
  message: str,
  *,
  cases: Sequence[MocEulerTwoSidedFieldIterationRefinementCase] = (),
  iteration_audits: Sequence[MocEulerTwoSidedFieldIterationAudit] = (),
  entropy_audits: Sequence[MocEulerVariableEntropyLineageAudit] = (),
  resolutions: Sequence[int] = (),
  residuals: Sequence[float] = (),
  case_audits_verified: bool = False,
  resolution_order_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  residual_nonincreasing_verified: bool = False,
  residual_reduction_verified: bool = False,
  variable_entropy_lineage_verified: bool = False,
  entropy_transport_convergence_verified: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  fidelity_flags_verified: bool = False,
  refinement_tolerance: float = 1.0e-8,
  entropy_advection_tolerance: float = 1.0e-3,
) -> MocEulerTwoSidedEntropyRefinementMeasurement:
  case_values = tuple(cases)
  iteration_values = tuple(iteration_audits)
  entropy_values = tuple(entropy_audits)
  resolution_values = tuple(resolutions)
  residual_values = tuple(residuals)
  aligned_count = min(
    len(case_values),
    len(iteration_values),
    len(entropy_values),
    len(resolution_values),
    len(residual_values),
  )
  return MocEulerTwoSidedEntropyRefinementMeasurement(
    status=status,
    cases=case_values[:aligned_count],
    iteration_audits=iteration_values[:aligned_count],
    entropy_audits=entropy_values[:aligned_count],
    resolution_sample_counts=resolution_values[:aligned_count],
    maximum_entropy_advection_residuals=residual_values[:aligned_count],
    case_audits_verified=case_audits_verified,
    resolution_order_verified=resolution_order_verified,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    residual_reduction_verified=residual_reduction_verified,
    variable_entropy_lineage_verified=variable_entropy_lineage_verified,
    entropy_transport_convergence_verified=entropy_transport_convergence_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    fidelity_flags_verified=fidelity_flags_verified,
    refinement_tolerance=refinement_tolerance,
    entropy_advection_tolerance=entropy_advection_tolerance,
    message=message,
  )


def measure_moc_euler_two_sided_entropy_refinement(
  cases: Sequence[MocEulerTwoSidedFieldIterationRefinementCase],
  *,
  refinement_tolerance: float = 1.0e-8,
  entropy_advection_tolerance: float = 1.0e-3,
) -> MocEulerTwoSidedEntropyRefinementMeasurement:
  """Measure entropy-advection refinement on independently solved fields."""

  try:
    items = tuple(cases)
  except TypeError:
    return _failure(
      MocEulerTwoSidedEntropyRefinementAuditStatus.INVALID_INPUT,
      'cases must be iterable',
    )
  ####
  if len(items) < 2:
    return _failure(
      MocEulerTwoSidedEntropyRefinementAuditStatus.INVALID_INPUT,
      'at least two resolution cases are required',
    )
  ####
  if any(
    not isinstance(case, MocEulerTwoSidedFieldIterationRefinementCase)
    for case in items
  ):
    return _failure(
      MocEulerTwoSidedEntropyRefinementAuditStatus.INVALID_INPUT,
      'cases must contain typed two-sided field refinement cases',
    )
  ####
  refinement_bound = float(refinement_tolerance)
  entropy_bound = float(entropy_advection_tolerance)
  if (
    not isfinite(refinement_bound)
    or refinement_bound < 0.0
    or not isfinite(entropy_bound)
    or entropy_bound <= 0.0
  ):
    raise ValueError(
      'refinement_tolerance must be finite and nonnegative and '
      'entropy_advection_tolerance must be finite and positive'
    )
  ####
  resolutions = tuple(case.resolution_sample_count for case in items)
  resolution_order = bool(
    all(right > left for left, right in zip(resolutions, resolutions[1:]))
  )
  if not resolution_order:
    return _failure(
      MocEulerTwoSidedEntropyRefinementAuditStatus.RESOLUTION_ORDER_FAILURE,
      'resolution sample counts must be strictly increasing',
      cases=items,
      resolutions=resolutions,
      resolution_order_verified=False,
      refinement_tolerance=refinement_bound,
      entropy_advection_tolerance=entropy_bound,
    )
  ####
  iteration_audits: list[MocEulerTwoSidedFieldIterationAudit] = []
  entropy_audits: list[MocEulerVariableEntropyLineageAudit] = []
  residuals: list[float] = []
  case_audits_verified = True
  variable_entropy_lineage_verified = True
  for case in items:
    try:
      iteration_audit = measure_moc_euler_two_sided_field_iteration(
        case.result
      )
      field = case.result.final_physical_field
      entropy_audit = (
        None
        if field is None
        else measure_moc_euler_variable_entropy_lineage(
          field,
          entropy_advection_tolerance=entropy_bound,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerTwoSidedEntropyRefinementAuditStatus.CASE_FAILURE,
        f'independent entropy refinement audit raised: {error}',
        cases=items,
        iteration_audits=iteration_audits,
        entropy_audits=entropy_audits,
        resolutions=resolutions,
        residuals=residuals,
        refinement_tolerance=refinement_bound,
        entropy_advection_tolerance=entropy_bound,
      )
    ####
    if entropy_audit is None:
      case_audits_verified = False
      break
    ####
    iteration_audits.append(iteration_audit)
    entropy_audits.append(entropy_audit)
    variable_entropy_lineage_verified = (
      variable_entropy_lineage_verified
      and entropy_audit.variable_entropy_lineage_verified
    )
    if not (
      iteration_audit.local_consistency_verified
      and entropy_audit.local_consistency_verified
    ):
      case_audits_verified = False
      break
    ####
    maximum_residual = entropy_audit.maximum_entropy_advection_residual
    if maximum_residual is None:
      case_audits_verified = False
      break
    residuals.append(maximum_residual)
  ####
  if not case_audits_verified or len(entropy_audits) != len(items):
    return _failure(
      MocEulerTwoSidedEntropyRefinementAuditStatus.CASE_FAILURE,
      'one or more two-sided cases failed independent entropy-lineage gates',
      cases=items,
      iteration_audits=iteration_audits,
      entropy_audits=entropy_audits,
      resolutions=resolutions,
      residuals=residuals,
      case_audits_verified=False,
      resolution_order_verified=True,
      refinement_tolerance=refinement_bound,
      entropy_advection_tolerance=entropy_bound,
    )
  ####
  residuals_finite = bool(
    residuals and all(isfinite(value) and value >= 0.0 for value in residuals)
  )
  residuals_verified = bool(
    residuals_finite and all(value <= entropy_bound for value in residuals)
  )
  residual_nonincreasing = bool(
    all(
      right <= left + refinement_bound * max(1.0, abs(left))
      for left, right in zip(residuals, residuals[1:])
    )
  )
  residual_reduction = bool(len(residuals) >= 2 and residuals[-1] < residuals[0])
  entropy_transport_convergence = bool(
    residuals_finite
    and residuals_verified
    and residual_nonincreasing
    and residual_reduction
  )
  flags_verified = bool(
    all(
      case.result.chain_promotion_blocked
      and not case.result.production_claim_allowed
      and not case.result.canonical_free_boundary_verified
      and not case.result.canonical_euler_verified
      for case in items
    )
  )
  convergence = bool(
    case_audits_verified
    and resolution_order
    and variable_entropy_lineage_verified
    and entropy_transport_convergence
    and flags_verified
  )
  if not residuals_finite or not residuals_verified or not residual_nonincreasing:
    status = MocEulerTwoSidedEntropyRefinementAuditStatus.RESIDUAL_FAILURE
    message = 'entropy-advection residuals failed the cross-resolution research gate'
  elif not flags_verified:
    status = MocEulerTwoSidedEntropyRefinementAuditStatus.FLAG_FAILURE
    message = 'entropy refinement cases weakened research or promotion flags'
  else:
    status = MocEulerTwoSidedEntropyRefinementAuditStatus.CONVERGED_LOCAL_REFINEMENT
    message = (
      'independent entropy-advection refinement passed variable-lineage, '
      'bounded-residual, and decreasing-residual gates; canonical free-boundary '
      'closure and production shock-cell promotion remain pending'
      if convergence
      else 'independent entropy-advection fields are locally auditable, but '
      'strict residual reduction remains required for convergence'
    )
  ####
  return _failure(
    status,
    message,
    cases=items,
    iteration_audits=iteration_audits,
    entropy_audits=entropy_audits,
    resolutions=resolutions,
    residuals=residuals,
    case_audits_verified=case_audits_verified,
    resolution_order_verified=resolution_order,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing,
    residual_reduction_verified=residual_reduction,
    variable_entropy_lineage_verified=variable_entropy_lineage_verified,
    entropy_transport_convergence_verified=entropy_transport_convergence,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_flags_verified=flags_verified,
    refinement_tolerance=refinement_bound,
    entropy_advection_tolerance=entropy_bound,
  )
