"""Cross-case and resolution coverage for the upstream state equation.

The P3.33 interface-strip equation is a local research seam.  This module
executes it on fresh downstream traces from explicitly named source closures
and increasing mesh resolutions, then independently replays every retained
equation report.  Coverage is evidence that the same contract is exercised;
it is not a canonical global/free-boundary convergence claim.
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
from exhaust_plume.models.moc.global_mixed_regime_state_consumer import (
  MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  consume_reflected_domain_global_mixed_regime_state,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_state_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus,
  audit_reflected_domain_global_mixed_regime_upstream_state_equation,
  solve_reflected_domain_global_mixed_regime_upstream_state_equation,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementMeasurement',
  'measure_reflected_domain_global_mixed_regime_upstream_state_equation_refinement',
  'run_reflected_domain_global_mixed_regime_upstream_state_equation_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-state-equation-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the upstream state-equation coverage audit."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-upstream-state-equation-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-upstream-state-equation-coverage'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_ID_FAILURE = 'upstream-state-equation-refinement-case-id-failure'
  CASE_FAILURE = 'upstream-state-equation-refinement-case-failure'
  RESOLUTION_FAILURE = 'upstream-state-equation-refinement-resolution-failure'
  LINEAGE_FAILURE = 'upstream-state-equation-refinement-lineage-failure'
  DOWNSTREAM_FAILURE = 'upstream-state-equation-refinement-downstream-failure'
  TARGET_FAILURE = 'upstream-state-equation-refinement-target-failure'
  EQUATION_FAILURE = 'upstream-state-equation-refinement-equation-failure'
  AUDIT_FAILURE = 'upstream-state-equation-refinement-audit-failure'
  METRIC_FAILURE = 'upstream-state-equation-refinement-metric-failure'
  FIDELITY_FAILURE = 'upstream-state-equation-refinement-fidelity-failure'
####


def _resolution(value: object, name: str) -> tuple[int, int]:
  try:
    pair = tuple(value)  # type: ignore[arg-type]
  except TypeError as error:
    raise ValueError(f'{name} must contain an axial/transverse pair') from error
  ####
  if (
    len(pair) != 2
    or any(isinstance(item, bool) or not isinstance(item, int) for item in pair)
    or pair[0] < 8
    or pair[1] < 4
  ):
    raise ValueError(
      f'{name} must contain integer counts with axial >= 8 and transverse >= 4'
    )
  ####
  return int(pair[0]), int(pair[1])
####


def _increasing(resolutions: Sequence[tuple[int, int]]) -> bool:
  return bool(
    len(resolutions) >= 2
    and all(
      right[0] > left[0] and right[1] > left[1]
      for left, right in zip(resolutions, resolutions[1:])
    )
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


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementCase:
  """One source closure and its increasing downstream resolution ladder."""

  case_id: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolutions: tuple[tuple[int, int], ...]
  reference_total_temperature_K: float
  ambient_pressure_Pa: float | None = None
  downstream_options: Mapping[str, Any] | None = None
  equation_options: Mapping[str, Any] | None = None

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
      resolutions = tuple(
        _resolution(value, 'resolution') for value in self.resolutions
      )
    except TypeError as error:
      raise ValueError(
        'resolutions must contain axial/transverse integer pairs'
      ) from error
    ####
    if len(resolutions) < 2 or not _increasing(resolutions):
      raise ValueError(
        'resolutions must contain at least two strictly increasing pairs'
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
    _options(self.downstream_options, 'downstream_options')
    _options(self.equation_options, 'equation_options')
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'resolutions', resolutions)
    object.__setattr__(self, 'reference_total_temperature_K', temperature)
    object.__setattr__(self, 'ambient_pressure_Pa', ambient)
    if self.downstream_options is not None:
      object.__setattr__(
        self,
        'downstream_options',
        dict(self.downstream_options),
      )
    ####
    if self.equation_options is not None:
      object.__setattr__(
        self,
        'equation_options',
        dict(self.equation_options),
      )
    ####
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolutions': self.resolutions,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'resolution_ladder_verified': _increasing(self.resolutions),
      'closure_status': self.closure.status.value,
      'closure_converged': self.closure.converged,
      'physical_closure_verified': self.closure.physical_closure_verified,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep:
  """One fresh downstream trace, equation solve, and replay audit."""

  case_id: str
  resolution: tuple[int, int]
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult
  equation: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult
  audit: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit

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
      raise TypeError('closure must be a typed global physical closure')
    ####
    if not isinstance(
      self.downstream,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError('downstream must be a typed coupled-downstream result')
    ####
    if not isinstance(
      self.consumer,
      MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
    ):
      raise TypeError('consumer must be a typed mixed-regime state consumer')
    ####
    if not isinstance(
      self.equation,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
    ):
      raise TypeError('equation must be a typed upstream state-equation result')
    ####
    if not isinstance(
      self.audit,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
    ):
      raise TypeError('audit must be a typed upstream state-equation audit')
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
    if self.equation.request is None or self.equation.request.closure is not self.closure:
      raise ValueError('equation must retain the exact source closure request')
    ####
    if self.audit.result is not self.equation:
      raise ValueError('audit must retain the exact equation result')
    ####
    if self.downstream.coupled_request is not None:
      request = self.downstream.coupled_request
      if (
        request.axial_cell_count != resolution[0]
        or request.transverse_cell_count != resolution[1]
      ):
        raise ValueError('downstream request must retain the declared resolution')
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
  def target_frame_verified(self) -> bool:
    trace = self.consumer.trace
    return bool(
      trace is not None
      and trace.local_trace_verified
      and self.equation.target_frame_verified
    )
  ####

  @property
  def equation_consumption_verified(self) -> bool:
    return bool(
      self.equation.research_state_equation_consumed
      and self.equation.target_conservative_state_consumed
      and self.equation.entropy_target_consumed
      and self.equation.entropy_flux_verified
      and self.equation.source_field_lineage_verified
    )
  ####

  @property
  def independent_audit_verified(self) -> bool:
    return bool(
      self.audit.converged
      and self.audit.result is self.equation
      and self.audit.target_boundary_replayed
      and self.audit.source_boundary_replayed
      and self.audit.entropy_target_replayed
      and self.audit.residual_report_verified
    )
  ####

  @property
  def residual_metrics_finite(self) -> bool:
    return bool(
      self.equation.maximum_conservative_euler_residual is not None
      and isfinite(float(self.equation.maximum_conservative_euler_residual))
      and self.equation.maximum_conservative_euler_residual >= 0.0
      and self.equation.maximum_target_boundary_entropy_log_residual is not None
      and isfinite(
        float(self.equation.maximum_target_boundary_entropy_log_residual)
      )
      and self.equation.maximum_target_boundary_entropy_log_residual >= 0.0
      and self.equation.maximum_entropy_flux_defect is not None
      and isfinite(float(self.equation.maximum_entropy_flux_defect))
      and self.equation.maximum_entropy_flux_defect >= 0.0
      and all(
        isfinite(value) and value >= 0.0
        for row in self.equation.residual_channels_by_cell
        for value in row
      )
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      self.downstream.chain_promotion_blocked
      and not self.downstream.production_claim_allowed
      and not self.downstream.global_coupling_verified
      and self.consumer.chain_promotion_blocked
      and not self.consumer.production_claim_allowed
      and not self.consumer.global_coupling_verified
      and self.equation.chain_promotion_blocked
      and not self.equation.production_claim_allowed
      and not self.equation.canonical_free_boundary_verified
      and not self.equation.global_coupling_verified
      and self.audit.chain_promotion_blocked
      and not self.audit.production_claim_allowed
      and not self.audit.canonical_free_boundary_verified
      and not self.audit.global_coupling_verified
    )
  ####

  @property
  def source_lineage_verified(self) -> bool:
    return bool(
      self.downstream.closure_lineage_verified
      and self.consumer.closure_lineage_verified
      and self.consumer.source_closure_fingerprint
      == self.source_closure_fingerprint
      and self.equation.request is not None
      and self.equation.request.closure is self.closure
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.equation.status
      in (
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
        .CONVERGED_LOCAL_RESEARCH_UPSTREAM_STATE_EQUATION,
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationStatus
        .COMPLETED_RESEARCH_UPSTREAM_STATE_EQUATION_WITH_OPEN_RESIDUAL,
      )
      and self.fresh_downstream_verified
      and self.source_lineage_verified
      and self.consumer.consumed_local_research_state
      and self.target_frame_verified
      and self.equation_consumption_verified
      and self.independent_audit_verified
      and self.residual_metrics_finite
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'resolution': self.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'fresh_downstream_verified': self.fresh_downstream_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'target_frame_verified': self.target_frame_verified,
      'equation_consumption_verified': self.equation_consumption_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'residual_metrics_finite': self.residual_metrics_finite,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'locally_verified': self.locally_verified,
      'maximum_conservative_euler_residual': (
        self.equation.maximum_conservative_euler_residual
      ),
      'maximum_target_boundary_entropy_log_residual': (
        self.equation.maximum_target_boundary_entropy_log_residual
      ),
      'maximum_entropy_flux_defect': self.equation.maximum_entropy_flux_defect,
      'downstream_status': self.downstream.status.value,
      'consumer_status': self.consumer.status.value,
      'equation_status': self.equation.status.value,
      'audit_status': self.audit.status.value,
      'equation': self.equation.as_report(),
      'audit': self.audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementMeasurement:
  """Coverage evidence below the canonical and production claim ceilings."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
  steps: tuple[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep,
    ...,
  ] = ()
  case_ids: tuple[str, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  equation_statuses: tuple[str, ...] = ()
  audit_statuses: tuple[str, ...] = ()
  maximum_conservative_euler_residuals: tuple[float | None, ...] = ()
  maximum_target_boundary_entropy_log_residuals: tuple[float | None, ...] = ()
  maximum_entropy_flux_defects: tuple[float | None, ...] = ()
  case_ids_verified: bool = False
  source_closure_bindings_verified: bool = False
  distinct_source_closures_verified: bool = False
  resolution_ladders_verified: bool = False
  fresh_downstream_verified: bool = False
  target_frames_verified: bool = False
  equation_consumption_verified: bool = False
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
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus,
    ):
      raise TypeError('status must be a typed upstream refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed upstream refinement steps')
    ####
    fields = {
      'case_ids': tuple(str(value) for value in self.case_ids),
      'resolutions': tuple(
        _resolution(value, 'resolution') for value in self.resolutions
      ),
      'source_closure_fingerprints': tuple(
        str(value) for value in self.source_closure_fingerprints
      ),
      'equation_statuses': tuple(str(value) for value in self.equation_statuses),
      'audit_statuses': tuple(str(value) for value in self.audit_statuses),
      'maximum_conservative_euler_residuals': tuple(
        self.maximum_conservative_euler_residuals
      ),
      'maximum_target_boundary_entropy_log_residuals': tuple(
        self.maximum_target_boundary_entropy_log_residuals
      ),
      'maximum_entropy_flux_defects': tuple(self.maximum_entropy_flux_defects),
    }
    if any(len(value) != len(steps) for value in fields.values()):
      raise ValueError('refinement summaries must match the step count')
    ####
    for name in (
      'maximum_conservative_euler_residuals',
      'maximum_target_boundary_entropy_log_residuals',
      'maximum_entropy_flux_defects',
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
      'target_frames_verified',
      'equation_consumption_verified',
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
      raise ValueError('upstream refinement cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('upstream refinement must remain promotion-blocked')
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
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      )
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
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
      'equation_statuses': self.equation_statuses,
      'audit_statuses': self.audit_statuses,
      'maximum_conservative_euler_residuals': (
        self.maximum_conservative_euler_residuals
      ),
      'maximum_target_boundary_entropy_log_residuals': (
        self.maximum_target_boundary_entropy_log_residuals
      ),
      'maximum_entropy_flux_defects': self.maximum_entropy_flux_defects,
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
        'target_frames_verified': self.target_frames_verified,
        'equation_consumption_verified': self.equation_consumption_verified,
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
        'research-only cross-case and increasing-resolution coverage for the '
        'upstream state/entropy interface equation; no canonical or '
        'production claim is inferred'
      ),
    }
  ####
