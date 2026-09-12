"""Disjoint-case and resolution coverage for the moving upstream corrector.

This module runs the P3.35 moving upstream state/entropy corrector on fresh
downstream solves for every declared source closure and resolution.  It
proves that the exact target frame, moving/global handoff, and independent
equation replays survive a refinement ladder.  It deliberately reports
component-wise residual admission as a separate gate: coverage is not
canonical fixed-point convergence.
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
from exhaust_plume.validation.moc_global_mixed_regime_moving_upstream_state_equation_corrector import (
  MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
  run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementMeasurement',
  'measure_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector_refinement',
  'run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-moving-upstream-state-equation-corrector-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the moving upstream-corrector coverage audit."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-moving-upstream-corrector-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-moving-upstream-corrector-coverage'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'moving-upstream-corrector-refinement-case-failure'
  CASE_ID_FAILURE = 'moving-upstream-corrector-refinement-case-id-failure'
  RESOLUTION_FAILURE = 'moving-upstream-corrector-refinement-resolution-failure'
  LINEAGE_FAILURE = 'moving-upstream-corrector-refinement-lineage-failure'
  EQUATION_FAILURE = 'moving-upstream-corrector-refinement-equation-failure'
  MOVING_FAILURE = 'moving-upstream-corrector-refinement-moving-failure'
  METRIC_FAILURE = 'moving-upstream-corrector-refinement-metric-failure'
  FIDELITY_FAILURE = 'moving-upstream-corrector-refinement-fidelity-failure'
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


def _increasing(resolutions: tuple[tuple[int, int], ...]) -> bool:
  return bool(
    len(resolutions) >= 2
    and all(
      right[0] > left[0] and right[1] > left[1]
      for left, right in zip(resolutions, resolutions[1:])
    )
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementCase:
  """One source closure and its strictly increasing resolution ladder."""

  case_id: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolutions: tuple[tuple[int, int], ...]
  reference_total_temperature_K: float
  ambient_pressure_Pa: float
  equation_options: Mapping[str, Any] | None = None
  moving_interface_options: Mapping[str, Any] | None = None
  state_resolve_options: Mapping[str, Any] | None = None
  state_boundary_condition_options: Mapping[str, Any] | None = None
  downstream_options: Mapping[str, Any] | None = None
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
      raise TypeError('closure must be a typed global physical closure')
    ####
    resolutions = tuple(_resolution(value, 'resolution') for value in self.resolutions)
    if not _increasing(resolutions):
      raise ValueError(
        'resolutions must contain at least two strictly increasing pairs'
      )
    ####
    temperature = float(self.reference_total_temperature_K)
    ambient = float(self.ambient_pressure_Pa)
    if not isfinite(temperature) or temperature <= 0.0:
      raise ValueError('reference_total_temperature_K must be finite and positive')
    ####
    if not isfinite(ambient) or ambient <= 0.0:
      raise ValueError('ambient_pressure_Pa must be finite and positive')
    ####
    for value, name in (
      (self.equation_options, 'equation_options'),
      (self.moving_interface_options, 'moving_interface_options'),
      (self.state_resolve_options, 'state_resolve_options'),
      (self.state_boundary_condition_options, 'state_boundary_condition_options'),
      (self.downstream_options, 'downstream_options'),
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
      'equation_options',
      'moving_interface_options',
      'state_resolve_options',
      'state_boundary_condition_options',
      'downstream_options',
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
    return moc_reflected_domain_global_physical_closure_fingerprint(self.closure)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolutions': self.resolutions,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'resolution_ladder_verified': _increasing(self.resolutions),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep:
  """One fresh downstream solve and moving upstream correction."""

  case_id: str
  resolution: tuple[int, int]
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult
  result: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    resolution = _resolution(self.resolution, 'resolution')
    if not isinstance(self.closure, MocReflectedDomainGlobalPhysicalClosureResult):
      raise TypeError('closure must be a typed global physical closure')
    ####
    if not isinstance(
      self.downstream,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError('downstream must be a typed coupled-downstream result')
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorResult,
    ):
      raise TypeError('result must be a typed moving upstream corrector result')
    ####
    if self.downstream.closure is not self.closure:
      raise ValueError('downstream must retain the exact source closure')
    ####
    if self.result.source_closure is not self.closure:
      raise ValueError('result must retain the exact source closure')
    ####
    if self.result.source_downstream is not self.downstream:
      raise ValueError('result must retain the exact source downstream result')
    ####
    request = self.downstream.coupled_request
    if request is not None and (
      request.axial_cell_count != resolution[0]
      or request.transverse_cell_count != resolution[1]
    ):
      raise ValueError('downstream request must retain the declared resolution')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'resolution', resolution)
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(self.closure)
  ####

  @property
  def equation_consumption_verified(self) -> bool:
    return bool(
      self.result.initial_equation_consumption_verified
      and self.result.initial_equation_replay_verified
      and self.result.final_equation_consumption_verified
      and self.result.final_equation_replay_verified
      and self.result.upstream_state_equation_consumed
    )
  ####

  @property
  def moving_corrector_verified(self) -> bool:
    return self.result.moving_global_corrector_verified
  ####

  @property
  def residual_metrics_finite(self) -> bool:
    vectors = (
      self.result.initial_upstream_residual_vector,
      self.result.final_upstream_residual_vector,
      self.result.initial_downstream_residual_vector,
      self.result.final_downstream_residual_vector,
      self.result.initial_combined_residual_vector,
      self.result.final_combined_residual_vector,
    )
    return bool(
      len(vectors[0]) == len(vectors[1]) == 7
      and len(vectors[2]) == len(vectors[3]) == 10
      and len(vectors[4]) == len(vectors[5]) == 17
      and all(isfinite(value) and value >= 0.0 for vector in vectors for value in vector)
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      self.result.global_coupling_verified is False
      and self.result.canonical_free_boundary_verified is False
      and self.result.chain_promotion_blocked
      and self.result.production_claim_allowed is False
      and self.result.initial_equation is not None
      and self.result.initial_equation.global_coupling_verified is False
      and self.result.initial_equation.canonical_free_boundary_verified is False
      and self.result.final_equation is not None
      and self.result.final_equation.global_coupling_verified is False
      and self.result.final_equation.canonical_free_boundary_verified is False
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.result.source_lineage_verified
      and self.result.final_lineage_verified
      and self.equation_consumption_verified
      and self.moving_corrector_verified
      and self.residual_metrics_finite
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolution': self.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'equation_consumption_verified': self.equation_consumption_verified,
      'moving_corrector_verified': self.moving_corrector_verified,
      'residual_metrics_finite': self.residual_metrics_finite,
      'componentwise_residual_descent_verified': (
        self.result.combined_componentwise_residual_descent_verified
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'locally_verified': self.locally_verified,
      'downstream': self.downstream.as_report(),
      'result': self.result.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementMeasurement:
  """Cross-case coverage evidence below canonical closure."""

  status: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep,
    ...,
  ] = ()
  case_ids: tuple[str, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  componentwise_residual_descent: tuple[bool, ...] = ()
  case_ids_verified: bool = False
  source_closure_bindings_verified: bool = False
  distinct_source_closures_verified: bool = False
  resolution_ladders_verified: bool = False
  local_coverage_verified: bool = False
  cross_case_coverage_verified: bool = False
  equation_consumption_verified: bool = False
  moving_corrector_verified: bool = False
  residual_metrics_finite: bool = False
  componentwise_residual_admission_verified: bool = False
  fidelity_isolation_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus,
    ):
      raise TypeError('status must be a typed moving upstream refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed moving upstream refinement steps')
    ####
    summaries = (
      tuple(str(value) for value in self.case_ids),
      tuple(_resolution(value, 'resolution') for value in self.resolutions),
      tuple(str(value) for value in self.source_closure_fingerprints),
      tuple(bool(value) for value in self.componentwise_residual_descent),
    )
    if any(len(value) != len(steps) for value in summaries):
      raise ValueError('refinement summaries must match the step count')
    ####
    for name in (
      'case_ids_verified',
      'source_closure_bindings_verified',
      'distinct_source_closures_verified',
      'resolution_ladders_verified',
      'local_coverage_verified',
      'cross_case_coverage_verified',
      'equation_consumption_verified',
      'moving_corrector_verified',
      'residual_metrics_finite',
      'componentwise_residual_admission_verified',
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
      raise ValueError('moving upstream refinement cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('moving upstream refinement must remain promotion-blocked')
    ####
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'case_ids', summaries[0])
    object.__setattr__(self, 'resolutions', summaries[1])
    object.__setattr__(self, 'source_closure_fingerprints', summaries[2])
    object.__setattr__(self, 'componentwise_residual_descent', summaries[3])
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in (
        MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      )
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_MOVING_UPSTREAM_STATE_EQUATION_CORRECTOR_REFINEMENT_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'resolutions': self.resolutions,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'componentwise_residual_descent': self.componentwise_residual_descent,
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'source_closure_bindings_verified': self.source_closure_bindings_verified,
        'distinct_source_closures_verified': self.distinct_source_closures_verified,
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'local_coverage_verified': self.local_coverage_verified,
        'cross_case_coverage_verified': self.cross_case_coverage_verified,
        'equation_consumption_verified': self.equation_consumption_verified,
        'moving_corrector_verified': self.moving_corrector_verified,
        'residual_metrics_finite': self.residual_metrics_finite,
        'componentwise_residual_admission_verified': self.componentwise_residual_admission_verified,
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
        'research-only disjoint-case and increasing-resolution coverage for the '
        'moving upstream state/entropy corrector; residual admission, canonical '
        'global closure, physical validation, and production remain open'
      ),
    }
  ####
####


def _summary(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep,
  ],
) -> dict[str, tuple[Any, ...]]:
  return {
    'case_ids': tuple(step.case_id for step in steps),
    'resolutions': tuple(step.resolution for step in steps),
    'source_closure_fingerprints': tuple(
      step.source_closure_fingerprint for step in steps
    ),
    'componentwise_residual_descent': tuple(
      step.result.combined_componentwise_residual_descent_verified
      for step in steps
    ),
  }
####


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus,
  message: str,
  *,
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep,
  ] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementMeasurement(
    status=status,
    steps=retained,
    **_summary(retained),
    **flags,
    message=message,
  )
####


def measure_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector_refinement(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep,
  ],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementMeasurement:
  """Audit exact moving-corrector coverage by case and resolution."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus
  )
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'steps must be iterable')
  ####
  if len(retained) < 2:
    return _measurement(status_type.INVALID_INPUT, 'at least two refinement steps are required')
  ####
  if any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep,
    )
    for step in retained
  ):
    return _measurement(status_type.INVALID_INPUT, 'steps must contain typed refinement steps')
  ####
  grouped: dict[str, list[int]] = {}
  for index, step in enumerate(retained):
    grouped.setdefault(step.case_id, []).append(index)
  ####
  actual_case_ids = tuple(grouped)
  expected = None if expected_case_ids is None else tuple(str(value) for value in expected_case_ids)
  case_ids_verified = bool(
    actual_case_ids
    and len(actual_case_ids) == len(set(actual_case_ids))
    and (expected is None or actual_case_ids == expected)
  )
  source_bindings = all(
    step.result.source_lineage_verified and step.result.final_lineage_verified
    for step in retained
  )
  distinct_sources = bool(
    len(grouped) >= 2
    and len({retained[indices[0]].source_closure_fingerprint for indices in grouped.values()})
    == len(grouped)
  )
  ladders = bool(
    all(
      len(indices) >= 2
      and _increasing(tuple(retained[index].resolution for index in indices))
      for indices in grouped.values()
    )
  )
  equations = all(step.equation_consumption_verified for step in retained)
  moving = all(step.moving_corrector_verified for step in retained)
  metrics = all(step.residual_metrics_finite for step in retained)
  fidelity = all(step.fidelity_isolation_verified for step in retained)
  local = bool(
    case_ids_verified
    and source_bindings
    and ladders
    and equations
    and moving
    and metrics
    and fidelity
  )
  cross_case = bool(local and distinct_sources)
  componentwise = bool(
    retained
    and all(step.result.combined_componentwise_residual_descent_verified for step in retained)
  )
  if not case_ids_verified:
    status = status_type.CASE_ID_FAILURE
    message = 'case IDs are missing or unexpected'
  elif not ladders:
    status = status_type.RESOLUTION_FAILURE
    message = 'every case must retain at least two strictly increasing resolutions'
  elif not source_bindings:
    status = status_type.LINEAGE_FAILURE
    message = 'one or more steps lost exact source or final closure lineage'
  elif not equations:
    status = status_type.EQUATION_FAILURE
    message = 'one or more steps lost exact state/entropy equation consumption or replay'
  elif not moving:
    status = status_type.MOVING_FAILURE
    message = 'one or more steps lost strict moving/global corrector evidence'
  elif not metrics:
    status = status_type.METRIC_FAILURE
    message = 'one or more combined residual vectors are not finite and aligned'
  elif not fidelity:
    status = status_type.FIDELITY_FAILURE
    message = 'one or more steps weakened the research-only promotion block'
  elif cross_case:
    status = status_type.CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    message = (
      'fresh moving upstream state/entropy correction and independent replay '
      'passed across distinct source closures and increasing resolutions; '
      'component-wise residual admission remains a separate gate'
    )
  else:
    status = status_type.CONVERGED_LOCAL_RESEARCH_COVERAGE
    message = (
      'fresh moving upstream state/entropy correction and independent replay '
      'passed across increasing resolutions; no canonical coupling is inferred'
    )
  ####
  return _measurement(
    status,
    message,
    steps=retained,
    case_ids_verified=case_ids_verified,
    source_closure_bindings_verified=source_bindings,
    distinct_source_closures_verified=distinct_sources,
    resolution_ladders_verified=ladders,
    local_coverage_verified=local,
    cross_case_coverage_verified=cross_case,
    equation_consumption_verified=equations,
    moving_corrector_verified=moving,
    residual_metrics_finite=metrics,
    componentwise_residual_admission_verified=componentwise,
    fidelity_isolation_verified=fidelity,
  )
