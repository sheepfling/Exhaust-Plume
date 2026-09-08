"""Declared-resolution evidence for the front-aligned Euler consumer.

This module does not manufacture a refinement level by changing a label on one
mesh.  Callers must supply independently generated physical-field shock-front
conditions, each with a declared shock-front sample count.  The runner then
executes a fresh conservative reconciliation and an independent residual
audit for every case.  The resulting ladder is local research evidence only;
it cannot close global shock placement or authorize a production cell fit.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerReconciliationRequest,
  MocPhysicalFieldEulerReconciliationResult,
  solve_moc_physical_field_euler_reconciliation,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionResult,
)
from exhaust_plume.validation.moc_physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerReconciliationAudit,
  measure_moc_physical_field_euler_reconciliation,
)

__all__ = (
  'MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_REFINEMENT_OPERATOR_ID',
  'MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_REFINEMENT_RUN_OPERATOR_ID',
  'MocPhysicalFieldEulerReconciliationRefinementStatus',
  'MocPhysicalFieldEulerReconciliationSourceCase',
  'MocPhysicalFieldEulerReconciliationRefinementCase',
  'MocPhysicalFieldEulerReconciliationRefinementMeasurement',
  'MocPhysicalFieldEulerReconciliationRefinementRun',
  'measure_moc_physical_field_euler_reconciliation_refinement',
  'run_moc_physical_field_euler_reconciliation_refinement',
)


MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_REFINEMENT_OPERATOR_ID = (
  'op.moc.physical-field-euler-reconciliation-refinement'
)
MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.physical-field-euler-reconciliation-refinement-run'
)


class MocPhysicalFieldEulerReconciliationRefinementStatus(str, Enum):
  """Typed outcome for one independently executed resolution ladder."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged-local-physical-field-euler-reconciliation-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'physical-field-euler-reconciliation-resolution-failure'
  SOURCE_FAILURE = 'physical-field-euler-reconciliation-source-failure'
  SOLVER_FAILURE = 'physical-field-euler-reconciliation-solver-failure'
  AUDIT_FAILURE = 'physical-field-euler-reconciliation-audit-failure'
  FIDELITY_FAILURE = 'physical-field-euler-reconciliation-fidelity-failure'
####


def _source_geometry_payload(
  condition: MocPhysicalFieldShockFrontConditionResult,
) -> dict[str, object]:
  """Serialize retained paths and cell topology for a source fingerprint."""

  field = condition.field
  if field is None:
    raise ValueError('source condition does not retain a physical field')
  ####
  cells = tuple(
    tuple(
      tuple(float(coordinate) for coordinate in point)
      for point in getattr(cell, 'vertices_xr_m', ())
    )
    for cell in getattr(field, 'cells', ())
  )
  if not cells:
    raise ValueError('source physical field retains no cell geometry')
  ####
  return {
    'shock_front_points_m': tuple(condition.shock_front_points_m),
    'ambient_neighbor_points_m': tuple(condition.ambient_neighbor_points_m),
    'centerline_neighbor_points_m': tuple(condition.centerline_neighbor_points_m),
    'cell_vertices_by_cell_m': cells,
  }
####