####


def _summary(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep
  ],
) -> dict[str, tuple[Any, ...]]:
  return {
    'case_ids': tuple(step.case_id for step in steps),
    'resolutions': tuple(step.resolution for step in steps),
    'source_closure_fingerprints': tuple(
      step.source_closure_fingerprint for step in steps
    ),
    'equation_statuses': tuple(step.equation.status.value for step in steps),
    'audit_statuses': tuple(step.audit.status.value for step in steps),
    'maximum_conservative_euler_residuals': tuple(
      step.equation.maximum_conservative_euler_residual for step in steps
    ),
    'maximum_target_boundary_entropy_log_residuals': tuple(
      step.equation.maximum_target_boundary_entropy_log_residual
      for step in steps
    ),
    'maximum_entropy_flux_defects': tuple(
      step.equation.maximum_entropy_flux_defect for step in steps
    ),
  }
####


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus,
  message: str,
  *,
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep
  ] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementMeasurement(
    status=status,
    steps=retained,
    **_summary(retained),
    **flags,
    message=message,
  )
####


def _group_indices(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep
  ],
) -> dict[str, list[int]]:
  grouped: dict[str, list[int]] = {}
  for index, step in enumerate(steps):
    grouped.setdefault(step.case_id, []).append(index)
  ####
  return grouped
