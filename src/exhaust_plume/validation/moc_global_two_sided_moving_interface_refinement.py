"""Cross-case refinement audit for the global two-sided moving-interface seam.

This operator audits the global-closure adapter separately from the lower-level
interface-law ladder.  Each case must retain a fresh global closure identity,
an independently remeasured moving/joint audit, and a stable response mode
across increasing shock resolutions.  The result is research evidence only:
it cannot turn a locally refining interior-probe response into canonical
mixed-regime closure or a production shock-cell claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
)
from exhaust_plume.validation.moc_euler_two_sided_interface_field_joint_closure import (
  MocEulerTwoSidedInterfaceFieldJointClosureAudit,
  measure_moc_euler_two_sided_interface_field_joint_closure,
)
from exhaust_plume.validation.moc_euler_two_sided_moving_interface import (
  MocEulerTwoSidedMovingInterfaceAudit,
  measure_moc_euler_two_sided_moving_interface,
)

__all__ = (
  'MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocGlobalTwoSidedMovingInterfaceRefinementCase',
  'MocGlobalTwoSidedMovingInterfaceRefinementStatus',
  'MocGlobalTwoSidedMovingInterfaceRefinementMeasurement',
  'measure_moc_global_two_sided_moving_interface_refinement',
)


MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.global-two-sided-moving-interface-refinement-audit-v1'
)


@dataclass(frozen=True, slots=True)
class MocGlobalTwoSidedMovingInterfaceRefinementCase:
  """One freshly solved global adapter result at a declared resolution."""

  case_id: str
  resolution_sample_count: int
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if (
      isinstance(self.resolution_sample_count, bool)
      or not isinstance(self.resolution_sample_count, int)
      or self.resolution_sample_count < 3
    ):
      raise ValueError('resolution_sample_count must be an integer >= 3')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
    ):
      raise TypeError(
        'result must be a MocReflectedDomainGlobalTwoSidedMovingInterfaceResult'
      )
    ####
    boundary = self.result.shock_boundary
    if boundary is not None and len(boundary.shock_points_m) != (
      self.resolution_sample_count
    ):
      raise ValueError(
        'resolution_sample_count must match the exact retained global shock '
        'sample count'
      )
    ####
    object.__setattr__(self, 'case_id', case_id)
  ####


class MocGlobalTwoSidedMovingInterfaceRefinementStatus(str, Enum):
  """Typed outcomes of the global adapter refinement audit."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged-global-two-sided-moving-interface-local-refinement'
  )
  CONVERGED_CROSS_CASE_REFINEMENT = (
    'converged-global-two-sided-moving-interface-cross-case-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'global-two-sided-moving-interface-refinement-case-failure'
  RESOLUTION_ORDER_FAILURE = (
    'global-two-sided-moving-interface-refinement-resolution-order-failure'
  )
  RESPONSE_MODE_FAILURE = (
    'global-two-sided-moving-interface-refinement-response-mode-failure'
  )
  RESIDUAL_FAILURE = (
    'global-two-sided-moving-interface-refinement-residual-failure'
  )
  FLAG_FAILURE = 'global-two-sided-moving-interface-refinement-flag-failure'


@dataclass(frozen=True, slots=True)
class MocGlobalTwoSidedMovingInterfaceRefinementMeasurement:
  """Independent global-adapter evidence below the production ceiling."""

  status: MocGlobalTwoSidedMovingInterfaceRefinementStatus
  cases: tuple[MocGlobalTwoSidedMovingInterfaceRefinementCase, ...]
  moving_audits: tuple[MocEulerTwoSidedMovingInterfaceAudit, ...]
  joint_audits: tuple[MocEulerTwoSidedInterfaceFieldJointClosureAudit, ...]
  case_ids: tuple[str, ...]
  resolution_sample_counts: tuple[int, ...]
  source_closure_fingerprints: tuple[str | None, ...]
  maximum_interface_normal_speeds_m_s: tuple[float, ...]
  maximum_mass_flux_residuals_kg_m2_s: tuple[float, ...]
  maximum_normal_momentum_residuals_Pa: tuple[float, ...]
  maximum_energy_flux_residuals_W_m2: tuple[float, ...]
  case_audits_verified: bool
  case_identity_verified: bool
  closure_identity_verified: bool
  response_mode_identity_verified: bool
  resolution_order_verified: bool
  residuals_finite: bool
  momentum_nonincreasing_verified: bool
  momentum_reduction_verified: bool
  cross_case_verified: bool
  local_refinement_verified: bool
  refinement_convergence_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  refinement_tolerance: float = 1.0e-8
  message: str = ''
  operator_id: str = (
    MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_REFINEMENT_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocGlobalTwoSidedMovingInterfaceRefinementStatus,
    ):
      raise TypeError('status must be a global moving-interface refinement status')
    ####
    cases = tuple(self.cases)
    moving_audits = tuple(self.moving_audits)
    joint_audits = tuple(self.joint_audits)
    if not (
      len(cases) == len(moving_audits) == len(joint_audits)
    ):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(case, MocGlobalTwoSidedMovingInterfaceRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed global moving-interface cases')
    ####
    if any(
      not isinstance(audit, MocEulerTwoSidedMovingInterfaceAudit)
      for audit in moving_audits
    ):
      raise TypeError('moving_audits must contain typed moving-interface audits')
    ####
    if any(
      not isinstance(audit, MocEulerTwoSidedInterfaceFieldJointClosureAudit)
      for audit in joint_audits
    ):
      raise TypeError('joint_audits must contain typed joint-closure audits')
    ####
    case_ids = tuple(str(value) for value in self.case_ids)
    resolutions = tuple(self.resolution_sample_counts)
    fingerprints = tuple(self.source_closure_fingerprints)
    speeds = tuple(float(value) for value in self.maximum_interface_normal_speeds_m_s)
    mass = tuple(float(value) for value in self.maximum_mass_flux_residuals_kg_m2_s)
    momentum = tuple(float(value) for value in self.maximum_normal_momentum_residuals_Pa)
    energy = tuple(float(value) for value in self.maximum_energy_flux_residuals_W_m2)
    if not (
      len(cases)
      == len(case_ids)
      == len(resolutions)
      == len(fingerprints)
      == len(speeds)
      == len(mass)
      == len(momentum)
      == len(energy)
    ):
      raise ValueError('refinement summaries must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in resolutions
    ):
      raise ValueError('resolution sample counts must be nonnegative integers')
    ####
    for name, values in (
      ('maximum_interface_normal_speeds_m_s', speeds),
      ('maximum_mass_flux_residuals_kg_m2_s', mass),
      ('maximum_normal_momentum_residuals_Pa', momentum),
      ('maximum_energy_flux_residuals_W_m2', energy),
    ):
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
    ####
    for name in (
      'case_audits_verified',
      'case_identity_verified',
      'closure_identity_verified',
      'response_mode_identity_verified',
      'resolution_order_verified',
      'residuals_finite',
      'momentum_nonincreasing_verified',
      'momentum_reduction_verified',
      'cross_case_verified',
      'local_refinement_verified',
      'refinement_convergence_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    tolerance = float(self.refinement_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('refinement_tolerance must be finite and positive')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'moving_audits', moving_audits)
    object.__setattr__(self, 'joint_audits', joint_audits)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'maximum_interface_normal_speeds_m_s', speeds)
    object.__setattr__(self, 'maximum_mass_flux_residuals_kg_m2_s', mass)
    object.__setattr__(self, 'maximum_normal_momentum_residuals_Pa', momentum)
    object.__setattr__(self, 'maximum_energy_flux_residuals_W_m2', energy)
    object.__setattr__(self, 'refinement_tolerance', tolerance)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in (
        MocGlobalTwoSidedMovingInterfaceRefinementStatus
        .CONVERGED_LOCAL_REFINEMENT,
        MocGlobalTwoSidedMovingInterfaceRefinementStatus
        .CONVERGED_CROSS_CASE_REFINEMENT,
      )
      and self.local_refinement_verified
      and self.refinement_convergence_verified
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
      'maximum_interface_normal_speeds_m_s': (
        self.maximum_interface_normal_speeds_m_s
      ),
      'maximum_mass_flux_residuals_kg_m2_s': (
        self.maximum_mass_flux_residuals_kg_m2_s
      ),
      'maximum_normal_momentum_residuals_Pa': (
        self.maximum_normal_momentum_residuals_Pa
      ),
      'maximum_energy_flux_residuals_W_m2': (
        self.maximum_energy_flux_residuals_W_m2
      ),
      'case_audits_verified': self.case_audits_verified,
      'case_identity_verified': self.case_identity_verified,
      'closure_identity_verified': self.closure_identity_verified,
      'response_mode_identity_verified': self.response_mode_identity_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'residuals_finite': self.residuals_finite,
      'momentum_nonincreasing_verified': self.momentum_nonincreasing_verified,
      'momentum_reduction_verified': self.momentum_reduction_verified,
      'cross_case_verified': self.cross_case_verified,
      'local_refinement_verified': self.local_refinement_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'refinement_tolerance': self.refinement_tolerance,
      'cases': tuple(case.result.as_report() for case in self.cases),
      'moving_audits': tuple(audit.as_report() for audit in self.moving_audits),
      'joint_audits': tuple(audit.as_report() for audit in self.joint_audits),
      'message': self.message,
    }
  ####


def _failure(
  status: MocGlobalTwoSidedMovingInterfaceRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocGlobalTwoSidedMovingInterfaceRefinementCase] = (),
  moving_audits: Sequence[MocEulerTwoSidedMovingInterfaceAudit] = (),
  joint_audits: Sequence[MocEulerTwoSidedInterfaceFieldJointClosureAudit] = (),
  refinement_tolerance: float = 1.0e-8,
  **kwargs: object,
) -> MocGlobalTwoSidedMovingInterfaceRefinementMeasurement:
  case_values = tuple(cases)
  moving_values = tuple(moving_audits)
  joint_values = tuple(joint_audits)
  return MocGlobalTwoSidedMovingInterfaceRefinementMeasurement(
    status=status,
    cases=case_values,
    moving_audits=moving_values,
    joint_audits=joint_values,
    case_ids=tuple(case.case_id for case in case_values),
    resolution_sample_counts=tuple(
      case.resolution_sample_count for case in case_values
    ),
    source_closure_fingerprints=tuple(
      case.result.source_closure_fingerprint for case in case_values
    ),
    maximum_interface_normal_speeds_m_s=tuple(
      float(value) for value in kwargs.pop('speeds', ())
    ),
    maximum_mass_flux_residuals_kg_m2_s=tuple(
      float(value) for value in kwargs.pop('mass', ())
    ),
    maximum_normal_momentum_residuals_Pa=tuple(
      float(value) for value in kwargs.pop('momentum', ())
    ),
    maximum_energy_flux_residuals_W_m2=tuple(
      float(value) for value in kwargs.pop('energy', ())
    ),
    case_audits_verified=bool(kwargs.pop('case_audits_verified', False)),
    case_identity_verified=bool(kwargs.pop('case_identity_verified', False)),
    closure_identity_verified=bool(kwargs.pop('closure_identity_verified', False)),
    response_mode_identity_verified=bool(
      kwargs.pop('response_mode_identity_verified', False)
    ),
    resolution_order_verified=bool(kwargs.pop('resolution_order_verified', False)),
    residuals_finite=bool(kwargs.pop('residuals_finite', False)),
    momentum_nonincreasing_verified=bool(
      kwargs.pop('momentum_nonincreasing_verified', False)
    ),
    momentum_reduction_verified=bool(
      kwargs.pop('momentum_reduction_verified', False)
    ),
    cross_case_verified=bool(kwargs.pop('cross_case_verified', False)),
    local_refinement_verified=bool(kwargs.pop('local_refinement_verified', False)),
    refinement_convergence_verified=bool(
      kwargs.pop('refinement_convergence_verified', False)
    ),
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=bool(kwargs.pop('chain_promotion_blocked', True)),
    production_claim_allowed=bool(kwargs.pop('production_claim_allowed', False)),
    fidelity_flags_verified=bool(kwargs.pop('fidelity_flags_verified', False)),
    refinement_tolerance=refinement_tolerance,
    message=message,
  )


