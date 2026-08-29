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
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeRemeshResult,
)
from exhaust_plume.models.moc.topology import validate_moc_mesh
from exhaust_plume.validation.moc_euler import (
  MocEulerAmbientPhysicalFieldAudit,
  _cell_flux_residual,
  measure_moc_euler_ambient_physical_field,
  measure_moc_physical_field_euler_audit,
)

__all__ = (
  'MOC_EULER_AMBIENT_PHYSICAL_FIELD_REFINEMENT_OPERATOR_ID',
  'MocEulerAmbientPhysicalFieldRefinementStatus',
  'MocEulerAmbientPhysicalFieldRefinementCase',
  'MocEulerAmbientPhysicalFieldRefinementMeasurement',
  'measure_moc_euler_ambient_physical_field_refinement',
  'MOC_EULER_AMBIENT_FIRST_WEDGE_REMESH_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeRemeshAuditStatus',
  'MocEulerAmbientFirstWedgeRemeshAudit',
  'measure_moc_euler_ambient_first_wedge_remesh',
  'MocEulerAmbientFirstWedgeRemeshRefinementCase',
  'MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus',
  'MocEulerAmbientFirstWedgeRemeshRefinementMeasurement',
  'measure_moc_euler_ambient_first_wedge_remesh_refinement',
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


MOC_EULER_AMBIENT_FIRST_WEDGE_REMESH_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-remesh-audit'
)


class MocEulerAmbientFirstWedgeRemeshAuditStatus(str, Enum):
  """Outcome of independently auditing one diagnostic wedge remesh."""

  CONVERGED_LOCAL_AUDIT = 'converged_euler_ambient_first_wedge_remesh_audit'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'euler_ambient_first_wedge_remesh_source_failure'
  TOPOLOGY_FAILURE = 'euler_ambient_first_wedge_remesh_topology_failure'
  STATE_FAILURE = 'euler_ambient_first_wedge_remesh_state_failure'
  CELL_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_remesh_cell_residual_failure'
  )
  FLAG_FAILURE = 'euler_ambient_first_wedge_remesh_flag_failure'


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeRemeshAudit:
  """Independent evidence for one bounded first-wedge subdivision."""

  status: MocEulerAmbientFirstWedgeRemeshAuditStatus
  remesh_status: str | None
  subdivision_level: int
  subdivision_side_count: int
  cell_count: int
  state_sample_count: int
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  topology_verified: bool
  state_projection_verified: bool
  pressure_lineage_carried: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  cell_residual_tolerance: float
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_FIRST_WEDGE_REMESH_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientFirstWedgeRemeshAuditStatus):
      raise TypeError(
        'status must be a MocEulerAmbientFirstWedgeRemeshAuditStatus'
      )
    if self.remesh_status is not None:
      object.__setattr__(self, 'remesh_status', str(self.remesh_status))
    for name in (
      'subdivision_level',
      'subdivision_side_count',
      'cell_count',
      'state_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'cell_euler_residuals must contain finite nonnegative values'
      )
    if len(residuals) != self.cell_count:
      raise ValueError('cell_euler_residuals must match cell_count')
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    if self.maximum_cell_euler_residual is not None:
      maximum = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative'
        )
      object.__setattr__(self, 'maximum_cell_euler_residual', maximum)
    tolerance = float(self.cell_residual_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('cell_residual_tolerance must be finite and positive')
    object.__setattr__(self, 'cell_residual_tolerance', tolerance)
    for name in (
      'topology_verified',
      'state_projection_verified',
      'pressure_lineage_carried',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeRemeshAuditStatus.CONVERGED_LOCAL_AUDIT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.topology_verified
      and self.state_projection_verified
      and self.pressure_lineage_carried
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'remesh_status': self.remesh_status,
      'subdivision_level': self.subdivision_level,
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'state_sample_count': self.state_sample_count,
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'topology_verified': self.topology_verified,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-diagnostic-first-wedge-remesh-audit; conservative '
        'terminal-wedge solver, canonical closure, and external validation '
        'remain pending'
      ),
      'message': self.message,
    }


