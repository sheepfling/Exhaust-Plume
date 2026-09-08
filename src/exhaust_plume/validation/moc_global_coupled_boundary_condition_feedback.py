"""Bounded downstream/global feedback through a solver-owned pressure frame.

The existing downstream feedback runner and the global frontier boundary
consumer are useful independently, but a product-facing validation surface
needs one typed outer operation that binds them without losing provenance:

``global closure -> coupled downstream response -> exact frontier request ->
lineage-bound base/overlay pressure frame -> fresh global ambient re-solve``.

This module deliberately remains below canonical mixed-regime closure.  It
records the pressure, tangent, entropy, and conservative residual channels and
keeps the production and chain-promotion gates closed when the moving
solver-owned frame cannot be covered.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
)
from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  build_reflected_domain_global_frontier_reconciliation_request,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_global_coupled_downstream_feedback import (
  MocReflectedDomainGlobalCoupledDownstreamFeedbackRun,
  run_reflected_domain_global_coupled_downstream_feedback,
)
from exhaust_plume.validation.moc_global_frontier_boundary_condition import (
  MocReflectedDomainGlobalFrontierBoundaryConditionStatus,
  MocReflectedDomainGlobalFrontierBoundaryConditionResult,
  run_reflected_domain_global_frontier_boundary_conditioned_resolve,
)
from exhaust_plume.validation.moc_global_boundary_frame_negotiation import (
  MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
  MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
  build_reflected_domain_global_boundary_frame_negotiation_request,
  negotiate_reflected_domain_global_boundary_frame,
  solver_owned_global_boundary_station_xs,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun',
  'run_reflected_domain_global_coupled_boundary_condition_feedback',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback'
)


class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus(str, Enum):
  """Outcome of one bounded downstream/global boundary-condition run."""

  COMPLETED_RESEARCH_BOUNDARY_FEEDBACK = (
    'completed-research-global-coupled-boundary-condition-feedback'
  )
  INVALID_INPUT = 'invalid_input'
  DOWNSTREAM_FEEDBACK_FAILURE = (
    'global-coupled-boundary-condition-downstream-failure'
  )
  FRONTIER_REQUEST_FAILURE = (
    'global-coupled-boundary-condition-frontier-request-failure'
  )
  BASE_TARGET_FAILURE = (
    'global-coupled-boundary-condition-base-target-failure'
  )
  BOUNDARY_CONDITION_FAILURE = (
    'global-coupled-boundary-condition-resolve-failure'
  )
  FRAME_NEGOTIATION_REQUIRED = (
    'global-coupled-boundary-condition-frame-negotiation-required'
  )
  FRAME_NEGOTIATION_FAILURE = (
    'global-coupled-boundary-condition-frame-negotiation-failure'
  )
  FIDELITY_FAILURE = 'global-coupled-boundary-condition-fidelity-failure'
  ITERATION_LIMIT = 'global-coupled-boundary-condition-iteration-limit'
####


def _options(
  value: Mapping[str, Any] | None,
  name: str,
  *,
  reserved: tuple[str, ...],
) -> dict[str, Any]:
  if value is None:
    return {}
  ####
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  ####
  resolved = dict(value)
  collisions = tuple(key for key in reserved if key in resolved)
  if collisions:
    raise ValueError(
      f'{name} cannot override positional controls: {", ".join(collisions)}'
    )
  ####
  return resolved
####


def _configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
  serialized = json.dumps(
    dict(configuration),
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _build_solver_owned_base_target(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  source_id: str,
) -> MocPhysicalFieldEulerBoundaryPressureTarget:
  """Materialize the exact source ambient frame for an overlay target."""

  if closure.global_euler is None or closure.global_euler.physical_field is None:
    raise ValueError('source closure retained no physical field for base target')
  ####
  field = closure.global_euler.physical_field.field
  if field is None:
    raise ValueError('source closure retained no physical field geometry')
  ####
  boundary = field.ambient_boundary
  points = tuple(boundary.points_m)
  states = tuple(boundary.states)
  pressures = tuple(boundary.static_pressure_Pa)
  if not (len(points) == len(states) == len(pressures) >= 2):
    raise ValueError(
      'source closure ambient boundary must retain aligned solver-owned '
      'points, states, and pressure samples'
    )
  ####
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=tuple(point[0] for point in points),
    static_pressure_Pa=pressures,
    boundary_points_m=points,
    tangent_rad=tuple(state.theta_rad for state in states),
    source_id=source_id,
    source_closure_fingerprint=(
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    source_proposal_fingerprint=request.source_proposal_fingerprint,
  )
####


def _residual_channels_verified(
  result: MocReflectedDomainGlobalFrontierBoundaryConditionResult | None,
) -> tuple[bool, bool, bool]:
  """Independently classify coordinate, tangent, and pressure channels."""

  if result is None or result.target is None:
    return False, False, False
  ####
  coordinate = result.coordinate_residuals_m
  tangent = result.tangent_residuals_rad
  pressure = result.pressure_residuals_Pa
  if not coordinate or not tangent or not pressure:
    return False, False, False
  ####
  if not all(
    isfinite(value)
    for values in (coordinate, tangent, pressure)
    for value in values
  ):
    return False, False, False
  ####
  configuration = result.configuration
  position_tolerance = float(configuration.get('position_tolerance_m', 0.0))
  tangent_tolerance = float(configuration.get('tangent_tolerance_rad', 0.0))
  pressure_tolerance = float(
    configuration.get('pressure_tolerance_fraction', 0.0)
  )
  expected_pressure = result.target.static_pressure_Pa
  pressure_match = bool(
    len(pressure) == len(expected_pressure)
    and all(
      residual / max(abs(expected), 1.0) <= pressure_tolerance
      for residual, expected in zip(pressure, expected_pressure, strict=True)
    )
  )
  return (
    max(coordinate) <= position_tolerance,
    max(tangent) <= tangent_tolerance,
    pressure_match,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration:
  """One downstream-response and solver-owned global boundary step."""

  iteration_index: int
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  downstream_feedback: MocReflectedDomainGlobalCoupledDownstreamFeedbackRun | None
  proposal: (
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None
  )
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest | None
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget | None
  boundary_condition: MocReflectedDomainGlobalFrontierBoundaryConditionResult | None
  next_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  frame_negotiation: MocReflectedDomainGlobalBoundaryFrameNegotiationResult | None = None
  downstream_response_verified: bool = False
  source_lineage_verified: bool = False
  base_target_lineage_verified: bool = False
  target_lineage_verified: bool = False
  target_composition_verified: bool = False
  fresh_global_solve_attempted: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  coordinate_residuals_verified: bool = False
  tangent_residuals_verified: bool = False
  pressure_residuals_verified: bool = False
  entropy_residual_verified: bool = False
  euler_residuals_verified: bool = False
  frame_negotiation_verified: bool = False
  frame_coverage_verified: bool = False
  frame_extension_required: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.iteration_index, bool)
      or not isinstance(self.iteration_index, int)
      or self.iteration_index < 0
    ):
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    for name in ('source_closure',):
      if not isinstance(
        getattr(self, name),
        MocReflectedDomainGlobalPhysicalClosureResult,
      ):
        raise TypeError(
          f'{name} must be a '
          'MocReflectedDomainGlobalPhysicalClosureResult'
        )
      ####
    ####
    if self.downstream_feedback is not None and not isinstance(
      self.downstream_feedback,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackRun,
    ):
      raise TypeError(
        'downstream_feedback must be a '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackRun or None'
      )
    ####
    if self.proposal is not None and not isinstance(
      self.proposal,
      MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
    ):
      raise TypeError(
        'proposal must be a typed global downstream feedback proposal or None'
      )
    ####
    if self.frontier_request is not None and not isinstance(
      self.frontier_request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError('frontier_request must be a typed frontier request or None')
    ####
    for name in ('base_target',):
      if getattr(self, name) is not None and not isinstance(
        getattr(self, name),
        MocPhysicalFieldEulerBoundaryPressureTarget,
      ):
        raise TypeError(f'{name} must be a typed pressure target or None')
      ####
    ####
    if self.boundary_condition is not None and not isinstance(
      self.boundary_condition,
      MocReflectedDomainGlobalFrontierBoundaryConditionResult,
    ):
      raise TypeError(
        'boundary_condition must be a typed boundary-condition result or None'
      )
    ####
    if self.next_closure is not None and not isinstance(
      self.next_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('next_closure must be a typed physical closure or None')
    ####
    if self.frame_negotiation is not None and not isinstance(
      self.frame_negotiation,
      MocReflectedDomainGlobalBoundaryFrameNegotiationResult,
    ):
      raise TypeError(
        'frame_negotiation must be a typed boundary-frame result or None'
      )
    ####
    for name in (
      'downstream_response_verified',
      'source_lineage_verified',
      'base_target_lineage_verified',
      'target_lineage_verified',
      'target_composition_verified',
      'fresh_global_solve_attempted',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'coordinate_residuals_verified',
      'tangent_residuals_verified',
      'pressure_residuals_verified',
      'entropy_residual_verified',
      'euler_residuals_verified',
      'frame_negotiation_verified',
      'frame_coverage_verified',
      'frame_extension_required',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_step_verified(self) -> bool:
    """Whether this step reached every local research-only evidence gate."""

    return bool(
      self.downstream_response_verified
      and self.source_lineage_verified
      and self.base_target_lineage_verified
      and self.target_lineage_verified
      and self.target_composition_verified
      and self.fresh_global_solve_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.coordinate_residuals_verified
      and self.tangent_residuals_verified
      and self.pressure_residuals_verified
      and self.entropy_residual_verified
      and self.euler_residuals_verified
      and self.frame_negotiation_verified
      and self.frame_coverage_verified
      and self.fidelity_isolation_verified
      and self.boundary_condition is not None
      and self.boundary_condition.converged_research_resolve
      and self.next_closure is not None
      and self.next_closure.physical_closure_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'research_step_verified': self.research_step_verified,
      'downstream_response_verified': self.downstream_response_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'base_target_lineage_verified': self.base_target_lineage_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'target_composition_verified': self.target_composition_verified,
      'fresh_global_solve_attempted': self.fresh_global_solve_attempted,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_match_verified': self.target_match_verified,
      'coordinate_residuals_verified': self.coordinate_residuals_verified,
      'tangent_residuals_verified': self.tangent_residuals_verified,
      'pressure_residuals_verified': self.pressure_residuals_verified,
      'entropy_residual_verified': self.entropy_residual_verified,
      'euler_residuals_verified': self.euler_residuals_verified,
      'frame_negotiation_verified': self.frame_negotiation_verified,
      'frame_coverage_verified': self.frame_coverage_verified,
      'frame_extension_required': self.frame_extension_required,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'base_target': (
        None if self.base_target is None else self.base_target.as_report()
      ),
      'frontier_request': (
        None
        if self.frontier_request is None
        else self.frontier_request.as_report()
      ),
      'downstream_feedback': (
        None
        if self.downstream_feedback is None
        else self.downstream_feedback.as_report()
      ),
      'boundary_condition': (
        None
        if self.boundary_condition is None
        else self.boundary_condition.as_report()
      ),
      'frame_negotiation': (
        None
        if self.frame_negotiation is None
        else self.frame_negotiation.as_report()
      ),
      'next_closure': (
        None if self.next_closure is None else self.next_closure.as_report()
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun:
  """Research-only outer feedback evidence with production gates closed."""

  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_iterations: int
  iterations: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration, ...
  ]
  status: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
  configuration: dict[str, Any]
  configuration_fingerprint: str
  downstream_response_verified: bool = False
  source_lineage_verified: bool = False
  base_target_lineage_verified: bool = False
  target_lineage_verified: bool = False
  target_composition_verified: bool = False
  fresh_global_solve_attempted: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  coordinate_residuals_verified: bool = False
  tangent_residuals_verified: bool = False
  pressure_residuals_verified: bool = False
  entropy_residual_verified: bool = False
  euler_residuals_verified: bool = False
  frame_negotiation_verified: bool = False
  frame_coverage_verified: bool = False
  frame_extension_required: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    for name in ('source_closure', 'final_closure'):
      if not isinstance(
        getattr(self, name),
        MocReflectedDomainGlobalPhysicalClosureResult,
      ):
        raise TypeError(
          f'{name} must be a '
          'MocReflectedDomainGlobalPhysicalClosureResult'
        )
      ####
    ####
    if (
      isinstance(self.requested_iterations, bool)
      or not isinstance(self.requested_iterations, int)
      or self.requested_iterations < 1
    ):
      raise ValueError('requested_iterations must be a positive integer')
    ####
    iterations = tuple(self.iterations)
    if any(
      not isinstance(
        iteration,
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration,
      )
      for iteration in iterations
    ):
      raise TypeError('iterations must contain typed boundary feedback steps')
    ####
    if len(iterations) > self.requested_iterations:
      raise ValueError('iterations cannot exceed requested_iterations')
    ####
    if tuple(item.iteration_index for item in iterations) != tuple(
      range(len(iterations))
    ):
      raise ValueError('iterations must have contiguous zero-based indices')
    ####
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus,
    ):
      raise TypeError('status must be a typed boundary feedback status')
    ####
    for name in (
      'downstream_response_verified',
      'source_lineage_verified',
      'base_target_lineage_verified',
      'target_lineage_verified',
      'target_composition_verified',
      'fresh_global_solve_attempted',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'coordinate_residuals_verified',
      'tangent_residuals_verified',
      'pressure_residuals_verified',
      'entropy_residual_verified',
      'euler_residuals_verified',
      'frame_negotiation_verified',
      'frame_coverage_verified',
      'frame_extension_required',
      'fidelity_isolation_verified',
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
        'bounded boundary feedback cannot claim canonical global closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'bounded boundary feedback must remain blocked from production'
      )
    ####
    object.__setattr__(self, 'iterations', iterations)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_feedback_completed(self) -> bool:
    """Whether every requested step reached the bounded research contract."""

    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
      .COMPLETED_RESEARCH_BOUNDARY_FEEDBACK
      and len(self.iterations) == self.requested_iterations
      and self.downstream_response_verified
      and self.source_lineage_verified
      and self.base_target_lineage_verified
      and self.target_lineage_verified
      and self.target_composition_verified
      and self.fresh_global_solve_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.coordinate_residuals_verified
      and self.tangent_residuals_verified
      and self.pressure_residuals_verified
      and self.entropy_residual_verified
      and self.euler_residuals_verified
      and self.frame_negotiation_verified
      and self.frame_coverage_verified
      and self.fidelity_isolation_verified
      and all(item.research_step_verified for item in self.iterations)
    )
  ####

  @property
  def converged(self) -> bool:
    """Alias for bounded research completion, never canonical closure."""

    return self.research_feedback_completed
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_OPERATOR_ID
      ),
      'status': self.status.value,
      'research_feedback_completed': self.research_feedback_completed,
      'converged': self.converged,
      'requested_iterations': self.requested_iterations,
      'iteration_count': len(self.iterations),
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'final_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.final_closure
        )
      ),
      'downstream_response_verified': self.downstream_response_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'base_target_lineage_verified': self.base_target_lineage_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'target_composition_verified': self.target_composition_verified,
      'fresh_global_solve_attempted': self.fresh_global_solve_attempted,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_match_verified': self.target_match_verified,
      'coordinate_residuals_verified': self.coordinate_residuals_verified,
      'tangent_residuals_verified': self.tangent_residuals_verified,
      'pressure_residuals_verified': self.pressure_residuals_verified,
      'entropy_residual_verified': self.entropy_residual_verified,
      'euler_residuals_verified': self.euler_residuals_verified,
      'frame_negotiation_verified': self.frame_negotiation_verified,
      'frame_coverage_verified': self.frame_coverage_verified,
      'frame_extension_required': self.frame_extension_required,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'iterations': tuple(item.as_report() for item in self.iterations),
      'final_closure': self.final_closure.as_report(),
      'message': self.message,
    }
  ####
####


def _run_result(
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  requested_iterations: int,
  iterations: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration, ...
  ],
  status: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus,
  configuration: Mapping[str, Any],
  message: str,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun:
  def all_steps(name: str) -> bool:
    return bool(iterations) and all(getattr(item, name) for item in iterations)
  ####
  return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun(
    source_closure=source_closure,
    final_closure=final_closure,
    requested_iterations=requested_iterations,
    iterations=iterations,
    status=status,
    configuration=dict(configuration),
    configuration_fingerprint=_configuration_fingerprint(configuration),
    downstream_response_verified=all_steps('downstream_response_verified'),
    source_lineage_verified=all_steps('source_lineage_verified'),
    base_target_lineage_verified=all_steps('base_target_lineage_verified'),
    target_lineage_verified=all_steps('target_lineage_verified'),
    target_composition_verified=all_steps('target_composition_verified'),
    fresh_global_solve_attempted=all_steps('fresh_global_solve_attempted'),
    fresh_global_solve_verified=all_steps('fresh_global_solve_verified'),
    target_consumption_verified=all_steps('target_consumption_verified'),
    target_coverage_verified=all_steps('target_coverage_verified'),
    target_match_verified=all_steps('target_match_verified'),
    coordinate_residuals_verified=all_steps('coordinate_residuals_verified'),
    tangent_residuals_verified=all_steps('tangent_residuals_verified'),
    pressure_residuals_verified=all_steps('pressure_residuals_verified'),
    entropy_residual_verified=all_steps('entropy_residual_verified'),
    euler_residuals_verified=all_steps('euler_residuals_verified'),
    frame_negotiation_verified=all_steps('frame_negotiation_verified'),
    frame_coverage_verified=all_steps('frame_coverage_verified'),
    frame_extension_required=any(
      item.frame_extension_required for item in iterations
    ),
    fidelity_isolation_verified=all_steps('fidelity_isolation_verified'),
    message=message,
  )
####


def run_reflected_domain_global_coupled_boundary_condition_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  maximum_iterations: int = 1,
  downstream_feedback_iterations: int = 2,
  consumer_id: str = 'moc-global-coupled-boundary-condition-feedback-v1',
  downstream_options: Mapping[str, Any] | None = None,
  boundary_condition_options: Mapping[str, Any] | None = None,
  maximum_frame_extension_m: float = 0.5,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun:
  """Run bounded downstream/global feedback with exact pressure consumption.

  The downstream response is never passed directly as a geometry profile.  A
  fresh base target is materialized from the current solver-owned ambient
  boundary, the response is composed as a bounded pressure overlay, and the
  global boundary consumer owns the new geometry.  Any moving-frame coverage
  failure is retained as a typed stop.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  if (
    isinstance(downstream_feedback_iterations, bool)
    or not isinstance(downstream_feedback_iterations, int)
    or downstream_feedback_iterations < 2
  ):
    raise ValueError('downstream_feedback_iterations must be at least two')
  ####
  try:
    reference_temperature = float(reference_total_temperature_K)
  except (TypeError, ValueError) as error:
    raise ValueError('reference_total_temperature_K must be numeric') from error
  ####
  if not isfinite(reference_temperature) or reference_temperature <= 0.0:
    raise ValueError(
      'reference_total_temperature_K must be finite and positive'
    )
  ####
  resolved_consumer_id = str(consumer_id)
  if not resolved_consumer_id:
    raise ValueError('consumer_id must be non-empty')
  ####
  try:
    resolved_maximum_frame_extension = float(maximum_frame_extension_m)
  except (TypeError, ValueError) as error:
    raise ValueError('maximum_frame_extension_m must be numeric') from error
  ####
  if (
    not isfinite(resolved_maximum_frame_extension)
    or resolved_maximum_frame_extension < 0.0
  ):
    raise ValueError(
      'maximum_frame_extension_m must be finite and nonnegative'
    )
  ####
  resolved_downstream_options = _options(
    downstream_options,
    'downstream_options',
    reserved=(
      'closure',
      'reference_total_temperature_K',
      'maximum_iterations',
      'maximum_frame_extension_m',
    ),
  )
  resolved_boundary_options = _options(
    boundary_condition_options,
    'boundary_condition_options',
    reserved=('request', 'source_closure', 'base_target'),
  )
  configuration: dict[str, Any] = {
    'source_closure_fingerprint': (
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    'reference_total_temperature_K': reference_temperature,
    'maximum_iterations': maximum_iterations,
    'downstream_feedback_iterations': downstream_feedback_iterations,
    'maximum_frame_extension_m': resolved_maximum_frame_extension,
    'consumer_id': resolved_consumer_id,
    'downstream_options': resolved_downstream_options,
    'boundary_condition_options': resolved_boundary_options,
    'feedback_policy': (
      'downstream-response-explicit-pressure-overlay-fresh-global-ambient-march-v1'
    ),
  }
  if not closure.converged or not closure.physical_closure_verified:
    return _run_result(
      closure,
      closure,
      maximum_iterations,
      (),
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus.INVALID_INPUT,
      configuration,
      'boundary-condition feedback requires a locally verified source closure',
    )
  ####
  current = closure
  iterations: list[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration
  ] = []
  failure_status: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus | None
  ) = None
  failure_message: str | None = None
  for iteration_index in range(maximum_iterations):
    source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
      current
    )
    downstream: MocReflectedDomainGlobalCoupledDownstreamFeedbackRun | None = None
    proposal: (
      MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal | None
    ) = None
    request: MocReflectedDomainGlobalFrontierReconciliationRequest | None = None
    base_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
    boundary_condition: (
      MocReflectedDomainGlobalFrontierBoundaryConditionResult | None
    ) = None
    frame_negotiation: MocReflectedDomainGlobalBoundaryFrameNegotiationResult | None = None
    try:
      downstream = run_reflected_domain_global_coupled_downstream_feedback(
        current,
        reference_total_temperature_K=reference_temperature,
        maximum_iterations=downstream_feedback_iterations,
        **resolved_downstream_options,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .DOWNSTREAM_FEEDBACK_FAILURE
      )
      failure_message = f'downstream feedback raised: {error}'
      iterations.append(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=None,
          proposal=None,
          frontier_request=None,
          base_target=None,
          boundary_condition=None,
          next_closure=None,
          source_lineage_verified=(
            source_fingerprint
            == moc_reflected_domain_global_physical_closure_fingerprint(current)
          ),
          fidelity_isolation_verified=True,
          message=failure_message,
        )
      )
      break
    ####
    downstream_response_verified = bool(
      downstream.fresh_solver_invocation_verified
      and downstream.upstream_feedback_proposal_verified
      and downstream.fidelity_isolation_verified
      and downstream.upstream_feedback_proposals
    )
    proposal = (
      downstream.upstream_feedback_proposals[-1]
      if downstream.upstream_feedback_proposals
      else None
    )
    if not downstream_response_verified or proposal is None:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .DOWNSTREAM_FEEDBACK_FAILURE
      )
      failure_message = (
        'downstream feedback did not retain a ready exact frontier proposal'
      )
      iterations.append(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=None,
          base_target=None,
          boundary_condition=None,
          next_closure=None,
          downstream_response_verified=downstream_response_verified,
          source_lineage_verified=(
            downstream.closure is current
            and downstream.closure_lineage_verified
          ),
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=failure_message,
        )
      )
      break
    ####
    try:
      request = build_reflected_domain_global_frontier_reconciliation_request(
        current,
        proposal,
        consumer_id=f'{resolved_consumer_id}-iteration-{iteration_index}',
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .FRONTIER_REQUEST_FAILURE
      )
      failure_message = f'frontier request construction failed: {error}'
      iterations.append(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=None,
          base_target=None,
          boundary_condition=None,
          next_closure=None,
          downstream_response_verified=downstream_response_verified,
          source_lineage_verified=(
            downstream.closure is current
            and downstream.closure_lineage_verified
          ),
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=failure_message,
        )
      )
      break
    ####
    source_lineage_verified = bool(
      request.source_closure_fingerprint == source_fingerprint
      and request.lineage_verified
      and downstream.closure is current
    )
    try:
      base_target = _build_solver_owned_base_target(
        current,
        request,
        source_id=(
          f'{resolved_consumer_id}:base:{iteration_index}:{source_fingerprint}'
        ),
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .BASE_TARGET_FAILURE
      )
      failure_message = f'solver-owned base target construction failed: {error}'
      iterations.append(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=request,
          base_target=None,
          boundary_condition=None,
          next_closure=None,
          downstream_response_verified=downstream_response_verified,
          source_lineage_verified=source_lineage_verified,
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=failure_message,
        )
      )
      break
    ####
    base_target_lineage_verified = bool(
      base_target.source_closure_fingerprint == source_fingerprint
      and base_target.source_proposal_fingerprint
      == request.source_proposal_fingerprint
    )
    try:
      boundary_condition = (
        run_reflected_domain_global_frontier_boundary_conditioned_resolve(
          request,
          current,
          base_target=base_target,
          **resolved_boundary_options,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .BOUNDARY_CONDITION_FAILURE
      )
      failure_message = f'boundary-conditioned global solve raised: {error}'
      iterations.append(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration(
          iteration_index=iteration_index,
          source_closure=current,
          downstream_feedback=downstream,
          proposal=proposal,
          frontier_request=request,
          base_target=base_target,
          boundary_condition=None,
          next_closure=None,
          downstream_response_verified=downstream_response_verified,
          source_lineage_verified=source_lineage_verified,
          base_target_lineage_verified=base_target_lineage_verified,
          fidelity_isolation_verified=downstream.fidelity_isolation_verified,
          message=failure_message,
        )
      )
      break
    ####
    conditioned = boundary_condition.conditioned_closure
    fresh_global_solve_attempted = conditioned is not None
    fresh_global_solve_verified = bool(
      conditioned is not None
      and conditioned is not current
      and conditioned.converged
      and conditioned.physical_closure_verified
    )
    coordinate_verified, tangent_verified, pressure_verified = (
      _residual_channels_verified(boundary_condition)
    )
    entropy_verified = bool(
      conditioned is not None
      and conditioned.variable_entropy_transport_verified
      and conditioned.maximum_entropy_lineage_residual is not None
    )
    euler_verified = bool(
      conditioned is not None
      and conditioned.cell_euler_residuals_verified
      and conditioned.field_audit is not None
      and conditioned.field_audit.cell_euler_residuals_verified
    )
    if conditioned is not None and boundary_condition.consumed_target is not None:
      try:
        solver_stations = solver_owned_global_boundary_station_xs(conditioned)
        if len(solver_stations) >= 2:
          frame_request = (
            build_reflected_domain_global_boundary_frame_negotiation_request(
              current,
              request,
              boundary_condition.consumed_target,
              solver_stations,
              maximum_extension_m=resolved_maximum_frame_extension,
              consumer_id=(
                f'{resolved_consumer_id}-frame-{iteration_index}'
              ),
              # The global solver's exact station lookup uses its own
              # 1e-9-domain tolerance.  The looser research measurement
              # tolerance must not hide a station that the solver rejected.
              position_tolerance_m=1.0e-9,
            )
          )
          frame_negotiation = negotiate_reflected_domain_global_boundary_frame(
            frame_request
          )
        ####
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        failure_status = (
          MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
          .FRAME_NEGOTIATION_FAILURE
        )
        failure_message = f'boundary-frame negotiation raised: {error}'
      ####
    ####
    frame_negotiation_verified = bool(
      frame_negotiation is not None
      and frame_negotiation.lineage_verified
      and frame_negotiation.frame_request_verified
    )
    frame_coverage_verified = bool(
      frame_negotiation is not None and frame_negotiation.frame_covered
    )
    frame_extension_required = bool(
      frame_negotiation is not None
      and frame_negotiation.extension_required
    )
    if (
      frame_negotiation is not None
      and frame_negotiation.status
      in (
        MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
        .EXTENSION_BUDGET_FAILURE,
        MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.NON_PHYSICAL_FRAME,
        MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.LINEAGE_FAILURE,
      )
    ):
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .FRAME_NEGOTIATION_FAILURE
      )
      failure_message = frame_negotiation.message
    ####
    target_consumption_verified = bool(
      boundary_condition.target_boundary_condition_consumed
    )
    target_coverage_verified = bool(boundary_condition.target_coverage_verified)
    target_match_verified = bool(boundary_condition.target_match_verified)
    fidelity_isolation_verified = bool(
      downstream.fidelity_isolation_verified
      and boundary_condition.fidelity_isolation_verified
      and boundary_condition.chain_promotion_blocked
      and not boundary_condition.production_claim_allowed
      and (
        conditioned is None or not conditioned.production_claim_allowed
      )
    )
    step = MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackIteration(
      iteration_index=iteration_index,
      source_closure=current,
      downstream_feedback=downstream,
      proposal=proposal,
      frontier_request=request,
      base_target=base_target,
      boundary_condition=boundary_condition,
      next_closure=conditioned if fresh_global_solve_verified else None,
      downstream_response_verified=downstream_response_verified,
      source_lineage_verified=source_lineage_verified,
      base_target_lineage_verified=base_target_lineage_verified,
      target_lineage_verified=boundary_condition.target_lineage_verified,
      target_composition_verified=(
        boundary_condition.target_composition_verified
      ),
      fresh_global_solve_attempted=fresh_global_solve_attempted,
      fresh_global_solve_verified=fresh_global_solve_verified,
      target_consumption_verified=target_consumption_verified,
      target_coverage_verified=target_coverage_verified,
      target_match_verified=target_match_verified,
      coordinate_residuals_verified=coordinate_verified,
      tangent_residuals_verified=tangent_verified,
      pressure_residuals_verified=pressure_verified,
      entropy_residual_verified=entropy_verified,
      euler_residuals_verified=euler_verified,
      frame_negotiation=frame_negotiation,
      frame_negotiation_verified=frame_negotiation_verified,
      frame_coverage_verified=frame_coverage_verified,
      frame_extension_required=frame_extension_required,
      fidelity_isolation_verified=fidelity_isolation_verified,
      message=boundary_condition.message,
    )
    iterations.append(step)
    if failure_status is not None:
      break
    ####
    if frame_extension_required:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .FRAME_NEGOTIATION_REQUIRED
      )
      failure_message = (
        frame_negotiation.message
        if frame_negotiation is not None
        else 'solver-owned boundary-frame extension is required'
      )
      break
    ####
    if not step.research_step_verified:
      failure_status = (
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .FIDELITY_FAILURE
        if boundary_condition.status
        is MocReflectedDomainGlobalFrontierBoundaryConditionStatus.FIDELITY_FAILURE
        else MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
        .BOUNDARY_CONDITION_FAILURE
      )
      failure_message = boundary_condition.message
      break
    ####
    assert conditioned is not None
    current = conditioned
  ####
  retained_iterations = tuple(iterations)
  if failure_status is None:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
      .COMPLETED_RESEARCH_BOUNDARY_FEEDBACK
      if len(retained_iterations) == maximum_iterations
      and all(item.research_step_verified for item in retained_iterations)
      else MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
      .ITERATION_LIMIT
    )
    message = (
      'downstream responses were consumed by fresh solver-owned global '
      'ambient boundary solves for every requested research step; canonical '
      'mixed-regime closure, refinement, validation, and promotion remain '
      'open'
      if status
      is MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackStatus
      .COMPLETED_RESEARCH_BOUNDARY_FEEDBACK
      else 'boundary-condition feedback stopped before all requested steps completed'
    )
  else:
    status = failure_status
    message = failure_message or 'boundary-condition feedback stopped'
  ####
  return _run_result(
    closure,
    current,
    maximum_iterations,
    retained_iterations,
    status,
    configuration,
    message,
  )
####
