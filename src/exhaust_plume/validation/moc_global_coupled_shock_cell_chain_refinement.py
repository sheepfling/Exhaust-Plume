"""Refinement evidence for the retained global-coupled continued shock chain.

This lane executes the exact P2.2c/P3-bound continued-chain adapter for every
accepted first-cell resolution, then independently compares the resulting
physical-field observations.  It reports numerical sensitivity only.  It
does not turn a passing ladder into accepted physical lengths, canonical
reflected closure, external validation, or a production provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainContinuationPolicy,
)
from exhaust_plume.models.moc.physical_cell import MocPhysicalPostShockFieldResult
from exhaust_plume.models.moc.planner import MocGlobalEulerContinuedChainReference
from exhaust_plume.validation.moc_global_coupled_shock_cell_chain import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun,
  run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_chain,
)
from exhaust_plume.validation.moc_global_coupled_shock_cell_fit import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
)
from exhaust_plume.validation.moc_measurements import (
  MocShockCellChainRefinementCase,
  MocShockCellChainRefinementMeasurement,
  MocShockCellChainRefinementMeasurementStatus,
  MocShockCellObservation,
  measure_moc_shock_cell_chain_refinement,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementRun',
  'run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_chain_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-chain-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-chain-refinement-run'
)


class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus(
  str, Enum
):
  """Typed outcome for the continued-chain resolution ladder."""

  CONVERGED_RESEARCH_CONTINUED_CHAIN_REFINEMENT = (
    'converged-research-global-coupled-boundary-condition-feedback-continued-chain-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  FIRST_CELL_FIT_REQUIRED = (
    'global-coupled-boundary-condition-feedback-continued-chain-refinement-first-cell-fit-required'
  )
  CASE_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-refinement-case-failure'
  )
  RESOLUTION_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-refinement-resolution-failure'
  )
  MEASUREMENT_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-refinement-measurement-failure'
  )
  SENSITIVITY_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-refinement-sensitivity-failure'
  )
  FIDELITY_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-refinement-fidelity-failure'
  )
####


def _payload_fingerprint(payload: Any) -> str:
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _policy_report(policy: MocChainContinuationPolicy) -> dict[str, Any]:
  return {
    'max_cells': policy.max_cells,
    'max_axial_distance_m': policy.max_axial_distance_m,
    'position_tolerance_m': policy.position_tolerance_m,
    'allowed_fidelities': [
      getattr(fidelity, 'value', str(fidelity))
      for fidelity in policy.allowed_fidelities
    ],
    'require_state_carry': policy.require_state_carry,
    'state_tolerance': policy.state_tolerance,
  }
####


def _field_observation(
  field: MocPhysicalPostShockFieldResult,
  cell_index: int,
) -> MocShockCellObservation:
  outgoing_handoff = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  return MocShockCellObservation(
    cell_index=cell_index,
    shock_boundary_points_m=tuple(field.shock_boundary_points_m),
    centerline_boundary_points_m=tuple(field.centerline_boundary_points_m),
    cells=tuple(field.cells),
    upstream_total_pressure_Pa=tuple(
      field.upstream_shock_boundary_total_pressure_Pa
    ),
    downstream_total_pressure_Pa=tuple(
      field.post_shock_boundary_total_pressure_Pa
    ),
    incoming_handoff=field.incoming_handoff,
    outgoing_handoff=outgoing_handoff,
    incoming_boundary_kind=(
      MocChainBoundaryKind.CENTERLINE_TRACE
      if field.incoming_handoff else None
    ),
    outgoing_boundary_kind=MocChainBoundaryKind.CENTERLINE_TRACE,
    zero_strength_shock_start_allowed=field.zero_strength_shock_start_allowed,
    zero_strength_shock_endpoints_allowed=field.zero_strength_shock_endpoints_allowed,
  )
####


def _observations_for_run(
  run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun,
) -> tuple[MocShockCellObservation, ...] | None:
  if not run.physical_fields:
    return None
  ####
  try:
    return tuple(
      _field_observation(field, cell_index)
      for cell_index, field in enumerate(run.physical_fields, start=1)
    )
  except (IndexError, TypeError, ValueError):
    return None
  ####
####


def _configuration(
  *,
  first_cell_fit_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
  reference: MocGlobalEulerContinuedChainReference,
  policy: MocChainContinuationPolicy,
  start_x_m: float,
  requested_end_x_m: float | None,
  end_margin_m: float,
  length_tolerance_m: float,
  endpoint_tolerance_m: float,
  shock_spacing_tolerance_m: float,
  area_tolerance_m2: float,
) -> tuple[tuple[tuple[str, Any], ...], str]:
  payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_REFINEMENT_RUN_OPERATOR_ID
    ),
    'first_cell_fit_configuration_fingerprint': (
      first_cell_fit_run.configuration_fingerprint
    ),
    'reference': reference.as_report(),
    'policy': _policy_report(policy),
    'start_x_m': start_x_m,
    'requested_end_x_m': requested_end_x_m,
    'end_margin_m': end_margin_m,
    'length_tolerance_m': length_tolerance_m,
    'endpoint_tolerance_m': endpoint_tolerance_m,
    'shock_spacing_tolerance_m': shock_spacing_tolerance_m,
    'area_tolerance_m2': area_tolerance_m2,
    'model': 'exact-retained-p2.2c-case-wise-global-euler-chain-refinement',
  }
  configuration = tuple(
    (name, payload[name]) for name in sorted(payload)
  )
  return configuration, _payload_fingerprint(payload)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementRun:
  """Research-only continued-chain refinement over accepted P3 cases."""

  first_cell_fit_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun
  chain_runs: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun,
    ...,
  ]
  measurement: MocShockCellChainRefinementMeasurement | None
  reference: MocGlobalEulerContinuedChainReference
  policy: MocChainContinuationPolicy
  status: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
  )
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  start_x_m: float
  end_x_m: float | None
  length_tolerance_m: float
  case_lineage_verified: bool
  continued_field_fit_verified: bool
  fidelity_isolation_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.first_cell_fit_run,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
    ):
      raise TypeError('first_cell_fit_run must be a typed P3 first-cell run')
    ####
    chain_runs = tuple(self.chain_runs)
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun,
      )
      for run in chain_runs
    ):
      raise TypeError('chain_runs must contain typed continued-chain runs')
    ####
    if self.measurement is not None and not isinstance(
      self.measurement,
      MocShockCellChainRefinementMeasurement,
    ):
      raise TypeError(
        'measurement must be a MocShockCellChainRefinementMeasurement or None'
      )
    ####
    if not isinstance(self.reference, MocGlobalEulerContinuedChainReference):
      raise TypeError('reference must be a MocGlobalEulerContinuedChainReference')
    ####
    if not isinstance(self.policy, MocChainContinuationPolicy):
      raise TypeError('policy must be a MocChainContinuationPolicy')
    ####
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus,
    ):
      raise TypeError('status must be a typed chain-refinement status')
    ####
    start = float(self.start_x_m)
    if not isfinite(start):
      raise ValueError('start_x_m must be finite')
    ####
    end = None if self.end_x_m is None else float(self.end_x_m)
    if end is not None and (not isfinite(end) or end <= start):
      raise ValueError('end_x_m must be finite and greater than start_x_m')
    ####
    length_tolerance = float(self.length_tolerance_m)
    if not isfinite(length_tolerance) or length_tolerance <= 0.0:
      raise ValueError('length_tolerance_m must be finite and positive')
    ####
    for name in (
      'case_lineage_verified',
      'continued_field_fit_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if len(str(self.configuration_fingerprint)) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    object.__setattr__(self, 'chain_runs', chain_runs)
    object.__setattr__(self, 'start_x_m', start)
    object.__setattr__(self, 'end_x_m', end)
    object.__setattr__(self, 'length_tolerance_m', length_tolerance)
    object.__setattr__(self, 'configuration', tuple(self.configuration))
    object.__setattr__(self, 'configuration_fingerprint', str(self.configuration_fingerprint))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def resolved(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .CONVERGED_RESEARCH_CONTINUED_CHAIN_REFINEMENT
    )
  ####

  @property
  def continued_cell_count(self) -> int:
    counts = tuple(run.continued_cell_count for run in self.chain_runs)
    return counts[0] if counts and len(set(counts)) == 1 else 0
  ####

  @property
  def continued_lengths_m(self) -> tuple[tuple[float, ...], ...]:
    return tuple(run.continued_cell_lengths_m for run in self.chain_runs)
  ####

  @property
  def continued_length_deltas_m(self) -> tuple[tuple[float, ...], ...]:
    deltas: list[tuple[float, ...]] = []
    for previous, current in zip(
      self.continued_lengths_m,
      self.continued_lengths_m[1:],
    ):
      if len(previous) != len(current):
        deltas.append(())
        continue
      ####
      deltas.append(tuple(
        abs(right - left)
        for left, right in zip(previous, current, strict=True)
      ))
    ####
    return tuple(deltas)
  ####

  @property
  def maximum_continued_length_delta_m(self) -> float | None:
    deltas = tuple(
      delta
      for pair in self.continued_length_deltas_m
      for delta in pair
    )
    return None if not deltas else max(deltas)
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.resolved
      and self.first_cell_fit_run.converged
      and self.first_cell_fit_run.measurement.local_consistency_verified
      and len(self.chain_runs) >= 2
      and all(run.local_consistency_verified for run in self.chain_runs)
      and self.measurement is not None
      and self.measurement.converged
      and self.case_lineage_verified
      and self.continued_field_fit_verified
      and self.fidelity_isolation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    configuration = dict(self.configuration)
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_REFINEMENT_RUN_OPERATOR_ID
      ),
      'status': self.status.value,
      'resolved': self.resolved,
      'local_consistency_verified': self.local_consistency_verified,
      'configuration': configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'start_x_m': self.start_x_m,
      'end_x_m': self.end_x_m,
      'length_tolerance_m': self.length_tolerance_m,
      'refinement_tolerances': {
        name: configuration.get(name)
        for name in (
          'endpoint_tolerance_m',
          'shock_spacing_tolerance_m',
          'area_tolerance_m2',
        )
      },
      'reference': self.reference.as_report(),
      'policy': _policy_report(self.policy),
      'continued_cell_count': self.continued_cell_count,
      'continued_lengths_m': [list(lengths) for lengths in self.continued_lengths_m],
      'continued_length_deltas_m': [
        list(deltas) for deltas in self.continued_length_deltas_m
      ],
      'maximum_continued_length_delta_m': self.maximum_continued_length_delta_m,
      'checks': {
        'case_lineage_verified': self.case_lineage_verified,
        'continued_field_fit_verified': self.continued_field_fit_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'measurement': (
        None if self.measurement is None else self.measurement.as_report()
      ),
      'chain_runs': [run.as_report() for run in self.chain_runs],
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'physical_length_accepted': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'continued-chain-refinement; local-research-only; '
        'physical-length-not-accepted'
      ),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_chain_refinement(
  first_cell_fit_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
  *,
  start_x_m: float | None = None,
  end_x_m: float | None = None,
  end_margin_m: float = 8.0,
  reference: MocGlobalEulerContinuedChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
  length_tolerance_m: float = 2.0e-5,
  endpoint_tolerance_m: float = 2.5e-4,
  shock_spacing_tolerance_m: float = 1.0e-4,
  area_tolerance_m2: float = 2.0e-4,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementRun:
  """Run and independently compare one continued chain per accepted P3 case."""

  if not isinstance(
    first_cell_fit_run,
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
  ):
    raise TypeError('first_cell_fit_run must be a typed P3 first-cell run')
  ####
  resolved_reference = (
    MocGlobalEulerContinuedChainReference()
    if reference is None else reference
  )
  if not isinstance(
    resolved_reference,
    MocGlobalEulerContinuedChainReference,
  ):
    raise TypeError('reference must be a MocGlobalEulerContinuedChainReference')
  ####
  resolved_policy = (
    MocChainContinuationPolicy(
      max_cells=resolved_reference.total_cell_count + 1,
      require_state_carry=True,
    )
    if policy is None else policy
  )
  if not isinstance(resolved_policy, MocChainContinuationPolicy):
    raise TypeError('policy must be a MocChainContinuationPolicy or None')
  ####
  start = (
    first_cell_fit_run.start_x_m
    if start_x_m is None else float(start_x_m)
  )
  if not isfinite(start):
    raise ValueError('start_x_m must be finite')
  ####
  margin = float(end_margin_m)
  length_tolerance = float(length_tolerance_m)
  if not isfinite(margin) or margin <= 0.0:
    raise ValueError('end_margin_m must be finite and positive')
  ####
  if not isfinite(length_tolerance) or length_tolerance <= 0.0:
    raise ValueError('length_tolerance_m must be finite and positive')
  ####
  for name, value in (
    ('endpoint_tolerance_m', endpoint_tolerance_m),
    ('shock_spacing_tolerance_m', shock_spacing_tolerance_m),
    ('area_tolerance_m2', area_tolerance_m2),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  requested_end = None if end_x_m is None else float(end_x_m)
  if requested_end is not None and not isfinite(requested_end):
    raise ValueError('end_x_m must be finite when supplied')
  ####
  configuration, configuration_fingerprint = _configuration(
    first_cell_fit_run=first_cell_fit_run,
    reference=resolved_reference,
    policy=resolved_policy,
    start_x_m=start,
    requested_end_x_m=requested_end,
    end_margin_m=margin,
    length_tolerance_m=length_tolerance,
    endpoint_tolerance_m=float(endpoint_tolerance_m),
    shock_spacing_tolerance_m=float(shock_spacing_tolerance_m),
    area_tolerance_m2=float(area_tolerance_m2),
  )

  def build_run(
    *,
    status: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus,
    chain_runs: Sequence[MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun] = (),
    measurement: MocShockCellChainRefinementMeasurement | None = None,
    end: float | None = None,
    case_lineage_verified: bool = False,
    continued_field_fit_verified: bool = False,
    fidelity_isolation_verified: bool = True,
    message: str,
  ) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementRun:
    return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementRun(
      first_cell_fit_run=first_cell_fit_run,
      chain_runs=tuple(chain_runs),
      measurement=measurement,
      reference=resolved_reference,
      policy=resolved_policy,
      status=status,
      configuration=configuration,
      configuration_fingerprint=configuration_fingerprint,
      start_x_m=start,
      end_x_m=end,
      length_tolerance_m=length_tolerance,
      case_lineage_verified=case_lineage_verified,
      continued_field_fit_verified=continued_field_fit_verified,
      fidelity_isolation_verified=fidelity_isolation_verified,
      message=message,
    )
  ####

  if not (
    first_cell_fit_run.converged
    and first_cell_fit_run.measurement.local_consistency_verified
    and first_cell_fit_run.measurement.fidelity_isolation_verified
    and len(first_cell_fit_run.cases) >= 2
  ):
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
        .FIRST_CELL_FIT_REQUIRED
      ),
      message=(
        'continued-chain refinement requires at least two independently '
        'passing P3 first-cell cases'
      ),
    )
  ####

  cases = tuple(first_cell_fit_run.cases)
  resolutions = tuple(case.resolution for case in cases)
  if any(
    right <= left
    for left, right in zip(resolutions, resolutions[1:])
  ):
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
        .RESOLUTION_FAILURE
      ),
      message='P3 first-cell cases must be strictly ordered by resolution',
    )
  ####

  seed_endpoints = tuple(
    float(case.physical_field.ambient_boundary_points_m[-1][0])
    for case in cases
    if case.physical_field is not None
    and case.physical_field.ambient_boundary_points_m
  )
  if len(seed_endpoints) != len(cases):
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
        .CASE_FAILURE
      ),
      message='each P3 case must retain a finite ambient endpoint for continuation',
    )
  ####
  resolved_end = (
    max(seed_endpoints) + margin if requested_end is None else requested_end
  )
  if not isfinite(resolved_end) or resolved_end <= max(seed_endpoints):
    raise ValueError(
      'resolved end_x_m must be finite and downstream of every P3 seed endpoint'
    )
  ####

  chain_runs: list[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun
  ] = []
  for case in cases:
    chain_runs.append(
      run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_chain(
        first_cell_fit_run,
        start_x_m=start,
        end_x_m=resolved_end,
        end_margin_m=margin,
        reference=resolved_reference,
        policy=resolved_policy,
        seed_case=case,
      )
    )
  ####
  retained_chain_runs = tuple(chain_runs)
  case_lineage_verified = bool(
    len(retained_chain_runs) == len(cases)
    and all(
      run.seed_case is case
      and run.seed_case.resolution == case.resolution
      for run, case in zip(retained_chain_runs, cases, strict=True)
    )
  )
  continued_field_fit_verified = bool(
    case_lineage_verified
    and all(
      run.resolved
      and run.local_consistency_verified
      and run.continued_field_fit_verified
      and run.continued_cell_count == resolved_reference.total_cell_count - 1
      for run in retained_chain_runs
    )
  )
  fidelity_isolation_verified = bool(
    all(
      run.chain_promotion_blocked and not run.production_claim_allowed
      for run in retained_chain_runs
    )
  )
  observation_cases: list[MocShockCellChainRefinementCase] = []
  for resolution, run in zip(resolutions, retained_chain_runs, strict=True):
    observations = _observations_for_run(run)
    if observations is None:
      continue
    ####
    termination_reason = None
    physical_termination = None
    if run.planner is not None:
      termination_reason = run.planner.chain.termination_reason.value
      physical_termination = run.planner.chain.physical_termination
    ####
    observation_cases.append(
      MocShockCellChainRefinementCase(
        resolution=resolution[0],
        observations=observations,
        termination_reason=termination_reason,
        physical_termination=physical_termination,
      )
    )
  ####
  measurement = None
  if len(observation_cases) >= 2:
    measurement = measure_moc_shock_cell_chain_refinement(
      observation_cases,
      endpoint_tolerance_m=endpoint_tolerance_m,
      shock_spacing_tolerance_m=shock_spacing_tolerance_m,
      area_tolerance_m2=area_tolerance_m2,
    )
  ####
  continued_lengths = tuple(
    run.continued_cell_lengths_m for run in retained_chain_runs
  )
  continued_length_deltas = tuple(
    tuple(
      abs(right - left)
      for left, right in zip(previous, current, strict=True)
    )
    if len(previous) == len(current) else ()
    for previous, current in zip(continued_lengths, continued_lengths[1:])
  )
  continued_length_sensitivity_verified = bool(
    all(
      delta <= length_tolerance
      for pair in continued_length_deltas
      for delta in pair
    )
    and all(len(lengths) == resolved_reference.total_cell_count - 1 for lengths in continued_lengths)
  )
  if not case_lineage_verified or not continued_field_fit_verified:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .CASE_FAILURE
    )
    message = (
      'one or more retained P3 cases failed exact continued-chain lineage or '
      'independent downstream field-fit gates'
    )
  elif measurement is None:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .MEASUREMENT_FAILURE
    )
    message = (
      'independent continued-chain refinement measurement had no valid '
      'observation ladder'
    )
  elif not measurement.converged:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .SENSITIVITY_FAILURE
      if measurement.status is MocShockCellChainRefinementMeasurementStatus.SENSITIVITY_FAILURE
      else MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus.MEASUREMENT_FAILURE
    )
    measurement_report = measurement.as_report()
    message = (
      'independent continued-chain refinement measurement did not converge: '
      f'{measurement.status.value}: {measurement.message}; '
      f'checks={measurement_report.get("checks")}; '
      f'residuals={measurement_report.get("residuals")}'
    )
  elif not fidelity_isolation_verified:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .FIDELITY_FAILURE
    )
    message = 'continued-chain refinement weakened its research-only boundary'
  elif (
    measurement.refinement_convergence_verified is not True
    or not continued_length_sensitivity_verified
  ):
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .SENSITIVITY_FAILURE
    )
    message = (
      'continued-chain geometry or downstream axial lengths exceeded the '
      'declared refinement tolerances'
    )
  else:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRefinementStatus
      .CONVERGED_RESEARCH_CONTINUED_CHAIN_REFINEMENT
    )
    message = (
      'continued-chain field fits and geometry are stable across the accepted '
      'P3 resolution ladder; physical length acceptance and external validation '
      'remain open'
    )
  ####
  return build_run(
    status=status,
    chain_runs=retained_chain_runs,
    measurement=measurement,
    end=resolved_end,
    case_lineage_verified=case_lineage_verified,
    continued_field_fit_verified=continued_field_fit_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####