def _source_geometry_fingerprint(
  condition: MocPhysicalFieldShockFrontConditionResult,
) -> str:
  payload = _source_geometry_payload(condition)
  encoded = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    allow_nan=False,
  ).encode('utf-8')
  return sha256(encoded).hexdigest()
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationSourceCase:
  """One independently generated source field at a declared resolution."""

  resolution: int
  shock_front_condition: MocPhysicalFieldShockFrontConditionResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 3
    ):
      raise ValueError('resolution must be an integer of at least three')
    ####
    if not isinstance(
      self.shock_front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'shock_front_condition must be a '
        'MocPhysicalFieldShockFrontConditionResult'
      )
    ####
    if self.resolution != len(self.shock_front_condition.shock_front_points_m):
      raise ValueError(
        'resolution must equal the retained shock-front sample count; '
        'a label cannot create a refinement level'
      )
    ####
    if not self.shock_front_condition.converged:
      raise ValueError(
        'source cases must retain a converged physical shock-front condition'
      )
    ####
    _source_geometry_fingerprint(self.shock_front_condition)
  ####

  @property
  def source_geometry_fingerprint(self) -> str:
    """Return the exact retained source geometry fingerprint."""

    return _source_geometry_fingerprint(self.shock_front_condition)
  ####

  @property
  def source_cell_count(self) -> int:
    field = self.shock_front_condition.field
    return 0 if field is None else len(tuple(getattr(field, 'cells', ())))
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'resolution': self.resolution,
      'source_cell_count': self.source_cell_count,
      'source_geometry_fingerprint': self.source_geometry_fingerprint,
      'condition_status': self.shock_front_condition.status.value,
      'condition_converged': self.shock_front_condition.converged,
      'condition_id': self.shock_front_condition.request.condition_id,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationRefinementCase:
  """One fresh consumer solve plus its independent residual audit."""

  source_case: MocPhysicalFieldEulerReconciliationSourceCase
  request: MocPhysicalFieldEulerReconciliationRequest
  result: MocPhysicalFieldEulerReconciliationResult
  audit: MocPhysicalFieldEulerReconciliationAudit

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_case,
      MocPhysicalFieldEulerReconciliationSourceCase,
    ):
      raise TypeError('source_case must be a typed reconciliation source case')
    ####
    if not isinstance(
      self.request,
      MocPhysicalFieldEulerReconciliationRequest,
    ):
      raise TypeError(
        'request must be a MocPhysicalFieldEulerReconciliationRequest'
      )
    ####
    if not isinstance(
      self.result,
      MocPhysicalFieldEulerReconciliationResult,
    ):
      raise TypeError(
        'result must be a MocPhysicalFieldEulerReconciliationResult'
      )
    ####
    if not isinstance(self.audit, MocPhysicalFieldEulerReconciliationAudit):
      raise TypeError(
        'audit must be a MocPhysicalFieldEulerReconciliationAudit'
      )
    ####
    condition = self.source_case.shock_front_condition
    if self.request.shock_front_condition is not condition:
      raise ValueError('request must retain the exact source condition')
    ####
    if self.result.request is not self.request:
      raise ValueError('result must retain the exact reconciliation request')
    ####
    if self.result.shock_front_condition is not condition:
      raise ValueError('result must retain the exact source condition')
    ####
    if self.audit.candidate is not self.result:
      raise ValueError('audit must retain the exact reconciliation result')
    ####
  ####
  @property
  def resolution(self) -> int:
    return self.source_case.resolution
  ####

  @property
  def cell_count(self) -> int:
    return len(self.result.cell_vertices_by_cell_m)
  ####

  @property
  def local_closure_verified(self) -> bool:
    return bool(self.result.converged and self.audit.converged)
  ####

  @property
  def fidelity_isolated(self) -> bool:
    return bool(
      self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and not self.result.physical_closure_verified
      and not self.result.global_coupling_verified
      and self.audit.chain_promotion_blocked
      and not self.audit.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'resolution': self.resolution,
      'cell_count': self.cell_count,
      'source_case': self.source_case.as_report(),
      'local_closure_verified': self.local_closure_verified,
      'fidelity_isolated': self.fidelity_isolated,
      'solver_status': self.result.status.value,
      'solver_converged': self.result.converged,
      'audit_status': self.audit.status.value,
      'audit_converged': self.audit.converged,
      'maximum_conservative_euler_residual': (
        self.result.maximum_conservative_euler_residual
      ),
      'maximum_shock_jump_residual': self.result.maximum_shock_jump_residual,
      'maximum_ambient_pressure_residual_Pa': (
        self.result.maximum_ambient_pressure_residual_Pa
      ),
      'maximum_ambient_normal_velocity_residual_m_s': (
        self.result.maximum_ambient_normal_velocity_residual_m_s
      ),
      'maximum_centerline_normal_velocity_residual_m_s': (
        self.result.maximum_centerline_normal_velocity_residual_m_s
      ),
      'result': self.result.as_report(),
      'audit': self.audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationRefinementMeasurement:
  """Independent local ladder evidence below the production ceiling."""

  status: MocPhysicalFieldEulerReconciliationRefinementStatus
  cases: tuple[MocPhysicalFieldEulerReconciliationRefinementCase, ...] = ()
  resolutions: tuple[int, ...] = ()
  source_geometry_fingerprints: tuple[str, ...] = ()
  cell_counts: tuple[int, ...] = ()
  maximum_conservative_euler_residuals: tuple[float | None, ...] = ()
  maximum_shock_jump_residuals: tuple[float | None, ...] = ()
  maximum_ambient_pressure_residuals_Pa: tuple[float | None, ...] = ()
  maximum_ambient_normal_velocity_residuals_m_s: tuple[float | None, ...] = ()
  maximum_centerline_normal_velocity_residuals_m_s: tuple[float | None, ...] = ()
  resolution_order_verified: bool = False
  source_geometry_distinct_verified: bool = False
  mesh_growth_verified: bool = False
  case_audits_verified: bool = False
  residuals_finite: bool = False
  boundary_diagnostics_finite: bool = False
  local_refinement_verified: bool = False
  fidelity_isolation_verified: bool = False
  physical_closure_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldEulerReconciliationRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocPhysicalFieldEulerReconciliationRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(case, MocPhysicalFieldEulerReconciliationRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed refinement cases')
    ####
    object.__setattr__(self, 'cases', cases)
    derived_resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != derived_resolutions:
      raise ValueError('resolutions must match case resolutions')
    ####
    object.__setattr__(self, 'resolutions', derived_resolutions)
    derived_fingerprints = tuple(
      case.source_case.source_geometry_fingerprint for case in cases
    )
    if (
      self.source_geometry_fingerprints
      and tuple(self.source_geometry_fingerprints) != derived_fingerprints
    ):
      raise ValueError(
        'source_geometry_fingerprints must match the supplied cases'
      )
    ####
    object.__setattr__(
      self,
      'source_geometry_fingerprints',
      derived_fingerprints,
    )
    derived_cell_counts = tuple(case.cell_count for case in cases)
    if self.cell_counts and tuple(self.cell_counts) != derived_cell_counts:
      raise ValueError('cell_counts must match case cell counts')
    ####
    object.__setattr__(self, 'cell_counts', derived_cell_counts)
    for name in (
      'maximum_conservative_euler_residuals',
      'maximum_shock_jump_residuals',
      'maximum_ambient_pressure_residuals_Pa',
      'maximum_ambient_normal_velocity_residuals_m_s',
      'maximum_centerline_normal_velocity_residuals_m_s',
    ):
      values = tuple(
        None if value is None else float(value)
        for value in getattr(self, name)
      )
      if any(
        value is not None and (not isfinite(value) or value < 0.0)
        for value in values
      ):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    if self.cases and any(
      len(getattr(self, name)) != len(self.cases)
      for name in (
        'maximum_conservative_euler_residuals',
        'maximum_shock_jump_residuals',
        'maximum_ambient_pressure_residuals_Pa',
        'maximum_ambient_normal_velocity_residuals_m_s',
        'maximum_centerline_normal_velocity_residuals_m_s',
      )
    ):
      raise ValueError('refinement metric arrays must match case count')
    ####
    for name in (
      'resolution_order_verified',
      'source_geometry_distinct_verified',
      'mesh_growth_verified',
      'case_audits_verified',
      'residuals_finite',
      'boundary_diagnostics_finite',
      'local_refinement_verified',
      'fidelity_isolation_verified',
      'physical_closure_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('reconciliation refinement must retain promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'reconciliation refinement cannot allow production claims'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'reconciliation refinement must retain the external-validation gate'
      )
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
    return bool(
      self.status
      is MocPhysicalFieldEulerReconciliationRefinementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and len(self.cases) >= 2
      and self.resolution_order_verified
      and self.source_geometry_distinct_verified
      and self.mesh_growth_verified
      and self.case_audits_verified
      and self.residuals_finite
      and self.boundary_diagnostics_finite
      and self.local_refinement_verified
      and self.fidelity_isolation_verified
      and not self.physical_closure_verified
      and not self.global_coupling_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and self.external_validation_required
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': list(self.resolutions),
      'source_geometry_fingerprints': list(self.source_geometry_fingerprints),
      'cell_counts': list(self.cell_counts),
      'maximum_conservative_euler_residuals': list(
        self.maximum_conservative_euler_residuals
      ),
      'maximum_shock_jump_residuals': list(self.maximum_shock_jump_residuals),
      'maximum_ambient_pressure_residuals_Pa': list(
        self.maximum_ambient_pressure_residuals_Pa
      ),
      'maximum_ambient_normal_velocity_residuals_m_s': list(
        self.maximum_ambient_normal_velocity_residuals_m_s
      ),
      'maximum_centerline_normal_velocity_residuals_m_s': list(
        self.maximum_centerline_normal_velocity_residuals_m_s
      ),
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'source_geometry_distinct_verified': self.source_geometry_distinct_verified,
        'mesh_growth_verified': self.mesh_growth_verified,
        'case_audits_verified': self.case_audits_verified,
        'residuals_finite': self.residuals_finite,
        'boundary_diagnostics_finite': self.boundary_diagnostics_finite,
        'local_refinement_verified': self.local_refinement_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'physical_closure_verified': False,
        'global_coupling_verified': False,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'external_validation_required': self.external_validation_required,
      },
      'cases': [case.as_report() for case in self.cases],
      'physical_closure_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'external_validation_required': self.external_validation_required,
      'claim_status': (
        'independent-front-aligned-euler-resolution-ladder; '
        'global placement, canonical closure, physical shock-cell fitting, '
        'external validation, and production claims remain blocked'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationRefinementRun:
  """Fresh solver execution packet for one source resolution ladder."""

  requested_resolutions: tuple[int, ...]
  source_cases: tuple[MocPhysicalFieldEulerReconciliationSourceCase, ...]
  cases: tuple[MocPhysicalFieldEulerReconciliationRefinementCase, ...]
  measurement: MocPhysicalFieldEulerReconciliationRefinementMeasurement
  request_options: MappingProxyType = MappingProxyType({})
  operator_id: str = (
    MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_REFINEMENT_RUN_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    requested = tuple(self.requested_resolutions)
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 3
      for value in requested
    ):
      raise ValueError('requested_resolutions must contain integers of at least three')
    ####
    source_cases = tuple(self.source_cases)
    cases = tuple(self.cases)
    if any(
      not isinstance(case, MocPhysicalFieldEulerReconciliationSourceCase)
      for case in source_cases
    ):
      raise TypeError('source_cases must contain typed source cases')
    ####
    if any(
      not isinstance(case, MocPhysicalFieldEulerReconciliationRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed refinement cases')
    ####
    if tuple(case.resolution for case in source_cases) != requested:
      raise ValueError('source_cases must match requested_resolutions')
    ####
    if tuple(case.source_case for case in cases) != source_cases:
      raise ValueError('cases must retain the exact source_cases')
    ####
    if not isinstance(
      self.measurement,
      MocPhysicalFieldEulerReconciliationRefinementMeasurement,
    ):
      raise TypeError('measurement must be a typed refinement measurement')
    ####
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact refinement cases')
    ####
    options = dict(self.request_options)
    object.__setattr__(self, 'requested_resolutions', requested)
    object.__setattr__(self, 'source_cases', source_cases)
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'request_options', MappingProxyType(options))
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
  ####

  @property
  def converged(self) -> bool:
    return self.measurement.converged
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': self.operator_id,
      'requested_resolutions': list(self.requested_resolutions),
      'request_options': dict(self.request_options),
      'source_cases': [case.as_report() for case in self.source_cases],
      'cases': [case.as_report() for case in self.cases],
      'measurement': self.measurement.as_report(),
      'converged': self.converged,
    }
  ####
####


def _measurement_failure(
  status: MocPhysicalFieldEulerReconciliationRefinementStatus,
  message: str,
  cases: Sequence[MocPhysicalFieldEulerReconciliationRefinementCase] = (),
) -> MocPhysicalFieldEulerReconciliationRefinementMeasurement:
  return MocPhysicalFieldEulerReconciliationRefinementMeasurement(
    status=status,
    cases=tuple(cases),
    message=message,
  )
####


def measure_moc_physical_field_euler_reconciliation_refinement(
  cases: Sequence[MocPhysicalFieldEulerReconciliationRefinementCase],
) -> MocPhysicalFieldEulerReconciliationRefinementMeasurement:
  """Independently aggregate a supplied source-bound resolution ladder."""

  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement_failure(
      MocPhysicalFieldEulerReconciliationRefinementStatus.INVALID_INPUT,
      'cases must be an iterable of refinement cases',
    )
  ####
  if any(
    not isinstance(case, MocPhysicalFieldEulerReconciliationRefinementCase)
    for case in retained_cases
  ):
    return _measurement_failure(
      MocPhysicalFieldEulerReconciliationRefinementStatus.INVALID_INPUT,
      'cases must contain typed reconciliation refinement cases',
    )
  ####
  resolutions = tuple(case.resolution for case in retained_cases)
  fingerprints = tuple(
    case.source_case.source_geometry_fingerprint for case in retained_cases
  )
  cell_counts = tuple(case.cell_count for case in retained_cases)
  resolution_order_verified = bool(
    len(resolutions) >= 2
    and all(left < right for left, right in zip(resolutions, resolutions[1:]))
  )
  source_geometry_distinct_verified = bool(
    len(fingerprints) >= 2 and len(set(fingerprints)) == len(fingerprints)
  )
  mesh_growth_verified = bool(
    len(cell_counts) >= 2
    and all(left < right for left, right in zip(cell_counts, cell_counts[1:]))
  )
  case_audits_verified = bool(
    retained_cases and all(case.local_closure_verified for case in retained_cases)
  )
  maximum_residuals = tuple(
    case.result.maximum_conservative_euler_residual
    for case in retained_cases
  )
  shock_residuals = tuple(
    case.result.maximum_shock_jump_residual for case in retained_cases
  )
  ambient_pressure_residuals = tuple(
    case.result.maximum_ambient_pressure_residual_Pa
    for case in retained_cases
  )
  ambient_normal_residuals = tuple(
    case.result.maximum_ambient_normal_velocity_residual_m_s
    for case in retained_cases
  )
  centerline_normal_residuals = tuple(
    case.result.maximum_centerline_normal_velocity_residual_m_s
    for case in retained_cases
  )
  metric_values = (
    maximum_residuals,
    shock_residuals,
    ambient_pressure_residuals,
    ambient_normal_residuals,
    centerline_normal_residuals,
  )
  residuals_finite = bool(
    retained_cases
    and all(
      value is not None and isfinite(float(value)) and float(value) >= 0.0
      for values in maximum_residuals
      for value in (values,)
    )
  )
  boundary_diagnostics_finite = bool(
    retained_cases
    and all(
      value is not None and isfinite(float(value)) and float(value) >= 0.0
      for values in metric_values[1:]
      for value in values
    )
  )
  local_refinement_verified = bool(
    len(retained_cases) >= 2
    and resolution_order_verified
    and source_geometry_distinct_verified
    and mesh_growth_verified
    and case_audits_verified
    and residuals_finite
    and boundary_diagnostics_finite
  )
  fidelity_isolation_verified = bool(
    retained_cases and all(case.fidelity_isolated for case in retained_cases)
  )
  if not retained_cases:
    status = MocPhysicalFieldEulerReconciliationRefinementStatus.INVALID_INPUT
    message = 'at least two independently generated resolution cases are required'
  elif not resolution_order_verified or not mesh_growth_verified:
    status = MocPhysicalFieldEulerReconciliationRefinementStatus.RESOLUTION_FAILURE
    message = (
      'resolution cases must be strictly ordered and retain strictly growing '
      'consumer meshes'
    )
  elif not source_geometry_distinct_verified:
    status = MocPhysicalFieldEulerReconciliationRefinementStatus.SOURCE_FAILURE
    message = (
      'resolution cases must retain distinct source geometry fingerprints; '
      'a relabeled mesh cannot count as refinement'
    )
  elif not case_audits_verified or not residuals_finite or not boundary_diagnostics_finite:
    status = MocPhysicalFieldEulerReconciliationRefinementStatus.AUDIT_FAILURE
    message = 'one or more resolution cases failed local independent audit'
  elif not fidelity_isolation_verified:
    status = MocPhysicalFieldEulerReconciliationRefinementStatus.FIDELITY_FAILURE
    message = 'one or more resolution cases crossed the research fidelity ceiling'
  else:
    status = MocPhysicalFieldEulerReconciliationRefinementStatus.CONVERGED_LOCAL_REFINEMENT
    message = (
      'distinct source fields were freshly reconciled and independently audited '
      'across the declared local resolution ladder; global placement and '
      'production gates remain open'
    )
  ####
  return MocPhysicalFieldEulerReconciliationRefinementMeasurement(
    status=status,
    cases=retained_cases,
    resolutions=resolutions,
    source_geometry_fingerprints=fingerprints,
    cell_counts=cell_counts,
    maximum_conservative_euler_residuals=tuple(
      None if value is None else float(value) for value in maximum_residuals
    ),
    maximum_shock_jump_residuals=tuple(
      None if value is None else float(value) for value in shock_residuals
    ),
    maximum_ambient_pressure_residuals_Pa=tuple(
      None if value is None else float(value)
      for value in ambient_pressure_residuals
    ),
    maximum_ambient_normal_velocity_residuals_m_s=tuple(
      None if value is None else float(value)
      for value in ambient_normal_residuals
    ),
    maximum_centerline_normal_velocity_residuals_m_s=tuple(
      None if value is None else float(value)
      for value in centerline_normal_residuals
    ),
    resolution_order_verified=resolution_order_verified,
    source_geometry_distinct_verified=source_geometry_distinct_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    residuals_finite=residuals_finite,
    boundary_diagnostics_finite=boundary_diagnostics_finite,
    local_refinement_verified=local_refinement_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    physical_closure_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    message=message,
  )
####


def run_moc_physical_field_euler_reconciliation_refinement(
  source_cases: Sequence[MocPhysicalFieldEulerReconciliationSourceCase],
  *,
  reference_total_temperature_K: float,
  request_options: Mapping[str, Any] | None = None,
) -> MocPhysicalFieldEulerReconciliationRefinementRun:
  """Freshly execute and audit each supplied physical-field source case."""

  retained_source_cases = tuple(source_cases)
  if any(
    not isinstance(case, MocPhysicalFieldEulerReconciliationSourceCase)
    for case in retained_source_cases
  ):
    raise TypeError('source_cases must contain typed reconciliation source cases')
  ####
  temperature = float(reference_total_temperature_K)
  if not isfinite(temperature) or temperature <= 0.0:
    raise ValueError('reference_total_temperature_K must be finite and positive')
  ####
  options = {} if request_options is None else dict(request_options)
  if 'shock_front_condition' in options or 'source' in options:
    raise ValueError(
      'request_options cannot override the source condition or fidelity source'
    )
  ####
  cases: list[MocPhysicalFieldEulerReconciliationRefinementCase] = []
  for source_case in retained_source_cases:
    request = MocPhysicalFieldEulerReconciliationRequest(
      shock_front_condition=source_case.shock_front_condition,
      reference_total_temperature_K=temperature,
      **options,
    )
    result = solve_moc_physical_field_euler_reconciliation(request)
    audit = measure_moc_physical_field_euler_reconciliation(result)
    cases.append(
      MocPhysicalFieldEulerReconciliationRefinementCase(
        source_case=source_case,
        request=request,
        result=result,
        audit=audit,
      )
    )
  ####
  measurement = measure_moc_physical_field_euler_reconciliation_refinement(cases)
  return MocPhysicalFieldEulerReconciliationRefinementRun(
    requested_resolutions=tuple(case.resolution for case in retained_source_cases),
    source_cases=retained_source_cases,
    cases=tuple(cases),
    measurement=measurement,
    request_options=MappingProxyType(options),
  )
####