def _response_signature(
  case: MocGlobalTwoSidedMovingInterfaceRefinementCase,
) -> tuple[object, ...] | None:
  result = case.result
  request = result.request
  moving = result.moving_result
  if request is None or moving is None or not moving.records:
    return None
  ####
  response = moving.records[-1].response
  if response is None:
    return None
  ####
  return (
    response.response_source,
    response.law_id,
    round(request.downstream_probe_fraction, 12),
    request.anchor_endpoint_samples,
    request.branch.value,
    response.stationary_equilibrium_candidate,
  )


def _response_metrics(
  case: MocGlobalTwoSidedMovingInterfaceRefinementCase,
) -> tuple[float, float, float, float] | None:
  moving = case.result.moving_result
  if moving is None or not moving.records:
    return None
  ####
  response = moving.records[-1].response
  if response is None:
    return None
  ####
  return (
    response.maximum_normal_displacement_m,
    response.maximum_mass_flux_residual_kg_m2_s,
    response.maximum_normal_momentum_residual_Pa,
    response.maximum_energy_flux_residual_W_m2,
  )


def measure_moc_global_two_sided_moving_interface_refinement(
  cases: Sequence[MocGlobalTwoSidedMovingInterfaceRefinementCase],
  *,
  refinement_tolerance: float = 1.0e-8,
) -> MocGlobalTwoSidedMovingInterfaceRefinementMeasurement:
  """Independently audit fresh global-adapter results by case and resolution."""

  try:
    tolerance = float(refinement_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.INVALID_INPUT,
      'refinement_tolerance must be numeric',
    )
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.INVALID_INPUT,
      'refinement_tolerance must be finite and positive',
      refinement_tolerance=tolerance,
    )
  ####
  case_values = tuple(cases)
  if len(case_values) < 2:
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.INVALID_INPUT,
      'global two-sided refinement requires at least two cases',
      refinement_tolerance=tolerance,
    )
  ####
  if any(
    not isinstance(case, MocGlobalTwoSidedMovingInterfaceRefinementCase)
    for case in case_values
  ):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.INVALID_INPUT,
      'cases must contain typed global two-sided refinement cases',
      refinement_tolerance=tolerance,
    )
  ####
  moving_results = tuple(case.result.moving_result for case in case_values)
  if any(result is None for result in moving_results):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.CASE_FAILURE,
      'every global two-sided case must retain a moving-interface result',
      cases=case_values,
      refinement_tolerance=tolerance,
    )
  ####
  try:
    moving_audits = tuple(
      measure_moc_euler_two_sided_moving_interface(result)
      for result in moving_results
      if result is not None
    )
    joint_audits = tuple(
      measure_moc_euler_two_sided_interface_field_joint_closure(result)
      for result in moving_results
      if result is not None
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.CASE_FAILURE,
      f'independent global two-sided audit raised: {error}',
      cases=case_values,
      refinement_tolerance=tolerance,
    )
  ####
  metrics = tuple(_response_metrics(case) for case in case_values)
  if any(metric is None for metric in metrics):
    return _failure(
      MocGlobalTwoSidedMovingInterfaceRefinementStatus.CASE_FAILURE,
      'every global two-sided case must retain a final response with finite '
      'native residual channels',
      cases=case_values,
      moving_audits=moving_audits,
      joint_audits=joint_audits,
      refinement_tolerance=tolerance,
    )
  ####
  resolved_metrics = tuple(metric for metric in metrics if metric is not None)
  speeds = tuple(metric[0] for metric in resolved_metrics)
  mass = tuple(metric[1] for metric in resolved_metrics)
  momentum = tuple(metric[2] for metric in resolved_metrics)
  energy = tuple(metric[3] for metric in resolved_metrics)
  case_ids = tuple(case.case_id for case in case_values)
  grouped_indices: dict[str, list[int]] = {}
  for index, case_id in enumerate(case_ids):
    grouped_indices.setdefault(case_id, []).append(index)
  ####
  case_audits_verified = bool(
    all(audit.converged for audit in moving_audits)
    and all(audit.converged for audit in joint_audits)
    and all(case.result.converged for case in case_values)
  )
  case_identity_verified = bool(
    all(case.result.request is not None for case in case_values)
    and all(case.result.source_closure_fingerprint for case in case_values)
  )
  fingerprints = tuple(
    case.result.source_closure_fingerprint for case in case_values
  )
  closure_identity_verified = bool(
    case_identity_verified
    and all(
      len({fingerprints[index] for index in indices}) == len(indices)
      for indices in grouped_indices.values()
    )
  )
  response_signatures = tuple(
    _response_signature(case) for case in case_values
  )
  response_mode_identity_verified = bool(
    all(signature is not None for signature in response_signatures)
    and all(
      len({response_signatures[index] for index in indices}) == 1
      for indices in grouped_indices.values()
    )
  )
  resolution_order_verified = bool(
    all(
      all(
        case_values[right].resolution_sample_count
        > case_values[left].resolution_sample_count
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped_indices.values()
    )
  )
  residuals_finite = all(
    isfinite(value) and value >= 0.0
    for value in (*speeds, *mass, *momentum, *energy)
  )
  momentum_nonincreasing_verified = bool(
    residuals_finite
    and all(
      all(
        momentum[right] <= momentum[left] * (1.0 + tolerance)
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped_indices.values()
    )
  )
  momentum_reduction_verified = bool(
    residuals_finite
    and all(
      len(indices) >= 2
      and momentum[indices[-1]] < momentum[indices[0]]
      for indices in grouped_indices.values()
    )
  )
  group_fingerprints = tuple(
    tuple(fingerprints[index] for index in indices)
    for indices in grouped_indices.values()
  )
  cross_case_verified = bool(
    len(grouped_indices) >= 2
    and all(len(indices) >= 3 for indices in grouped_indices.values())
    and len(set(group_fingerprints)) == len(group_fingerprints)
  )
  fidelity_flags_verified = bool(
    all(case.result.chain_promotion_blocked for case in case_values)
    and all(not case.result.production_claim_allowed for case in case_values)
    and all(not case.result.physical_closure_verified for case in case_values)
  )
  local_refinement_verified = bool(
    case_audits_verified
    and case_identity_verified
    and closure_identity_verified
    and response_mode_identity_verified
    and resolution_order_verified
    and residuals_finite
    and momentum_nonincreasing_verified
    and momentum_reduction_verified
    and fidelity_flags_verified
  )
  refinement_convergence_verified = bool(
    local_refinement_verified
    and all(len(indices) >= 3 for indices in grouped_indices.values())
  )
  ####
  if not case_audits_verified:
    status = MocGlobalTwoSidedMovingInterfaceRefinementStatus.CASE_FAILURE
    message = 'one or more global two-sided cases failed an independent local audit'
  elif not closure_identity_verified:
    status = MocGlobalTwoSidedMovingInterfaceRefinementStatus.CASE_FAILURE
    message = 'global closure fingerprints are missing or reused within a case ladder'
  elif not resolution_order_verified:
    status = MocGlobalTwoSidedMovingInterfaceRefinementStatus.RESOLUTION_ORDER_FAILURE
    message = 'global two-sided cases are not strictly resolution ordered'
  elif not response_mode_identity_verified:
    status = MocGlobalTwoSidedMovingInterfaceRefinementStatus.RESPONSE_MODE_FAILURE
    message = (
      'global two-sided refinement cases mix response modes within a declared '
      'case ladder'
    )
  elif not (
    residuals_finite
    and momentum_nonincreasing_verified
    and momentum_reduction_verified
  ):
    status = MocGlobalTwoSidedMovingInterfaceRefinementStatus.RESIDUAL_FAILURE
    message = (
      'global two-sided native residuals did not satisfy the declared '
      'research refinement trend'
    )
  elif not fidelity_flags_verified:
    status = MocGlobalTwoSidedMovingInterfaceRefinementStatus.FLAG_FAILURE
    message = 'global two-sided refinement weakened its non-promotion flags'
  elif cross_case_verified:
    status = (
      MocGlobalTwoSidedMovingInterfaceRefinementStatus
      .CONVERGED_CROSS_CASE_REFINEMENT
    )
    message = (
      'independent global two-sided audits verified locally refining response '
      'ladders across distinct closure cases; canonical closure, physical '
      'shock-cell, and production gates remain open'
    )
  else:
    status = (
      MocGlobalTwoSidedMovingInterfaceRefinementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )
    message = (
      'independent global two-sided audits verified a locally refining '
      'closure ladder; cross-case, canonical closure, physical shock-cell, '
      'and production gates remain open'
    )
  ####
  return _failure(
    status,
    message,
    cases=case_values,
    moving_audits=moving_audits,
    joint_audits=joint_audits,
    speeds=speeds,
    mass=mass,
    momentum=momentum,
    energy=energy,
    case_audits_verified=case_audits_verified,
    case_identity_verified=case_identity_verified,
    closure_identity_verified=closure_identity_verified,
    response_mode_identity_verified=response_mode_identity_verified,
    resolution_order_verified=resolution_order_verified,
    residuals_finite=residuals_finite,
    momentum_nonincreasing_verified=momentum_nonincreasing_verified,
    momentum_reduction_verified=momentum_reduction_verified,
    cross_case_verified=cross_case_verified,
    local_refinement_verified=local_refinement_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    refinement_tolerance=tolerance,
  )
