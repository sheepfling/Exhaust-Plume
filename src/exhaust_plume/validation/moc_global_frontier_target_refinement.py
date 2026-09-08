"""Bounded target-conditioned refinement for the global frontier lane.

The target-guided resolver already fresh-solves a declared family of global
closures and selects the smallest exact frontier residual.  This module adds
the next research step: a deterministic bounded bracket refinement around
that selected solver parameter.  Each probe still invokes the global closure
from the immutable source closure, so the ladder records fresh equations,
exact target coverage, and fidelity isolation without turning parameter
search into a canonical free-boundary claim.

The compression-envelope skew is a research control parameter in the current
global remesh.  It is not a physical downstream boundary condition.  The
result therefore remains below global coupling, canonical downstream
closure, physical shock-cell fitting, and production promotion.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_frontier_target_resolve import (
  MocReflectedDomainGlobalFrontierTargetResolveCandidate,
  MocReflectedDomainGlobalFrontierTargetResolveResult,
  run_reflected_domain_global_frontier_target_guided_resolve,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierTargetRefinementStatus',
  'MocReflectedDomainGlobalFrontierTargetRefinementStep',
  'MocReflectedDomainGlobalFrontierTargetRefinementResult',
  'run_reflected_domain_global_frontier_target_conditioned_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-target-conditioned-refinement'
)


class MocReflectedDomainGlobalFrontierTargetRefinementStatus(str, Enum):
  """Outcome of the bounded target-conditioned refinement ladder."""

  CONVERGED_TARGET_CONDITIONED_RESEARCH_REFINEMENT = (
    'converged-target-conditioned-research-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-frontier-target-refinement-source-failure'
  TARGET_RESOLVE_FAILURE = 'global-frontier-target-refinement-resolve-failure'
  TARGET_MISMATCH = 'global-frontier-target-refinement-target-mismatch'
  REFINEMENT_LIMIT = 'global-frontier-target-refinement-iteration-limit'
  FIDELITY_FAILURE = 'global-frontier-target-refinement-fidelity-failure'


def _configuration_fingerprint(configuration: Mapping[str, Any]) -> str:
  serialized = json.dumps(
    dict(configuration),
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()


def _as_finite_float(value: object, name: str) -> float:
  try:
    resolved = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  if not isfinite(resolved):
    raise ValueError(f'{name} must be finite')
  return resolved


def _candidate_score(
  candidate: MocReflectedDomainGlobalFrontierTargetResolveCandidate,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  position_tolerance_m: float,
  tangent_tolerance_rad: float,
  pressure_tolerance_fraction: float,
) -> float:
  """Return one normalized, deterministic score for a fresh candidate."""

  if not (
    candidate.global_closure_verified
    and candidate.target_coverage_verified
    and candidate.target_residuals_finite
  ):
    return float('inf')
  ####
  pressure_score = max(
    (
      residual / max(abs(target_pressure), 1.0)
      for residual, target_pressure in zip(
        candidate.target_pressure_residuals_Pa,
        request.target_static_pressure_Pa,
        strict=True,
      )
    ),
    default=float('inf'),
  ) / pressure_tolerance_fraction
  return max(
    max(candidate.target_coordinate_residuals_m, default=float('inf'))
    / position_tolerance_m,
    max(candidate.target_tangent_residuals_rad, default=float('inf'))
    / tangent_tolerance_rad,
    pressure_score,
  )


def _probe_skews(lower: float, upper: float) -> tuple[float, ...]:
  midpoint = (lower + upper) / 2.0
  probes = (lower, midpoint, upper)
  return tuple(
    value
    for index, value in enumerate(probes)
    if index == 0 or value != probes[index - 1]
  )


def _next_bracket(
  lower: float,
  upper: float,
  selected_skew: float,
) -> tuple[float, float]:
  """Narrow around the best probe without extrapolating outside the bracket."""

  midpoint = (lower + upper) / 2.0
  if selected_skew <= lower:
    return lower, midpoint
  if selected_skew >= upper:
    return midpoint, upper
  half_width = (upper - lower) / 4.0
  return max(lower, selected_skew - half_width), min(
    upper,
    selected_skew + half_width,
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierTargetRefinementStep:
  """One fresh three-probe bracket and its target-guided selection."""

  iteration_index: int
  lower_skew: float
  upper_skew: float
  probe_skews: tuple[float, ...]
  target_resolve: MocReflectedDomainGlobalFrontierTargetResolveResult
  selected_probe_skew: float | None = None
  selected_score: float | None = None
  next_lower_skew: float | None = None
  next_upper_skew: float | None = None
  fresh_solver_invocation_verified: bool = False
  source_lineage_verified: bool = False
  target_lineage_verified: bool = False
  target_consumption_verified: bool = False
  target_match_verified: bool = False
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
    lower = _as_finite_float(self.lower_skew, 'lower_skew')
    upper = _as_finite_float(self.upper_skew, 'upper_skew')
    if not -1.0 <= lower < upper <= 1.0:
      raise ValueError('skew bracket must satisfy -1 <= lower < upper <= 1')
    ####
    probes = tuple(_as_finite_float(value, 'probe_skew') for value in self.probe_skews)
    if not probes or len(set(probes)) != len(probes):
      raise ValueError('probe_skews must contain unique values')
    if any(value < lower or value > upper for value in probes):
      raise ValueError('probe_skews must remain inside the retained bracket')
    ####
    if not isinstance(
      self.target_resolve,
      MocReflectedDomainGlobalFrontierTargetResolveResult,
    ):
      raise TypeError(
        'target_resolve must be a '
        'MocReflectedDomainGlobalFrontierTargetResolveResult'
      )
    ####
    if self.selected_probe_skew is not None:
      selected = _as_finite_float(self.selected_probe_skew, 'selected_probe_skew')
      if selected not in probes:
        raise ValueError('selected_probe_skew must select a retained probe')
      object.__setattr__(self, 'selected_probe_skew', selected)
    ####
    if self.selected_score is not None:
      score = _as_finite_float(self.selected_score, 'selected_score')
      if score < 0.0:
        raise ValueError('selected_score must be nonnegative')
      object.__setattr__(self, 'selected_score', score)
    ####
    for name in ('next_lower_skew', 'next_upper_skew'):
      value = getattr(self, name)
      if value is not None:
        resolved = _as_finite_float(value, name)
        object.__setattr__(self, name, resolved)
    ####
    if (self.next_lower_skew is None) != (self.next_upper_skew is None):
      raise ValueError('next bracket bounds must be supplied together')
    if self.next_lower_skew is not None and not (
      -1.0 <= self.next_lower_skew < self.next_upper_skew <= 1.0
    ):
      raise ValueError('next skew bracket must be ordered and bounded')
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'source_lineage_verified',
      'target_lineage_verified',
      'target_consumption_verified',
      'target_match_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.target_match_verified and self.selected_probe_skew is None:
      raise ValueError('target_match_verified requires a selected probe')
    ####
    object.__setattr__(self, 'lower_skew', lower)
    object.__setattr__(self, 'upper_skew', upper)
    object.__setattr__(self, 'probe_skews', probes)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def research_step_verified(self) -> bool:
    return bool(
      self.fresh_solver_invocation_verified
      and self.source_lineage_verified
      and self.target_lineage_verified
      and self.target_consumption_verified
      and self.fidelity_isolation_verified
      and self.selected_probe_skew is not None
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'lower_skew': self.lower_skew,
      'upper_skew': self.upper_skew,
      'probe_skews': self.probe_skews,
      'selected_probe_skew': self.selected_probe_skew,
      'selected_score': self.selected_score,
      'next_lower_skew': self.next_lower_skew,
      'next_upper_skew': self.next_upper_skew,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_match_verified': self.target_match_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'research_step_verified': self.research_step_verified,
      'target_resolve': self.target_resolve.as_report(),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierTargetRefinementResult:
  """Audited target-conditioned global refinement below promotion."""

  status: MocReflectedDomainGlobalFrontierTargetRefinementStatus
  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_iterations: int
  steps: tuple[MocReflectedDomainGlobalFrontierTargetRefinementStep, ...] = ()
  selected_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  target_lineage_verified: bool = False
  fresh_global_solve_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  refinement_brackets_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  configuration: dict[str, Any] | None = None
  configuration_fingerprint: str = ''
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierTargetRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierTargetRefinementStatus'
      )
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest'
      )
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult'
      )
    if (
      isinstance(self.requested_iterations, bool)
      or not isinstance(self.requested_iterations, int)
      or self.requested_iterations < 1
    ):
      raise ValueError('requested_iterations must be a positive integer')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalFrontierTargetRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed target-refinement steps')
    if len(steps) > self.requested_iterations:
      raise ValueError('steps cannot exceed requested_iterations')
    if tuple(step.iteration_index for step in steps) != tuple(range(len(steps))):
      raise ValueError('steps must have contiguous zero-based indices')
    ####
    if self.selected_closure is not None and not isinstance(
      self.selected_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'selected_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    for name in (
      'target_lineage_verified',
      'fresh_global_solve_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'refinement_brackets_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'target-conditioned research refinement cannot claim canonical closure'
      )
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'target-conditioned research refinement must remain blocked from production'
      )
    ####
    configuration = {} if self.configuration is None else dict(self.configuration)
    if self.configuration_fingerprint:
      expected = _configuration_fingerprint(configuration)
      if self.configuration_fingerprint != expected:
        raise ValueError('configuration_fingerprint does not match configuration')
    else:
      object.__setattr__(
        self,
        'configuration_fingerprint',
        _configuration_fingerprint(configuration),
      )
    ####
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def research_refinement_completed(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierTargetRefinementStatus
      .CONVERGED_TARGET_CONDITIONED_RESEARCH_REFINEMENT
      and self.selected_closure is not None
      and self.target_lineage_verified
      and self.fresh_global_solve_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.refinement_brackets_verified
      and self.fidelity_isolation_verified
      and all(step.research_step_verified for step in self.steps)
    )

  @property
  def converged(self) -> bool:
    """Alias for local research completion, never canonical closure."""

    return self.research_refinement_completed

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_REFINEMENT_OPERATOR_ID,
      'status': self.status.value,
      'research_refinement_completed': self.research_refinement_completed,
      'converged': self.converged,
      'requested_iterations': self.requested_iterations,
      'iteration_count': len(self.steps),
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'source_proposal_fingerprint': (
        moc_reflected_domain_global_frontier_proposal_fingerprint(
          self.request.proposal
        )
      ),
      'selected_closure_fingerprint': (
        None
        if self.selected_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.selected_closure
        )
      ),
      'target_lineage_verified': self.target_lineage_verified,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_match_verified': self.target_match_verified,
      'refinement_brackets_verified': self.refinement_brackets_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'steps': tuple(step.as_report() for step in self.steps),
      'message': self.message,
      'claim_status': (
        'research-only target-conditioned global parameter refinement; the '
        'compression-envelope skew remains a research control and was not '
        'promoted to a canonical mixed-regime boundary condition'
      ),
    }


def _result(
  status: MocReflectedDomainGlobalFrontierTargetRefinementStatus,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  requested_iterations: int,
  configuration: Mapping[str, Any],
  *,
  steps: tuple[MocReflectedDomainGlobalFrontierTargetRefinementStep, ...] = (),
  selected_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  target_lineage_verified: bool = False,
  fresh_global_solve_verified: bool = False,
  target_consumption_verified: bool = False,
  target_coverage_verified: bool = False,
  target_match_verified: bool = False,
  refinement_brackets_verified: bool = False,
  fidelity_isolation_verified: bool = False,
  message: str,
) -> MocReflectedDomainGlobalFrontierTargetRefinementResult:
  return MocReflectedDomainGlobalFrontierTargetRefinementResult(
    status=status,
    request=request,
    source_closure=source_closure,
    requested_iterations=requested_iterations,
    steps=steps,
    selected_closure=selected_closure,
    target_lineage_verified=target_lineage_verified,
    fresh_global_solve_verified=fresh_global_solve_verified,
    target_consumption_verified=target_consumption_verified,
    target_coverage_verified=target_coverage_verified,
    target_match_verified=target_match_verified,
    refinement_brackets_verified=refinement_brackets_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    configuration=dict(configuration),
    configuration_fingerprint=_configuration_fingerprint(configuration),
    message=message,
  )


def run_reflected_domain_global_frontier_target_conditioned_refinement(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  compression_envelope_skew_bounds: tuple[float, float] | None = None,
  maximum_iterations: int = 3,
  minimum_bracket_width: float = 1.0e-3,
  target_resolve_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalFrontierTargetRefinementResult:
  """Fresh-solve a bounded target-conditioned global refinement ladder.

  Every refinement step evaluates lower/middle/upper skew probes by calling
  the existing fresh global target resolver.  The next bracket is selected
  from the measured target residual, never from an extrapolated boundary.  A
  matched target ends the ladder; otherwise the bounded iteration limit is
  reported explicitly.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  minimum_width = _as_finite_float(
    minimum_bracket_width,
    'minimum_bracket_width',
  )
  if minimum_width <= 0.0:
    raise ValueError('minimum_bracket_width must be positive')
  ####
  if not request.lineage_verified:
    return _result(
      MocReflectedDomainGlobalFrontierTargetRefinementStatus.INVALID_INPUT,
      request,
      source_closure,
      maximum_iterations,
      {'target_resolve_options': {}},
      message='frontier request lineage is not verified',
    )
  ####
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  if source_fingerprint != request.source_closure_fingerprint:
    return _result(
      MocReflectedDomainGlobalFrontierTargetRefinementStatus.INVALID_INPUT,
      request,
      source_closure,
      maximum_iterations,
      {'target_resolve_options': {}},
      message='source closure does not match the exact frontier request fingerprint',
    )
  ####
  if not source_closure.converged or not source_closure.physical_closure_verified:
    return _result(
      MocReflectedDomainGlobalFrontierTargetRefinementStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      maximum_iterations,
      {'target_resolve_options': {}},
      message='target-conditioned refinement requires a locally verified source closure',
    )
  ####
  if target_resolve_options is None:
    resolved_options: dict[str, Any] = {}
  elif isinstance(target_resolve_options, Mapping):
    resolved_options = dict(target_resolve_options)
  else:
    raise TypeError('target_resolve_options must be a mapping when supplied')
  if 'candidate_compression_envelope_skews' in resolved_options:
    raise ValueError(
      'target_resolve_options cannot override the refinement probe family'
    )
  ####
  try:
    if compression_envelope_skew_bounds is None:
      remesh = source_closure.global_remesh
      retained = () if remesh is None else remesh.compression_envelope_skews
      if len(retained) < 2:
        raise ValueError(
          'source closure retained fewer than two compression-envelope skews'
        )
      lower, upper = min(retained), max(retained)
    else:
      if len(compression_envelope_skew_bounds) != 2:
        raise ValueError('compression_envelope_skew_bounds must have two values')
      lower = _as_finite_float(
        compression_envelope_skew_bounds[0],
        'compression_envelope_skew_bounds lower',
      )
      upper = _as_finite_float(
        compression_envelope_skew_bounds[1],
        'compression_envelope_skew_bounds upper',
      )
  except (TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierTargetRefinementStatus.INVALID_INPUT,
      request,
      source_closure,
      maximum_iterations,
      {'target_resolve_options': resolved_options},
      message=str(error),
    )
  ####
  if not -1.0 <= lower < upper <= 1.0:
    return _result(
      MocReflectedDomainGlobalFrontierTargetRefinementStatus.INVALID_INPUT,
      request,
      source_closure,
      maximum_iterations,
      {'target_resolve_options': resolved_options},
      message='compression-envelope skew bounds must satisfy -1 <= lower < upper <= 1',
    )
  ####
  position_tolerance = _as_finite_float(
    resolved_options.get('position_tolerance_m', 5.0e-3),
    'position_tolerance_m',
  )
  tangent_tolerance = _as_finite_float(
    resolved_options.get('tangent_tolerance_rad', 5.0e-3),
    'tangent_tolerance_rad',
  )
  pressure_tolerance = _as_finite_float(
    resolved_options.get('pressure_tolerance_fraction', 0.02),
    'pressure_tolerance_fraction',
  )
  if not all(
    value > 0.0
    for value in (position_tolerance, tangent_tolerance, pressure_tolerance)
  ):
    raise ValueError('target residual tolerances must be positive')
  ####
  configuration: dict[str, Any] = {
    'source_closure_fingerprint': source_fingerprint,
    'source_proposal_fingerprint': (
      moc_reflected_domain_global_frontier_proposal_fingerprint(request.proposal)
    ),
    'compression_envelope_skew_bounds': (lower, upper),
    'maximum_iterations': maximum_iterations,
    'minimum_bracket_width': minimum_width,
    'target_resolve_options': resolved_options,
    'refinement_policy': (
      'fresh-global-target-guided-three-probe-bracket-v1'
    ),
  }
  ####
  steps: list[MocReflectedDomainGlobalFrontierTargetRefinementStep] = []
  selected_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  target_lineage_verified = True
  fresh_global_solve_verified = True
  target_consumption_verified = True
  target_coverage_verified = True
  target_match_verified = False
  fidelity_isolation_verified = True
  refinement_brackets_verified = True
  status = (
    MocReflectedDomainGlobalFrontierTargetRefinementStatus.REFINEMENT_LIMIT
  )
  message = 'target-conditioned refinement reached its bounded iteration limit'
  for iteration_index in range(maximum_iterations):
    probes = _probe_skews(lower, upper)
    options = dict(resolved_options)
    try:
      target_resolve = run_reflected_domain_global_frontier_target_guided_resolve(
        request,
        source_closure,
        candidate_compression_envelope_skews=probes,
        **options,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      status = (
        MocReflectedDomainGlobalFrontierTargetRefinementStatus.TARGET_RESOLVE_FAILURE
      )
      message = f'target-guided refinement probe family raised: {error}'
      break
    ####
    candidates = tuple(target_resolve.candidates)
    valid = tuple(
      (
        index,
        _candidate_score(
          candidate,
          request,
          position_tolerance_m=position_tolerance,
          tangent_tolerance_rad=tangent_tolerance,
          pressure_tolerance_fraction=pressure_tolerance,
        ),
      )
      for index, candidate in enumerate(candidates)
      if isfinite(
        _candidate_score(
          candidate,
          request,
          position_tolerance_m=position_tolerance,
          tangent_tolerance_rad=tangent_tolerance,
          pressure_tolerance_fraction=pressure_tolerance,
        )
      )
    )
    selected_index = None if not valid else min(valid, key=lambda item: (item[1], item[0]))[0]
    selected_candidate = (
      None if selected_index is None else candidates[selected_index]
    )
    selected_skew = (
      None if selected_candidate is None else selected_candidate.compression_envelope_skew
    )
    selected_score = (
      None
      if selected_candidate is None
      else _candidate_score(
        selected_candidate,
        request,
        position_tolerance_m=position_tolerance,
        tangent_tolerance_rad=tangent_tolerance,
        pressure_tolerance_fraction=pressure_tolerance,
      )
    )
    next_lower: float | None = None
    next_upper: float | None = None
    if selected_skew is not None and upper - lower > minimum_width:
      next_lower, next_upper = _next_bracket(lower, upper, selected_skew)
    ####
    step_source_lineage = bool(
      target_resolve.source_closure is source_closure
      and target_resolve.request is request
      and target_resolve.request.source_closure_fingerprint == source_fingerprint
    )
    step_target_lineage = bool(
      target_resolve.target_lineage_verified
      and target_resolve.request.proposal is request.proposal
    )
    step_fresh = bool(
      target_resolve.fresh_global_solve_invocation_verified
      and selected_candidate is not None
      and selected_candidate.closure is not source_closure
    )
    step_consumption = bool(
      target_resolve.target_consumption_verified
      and target_resolve.target_coverage_verified
    )
    step_fidelity = bool(
      not target_resolve.global_coupling_verified
      and not target_resolve.downstream_boundary_closure_verified
      and target_resolve.chain_promotion_blocked
      and not target_resolve.production_claim_allowed
      and (
        selected_candidate is None
        or selected_candidate.closure is None
        or not selected_candidate.closure.production_claim_allowed
      )
    )
    step = MocReflectedDomainGlobalFrontierTargetRefinementStep(
      iteration_index=iteration_index,
      lower_skew=lower,
      upper_skew=upper,
      probe_skews=probes,
      target_resolve=target_resolve,
      selected_probe_skew=selected_skew,
      selected_score=selected_score,
      next_lower_skew=next_lower,
      next_upper_skew=next_upper,
      fresh_solver_invocation_verified=step_fresh,
      source_lineage_verified=step_source_lineage,
      target_lineage_verified=step_target_lineage,
      target_consumption_verified=step_consumption,
      target_match_verified=bool(
        selected_candidate is not None and selected_candidate.target_match_verified
      ),
      fidelity_isolation_verified=step_fidelity,
      message=target_resolve.message,
    )
    steps.append(step)
    target_lineage_verified = target_lineage_verified and step_target_lineage
    fresh_global_solve_verified = fresh_global_solve_verified and step_fresh
    target_consumption_verified = target_consumption_verified and step_consumption
    target_coverage_verified = target_coverage_verified and bool(
      target_resolve.target_coverage_verified
    )
    fidelity_isolation_verified = fidelity_isolation_verified and step_fidelity
    if not step_source_lineage or not step_target_lineage or not step_fresh or not step_fidelity:
      status = MocReflectedDomainGlobalFrontierTargetRefinementStatus.FIDELITY_FAILURE
      message = 'target-conditioned refinement failed its source, fresh-solve, or fidelity audit'
      break
    ####
    if (
      selected_candidate is not None
      and selected_candidate.target_match_verified
      and selected_candidate.closure is not None
    ):
      selected_closure = selected_candidate.closure
      target_match_verified = True
      refinement_brackets_verified = all(
        step.next_lower_skew is None
        or step.next_upper_skew is not None
        for step in steps
      )
      status = (
        MocReflectedDomainGlobalFrontierTargetRefinementStatus
        .CONVERGED_TARGET_CONDITIONED_RESEARCH_REFINEMENT
      )
      message = (
        'fresh global target probes reached the declared frontier tolerance; '
        'canonical global coupling and downstream closure remain open'
      )
      break
    ####
    if selected_skew is None:
      target_coverage_verified = False
      status = (
        MocReflectedDomainGlobalFrontierTargetRefinementStatus.TARGET_MISMATCH
      )
      message = (
        'fresh global probes retained no covered finite candidate for the exact '
        'frontier target'
      )
      break
    ####
    if next_lower is None or next_upper is None or next_upper - next_lower < minimum_width:
      refinement_brackets_verified = True
      status = (
        MocReflectedDomainGlobalFrontierTargetRefinementStatus.TARGET_MISMATCH
      )
      message = (
        'fresh global probes remained finite but the bounded skew bracket '
        'reached its minimum width without matching the exact target'
      )
      break
    ####
    lower, upper = next_lower, next_upper
  ####
  if not steps:
    target_lineage_verified = False
    fresh_global_solve_verified = False
    target_consumption_verified = False
    target_coverage_verified = False
    fidelity_isolation_verified = False
  ####
  return _result(
    status,
    request,
    source_closure,
    maximum_iterations,
    configuration,
    steps=tuple(steps),
    selected_closure=selected_closure,
    target_lineage_verified=target_lineage_verified,
    fresh_global_solve_verified=fresh_global_solve_verified,
    target_consumption_verified=target_consumption_verified,
    target_coverage_verified=target_coverage_verified,
    target_match_verified=target_match_verified,
    refinement_brackets_verified=refinement_brackets_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
