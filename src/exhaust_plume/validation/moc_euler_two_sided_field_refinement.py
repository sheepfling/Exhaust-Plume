"""Cross-resolution audit for the two-sided exact-Euler research lane.

This operator compares independently solved two-sided field iterations at
declared companion-frontier resolutions.  It accepts only exact case objects,
re-audits every case, and keeps entropy admission and production promotion as
separate gates.  A decreasing conservative residual trend is useful evidence,
but it is not a canonical reflected-field or shock-cell claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
)
from exhaust_plume.validation.moc_euler import (
  MocEulerAmbientPhysicalFieldAudit,
  measure_moc_euler_ambient_physical_field,
)
from exhaust_plume.validation.moc_euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationAudit,
  measure_moc_euler_two_sided_field_iteration,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_FIELD_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedFieldIterationRefinementCase',
  'MocEulerTwoSidedFieldRefinementAuditStatus',
  'MocEulerTwoSidedFieldRefinementMeasurement',
  'measure_moc_euler_two_sided_field_refinement',
)


MOC_EULER_TWO_SIDED_FIELD_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-field-refinement-audit'
)


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedFieldIterationRefinementCase:
  """One independently solved two-sided field at a declared resolution."""

  resolution_sample_count: int
  result: MocEulerTwoSidedFieldIterationResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution_sample_count, bool)
      or not isinstance(self.resolution_sample_count, int)
      or self.resolution_sample_count < 3
    ):
      raise ValueError('resolution_sample_count must be an integer >= 3')
    ####
    if not isinstance(self.result, MocEulerTwoSidedFieldIterationResult):
      raise TypeError(
        'result must be a MocEulerTwoSidedFieldIterationResult'
      )
    ####
    companion = self.result.initial_companion_field
    if companion is not None and len(companion.downstream_handoff) != self.resolution_sample_count:
      raise ValueError(
        'resolution_sample_count must match the exact companion-frontier '
        'sample count retained by the result'
      )
    ####
  ####
####


class MocEulerTwoSidedFieldRefinementAuditStatus(str, Enum):
  """Typed outcomes for the independent cross-resolution audit."""

  CONVERGED_LOCAL_REFINEMENT = 'converged_two_sided_field_local_refinement'
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'two_sided_field_refinement_case_failure'
  RESOLUTION_ORDER_FAILURE = 'two_sided_field_refinement_resolution_order_failure'
  CELL_GROWTH_FAILURE = 'two_sided_field_refinement_cell_growth_failure'
  RESIDUAL_FAILURE = 'two_sided_field_refinement_residual_failure'
  FLAG_FAILURE = 'two_sided_field_refinement_flag_failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedFieldRefinementMeasurement:
  """Independent cross-case evidence below canonical promotion."""

  status: MocEulerTwoSidedFieldRefinementAuditStatus
  cases: tuple[MocEulerTwoSidedFieldIterationRefinementCase, ...]
  iteration_audits: tuple[MocEulerTwoSidedFieldIterationAudit, ...]
  physical_field_audits: tuple[MocEulerAmbientPhysicalFieldAudit, ...]
  resolution_sample_counts: tuple[int, ...]
  physical_field_cell_counts: tuple[int, ...]
  maximum_cell_euler_residuals: tuple[float, ...]
  case_audits_verified: bool
  resolution_order_verified: bool
  cell_growth_verified: bool
  residuals_finite: bool
  residuals_verified: bool
  residual_nonincreasing_verified: bool
  residual_reduction_verified: bool
  entropy_lineage_verified: bool
  local_refinement_verified: bool
  refinement_convergence_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  refinement_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_FIELD_REFINEMENT_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedFieldRefinementAuditStatus):
      raise TypeError('status must be a two-sided refinement audit status')
    ####
    cases = tuple(self.cases)
    iteration_audits = tuple(self.iteration_audits)
    physical_audits = tuple(self.physical_field_audits)
    if len(cases) != len(iteration_audits) or len(cases) != len(physical_audits):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(case, MocEulerTwoSidedFieldIterationRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed refinement cases')
    ####
    if any(
      not isinstance(audit, MocEulerTwoSidedFieldIterationAudit)
      for audit in iteration_audits
    ):
      raise TypeError('iteration_audits must contain typed iteration audits')
    ####
    if any(
      not isinstance(audit, MocEulerAmbientPhysicalFieldAudit)
      for audit in physical_audits
    ):
      raise TypeError('physical_field_audits must contain typed field audits')
    ####
    resolutions = tuple(self.resolution_sample_counts)
    cell_counts = tuple(self.physical_field_cell_counts)
    residuals = tuple(float(value) for value in self.maximum_cell_euler_residuals)
    if not (
      len(cases)
      == len(resolutions)
      == len(cell_counts)
      == len(residuals)
    ):
      raise ValueError('resolution summaries must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in (*resolutions, *cell_counts)
    ):
      raise ValueError('resolution and cell counts must be nonnegative integers')
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('residuals must be finite and nonnegative')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'iteration_audits', iteration_audits)
    object.__setattr__(self, 'physical_field_audits', physical_audits)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'physical_field_cell_counts', cell_counts)
    object.__setattr__(self, 'maximum_cell_euler_residuals', residuals)
    for name in (
      'case_audits_verified',
      'resolution_order_verified',
      'cell_growth_verified',
      'residuals_finite',
      'residuals_verified',
      'residual_nonincreasing_verified',
      'residual_reduction_verified',
      'entropy_lineage_verified',
      'local_refinement_verified',
      'refinement_convergence_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in ('refinement_tolerance', 'cell_residual_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.physical_closure_verified:
      raise ValueError('two-sided research refinement cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('two-sided research refinement must block promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('two-sided research refinement cannot claim production validity')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedFieldRefinementAuditStatus.CONVERGED_LOCAL_REFINEMENT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.case_audits_verified
      and self.resolution_order_verified
      and self.cell_growth_verified
      and self.residuals_finite
      and self.residuals_verified
      and self.residual_nonincreasing_verified
      and self.local_refinement_verified
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
      'physical_field_cell_counts': list(self.physical_field_cell_counts),
      'maximum_cell_euler_residuals': list(self.maximum_cell_euler_residuals),
      'case_audits_verified': self.case_audits_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'cell_growth_verified': self.cell_growth_verified,
      'residuals_finite': self.residuals_finite,
      'residuals_verified': self.residuals_verified,
      'residual_nonincreasing_verified': self.residual_nonincreasing_verified,
      'residual_reduction_verified': self.residual_reduction_verified,
      'entropy_lineage_verified': self.entropy_lineage_verified,
      'local_refinement_verified': self.local_refinement_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'iteration_audits': [audit.as_report() for audit in self.iteration_audits],
      'physical_field_audits': [
        audit.as_report() for audit in self.physical_field_audits
      ],
      'refinement_tolerance': self.refinement_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedFieldRefinementAuditStatus,
  message: str,
  *,
  cases: Sequence[MocEulerTwoSidedFieldIterationRefinementCase] = (),
  iteration_audits: Sequence[MocEulerTwoSidedFieldIterationAudit] = (),
  physical_field_audits: Sequence[MocEulerAmbientPhysicalFieldAudit] = (),
  resolutions: Sequence[int] = (),
  cell_counts: Sequence[int] = (),
  residuals: Sequence[float] = (),
  case_audits_verified: bool = False,
  resolution_order_verified: bool = False,
  cell_growth_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  residual_nonincreasing_verified: bool = False,
  residual_reduction_verified: bool = False,
  entropy_lineage_verified: bool = False,
  local_refinement_verified: bool = False,
  refinement_convergence_verified: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  fidelity_flags_verified: bool = False,
  refinement_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerTwoSidedFieldRefinementMeasurement:
  case_values = tuple(cases)
  iteration_values = tuple(iteration_audits)
  physical_values = tuple(physical_field_audits)
  resolution_values = tuple(resolutions)
  cell_values = tuple(cell_counts)
  residual_values = tuple(residuals)
  aligned_count = min(
    len(case_values),
    len(iteration_values),
    len(physical_values),
    len(resolution_values),
    len(cell_values),
    len(residual_values),
  )
  return MocEulerTwoSidedFieldRefinementMeasurement(
    status=status,
    cases=case_values[:aligned_count],
    iteration_audits=iteration_values[:aligned_count],
    physical_field_audits=physical_values[:aligned_count],
    resolution_sample_counts=resolution_values[:aligned_count],
    physical_field_cell_counts=cell_values[:aligned_count],
    maximum_cell_euler_residuals=residual_values[:aligned_count],
    case_audits_verified=case_audits_verified,
    resolution_order_verified=resolution_order_verified,
    cell_growth_verified=cell_growth_verified,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    residual_reduction_verified=residual_reduction_verified,
    entropy_lineage_verified=entropy_lineage_verified,
    local_refinement_verified=local_refinement_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    fidelity_flags_verified=fidelity_flags_verified,
    refinement_tolerance=refinement_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def measure_moc_euler_two_sided_field_refinement(
  cases: Sequence[MocEulerTwoSidedFieldIterationRefinementCase],
  *,
  refinement_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerTwoSidedFieldRefinementMeasurement:
  """Recompute cross-resolution physical-field refinement evidence."""

  try:
    items = tuple(cases)
  except TypeError:
    return _failure(
      MocEulerTwoSidedFieldRefinementAuditStatus.INVALID_INPUT,
      'cases must be iterable',
    )
  ####
  if len(items) < 2:
    return _failure(
      MocEulerTwoSidedFieldRefinementAuditStatus.INVALID_INPUT,
      'at least two resolution cases are required',
    )
  ####
  if any(
    not isinstance(case, MocEulerTwoSidedFieldIterationRefinementCase)
    for case in items
  ):
    return _failure(
      MocEulerTwoSidedFieldRefinementAuditStatus.INVALID_INPUT,
      'cases must contain typed two-sided field refinement cases',
    )
  ####
  refinement_bound = float(refinement_tolerance)
  cell_tolerance = float(cell_residual_tolerance)
  if (
    not isfinite(refinement_bound)
    or refinement_bound < 0.0
    or not isfinite(cell_tolerance)
    or cell_tolerance <= 0.0
  ):
    raise ValueError(
      'refinement_tolerance must be finite and nonnegative and '
      'cell_residual_tolerance must be finite and positive'
    )
  ####
  resolutions = tuple(case.resolution_sample_count for case in items)
  resolution_order = bool(
    all(right > left for left, right in zip(resolutions, resolutions[1:]))
  )
  if not resolution_order:
    return _failure(
      MocEulerTwoSidedFieldRefinementAuditStatus.RESOLUTION_ORDER_FAILURE,
      'resolution sample counts must be strictly increasing',
      cases=items,
      resolutions=resolutions,
      resolution_order_verified=False,
      refinement_tolerance=refinement_bound,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  iteration_audits: list[MocEulerTwoSidedFieldIterationAudit] = []
  physical_audits: list[MocEulerAmbientPhysicalFieldAudit] = []
  cell_counts: list[int] = []
  residuals: list[float] = []
  entropy_lineage = True
  case_audits_verified = True
  for case in items:
    try:
      iteration_audit = measure_moc_euler_two_sided_field_iteration(case.result)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerTwoSidedFieldRefinementAuditStatus.CASE_FAILURE,
        f'independent two-sided iteration audit raised: {error}',
        cases=items,
        iteration_audits=iteration_audits,
        physical_field_audits=physical_audits,
        resolutions=resolutions,
        cell_counts=cell_counts,
        residuals=residuals,
        refinement_tolerance=refinement_bound,
        cell_residual_tolerance=cell_tolerance,
      )
    ####
    iteration_audits.append(iteration_audit)
    entropy_lineage = entropy_lineage and iteration_audit.entropy_lineage_verified
    if not iteration_audit.local_consistency_verified:
      case_audits_verified = False
      break
    ####
    field = case.result.final_physical_field
    if field is None or field.field is None:
      case_audits_verified = False
      break
    ####
    try:
      physical_audit = measure_moc_euler_ambient_physical_field(
        field,
        cell_residual_tolerance=cell_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      case_audits_verified = False
      break
    ####
    physical_audits.append(physical_audit)
    if not (
      physical_audit.physical_field_verified
      and physical_audit.physical_closure_verified
      and physical_audit.cell_euler_residuals_verified
      and physical_audit.chain_promotion_blocked
      and not physical_audit.production_claim_allowed
    ):
      case_audits_verified = False
      break
    ####
    cell_counts.append(len(field.field.cells))
    residuals.append(physical_audit.maximum_cell_euler_residual or 0.0)
  ####
  if not case_audits_verified or len(physical_audits) != len(items):
    return _failure(
      MocEulerTwoSidedFieldRefinementAuditStatus.CASE_FAILURE,
      'one or more two-sided resolution cases failed independent local gates',
      cases=items,
      iteration_audits=iteration_audits,
      physical_field_audits=physical_audits,
      resolutions=resolutions,
      cell_counts=cell_counts,
      residuals=residuals,
      case_audits_verified=False,
      resolution_order_verified=True,
      refinement_tolerance=refinement_bound,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  cell_growth = bool(
    all(right > left for left, right in zip(cell_counts, cell_counts[1:]))
  )
  residuals_finite = bool(
    residuals and all(isfinite(value) and value >= 0.0 for value in residuals)
  )
  residuals_verified = bool(
    residuals_finite and all(value <= cell_tolerance for value in residuals)
  )
  residual_nonincreasing = bool(
    all(
      right <= left + refinement_bound * max(1.0, abs(left))
      for left, right in zip(residuals, residuals[1:])
    )
  )
  residual_reduction = bool(len(residuals) >= 2 and residuals[-1] < residuals[0])
  local_refinement = bool(
    case_audits_verified
    and resolution_order
    and cell_growth
    and residuals_finite
    and residuals_verified
    and residual_nonincreasing
    and residual_reduction
  )
  refinement_convergence = bool(local_refinement and entropy_lineage)
  flags_verified = bool(
    all(
      case.result.chain_promotion_blocked
      and not case.result.production_claim_allowed
      and not case.result.canonical_free_boundary_verified
      and not case.result.canonical_euler_verified
      for case in items
    )
  )
  if not cell_growth:
    status = MocEulerTwoSidedFieldRefinementAuditStatus.CELL_GROWTH_FAILURE
    message = 'physical field cell counts did not increase across resolutions'
  elif not residuals_finite or not residuals_verified or not residual_nonincreasing:
    status = MocEulerTwoSidedFieldRefinementAuditStatus.RESIDUAL_FAILURE
    message = 'physical-field residuals failed the cross-resolution refinement gate'
  elif not flags_verified:
    status = MocEulerTwoSidedFieldRefinementAuditStatus.FLAG_FAILURE
    message = 'two-sided resolution cases weakened research or promotion flags'
  else:
    status = MocEulerTwoSidedFieldRefinementAuditStatus.CONVERGED_LOCAL_REFINEMENT
    message = (
      'independent two-sided physical-field refinement passed cell-growth and '
      'residual-reduction gates; entropy lineage, canonical closure, and '
      'production shock-cell promotion remain pending'
      if not entropy_lineage
      else 'independent two-sided physical-field refinement passed local gates; '
      'canonical closure and production shock-cell promotion remain pending'
    )
  ####
  return _failure(
    status,
    message,
    cases=items,
    iteration_audits=iteration_audits,
    physical_field_audits=physical_audits,
    resolutions=resolutions,
    cell_counts=cell_counts,
    residuals=residuals,
    case_audits_verified=case_audits_verified,
    resolution_order_verified=resolution_order,
    cell_growth_verified=cell_growth,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing,
    residual_reduction_verified=residual_reduction,
    entropy_lineage_verified=entropy_lineage,
    local_refinement_verified=local_refinement,
    refinement_convergence_verified=refinement_convergence,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_flags_verified=flags_verified,
    refinement_tolerance=refinement_bound,
    cell_residual_tolerance=cell_tolerance,
  )
####