####


def measure_reflected_domain_global_mixed_regime_upstream_state_equation_refinement(
  steps: Sequence[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep
  ],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementMeasurement:
  """Audit fresh state-equation coverage by source case and resolution."""

  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .INVALID_INPUT,
      'steps must be iterable',
    )
  ####
  if len(retained) < 2:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .INVALID_INPUT,
      'upstream state-equation refinement requires at least two steps',
    )
  ####
  if any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .INVALID_INPUT,
      'steps must contain typed upstream refinement steps',
    )
  ####
  grouped = _group_indices(retained)
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
  source_bindings = all(step.source_lineage_verified for step in retained)
  distinct_sources = bool(
    len(grouped) >= 2
    and len({retained[indices[0]].source_closure_fingerprint for indices in grouped.values()})
    == len(grouped)
  )
  resolution_ladders = bool(
    all(
      len(indices) >= 2
      and _increasing(tuple(retained[index].resolution for index in indices))
      for indices in grouped.values()
    )
  )
  downstream = all(step.fresh_downstream_verified for step in retained)
  targets = all(step.target_frame_verified for step in retained)
  equations = all(step.equation_consumption_verified for step in retained)
  audits = all(step.independent_audit_verified for step in retained)
  metrics = all(step.residual_metrics_finite for step in retained)
  fidelity = all(step.fidelity_isolation_verified for step in retained)
  local = bool(
    case_ids_verified
    and source_bindings
    and resolution_ladders
    and downstream
    and targets
    and equations
    and audits
    and metrics
    and fidelity
  )
  cross_case = bool(local and distinct_sources)
  status_type = (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
  )
  if not case_ids_verified:
    status = status_type.CASE_ID_FAILURE
    message = 'upstream refinement case IDs are missing or unexpected'
  elif not resolution_ladders:
    status = status_type.RESOLUTION_FAILURE
    message = 'every named case must retain at least two increasing resolutions'
  elif not source_bindings:
    status = status_type.LINEAGE_FAILURE
    message = 'one or more steps lost exact closure lineage'
  elif not downstream:
    status = status_type.DOWNSTREAM_FAILURE
    message = 'one or more fresh downstream traces failed local coverage'
  elif not targets:
    status = status_type.TARGET_FAILURE
    message = 'one or more equations lost the exact downstream target frame'
  elif not equations:
    status = status_type.EQUATION_FAILURE
    message = 'one or more state/entropy equations did not prove consumption'
  elif not audits:
    status = status_type.AUDIT_FAILURE
    message = 'one or more independent equation replays failed'
  elif not metrics:
    status = status_type.METRIC_FAILURE
    message = 'one or more state-equation residual metrics were non-finite'
  elif not fidelity:
    status = status_type.FIDELITY_FAILURE
    message = 'one or more steps weakened the research-only promotion block'
  elif cross_case:
    status = status_type.CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    message = (
      'fresh state/entropy equation consumption and independent replay passed '
      'across distinct source closures and increasing resolutions; local '
      'residual closure and canonical global coupling remain open'
    )
  else:
    status = status_type.CONVERGED_LOCAL_RESEARCH_COVERAGE
    message = (
      'fresh state/entropy equation consumption and independent replay passed '
      'across increasing resolutions; no canonical coupling is inferred'
    )
  ####
  return _measurement(
    status,
    message,
    steps=retained,
    case_ids_verified=case_ids_verified,
    source_closure_bindings_verified=source_bindings,
    distinct_source_closures_verified=distinct_sources,
    resolution_ladders_verified=resolution_ladders,
    fresh_downstream_verified=downstream,
    target_frames_verified=targets,
    equation_consumption_verified=equations,
    independent_audits_verified=audits,
    residual_metrics_finite=metrics,
    local_coverage_verified=local,
    cross_case_coverage_verified=cross_case,
    fidelity_isolation_verified=fidelity,
  )
