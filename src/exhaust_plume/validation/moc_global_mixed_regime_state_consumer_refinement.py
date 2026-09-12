"""Refinement coverage for the full-state mixed-regime consumer lane.

Each named closure is run through a fresh downstream solve at every declared
resolution, then through the full-state consumer and its fresh conservative
boundary re-solve.  The operator records exact lineage and finite residual
coverage without treating the current nonmonotonic research residuals as a
convergence proof.  Canonical global feedback, physical shock-cell fitting,
external validation, and production promotion remain separate gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  MocReflectedDomainGlobalMixedRegimeStateResolveResult,
  consume_reflected_domain_global_mixed_regime_state,
  solve_reflected_domain_global_mixed_regime_state_consumer,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement',
  'measure_reflected_domain_global_mixed_regime_state_consumer_refinement',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementRun',
  'run_reflected_domain_global_mixed_regime_state_consumer_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-state-consumer-refinement-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-state-consumer-refinement-run-v1'
)


class MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the full-state consumer coverage audit."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-global-mixed-regime-state-consumer-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-global-mixed-regime-state-consumer-coverage'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_ID_FAILURE = 'global-mixed-regime-state-consumer-case-id-failure'
  RESOLUTION_FAILURE = (
    'global-mixed-regime-state-consumer-resolution-failure'
  )
  LINEAGE_FAILURE = 'global-mixed-regime-state-consumer-lineage-failure'
  DOWNSTREAM_FAILURE = (
    'global-mixed-regime-state-consumer-downstream-failure'
  )
  CONSUMER_FAILURE = 'global-mixed-regime-state-consumer-consumer-failure'
  STATE_RESOLVE_FAILURE = (
    'global-mixed-regime-state-consumer-state-resolve-failure'
  )
  METRIC_FAILURE = 'global-mixed-regime-state-consumer-metric-failure'
  FIDELITY_FAILURE = 'global-mixed-regime-state-consumer-fidelity-failure'
####


def _validate_resolution(resolution: tuple[int, int]) -> tuple[int, int]:
  value = tuple(resolution)
  if len(value) != 2 or any(
    isinstance(item, bool) or not isinstance(item, int) for item in value
  ):
    raise ValueError('resolution must contain two integer counts')
  ####
  if value[0] < 4 or value[1] < 3:
    raise ValueError(
      'axial resolution must be at least four and transverse resolution '
      'must be at least three'
    )
  ####
  return value
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase:
  """One named source closure and its independent resolution ladder."""

  case_id: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolutions: tuple[tuple[int, int], ...]
  reference_total_temperature_K: float = 1500.0
  ambient_pressure_Pa: float | None = None

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    try:
      resolutions = tuple(_validate_resolution(tuple(value)) for value in self.resolutions)
    except TypeError as error:
      raise ValueError(
        'resolutions must contain (axial, transverse) integer pairs'
      ) from error
    ####
    if not resolutions:
      raise ValueError('resolutions must not be empty')
    ####
    temperature = float(self.reference_total_temperature_K)
    if not isfinite(temperature) or temperature <= 0.0:
      raise ValueError('reference_total_temperature_K must be finite and positive')
    ####
    ambient = self.ambient_pressure_Pa
    if ambient is not None:
      ambient = float(ambient)
      if not isfinite(ambient) or ambient <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      ####
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'resolutions', resolutions)
    object.__setattr__(self, 'reference_total_temperature_K', temperature)
    object.__setattr__(self, 'ambient_pressure_Pa', ambient)
  ####

  @property
  def closure_fingerprint(self) -> str:
    """Return the exact source closure identity for this case."""

    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def resolution_ladder_verified(self) -> bool:
    """Whether the case declares a strict multi-resolution ladder."""

    return bool(
      len(self.resolutions) >= 2
      and all(
        right[0] > left[0] and right[1] > left[1]
        for left, right in zip(self.resolutions, self.resolutions[1:])
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'closure_fingerprint': self.closure_fingerprint,
      'resolutions': self.resolutions,
      'resolution_ladder_verified': self.resolution_ladder_verified,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'closure_status': self.closure.status.value,
      'closure_converged': self.closure.converged,
      'physical_closure_verified': self.closure.physical_closure_verified,
    }
  ####
####


def _source_sample_count(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> int | None:
  global_euler = closure.global_euler
  physical_field = None if global_euler is None else global_euler.physical_field
  field = None if physical_field is None else physical_field.field
  if field is None:
    return None
  ####
  return len(field.ambient_boundary.points_m)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep:
  """One fresh downstream/consumer/state-resolve execution."""

  case_id: str
  resolution: tuple[int, int]
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult
  resolved: MocReflectedDomainGlobalMixedRegimeStateResolveResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    resolution = _validate_resolution(tuple(self.resolution))
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.downstream,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError(
        'downstream must be a MocReflectedDomainGlobalCoupledDownstreamResult'
      )
    ####
    if not isinstance(
      self.consumer,
      MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
    ):
      raise TypeError(
        'consumer must be a '
        'MocReflectedDomainGlobalMixedRegimeStateConsumerResult'
      )
    ####
    if not isinstance(
      self.resolved,
      MocReflectedDomainGlobalMixedRegimeStateResolveResult,
    ):
      raise TypeError(
        'resolved must be a '
        'MocReflectedDomainGlobalMixedRegimeStateResolveResult'
      )
    ####
    if self.downstream.closure is not self.closure:
      raise ValueError('downstream must retain the exact source closure')
    ####
    if self.consumer.closure is not self.closure:
      raise ValueError('consumer must retain the exact source closure')
    ####
    if self.consumer.downstream is not self.downstream:
      raise ValueError('consumer must retain the exact downstream result')
    ####
    if self.resolved.consumer is not self.consumer:
      raise ValueError('resolved result must retain the exact consumer result')
    ####
    if self.downstream.coupled_request is not None:
      request = self.downstream.coupled_request
      if (
        request.axial_cell_count != resolution[0]
        or request.transverse_cell_count != resolution[1]
      ):
        raise ValueError(
          'downstream coupled request must retain the declared resolution'
        )
      ####
    ####
    if self.resolved.request is not None:
      request = self.resolved.request
      if (
        request.axial_cell_count != resolution[0]
        or request.transverse_cell_count != resolution[1]
      ):
        raise ValueError(
          'resolved coupled request must retain the declared resolution'
        )
      ####
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'resolution', resolution)
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def source_sample_count(self) -> int | None:
    return _source_sample_count(self.closure)
  ####

  @property
  def fresh_downstream_verified(self) -> bool:
    trace = self.downstream.downstream_boundary_trace
    return bool(
      self.downstream.converged
      and self.downstream.local_coupled_field_verified
      and trace is not None
      and trace.local_trace_verified
    )
  ####

  @property
  def consumer_lineage_verified(self) -> bool:
    return bool(
      self.consumer.consumed_local_research_state
      and self.consumer.closure_lineage_verified
      and self.consumer.source_closure_fingerprint
      == self.source_closure_fingerprint
      and self.consumer.downstream is self.downstream
    )
  ####

  @property
  def state_resolve_verified(self) -> bool:
    return bool(self.resolved.fresh_local_research_state_resolve_verified)
  ####

  @property
  def maximum_conservative_euler_residual(self) -> float | None:
    field = self.resolved.field
    if field is None or field.maximum_conservative_euler_residual is None:
      return None
    ####
    return float(field.maximum_conservative_euler_residual)
  ####

  @property
  def maximum_free_boundary_pressure_residual_Pa(self) -> float | None:
    field = self.resolved.field
    if field is None:
      return None
    ####
    return float(field.maximum_free_boundary_pressure_residual_Pa)
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      self.downstream.chain_promotion_blocked
      and not self.downstream.production_claim_allowed
      and not self.downstream.global_coupling_verified
      and not self.downstream.downstream_boundary_closure_verified
      and self.consumer.chain_promotion_blocked
      and not self.consumer.production_claim_allowed
      and not self.consumer.canonical_free_boundary_verified
      and not self.consumer.global_coupling_verified
      and self.resolved.chain_promotion_blocked
      and not self.resolved.production_claim_allowed
      and not self.resolved.canonical_free_boundary_verified
      and not self.resolved.global_coupling_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolution': self.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_sample_count': self.source_sample_count,
      'fresh_downstream_verified': self.fresh_downstream_verified,
      'consumer_lineage_verified': self.consumer_lineage_verified,
      'state_resolve_verified': self.state_resolve_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'maximum_conservative_euler_residual': (
        self.maximum_conservative_euler_residual
      ),
      'maximum_free_boundary_pressure_residual_Pa': (
        self.maximum_free_boundary_pressure_residual_Pa
      ),
      'downstream_status': self.downstream.status.value,
      'consumer_status': self.consumer.status.value,
      'resolved_status': self.resolved.status.value,
      'downstream': self.downstream.as_report(),
      'consumer': self.consumer.as_report(),
      'resolved': self.resolved.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement:
  """Independent coverage evidence below the canonical promotion ceiling."""

  status: MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep,
    ...
  ] = ()
  case_ids: tuple[str, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  source_sample_counts: tuple[int | None, ...] = ()
  downstream_statuses: tuple[str, ...] = ()
  consumer_statuses: tuple[str, ...] = ()
  resolved_statuses: tuple[str, ...] = ()
  maximum_conservative_euler_residuals: tuple[float | None, ...] = ()
  maximum_free_boundary_pressure_residuals_Pa: tuple[float | None, ...] = ()
  case_ids_verified: bool = False
  source_closure_bindings_verified: bool = False
  distinct_source_closures_verified: bool = False
  resolution_ladders_verified: bool = False
  fresh_downstream_verified: bool = False
  consumer_lineage_verified: bool = False
  state_resolves_verified: bool = False
  independent_audits_verified: bool = False
  residual_metrics_finite: bool = False
  local_coverage_verified: bool = False
  cross_case_coverage_verified: bool = False
  fidelity_isolation_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus,
    ):
      raise TypeError('status must be a typed state-consumer refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed state-consumer refinement steps')
    ####
    fields = {
      'case_ids': tuple(str(value) for value in self.case_ids),
      'resolutions': tuple(tuple(value) for value in self.resolutions),
      'source_closure_fingerprints': tuple(
        str(value) for value in self.source_closure_fingerprints
      ),
      'source_sample_counts': tuple(self.source_sample_counts),
      'downstream_statuses': tuple(str(value) for value in self.downstream_statuses),
      'consumer_statuses': tuple(str(value) for value in self.consumer_statuses),
      'resolved_statuses': tuple(str(value) for value in self.resolved_statuses),
      'maximum_conservative_euler_residuals': tuple(
        self.maximum_conservative_euler_residuals
      ),
      'maximum_free_boundary_pressure_residuals_Pa': tuple(
        self.maximum_free_boundary_pressure_residuals_Pa
      ),
    }
    if any(len(value) != len(steps) for value in fields.values()):
      raise ValueError('refinement summaries must match the step count')
    ####
    if any(
      value is not None
      and (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
      )
      for value in fields['source_sample_counts']
    ):
      raise ValueError('source_sample_counts must contain nonnegative integers or None')
    ####
    for name in (
      'maximum_conservative_euler_residuals',
      'maximum_free_boundary_pressure_residuals_Pa',
    ):
      if any(
        value is not None
        and (not isfinite(float(value)) or float(value) < 0.0)
        for value in fields[name]
      ):
        raise ValueError(f'{name} must contain finite nonnegative values or None')
      ####
    ####
    for name in (
      'case_ids_verified',
      'source_closure_bindings_verified',
      'distinct_source_closures_verified',
      'resolution_ladders_verified',
      'fresh_downstream_verified',
      'consumer_lineage_verified',
      'state_resolves_verified',
      'independent_audits_verified',
      'residual_metrics_finite',
      'local_coverage_verified',
      'cross_case_coverage_verified',
      'fidelity_isolation_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('state-consumer coverage cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('state-consumer coverage must remain promotion-blocked')
    ####
    object.__setattr__(self, 'steps', steps)
    for name, value in fields.items():
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in (
        MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      )
      and self.local_coverage_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'resolutions': self.resolutions,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'source_sample_counts': self.source_sample_counts,
      'downstream_statuses': self.downstream_statuses,
      'consumer_statuses': self.consumer_statuses,
      'resolved_statuses': self.resolved_statuses,
      'maximum_conservative_euler_residuals': (
        self.maximum_conservative_euler_residuals
      ),
      'maximum_free_boundary_pressure_residuals_Pa': (
        self.maximum_free_boundary_pressure_residuals_Pa
      ),
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'source_closure_bindings_verified': (
          self.source_closure_bindings_verified
        ),
        'distinct_source_closures_verified': (
          self.distinct_source_closures_verified
        ),
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'fresh_downstream_verified': self.fresh_downstream_verified,
        'consumer_lineage_verified': self.consumer_lineage_verified,
        'state_resolves_verified': self.state_resolves_verified,
        'independent_audits_verified': self.independent_audits_verified,
        'residual_metrics_finite': self.residual_metrics_finite,
        'local_coverage_verified': self.local_coverage_verified,
        'cross_case_coverage_verified': self.cross_case_coverage_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'canonical_free_boundary_verified': False,
        'global_coupling_verified': False,
        'external_validation_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'steps': tuple(step.as_report() for step in self.steps),
      'message': self.message,
      'claim_status': (
        'full-state-consumer multi-resolution/cross-case coverage only; '
        'nonmonotonic research residuals do not establish convergence, '
        'canonical global closure, or production validity'
      ),
    }
  ####
####


def _group_indices(
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep],
) -> dict[str, list[int]]:
  grouped: dict[str, list[int]] = {}
  for index, step in enumerate(steps):
    grouped.setdefault(step.case_id, []).append(index)
  ####
  return grouped
####


def _summary_values(
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep],
) -> dict[str, tuple[Any, ...]]:
  return {
    'case_ids': tuple(step.case_id for step in steps),
    'resolutions': tuple(step.resolution for step in steps),
    'source_closure_fingerprints': tuple(
      step.source_closure_fingerprint for step in steps
    ),
    'source_sample_counts': tuple(step.source_sample_count for step in steps),
    'downstream_statuses': tuple(step.downstream.status.value for step in steps),
    'consumer_statuses': tuple(step.consumer.status.value for step in steps),
    'resolved_statuses': tuple(step.resolved.status.value for step in steps),
    'maximum_conservative_euler_residuals': tuple(
      step.maximum_conservative_euler_residual for step in steps
    ),
    'maximum_free_boundary_pressure_residuals_Pa': tuple(
      step.maximum_free_boundary_pressure_residual_Pa for step in steps
    ),
  }
####


def _measurement_failure(
  status: MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus,
  message: str,
  *,
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement:
  values = _summary_values(tuple(steps))
  return MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement(
    status=status,
    steps=tuple(steps),
    **values,
    **flags,
    message=message,
  )
####


def measure_reflected_domain_global_mixed_regime_state_consumer_refinement(
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement:
  """Audit fresh full-state consumer coverage by case and resolution.

  The operator intentionally checks coverage and identity rather than a
  monotonic residual trend.  The current research residuals can be
  nonmonotonic while still providing useful evidence that every declared
  resolution and source closure exercised the same explicit state contract.
  """

  try:
    retained_steps = tuple(steps)
  except TypeError:
    return _measurement_failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
      .INVALID_INPUT,
      'steps must be iterable',
    )
  ####
  if len(retained_steps) < 2:
    return _measurement_failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
      .INVALID_INPUT,
      'state-consumer refinement requires at least two steps',
    )
  ####
  if any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep,
    )
    for step in retained_steps
  ):
    return _measurement_failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
      .INVALID_INPUT,
      'steps must contain typed state-consumer refinement steps',
    )
  ####
  grouped = _group_indices(retained_steps)
  actual_case_ids = tuple(grouped)
  expected = (
    None
    if expected_case_ids is None
    else tuple(str(value) for value in expected_case_ids)
  )
  case_ids_verified = bool(
    actual_case_ids
    and all(actual_case_ids)
    and len(actual_case_ids) == len(set(actual_case_ids))
    and (expected is None or actual_case_ids == expected)
  )
  source_fingerprints = tuple(
    retained_steps[index].source_closure_fingerprint
    for index in (indices[0] for indices in grouped.values())
  )
  source_closure_bindings_verified = bool(
    all(
      step.source_closure_fingerprint
      == step.consumer.source_closure_fingerprint
      and step.downstream.closure_lineage_verified
      and step.consumer.closure_lineage_verified
      and step.resolved.consumer is step.consumer
      for step in retained_steps
    )
  )
  distinct_source_closures_verified = bool(
    len(grouped) >= 2
    and len(set(source_fingerprints)) == len(source_fingerprints)
  )
  resolution_ladders_verified = bool(
    all(
      len(indices) >= 2
      and all(
        retained_steps[right].resolution[0]
        > retained_steps[left].resolution[0]
        and retained_steps[right].resolution[1]
        > retained_steps[left].resolution[1]
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped.values()
    )
  )
  fresh_downstream_verified = all(
    step.fresh_downstream_verified for step in retained_steps
  )
  consumer_lineage_verified = all(
    step.consumer_lineage_verified for step in retained_steps
  )
  state_resolves_verified = all(
    step.state_resolve_verified for step in retained_steps
  )
  independent_audits_verified = all(
    step.resolved.independent_audit_verified for step in retained_steps
  )
  residuals = tuple(
    (
      step.maximum_conservative_euler_residual,
      step.maximum_free_boundary_pressure_residual_Pa,
    )
    for step in retained_steps
  )
  residual_metrics_finite = bool(
    all(
      value is not None and isfinite(float(value)) and float(value) >= 0.0
      for pair in residuals
      for value in pair
    )
  )
  fidelity_isolation_verified = all(
    step.fidelity_isolation_verified for step in retained_steps
  )
  local_coverage_verified = bool(
    case_ids_verified
    and source_closure_bindings_verified
    and resolution_ladders_verified
    and fresh_downstream_verified
    and consumer_lineage_verified
    and state_resolves_verified
    and independent_audits_verified
    and residual_metrics_finite
    and fidelity_isolation_verified
    and not any(
      step.resolved.canonical_free_boundary_verified
      or step.resolved.global_coupling_verified
      or step.resolved.production_claim_allowed
      for step in retained_steps
    )
  )
  cross_case_coverage_verified = bool(
    local_coverage_verified and distinct_source_closures_verified
  )
  status_type = (
    MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStatus
  )
  if not case_ids_verified:
    status = status_type.CASE_ID_FAILURE
    message = 'state-consumer refinement case IDs are missing or unexpected'
  elif not resolution_ladders_verified:
    status = status_type.RESOLUTION_FAILURE
    message = (
      'each named state-consumer case must retain at least two strictly '
      'increasing axial/transverse resolutions'
    )
  elif not source_closure_bindings_verified:
    status = status_type.LINEAGE_FAILURE
    message = (
      'state-consumer steps did not retain the exact source closure fingerprint '
      'through downstream, consumer, and fresh resolve'
    )
  elif not fresh_downstream_verified:
    status = status_type.DOWNSTREAM_FAILURE
    message = 'one or more fresh downstream fields failed local trace coverage'
  elif not consumer_lineage_verified:
    status = status_type.CONSUMER_FAILURE
    message = 'one or more full-state consumers failed their local lineage gate'
  elif not state_resolves_verified or not independent_audits_verified:
    status = status_type.STATE_RESOLVE_FAILURE
    message = (
      'one or more fresh conservative state resolves failed their independent '
      'local audit'
    )
  elif not residual_metrics_finite:
    status = status_type.METRIC_FAILURE
    message = 'state-consumer residual metrics were missing or non-finite'
  elif not fidelity_isolation_verified:
    status = status_type.FIDELITY_FAILURE
    message = 'state-consumer refinement weakened its non-promotion flags'
  elif cross_case_coverage_verified:
    status = status_type.CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    message = (
      'fresh full-state consumer coverage passed across distinct source '
      'closures and increasing resolutions; residual trend convergence, '
      'canonical global feedback, external validation, and production '
      'promotion remain open'
    )
  else:
    status = status_type.CONVERGED_LOCAL_RESEARCH_COVERAGE
    message = (
      'fresh full-state consumer coverage passed across increasing '
      'resolutions; no monotonic residual convergence or canonical promotion '
      'is inferred'
    )
  ####
  return _measurement_failure(
    status,
    message,
    steps=retained_steps,
    case_ids_verified=case_ids_verified,
    source_closure_bindings_verified=source_closure_bindings_verified,
    distinct_source_closures_verified=distinct_source_closures_verified,
    resolution_ladders_verified=resolution_ladders_verified,
    fresh_downstream_verified=fresh_downstream_verified,
    consumer_lineage_verified=consumer_lineage_verified,
    state_resolves_verified=state_resolves_verified,
    independent_audits_verified=independent_audits_verified,
    residual_metrics_finite=residual_metrics_finite,
    local_coverage_verified=local_coverage_verified,
    cross_case_coverage_verified=cross_case_coverage_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementRun:
  """Fresh execution of every named full-state consumer ladder."""

  cases: tuple[
    MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase,
    ...
  ]
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep,
    ...
  ]
  measurement: MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    steps = tuple(self.steps)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed state-consumer refinement cases')
    ####
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed state-consumer refinement steps')
    ####
    expected_count = sum(len(case.resolutions) for case in cases)
    if len(steps) != expected_count:
      raise ValueError('steps must cover every requested case resolution')
    ####
    if not isinstance(
      self.measurement,
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementMeasurement,
    ):
      raise TypeError('measurement must be a typed state-consumer measurement')
    ####
    if tuple(self.measurement.steps) != steps:
      raise ValueError('measurement must retain the exact run steps')
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
    fingerprint = str(self.configuration_fingerprint)
    if len(fingerprint) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'configuration', configuration)
    object.__setattr__(self, 'configuration_fingerprint', fingerprint)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'steps': tuple(step.as_report() for step in self.steps),
      'measurement': self.measurement.as_report(),
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': 'research-only state-consumer coverage',
      'message': self.message,
    }
  ####
####


def _configuration(
  cases: Sequence[MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase],
  runner_options: dict[str, Any],
) -> tuple[tuple[tuple[str, Any], ...], str]:
  payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_REFINEMENT_RUN_OPERATOR_ID
    ),
    'cases': [case.as_report() for case in cases],
    'runner_options': runner_options,
  }
  configuration = tuple(
    (name, payload[name]) for name in sorted(payload)
  )
  fingerprint = sha256(
    json.dumps(
      payload,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  return configuration, fingerprint
####


def run_reflected_domain_global_mixed_regime_state_consumer_refinement(
  cases: Sequence[MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase],
  **runner_options: Any,
) -> MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementRun:
  """Freshly execute every named closure at every requested resolution."""

  try:
    retained_cases = tuple(cases)
  except TypeError as error:
    raise ValueError('cases must be an iterable of typed refinement cases') from error
  ####
  if len(retained_cases) < 1:
    raise ValueError('state-consumer refinement requires at least one case')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementCase,
    )
    for case in retained_cases
  ):
    raise TypeError('cases must contain typed state-consumer refinement cases')
  ####
  case_ids = tuple(case.case_id for case in retained_cases)
  if len(set(case_ids)) != len(case_ids):
    raise ValueError('state-consumer refinement case IDs must be unique')
  ####
  forbidden = {
    'closure',
    'axial_cell_count',
    'transverse_cell_count',
    'reference_total_temperature_K',
    'ambient_pressure_Pa',
  }
  if forbidden.intersection(runner_options):
    raise ValueError(
      'runner_options cannot override closure, resolution, or source '
      'thermodynamic inputs owned by a case'
    )
  ####
  steps: list[
    MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep
  ] = []
  for case in retained_cases:
    for resolution in case.resolutions:
      downstream = solve_reflected_domain_global_coupled_downstream(
        case.closure,
        reference_total_temperature_K=case.reference_total_temperature_K,
        ambient_pressure_Pa=case.ambient_pressure_Pa,
        axial_cell_count=resolution[0],
        transverse_cell_count=resolution[1],
        **runner_options,
      )
      consumer = consume_reflected_domain_global_mixed_regime_state(
        case.closure,
        downstream,
      )
      resolved = solve_reflected_domain_global_mixed_regime_state_consumer(
        consumer
      )
      steps.append(
        MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementStep(
          case_id=case.case_id,
          resolution=resolution,
          closure=case.closure,
          downstream=downstream,
          consumer=consumer,
          resolved=resolved,
        )
      )
    ####
  ####
  retained_steps = tuple(steps)
  measurement = (
    measure_reflected_domain_global_mixed_regime_state_consumer_refinement(
      retained_steps,
      expected_case_ids=case_ids,
    )
  )
  configuration, configuration_fingerprint = _configuration(
    retained_cases,
    runner_options,
  )
  fidelity_isolation_verified = bool(
    measurement.fidelity_isolation_verified
    and measurement.chain_promotion_blocked
    and not measurement.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeStateConsumerRefinementRun(
    cases=retained_cases,
    steps=retained_steps,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(
      len(retained_steps) == sum(len(case.resolutions) for case in retained_cases)
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh downstream/full-state consumer ladders executed independently '
      'for every named closure; residual trend convergence, global feedback, '
      'canonical closure, external validation, and production promotion remain '
      'pending'
    ),
  )
####
