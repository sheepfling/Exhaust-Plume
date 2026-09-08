"""Continued shock-cell fields bound to the accepted coupled P2.2c field.

The first-cell adapter proves that a fine P2.2c ladder can feed the
solver-owned shock-cell fitter.  This module carries that exact highest
resolution field into the fresh exact-Euler continuation planner.  It does
not re-solve or replace the accepted seed, and it does not promote the
continued fields to a physical length, canonical closure, external
validation, or production provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.chain import MocChainContinuationPolicy
from exhaust_plume.models.moc.global_physical_closure import (
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_cell import MocPhysicalPostShockFieldResult
from exhaust_plume.models.moc.planner import (
  MocChainPlannerResult,
  MocGlobalEulerContinuedChainReference,
  plan_reflected_domain_global_euler_continued_chain,
)
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainGlobalEulerShockBoundaryResult,
)
from exhaust_plume.validation.moc_global_coupled_shock_cell_fit import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase,
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
)
from exhaust_plume.validation.moc_measurements import (
  MocPhysicalFieldChainMeasurement,
  MocShockCellMeasurement,
  measure_moc_ambient_closed_physical_field_chain,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun',
  'run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_chain',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-chain'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-chain-run'
)


class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus(
  str, Enum
):
  """Typed outcome for the carried continued-chain handoff."""

  CONVERGED_RESEARCH_CONTINUED_CHAIN = (
    'converged-research-global-coupled-boundary-condition-feedback-continued-chain'
  )
  INVALID_INPUT = 'invalid_input'
  FIRST_CELL_FIT_REQUIRED = (
    'global-coupled-boundary-condition-feedback-continued-chain-first-cell-fit-required'
  )
  FIELD_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-field-failure'
  )
  CONTINUED_FIELD_FIT_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-field-fit-failure'
  )
  CHAIN_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-solver-failure'
  )
  MEASUREMENT_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-measurement-failure'
  )
  FIDELITY_FAILURE = (
    'global-coupled-boundary-condition-feedback-continued-chain-fidelity-failure'
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


def _report_converged(value: Any) -> bool:
  return isinstance(value, dict) and value.get('status') == 'converged'
####


def _report_count(value: Any) -> int:
  try:
    return max(0, int(value))
  except (TypeError, ValueError):
    return 0
  ####
####


def _bridge_endpoints_from_report(
  value: Any,
) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...] | None:
  if value is None:
    return None
  ####
  try:
    raw_bridges = tuple(value)
    normalized: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for raw_bridge in raw_bridges:
      if len(raw_bridge) != 2:
        return None
      ####
      start, end = raw_bridge
      if len(start) != 2 or len(end) != 2:
        return None
      ####
      start_point = (float(start[0]), float(start[1]))
      end_point = (float(end[0]), float(end[1]))
      if not all(isfinite(value) for value in (*start_point, *end_point)):
        return None
      ####
      normalized.append((start_point, end_point))
    ####
    return tuple(normalized)
  except (IndexError, TypeError, ValueError):
    return None
  ####
####


def _configuration(
  *,
  first_cell_fit_run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
  seed_case: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase | None,
  start_x_m: float,
  requested_end_x_m: float | None,
  resolved_end_x_m: float | None,
  end_margin_m: float,
  reference: MocGlobalEulerContinuedChainReference,
  policy: MocChainContinuationPolicy,
) -> tuple[tuple[tuple[str, Any], ...], str]:
  payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_RUN_OPERATOR_ID
    ),
    'first_cell_fit_configuration_fingerprint': (
      first_cell_fit_run.configuration_fingerprint
    ),
    'seed_case_id': None if seed_case is None else seed_case.case_id,
    'seed_resolution': None if seed_case is None else seed_case.resolution,
    'start_x_m': start_x_m,
    'requested_end_x_m': requested_end_x_m,
    'resolved_end_x_m': resolved_end_x_m,
    'end_margin_m': end_margin_m,
    'reference': reference.as_report(),
    'policy': _policy_report(policy),
    'continuation_model': (
      'accepted-fine-p2.2c-global-euler-seed -> fresh-source-band -> '
      'global-shock-remesh -> exact-global-euler-continued-field'
    ),
  }
  configuration = tuple(
    (name, payload[name]) for name in sorted(payload)
  )
  return configuration, _payload_fingerprint(payload)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun:
  """Research-only continuation bound to one accepted fine P2.2c field."""

  first_cell_fit_run: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun
  )
  seed_case: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase
    | None
  )
  seed_global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult | None
  planner: MocChainPlannerResult | None
  reference: MocGlobalEulerContinuedChainReference
  policy: MocChainContinuationPolicy
  status: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
  )
  source_closure_fingerprint: str | None
  seed_field_fingerprint: str | None
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  start_x_m: float
  end_x_m: float | None
  requested_end_x_m: float | None
  seed_field_handoff_verified: bool = False
  seed_measurement_verified: bool = False
  continued_chain_measurement_verified: bool = False
  intercell_bridge_verified: bool = False
  stage_measurements_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''
  physical_fields: tuple[MocPhysicalPostShockFieldResult, ...] = ()
  physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None
  continued_field_fit_measurements: tuple[MocShockCellMeasurement, ...] = ()

  def __post_init__(self) -> None:
    if not isinstance(
      self.first_cell_fit_run,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun,
    ):
      raise TypeError('first_cell_fit_run must be a typed P3 first-cell run')
    ####
    if self.seed_case is not None and not isinstance(
      self.seed_case,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase,
    ):
      raise TypeError('seed_case must be a typed P3 shock-cell-fit case or None')
    ####
    if self.seed_global_euler is not None and not isinstance(
      self.seed_global_euler,
      MocReflectedDomainGlobalEulerShockBoundaryResult,
    ):
      raise TypeError(
        'seed_global_euler must be a global Euler result or None'
      )
    ####
    if self.planner is not None and not isinstance(
      self.planner,
      MocChainPlannerResult,
    ):
      raise TypeError('planner must be a MocChainPlannerResult or None')
    ####
    if self.seed_case is not None and not any(
      case is self.seed_case for case in self.first_cell_fit_run.cases
    ):
      raise ValueError(
        'seed_case must be retained by the exact first_cell_fit_run'
      )
    ####
    if not isinstance(self.reference, MocGlobalEulerContinuedChainReference):
      raise TypeError(
        'reference must be a MocGlobalEulerContinuedChainReference'
      )
    ####
    if not isinstance(self.policy, MocChainContinuationPolicy):
      raise TypeError('policy must be a MocChainContinuationPolicy')
    ####
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus,
    ):
      raise TypeError('status must be a typed continued-chain status')
    ####
    start = float(self.start_x_m)
    if not isfinite(start):
      raise ValueError('start_x_m must be finite')
    ####
    end = None if self.end_x_m is None else float(self.end_x_m)
    if end is not None and (not isfinite(end) or end <= start):
      raise ValueError('end_x_m must be finite and greater than start_x_m')
    ####
    requested = (
      None
      if self.requested_end_x_m is None
      else float(self.requested_end_x_m)
    )
    if requested is not None and not isfinite(requested):
      raise ValueError('requested_end_x_m must be finite when supplied')
    ####
    if len(str(self.configuration_fingerprint)) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    for name in (
      'seed_field_handoff_verified',
      'seed_measurement_verified',
      'continued_chain_measurement_verified',
      'intercell_bridge_verified',
      'stage_measurements_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.seed_global_euler is not None and self.seed_case is None:
      raise ValueError('seed_global_euler requires a retained seed_case')
    ####
    if self.seed_case is None:
      if self.source_closure_fingerprint is not None:
        raise ValueError(
          'source_closure_fingerprint requires a retained seed_case'
        )
      ####
    else:
      expected_source_fingerprint = (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.seed_case.source_closure
        )
      )
      if self.source_closure_fingerprint != expected_source_fingerprint:
        raise ValueError(
          'source_closure_fingerprint does not match the retained seed_case'
        )
      ####
      if (
        self.seed_global_euler is not None
        and self.seed_case.source_closure.global_euler
        is not self.seed_global_euler
      ):
        raise ValueError(
          'seed_global_euler must be the exact result retained by seed_case'
        )
      ####
    ####
    if self.planner is not None and self.seed_global_euler is None:
      raise ValueError('planner requires the exact retained seed_global_euler')
    ####
    if self.first_cell_fit_run.production_claim_allowed:
      raise ValueError('continued-chain handoff cannot consume production P3 evidence')
    ####
    physical_fields = tuple(self.physical_fields)
    if any(
      not isinstance(field, MocPhysicalPostShockFieldResult)
      for field in physical_fields
    ):
      raise TypeError(
        'physical_fields must contain MocPhysicalPostShockFieldResult values'
      )
    ####
    if self.physical_field_chain_measurement is not None and not isinstance(
      self.physical_field_chain_measurement,
      MocPhysicalFieldChainMeasurement,
    ):
      raise TypeError(
        'physical_field_chain_measurement must be a typed physical-field '
        'chain measurement or None'
      )
    ####
    continued_measurements = tuple(self.continued_field_fit_measurements)
    if any(
      not isinstance(measurement, MocShockCellMeasurement)
      for measurement in continued_measurements
    ):
      raise TypeError(
        'continued_field_fit_measurements must contain typed shock-cell measurements'
      )
    ####
    if len(continued_measurements) > max(0, len(physical_fields) - 1):
      raise ValueError(
        'continued_field_fit_measurements cannot exceed the retained '
        'downstream physical-field count'
      )
    ####
    object.__setattr__(self, 'start_x_m', start)
    object.__setattr__(self, 'end_x_m', end)
    object.__setattr__(self, 'requested_end_x_m', requested)
    object.__setattr__(self, 'configuration', tuple(self.configuration))
    object.__setattr__(self, 'configuration_fingerprint', str(self.configuration_fingerprint))
    object.__setattr__(self, 'message', str(self.message))
    object.__setattr__(self, 'physical_fields', physical_fields)
    object.__setattr__(
      self,
      'continued_field_fit_measurements',
      continued_measurements,
    )
  ####

  @property
  def resolved(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
      .CONVERGED_RESEARCH_CONTINUED_CHAIN
    )
  ####

  @property
  def continued_cell_count(self) -> int:
    if self.continued_field_fit_measurements:
      return len(self.continued_field_fit_measurements)
    ####
    if len(self.physical_fields) > 1:
      return len(self.physical_fields) - 1
    ####
    if self.planner is None:
      return 0
    ####
    value = self.planner.diagnostics.get(
      'global_euler_continued_chain_research_physical_cell_count',
      max(0, self.planner.chain.cell_count - 1),
    )
    return _report_count(value)
  ####

  @property
  def continued_cell_lengths_m(self) -> tuple[float, ...]:
    return tuple(
      float(measurement.axial_length_m)
      for measurement in self.continued_field_fit_measurements
      if measurement.axial_length_m is not None
      and isfinite(float(measurement.axial_length_m))
    )
  ####

  @property
  def continued_field_fit_verified(self) -> bool:
    return bool(
      self.physical_field_chain_measurement is not None
      and self.physical_field_chain_measurement.converged
      and len(self.physical_fields) >= 2
      and len(self.continued_field_fit_measurements)
      == len(self.physical_fields) - 1
      and all(measurement.converged for measurement in self.continued_field_fit_measurements)
    )
  ####

  @property
  def continued_length_refinement_pending(self) -> bool:
    """Return whether continued-cell length uncertainty still lacks a ladder."""

    return True
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.resolved
      and self.first_cell_fit_run.converged
      and self.first_cell_fit_run.measurement.local_consistency_verified
      and self.seed_case is not None
      and self.seed_global_euler is not None
      and self.planner is not None
      and self.planner.resolved
      and self.planner.handoff_links_verified is True
      and self.seed_field_handoff_verified
      and self.seed_measurement_verified
      and self.continued_chain_measurement_verified
      and self.continued_field_fit_verified
      and self.intercell_bridge_verified
      and self.stage_measurements_verified
      and self.fidelity_isolation_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    diagnostics = {} if self.planner is None else dict(self.planner.diagnostics)
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_CHAIN_RUN_OPERATOR_ID
      ),
      'status': self.status.value,
      'resolved': self.resolved,
      'local_consistency_verified': self.local_consistency_verified,
      'seed_case_id': None if self.seed_case is None else self.seed_case.case_id,
      'seed_resolution': None if self.seed_case is None else self.seed_case.resolution,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'seed_field_fingerprint': self.seed_field_fingerprint,
      'configuration': dict(self.configuration),
      'configuration_fingerprint': self.configuration_fingerprint,
      'start_x_m': self.start_x_m,
      'end_x_m': self.end_x_m,
      'requested_end_x_m': self.requested_end_x_m,
      'continued_cell_count': self.continued_cell_count,
      'retained_physical_field_count': len(self.physical_fields),
      'retained_physical_field_fingerprints': [
        _payload_fingerprint(field.as_report())
        for field in self.physical_fields
      ],
      'continued_cell_lengths_m': list(self.continued_cell_lengths_m),
      'continued_length_refinement_pending': (
        self.continued_length_refinement_pending
      ),
      'reference': self.reference.as_report(),
      'policy': _policy_report(self.policy),
      'checks': {
        'seed_field_handoff_verified': self.seed_field_handoff_verified,
        'seed_measurement_verified': self.seed_measurement_verified,
        'continued_chain_measurement_verified': (
          self.continued_chain_measurement_verified
        ),
        'continued_field_fit_verified': self.continued_field_fit_verified,
        'intercell_bridge_verified': self.intercell_bridge_verified,
        'stage_measurements_verified': self.stage_measurements_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'planner': None if self.planner is None else self.planner.as_report(),
      'planner_diagnostics': diagnostics,
      'physical_field_chain_measurement': (
        None
        if self.physical_field_chain_measurement is None
        else self.physical_field_chain_measurement.as_report()
      ),
      'continued_field_fit_measurements': [
        measurement.as_report()
        for measurement in self.continued_field_fit_measurements
      ],
      'first_cell_fit': self.first_cell_fit_run.as_report(),
      'seed_case': None if self.seed_case is None else self.seed_case.as_report(),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'physical_length_accepted': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'accepted-fine-p2.2c-field-to-fresh-global-euler-continued-chain; '
        'local-research-only; physical-length-not-accepted'
      ),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_chain(
  first_cell_fit_run: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun
  ),
  *,
  start_x_m: float | None = None,
  end_x_m: float | None = None,
  end_margin_m: float = 8.0,
  reference: MocGlobalEulerContinuedChainReference | None = None,
  policy: MocChainContinuationPolicy | None = None,
  seed_case: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase | None = None,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun:
  """Continue one exact retained P2.2c/P3 field.

  By default, the highest-resolution P3 case is selected.  A refinement
  adapter may explicitly select another retained, independently passing case;
  the function still passes that case's exact global-Euler result to the
  fresh-source continuation planner.  It never reconstructs a seed from a
  different source band and never treats a failed continuation as a physical
  endpoint.
  """

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
    raise TypeError(
      'reference must be a MocGlobalEulerContinuedChainReference or None'
    )
  ####
  if resolved_reference.total_cell_count < 2:
    raise ValueError(
      'continued-chain handoff requires at least one cell beyond the seed'
    )
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
  if resolved_policy.max_cells < 2:
    raise ValueError(
      'continued-chain handoff policy requires at least two cells'
    )
  ####
  resolved_start = (
    first_cell_fit_run.start_x_m
    if start_x_m is None else float(start_x_m)
  )
  if not isfinite(resolved_start):
    raise ValueError('start_x_m must be finite')
  ####
  requested_end = None if end_x_m is None else float(end_x_m)
  if requested_end is not None and not isfinite(requested_end):
    raise ValueError('end_x_m must be finite when supplied')
  ####
  margin = float(end_margin_m)
  if not isfinite(margin) or margin <= 0.0:
    raise ValueError('end_margin_m must be finite and positive')
  ####

  requested_seed_case = seed_case
  if requested_seed_case is not None and not any(
    case is requested_seed_case for case in first_cell_fit_run.cases
  ):
    raise ValueError(
      'seed_case must be one of the exact cases retained by first_cell_fit_run'
    )
  ####
  seed_case = (
    requested_seed_case
    if first_cell_fit_run.converged and requested_seed_case is not None
    else (
      first_cell_fit_run.cases[-1]
      if first_cell_fit_run.converged and first_cell_fit_run.cases else None
    )
  )
  initial_configuration, initial_fingerprint = _configuration(
    first_cell_fit_run=first_cell_fit_run,
    seed_case=seed_case,
    start_x_m=resolved_start,
    requested_end_x_m=requested_end,
    resolved_end_x_m=None,
    end_margin_m=margin,
    reference=resolved_reference,
    policy=resolved_policy,
  )

  def build_run(
    *,
    status: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus,
    seed_global_euler: MocReflectedDomainGlobalEulerShockBoundaryResult | None,
    planner: MocChainPlannerResult | None,
    source_closure_fingerprint: str | None,
    seed_field_fingerprint: str | None,
    end: float | None,
    seed_field_handoff_verified: bool,
    seed_measurement_verified: bool,
    continued_chain_measurement_verified: bool,
    intercell_bridge_verified: bool,
    stage_measurements_verified: bool,
    fidelity_isolation_verified: bool,
    message: str,
    physical_fields: tuple[MocPhysicalPostShockFieldResult, ...] = (),
    physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None,
    continued_field_fit_measurements: tuple[MocShockCellMeasurement, ...] = (),
  ) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun:
    configuration, configuration_fingerprint = _configuration(
      first_cell_fit_run=first_cell_fit_run,
      seed_case=seed_case,
      start_x_m=resolved_start,
      requested_end_x_m=requested_end,
      resolved_end_x_m=end,
      end_margin_m=margin,
      reference=resolved_reference,
      policy=resolved_policy,
    )
    if not configuration:
      configuration = initial_configuration
      configuration_fingerprint = initial_fingerprint
    ####
    return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainRun(
      first_cell_fit_run=first_cell_fit_run,
      seed_case=seed_case,
      seed_global_euler=seed_global_euler,
      planner=planner,
      reference=resolved_reference,
      policy=resolved_policy,
      status=status,
      source_closure_fingerprint=source_closure_fingerprint,
      seed_field_fingerprint=seed_field_fingerprint,
      configuration=configuration,
      configuration_fingerprint=configuration_fingerprint,
      start_x_m=resolved_start,
      end_x_m=end,
      requested_end_x_m=requested_end,
      seed_field_handoff_verified=seed_field_handoff_verified,
      seed_measurement_verified=seed_measurement_verified,
      continued_chain_measurement_verified=continued_chain_measurement_verified,
      intercell_bridge_verified=intercell_bridge_verified,
      stage_measurements_verified=stage_measurements_verified,
      fidelity_isolation_verified=fidelity_isolation_verified,
      message=message,
      physical_fields=physical_fields,
      physical_field_chain_measurement=physical_field_chain_measurement,
      continued_field_fit_measurements=continued_field_fit_measurements,
    )
  ####

  if not (
    first_cell_fit_run.converged
    and first_cell_fit_run.measurement.local_consistency_verified
    and first_cell_fit_run.measurement.fidelity_isolation_verified
  ):
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
        .FIRST_CELL_FIT_REQUIRED
      ),
      seed_global_euler=None,
      planner=None,
      source_closure_fingerprint=None,
      seed_field_fingerprint=None,
      end=requested_end,
      seed_field_handoff_verified=False,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      stage_measurements_verified=False,
      fidelity_isolation_verified=True,
      message=(
        'continued-chain handoff requires the converged fine P2.2c-bound '
        'P3 first-cell run; no lower-fidelity seed was inferred'
      ),
    )
  ####

  if seed_case is None or not (
    seed_case.measurement.converged
    and seed_case.coupled_field_lineage_verified
    and seed_case.physical_field_handoff_verified
    and seed_case.fit_field_binding_verified
    and seed_case.fidelity_isolation_verified
    and seed_case.physical_field is not None
    and seed_case.fit is not None
  ):
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
        .FIRST_CELL_FIT_REQUIRED
      ),
      seed_global_euler=None,
      planner=None,
      source_closure_fingerprint=None,
      seed_field_fingerprint=None,
      end=requested_end,
      seed_field_handoff_verified=False,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      stage_measurements_verified=False,
      fidelity_isolation_verified=True,
      message=(
        'the selected retained P3 case did not pass its independent first-cell '
        'fit and lineage gates'
      ),
    )
  ####

  assert seed_case is not None
  source_closure = seed_case.source_closure
  source_band = source_closure.source_band
  seed_global_euler = source_closure.global_euler
  seed_physical_field = seed_case.physical_field
  source_field = (
    None
    if seed_global_euler is None or seed_global_euler.physical_field is None
    else seed_global_euler.physical_field.field
  )
  coupled_field = seed_case.coupled_field
  condition = (
    None
    if coupled_field is None
    else coupled_field.physical_field_shock_front_condition
  )
  seed_field_handoff_verified = bool(
    source_band is not None
    and seed_global_euler is not None
    and source_closure.global_euler is seed_global_euler
    and seed_global_euler.converged
    and seed_global_euler.physical_closure_verified
    and seed_global_euler.global_remesh is not None
    and seed_global_euler.global_remesh.source_band is source_band
    and seed_global_euler.incoming_handoff == source_band.incoming_handoff
    and seed_physical_field is not None
    and source_field is seed_physical_field
    and seed_case.fit is not None
    and seed_case.fit.closure is source_closure
    and seed_case.fit.candidate_field is seed_physical_field
    and seed_case.physical_field_handoff_verified
    and coupled_field is not None
    and condition is not None
    and condition.converged
    and condition.field is seed_physical_field
    and coupled_field.physical_field_shock_front_condition_consumed
    and coupled_field.initial_state_field_bound
    and coupled_field.chain_promotion_blocked
    and not coupled_field.production_claim_allowed
  )
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  seed_fingerprint = (
    None if seed_physical_field is None
    else _payload_fingerprint(seed_physical_field.as_report())
  )
  if not seed_field_handoff_verified:
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
        .FIELD_FAILURE
      ),
      seed_global_euler=seed_global_euler,
      planner=None,
      source_closure_fingerprint=source_fingerprint,
      seed_field_fingerprint=seed_fingerprint,
      end=requested_end,
      seed_field_handoff_verified=False,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      stage_measurements_verified=False,
      fidelity_isolation_verified=True,
      message=(
        'the highest-resolution P3 case did not retain the exact P2.2c '
        'physical field, source band, or consumed shock-front condition'
      ),
    )
  ####

  assert seed_global_euler is not None
  assert seed_physical_field is not None
  seed_ambient_points = tuple(seed_physical_field.ambient_boundary_points_m)
  if not seed_ambient_points:
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
        .FIELD_FAILURE
      ),
      seed_global_euler=seed_global_euler,
      planner=None,
      source_closure_fingerprint=source_fingerprint,
      seed_field_fingerprint=seed_fingerprint,
      end=requested_end,
      seed_field_handoff_verified=True,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      stage_measurements_verified=False,
      fidelity_isolation_verified=True,
      message='the accepted seed physical field retained no ambient endpoint',
    )
  ####

  seed_end_x = float(seed_ambient_points[-1][0])
  resolved_end = seed_end_x + margin if requested_end is None else requested_end
  if (
    not isfinite(seed_end_x)
    or resolved_start >= seed_end_x
    or resolved_end <= seed_end_x
  ):
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
        .CHAIN_FAILURE
      ),
      seed_global_euler=seed_global_euler,
      planner=None,
      source_closure_fingerprint=source_fingerprint,
      seed_field_fingerprint=seed_fingerprint,
      end=resolved_end,
      seed_field_handoff_verified=True,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      stage_measurements_verified=False,
      fidelity_isolation_verified=True,
      message=(
        'continued-chain bounds must begin before and extend beyond the '
        'accepted seed ambient endpoint'
      ),
    )
  ####

  retained_fields: list[MocPhysicalPostShockFieldResult] = []
  try:
    planner = plan_reflected_domain_global_euler_continued_chain(
      seed_global_euler,
      start_x_m=resolved_start,
      end_x_m=resolved_end,
      reference=resolved_reference,
      policy=resolved_policy,
      _field_observer=retained_fields.append,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return build_run(
      status=(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
        .CHAIN_FAILURE
      ),
      seed_global_euler=seed_global_euler,
      planner=None,
      source_closure_fingerprint=source_fingerprint,
      seed_field_fingerprint=seed_fingerprint,
      end=resolved_end,
      seed_field_handoff_verified=True,
      seed_measurement_verified=False,
      continued_chain_measurement_verified=False,
      intercell_bridge_verified=False,
      stage_measurements_verified=False,
      fidelity_isolation_verified=True,
      message=f'continued-chain planner raised: {error}',
    )
  ####

  diagnostics = dict(planner.diagnostics)
  physical_fields = tuple(retained_fields)
  bridge_endpoints = _bridge_endpoints_from_report(
    diagnostics.get(
      'global_euler_continued_chain_intercell_bridge_endpoints_m'
    )
  )
  physical_field_chain_measurement: MocPhysicalFieldChainMeasurement | None = None
  physical_field_chain_measurement_error: str | None = None
  if bridge_endpoints is not None and physical_fields:
    try:
      physical_field_chain_measurement = (
        measure_moc_ambient_closed_physical_field_chain(
          physical_fields,
          position_tolerance_m=resolved_reference.position_tolerance_m,
          state_tolerance=resolved_reference.invariant_tolerance,
          pressure_tolerance=resolved_reference.pressure_tolerance,
          tangent_tolerance=resolved_reference.tangent_tolerance,
          intercell_bridge_endpoints_m=bridge_endpoints,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      physical_field_chain_measurement_error = (
        f'{type(error).__name__}: {error}'
      )
    ####
  else:
    physical_field_chain_measurement_error = (
      'planner did not retain a typed field sequence and bridge endpoint sequence'
    )
  ####
  continued_field_fit_measurements = (
    ()
    if physical_field_chain_measurement is None
    else tuple(physical_field_chain_measurement.field_measurements[1:])
  )
  continued_field_fit_verified = bool(
    physical_field_chain_measurement is not None
    and physical_field_chain_measurement.converged
    and len(physical_fields) >= 2
    and physical_fields[0] is seed_physical_field
    and len(continued_field_fit_measurements) == len(physical_fields) - 1
    and all(measurement.converged for measurement in continued_field_fit_measurements)
  )
  diagnostics['global_euler_continued_chain_retained_field_count'] = len(
    physical_fields
  )
  diagnostics['global_euler_continued_chain_retained_field_fingerprints'] = [
    _payload_fingerprint(field.as_report()) for field in physical_fields
  ]
  diagnostics['global_euler_continued_chain_retained_field_lineage_verified'] = bool(
    physical_fields
    and physical_fields[0] is seed_physical_field
    and len(physical_fields)
    == _report_count(
      diagnostics.get('global_euler_continued_chain_captured_field_count')
    )
  )
  diagnostics['global_euler_continued_chain_physical_field_chain_measurement'] = (
    None
    if physical_field_chain_measurement is None
    else physical_field_chain_measurement.as_report()
  )
  diagnostics['global_euler_continued_chain_physical_field_chain_measurement_error'] = (
    physical_field_chain_measurement_error
  )
  diagnostics['global_euler_continued_chain_continued_field_fit_measurements'] = [
    measurement.as_report() for measurement in continued_field_fit_measurements
  ]
  diagnostics['global_euler_continued_chain_continued_field_fit_verified'] = (
    continued_field_fit_verified
  )
  seed_measurement = diagnostics.get(
    'global_euler_continued_chain_source_measurement'
  )
  seed_checks = (
    {} if not isinstance(seed_measurement, dict)
    else seed_measurement.get('checks', {})
  )
  seed_measurement_verified = bool(
    _report_converged(seed_measurement)
    and isinstance(seed_checks, dict)
    and seed_checks.get('incoming_handoff_verified') is True
    and seed_checks.get('physical_closure_verified') is True
    and seed_checks.get('fidelity_isolation_verified') is True
    and seed_checks.get('chain_promotion_blocked') is True
    and seed_checks.get('production_claim_allowed') is False
  )
  chain_measurement = diagnostics.get(
    'global_euler_continued_chain_independent_measurement'
  )
  planner_measurement = diagnostics.get(
    'global_euler_continued_chain_planner_measurement'
  )
  chain_handoff = (
    {} if not isinstance(chain_measurement, dict)
    else chain_measurement.get('handoff', {})
  )
  intercell_bridges = (
    {} if not isinstance(chain_measurement, dict)
    else chain_measurement.get('intercell_bridges', {})
  )
  continued_chain_measurement_verified = bool(
    diagnostics.get('global_euler_continued_chain_audit_accepted') is True
    and _report_converged(chain_measurement)
    and _report_converged(planner_measurement)
    and isinstance(chain_measurement, dict)
    and isinstance(chain_handoff, dict)
    and chain_handoff.get('links_verified') is True
    and chain_measurement.get('fresh_domain_verified') is True
    and isinstance(intercell_bridges, dict)
    and intercell_bridges.get('verified') is True
    and chain_measurement.get('physical_closure_verified') is True
    and continued_field_fit_verified
  )
  intercell_bridge_verified = bool(
    isinstance(intercell_bridges, dict)
    and _report_count(intercell_bridges.get('count')) > 0
    and intercell_bridges.get('verified') is True
  )
  stage_measurements_verified = bool(
    diagnostics.get('global_euler_continued_chain_stage_measurements_converged')
    is True
  )
  field_reports = diagnostics.get(
    'global_euler_continued_chain_global_euler_fields',
    (),
  )
  fidelity_isolation_verified = bool(
    planner.production_claim_allowed is False
    and diagnostics.get('chain_promotion_blocked') is True
    and diagnostics.get('production_claim_allowed') is False
    and all(
      isinstance(report, dict)
      and report.get('chain_promotion_blocked') is True
      and report.get('production_claim_allowed') is False
      for report in field_reports
    )
  )
  if not planner.resolved:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
      .CHAIN_FAILURE
    )
    message = (
      'continued-chain planner did not resolve an accepted research prefix; '
      'no physical endpoint or lower-fidelity fallback was inferred'
    )
  elif not continued_field_fit_verified:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
      .CONTINUED_FIELD_FIT_FAILURE
    )
    message = (
      'continued fields were available, but the exact retained objects did not '
      'pass the independent downstream field-fit measurement'
    )
  elif not (
    seed_measurement_verified
    and continued_chain_measurement_verified
    and intercell_bridge_verified
    and stage_measurements_verified
  ):
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
      .MEASUREMENT_FAILURE
    )
    message = (
      'continued-chain fields were retained, but the independent seed, '
      'planner, chain, bridge, or stage audit did not pass'
    )
  elif not fidelity_isolation_verified:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
      .FIDELITY_FAILURE
    )
    message = 'continued-chain evidence weakened its research-only boundary'
  else:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellChainStatus
      .CONVERGED_RESEARCH_CONTINUED_CHAIN
    )
    message = (
      'the exact highest-resolution P2.2c/P3 seed fed fresh exact-Euler '
      'continued fields with independently verified handoff and intercell '
      'bridges; physical length acceptance and external validation remain open'
    )
  ####
  return build_run(
    status=status,
    seed_global_euler=seed_global_euler,
    planner=planner,
    source_closure_fingerprint=source_fingerprint,
    seed_field_fingerprint=seed_fingerprint,
    end=resolved_end,
    seed_field_handoff_verified=True,
    seed_measurement_verified=seed_measurement_verified,
    continued_chain_measurement_verified=continued_chain_measurement_verified,
    intercell_bridge_verified=intercell_bridge_verified,
    stage_measurements_verified=stage_measurements_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
    physical_fields=physical_fields,
    physical_field_chain_measurement=physical_field_chain_measurement,
    continued_field_fit_measurements=continued_field_fit_measurements,
  )
####
