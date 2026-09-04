"""Independent refinement evidence for the global reflected Euler bridge.

The global reflected-domain bridge now produces a locally closed exact-Euler
field, but that field is still a research result.  This module audits a
caller-supplied resolution ladder without rerunning any solver, changing a
shock path, or turning a refined field into a continued physical cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  MocReflectedDomainGlobalPhysicalClosureStatus,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceResult,
  MocReflectedDomainGlobalEulerShockBoundaryResult,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_measurements import (
  MocReflectedDomainGlobalEulerShockBoundaryMeasurement,
  MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus,
  measure_moc_reflected_domain_global_euler_shock_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus',
  'MocReflectedDomainGlobalEulerShockBoundaryRefinementCase',
  'MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement',
  'measure_moc_reflected_domain_global_euler_shock_boundary_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalEulerShockBoundaryRefinementRun',
  'run_moc_reflected_domain_global_euler_shock_boundary_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalEulerShockBoundaryCrossCase',
  'MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus',
  'MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement',
  'measure_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalEulerShockBoundaryCrossCaseRun',
  'run_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain-global-euler-shock-boundary-refinement'
)


class MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus(str, Enum):
  """Outcome of the independent global-Euler resolution audit."""

  CONVERGED = 'converged_global_euler_shock_boundary_refinement'
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'global_euler_refinement_resolution_failure'
  CASE_FAILURE = 'global_euler_refinement_case_failure'
  EULER_RESIDUAL_FAILURE = 'global_euler_refinement_euler_residual_failure'
  CONSISTENCY_FAILURE = 'global_euler_refinement_consistency_failure'
  FLAG_FAILURE = 'global_euler_refinement_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryRefinementCase:
  """One retained global-Euler field at a declared shock resolution."""

  resolution: int
  result: MocReflectedDomainGlobalEulerShockBoundaryResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.resolution, bool)
      or not isinstance(self.resolution, int)
      or self.resolution < 1
    ):
      raise ValueError('resolution must be a positive integer')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalEulerShockBoundaryResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalEulerShockBoundaryResult'
      )
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement:
  """Independent resolution and local-Euler evidence for the bridge.

  A converged measurement means that the supplied fields form an ordered
  resolution ladder, each field passes the independent global-Euler audit,
  and the retained cell residual does not worsen across the ladder.  The
  result remains below canonical reflected/free-boundary and external
  validation gates.
  """

  status: MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus
  cases: tuple[
    MocReflectedDomainGlobalEulerShockBoundaryRefinementCase,
    ...
  ] = ()
  audits: tuple[MocReflectedDomainGlobalEulerShockBoundaryMeasurement, ...] = ()
  resolutions: tuple[int, ...] = ()
  shock_sample_counts: tuple[int, ...] = ()
  field_cell_counts: tuple[int, ...] = ()
  source_frontier_x_m: tuple[float, ...] = ()
  maximum_cell_euler_residuals: tuple[float, ...] = ()
  maximum_endpoint_tangent_residuals_rad: tuple[float, ...] = ()
  resolution_order_verified: bool = False
  case_audits_verified: bool = False
  shock_sample_growth_verified: bool = False
  field_cell_growth_verified: bool = False
  residuals_finite: bool = False
  residual_nonincreasing_verified: bool = False
  residual_decrease_verified: bool = False
  endpoint_tangents_verified: bool = False
  source_frontier_location_verified: bool = False
  source_frontier_convergence_verified: bool = False
  physical_closure_verified: bool = False
  fidelity_isolation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  residual_tolerance: float = 1.0e-12
  frontier_tolerance_m: float = 1.0e-10
  claim_status: str = 'not_accepted'
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalEulerShockBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain '
        'MocReflectedDomainGlobalEulerShockBoundaryRefinementCase values'
      )
    ####
    if any(
      not isinstance(
        audit,
        MocReflectedDomainGlobalEulerShockBoundaryMeasurement,
      )
      for audit in audits
    ):
      raise TypeError(
        'audits must contain '
        'MocReflectedDomainGlobalEulerShockBoundaryMeasurement values'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)

    derived_resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != derived_resolutions:
      raise ValueError('resolutions must match the supplied case resolutions')
    ####
    object.__setattr__(self, 'resolutions', derived_resolutions)

    for name in (
      'shock_sample_counts',
      'field_cell_counts',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
      ):
        raise ValueError(f'{name} must contain nonnegative integers')
      ####
      object.__setattr__(self, name, values)
    ####

    for name in (
      'source_frontier_x_m',
      'maximum_cell_euler_residuals',
      'maximum_endpoint_tangent_residuals_rad',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(
          f'{name} must contain finite nonnegative values'
        )
      ####
      object.__setattr__(self, name, values)
    ####

    for name in (
      'resolution_order_verified',
      'case_audits_verified',
      'shock_sample_growth_verified',
      'field_cell_growth_verified',
      'residuals_finite',
      'residual_nonincreasing_verified',
      'residual_decrease_verified',
      'endpoint_tangents_verified',
      'source_frontier_location_verified',
      'source_frontier_convergence_verified',
      'physical_closure_verified',
      'fidelity_isolation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('residual_tolerance', 'frontier_tolerance_m'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    claim_status = str(self.claim_status)
    if not claim_status:
      raise ValueError('claim_status must be a non-empty string')
    ####
    object.__setattr__(self, 'claim_status', claim_status)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether all independent resolution gates passed."""

    return self.status is (
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CONVERGED
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the ladder passed while retaining the research ceiling."""

    return bool(
      self.converged
      and self.resolution_order_verified
      and self.case_audits_verified
      and self.shock_sample_growth_verified
      and self.field_cell_growth_verified
      and self.residuals_finite
      and self.residual_nonincreasing_verified
      and self.residual_decrease_verified
      and self.endpoint_tangents_verified
      and self.source_frontier_location_verified
      and self.source_frontier_convergence_verified
      and self.physical_closure_verified
      and self.fidelity_isolation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    """Return the refinement evidence without promoting a field."""

    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': list(self.resolutions),
      'shock_sample_counts': list(self.shock_sample_counts),
      'field_cell_counts': list(self.field_cell_counts),
      'cases': [
        {
          'resolution': case.resolution,
          'solver_status': case.result.status.value,
          'global_remesh_status': (
            None
            if case.result.global_remesh is None
            else case.result.global_remesh.status.value
          ),
          'selected_attempt_index': case.result.selected_attempt_index,
        }
        for case in self.cases
      ],
      'source_frontier_x_m': list(self.source_frontier_x_m),
      'maximum_cell_euler_residuals': list(
        self.maximum_cell_euler_residuals
      ),
      'maximum_endpoint_tangent_residuals_rad': list(
        self.maximum_endpoint_tangent_residuals_rad
      ),
      'audits': [audit.as_report() for audit in self.audits],
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'case_audits_verified': self.case_audits_verified,
        'shock_sample_growth_verified': self.shock_sample_growth_verified,
        'field_cell_growth_verified': self.field_cell_growth_verified,
        'residuals_finite': self.residuals_finite,
        'residual_nonincreasing_verified': (
          self.residual_nonincreasing_verified
        ),
        'residual_decrease_verified': self.residual_decrease_verified,
        'endpoint_tangents_verified': self.endpoint_tangents_verified,
        'source_frontier_location_verified': (
          self.source_frontier_location_verified
        ),
        'source_frontier_convergence_verified': (
          self.source_frontier_convergence_verified
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'residual_tolerance': self.residual_tolerance,
      'frontier_tolerance_m': self.frontier_tolerance_m,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'claim_status': self.claim_status,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus,
  message: str,
  *,
  cases: Sequence[
    MocReflectedDomainGlobalEulerShockBoundaryRefinementCase
  ] = (),
  audits: Sequence[MocReflectedDomainGlobalEulerShockBoundaryMeasurement] = (),
  shock_sample_counts: Sequence[int] = (),
  field_cell_counts: Sequence[int] = (),
  source_frontier_x_m: Sequence[float] = (),
  maximum_cell_euler_residuals: Sequence[float] = (),
  maximum_endpoint_tangent_residuals_rad: Sequence[float] = (),
  resolution_order_verified: bool = False,
  case_audits_verified: bool = False,
  shock_sample_growth_verified: bool = False,
  field_cell_growth_verified: bool = False,
  residuals_finite: bool = False,
  residual_nonincreasing_verified: bool = False,
  residual_decrease_verified: bool = False,
  endpoint_tangents_verified: bool = False,
  source_frontier_location_verified: bool = False,
  source_frontier_convergence_verified: bool = False,
  physical_closure_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  residual_tolerance: float = 1.0e-12,
  frontier_tolerance_m: float = 1.0e-10,
) -> MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement:
  return MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement(
    status=status,
    cases=tuple(cases),
    audits=tuple(audits),
    shock_sample_counts=tuple(shock_sample_counts),
    field_cell_counts=tuple(field_cell_counts),
    source_frontier_x_m=tuple(source_frontier_x_m),
    maximum_cell_euler_residuals=tuple(maximum_cell_euler_residuals),
    maximum_endpoint_tangent_residuals_rad=(
      tuple(maximum_endpoint_tangent_residuals_rad)
    ),
    resolution_order_verified=resolution_order_verified,
    case_audits_verified=case_audits_verified,
    shock_sample_growth_verified=shock_sample_growth_verified,
    field_cell_growth_verified=field_cell_growth_verified,
    residuals_finite=residuals_finite,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    residual_decrease_verified=residual_decrease_verified,
    endpoint_tangents_verified=endpoint_tangents_verified,
    source_frontier_location_verified=source_frontier_location_verified,
    source_frontier_convergence_verified=source_frontier_convergence_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    residual_tolerance=residual_tolerance,
    frontier_tolerance_m=frontier_tolerance_m,
    claim_status=(
      'independent-global-euler-refinement-audit; '
      'local-research-field-only'
    ),
    message=message,
  )
####


def measure_moc_reflected_domain_global_euler_shock_boundary_refinement(
  cases: Sequence[MocReflectedDomainGlobalEulerShockBoundaryRefinementCase],
  *,
  position_tolerance_m: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
  frontier_tolerance_m: float = 1.0e-10,
) -> MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement:
  """Independently audit a global-Euler field resolution ladder.

  The caller is responsible for producing fresh solver results at each
  resolution.  This operator only remeasures those retained results and
  checks the declared trend and fidelity metadata.
  """

  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
    tangent_tolerance_value = float(tangent_tolerance)
    residual_tolerance_value = float(residual_tolerance)
    frontier_tolerance_value = float(frontier_tolerance_m)
  except (TypeError, ValueError):
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'global Euler refinement tolerances must be numeric',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      invariant_tolerance_value,
      pressure_tolerance_value,
      tangent_tolerance_value,
      residual_tolerance_value,
      frontier_tolerance_value,
    )
  ):
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'global Euler refinement tolerances must be finite and positive',
    )
  ####
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'cases must be an iterable of global Euler refinement cases',
      residual_tolerance=residual_tolerance_value,
      frontier_tolerance_m=frontier_tolerance_value,
    )
  ####
  if not retained_cases:
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'at least one global Euler refinement case is required',
      residual_tolerance=residual_tolerance_value,
      frontier_tolerance_m=frontier_tolerance_value,
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalEulerShockBoundaryRefinementCase,
    )
    for case in retained_cases
  ):
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'cases must contain global Euler refinement case values',
      residual_tolerance=residual_tolerance_value,
      frontier_tolerance_m=frontier_tolerance_value,
    )
  ####

  resolutions = tuple(case.resolution for case in retained_cases)
  resolution_order_verified = all(
    right > left
    for left, right in zip(resolutions, resolutions[1:])
  )
  if len(retained_cases) < 2 or not resolution_order_verified:
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.RESOLUTION_FAILURE,
      'global Euler refinement requires at least two strictly increasing '
      'declared resolutions',
      resolution_order_verified=resolution_order_verified,
      residual_tolerance=residual_tolerance_value,
      frontier_tolerance_m=frontier_tolerance_value,
    )
  ####

  audits = tuple(
    measure_moc_reflected_domain_global_euler_shock_boundary(
      case.result,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      tangent_tolerance=tangent_tolerance_value,
    )
    for case in retained_cases
  )
  shock_sample_counts = tuple(audit.shock_sample_count for audit in audits)
  field_cell_counts = tuple(audit.field_cell_count for audit in audits)
  source_frontier_x_m = tuple(
    audit.source_frontier_x_m or 0.0 for audit in audits
  )
  maximum_cell_euler_residuals = tuple(
    audit.maximum_cell_euler_residual or 0.0 for audit in audits
  )
  maximum_endpoint_tangent_residuals_rad = tuple(
    max(
      audit.first_endpoint_tangent_residual_rad or 0.0,
      audit.last_endpoint_tangent_residual_rad or 0.0,
    )
    for audit in audits
  )
  case_audits_verified = all(
    audit.status is (
      MocReflectedDomainGlobalEulerShockBoundaryMeasurementStatus.CONVERGED
    )
    and audit.local_euler_consistency_verified
    for audit in audits
  )
  shock_sample_growth_verified = all(
    right > left
    for left, right in zip(shock_sample_counts, shock_sample_counts[1:])
  )
  field_cell_growth_verified = all(
    right >= left
    for left, right in zip(field_cell_counts, field_cell_counts[1:])
  )
  residuals_finite = bool(
    all(
      isfinite(value) and value >= 0.0
      for value in (
        *maximum_cell_euler_residuals,
        *maximum_endpoint_tangent_residuals_rad,
        *source_frontier_x_m,
      )
    )
  )
  residual_nonincreasing_verified = bool(
    residuals_finite
    and all(
      right <= left + residual_tolerance_value
      for left, right in zip(
        maximum_cell_euler_residuals,
        maximum_cell_euler_residuals[1:],
      )
    )
  )
  residual_decrease_verified = bool(
    any(
      right < left - residual_tolerance_value
      for left, right in zip(
        maximum_cell_euler_residuals,
        maximum_cell_euler_residuals[1:],
      )
    )
  )
  endpoint_tangents_verified = all(
    audit.endpoint_tangents_verified
    and maximum_endpoint_tangent_residual <= tangent_tolerance_value
    for audit, maximum_endpoint_tangent_residual in zip(
      audits,
      maximum_endpoint_tangent_residuals_rad,
    )
  )
  source_frontier_location_verified = all(
    audit.source_frontier_verified
    and audit.source_frontier_x_m is not None
    for audit in audits
  )
  source_frontier_convergence_verified = bool(
    source_frontier_location_verified
    and all(
      right <= left + frontier_tolerance_value
      for left, right in zip(
        tuple(
          abs(right - left)
          for left, right in zip(
            source_frontier_x_m,
            source_frontier_x_m[1:],
          )
        ),
        tuple(
          abs(right - left)
          for left, right in zip(
            source_frontier_x_m[1:],
            source_frontier_x_m[2:],
          )
        ),
      )
    )
    if len(source_frontier_x_m) > 2
    else source_frontier_location_verified
  )
  physical_closure_verified = all(
    audit.physical_closure_verified for audit in audits
  )
  fidelity_isolation_verified = all(
    audit.fidelity_isolation_verified
    and not audit.canonical_free_boundary_verified
    and not audit.canonical_euler_verified
    and not audit.external_validation_verified
    and audit.chain_promotion_blocked
    and not audit.production_claim_allowed
    for audit in audits
  )
  common = dict(
    cases=retained_cases,
    audits=audits,
    resolution_order_verified=resolution_order_verified,
    case_audits_verified=case_audits_verified,
    shock_sample_growth_verified=shock_sample_growth_verified,
    field_cell_growth_verified=field_cell_growth_verified,
    residuals_finite=residuals_finite,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    residual_decrease_verified=residual_decrease_verified,
    endpoint_tangents_verified=endpoint_tangents_verified,
    source_frontier_location_verified=source_frontier_location_verified,
    source_frontier_convergence_verified=source_frontier_convergence_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    shock_sample_counts=shock_sample_counts,
    field_cell_counts=field_cell_counts,
    source_frontier_x_m=source_frontier_x_m,
    maximum_cell_euler_residuals=maximum_cell_euler_residuals,
    maximum_endpoint_tangent_residuals_rad=(
      maximum_endpoint_tangent_residuals_rad
    ),
    residual_tolerance=residual_tolerance_value,
    frontier_tolerance_m=frontier_tolerance_value,
  )
  if not case_audits_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CASE_FAILURE
    )
    message = 'one or more global Euler refinement cases failed independent audit'
  elif not residuals_finite or not residual_nonincreasing_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus
      .EULER_RESIDUAL_FAILURE
    )
    message = 'global Euler cell residuals were non-finite or worsened with refinement'
  elif not residual_decrease_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus
      .CONSISTENCY_FAILURE
    )
    message = 'global Euler refinement did not demonstrate residual reduction'
  elif not (
    shock_sample_growth_verified
    and field_cell_growth_verified
    and endpoint_tangents_verified
    and source_frontier_location_verified
    and source_frontier_convergence_verified
    and physical_closure_verified
  ):
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus
      .CONSISTENCY_FAILURE
    )
    message = 'global Euler resolution or frontier consistency gates failed'
  elif not fidelity_isolation_verified:
    status = MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.FLAG_FAILURE
    message = 'global Euler refinement weakened its fidelity boundary'
  else:
    status = MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CONVERGED
    message = (
      'global exact-Euler field passed an independent declared-resolution '
      'ladder; canonical and external promotion gates remain pending'
    )
  ####
  return _failure(status, message, **common)
####


MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain-global-euler-shock-boundary-refinement-run'
)


MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain-global-euler-shock-boundary-cross-case-refinement'
)


def _refinement_fingerprint(payload: Any) -> str:
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _state_fingerprint_payload(state: Any) -> dict[str, float]:
  return {
    'x_m': float(state.x_m),
    'y_m': float(state.y_m),
    'theta_rad': float(state.theta_rad),
    'mach': float(state.mach),
    'gamma': float(state.gamma),
  }
####


def _boundary_fingerprint_payload(
  sample: MocChainBoundarySample,
) -> dict[str, Any]:
  return {
    'state': _state_fingerprint_payload(sample.state),
    'total_pressure_Pa': float(sample.total_pressure_Pa),
  }
####


def _source_band_fingerprint(
  source_band: Any,
) -> str:
  return _refinement_fingerprint({
    'report': source_band.as_report(),
    'centerline_source_states': [
      _state_fingerprint_payload(state)
      for state in source_band.centerline_source_states
    ],
    'outer_source_states': [
      _state_fingerprint_payload(state)
      for state in source_band.outer_source_states
    ],
    'centerline_total_pressure_Pa': list(
      source_band.centerline_total_pressure_Pa
    ),
    'outer_total_pressure_Pa': list(source_band.outer_total_pressure_Pa),
    'incoming_handoff': [
      _boundary_fingerprint_payload(sample)
      for sample in source_band.incoming_handoff
    ],
  })
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryRefinementRun:
  """Fresh solver execution plus independent resolution-ladder evidence.

  The existing refinement measurement intentionally audits retained fields and
  does not rerun a solver.  This result records the complementary execution
  seam: one immutable source band, one declared shock-resolution ladder, and a
  fresh global physical-closure solve for every resolution.  It remains a
  local research result even when the independent ladder converges.
  """

  source_band: MocReflectedDomainAlternatingSourceResult
  requested_resolutions: tuple[int, ...]
  closures: tuple[MocReflectedDomainGlobalPhysicalClosureResult, ...]
  cases: tuple[
    MocReflectedDomainGlobalEulerShockBoundaryRefinementCase,
    ...
  ]
  measurement: MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement
  source_band_fingerprint: str
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool
  local_physical_closure_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.source_band, MocReflectedDomainAlternatingSourceResult):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult'
      )
    ####
    resolutions = tuple(self.requested_resolutions)
    if not resolutions:
      raise ValueError('requested_resolutions must not be empty')
    ####
    if any(
      isinstance(resolution, bool)
      or not isinstance(resolution, int)
      or resolution < 1
      for resolution in resolutions
    ):
      raise ValueError(
        'requested_resolutions must contain positive integers'
      )
    ####
    closures = tuple(self.closures)
    if len(closures) != len(resolutions):
      raise ValueError('closures must match requested_resolutions')
    ####
    if any(
      not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult)
      for closure in closures
    ):
      raise TypeError(
        'closures must contain MocReflectedDomainGlobalPhysicalClosureResult values'
      )
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalEulerShockBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain global Euler refinement case values'
      )
    ####
    case_resolutions = tuple(case.resolution for case in cases)
    if len(set(case_resolutions)) != len(case_resolutions):
      raise ValueError('cases must not repeat a resolution')
    ####
    if any(resolution not in resolutions for resolution in case_resolutions):
      raise ValueError('cases must use requested resolutions')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainGlobalEulerShockBoundaryRefinementMeasurement,
    ):
      raise TypeError(
        'measurement must be a global Euler refinement measurement'
      )
    ####
    if self.measurement.cases and tuple(self.measurement.cases) != cases:
      raise ValueError('measurement cases must match retained run cases')
    ####
    object.__setattr__(self, 'requested_resolutions', resolutions)
    object.__setattr__(self, 'closures', closures)
    object.__setattr__(self, 'cases', cases)
    configuration = tuple(self.configuration)
    if any(
      not isinstance(item, tuple)
      or len(item) != 2
      or not isinstance(item[0], str)
      for item in configuration
    ):
      raise ValueError(
        'configuration must contain (name, value) pairs'
      )
    ####
    object.__setattr__(self, 'configuration', configuration)
    for name in (
      'source_band_fingerprint',
      'configuration_fingerprint',
    ):
      value = str(getattr(self, name))
      if not value:
        raise ValueError(f'{name} must be a non-empty string')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'local_physical_closure_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the independent retained-field ladder converged."""

    return self.measurement.converged
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether fresh execution and local evidence agree without promotion."""

    return bool(
      self.measurement.local_consistency_verified
      and self.fresh_solver_invocation_verified
      and len(self.cases) == len(self.requested_resolutions)
      and self.local_physical_closure_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return bool(
      self.closures
      and all(closure.chain_promotion_blocked for closure in self.closures)
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """Whether every retained resolution has a solver-owned downstream closure."""

    return bool(
      self.closures
      and all(
        closure.downstream_boundary_closure_verified
        for closure in self.closures
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.measurement.status.value,
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_band_fingerprint': self.source_band_fingerprint,
      'configuration_fingerprint': self.configuration_fingerprint,
      'configuration': dict(self.configuration),
      'requested_resolutions': list(self.requested_resolutions),
      'closures': [
        {
          'resolution': resolution,
          'status': closure.status.value,
          'converged': closure.converged,
          'physical_closure_verified': closure.physical_closure_verified,
          'global_euler_status': (
            None
            if closure.global_euler is None
            else closure.global_euler.status.value
          ),
          'global_euler_retained': closure.global_euler is not None,
          'downstream_boundary_model': closure.downstream_boundary_model,
          'downstream_boundary_closure_verified': (
            closure.downstream_boundary_closure_verified
          ),
          'promotion_blockers': list(closure.promotion_blockers),
          'production_promotion_gates': dict(
            closure.production_promotion_gates
          ),
          'chain_promotion_blocked': closure.chain_promotion_blocked,
          'production_claim_allowed': closure.production_claim_allowed,
        }
        for resolution, closure in zip(
          self.requested_resolutions,
          self.closures,
          strict=True,
        )
      ],
      'cases': [
        {
          'resolution': case.resolution,
          'solver_status': case.result.status.value,
        }
        for case in self.cases
      ],
      'measurement': self.measurement.as_report(),
      'checks': {
        'fresh_solver_invocation_verified': (
          self.fresh_solver_invocation_verified
        ),
        'local_physical_closure_verified': (
          self.local_physical_closure_verified
        ),
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'claim_status': (
        'fresh-global-physical-closure-resolution-run; '
        'local-research-field-only'
      ),
      'message': self.message,
    }
  ####
####


def run_moc_reflected_domain_global_euler_shock_boundary_refinement(
  source_band: MocReflectedDomainAlternatingSourceResult,
  resolutions: Sequence[int],
  *,
  outer_source_indices: Sequence[int] | None = None,
  target_centerline_indices: Sequence[int] | None = None,
  compression_amplitude_lower_rad: float = 0.005,
  compression_amplitude_upper_rad: float = 0.05,
  compression_envelope_skews: Sequence[float] = (-0.75, 0.0, 0.75),
  closure_tolerance_m: float = 1.0e-6,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  euler_reconciliation_shock_angle_tolerance_rad: float = 1.0e-8,
  euler_reconciliation_residual_tolerance: float = 1.0e-8,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  maximum_bracket_scan_samples: int = 0,
  maximum_attempts: int = 64,
) -> MocReflectedDomainGlobalEulerShockBoundaryRefinementRun:
  """Run fresh global closures and independently audit their shock ladder.

  ``resolutions`` controls only the retained shock-path sample count; the
  source band remains fixed for every run.  This makes the evidence useful for
  separating discretization behavior from upstream-source changes.  A missing
  global Euler result is retained as a typed closure failure and prevents the
  refinement measurement from silently dropping that resolution.
  """

  if not isinstance(source_band, MocReflectedDomainAlternatingSourceResult):
    raise TypeError(
      'source_band must be a MocReflectedDomainAlternatingSourceResult'
    )
  ####
  try:
    requested_resolutions = tuple(resolutions)
  except TypeError as error:
    raise ValueError('resolutions must be an iterable of positive integers') from error
  ####
  if not requested_resolutions:
    raise ValueError('resolutions must not be empty')
  ####
  if any(
    isinstance(resolution, bool)
    or not isinstance(resolution, int)
    or resolution < 1
    for resolution in requested_resolutions
  ):
    raise ValueError('resolutions must contain positive integers')
  ####

  def optional_tuple(
    value: Sequence[Any] | None,
    name: str,
  ) -> tuple[Any, ...] | None:
    if value is None:
      return None
    ####
    try:
      return tuple(value)
    except TypeError as error:
      raise ValueError(f'{name} must be an iterable or None') from error
    ####
  ####

  resolved_outer_indices = optional_tuple(
    outer_source_indices,
    'outer_source_indices',
  )
  resolved_centerline_indices = optional_tuple(
    target_centerline_indices,
    'target_centerline_indices',
  )
  resolved_skews = optional_tuple(
    compression_envelope_skews,
    'compression_envelope_skews',
  )
  resolved_handoff = optional_tuple(incoming_handoff, 'incoming_handoff')
  if resolved_handoff is not None and any(
    not isinstance(sample, MocChainBoundarySample)
    for sample in resolved_handoff
  ):
    raise TypeError(
      'incoming_handoff must contain MocChainBoundarySample values'
    )
  ####
  resolved_source_handoff = (
    source_band.incoming_handoff
    if resolved_handoff is None
    else resolved_handoff
  )
  source_fingerprint = _source_band_fingerprint(source_band)
  configuration_payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID
    ),
    'source_band_fingerprint': source_fingerprint,
    'requested_resolutions': list(requested_resolutions),
    'outer_source_indices': (
      None
      if resolved_outer_indices is None
      else list(resolved_outer_indices)
    ),
    'target_centerline_indices': (
      None
      if resolved_centerline_indices is None
      else list(resolved_centerline_indices)
    ),
    'compression_amplitude_lower_rad': compression_amplitude_lower_rad,
    'compression_amplitude_upper_rad': compression_amplitude_upper_rad,
    'compression_envelope_skews': (
      None if resolved_skews is None else list(resolved_skews)
    ),
    'closure_tolerance_m': closure_tolerance_m,
    'incoming_handoff': [
      _boundary_fingerprint_payload(sample)
      for sample in resolved_source_handoff
    ],
    'branch': getattr(branch, 'value', str(branch)),
    'position_tolerance_m': position_tolerance_m,
    'invariant_tolerance': invariant_tolerance,
    'attachment_pressure_tolerance': attachment_pressure_tolerance,
    'pressure_tolerance': pressure_tolerance,
    'tangent_tolerance': tangent_tolerance,
    'shock_angle_tolerance_rad': shock_angle_tolerance_rad,
    'euler_reconciliation_shock_angle_tolerance_rad': (
      euler_reconciliation_shock_angle_tolerance_rad
    ),
    'euler_reconciliation_residual_tolerance': (
      euler_reconciliation_residual_tolerance
    ),
    'maximum_segment_iterations': maximum_segment_iterations,
    'maximum_boundary_iterations': maximum_boundary_iterations,
    'maximum_shooting_iterations': maximum_shooting_iterations,
    'maximum_bracket_scan_samples': maximum_bracket_scan_samples,
    'maximum_attempts': maximum_attempts,
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = _refinement_fingerprint(configuration_payload)

  closures: list[MocReflectedDomainGlobalPhysicalClosureResult] = []
  cases: list[MocReflectedDomainGlobalEulerShockBoundaryRefinementCase] = []
  for resolution in requested_resolutions:
    try:
      closure = solve_reflected_domain_global_physical_closure(
        source_band,
        outer_source_indices=resolved_outer_indices,
        target_centerline_indices=resolved_centerline_indices,
        compression_amplitude_lower_rad=compression_amplitude_lower_rad,
        compression_amplitude_upper_rad=compression_amplitude_upper_rad,
        compression_envelope_skews=(
          () if resolved_skews is None else resolved_skews
        ),
        closure_tolerance_m=closure_tolerance_m,
        incoming_handoff=resolved_handoff,
        sample_count=resolution,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        attachment_pressure_tolerance=attachment_pressure_tolerance,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        euler_reconciliation_shock_angle_tolerance_rad=(
          euler_reconciliation_shock_angle_tolerance_rad
        ),
        euler_reconciliation_residual_tolerance=(
          euler_reconciliation_residual_tolerance
        ),
        maximum_segment_iterations=maximum_segment_iterations,
        maximum_boundary_iterations=maximum_boundary_iterations,
        maximum_shooting_iterations=maximum_shooting_iterations,
        maximum_bracket_scan_samples=maximum_bracket_scan_samples,
        maximum_attempts=maximum_attempts,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      closure = MocReflectedDomainGlobalPhysicalClosureResult(
        status=MocReflectedDomainGlobalPhysicalClosureStatus.GLOBAL_REMESH_FAILURE,
        source_band=source_band,
        global_remesh=None,
        global_euler=None,
        message=f'fresh global physical closure raised: {error}',
      )
    ####
    closures.append(closure)
    if closure.global_euler is not None:
      cases.append(
        MocReflectedDomainGlobalEulerShockBoundaryRefinementCase(
          resolution=resolution,
          result=closure.global_euler,
        )
      )
    ####
  ####

  if len(cases) == len(requested_resolutions):
    measurement = measure_moc_reflected_domain_global_euler_shock_boundary_refinement(
      tuple(cases),
    )
    message = (
      'fresh global physical-closure resolution ladder completed; '
      'independent global-Euler evidence remains below canonical and external '
      'promotion gates'
    )
  else:
    missing = tuple(
      resolution
      for resolution, closure in zip(
        requested_resolutions,
        closures,
        strict=True,
      )
      if closure.global_euler is None
    )
    measurement = _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.CASE_FAILURE,
      'fresh global physical closure did not retain a global Euler result at '
      f'resolution(s) {missing}',
    )
    message = measurement.message
  ####
  local_physical_closure_verified = bool(
    closures and all(closure.physical_closure_verified for closure in closures)
  )
  fidelity_isolation_verified = bool(
    closures
    and all(
      closure.chain_promotion_blocked
      and not closure.production_claim_allowed
      for closure in closures
    )
  )
  return MocReflectedDomainGlobalEulerShockBoundaryRefinementRun(
    source_band=source_band,
    requested_resolutions=requested_resolutions,
    closures=tuple(closures),
    cases=tuple(cases),
    measurement=measurement,
    source_band_fingerprint=source_fingerprint,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(
      len(closures) == len(requested_resolutions)
    ),
    local_physical_closure_verified=local_physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryCrossCase:
  """One named source band and its independent resolution ladder.

  A cross-case study keeps the physical cases separate from one another.  In
  particular, samples from a reflected case are never compared as if they
  were resolution samples from a mild-attached case.  The source-band
  fingerprint is derived from the retained solver-owned handoff so the
  aggregate report can prove which input each run used.
  """

  case_id: str
  regime: str
  source_band: MocReflectedDomainAlternatingSourceResult
  resolutions: tuple[int, ...]

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be a non-empty string')
    ####
    object.__setattr__(self, 'case_id', case_id)
    regime = str(self.regime)
    if not regime:
      raise ValueError('regime must be a non-empty string')
    ####
    object.__setattr__(self, 'regime', regime)
    if not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult'
      )
    ####
    try:
      resolutions = tuple(self.resolutions)
    except TypeError as error:
      raise ValueError(
        'resolutions must be an iterable of positive integers'
      ) from error
    ####
    if any(
      isinstance(resolution, bool)
      or not isinstance(resolution, int)
      or resolution < 1
      for resolution in resolutions
    ):
      raise ValueError('resolutions must contain positive integers')
    ####
    if not resolutions:
      raise ValueError('resolutions must not be empty')
    ####
    object.__setattr__(self, 'resolutions', resolutions)
  ####

  @property
  def source_band_fingerprint(self) -> str:
    """Deterministic identity for the source data used by this case."""

    return _source_band_fingerprint(self.source_band)
  ####

  @property
  def resolution_ladder_verified(self) -> bool:
    """Whether this case declares a strict two-or-more-point ladder."""

    return bool(
      len(self.resolutions) >= 2
      and all(
        right > left
        for left, right in zip(self.resolutions, self.resolutions[1:])
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'source_band_fingerprint': self.source_band_fingerprint,
      'resolutions': list(self.resolutions),
      'resolution_ladder_verified': self.resolution_ladder_verified,
      'source_status': self.source_band.status.value,
      'source_converged': self.source_band.converged,
      'source_node_count': self.source_band.node_count,
      'source_cell_count': self.source_band.cell_count,
    }
  ####
####


class MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus(str, Enum):
  """Outcome of the independent multi-case global-Euler study."""

  CONVERGED_LOCAL_CROSS_CASE = (
    'converged_local_global_euler_cross_case_refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_ID_FAILURE = 'global_euler_cross_case_case_id_failure'
  SOURCE_FAILURE = 'global_euler_cross_case_source_binding_failure'
  RESOLUTION_FAILURE = 'global_euler_cross_case_resolution_failure'
  CASE_FAILURE = 'global_euler_cross_case_case_failure'
  FIDELITY_FAILURE = 'global_euler_cross_case_fidelity_failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement:
  """Independent aggregate evidence for distinct physical case ladders.

  A converged measurement means every named case has its own converged local
  exact-Euler resolution ladder and the retained run is bound to the exact
  source fingerprint declared for that case.  It remains below canonical
  reflected/free-boundary, external-validation, and production gates.
  """

  status: MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus
  cases: tuple[MocReflectedDomainGlobalEulerShockBoundaryCrossCase, ...] = ()
  runs: tuple[MocReflectedDomainGlobalEulerShockBoundaryRefinementRun, ...] = ()
  case_ids: tuple[str, ...] = ()
  regimes: tuple[str, ...] = ()
  source_band_fingerprints: tuple[str, ...] = ()
  requested_resolutions: tuple[tuple[int, ...], ...] = ()
  run_statuses: tuple[str, ...] = ()
  downstream_boundary_models: tuple[tuple[str, ...], ...] = ()
  downstream_boundary_closure_verified: bool = False
  case_ids_verified: bool = False
  source_bindings_verified: bool = False
  distinct_source_band_fingerprints_verified: bool = False
  resolution_ladders_verified: bool = False
  case_runs_verified: bool = False
  local_physical_closure_verified: bool = False
  fidelity_isolation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus'
      )
    ####
    cases = tuple(self.cases)
    runs = tuple(self.runs)
    if len(cases) != len(runs):
      raise ValueError('cases and runs must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalEulerShockBoundaryCrossCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain '
        'MocReflectedDomainGlobalEulerShockBoundaryCrossCase values'
      )
    ####
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalEulerShockBoundaryRefinementRun,
      )
      for run in runs
    ):
      raise TypeError(
        'runs must contain '
        'MocReflectedDomainGlobalEulerShockBoundaryRefinementRun values'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'runs', runs)

    derived_case_ids = tuple(case.case_id for case in cases)
    if self.case_ids and tuple(self.case_ids) != derived_case_ids:
      raise ValueError('case_ids must match the supplied cases')
    ####
    object.__setattr__(self, 'case_ids', derived_case_ids)

    derived_regimes = tuple(case.regime for case in cases)
    if self.regimes and tuple(self.regimes) != derived_regimes:
      raise ValueError('regimes must match the supplied cases')
    ####
    object.__setattr__(self, 'regimes', derived_regimes)

    derived_fingerprints = tuple(
      case.source_band_fingerprint for case in cases
    )
    if (
      self.source_band_fingerprints
      and tuple(self.source_band_fingerprints) != derived_fingerprints
    ):
      raise ValueError(
        'source_band_fingerprints must match the supplied cases'
      )
    ####
    object.__setattr__(
      self,
      'source_band_fingerprints',
      derived_fingerprints,
    )

    derived_resolutions = tuple(
      tuple(case.resolutions) for case in cases
    )
    if (
      self.requested_resolutions
      and tuple(tuple(value) for value in self.requested_resolutions)
      != derived_resolutions
    ):
      raise ValueError(
        'requested_resolutions must match the supplied cases'
      )
    ####
    object.__setattr__(self, 'requested_resolutions', derived_resolutions)

    derived_statuses = tuple(
      run.measurement.status.value for run in runs
    )
    if self.run_statuses and tuple(self.run_statuses) != derived_statuses:
      raise ValueError('run_statuses must match the supplied runs')
    ####
    object.__setattr__(self, 'run_statuses', derived_statuses)

    derived_downstream_models = tuple(
      tuple(closure.downstream_boundary_model for closure in run.closures)
      for run in runs
    )
    if self.downstream_boundary_models and tuple(
      tuple(value) for value in self.downstream_boundary_models
    ) != derived_downstream_models:
      raise ValueError(
        'downstream_boundary_models must match the supplied runs'
      )
    ####
    object.__setattr__(
      self,
      'downstream_boundary_models',
      derived_downstream_models,
    )
    derived_downstream_gate = bool(
      runs
      and all(
        closure.downstream_boundary_closure_verified
        for run in runs
        for closure in run.closures
      )
    )
    if self.downstream_boundary_closure_verified != derived_downstream_gate:
      raise ValueError(
        'downstream_boundary_closure_verified must match the supplied runs'
      )
    ####
    object.__setattr__(
      self,
      'downstream_boundary_closure_verified',
      derived_downstream_gate,
    )

    for name in (
      'case_ids_verified',
      'source_bindings_verified',
      'distinct_source_band_fingerprints_verified',
      'resolution_ladders_verified',
      'case_runs_verified',
      'local_physical_closure_verified',
      'fidelity_isolation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('cross-case refinement must retain promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'cross-case refinement cannot claim production validity'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'cross-case refinement must retain the external-validation gate'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus
      .CONVERGED_LOCAL_CROSS_CASE
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and len(self.cases) >= 2
      and self.case_ids_verified
      and self.source_bindings_verified
      and self.distinct_source_band_fingerprints_verified
      and self.resolution_ladders_verified
      and self.case_runs_verified
      and self.local_physical_closure_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'case_ids': list(self.case_ids),
      'regimes': list(self.regimes),
      'source_band_fingerprints': list(self.source_band_fingerprints),
      'requested_resolutions': [
        list(resolutions) for resolutions in self.requested_resolutions
      ],
      'run_statuses': list(self.run_statuses),
      'downstream_boundary_models': [
        list(models) for models in self.downstream_boundary_models
      ],
      'cases': [case.as_report() for case in self.cases],
      'runs': [run.as_report() for run in self.runs],
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'source_bindings_verified': self.source_bindings_verified,
        'distinct_source_band_fingerprints_verified': (
          self.distinct_source_band_fingerprints_verified
        ),
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'case_runs_verified': self.case_runs_verified,
        'local_physical_closure_verified': (
          self.local_physical_closure_verified
        ),
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'physical_closure_verified': False,
        'canonical_free_boundary_verified': False,
        'canonical_euler_verified': False,
        'external_validation_verified': False,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'physical_closure_verified': False,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'external_validation_required': self.external_validation_required,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'independent-global-euler-cross-case-refinement; '
        'local-research-field-only'
      ),
      'message': self.message,
    }
  ####
####


def _cross_case_measurement_failure(
  status: MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus,
  message: str,
  *,
  cases: Sequence[MocReflectedDomainGlobalEulerShockBoundaryCrossCase] = (),
  runs: Sequence[MocReflectedDomainGlobalEulerShockBoundaryRefinementRun] = (),
) -> MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement:
  case_values = tuple(cases)
  run_values = tuple(runs)
  paired = min(len(case_values), len(run_values))
  return MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement(
    status=status,
    cases=case_values[:paired],
    runs=run_values[:paired],
    message=message,
  )
####


def measure_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalEulerShockBoundaryCrossCase],
  runs: Sequence[MocReflectedDomainGlobalEulerShockBoundaryRefinementRun],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement:
  """Independently audit named reflected/mild-attached case ladders.

  This function does not rerun a solver.  Each nested run has already
  independently audited its own resolution ladder; this operator verifies
  that the case labels, source fingerprints, and run outputs are aligned
  before aggregating those results.  It never compares residuals between
  physically different cases as though they formed one resolution sequence.
  """

  try:
    case_values = tuple(cases)
    run_values = tuple(runs)
  except TypeError:
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.INVALID_INPUT,
      'cross-case cases and runs must be iterable',
    )
  ####
  if len(case_values) < 2 or len(run_values) < 2:
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.INVALID_INPUT,
      'cross-case refinement requires at least two named cases',
    )
  ####
  if len(case_values) != len(run_values):
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.INVALID_INPUT,
      'cross-case cases and runs must have equal lengths',
      cases=case_values,
      runs=run_values,
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalEulerShockBoundaryCrossCase,
    )
    for case in case_values
  ):
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.INVALID_INPUT,
      'cases must contain typed cross-case values',
    )
  ####
  if any(
    not isinstance(
      run,
      MocReflectedDomainGlobalEulerShockBoundaryRefinementRun,
    )
    for run in run_values
  ):
    return _cross_case_measurement_failure(
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.INVALID_INPUT,
      'runs must contain typed global-Euler refinement runs',
    )
  ####

  case_ids = tuple(case.case_id for case in case_values)
  case_ids_verified = bool(
    len(set(case_ids)) == len(case_ids)
    and (
      expected_case_ids is None
      or case_ids == tuple(str(value) for value in expected_case_ids)
    )
  )
  source_fingerprints = tuple(
    case.source_band_fingerprint for case in case_values
  )
  source_bindings_verified = all(
    run.source_band_fingerprint == fingerprint
    for case, run, fingerprint in zip(
      case_values,
      run_values,
      source_fingerprints,
      strict=True,
    )
  )
  distinct_source_band_fingerprints_verified = bool(
    len(set(source_fingerprints)) == len(source_fingerprints)
  )
  resolution_ladders_verified = bool(
    all(case.resolution_ladder_verified for case in case_values)
    and all(
      run.requested_resolutions == case.resolutions
      for case, run in zip(case_values, run_values, strict=True)
    )
  )
  case_runs_verified = all(
    run.local_consistency_verified
    and run.measurement.converged
    for run in run_values
  )
  local_physical_closure_verified = all(
    run.local_physical_closure_verified for run in run_values
  )
  fidelity_isolation_verified = all(
    run.fidelity_isolation_verified
    and run.chain_promotion_blocked
    and not run.production_claim_allowed
    for run in run_values
  )
  if not case_ids_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus
      .CASE_ID_FAILURE
    )
    message = 'cross-case IDs are duplicated or do not match expected order'
  elif not source_bindings_verified or not distinct_source_band_fingerprints_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.SOURCE_FAILURE
    )
    message = (
      'cross-case runs are not bound to distinct declared source-band '
      'fingerprints'
    )
  elif not resolution_ladders_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus
      .RESOLUTION_FAILURE
    )
    message = (
      'one or more named cases does not retain the same strict resolution '
      'ladder used by its run'
    )
  elif not case_runs_verified or not local_physical_closure_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus.CASE_FAILURE
    )
    message = 'one or more named global-Euler case ladders failed local audit'
  elif not fidelity_isolation_verified:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus
      .FIDELITY_FAILURE
    )
    message = 'cross-case aggregation weakened the fidelity or promotion boundary'
  else:
    status = (
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseStatus
      .CONVERGED_LOCAL_CROSS_CASE
    )
    message = (
      'named reflected/mild-attached global-Euler ladders passed independently; '
      'cross-case evidence remains local research evidence below canonical and '
      'external promotion gates'
    )
  ####
  return MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement(
    status=status,
    cases=case_values,
    runs=run_values,
    case_ids=case_ids,
    regimes=tuple(case.regime for case in case_values),
    source_band_fingerprints=source_fingerprints,
    requested_resolutions=tuple(case.resolutions for case in case_values),
    run_statuses=tuple(run.measurement.status.value for run in run_values),
    downstream_boundary_models=tuple(
      tuple(closure.downstream_boundary_model for closure in run.closures)
      for run in run_values
    ),
    downstream_boundary_closure_verified=bool(
      run_values
      and all(
        closure.downstream_boundary_closure_verified
        for run in run_values
        for closure in run.closures
      )
    ),
    case_ids_verified=case_ids_verified,
    source_bindings_verified=source_bindings_verified,
    distinct_source_band_fingerprints_verified=(
      distinct_source_band_fingerprints_verified
    ),
    resolution_ladders_verified=resolution_ladders_verified,
    case_runs_verified=case_runs_verified,
    local_physical_closure_verified=local_physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain-global-euler-shock-boundary-cross-case-refinement-run'
)


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalEulerShockBoundaryCrossCaseRun:
  """Fresh execution of every named case in a separate resolution ladder."""

  cases: tuple[MocReflectedDomainGlobalEulerShockBoundaryCrossCase, ...]
  runs: tuple[MocReflectedDomainGlobalEulerShockBoundaryRefinementRun, ...]
  measurement: MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool
  local_physical_closure_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    runs = tuple(self.runs)
    if len(cases) != len(runs):
      raise ValueError('cases and runs must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalEulerShockBoundaryCrossCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed cross-case values')
    ####
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalEulerShockBoundaryRefinementRun,
      )
      for run in runs
    ):
      raise TypeError('runs must contain typed global-Euler refinement runs')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainGlobalEulerShockBoundaryCrossCaseMeasurement,
    ):
      raise TypeError('measurement must be a typed cross-case measurement')
    ####
    if self.measurement.cases and tuple(self.measurement.cases) != cases:
      raise ValueError('measurement cases must match retained cross-case values')
    ####
    if self.measurement.runs and tuple(self.measurement.runs) != runs:
      raise ValueError('measurement runs must match retained run values')
    ####
    configuration = tuple(self.configuration)
    if any(
      not isinstance(item, tuple)
      or len(item) != 2
      or not isinstance(item[0], str)
      for item in configuration
    ):
      raise ValueError('configuration must contain (name, value) pairs')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'runs', runs)
    object.__setattr__(self, 'configuration', configuration)
    configuration_fingerprint = str(self.configuration_fingerprint)
    if not configuration_fingerprint:
      raise ValueError('configuration_fingerprint must be non-empty')
    ####
    object.__setattr__(
      self,
      'configuration_fingerprint',
      configuration_fingerprint,
    )
    for name in (
      'fresh_solver_invocation_verified',
      'local_physical_closure_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.measurement.converged
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.measurement.local_consistency_verified
      and len(self.cases) >= 2
      and len(self.runs) == len(self.cases)
      and self.fresh_solver_invocation_verified
      and self.local_physical_closure_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return bool(
      self.runs
      and all(run.chain_promotion_blocked for run in self.runs)
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """Whether every named case and resolution has downstream closure."""

    return bool(
      self.runs
      and all(
        closure.downstream_boundary_closure_verified
        for run in self.runs
        for closure in run.closures
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.measurement.status.value,
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'configuration': dict(self.configuration),
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': [case.as_report() for case in self.cases],
      'runs': [run.as_report() for run in self.runs],
      'measurement': self.measurement.as_report(),
      'checks': {
        'fresh_solver_invocation_verified': (
          self.fresh_solver_invocation_verified
        ),
        'local_physical_closure_verified': (
          self.local_physical_closure_verified
        ),
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'physical_closure_verified': False,
        'canonical_free_boundary_verified': False,
        'canonical_euler_verified': False,
        'external_validation_verified': False,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'physical_closure_verified': False,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'fresh-global-euler-cross-case-refinement; '
        'local-research-field-only'
      ),
      'message': self.message,
    }
  ####
####


def run_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalEulerShockBoundaryCrossCase],
  **runner_options: Any,
) -> MocReflectedDomainGlobalEulerShockBoundaryCrossCaseRun:
  """Run each named case through the existing fresh-ladder operator.

  ``runner_options`` are the keyword options accepted by
  ``run_moc_reflected_domain_global_euler_shock_boundary_refinement``.  The
  source band and resolution ladder are owned by each named case and cannot
  be overridden through this mapping.
  """

  try:
    case_values = tuple(cases)
  except TypeError as error:
    raise ValueError('cases must be an iterable of typed cross-case values') from error
  ####
  if len(case_values) < 2:
    raise ValueError('cross-case refinement requires at least two named cases')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalEulerShockBoundaryCrossCase,
    )
    for case in case_values
  ):
    raise TypeError('cases must contain typed cross-case values')
  ####
  forbidden = {'source_band', 'resolutions'}
  if forbidden.intersection(runner_options):
    raise ValueError(
      'runner_options cannot override source_band or resolutions owned by a case'
    )
  ####

  runs = tuple(
    run_moc_reflected_domain_global_euler_shock_boundary_refinement(
      case.source_band,
      case.resolutions,
      **runner_options,
    )
    for case in case_values
  )
  measurement = (
    measure_moc_reflected_domain_global_euler_shock_boundary_cross_case_refinement(
      case_values,
      runs,
    )
  )
  configuration_payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_EULER_SHOCK_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID
    ),
    'cases': [
      {
        'case_id': case.case_id,
        'regime': case.regime,
        'source_band_fingerprint': case.source_band_fingerprint,
        'resolutions': list(case.resolutions),
      }
      for case in case_values
    ],
    'runner_options': runner_options,
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  local_physical_closure_verified = bool(
    runs and all(run.local_physical_closure_verified for run in runs)
  )
  fidelity_isolation_verified = bool(
    runs
    and all(
      run.fidelity_isolation_verified
      and run.chain_promotion_blocked
      and not run.production_claim_allowed
      for run in runs
    )
  )
  return MocReflectedDomainGlobalEulerShockBoundaryCrossCaseRun(
    cases=case_values,
    runs=runs,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=_refinement_fingerprint(configuration_payload),
    fresh_solver_invocation_verified=all(
      run.fresh_solver_invocation_verified for run in runs
    ),
    local_physical_closure_verified=local_physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh global-Euler ladders executed independently for every named case; '
      'canonical and external promotion gates remain pending'
    ),
  )
####
