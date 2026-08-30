"""Independent refinement evidence for the global reflected Euler bridge.

The global reflected-domain bridge now produces a locally closed exact-Euler
field, but that field is still a research result.  This module audits a
caller-supplied resolution ladder without rerunning any solver, changing a
shock path, or turning a refined field into a continued physical cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainGlobalEulerShockBoundaryResult,
)
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
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalEulerShockBoundaryResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalEulerShockBoundaryResult'
      )
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
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
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
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)

    derived_resolutions = tuple(case.resolution for case in cases)
    if self.resolutions and tuple(self.resolutions) != derived_resolutions:
      raise ValueError('resolutions must match the supplied case resolutions')
    object.__setattr__(self, 'resolutions', derived_resolutions)

    for name in (
      'shock_sample_counts',
      'field_cell_counts',
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
      'source_frontier_x_m',
      'maximum_cell_euler_residuals',
      'maximum_endpoint_tangent_residuals_rad',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(
          f'{name} must contain finite nonnegative values'
        )
      object.__setattr__(self, name, values)

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
    for name in ('residual_tolerance', 'frontier_tolerance_m'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    claim_status = str(self.claim_status)
    if not claim_status:
      raise ValueError('claim_status must be a non-empty string')
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
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'cases must be an iterable of global Euler refinement cases',
      residual_tolerance=residual_tolerance_value,
      frontier_tolerance_m=frontier_tolerance_value,
    )
  if not retained_cases:
    return _failure(
      MocReflectedDomainGlobalEulerShockBoundaryRefinementStatus.INVALID_INPUT,
      'at least one global Euler refinement case is required',
      residual_tolerance=residual_tolerance_value,
      frontier_tolerance_m=frontier_tolerance_value,
    )
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
  return _failure(status, message, **common)
  ####