def _first_wedge_remesh_audit_failure(
  status: MocEulerAmbientFirstWedgeRemeshAuditStatus,
  message: str,
  *,
  remesh_status: str | None = None,
  subdivision_level: int = 0,
  subdivision_side_count: int = 1,
  cell_count: int = 0,
  state_sample_count: int = 0,
  cell_euler_residuals: Sequence[float] = (),
  maximum_cell_euler_residual: float | None = None,
  topology_verified: bool = False,
  state_projection_verified: bool = False,
  pressure_lineage_carried: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeRemeshAudit:
  return MocEulerAmbientFirstWedgeRemeshAudit(
    status=status,
    remesh_status=remesh_status,
    subdivision_level=subdivision_level,
    subdivision_side_count=subdivision_side_count,
    cell_count=cell_count,
    state_sample_count=state_sample_count,
    cell_euler_residuals=tuple(cell_euler_residuals),
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_remesh(
  remesh: MocEulerAmbientFirstWedgeRemeshResult,
  *,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeRemeshAudit:
  """Recompute local remesh topology, state samples, and Euler flux residuals."""

  if not isinstance(remesh, MocEulerAmbientFirstWedgeRemeshResult):
    return _first_wedge_remesh_audit_failure(
      MocEulerAmbientFirstWedgeRemeshAuditStatus.INVALID_INPUT,
      'remesh must be a MocEulerAmbientFirstWedgeRemeshResult',
    )
  try:
    tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _first_wedge_remesh_audit_failure(
      MocEulerAmbientFirstWedgeRemeshAuditStatus.INVALID_INPUT,
      'cell_residual_tolerance must be numeric',
      remesh_status=remesh.status.value,
      subdivision_level=remesh.subdivision_level,
      subdivision_side_count=remesh.subdivision_side_count,
      cell_count=remesh.cell_count,
      state_sample_count=remesh.state_sample_count,
    )
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('cell_residual_tolerance must be finite and positive')
  common = {
    'remesh_status': remesh.status.value,
    'subdivision_level': remesh.subdivision_level,
    'subdivision_side_count': remesh.subdivision_side_count,
    'cell_count': remesh.cell_count,
    'state_sample_count': remesh.state_sample_count,
    'cell_residual_tolerance': tolerance,
  }
  if not remesh.converged:
    return _first_wedge_remesh_audit_failure(
      MocEulerAmbientFirstWedgeRemeshAuditStatus.SOURCE_FAILURE,
      'first-wedge remesh audit requires a converged diagnostic subdivision',
      **common,
    )
  independent_topology = validate_moc_mesh(remesh.cells)
  topology_verified = bool(
    independent_topology.status is remesh.topology.status
    and independent_topology.cell_count == remesh.topology.cell_count
    and independent_topology.edge_count == remesh.topology.edge_count
    and independent_topology.boundary_edge_count == remesh.topology.boundary_edge_count
    and independent_topology.nonmanifold_edge_count == remesh.topology.nonmanifold_edge_count
    and independent_topology.connected
    and independent_topology.forms_closed_zone
    and independent_topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _first_wedge_remesh_audit_failure(
      MocEulerAmbientFirstWedgeRemeshAuditStatus.TOPOLOGY_FAILURE,
      'independent first-wedge remesh topology check failed',
      topology_verified=False,
      **common,
    )
  state_projection_verified = bool(
    len(remesh.cells) == len(remesh.cell_samples)
    and remesh.state_projection_verified
    and all(
      sample.vertices_xr_m == tuple(cell.vertices_xr_m)
      and len(sample.states) == len(sample.vertices_xr_m)
      and len(sample.total_pressure_Pa) == len(sample.vertices_xr_m)
      and all(
        abs(state.x_m - point[0]) <= 1.0e-10
        and abs(state.y_m - point[1]) <= 1.0e-10
        and isfinite(float(pressure))
        and pressure > 0.0
        for point, state, pressure in zip(
          sample.vertices_xr_m,
          sample.states,
          sample.total_pressure_Pa,
          strict=True,
        )
      )
      for cell, sample in zip(remesh.cells, remesh.cell_samples, strict=True)
    )
  )
  if not state_projection_verified:
    return _first_wedge_remesh_audit_failure(
      MocEulerAmbientFirstWedgeRemeshAuditStatus.STATE_FAILURE,
      'independent first-wedge state/pressure projection check failed',
      topology_verified=topology_verified,
      **common,
    )
  cell_residuals: list[float] = []
  try:
    for sample in remesh.cell_samples:
      cell_residuals.append(
        _cell_flux_residual(
          sample.vertices_xr_m,
          sample.states,
          sample.total_pressure_Pa,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _first_wedge_remesh_audit_failure(
      MocEulerAmbientFirstWedgeRemeshAuditStatus.CELL_RESIDUAL_FAILURE,
      f'first-wedge remesh Euler residual reconstruction failed: {error}',
      topology_verified=topology_verified,
      state_projection_verified=state_projection_verified,
      pressure_lineage_carried=remesh.pressure_lineage_carried,
      **common,
    )
  residuals_finite = len(cell_residuals) == remesh.cell_count and all(
    isfinite(value) and value >= 0.0 for value in cell_residuals
  )
  maximum_residual = max(cell_residuals, default=0.0)
  residuals_verified = bool(
    residuals_finite and maximum_residual <= tolerance
  )
  if not residuals_finite:
    status = MocEulerAmbientFirstWedgeRemeshAuditStatus.CELL_RESIDUAL_FAILURE
    message = 'first-wedge remesh returned non-finite Euler residuals'
  elif not residuals_verified:
    status = MocEulerAmbientFirstWedgeRemeshAuditStatus.CELL_RESIDUAL_FAILURE
    message = (
      'diagnostic first-wedge remesh conservative Euler residual exceeded '
      'the declared tolerance; a solver-owned remesh is still required'
    )
  elif not remesh.pressure_lineage_carried:
    status = MocEulerAmbientFirstWedgeRemeshAuditStatus.FLAG_FAILURE
    message = 'first-wedge remesh did not retain positive source pressure lineage'
  elif (
    remesh.physical_closure_verified
    or not remesh.chain_promotion_blocked
    or remesh.production_claim_allowed
  ):
    status = MocEulerAmbientFirstWedgeRemeshAuditStatus.FLAG_FAILURE
    message = 'first-wedge diagnostic remesh weakened its fidelity boundary'
  else:
    status = MocEulerAmbientFirstWedgeRemeshAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent first-wedge remesh audit passed topology, bounded state '
      'projection, pressure lineage, and conservative residual checks; '
      'physical closure remains blocked'
    )
  return MocEulerAmbientFirstWedgeRemeshAudit(
    status=status,
    remesh_status=remesh.status.value,
    subdivision_level=remesh.subdivision_level,
    subdivision_side_count=remesh.subdivision_side_count,
    cell_count=remesh.cell_count,
    state_sample_count=remesh.state_sample_count,
    cell_euler_residuals=tuple(cell_residuals),
    maximum_cell_euler_residual=maximum_residual,
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=remesh.pressure_lineage_carried,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    physical_closure_verified=remesh.physical_closure_verified,
    chain_promotion_blocked=remesh.chain_promotion_blocked,
    production_claim_allowed=remesh.production_claim_allowed,
    cell_residual_tolerance=tolerance,
    message=message,
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeRemeshRefinementCase:
  """One diagnostic remesh at a declared subdivision level."""

  subdivision_level: int
  result: MocEulerAmbientFirstWedgeRemeshResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.subdivision_level, bool)
      or not isinstance(self.subdivision_level, int)
      or self.subdivision_level < 1
    ):
      raise ValueError('subdivision_level must be a positive integer')
    if not isinstance(self.result, MocEulerAmbientFirstWedgeRemeshResult):
      raise TypeError(
        'result must be a MocEulerAmbientFirstWedgeRemeshResult'
      )
    if self.result.subdivision_level != self.subdivision_level:
      raise ValueError(
        'subdivision_level must match the remesh result subdivision level'
      )


class MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus(str, Enum):
  """Outcome of the independent first-wedge remesh ladder audit."""

  CONVERGED = 'converged_euler_ambient_first_wedge_remesh_refinement'
  INVALID_INPUT = 'invalid_input'
  LEVEL_FAILURE = 'euler_ambient_first_wedge_remesh_level_failure'
  TOPOLOGY_FAILURE = 'euler_ambient_first_wedge_remesh_topology_failure'
  CELL_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_remesh_refinement_cell_residual_failure'
  )
  CONSISTENCY_FAILURE = (
    'euler_ambient_first_wedge_remesh_refinement_consistency_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeRemeshRefinementMeasurement:
  """Resolution evidence for the solver-owned first-wedge remesh seam."""

  status: MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus
  cases: tuple[MocEulerAmbientFirstWedgeRemeshRefinementCase, ...]
  audits: tuple[MocEulerAmbientFirstWedgeRemeshAudit, ...]
  subdivision_levels: tuple[int, ...]
  subdivision_side_counts: tuple[int, ...]
  cell_counts: tuple[int, ...]
  state_sample_counts: tuple[int, ...]
  maximum_cell_euler_residuals: tuple[float, ...]
  topology_verified: bool
  state_projection_verified: bool
  pressure_lineage_verified: bool
  cell_residuals_finite: bool
  cell_residuals_verified: bool
  subdivision_growth_verified: bool
  residual_nonincreasing_verified: bool
  refinement_convergence_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  claim_status: str = 'not_accepted'
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_FIRST_WEDGE_REMESH_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus'
      )
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    if any(
      not isinstance(case, MocEulerAmbientFirstWedgeRemeshRefinementCase)
      for case in cases
    ):
      raise TypeError(
        'cases must contain '
        'MocEulerAmbientFirstWedgeRemeshRefinementCase values'
      )
    if any(
      not isinstance(audit, MocEulerAmbientFirstWedgeRemeshAudit)
      for audit in audits
    ):
      raise TypeError(
        'audits must contain MocEulerAmbientFirstWedgeRemeshAudit values'
      )
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    levels = tuple(case.subdivision_level for case in cases)
    if self.subdivision_levels and tuple(self.subdivision_levels) != levels:
      raise ValueError('subdivision_levels must match the supplied cases')
    object.__setattr__(self, 'subdivision_levels', levels)
    for name in (
      'subdivision_side_counts',
      'cell_counts',
      'state_sample_counts',
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
    residuals = tuple(float(value) for value in self.maximum_cell_euler_residuals)
    if len(residuals) != len(cases):
      raise ValueError(
        'maximum_cell_euler_residuals must match the case count'
      )
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'maximum_cell_euler_residuals must contain finite nonnegative values'
      )
    object.__setattr__(self, 'maximum_cell_euler_residuals', residuals)
    for name in (
      'topology_verified',
      'state_projection_verified',
      'pressure_lineage_verified',
      'cell_residuals_finite',
      'cell_residuals_verified',
      'subdivision_growth_verified',
      'residual_nonincreasing_verified',
      'refinement_convergence_verified',
      'physical_closure_verified',
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
    return self.status is (
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.CONVERGED
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.topology_verified
      and self.state_projection_verified
      and self.pressure_lineage_verified
      and self.cell_residuals_finite
      and self.cell_residuals_verified
      and self.subdivision_growth_verified
      and self.residual_nonincreasing_verified
      and self.refinement_convergence_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'subdivision_levels': list(self.subdivision_levels),
      'subdivision_side_counts': list(self.subdivision_side_counts),
      'cell_counts': list(self.cell_counts),
      'state_sample_counts': list(self.state_sample_counts),
      'maximum_cell_euler_residuals': list(
        self.maximum_cell_euler_residuals
      ),
      'audits': [audit.as_report() for audit in self.audits],
      'checks': {
        'topology_verified': self.topology_verified,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'cell_residuals_finite': self.cell_residuals_finite,
        'cell_residuals_verified': self.cell_residuals_verified,
        'subdivision_growth_verified': self.subdivision_growth_verified,
        'residual_nonincreasing_verified': (
          self.residual_nonincreasing_verified
        ),
        'refinement_convergence_verified': (
          self.refinement_convergence_verified
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'claim_status': self.claim_status,
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'message': self.message,
    }


def _first_wedge_remesh_refinement_failure(
  status: MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocEulerAmbientFirstWedgeRemeshRefinementCase] = (),
  audits: Sequence[MocEulerAmbientFirstWedgeRemeshAudit] = (),
  subdivision_side_counts: Sequence[int] = (),
  cell_counts: Sequence[int] = (),
  state_sample_counts: Sequence[int] = (),
  maximum_cell_euler_residuals: Sequence[float] = (),
  topology_verified: bool = False,
  state_projection_verified: bool = False,
  pressure_lineage_verified: bool = False,
  cell_residuals_finite: bool = False,
  cell_residuals_verified: bool = False,
  subdivision_growth_verified: bool = False,
  residual_nonincreasing_verified: bool = False,
  refinement_convergence_verified: bool = False,
) -> MocEulerAmbientFirstWedgeRemeshRefinementMeasurement:
  case_values = tuple(cases)
  audit_values = tuple(audits)
  paired_count = min(len(case_values), len(audit_values))
  case_values = case_values[:paired_count]
  audit_values = audit_values[:paired_count]

  def align(values: Sequence[Any], default: Any) -> tuple[Any, ...]:
    normalised = tuple(values)
    if not normalised:
      return (default,) * paired_count
    return normalised[:paired_count]

  return MocEulerAmbientFirstWedgeRemeshRefinementMeasurement(
    status=status,
    cases=case_values,
    audits=audit_values,
    subdivision_levels=tuple(case.subdivision_level for case in case_values),
    subdivision_side_counts=align(subdivision_side_counts, 0),
    cell_counts=align(cell_counts, 0),
    state_sample_counts=align(state_sample_counts, 0),
    maximum_cell_euler_residuals=align(maximum_cell_euler_residuals, 0.0),
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    cell_residuals_finite=cell_residuals_finite,
    cell_residuals_verified=cell_residuals_verified,
    subdivision_growth_verified=subdivision_growth_verified,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    claim_status=(
      'independent-first-wedge-diagnostic-remesh-refinement; conservative '
      'terminal-wedge solver, canonical closure, and external validation '
      'remain pending'
    ),
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_remesh_refinement(
  cases: Sequence[MocEulerAmbientFirstWedgeRemeshRefinementCase],
  *,
  expected_subdivision_levels: Sequence[int] | None = None,
  cell_residual_tolerance: float = 1.0e-2,
  refinement_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeRemeshRefinementMeasurement:
  """Independently compare a sequence of local first-wedge remeshes."""

  try:
    items = tuple(cases)
  except TypeError:
    return _first_wedge_remesh_refinement_failure(
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.INVALID_INPUT,
      'remesh refinement cases must be iterable',
    )
  if len(items) < 2:
    return _first_wedge_remesh_refinement_failure(
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.INVALID_INPUT,
      'at least two first-wedge remesh cases are required',
    )
  if any(
    not isinstance(item, MocEulerAmbientFirstWedgeRemeshRefinementCase)
    for item in items
  ):
    return _first_wedge_remesh_refinement_failure(
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.INVALID_INPUT,
      'remesh refinement cases must contain typed refinement cases',
    )
  try:
    cell_tolerance = float(cell_residual_tolerance)
    refinement_bound = float(refinement_tolerance)
  except (TypeError, ValueError):
    return _first_wedge_remesh_refinement_failure(
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.INVALID_INPUT,
      'remesh refinement tolerances must be numeric',
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
  levels = tuple(item.subdivision_level for item in items)
  level_order_verified = all(
    right > left for left, right in zip(levels, levels[1:])
  )
  if expected_subdivision_levels is not None:
    try:
      expected = tuple(expected_subdivision_levels)
    except TypeError:
      return _first_wedge_remesh_refinement_failure(
        MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.INVALID_INPUT,
        'expected_subdivision_levels must contain integers',
      )
    if any(
      isinstance(value, bool) or not isinstance(value, int)
      for value in expected
    ):
      return _first_wedge_remesh_refinement_failure(
        MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.INVALID_INPUT,
        'expected_subdivision_levels must contain integers',
      )
    if expected != levels:
      return _first_wedge_remesh_refinement_failure(
        MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.LEVEL_FAILURE,
        'supplied subdivision levels do not match expected cases',
      )
  if not level_order_verified:
    return _first_wedge_remesh_refinement_failure(
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.LEVEL_FAILURE,
      'subdivision levels must be strictly increasing',
    )
  audits: list[MocEulerAmbientFirstWedgeRemeshAudit] = []
  side_counts: list[int] = []
  cell_counts: list[int] = []
  state_sample_counts: list[int] = []
  maximum_residuals: list[float] = []
  topology_verified = True
  state_projection_verified = True
  pressure_lineage_verified = True
  cell_residuals_finite = True
  cell_residuals_verified = True
  for case in items:
    audit = measure_moc_euler_ambient_first_wedge_remesh(
      case.result,
      cell_residual_tolerance=cell_tolerance,
    )
    audits.append(audit)
    side_counts.append(case.result.subdivision_side_count)
    cell_counts.append(case.result.cell_count)
    state_sample_counts.append(case.result.state_sample_count)
    maximum_residuals.append(audit.maximum_cell_euler_residual or 0.0)
    topology_verified = topology_verified and audit.topology_verified
    state_projection_verified = (
      state_projection_verified and audit.state_projection_verified
    )
    pressure_lineage_verified = (
      pressure_lineage_verified and audit.pressure_lineage_carried
    )
    cell_residuals_finite = (
      cell_residuals_finite and audit.cell_euler_residuals_finite
    )
    cell_residuals_verified = (
      cell_residuals_verified and audit.cell_euler_residuals_verified
    )
  subdivision_growth_verified = all(
    right > left for left, right in zip(cell_counts, cell_counts[1:])
  )
  residual_nonincreasing_verified = bool(
    all(
      right <= left + refinement_bound
      for left, right in zip(maximum_residuals, maximum_residuals[1:])
    )
  )
  refinement_convergence_verified = bool(
    level_order_verified
    and topology_verified
    and state_projection_verified
    and pressure_lineage_verified
    and cell_residuals_finite
    and cell_residuals_verified
    and subdivision_growth_verified
    and residual_nonincreasing_verified
  )
  if not topology_verified:
    status = (
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus
      .TOPOLOGY_FAILURE
    )
    message = 'one or more first-wedge remeshes failed independent topology checks'
  elif not state_projection_verified or not pressure_lineage_verified:
    status = (
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus
      .CONSISTENCY_FAILURE
    )
    message = 'one or more first-wedge remeshes failed bounded state/pressure checks'
  elif not cell_residuals_finite or not cell_residuals_verified:
    status = (
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus
      .CELL_RESIDUAL_FAILURE
    )
    message = (
      'first-wedge remesh residuals remain above the conservative Euler '
      'tolerance; refinement is diagnostic until a solver-owned remesh closes'
    )
  elif not subdivision_growth_verified or not residual_nonincreasing_verified:
    status = (
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus
      .CONSISTENCY_FAILURE
    )
    message = 'first-wedge remesh ladder did not show a consistent refinement trend'
  else:
    status = (
      MocEulerAmbientFirstWedgeRemeshRefinementMeasurementStatus.CONVERGED
    )
    message = (
      'independent first-wedge remesh refinement passed local topology, '
      'state, pressure, and conservative residual gates; canonical closure '
      'remains pending'
    )
  return _first_wedge_remesh_refinement_failure(
    status,
    message,
    cases=items,
    audits=audits,
    subdivision_side_counts=side_counts,
    cell_counts=cell_counts,
    state_sample_counts=state_sample_counts,
    maximum_cell_euler_residuals=maximum_residuals,
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    cell_residuals_finite=cell_residuals_finite,
    cell_residuals_verified=cell_residuals_verified,
    subdivision_growth_verified=subdivision_growth_verified,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    refinement_convergence_verified=refinement_convergence_verified,
  )
