"""Independent refinement evidence for the exact ambient-closed MOC field.

The exact ambient-closed field can contain a valid connected characteristic
mesh while its reflected first wedge remains a single finite cell.  More
samples on the shock and ambient traces do not, by themselves, subdivide
that wedge.  This operator records that distinction explicitly and keeps the
result below the continued shock-cell chain promotion boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)
from exhaust_plume.validation.moc_euler import (
  MocEulerAmbientPhysicalFieldAudit,
  measure_moc_euler_ambient_physical_field,
  measure_moc_physical_field_euler_audit,
)

__all__ = (
  'MOC_EULER_AMBIENT_PHYSICAL_FIELD_REFINEMENT_OPERATOR_ID',
  'MocEulerAmbientPhysicalFieldRefinementStatus',
  'MocEulerAmbientPhysicalFieldRefinementCase',
  'MocEulerAmbientPhysicalFieldRefinementMeasurement',
  'measure_moc_euler_ambient_physical_field_refinement',
)


MOC_EULER_AMBIENT_PHYSICAL_FIELD_REFINEMENT_OPERATOR_ID = (
  'op.moc.euler-ambient-physical-field-refinement'
)


class MocEulerAmbientPhysicalFieldRefinementStatus(str, Enum):
  """Outcome of the independent ambient-closed field refinement audit."""

  CONVERGED = 'converged_euler_ambient_physical_field_refinement'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'euler_ambient_physical_field_refinement_resolution_failure'
  CASE_FAILURE = 'euler_ambient_physical_field_refinement_case_failure'
  FIRST_WEDGE_REFINEMENT_FAILURE = (
    'euler_ambient_physical_field_refinement_first_wedge_failure'
  )
  CELL_RESIDUAL_FAILURE = (
    'euler_ambient_physical_field_refinement_cell_residual_failure'
  )
  CONSISTENCY_FAILURE = (
    'euler_ambient_physical_field_refinement_consistency_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientPhysicalFieldRefinementCase:
  """One exact ambient-closed result at a declared boundary resolution."""

  resolution: int
  result: MocEulerAmbientPhysicalFieldResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 1
    ):
      raise ValueError('resolution must be a positive integer')
    if not isinstance(self.result, MocEulerAmbientPhysicalFieldResult):
      raise TypeError(
        'result must be a MocEulerAmbientPhysicalFieldResult'
      )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientPhysicalFieldRefinementMeasurement:
  """Independent refinement and topology evidence for a physical-field lane.

  A passing result means that all supplied cases pass their local field and
  cell-residual gates and that the first reflected wedge is actually
  subdivided.  It still does not authorize a production provider or a
  continued physical chain; canonical reflected free-boundary and external
  validation remain separate gates.
  """

  status: MocEulerAmbientPhysicalFieldRefinementStatus
  cases: tuple[MocEulerAmbientPhysicalFieldRefinementCase, ...] = ()
  audits: tuple[MocEulerAmbientPhysicalFieldAudit, ...] = ()
  resolutions: tuple[int, ...] = ()
  field_cell_counts: tuple[int, ...] = ()
  first_wedge_cell_counts: tuple[int, ...] = ()
  maximum_cell_euler_residuals: tuple[float, ...] = ()
  first_wedge_euler_residuals: tuple[float, ...] = ()
  non_first_wedge_maximum_residuals: tuple[float, ...] = ()
  resolution_order_verified: bool = False
  candidate_fields_verified: bool = False
  shock_jumps_verified: bool = False
  cell_residuals_finite: bool = False
  first_wedge_subdivision_verified: bool = False
  non_first_wedge_refinement_verified: bool = False
  cell_residuals_verified: bool = False
  refinement_convergence_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_PHYSICAL_FIELD_REFINEMENT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientPhysicalFieldRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientPhysicalFieldRefinementStatus'
      )
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    if any(
      not isinstance(case, MocEulerAmbientPhysicalFieldRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain '
        'MocEulerAmbientPhysicalFieldRefinementCase values'
      )
    if any(
      not isinstance(audit, MocEulerAmbientPhysicalFieldAudit)
      for audit in audits
    ):
      raise TypeError(
        'audits must contain MocEulerAmbientPhysicalFieldAudit values'
      )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    derived_resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != derived_resolutions:
      raise ValueError('resolutions must match the supplied case resolutions')
    object.__setattr__(self, 'resolutions', derived_resolutions)
    for name in (
      'field_cell_counts',
      'first_wedge_cell_counts',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
      ):
        raise ValueError(f'{name} must contain nonnegative integers')
      object.__setattr__(self, name, values)
    for name in (
      'maximum_cell_euler_residuals',
      'first_wedge_euler_residuals',
      'non_first_wedge_maximum_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'resolution_order_verified',
      'candidate_fields_verified',
      'shock_jumps_verified',
      'cell_residuals_finite',
      'first_wedge_subdivision_verified',
      'non_first_wedge_refinement_verified',
      'cell_residuals_verified',
      'refinement_convergence_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    claim_status = str(self.claim_status)
    if not claim_status:
      raise ValueError('claim_status must be a non-empty string')
    object.__setattr__(self, 'claim_status', claim_status)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether all independent refinement and local field gates passed."""

    return self.status is MocEulerAmbientPhysicalFieldRefinementStatus.CONVERGED

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the measurement passed without weakening its claim ceiling."""

    return bool(
      self.converged
      and self.resolution_order_verified
      and self.candidate_fields_verified
      and self.shock_jumps_verified
      and self.cell_residuals_finite
      and self.first_wedge_subdivision_verified
      and self.non_first_wedge_refinement_verified
      and self.cell_residuals_verified
      and self.refinement_convergence_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': list(self.resolutions),
      'field_cell_counts': list(self.field_cell_counts),
      'first_wedge_cell_counts': list(self.first_wedge_cell_counts),
      'maximum_cell_euler_residuals': list(self.maximum_cell_euler_residuals),
      'first_wedge_euler_residuals': list(self.first_wedge_euler_residuals),
      'non_first_wedge_maximum_residuals': list(
        self.non_first_wedge_maximum_residuals
      ),
      'audits': [audit.as_report() for audit in self.audits],
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'candidate_fields_verified': self.candidate_fields_verified,
        'shock_jumps_verified': self.shock_jumps_verified,
        'cell_residuals_finite': self.cell_residuals_finite,
        'first_wedge_subdivision_verified': (
          self.first_wedge_subdivision_verified
        ),
        'non_first_wedge_refinement_verified': (
          self.non_first_wedge_refinement_verified
        ),
        'cell_residuals_verified': self.cell_residuals_verified,
        'refinement_convergence_verified': (
          self.refinement_convergence_verified
        ),
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'claim_status': self.claim_status,
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientPhysicalFieldRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocEulerAmbientPhysicalFieldRefinementCase] = (),
  audits: Sequence[MocEulerAmbientPhysicalFieldAudit] = (),
  field_cell_counts: Sequence[int] = (),
  first_wedge_cell_counts: Sequence[int] = (),
  maximum_cell_euler_residuals: Sequence[float] = (),
  first_wedge_euler_residuals: Sequence[float] = (),
  non_first_wedge_maximum_residuals: Sequence[float] = (),
  resolution_order_verified: bool = False,
  candidate_fields_verified: bool = False,
  shock_jumps_verified: bool = False,
  cell_residuals_finite: bool = False,
  first_wedge_subdivision_verified: bool = False,
  non_first_wedge_refinement_verified: bool = False,
  cell_residuals_verified: bool = False,
  refinement_convergence_verified: bool = False,
) -> MocEulerAmbientPhysicalFieldRefinementMeasurement:
  case_values = tuple(cases)
  audit_values = tuple(audits)
  paired_count = min(len(case_values), len(audit_values))
  case_values = case_values[:paired_count]
  audit_values = audit_values[:paired_count]

  def align(values: Sequence[Any], default: Any) -> tuple[Any, ...]:
    normalised = tuple(values)
    if not normalised:
      return (default,) * paired_count
    if len(normalised) != paired_count:
      return normalised[:paired_count]
    return normalised

  return MocEulerAmbientPhysicalFieldRefinementMeasurement(
    status=status,
    cases=case_values,
    audits=audit_values,
    field_cell_counts=align(field_cell_counts, 0),
    first_wedge_cell_counts=align(first_wedge_cell_counts, 0),
    maximum_cell_euler_residuals=align(maximum_cell_euler_residuals, 0.0),
    first_wedge_euler_residuals=align(first_wedge_euler_residuals, 0.0),
    non_first_wedge_maximum_residuals=align(
      non_first_wedge_maximum_residuals,
      0.0,
    ),
    resolution_order_verified=resolution_order_verified,
    candidate_fields_verified=candidate_fields_verified,
    shock_jumps_verified=shock_jumps_verified,
    cell_residuals_finite=cell_residuals_finite,
    first_wedge_subdivision_verified=first_wedge_subdivision_verified,
    non_first_wedge_refinement_verified=non_first_wedge_refinement_verified,
    cell_residuals_verified=cell_residuals_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    claim_status=(
      'independent-ambient-closed-field-refinement; first-wedge remesh, '
      'canonical reflected free-boundary, and external validation remain '
      'pending'
    ),
    message=message,
  )


def measure_moc_euler_ambient_physical_field_refinement(
  cases: Sequence[MocEulerAmbientPhysicalFieldRefinementCase],
  *,
  expected_resolutions: Sequence[int] | None = None,
  cell_residual_tolerance: float = 1.0e-2,
  refinement_tolerance: float = 1.0e-8,
) -> MocEulerAmbientPhysicalFieldRefinementMeasurement:
  """Audit field cases without repairing or interpolating their outputs.

  The first reflected wedge is considered resolution-complete only when the
  number of cells carrying ``post-shock-ambient-centerline-triangle`` grows
  across the supplied cases.  This is deliberately stricter than observing
  a smaller residual from a changed boundary trace: a boundary-resolution
  sweep cannot claim to have refined an unsplit topological cell.
  """

  try:
    items = tuple(cases)
  except TypeError:
    return _failure(
      MocEulerAmbientPhysicalFieldRefinementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
    )
  if len(items) < 2:
    return _failure(
      MocEulerAmbientPhysicalFieldRefinementStatus.INVALID_INPUT,
      'at least two ambient physical-field refinement cases are required',
    )
  if any(
    not isinstance(item, MocEulerAmbientPhysicalFieldRefinementCase)
    for item in items
  ):
    return _failure(
      MocEulerAmbientPhysicalFieldRefinementStatus.INVALID_INPUT,
      'refinement cases must contain '
      'MocEulerAmbientPhysicalFieldRefinementCase values',
    )
  try:
    cell_tolerance = float(cell_residual_tolerance)
    refinement_bound = float(refinement_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientPhysicalFieldRefinementStatus.INVALID_INPUT,
      'refinement tolerances must be numeric',
    )
  if (
    not isfinite(cell_tolerance)
    or cell_tolerance <= 0.0
    or not isfinite(refinement_bound)
    or refinement_bound < 0.0
  ):
    raise ValueError(
      'cell_residual_tolerance must be finite and positive and '
      'refinement_tolerance must be finite and nonnegative'
    )
  resolutions = tuple(item.resolution for item in items)
  resolution_order_verified = all(
    right > left for left, right in zip(resolutions, resolutions[1:])
  )
  if expected_resolutions is not None:
    try:
      expected_values = tuple(expected_resolutions)
    except TypeError:
      return _failure(
        MocEulerAmbientPhysicalFieldRefinementStatus.INVALID_INPUT,
        'expected_resolutions must contain integers',
      )
    if any(
      isinstance(value, bool) or not isinstance(value, int)
      for value in expected_values
    ):
      return _failure(
        MocEulerAmbientPhysicalFieldRefinementStatus.INVALID_INPUT,
        'expected_resolutions must contain integers',
      )
    expected = tuple(expected_values)
    if expected != resolutions:
      return _failure(
        MocEulerAmbientPhysicalFieldRefinementStatus.RESOLUTION_FAILURE,
        'supplied resolutions do not match expected coarse-to-fine cases',
      )
  if not resolution_order_verified:
    return _failure(
      MocEulerAmbientPhysicalFieldRefinementStatus.RESOLUTION_FAILURE,
      'refinement resolutions must be strictly increasing',
    )

  audits: list[MocEulerAmbientPhysicalFieldAudit] = []
  field_cell_counts: list[int] = []
  first_wedge_cell_counts: list[int] = []
  maximum_residuals: list[float] = []
  first_wedge_residuals: list[float] = []
  non_first_wedge_residuals: list[float] = []
  candidate_fields_verified = True
  shock_jumps_verified = True
  cell_residuals_finite = True
  cell_residuals_verified = True
  for case in items:
    result = case.result
    audit = measure_moc_euler_ambient_physical_field(
      result,
      cell_residual_tolerance=cell_tolerance,
    )
    audits.append(audit)
    field = result.field
    if field is None:
      return _failure(
        MocEulerAmbientPhysicalFieldRefinementStatus.CASE_FAILURE,
        'ambient physical-field refinement case did not retain a field',
        resolution_order_verified=True,
      )
    field_cell_counts.append(len(field.cells))
    wedge_indices = tuple(
      index
      for index, cell in enumerate(field.cells)
      if cell.cell_kind == 'post-shock-ambient-centerline-triangle'
    )
    first_wedge_cell_counts.append(len(wedge_indices))
    candidate_fields_verified = candidate_fields_verified and bool(
      result.converged
      and result.physical_closure_verified
      and result.state_sampling_available
      and audit.physical_field_verified
      and audit.physical_closure_verified
    )
    shock_jumps_verified = shock_jumps_verified and audit.shock_jump_verified
    try:
      field_audit = measure_moc_physical_field_euler_audit(
        field,
        cell_residual_tolerance=cell_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerAmbientPhysicalFieldRefinementStatus.CASE_FAILURE,
        f'independent cell audit raised: {error}',
        cases=items[:len(audits)],
        audits=audits,
        field_cell_counts=field_cell_counts,
        first_wedge_cell_counts=first_wedge_cell_counts,
        resolution_order_verified=True,
        candidate_fields_verified=candidate_fields_verified,
        shock_jumps_verified=shock_jumps_verified,
      )
    values = tuple(field_audit.cell_euler_residuals)
    if len(values) != len(field.cells):
      return _failure(
        MocEulerAmbientPhysicalFieldRefinementStatus.CASE_FAILURE,
        'independent cell audit did not return one residual per field cell',
        cases=items[:len(audits)],
        audits=audits,
        field_cell_counts=field_cell_counts,
        first_wedge_cell_counts=first_wedge_cell_counts,
        resolution_order_verified=True,
        candidate_fields_verified=candidate_fields_verified,
        shock_jumps_verified=shock_jumps_verified,
      )
    wedge_values = tuple(values[index] for index in wedge_indices)
    non_wedge_values = tuple(
      value for index, value in enumerate(values) if index not in wedge_indices
    )
    maximum = max(values, default=0.0)
    wedge_maximum = max(wedge_values, default=0.0)
    non_wedge_maximum = max(non_wedge_values, default=0.0)
    maximum_residuals.append(maximum)
    first_wedge_residuals.append(wedge_maximum)
    non_first_wedge_residuals.append(non_wedge_maximum)
    cell_residuals_finite = cell_residuals_finite and bool(
      field_audit.cell_euler_residuals_finite
      and all(isfinite(value) for value in values)
    )
    cell_residuals_verified = cell_residuals_verified and bool(
      field_audit.cell_euler_residuals_verified
    )

  first_wedge_subdivision_verified = bool(
    first_wedge_cell_counts[0] > 0
    and all(
      right > left
      for left, right in zip(first_wedge_cell_counts, first_wedge_cell_counts[1:])
    )
  )
  non_first_wedge_refinement_verified = bool(
    all(
      right <= left + refinement_bound
      for left, right in zip(
        non_first_wedge_residuals,
        non_first_wedge_residuals[1:],
      )
    )
    and non_first_wedge_residuals[-1] <= cell_tolerance
  )
  refinement_convergence_verified = bool(
    candidate_fields_verified
    and shock_jumps_verified
    and cell_residuals_finite
    and first_wedge_subdivision_verified
    and non_first_wedge_refinement_verified
    and cell_residuals_verified
    and all(value <= cell_tolerance for value in maximum_residuals)
  )
  if not candidate_fields_verified:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.CASE_FAILURE
    message = 'one or more local ambient-closed field cases failed independent field checks'
  elif not shock_jumps_verified:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.CASE_FAILURE
    message = 'one or more refinement cases failed independent shock-jump checks'
  elif not cell_residuals_finite:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.CELL_RESIDUAL_FAILURE
    message = 'one or more refinement cases returned non-finite cell residuals'
  elif not first_wedge_subdivision_verified:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.FIRST_WEDGE_REFINEMENT_FAILURE
    message = (
      'boundary samples were increased without subdividing the reflected '
      'first wedge; a terminal-wedge remesh is required before chain promotion'
    )
  elif not cell_residuals_verified:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.CELL_RESIDUAL_FAILURE
    message = 'independent conservative cell residuals exceeded the declared tolerance'
  elif not non_first_wedge_refinement_verified:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.CONSISTENCY_FAILURE
    message = 'non-wedge cell residuals did not converge across the supplied resolutions'
  else:
    status = MocEulerAmbientPhysicalFieldRefinementStatus.CONVERGED
    message = (
      'independent ambient-closed field refinement passed local cell and '
      'first-wedge subdivision gates; canonical closure and external validation remain pending'
    )
  return _failure(
    status,
    message,
    cases=items,
    audits=audits,
    field_cell_counts=field_cell_counts,
    first_wedge_cell_counts=first_wedge_cell_counts,
    maximum_cell_euler_residuals=maximum_residuals,
    first_wedge_euler_residuals=first_wedge_residuals,
    non_first_wedge_maximum_residuals=non_first_wedge_residuals,
    resolution_order_verified=resolution_order_verified,
    candidate_fields_verified=candidate_fields_verified,
    shock_jumps_verified=shock_jumps_verified,
    cell_residuals_finite=cell_residuals_finite,
    first_wedge_subdivision_verified=first_wedge_subdivision_verified,
    non_first_wedge_refinement_verified=non_first_wedge_refinement_verified,
    cell_residuals_verified=cell_residuals_verified,
    refinement_convergence_verified=refinement_convergence_verified,
  )