####


def _downstream_options(
  case: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementCase,
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


def _equation_request(
  case: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementCase,
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  *,
  max_pseudo_iterations: int,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest:
  trace = consumer.trace
  if trace is None or not trace.samples:
    raise ValueError('state consumer did not retain an exact downstream trace')
  ####
  if not consumer.consumed_local_research_state:
    raise ValueError('state consumer did not pass its local channel gates')
  ####
  gamma = float(trace.samples[0].gamma)
  if any(abs(float(sample.gamma) - gamma) > 1.0e-12 for sample in trace.samples):
    raise ValueError('downstream trace gamma must be constant across vertices')
  ####
  options = _options(case.equation_options, 'equation_options')
  reserved = (
    'closure',
    'target_points_m',
    'target_conservative_state_profile',
    'target_entropy_proxy_profile',
    'target_gamma',
    'reference_total_temperature_K',
  )
  collisions = tuple(key for key in reserved if key in options)
  if collisions:
    raise ValueError(
      'equation_options cannot override the exact target frame: '
      + ', '.join(collisions)
    )
  ####
  options.setdefault('max_pseudo_iterations', max_pseudo_iterations)
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest(
    closure=case.closure,
    target_points_m=tuple(sample.point_m for sample in trace.samples),
    target_conservative_state_profile=tuple(
      sample.conservative_state for sample in trace.samples
    ),
    target_entropy_proxy_profile=tuple(
      sample.entropy_proxy for sample in trace.samples
    ),
    target_gamma=gamma,
    reference_total_temperature_K=case.reference_total_temperature_K,
    **options,
  )
####


def run_reflected_domain_global_mixed_regime_upstream_state_equation_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementCase
  ],
  *,
  max_pseudo_iterations: int = 400,
  max_shape_iterations: int = 12,
  equation_max_pseudo_iterations: int = 80,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementMeasurement:
  """Freshly execute every declared closure/resolution pair."""

  for value, name in (
    (max_pseudo_iterations, 'max_pseudo_iterations'),
    (max_shape_iterations, 'max_shape_iterations'),
    (equation_max_pseudo_iterations, 'equation_max_pseudo_iterations'),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      return _measurement(
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
        .INVALID_INPUT,
        f'{name} must be a positive integer',
      )
    ####
  ####
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .INVALID_INPUT,
      'cases must be iterable',
    )
  ####
  if not retained_cases:
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .INVALID_INPUT,
      'cases must not be empty',
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .INVALID_INPUT,
      'cases must contain typed upstream refinement cases',
    )
  ####
  case_ids = tuple(case.case_id for case in retained_cases)
  if len(set(case_ids)) != len(case_ids):
    return _measurement(
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
      .CASE_ID_FAILURE,
      'upstream refinement case IDs must be unique',
    )
  ####
  retained_steps: list[
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep
  ] = []
  status_type = (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStatus
  )
  for case in retained_cases:
    ambient = case.ambient_pressure_Pa
    if ambient is None or not isfinite(float(ambient)) or float(ambient) <= 0.0:
      return _measurement(
        status_type.INVALID_INPUT,
        f'case {case.case_id} has no explicit positive ambient pressure',
        steps=retained_steps,
      )
    ####
    for resolution in case.resolutions:
      try:
        downstream = solve_reflected_domain_global_coupled_downstream(
          case.closure,
          reference_total_temperature_K=case.reference_total_temperature_K,
          ambient_pressure_Pa=float(ambient),
          **_downstream_options(
            case,
            resolution,
            max_pseudo_iterations=max_pseudo_iterations,
            max_shape_iterations=max_shape_iterations,
          ),
        )
        consumer = consume_reflected_domain_global_mixed_regime_state(
          case.closure,
          downstream,
        )
        request = _equation_request(
          case,
          consumer,
          max_pseudo_iterations=equation_max_pseudo_iterations,
        )
        equation = solve_reflected_domain_global_mixed_regime_upstream_state_equation(
          request
        )
        audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
          equation
        )
        retained_steps.append(
          MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRefinementStep(
            case_id=case.case_id,
            resolution=resolution,
            closure=case.closure,
            downstream=downstream,
            consumer=consumer,
            equation=equation,
            audit=audit,
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
  return measure_reflected_domain_global_mixed_regime_upstream_state_equation_refinement(
    retained_steps,
    expected_case_ids=expected_case_ids,
  )
####
