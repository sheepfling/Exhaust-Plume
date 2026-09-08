"""P3 shock-cell fitting bound to the accepted local P2.2c field.

The production shock-cell fitter already consumes a solver-owned global
physical closure.  This adapter closes the missing provenance seam between
the fine global/downstream boundary-feedback refinement and that fitter.  It
accepts only a converged research refinement run, verifies that each final
coupled field consumed the exact source shock-front condition, and measures
the resulting first-cell candidate independently.

The reported length uncertainty is a resolution-sequence quantity: the
maximum adjacent change in independently measured axial extent.  It is not an
accepted physical uncertainty, and the continued-chain, external-observation,
canonical-closure, and production gates remain explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  PHYSICAL_FIELD_EXACT_INITIAL_STATE_SOURCE,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocProductionShockCellFitResult,
  MocReflectedDomainGlobalPhysicalClosureResult,
  fit_reflected_domain_production_shock_cell,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_cell import MocPhysicalPostShockFieldResult
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback_refinement import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase,
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun,
)
from exhaust_plume.validation.moc_measurements import (
  MocShockCellMeasurement,
  measure_moc_production_shock_cell_fit,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement',
  'measure_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_fit',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun',
  'run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_fit',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-fit'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-shock-cell-fit-run'
)


class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus(
  str, Enum
):
  """Typed P3 outcome for a coupled-field first-cell fit."""

  CONVERGED_RESEARCH_FIRST_CELL_FIT = (
    'converged-research-global-coupled-boundary-condition-feedback-first-cell-fit'
  )
  INVALID_INPUT = 'invalid_input'
  P2_REFINEMENT_REQUIRED = (
    'global-coupled-boundary-condition-feedback-shock-cell-fit-p2-refinement-required'
  )
  FIELD_FAILURE = (
    'global-coupled-boundary-condition-feedback-shock-cell-fit-field-failure'
  )
  FIT_FAILURE = (
    'global-coupled-boundary-condition-feedback-shock-cell-fit-fit-failure'
  )
  MEASUREMENT_FAILURE = (
    'global-coupled-boundary-condition-feedback-shock-cell-fit-measurement-failure'
  )
  LENGTH_STABILITY_FAILURE = (
    'global-coupled-boundary-condition-feedback-shock-cell-fit-length-stability-failure'
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


def _resolution(value: Sequence[int]) -> tuple[int, int, int]:
  resolved = tuple(value)
  if len(resolved) != 3 or any(
    isinstance(item, bool) or not isinstance(item, int) or item < 1
    for item in resolved
  ):
    raise ValueError('resolution must contain three positive integers')
  ####
  return resolved  # type: ignore[return-value]
####


def _resolution_ladder_verified(
  resolutions: Sequence[tuple[int, int, int]],
) -> bool:
  return bool(
    len(resolutions) >= 2
    and all(
      all(right[index] > left[index] for index in range(3))
      for left, right in zip(resolutions, resolutions[1:])
    )
  )
####


def _source_field(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> MocPhysicalPostShockFieldResult | None:
  global_euler = closure.global_euler
  physical = None if global_euler is None else global_euler.physical_field
  return None if physical is None else physical.field
####


def _final_coupled_field(
  case: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult | None:
  """Return the final retained coupled field for one P2.2c case."""

  if not case.run.iterations:
    return None
  ####
  downstream = case.run.iterations[-1].downstream_feedback
  if downstream is None or not downstream.iterations:
    return None
  ####
  return downstream.iterations[-1].result.coupled_field
####


def _coupled_field_fingerprint(
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None,
) -> str:
  if coupled_field is None:
    return 'unavailable'
  ####
  return _payload_fingerprint(coupled_field.as_report())
####


def _physical_field_handoff_verified(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None,
) -> tuple[bool, MocPhysicalPostShockFieldResult | None]:
  source_field = _source_field(closure)
  if source_field is None or coupled_field is None:
    return False, None
  ####
  condition = coupled_field.physical_field_shock_front_condition
  request = coupled_field.request
  verified = bool(
    condition is not None
    and condition.converged
    and condition.field is source_field
    and request is not None
    and request.physical_field_shock_front_condition is condition
    and coupled_field.physical_field_shock_front_condition_consumed
    and coupled_field.initial_state_field_bound
    and coupled_field.initial_state_source
    == PHYSICAL_FIELD_EXACT_INITIAL_STATE_SOURCE
  )
  return verified, condition.field if condition is not None else None
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase:
  """One first-cell fit bound to one retained P2.2c coupled field."""

  case_id: str
  regime: str
  resolution: tuple[int, int, int]
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  feedback_case: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase
  )
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  physical_field: MocPhysicalPostShockFieldResult | None
  fit: MocProductionShockCellFitResult | None
  measurement: MocShockCellMeasurement
  coupled_field_lineage_verified: bool = False
  physical_field_handoff_verified: bool = False
  fit_field_binding_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not str(self.case_id) or not str(self.regime):
      raise ValueError('case_id and regime must be non-empty')
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.feedback_case,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase,
    ):
      raise TypeError('feedback_case must be a typed P2.2c case')
    ####
    if self.coupled_field is not None and not isinstance(
      self.coupled_field,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError('coupled_field must be a coupled Euler result or None')
    ####
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError('physical_field must be a physical field result or None')
    ####
    if self.fit is not None and not isinstance(
      self.fit,
      MocProductionShockCellFitResult,
    ):
      raise TypeError('fit must be a MocProductionShockCellFitResult or None')
    ####
    if not isinstance(self.measurement, MocShockCellMeasurement):
      raise TypeError('measurement must be a MocShockCellMeasurement')
    ####
    for name in (
      'coupled_field_lineage_verified',
      'physical_field_handoff_verified',
      'fit_field_binding_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'case_id', str(self.case_id))
    object.__setattr__(self, 'regime', str(self.regime))
    object.__setattr__(self, 'resolution', _resolution(self.resolution))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def local_research_verified(self) -> bool:
    return bool(
      self.feedback_case.local_research_verified
      and self.coupled_field is not None
      and self.coupled_field.coupled_euler_field_verified
      and self.physical_field is not None
      and self.fit is not None
      and self.fit.local_fit_verified
      and self.measurement.converged
      and self.coupled_field_lineage_verified
      and self.physical_field_handoff_verified
      and self.fit_field_binding_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'resolution': self.resolution,
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'coupled_field_fingerprint': _coupled_field_fingerprint(
        self.coupled_field
      ),
      'coupled_field_status': (
        None if self.coupled_field is None else self.coupled_field.status.value
      ),
      'physical_field_status': (
        None if self.physical_field is None else self.physical_field.status.value
      ),
      'fit_status': None if self.fit is None else self.fit.status.value,
      'measurement': self.measurement.as_report(),
      'local_research_verified': self.local_research_verified,
      'checks': {
        'coupled_field_lineage_verified': self.coupled_field_lineage_verified,
        'physical_field_handoff_verified': self.physical_field_handoff_verified,
        'fit_field_binding_verified': self.fit_field_binding_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
      },
      'fit': None if self.fit is None else self.fit.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement:
  """Independent first-cell evidence and resolution-derived uncertainty."""

  status: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
  )
  cases: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase, ...
  ] = ()
  resolutions: tuple[tuple[int, int, int], ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  coupled_field_fingerprints: tuple[str, ...] = ()
  axial_lengths_m: tuple[float | None, ...] = ()
  axial_length_deltas_m: tuple[float | None, ...] = ()
  length_uncertainty_m: float | None = None
  length_uncertainty_fraction: float | None = None
  p2_refinement_verified: bool = False
  resolution_order_verified: bool = False
  case_bindings_verified: bool = False
  coupled_fields_verified: bool = False
  physical_field_handoffs_verified: bool = False
  first_cell_fits_verified: bool = False
  measurements_verified: bool = False
  solver_owned_length_verified: bool = False
  lengths_finite_verified: bool = False
  length_resolution_sequence_verified: bool = False
  physical_closure_verified: bool = False
  fidelity_isolation_verified: bool = False
  continued_chain_fits_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  continued_chain_status: str = 'not_attempted; separate P3 gate'
  claim_status: str = (
    'global-coupled-first-cell-fit; local-research-only; physical-length-not-accepted'
  )
  message: str = ''
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus,
    ):
      raise TypeError('status must be a typed P3 shock-cell-fit status')
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed P3 shock-cell-fit cases')
    ####
    resolutions = tuple(_resolution(value) for value in self.resolutions)
    if resolutions and resolutions != tuple(case.resolution for case in cases):
      raise ValueError('resolutions must match case resolutions')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'resolutions', resolutions)
    for name in ('source_closure_fingerprints', 'coupled_field_fingerprints'):
      values = tuple(str(value) for value in getattr(self, name))
      if values and len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      if values and any(not value for value in values):
        raise ValueError(f'{name} must contain non-empty strings')
      ####
      object.__setattr__(self, name, values)
    ####
    lengths = tuple(self.axial_lengths_m)
    if len(lengths) != len(cases):
      raise ValueError('axial_lengths_m must match the case count')
    ####
    if any(
      value is not None
      and (not isfinite(float(value)) or float(value) < 0.0)
      for value in lengths
    ):
      raise ValueError('axial_lengths_m must be finite nonnegative values or None')
    ####
    object.__setattr__(self, 'axial_lengths_m', lengths)
    deltas = tuple(self.axial_length_deltas_m)
    if len(deltas) != max(0, len(cases) - 1):
      raise ValueError('axial_length_deltas_m must align adjacent cases')
    ####
    if any(
      value is not None
      and (not isfinite(float(value)) or float(value) < 0.0)
      for value in deltas
    ):
      raise ValueError(
        'axial_length_deltas_m must be finite nonnegative values or None'
      )
    ####
    object.__setattr__(self, 'axial_length_deltas_m', deltas)
    for name in (
      'p2_refinement_verified',
      'resolution_order_verified',
      'case_bindings_verified',
      'coupled_fields_verified',
      'physical_field_handoffs_verified',
      'first_cell_fits_verified',
      'measurements_verified',
      'solver_owned_length_verified',
      'lengths_finite_verified',
      'length_resolution_sequence_verified',
      'physical_closure_verified',
      'fidelity_isolation_verified',
      'continued_chain_fits_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('length_uncertainty_m', 'length_uncertainty_fraction'):
      value = getattr(self, name)
      if value is not None:
        normalized = float(value)
        if not isfinite(normalized) or normalized < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, normalized)
      ####
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('P3 shock-cell fit must remain promotion-blocked')
    ####
    if not self.external_validation_required:
      raise ValueError('P3 shock-cell fit must retain external validation')
    ####
    object.__setattr__(self, 'continued_chain_status', str(self.continued_chain_status))
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .CONVERGED_RESEARCH_FIRST_CELL_FIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and len(self.cases) >= 2
      and self.p2_refinement_verified
      and self.resolution_order_verified
      and self.case_bindings_verified
      and self.coupled_fields_verified
      and self.physical_field_handoffs_verified
      and self.first_cell_fits_verified
      and self.measurements_verified
      and self.solver_owned_length_verified
      and self.lengths_finite_verified
      and self.length_resolution_sequence_verified
      and self.physical_closure_verified
      and self.fidelity_isolation_verified
      and not self.continued_chain_fits_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and self.external_validation_required
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'resolutions': self.resolutions,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'coupled_field_fingerprints': self.coupled_field_fingerprints,
      'axial_lengths_m': self.axial_lengths_m,
      'axial_length_deltas_m': self.axial_length_deltas_m,
      'length_uncertainty_m': self.length_uncertainty_m,
      'length_uncertainty_fraction': self.length_uncertainty_fraction,
      'checks': {
        'p2_refinement_verified': self.p2_refinement_verified,
        'resolution_order_verified': self.resolution_order_verified,
        'case_bindings_verified': self.case_bindings_verified,
        'coupled_fields_verified': self.coupled_fields_verified,
        'physical_field_handoffs_verified': (
          self.physical_field_handoffs_verified
        ),
        'first_cell_fits_verified': self.first_cell_fits_verified,
        'measurements_verified': self.measurements_verified,
        'solver_owned_length_verified': self.solver_owned_length_verified,
        'lengths_finite_verified': self.lengths_finite_verified,
        'length_resolution_sequence_verified': (
          self.length_resolution_sequence_verified
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'continued_chain_fits_verified': self.continued_chain_fits_verified,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'continued_chain_status': self.continued_chain_status,
      'physical_length_accepted': False,
      'external_validation_verified': False,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'cases': tuple(case.as_report() for case in self.cases),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus,
  message: str,
  *,
  cases: Sequence[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase
  ] = (),
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement:
  return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement(
    status=status,
    cases=tuple(cases),
    resolutions=tuple(case.resolution for case in cases),
    source_closure_fingerprints=tuple(
      moc_reflected_domain_global_physical_closure_fingerprint(
        case.source_closure
      )
      for case in cases
    ),
    coupled_field_fingerprints=tuple(
      _coupled_field_fingerprint(case.coupled_field) for case in cases
    ),
    axial_lengths_m=tuple(
      case.measurement.axial_length_m for case in cases
    ),
    axial_length_deltas_m=tuple(
      None
      if cases[index].measurement.axial_length_m is None
      or cases[index + 1].measurement.axial_length_m is None
      else abs(
        float(cases[index + 1].measurement.axial_length_m)
        - float(cases[index].measurement.axial_length_m)
      )
      for index in range(max(0, len(cases) - 1))
    ),
    message=message,
  )
####


def measure_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_fit(
  cases: Sequence[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase
  ],
  *,
  length_tolerance_m: float = 1.0e-6,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement:
  """Independently audit first-cell fits bound to a P2.2c field ladder."""

  try:
    length_tolerance = float(length_tolerance_m)
  except (TypeError, ValueError):
    return _failure(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .INVALID_INPUT,
      'length_tolerance_m must be numeric',
    )
  ####
  if not isfinite(length_tolerance) or length_tolerance <= 0.0:
    return _failure(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .INVALID_INPUT,
      'length_tolerance_m must be finite and positive',
    )
  ####
  try:
    case_values = tuple(cases)
  except TypeError:
    return _failure(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .INVALID_INPUT,
      'cases must be an iterable of typed P3 shock-cell-fit cases',
    )
  ####
  if len(case_values) < 2:
    return _failure(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .P2_REFINEMENT_REQUIRED,
      'P3 first-cell fitting requires at least two P2.2c cases',
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase,
    )
    for case in case_values
  ):
    return _failure(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .INVALID_INPUT,
      'cases must contain typed P3 shock-cell-fit cases',
    )
  ####

  resolutions = tuple(case.resolution for case in case_values)
  resolution_order_verified = _resolution_ladder_verified(resolutions)
  p2_refinement_verified = bool(
    all(case.feedback_case.local_research_verified for case in case_values)
  )
  case_bindings_verified = bool(
    all(
      case.feedback_case.source_closure is case.source_closure
      and case.feedback_case.case_id == case.case_id
      and case.feedback_case.resolution == case.resolution
      for case in case_values
    )
  )
  coupled_fields_verified = bool(
    all(
      case.coupled_field is not None
      and case.coupled_field.coupled_euler_field_verified
      for case in case_values
    )
  )
  physical_field_handoffs_verified = bool(
    all(case.physical_field_handoff_verified for case in case_values)
  )
  first_cell_fits_verified = bool(
    all(case.fit is not None and case.fit.local_fit_verified for case in case_values)
  )
  measurements_verified = bool(
    all(case.measurement.converged for case in case_values)
  )
  solver_owned_length_verified = bool(
    all(case.fit_field_binding_verified for case in case_values)
  )
  lengths = tuple(case.measurement.axial_length_m for case in case_values)
  lengths_finite_verified = bool(
    all(
      value is not None and isfinite(float(value)) and float(value) > 0.0
      for value in lengths
    )
  )
  deltas = tuple(
    None
    if lengths[index] is None or lengths[index + 1] is None
    else abs(float(lengths[index + 1]) - float(lengths[index]))
    for index in range(len(lengths) - 1)
  )
  length_resolution_sequence_verified = bool(
    lengths_finite_verified
    and all(delta is not None and isfinite(float(delta)) for delta in deltas)
    and all(
      float(deltas[index]) <= float(deltas[index - 1]) + length_tolerance
      for index in range(1, len(deltas))
    )
  )
  length_uncertainty = (
    None
    if not lengths_finite_verified or not deltas
    else max(float(delta) for delta in deltas if delta is not None)
  )
  reference_length = (
    None
    if not lengths_finite_verified
    else max(float(length) for length in lengths if length is not None)
  )
  length_uncertainty_fraction = (
    None
    if length_uncertainty is None or reference_length is None
    else length_uncertainty / max(reference_length, 1.0e-12)
  )
  physical_closure_verified = bool(
    all(
      case.source_closure.physical_closure_verified
      and case.fit is not None
      and case.fit.closure is case.source_closure
      for case in case_values
    )
  )
  fidelity_isolation_verified = bool(
    all(
      case.fidelity_isolation_verified
      and case.feedback_case.run.production_claim_allowed is False
      and case.feedback_case.run.chain_promotion_blocked
      and (case.fit is None or not case.fit.production_claim_allowed)
      for case in case_values
    )
  )
  common = dict(
    cases=case_values,
    resolutions=resolutions,
    source_closure_fingerprints=tuple(
      moc_reflected_domain_global_physical_closure_fingerprint(
        case.source_closure
      )
      for case in case_values
    ),
    coupled_field_fingerprints=tuple(
      _coupled_field_fingerprint(case.coupled_field) for case in case_values
    ),
    axial_lengths_m=lengths,
    axial_length_deltas_m=deltas,
    length_uncertainty_m=length_uncertainty,
    length_uncertainty_fraction=length_uncertainty_fraction,
    p2_refinement_verified=p2_refinement_verified,
    resolution_order_verified=resolution_order_verified,
    case_bindings_verified=case_bindings_verified,
    coupled_fields_verified=coupled_fields_verified,
    physical_field_handoffs_verified=physical_field_handoffs_verified,
    first_cell_fits_verified=first_cell_fits_verified,
    measurements_verified=measurements_verified,
    solver_owned_length_verified=solver_owned_length_verified,
    lengths_finite_verified=lengths_finite_verified,
    length_resolution_sequence_verified=length_resolution_sequence_verified,
    physical_closure_verified=physical_closure_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
  )
  status_type = (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
  )
  if not p2_refinement_verified or not resolution_order_verified:
    status = status_type.P2_REFINEMENT_REQUIRED
    message = (
      'P3 fitting requires a converged fine P2.2c research ladder with strict '
      'source/resolution ordering; no lower-fidelity fit was attempted'
    )
  elif not case_bindings_verified or not coupled_fields_verified:
    status = status_type.FIELD_FAILURE
    message = (
      'one or more P2.2c cases did not retain the expected solver-owned '
      'coupled field or exact case lineage'
    )
  elif not physical_field_handoffs_verified:
    status = status_type.FIELD_FAILURE
    message = (
      'the coupled field did not retain and consume the exact source '
      'shock-front physical-field handoff'
    )
  elif not first_cell_fits_verified or not physical_closure_verified:
    status = status_type.FIT_FAILURE
    message = (
      'one or more solver-owned first-cell fits did not pass the local '
      'physical-closure and fit gates'
    )
  elif not measurements_verified or not solver_owned_length_verified:
    status = status_type.MEASUREMENT_FAILURE
    message = (
      'the independent first-cell geometry measurement did not remain bound '
      'to each solver-owned physical field'
    )
  elif not lengths_finite_verified or not length_resolution_sequence_verified:
    status = status_type.LENGTH_STABILITY_FAILURE
    message = (
      'solver-owned first-cell lengths were measured but did not form the '
      'declared non-increasing resolution-difference sequence'
    )
  elif not fidelity_isolation_verified:
    status = status_type.FIT_FAILURE
    message = 'P3 fitting weakened its research-only promotion boundary'
  else:
    status = status_type.CONVERGED_RESEARCH_FIRST_CELL_FIT
    message = (
      'solver-owned first-cell fits were independently measured through the '
      'accepted local P2.2c field ladder; the reported length uncertainty is '
      'resolution-derived only, and continued-chain/external gates remain open'
    )
  ####
  return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement(
    status=status,
    claim_status=(
      'global-coupled-first-cell-fit; local-research-only; '
      'resolution-uncertainty-not-physical-acceptance'
    ),
    message=message,
    **common,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun:
  """P3 first-cell execution record with the upstream P2.2c run retained."""

  refinement_run: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun
  )
  cases: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase, ...
  ]
  measurement: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitMeasurement
  )
  start_x_m: float
  end_x_m: float | None
  configuration: tuple[tuple[str, Any], ...]
  configuration_fingerprint: str
  upstream_refinement_verified: bool = False
  field_binding_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.refinement_run,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun,
    ):
      raise TypeError('refinement_run must be a typed P2.2c refinement run')
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed P3 shock-cell-fit cases')
    ####
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact P3 fit cases')
    ####
    start = float(self.start_x_m)
    if not isfinite(start):
      raise ValueError('start_x_m must be finite')
    ####
    end = None if self.end_x_m is None else float(self.end_x_m)
    if end is not None and (not isfinite(end) or end <= start):
      raise ValueError('end_x_m must be finite and greater than start_x_m')
    ####
    if len(str(self.configuration_fingerprint)) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    for name in (
      'upstream_refinement_verified',
      'field_binding_verified',
      'fidelity_isolation_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.measurement.production_claim_allowed:
      raise ValueError('P3 first-cell fitting cannot claim production validity')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'start_x_m', start)
    object.__setattr__(self, 'end_x_m', end)
    object.__setattr__(self, 'configuration', tuple(self.configuration))
    object.__setattr__(self, 'configuration_fingerprint', str(self.configuration_fingerprint))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.local_consistency_verified
      and self.upstream_refinement_verified
      and self.field_binding_verified
      and self.fidelity_isolation_verified
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
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'start_x_m': self.start_x_m,
      'end_x_m': self.end_x_m,
      'upstream_refinement_verified': self.upstream_refinement_verified,
      'field_binding_verified': self.field_binding_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': dict(self.configuration),
      'configuration_fingerprint': self.configuration_fingerprint,
      'measurement': self.measurement.as_report(),
      'cases': tuple(case.as_report() for case in self.cases),
      'upstream_refinement': self.refinement_run.as_report(),
      'continued_chain_status': self.measurement.continued_chain_status,
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_fit(
  refinement_run: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun
  ),
  *,
  start_x_m: float,
  end_x_m: float | None = None,
  end_margin_m: float = 0.05,
  cell_index: int = 1,
  length_tolerance_m: float = 1.0e-6,
  position_tolerance_m: float = 1.0e-8,
  measurement_position_tolerance_m: float = 1.0e-10,
  measurement_axis_tolerance_m: float = 1.0e-10,
  measurement_area_tolerance_m2: float = 1.0e-9,
  measurement_mesh_vertex_tolerance_m: float = 1.0e-12,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun:
  """Fit first cells only from the final fields retained by P2.2c."""

  if not isinstance(
    refinement_run,
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun,
  ):
    raise TypeError('refinement_run must be a typed P2.2c refinement run')
  ####
  try:
    start = float(start_x_m)
    margin = float(end_margin_m)
  except (TypeError, ValueError) as error:
    raise ValueError('start_x_m and end_margin_m must be numeric') from error
  ####
  if not isfinite(start):
    raise ValueError('start_x_m must be finite')
  ####
  if not isfinite(margin) or margin < 0.0:
    raise ValueError('end_margin_m must be finite and nonnegative')
  ####
  if isinstance(cell_index, bool) or not isinstance(cell_index, int) or cell_index < 1:
    raise ValueError('cell_index must be a positive integer')
  ####
  resolved_end = None if end_x_m is None else float(end_x_m)
  if resolved_end is not None and (not isfinite(resolved_end) or resolved_end <= start):
    raise ValueError('end_x_m must be finite and greater than start_x_m')
  ####
  configuration_payload: dict[str, Any] = {
    'operator_id': (
      MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_SHOCK_CELL_FIT_RUN_OPERATOR_ID
    ),
    'upstream_configuration_fingerprint': (
      refinement_run.configuration_fingerprint
    ),
    'case_ids': tuple(case.case_id for case in refinement_run.cases),
    'resolutions': tuple(case.resolution for case in refinement_run.cases),
    'start_x_m': start,
    'end_x_m': resolved_end,
    'end_margin_m': margin,
    'cell_index': cell_index,
    'length_tolerance_m': length_tolerance_m,
    'position_tolerance_m': position_tolerance_m,
    'measurement_position_tolerance_m': measurement_position_tolerance_m,
    'measurement_axis_tolerance_m': measurement_axis_tolerance_m,
    'measurement_area_tolerance_m2': measurement_area_tolerance_m2,
    'measurement_mesh_vertex_tolerance_m': measurement_mesh_vertex_tolerance_m,
    'continued_chain_policy': 'not-attempted; requires separate carried-chain field',
  }
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = _payload_fingerprint(configuration_payload)
  upstream_verified = refinement_run.converged
  if not upstream_verified:
    measurement = _failure(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
      .P2_REFINEMENT_REQUIRED,
      'P3 fitting requires a converged fine P2.2c refinement run; no fit was attempted',
    )
    return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun(
      refinement_run=refinement_run,
      cases=(),
      measurement=measurement,
      start_x_m=start,
      end_x_m=resolved_end,
      configuration=configuration,
      configuration_fingerprint=configuration_fingerprint,
      upstream_refinement_verified=False,
      field_binding_verified=False,
      fidelity_isolation_verified=True,
      message=measurement.message,
    )
  ####

  p2_cases = tuple(refinement_run.cases)
  extracted: list[
    tuple[
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
      MocPhysicalPostShockFieldResult,
    ]
  ] = []
  for p2_case in p2_cases:
    coupled_field = _final_coupled_field(p2_case)
    handoff_verified, physical_field = _physical_field_handoff_verified(
      p2_case.source_closure,
      coupled_field,
    )
    if coupled_field is None or physical_field is None or not handoff_verified:
      measurement = _failure(
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitStatus
        .FIELD_FAILURE,
        'P2.2c case did not retain an exact consumed physical-field handoff; no fit was attempted',
      )
      return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun(
        refinement_run=refinement_run,
        cases=(),
        measurement=measurement,
        start_x_m=start,
        end_x_m=resolved_end,
        configuration=configuration,
        configuration_fingerprint=configuration_fingerprint,
        upstream_refinement_verified=True,
        field_binding_verified=False,
        fidelity_isolation_verified=True,
        message=measurement.message,
      )
    ####
    extracted.append((p2_case, coupled_field, physical_field))
  ####

  if resolved_end is None:
    resolved_end = max(
      field.ambient_boundary_points_m[-1][0]
      for _case, _coupled_field, field in extracted
    ) + margin
  ####
  if not isfinite(resolved_end) or resolved_end <= start:
    raise ValueError('resolved end_x_m must be finite and greater than start_x_m')
  ####
  fit_cases: list[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase
  ] = []
  for p2_case, coupled_field, physical_field in extracted:
    fit = fit_reflected_domain_production_shock_cell(
      p2_case.source_closure,
      start_x_m=start,
      end_x_m=resolved_end,
      cell_index=cell_index,
      incoming_frontier=p2_case.source_closure.incoming_handoff,
      position_tolerance_m=position_tolerance_m,
    )
    fit_measurement = measure_moc_production_shock_cell_fit(
      fit,
      position_tolerance_m=measurement_position_tolerance_m,
      axis_tolerance_m=measurement_axis_tolerance_m,
      area_tolerance_m2=measurement_area_tolerance_m2,
      mesh_vertex_tolerance_m=measurement_mesh_vertex_tolerance_m,
    )
    fit_field_binding_verified = bool(
      fit.candidate_field is physical_field
      and fit.closure is p2_case.source_closure
      and tuple(fit.fitted_shock_points_m)
      == tuple(physical_field.shock_boundary_points_m)
    )
    fidelity_isolation_verified = bool(
      p2_case.run.chain_promotion_blocked
      and not p2_case.run.production_claim_allowed
      and coupled_field.chain_promotion_blocked
      and not coupled_field.production_claim_allowed
      and fit.chain_promotion_blocked
      and not fit.production_claim_allowed
    )
    fit_cases.append(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitCase(
        case_id=p2_case.case_id,
        regime=p2_case.regime,
        resolution=p2_case.resolution,
        source_closure=p2_case.source_closure,
        feedback_case=p2_case,
        coupled_field=coupled_field,
        physical_field=physical_field,
        fit=fit,
        measurement=fit_measurement,
        coupled_field_lineage_verified=bool(
          p2_case.run.source_closure is p2_case.source_closure
          and p2_case.run.converged
          and p2_case.run.fidelity_isolation_verified
        ),
        physical_field_handoff_verified=True,
        fit_field_binding_verified=fit_field_binding_verified,
        fidelity_isolation_verified=fidelity_isolation_verified,
        message=fit.message,
      )
    )
  ####
  retained_cases = tuple(fit_cases)
  measurement = (
    measure_reflected_domain_global_coupled_boundary_condition_feedback_shock_cell_fit(
      retained_cases,
      length_tolerance_m=length_tolerance_m,
    )
  )
  field_binding_verified = bool(
    measurement.coupled_fields_verified
    and measurement.physical_field_handoffs_verified
    and measurement.solver_owned_length_verified
  )
  fidelity_isolation_verified = bool(
    measurement.fidelity_isolation_verified
    and all(case.fit is not None and case.fit.chain_promotion_blocked for case in retained_cases)
  )
  configuration_payload['end_x_m'] = resolved_end
  configuration = tuple(
    (name, configuration_payload[name])
    for name in sorted(configuration_payload)
  )
  configuration_fingerprint = _payload_fingerprint(configuration_payload)
  return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackShockCellFitRun(
    refinement_run=refinement_run,
    cases=retained_cases,
    measurement=measurement,
    start_x_m=start,
    end_x_m=resolved_end,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    upstream_refinement_verified=True,
    field_binding_verified=field_binding_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=measurement.message,
  )
####
