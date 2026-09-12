"""Bounded residual line search for the moving upstream equation corrector.

The P3.35 corrector evaluates one solver-owned moving/global front update.  A
line search is the next control layer: it tries an explicitly bounded list of
correction fractions from the same exact source closure and accepts only a
candidate whose complete upstream state/entropy plus downstream residual
vector does not worsen any component and strictly improves at least one.

Every candidate is a fresh solve.  A candidate with an open residual is
retained as evidence but is never relabeled as an accepted fixed point.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_mixed_regime_moving_upstream_state_equation_corrector import (
  MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
  run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_LINE_SEARCH_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchResult',
  'run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_line_search',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_LINE_SEARCH_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-moving-upstream-state-equation-line-search-v1'
)


class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus(
  str,
  Enum,
):
  """Typed outcomes of the bounded moving-corrector line search."""

  CONVERGED_RESEARCH_LINE_SEARCH = (
    'converged-research-moving-upstream-state-equation-line-search'
  )
  COMPLETED_RESEARCH_LINE_SEARCH_WITH_OPEN_RESIDUAL = (
    'completed-research-moving-upstream-state-equation-line-search-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  LINEAGE_FAILURE = 'moving-upstream-state-equation-line-search-lineage-failure'
  CANDIDATE_FAILURE = 'moving-upstream-state-equation-line-search-candidate-failure'
  RESIDUAL_VECTOR_FAILURE = (
    'moving-upstream-state-equation-line-search-residual-vector-failure'
  )
####


def _fractions(value: Sequence[float]) -> tuple[float, ...]:
  try:
    resolved = tuple(float(item) for item in value)
  except (TypeError, ValueError) as error:
    raise ValueError('correction_fractions must contain numeric values') from error
  ####
  if not resolved:
    raise ValueError('correction_fractions must not be empty')
  ####
  if any(not isfinite(item) or item <= 0.0 or item > 1.0 for item in resolved):
    raise ValueError('correction_fractions must be finite values in (0, 1]')
  ####
  if len(set(resolved)) != len(resolved):
    raise ValueError('correction_fractions must not contain duplicates')
  ####
  return resolved
####


def _componentwise_descent(
  before: tuple[float, ...],
  after: tuple[float, ...],
) -> bool:
  if not before or len(before) != len(after):
    return False
  ####
  if any(
    not isfinite(value) or value < 0.0
    for value in (*before, *after)
  ):
    return False
  ####
  tolerance = 1.0e-12
  nonincreasing = all(
    next_value
    <= current_value + tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  strict = any(
    next_value
    < current_value - tolerance * max(1.0, abs(current_value))
    for current_value, next_value in zip(before, after, strict=True)
  )
  return bool(nonincreasing and strict)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchResult:
  """Evidence from a bounded set of fresh moving-corrector candidates."""

  status: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  correction_fractions: tuple[float, ...] = ()
  attempts: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
    ...,
  ] = ()
  selected_attempt: (
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult
    | None
  ) = None
  baseline_residual_vector: tuple[float, ...] = ()
  selected_residual_vector: tuple[float, ...] = ()
  source_lineage_verified: bool = False
  candidate_vectors_consistent: bool = False
  upstream_state_equation_consumed: bool = False
  independent_replays_verified: bool = False
  moving_global_corrector_verified: bool = False
  componentwise_residual_admission_verified: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus,
    ):
      raise TypeError('status must be a typed line-search status')
    ####
    for name, expected in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('source_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'selected_attempt',
        MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed result')
      ####
    ####
    attempts = tuple(self.attempts)
    if any(
      not isinstance(
        attempt,
        MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
      )
      for attempt in attempts
    ):
      raise TypeError('attempts must contain typed corrector results')
    ####
    fractions = tuple(float(value) for value in self.correction_fractions)
    if any(not isfinite(value) or value <= 0.0 or value > 1.0 for value in fractions):
      raise ValueError('correction_fractions must contain values in (0, 1]')
    ####
    if len(attempts) > len(fractions):
      raise ValueError('attempt count cannot exceed correction-fraction count')
    ####
    for name in ('baseline_residual_vector', 'selected_residual_vector'):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'source_lineage_verified',
      'candidate_vectors_consistent',
      'upstream_state_equation_consumed',
      'independent_replays_verified',
      'moving_global_corrector_verified',
      'componentwise_residual_admission_verified',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('line search cannot claim canonical global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('line search must remain promotion-blocked')
    ####
    if self.selected_attempt is not None and self.selected_attempt not in attempts:
      raise ValueError('selected_attempt must be one of attempts')
    ####
    if self.status is (
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus
      .CONVERGED_RESEARCH_LINE_SEARCH
    ) and not (
      self.selected_attempt is not None
      and self.source_lineage_verified
      and self.candidate_vectors_consistent
      and self.upstream_state_equation_consumed
      and self.independent_replays_verified
      and self.moving_global_corrector_verified
      and self.componentwise_residual_admission_verified
    ):
      raise ValueError('converged line search must pass all candidate gates')
    ####
    object.__setattr__(self, 'correction_fractions', fractions)
    object.__setattr__(self, 'attempts', attempts)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.source_closure is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus
      .CONVERGED_RESEARCH_LINE_SEARCH
      and self.selected_attempt is not None
      and self.componentwise_residual_admission_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_LINE_SEARCH_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'correction_fractions': self.correction_fractions,
      'attempt_count': len(self.attempts),
      'baseline_residual_vector': self.baseline_residual_vector,
      'selected_residual_vector': self.selected_residual_vector,
      'source_lineage_verified': self.source_lineage_verified,
      'candidate_vectors_consistent': self.candidate_vectors_consistent,
      'upstream_state_equation_consumed': self.upstream_state_equation_consumed,
      'independent_replays_verified': self.independent_replays_verified,
      'moving_global_corrector_verified': self.moving_global_corrector_verified,
      'componentwise_residual_admission_verified': (
        self.componentwise_residual_admission_verified
      ),
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'attempts': tuple(attempt.as_report() for attempt in self.attempts),
      'selected_attempt': (
        None
        if self.selected_attempt is None
        else self.selected_attempt.as_report()
      ),
      'claim_status': (
        'research-only bounded moving upstream state/entropy residual line '
        'search; candidate admission is local evidence and does not close the '
        'canonical global/free-boundary, physical shock-cell, validation, or '
        'production gates'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus,
  message: str,
  *,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  correction_fractions: tuple[float, ...] = (),
  attempts: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
    ...,
  ] = (),
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchResult:
  return MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchResult(
    status=status,
    source_closure=source_closure,
    source_downstream=source_downstream,
    correction_fractions=correction_fractions,
    attempts=attempts,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_line_search(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  *,
  reference_total_temperature_K: float,
  correction_fractions: Sequence[float] = (0.005, 0.0025, 0.00125),
  equation_options: dict[str, Any] | None = None,
  moving_interface_options: dict[str, Any] | None = None,
  state_resolve_options: dict[str, Any] | None = None,
  state_boundary_condition_options: dict[str, Any] | None = None,
  downstream_options: dict[str, Any] | None = None,
  geometry_response_options: dict[str, Any] | None = None,
  max_equation_pseudo_iterations: int = 80,
  consumer_id: str = (
    'research-global-mixed-regime-moving-upstream-state-equation-line-search-v1'
  ),
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchResult:
  """Try fresh correction fractions and accept only component-wise descent."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationLineSearchStatus
  )
  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _result(status_type.INVALID_INPUT, 'closure must be a typed global physical closure')
  ####
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _result(
      status_type.INVALID_INPUT,
      'downstream must be a typed global coupled-downstream result',
      source_closure=closure,
    )
  ####
  try:
    fractions = _fractions(correction_fractions)
    temperature = float(reference_total_temperature_K)
    resolved_equation_options = None if equation_options is None else dict(equation_options)
    resolved_moving_options = None if moving_interface_options is None else dict(moving_interface_options)
    resolved_state_options = None if state_resolve_options is None else dict(state_resolve_options)
    resolved_boundary_options = (
      None
      if state_boundary_condition_options is None
      else dict(state_boundary_condition_options)
    )
    resolved_downstream_options = None if downstream_options is None else dict(downstream_options)
    resolved_geometry_options = None if geometry_response_options is None else dict(geometry_response_options)
    resolved_consumer_id = str(consumer_id)
  except (TypeError, ValueError) as error:
    return _result(status_type.INVALID_INPUT, f'line-search controls are invalid: {error}', source_closure=closure, source_downstream=downstream)
  ####
  if not isfinite(temperature) or temperature <= 0.0:
    return _result(status_type.INVALID_INPUT, 'reference_total_temperature_K must be finite and positive', source_closure=closure, source_downstream=downstream)
  ####
  if not resolved_consumer_id:
    return _result(status_type.INVALID_INPUT, 'consumer_id must be non-empty', source_closure=closure, source_downstream=downstream)
  ####
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  source_lineage = bool(
    closure.converged
    and closure.physical_closure_verified
    and downstream.closure is closure
    and downstream.closure_lineage_verified
    and downstream.source_closure_fingerprint == fingerprint
  )
  if not source_lineage:
    return _result(
      status_type.LINEAGE_FAILURE,
      'source downstream result did not retain the exact verified closure identity',
      source_closure=closure,
      source_downstream=downstream,
      correction_fractions=fractions,
    )
  ####
  attempts: list[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
  ] = []
  baseline: tuple[float, ...] | None = None
  selected: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult | None = None
  candidate_vectors_consistent = True
  for index, fraction in enumerate(fractions):
    try:
      attempt = run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector(
        closure,
        downstream,
        reference_total_temperature_K=temperature,
        correction_fraction=fraction,
        equation_options=resolved_equation_options,
        moving_interface_options=resolved_moving_options,
        state_resolve_options=resolved_state_options,
        state_boundary_condition_options=resolved_boundary_options,
        downstream_options=resolved_downstream_options,
        geometry_response_options=resolved_geometry_options,
        max_equation_pseudo_iterations=max_equation_pseudo_iterations,
        consumer_id=f'{resolved_consumer_id}:candidate-{index}',
        require_componentwise_residual_descent=False,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _result(
        status_type.CANDIDATE_FAILURE,
        f'line-search candidate {fraction} raised: {error}',
        source_closure=closure,
        source_downstream=downstream,
        correction_fractions=fractions,
        attempts=tuple(attempts),
        source_lineage_verified=source_lineage,
        candidate_vectors_consistent=candidate_vectors_consistent,
      )
    ####
    attempts.append(attempt)
    vector = tuple(attempt.initial_combined_residual_vector)
    if vector:
      if baseline is None:
        baseline = vector
      elif vector != baseline:
        candidate_vectors_consistent = False
        return _result(
          status_type.RESIDUAL_VECTOR_FAILURE,
          'fresh candidates did not retain an identical source residual vector',
          source_closure=closure,
          source_downstream=downstream,
          correction_fractions=fractions,
          attempts=tuple(attempts),
          baseline_residual_vector=baseline,
          source_lineage_verified=source_lineage,
          candidate_vectors_consistent=False,
        )
      ####
    ####
    if (
      attempt.research_corrector_verified
      and attempt.combined_componentwise_residual_descent_verified
    ):
      selected = attempt
      break
    ####
  ####
  if selected is None:
    return _result(
      status_type.COMPLETED_RESEARCH_LINE_SEARCH_WITH_OPEN_RESIDUAL,
      'all fresh correction candidates were retained, but none passed the '
      'complete component-wise upstream/downstream residual admission gate',
      source_closure=closure,
      source_downstream=downstream,
      correction_fractions=fractions,
      attempts=tuple(attempts),
      baseline_residual_vector=() if baseline is None else baseline,
      candidate_vectors_consistent=candidate_vectors_consistent,
      source_lineage_verified=source_lineage,
      upstream_state_equation_consumed=bool(
        attempts
        and all(attempt.upstream_state_equation_consumed for attempt in attempts)
      ),
      independent_replays_verified=bool(
        attempts
        and all(
          attempt.initial_equation_replay_verified
          and attempt.final_equation_replay_verified
          for attempt in attempts
        )
      ),
      moving_global_corrector_verified=bool(
        attempts and all(attempt.moving_global_corrector_verified for attempt in attempts)
      ),
      componentwise_residual_admission_verified=False,
    )
  ####
  return _result(
    status_type.CONVERGED_RESEARCH_LINE_SEARCH,
    'a fresh bounded correction candidate passed exact upstream state/entropy '
    'and downstream component-wise residual admission; canonical global '
    'closure and production gates remain closed',
    source_closure=closure,
    source_downstream=downstream,
    correction_fractions=fractions,
    attempts=tuple(attempts),
    selected_attempt=selected,
    baseline_residual_vector=() if baseline is None else baseline,
    selected_residual_vector=selected.final_combined_residual_vector,
    source_lineage_verified=source_lineage,
    candidate_vectors_consistent=candidate_vectors_consistent,
    upstream_state_equation_consumed=selected.upstream_state_equation_consumed,
    independent_replays_verified=bool(
      selected.initial_equation_replay_verified
      and selected.final_equation_replay_verified
    ),
    moving_global_corrector_verified=selected.moving_global_corrector_verified,
    componentwise_residual_admission_verified=True,
  )
####
