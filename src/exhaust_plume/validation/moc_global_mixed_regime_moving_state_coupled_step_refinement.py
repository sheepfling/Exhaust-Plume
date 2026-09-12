"""Cross-case and resolution coverage for the moving/global MOC composition.

The P3.31 composition is intentionally a research harness, not a canonical
free-boundary solver.  This module makes its coverage requirement executable:
each supplied source closure is freshly solved at an increasing downstream
resolution ladder, the moving conservative/entropy response is independently
retained, the returned geometry is reconciled into a fresh global closure, and
the final trace is audited again.  Component-wise residual descent is reported
as its own gate and is never inferred from a scalar norm or from coverage.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_mixed_regime_moving_state_coupled_step import (
  MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult,
  MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus,
  run_reflected_domain_global_mixed_regime_moving_state_coupled_step,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_STATE_COUPLED_STEP_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementMeasurement',
  'measure_reflected_domain_global_mixed_regime_moving_state_coupled_step_refinement',
  'run_reflected_domain_global_mixed_regime_moving_state_coupled_step_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_STATE_COUPLED_STEP_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-moving-state-coupled-step-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the moving/global coverage audit."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-moving-global-state-coupled-step-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-moving-global-state-coupled-step-coverage'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = (
    'moving-global-state-coupled-step-refinement-case-failure'
  )
  LINEAGE_FAILURE = (
    'moving-global-state-coupled-step-refinement-lineage-failure'
  )
  RESOLUTION_ORDER_FAILURE = (
    'moving-global-state-coupled-step-refinement-resolution-order-failure'
  )
  MOVING_GATE_FAILURE = (
    'moving-global-state-coupled-step-refinement-moving-gate-failure'
  )
  GEOMETRY_GATE_FAILURE = (
    'moving-global-state-coupled-step-refinement-geometry-gate-failure'
  )
  FINAL_TRACE_FAILURE = (
    'moving-global-state-coupled-step-refinement-final-trace-failure'
  )
  RESIDUAL_METRIC_FAILURE = (
    'moving-global-state-coupled-step-refinement-residual-metric-failure'
  )
  RESIDUAL_DESCENT_FAILURE = (
    'moving-global-state-coupled-step-refinement-residual-descent-failure'
  )
  FIDELITY_FAILURE = (
    'moving-global-state-coupled-step-refinement-fidelity-failure'
  )
####


def _options(value: Mapping[str, Any] | None, name: str) -> dict[str, Any]:
  if value is None:
    return {}
  ####
  if not isinstance(value, Mapping):
    raise TypeError(f'{name} must be a mapping when supplied')
  ####
  return dict(value)
####


def _resolution(value: object, name: str) -> tuple[int, int]:
  try:
    resolved = tuple(value)  # type: ignore[arg-type]
  except TypeError as error:
    raise ValueError(f'{name} must contain an axial/transverse pair') from error
  ####
  if (
    len(resolved) != 2
    or any(isinstance(item, bool) or not isinstance(item, int) for item in resolved)
    or resolved[0] < 8
    or resolved[1] < 4
  ):
    raise ValueError(
      f'{name} must contain integer counts with axial >= 8 and transverse >= 4'
    )
  ####
  return int(resolved[0]), int(resolved[1])
####


def _strictly_increasing(resolutions: tuple[tuple[int, int], ...]) -> bool:
  return bool(
    len(resolutions) >= 2
    and all(
      right[0] > left[0] and right[1] > left[1]
      for left, right in zip(resolutions, resolutions[1:])
    )
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementCase:
  """One source closure with a declared increasing resolution ladder."""

  case_id: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolutions: tuple[tuple[int, int], ...]
  reference_total_temperature_K: float
  ambient_pressure_Pa: float | None = None
  moving_interface_options: Mapping[str, Any] | None = None
  downstream_options: Mapping[str, Any] | None = None
  state_resolve_options: Mapping[str, Any] | None = None
  state_boundary_condition_options: Mapping[str, Any] | None = None
  geometry_response_options: Mapping[str, Any] | None = None

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
    resolutions = tuple(_resolution(item, 'resolution') for item in self.resolutions)
    if len(resolutions) < 2 or not _strictly_increasing(resolutions):
      raise ValueError(
        'resolutions must contain at least two strictly increasing '
        '(axial, transverse) pairs'
      )
    ####
    temperature = float(self.reference_total_temperature_K)
    if not isfinite(temperature) or temperature <= 0.0:
      raise ValueError(
        'reference_total_temperature_K must be finite and positive'
      )
    ####
    ambient = self.ambient_pressure_Pa
    if ambient is not None:
      ambient = float(ambient)
      if not isfinite(ambient) or ambient <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      ####
    ####
    for value, name in (
      (self.moving_interface_options, 'moving_interface_options'),
      (self.downstream_options, 'downstream_options'),
      (self.state_resolve_options, 'state_resolve_options'),
      (
        self.state_boundary_condition_options,
        'state_boundary_condition_options',
      ),
      (self.geometry_response_options, 'geometry_response_options'),
    ):
      if value is not None and not isinstance(value, Mapping):
        raise TypeError(f'{name} must be a mapping when supplied')
      ####
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'resolutions', resolutions)
    object.__setattr__(self, 'reference_total_temperature_K', temperature)
    object.__setattr__(self, 'ambient_pressure_Pa', ambient)
    for name in (
      'moving_interface_options',
      'downstream_options',
      'state_resolve_options',
      'state_boundary_condition_options',
      'geometry_response_options',
    ):
      value = getattr(self, name)
      if value is not None:
        object.__setattr__(self, name, dict(value))
      ####
    ####
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def resolution_ladder_verified(self) -> bool:
    return _strictly_increasing(self.resolutions)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolutions': self.resolutions,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'resolution_ladder_verified': self.resolution_ladder_verified,
      'closure': self.closure.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep:
  """One freshly solved composition at one declared resolution."""

  case_id: str
  resolution: tuple[int, int]
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  initial_downstream: MocReflectedDomainGlobalCoupledDownstreamResult
  result: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    resolution = _resolution(self.resolution, 'resolution')
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.initial_downstream,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError(
        'initial_downstream must be a '
        'MocReflectedDomainGlobalCoupledDownstreamResult'
      )
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepResult,
    ):
      raise TypeError(
        'result must be a typed moving/global state-coupled-step result'
      )
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
  def source_closure_binding_verified(self) -> bool:
    return bool(
      self.result.source_closure is self.closure
      and self.result.source_closure_fingerprint == self.source_closure_fingerprint
      and self.result.source_downstream is self.initial_downstream
      and self.initial_downstream.closure is self.closure
      and self.initial_downstream.closure_lineage_verified
    )
  ####

  @property
  def resolution_verified(self) -> bool:
    candidates = (
      self.initial_downstream,
      self.result.final_downstream,
    )
    return bool(
      all(
        candidate is not None
        and candidate.coupled_request is not None
        and candidate.coupled_request.axial_cell_count == self.resolution[0]
        and candidate.coupled_request.transverse_cell_count == self.resolution[1]
        for candidate in candidates
      )
    )
  ####

  @property
  def moving_gates_verified(self) -> bool:
    return bool(
      self.result.moving_lineage_verified
      and self.result.moving_conservative_flux_closure_verified
      and self.result.moving_entropy_transition_verified
      and self.result.moving_global_physical_field_consumed
      and self.result.moving_interface is not None
      and self.result.moving_interface.converged
    )
  ####

  @property
  def geometry_gate_verified(self) -> bool:
    return bool(
      self.result.moving_geometry_reconciliation_verified
      and self.result.geometry_closure is not None
      and self.result.geometry_closure.converged
      and self.result.geometry_closure.physical_closure_verified
    )
  ####

  @property
  def final_trace_verified(self) -> bool:
    return bool(
      self.result.final_trace_audit_verified
      and self.result.final_state_consumer is not None
      and self.result.final_state_consumer.consumed_local_research_state
      and self.result.final_downstream is not None
      and self.result.final_downstream.converged
    )
  ####

  @property
  def residual_metrics_finite(self) -> bool:
    vectors = (
      self.result.initial_residual_vector,
      self.result.final_residual_vector,
    )
    return bool(
      all(len(vector) == 10 for vector in vectors)
      and all(
        isfinite(value) and value >= 0.0
        for vector in vectors
        for value in vector
      )
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    moving = self.result.moving_interface
    geometry = self.result.geometry_closure
    return bool(
      self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and not self.result.upstream_state_equation_consumed
      and not self.result.global_coupling_verified
      and not self.result.canonical_free_boundary_verified
      and moving is not None
      and moving.chain_promotion_blocked
      and not moving.production_claim_allowed
      and not moving.physical_closure_verified
      and geometry is not None
      and not geometry.production_claim_allowed
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.result.status
      in (
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
        .CONVERGED_RESEARCH_MOVING_GLOBAL_STATE_STEP,
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepStatus
        .COMPLETED_RESEARCH_MOVING_GLOBAL_STATE_STEP_WITH_OPEN_RESIDUAL,
      )
      and self.source_closure_binding_verified
      and self.resolution_verified
      and self.result.state_target_consumed_by_downstream_equations
      and self.moving_gates_verified
      and self.geometry_gate_verified
      and self.final_trace_verified
      and self.residual_metrics_finite
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolution': self.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_closure_binding_verified': self.source_closure_binding_verified,
      'resolution_verified': self.resolution_verified,
      'moving_gates_verified': self.moving_gates_verified,
      'geometry_gate_verified': self.geometry_gate_verified,
      'final_trace_verified': self.final_trace_verified,
      'residual_metrics_finite': self.residual_metrics_finite,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'locally_verified': self.locally_verified,
      'initial_downstream': self.initial_downstream.as_report(),
      'result': self.result.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementMeasurement:
  """Cross-case coverage below canonical and production claim ceilings."""

  status: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep,
    ...
  ] = ()
  case_ids: tuple[str, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  initial_residual_vectors: tuple[tuple[float, ...], ...] = ()
  final_residual_vectors: tuple[tuple[float, ...], ...] = ()
  componentwise_residual_descent: tuple[bool, ...] = ()
  case_ids_verified: bool = False
  source_closure_bindings_verified: bool = False
  distinct_source_closures_verified: bool = False
  resolution_ladders_verified: bool = False
  local_composition_verified: bool = False
  moving_gates_verified: bool = False
  geometry_reconciliation_verified: bool = False
  final_trace_verified: bool = False
  residual_metrics_finite: bool = False
  componentwise_residual_descent_verified: bool = False
  cross_case_coverage_verified: bool = False
  fidelity_isolation_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  require_componentwise_residual_descent: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_STATE_COUPLED_STEP_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus,
    ):
      raise TypeError('status must be a typed moving/global refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed moving/global refinement steps')
    ####
    fields = {
      'case_ids': tuple(str(value) for value in self.case_ids),
      'resolutions': tuple(_resolution(value, 'resolution') for value in self.resolutions),
      'source_closure_fingerprints': tuple(
        str(value) for value in self.source_closure_fingerprints
      ),
      'initial_residual_vectors': tuple(
        tuple(float(item) for item in value)
        for value in self.initial_residual_vectors
      ),
      'final_residual_vectors': tuple(
        tuple(float(item) for item in value)
        for value in self.final_residual_vectors
      ),
      'componentwise_residual_descent': tuple(
        bool(value) for value in self.componentwise_residual_descent
      ),
    }
    if any(len(value) != len(steps) for value in fields.values()):
      raise ValueError('refinement summaries must match the step count')
    ####
    if any(
      len(vector) not in (0, 10)
      or any(not isfinite(value) or value < 0.0 for value in vector)
      for vectors in (
        fields['initial_residual_vectors'],
        fields['final_residual_vectors'],
      )
      for vector in vectors
    ):
      raise ValueError(
        'residual vectors must be empty or contain ten finite nonnegative '
        'channels'
      )
    ####
    for name in (
      'case_ids_verified',
      'source_closure_bindings_verified',
      'distinct_source_closures_verified',
      'resolution_ladders_verified',
      'local_composition_verified',
      'moving_gates_verified',
      'geometry_reconciliation_verified',
      'final_trace_verified',
      'residual_metrics_finite',
      'componentwise_residual_descent_verified',
      'cross_case_coverage_verified',
      'fidelity_isolation_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'require_componentwise_residual_descent',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('moving/global refinement cannot claim canonical coupling')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('moving/global refinement must remain promotion-blocked')
    ####
    object.__setattr__(self, 'steps', steps)
    for name, value in fields.items():
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def research_coverage_verified(self) -> bool:
    return bool(
      self.status
      in (
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      )
      and self.local_composition_verified
      and self.resolution_ladders_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def converged(self) -> bool:
    return self.research_coverage_verified
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'research_coverage_verified': self.research_coverage_verified,
      'case_ids': self.case_ids,
      'resolutions': self.resolutions,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'initial_residual_vectors': self.initial_residual_vectors,
      'final_residual_vectors': self.final_residual_vectors,
      'componentwise_residual_descent': self.componentwise_residual_descent,
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'source_closure_bindings_verified': self.source_closure_bindings_verified,
        'distinct_source_closures_verified': self.distinct_source_closures_verified,
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'local_composition_verified': self.local_composition_verified,
        'moving_gates_verified': self.moving_gates_verified,
        'geometry_reconciliation_verified': self.geometry_reconciliation_verified,
        'final_trace_verified': self.final_trace_verified,
        'residual_metrics_finite': self.residual_metrics_finite,
        'componentwise_residual_descent_verified': (
          self.componentwise_residual_descent_verified
        ),
        'cross_case_coverage_verified': self.cross_case_coverage_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'canonical_free_boundary_verified': False,
        'global_coupling_verified': False,
        'external_validation_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'steps': tuple(step.as_report() for step in self.steps),
      'require_componentwise_residual_descent': (
        self.require_componentwise_residual_descent
      ),
      'message': self.message,
      'claim_status': (
        'research-only disjoint-case and increasing-resolution coverage for '
        'the moving/global composition; open component-wise residuals do not '
        'establish a canonical global fixed point or production validity'
      ),
    }
  ####
####


def _summary(
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep,
    ...
  ],
) -> dict[str, tuple[Any, ...]]:
  return {
    'case_ids': tuple(step.case_id for step in steps),
    'resolutions': tuple(step.resolution for step in steps),
    'source_closure_fingerprints': tuple(
      step.source_closure_fingerprint for step in steps
    ),
    'initial_residual_vectors': tuple(
      step.result.initial_residual_vector for step in steps
    ),
    'final_residual_vectors': tuple(
      step.result.final_residual_vector for step in steps
    ),
    'componentwise_residual_descent': tuple(
      step.result.componentwise_residual_descent_verified for step in steps
    ),
  }
####


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus,
  message: str,
  *,
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep,
    ...
  ] = (),
  require_componentwise_residual_descent: bool = False,
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementMeasurement:
  values = _summary(steps)
  return MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementMeasurement(
    status=status,
    steps=steps,
    **values,
    **flags,
    require_componentwise_residual_descent=require_componentwise_residual_descent,
    message=message,
  )
####


def _group_indices(
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep,
    ...
  ],
) -> dict[str, list[int]]:
  grouped: dict[str, list[int]] = {}
  for index, step in enumerate(steps):
    grouped.setdefault(step.case_id, []).append(index)
  ####
  return grouped
####


def measure_reflected_domain_global_mixed_regime_moving_state_coupled_step_refinement(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep
  ],
  *,
  require_componentwise_residual_descent: bool = False,
) -> MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementMeasurement:
  """Independently check local, cross-case, and resolution coverage."""

  if not isinstance(require_componentwise_residual_descent, bool):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'require_componentwise_residual_descent must be a bool',
    )
  ####
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'steps must be iterable',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if len(retained) < 2:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'refinement requires at least two solved steps',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'steps must contain typed moving/global refinement steps',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  grouped = _group_indices(retained)
  case_ids_verified = bool(
    all(grouped)
    and len(grouped) == len(set(grouped))
  )
  fingerprints_by_case = {
    case_id: retained[indices[0]].source_closure_fingerprint
    for case_id, indices in grouped.items()
  }
  source_bindings = all(
    step.source_closure_binding_verified for step in retained
  )
  distinct_source_closures = bool(
    len(grouped) >= 2
    and len(set(fingerprints_by_case.values())) == len(grouped)
  )
  resolution_ladders = bool(
    all(
      len(indices) >= 2
      and all(
        retained[right].resolution[0] > retained[left].resolution[0]
        and retained[right].resolution[1] > retained[left].resolution[1]
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped.values()
    )
  )
  local_composition = all(step.locally_verified for step in retained)
  moving_gates = all(step.moving_gates_verified for step in retained)
  geometry_gates = all(step.geometry_gate_verified for step in retained)
  final_trace = all(step.final_trace_verified for step in retained)
  residuals_finite = all(step.residual_metrics_finite for step in retained)
  componentwise = tuple(
    step.result.componentwise_residual_descent_verified for step in retained
  )
  componentwise_verified = bool(componentwise and all(componentwise))
  fidelity = all(step.fidelity_isolation_verified for step in retained)
  cross_case = bool(
    case_ids_verified
    and distinct_source_closures
    and resolution_ladders
    and local_composition
    and moving_gates
    and geometry_gates
    and final_trace
    and residuals_finite
    and fidelity
    and len(grouped) >= 2
  )
  common = dict(
    steps=retained,
    require_componentwise_residual_descent=require_componentwise_residual_descent,
    case_ids_verified=case_ids_verified,
    source_closure_bindings_verified=source_bindings,
    distinct_source_closures_verified=distinct_source_closures,
    resolution_ladders_verified=resolution_ladders,
    local_composition_verified=local_composition,
    moving_gates_verified=moving_gates,
    geometry_reconciliation_verified=geometry_gates,
    final_trace_verified=final_trace,
    residual_metrics_finite=residuals_finite,
    componentwise_residual_descent_verified=componentwise_verified,
    cross_case_coverage_verified=cross_case,
    fidelity_isolation_verified=fidelity,
  )
  if not case_ids_verified or not source_bindings:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.LINEAGE_FAILURE,
      'one or more steps do not retain exact source closure and initial '
      'downstream lineage',
      **common,
    )
  ####
  if not resolution_ladders:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.RESOLUTION_ORDER_FAILURE,
      'every case must retain at least two strictly increasing resolutions',
      **common,
    )
  ####
  if not local_composition or not residuals_finite:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.CASE_FAILURE,
      'one or more declared case/resolution steps did not pass local '
      'moving/global composition or residual-shape gates',
      **common,
    )
  ####
  if not moving_gates:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.MOVING_GATE_FAILURE,
      'one or more moving responses did not pass strict conservative, entropy, '
      'field-consumption, or exact-lineage gates',
      **common,
    )
  ####
  if not geometry_gates:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.GEOMETRY_GATE_FAILURE,
      'one or more moving geometries did not reconcile into a fresh global '
      'physical closure',
      **common,
    )
  ####
  if not final_trace:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.FINAL_TRACE_FAILURE,
      'one or more post-geometry downstream traces failed independent replay',
      **common,
    )
  ####
  if not residuals_finite:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.RESIDUAL_METRIC_FAILURE,
      'one or more normalized residual vectors are not finite ten-channel '
      'metrics',
      **common,
    )
  ####
  if not fidelity:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.FIDELITY_FAILURE,
      'one or more results do not retain the research-only promotion block',
      **common,
    )
  ####
  if require_componentwise_residual_descent and not componentwise_verified:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.RESIDUAL_DESCENT_FAILURE,
      'coverage completed, but at least one component-wise residual descent '
      'gate remains open',
      **common,
    )
  ####
  status = (
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
    .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    if len(grouped) >= 2
    else (
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .CONVERGED_LOCAL_RESEARCH_COVERAGE
    )
  )
  return _measurement(
    status,
    'each declared case retained exact closure lineage, increasing resolution, '
    'strict moving conservative/entropy evidence, fresh global geometry '
    'reconciliation, and independent final trace replay; component-wise '
    'residual descent remains a separately reported research gate',
    **common,
  )
####


def _ambient_pressure(
  case: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementCase,
) -> float | None:
  # The global source-band pressure and the mixed-regime downstream control
  # pressure are distinct contracts on the retained fixture.  Requiring the
  # downstream pressure explicitly prevents this runner from selecting a
  # numerically plausible but physically different ambient target.
  return case.ambient_pressure_Pa
####


def _resolution_downstream_options(
  case: MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementCase,
  resolution: tuple[int, int],
  *,
  max_pseudo_iterations: int,
  max_shape_iterations: int,
) -> dict[str, Any]:
  options = _options(case.downstream_options, 'downstream_options')
  reserved = (
    'closure',
    'reference_total_temperature_K',
    'ambient_pressure_Pa',
    'physical_field_continuation_profile',
    'physical_field_shock_front_condition',
    'transonic_shock_interface_field_placement',
    'boundary_pressure_profile',
    'boundary_geometry_profile',
  )
  collisions = tuple(key for key in reserved if key in options)
  if collisions:
    raise ValueError(
      'downstream_options cannot carry composed or stale handoffs: '
      + ', '.join(collisions)
    )
  ####
  for name, value in (
    ('axial_station_count', resolution[0]),
    ('axial_cell_count', resolution[0]),
    ('transverse_cell_count', resolution[1]),
  ):
    if name in options and options[name] != value:
      raise ValueError(f'downstream_options.{name} must match declared resolution')
    ####
    options[name] = value
  ####
  options.setdefault('max_pseudo_iterations', max_pseudo_iterations)
  options.setdefault('max_shape_iterations', max_shape_iterations)
  return options
####


def run_reflected_domain_global_mixed_regime_moving_state_coupled_step_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementCase
  ],
  *,
  max_pseudo_iterations: int = 400,
  max_shape_iterations: int = 12,
  correction_fraction: float = 0.005,
  require_componentwise_residual_descent: bool = False,
) -> MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementMeasurement:
  """Freshly solve each case/resolution pair and measure the coverage."""

  if not isinstance(require_componentwise_residual_descent, bool):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'require_componentwise_residual_descent must be a bool',
    )
  ####
  if (
    isinstance(max_pseudo_iterations, bool)
    or not isinstance(max_pseudo_iterations, int)
    or max_pseudo_iterations < 1
  ):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'max_pseudo_iterations must be a positive integer',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if (
    isinstance(max_shape_iterations, bool)
    or not isinstance(max_shape_iterations, int)
    or max_shape_iterations < 1
  ):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'max_shape_iterations must be a positive integer',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    fraction = float(correction_fraction)
  except (TypeError, ValueError):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'correction_fraction must be numeric',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'correction_fraction must be finite and in (0, 1]',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  try:
    case_values = tuple(cases)
  except TypeError:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'cases must be iterable',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if not case_values:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'cases must not be empty',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementCase,
    )
    for case in case_values
  ):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus
      .INVALID_INPUT,
      'cases must contain typed moving/global refinement cases',
      require_componentwise_residual_descent=require_componentwise_residual_descent,
    )
  ####
  retained_steps: list[
    MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep
  ] = []
  for case in case_values:
    ambient = _ambient_pressure(case)
    if ambient is None or not isfinite(float(ambient)) or float(ambient) <= 0.0:
      return _measurement(
        MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.INVALID_INPUT,
        f'case {case.case_id} has no finite positive ambient pressure',
        steps=tuple(retained_steps),
        require_componentwise_residual_descent=require_componentwise_residual_descent,
      )
    ####
    for resolution in case.resolutions:
      try:
        downstream_options = _resolution_downstream_options(
          case,
          resolution,
          max_pseudo_iterations=max_pseudo_iterations,
          max_shape_iterations=max_shape_iterations,
        )
        initial_downstream = solve_reflected_domain_global_coupled_downstream(
          case.closure,
          reference_total_temperature_K=case.reference_total_temperature_K,
          ambient_pressure_Pa=float(ambient),
          **downstream_options,
        )
        composition = (
          run_reflected_domain_global_mixed_regime_moving_state_coupled_step(
            case.closure,
            initial_downstream,
            reference_total_temperature_K=case.reference_total_temperature_K,
            ambient_pressure_Pa=float(ambient),
            correction_fraction=fraction,
            consumer_id=(
              f'research-{case.case_id}-moving-state-coupled-step-v1'
            ),
            require_componentwise_residual_descent=(
              require_componentwise_residual_descent
            ),
            state_resolve_options=case.state_resolve_options,
            state_boundary_condition_options=(
              case.state_boundary_condition_options
            ),
            moving_interface_options=case.moving_interface_options,
            downstream_options=downstream_options,
            geometry_response_options=case.geometry_response_options,
          )
        )
        retained_steps.append(
          MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStep(
            case_id=case.case_id,
            resolution=resolution,
            closure=case.closure,
            initial_downstream=initial_downstream,
            result=composition,
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return _measurement(
          MocReflectedDomainGlobalMixedRegimeMovingStateCoupledStepRefinementStatus.CASE_FAILURE,
          f'case {case.case_id} at resolution {resolution} failed: {error}',
          steps=tuple(retained_steps),
          require_componentwise_residual_descent=require_componentwise_residual_descent,
        )
      ####
    ####
  ####
  return measure_reflected_domain_global_mixed_regime_moving_state_coupled_step_refinement(
    tuple(retained_steps),
    require_componentwise_residual_descent=require_componentwise_residual_descent,
  )
####