####


def _downstream_options(
  case: MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementCase,
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
      raise ValueError(f'downstream_options.{name} must match resolution')
    ####
    options[name] = value
  ####
  options.setdefault('max_pseudo_iterations', max_pseudo_iterations)
  options.setdefault('max_shape_iterations', max_shape_iterations)
  return options
####


def run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementCase,
  ],
  *,
  max_pseudo_iterations: int = 400,
  max_shape_iterations: int = 12,
  max_equation_pseudo_iterations: int = 80,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementMeasurement:
  """Freshly run the moving upstream corrector for each case/resolution pair."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStatus
  )
  for value, name in (
    (max_pseudo_iterations, 'max_pseudo_iterations'),
    (max_shape_iterations, 'max_shape_iterations'),
    (max_equation_pseudo_iterations, 'max_equation_pseudo_iterations'),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      return _measurement(status_type.INVALID_INPUT, f'{name} must be a positive integer')
    ####
  ####
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'cases must be iterable')
  ####
  if not retained_cases:
    return _measurement(status_type.INVALID_INPUT, 'cases must not be empty')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(status_type.INVALID_INPUT, 'cases must contain typed refinement cases')
  ####
  case_ids = tuple(case.case_id for case in retained_cases)
  if len(case_ids) != len(set(case_ids)):
    return _measurement(status_type.CASE_ID_FAILURE, 'case IDs must be unique')
  ####
  retained_steps: list[
    MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep
  ] = []
  for case in retained_cases:
    for resolution in case.resolutions:
      try:
        downstream = solve_reflected_domain_global_coupled_downstream(
          case.closure,
          reference_total_temperature_K=case.reference_total_temperature_K,
          ambient_pressure_Pa=case.ambient_pressure_Pa,
          **_downstream_options(
            case,
            resolution,
            max_pseudo_iterations=max_pseudo_iterations,
            max_shape_iterations=max_shape_iterations,
          ),
        )
        result = run_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector(
          case.closure,
          downstream,
          reference_total_temperature_K=case.reference_total_temperature_K,
          equation_options=case.equation_options,
          moving_interface_options=case.moving_interface_options,
          state_resolve_options=case.state_resolve_options,
          state_boundary_condition_options=case.state_boundary_condition_options,
          downstream_options=_downstream_options(
            case,
            resolution,
            max_pseudo_iterations=max_pseudo_iterations,
            max_shape_iterations=max_shape_iterations,
          ),
          geometry_response_options=case.geometry_response_options,
          max_equation_pseudo_iterations=max_equation_pseudo_iterations,
          consumer_id=f'{case.case_id}:resolution-{resolution[0]}x{resolution[1]}',
          require_componentwise_residual_descent=False,
        )
        retained_steps.append(
          MocReflectedDomainGlobalMixedRegimeMovingUpstreamStateEquationCorrectorRefinementStep(
            case_id=case.case_id,
            resolution=resolution,
            closure=case.closure,
            downstream=downstream,
            result=result,
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return _measurement(
          status_type.CASE_FAILURE,
          f'case {case.case_id} resolution {resolution} failed: {error}',
          steps=retained_steps,
        )
      ####
    ####
  ####
  return measure_reflected_domain_global_mixed_regime_moving_upstream_state_equation_corrector_refinement(
    retained_steps,
    expected_case_ids=expected_case_ids,
  )
####
