"""Cross-case refinement evidence for bounded global boundary feedback.

The bounded boundary-feedback operator proves that one exact source closure can
consume a solver-owned ambient frame extension.  It does not prove that the
handoff is stable when the source closure and downstream mesh are refined.
This module runs that operator over disjoint source closures and an increasing
mesh/frame ladder, then retains independent stability and conservative-flux
gates.  It deliberately cannot promote a canonical mixed-regime closure or a
production shock-cell result.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  build_reflected_domain_global_solver_owned_physical_field_handoff,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_coupled_boundary_condition_feedback import (
  MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  run_reflected_domain_global_coupled_boundary_condition_feedback,
)
from exhaust_plume.validation.moc_conservative_boundary_flux_audit import (
  MocReflectedDomainCoupledEulerBoundaryFluxAudit,
  measure_reflected_domain_coupled_euler_boundary_fluxes,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_CROSS_CASE_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackCrossCase',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementMeasurement',
  'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun',
  'run_reflected_domain_global_coupled_boundary_condition_feedback_cross_case_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_CROSS_CASE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-cross-case-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-boundary-condition-feedback-refinement-run'
)

_GEOMETRY_POLICY = 'solver-owned-global-march-no-target-geometry-injection-v1'
_FORBIDDEN_PROFILE_KEYS = frozenset(
  {
    'boundary_geometry_profile',
    'boundary_pressure_profile',
    'free_boundary_geometry_profile_y_m',
    'free_boundary_pressure_profile_Pa',
    'free_boundary_pressure_profile_x_stations_m',
    'physical_field_continuation_profile',
    'physical_field_shock_front_condition',
  }
)
_MESH_KEYS = frozenset(
  {'axial_station_count', 'axial_cell_count', 'transverse_cell_count'}
)


class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus(
  str, Enum
):
  """Typed result for disjoint boundary-feedback refinement evidence."""

  CONVERGED_RESEARCH_CROSS_CASE = (
    'converged-research-global-coupled-boundary-condition-feedback-cross-case'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = (
    'global-coupled-boundary-condition-feedback-source-closure-failure'
  )
  FEEDBACK_FAILURE = (
    'global-coupled-boundary-condition-feedback-refinement-feedback-failure'
  )
  RESOLUTION_FAILURE = (
    'global-coupled-boundary-condition-feedback-refinement-resolution-failure'
  )
  STABILITY_FAILURE = (
    'global-coupled-boundary-condition-feedback-refinement-stability-failure'
  )
  BOUNDARY_FLUX_EVIDENCE_REQUIRED = (
    'global-coupled-boundary-condition-feedback-refinement-boundary-flux-evidence-required'
  )
  FIDELITY_FAILURE = (
    'global-coupled-boundary-condition-feedback-refinement-fidelity-failure'
  )
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


def _resolution(value: Sequence[int]) -> tuple[int, int, int]:
  resolved = tuple(value)
  if len(resolved) != 3 or any(
    isinstance(item, bool) or not isinstance(item, int) for item in resolved
  ):
    raise ValueError(
      'resolution must contain axial stations, axial cells, and transverse '
      'cells as integers'
    )
  ####
  if resolved[0] < 4 or resolved[1] < 4 or resolved[2] < 3:
    raise ValueError(
      'resolution must contain axial stations >= 4, axial cells >= 4, and '
      'transverse cells >= 3'
    )
  ####
  return resolved
####


def _finite_values(values: Sequence[float]) -> bool:
  return all(isfinite(float(value)) for value in values)
####


def _maximum_absolute(values: Sequence[float]) -> float:
  return max((abs(float(value)) for value in values), default=0.0)
####


def _relative_change(first: float, second: float, floor: float) -> float:
  scale = max(abs(float(first)), abs(float(second)), float(floor))
  return abs(float(second) - float(first)) / scale
####


def _initial_frame_extension_m(iteration: Any) -> float:
  extension = iteration.frame_extension
  if extension is None:
    return 0.0
  ####
  negotiation = extension.request.frame_negotiation
  return float(negotiation.maximum_required_extension_m)
####


def _response_signature(
  run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
) -> tuple[float, float, float, float, float]:
  """Return bounded response magnitudes plus the initial frame demand."""

  coordinate = 0.0
  tangent = 0.0
  pressure = 0.0
  normal_velocity = 0.0
  frame_extension = 0.0
  for iteration in run.iterations:
    proposal = iteration.proposal
    if proposal is not None:
      coordinate = max(
        coordinate,
        _maximum_absolute(proposal.coordinate_corrections_m),
      )
      tangent = max(
        tangent,
        _maximum_absolute(proposal.tangent_corrections_rad),
      )
      pressure = max(
        pressure,
        _maximum_absolute(proposal.pressure_corrections_Pa),
      )
      normal_velocity = max(
        normal_velocity,
        _maximum_absolute(proposal.normal_velocity_values_m_s),
      )
    ####
    frame_extension = max(frame_extension, _initial_frame_extension_m(iteration))
  ####
  return (coordinate, tangent, pressure, normal_velocity, frame_extension)
####


def _response_channels_finite(
  run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
) -> bool:
  if not run.iterations:
    return False
  ####
  for iteration in run.iterations:
    proposal = iteration.proposal
    if proposal is None:
      return False
    ####
    channels = (
      proposal.coordinate_corrections_m,
      proposal.tangent_corrections_rad,
      proposal.pressure_corrections_Pa,
      proposal.normal_velocity_values_m_s,
    )
    if any(not values or not _finite_values(values) for values in channels):
      return False
    ####
    boundary_condition = iteration.boundary_condition
    if boundary_condition is None:
      return False
    ####
    if any(
      not _finite_values(values)
      for values in (
        boundary_condition.coordinate_residuals_m,
        boundary_condition.tangent_residuals_rad,
        boundary_condition.pressure_residuals_Pa,
      )
    ):
      return False
    ####
  ####
  return True
####


def _geometry_profile_injection_blocked(
  run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
  downstream_options: Mapping[str, Any],
) -> bool:
  if any(key in downstream_options for key in _FORBIDDEN_PROFILE_KEYS):
    return False
  ####
  if not run.iterations:
    return False
  ####
  for iteration in run.iterations:
    boundary_condition = iteration.boundary_condition
    negotiation = iteration.frame_negotiation
    extension = iteration.frame_extension
    if boundary_condition is None or negotiation is None:
      return False
    ####
    if boundary_condition.configuration.get('geometry_policy') != _GEOMETRY_POLICY:
      return False
    ####
    if not negotiation.geometry_injection_blocked:
      return False
    ####
    if extension is not None and not extension.geometry_injection_blocked:
      return False
    ####
  ####
  return True
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackCrossCase:
  """One disjoint source closure and one increasing mesh/frame resolution."""

  case_id: str
  regime: str
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolution: tuple[int, int, int]
  downstream_options: Mapping[str, Any] = field(default_factory=dict)

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    regime = str(self.regime)
    if not case_id or not regime:
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
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'regime', regime)
    object.__setattr__(self, 'resolution', _resolution(self.resolution))
    if not isinstance(self.downstream_options, Mapping):
      raise TypeError('downstream_options must be a mapping')
    ####
    options = dict(self.downstream_options)
    if any(key in options for key in _FORBIDDEN_PROFILE_KEYS | _MESH_KEYS):
      raise ValueError(
        'cross-case refinement owns solver profiles and mesh resolution; '
        'caller-supplied profile or mesh overrides are not allowed'
      )
    ####
    object.__setattr__(self, 'downstream_options', options)
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'resolution': self.resolution,
      'downstream_options': dict(self.downstream_options),
      'source_closure_converged': self.source_closure.converged,
      'source_physical_closure_verified': (
        self.source_closure.physical_closure_verified
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase:
  """One fresh feedback run retained for independent aggregate auditing."""

  case_id: str
  regime: str
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  resolution: tuple[int, int, int]
  run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun
  response_signature: tuple[float, float, float, float, float]
  boundary_flux_audits: tuple[
    MocReflectedDomainCoupledEulerBoundaryFluxAudit, ...
  ] = ()
  source_lineage_verified: bool = False
  fresh_solver_invocations_verified: bool = False
  target_lineage_verified: bool = False
  frame_coverage_verified: bool = False
  residuals_finite: bool = False
  geometry_profile_injection_blocked: bool = False
  fidelity_isolation_verified: bool = False
  conservative_boundary_fluxes_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.run,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
    ):
      raise TypeError(
        'run must be a '
        'MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun'
      )
    ####
    resolution = _resolution(self.resolution)
    signature = tuple(float(value) for value in self.response_signature)
    if len(signature) != 5 or any(not isfinite(value) for value in signature):
      raise ValueError(
        'response_signature must contain five finite response magnitudes'
      )
    ####
    audits = tuple(self.boundary_flux_audits)
    if any(
      not isinstance(
        audit,
        MocReflectedDomainCoupledEulerBoundaryFluxAudit,
      )
      for audit in audits
    ):
      raise TypeError('boundary_flux_audits must contain typed flux audits')
    ####
    for name in (
      'source_lineage_verified',
      'fresh_solver_invocations_verified',
      'target_lineage_verified',
      'frame_coverage_verified',
      'residuals_finite',
      'geometry_profile_injection_blocked',
      'fidelity_isolation_verified',
      'conservative_boundary_fluxes_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'case_id', str(self.case_id))
    object.__setattr__(self, 'regime', str(self.regime))
    object.__setattr__(self, 'resolution', resolution)
    object.__setattr__(self, 'response_signature', signature)
    object.__setattr__(self, 'boundary_flux_audits', audits)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  @property
  def local_research_verified(self) -> bool:
    return bool(
      self.run.research_feedback_completed
      and self.source_lineage_verified
      and self.fresh_solver_invocations_verified
      and self.target_lineage_verified
      and self.frame_coverage_verified
      and self.residuals_finite
      and self.geometry_profile_injection_blocked
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'resolution': self.resolution,
      'response_signature': self.response_signature,
      'boundary_flux_audits': tuple(
        audit.as_report() for audit in self.boundary_flux_audits
      ),
      'local_research_verified': self.local_research_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'fresh_solver_invocations_verified': (
        self.fresh_solver_invocations_verified
      ),
      'target_lineage_verified': self.target_lineage_verified,
      'frame_coverage_verified': self.frame_coverage_verified,
      'residuals_finite': self.residuals_finite,
      'geometry_profile_injection_blocked': (
        self.geometry_profile_injection_blocked
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'conservative_boundary_fluxes_verified': (
        self.conservative_boundary_fluxes_verified
      ),
      'run': self.run.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementMeasurement:
  """Aggregate stability evidence over disjoint feedback cases."""

  status: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
  cases: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase, ...
  ] = ()
  case_ids: tuple[str, ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  resolution_order_verified: bool = False
  distinct_source_closures_verified: bool = False
  case_bindings_verified: bool = False
  fresh_solver_invocations_verified: bool = False
  target_lineage_verified: bool = False
  frame_coverage_verified: bool = False
  residuals_finite: bool = False
  geometry_profile_injection_blocked: bool = False
  fidelity_isolation_verified: bool = False
  response_stability_verified: bool = False
  frame_extension_stability_verified: bool = False
  conservative_boundary_fluxes_verified: bool = False
  maximum_relative_response_change: float | None = None
  maximum_relative_frame_extension_change: float | None = None
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_CROSS_CASE_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus,
    ):
      raise TypeError('status must be a typed feedback-refinement status')
    ####
    cases = tuple(self.cases)
    ids = tuple(str(value) for value in self.case_ids)
    fingerprints = tuple(str(value) for value in self.source_closure_fingerprints)
    if len(ids) != len(cases) or len(fingerprints) != len(cases):
      raise ValueError('case IDs, fingerprints, and cases must align')
    ####
    if len(set(ids)) != len(ids):
      raise ValueError('case IDs must be unique')
    ####
    if len(set(fingerprints)) != len(fingerprints):
      raise ValueError('source closure fingerprints must be distinct')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed feedback-refinement cases')
    ####
    for name in (
      'resolution_order_verified',
      'distinct_source_closures_verified',
      'case_bindings_verified',
      'fresh_solver_invocations_verified',
      'target_lineage_verified',
      'frame_coverage_verified',
      'residuals_finite',
      'geometry_profile_injection_blocked',
      'fidelity_isolation_verified',
      'response_stability_verified',
      'frame_extension_stability_verified',
      'conservative_boundary_fluxes_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in (
      'maximum_relative_response_change',
      'maximum_relative_frame_extension_change',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError('feedback refinement cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('feedback refinement must remain promotion-blocked')
    ####
    if not self.external_validation_required:
      raise ValueError('feedback refinement must retain external validation')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'case_ids', ids)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      and len(self.cases) >= 2
      and self.resolution_order_verified
      and self.distinct_source_closures_verified
      and self.case_bindings_verified
      and self.fresh_solver_invocations_verified
      and self.target_lineage_verified
      and self.frame_coverage_verified
      and self.residuals_finite
      and self.geometry_profile_injection_blocked
      and self.fidelity_isolation_verified
      and self.response_stability_verified
      and self.frame_extension_stability_verified
      and self.conservative_boundary_fluxes_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and all(case.local_research_verified for case in self.cases)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'distinct_source_closures_verified': (
          self.distinct_source_closures_verified
        ),
        'case_bindings_verified': self.case_bindings_verified,
        'fresh_solver_invocations_verified': (
          self.fresh_solver_invocations_verified
        ),
        'target_lineage_verified': self.target_lineage_verified,
        'frame_coverage_verified': self.frame_coverage_verified,
        'residuals_finite': self.residuals_finite,
        'geometry_profile_injection_blocked': (
          self.geometry_profile_injection_blocked
        ),
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'response_stability_verified': self.response_stability_verified,
        'frame_extension_stability_verified': (
          self.frame_extension_stability_verified
        ),
        'conservative_boundary_fluxes_verified': (
          self.conservative_boundary_fluxes_verified
        ),
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'maximum_relative_response_change': self.maximum_relative_response_change,
      'maximum_relative_frame_extension_change': (
        self.maximum_relative_frame_extension_change
      ),
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'cases': tuple(case.as_report() for case in self.cases),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun:
  """Execution record for disjoint feedback refinement."""

  requested_cases: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackCrossCase, ...
  ]
  cases: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase, ...
  ]
  measurement: (
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementMeasurement
  )
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    requested = tuple(self.requested_cases)
    cases = tuple(self.cases)
    if len(requested) != len(cases):
      raise ValueError('requested_cases and cases must align')
    ####
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact refinement cases')
    ####
    if len(str(self.configuration_fingerprint)) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    if self.measurement.production_claim_allowed:
      raise ValueError('feedback refinement cannot claim production validity')
    ####
    object.__setattr__(self, 'requested_cases', requested)
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'configuration_fingerprint', str(self.configuration_fingerprint))
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
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_BOUNDARY_CONDITION_FEEDBACK_REFINEMENT_RUN_OPERATOR_ID,
      'converged': self.converged,
      'requested_cases': tuple(case.as_report() for case in self.requested_cases),
      'cases': tuple(case.as_report() for case in self.cases),
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def _adjacent_stability(
  cases: Sequence[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase
  ],
  *,
  response_stability_fraction: float,
) -> tuple[bool, bool, float | None, float | None]:
  if len(cases) < 2:
    return False, False, None, None
  ####
  maximum_response: float | None = None
  maximum_frame: float | None = None
  response_stable = True
  frame_stable = True
  floors = (1.0e-6, 1.0e-3, 1.0e2, 1.0, 1.0e-4)
  for first, second in zip(cases, cases[1:]):
    changes = tuple(
      _relative_change(left, right, floor)
      for left, right, floor in zip(
        first.response_signature,
        second.response_signature,
        floors,
        strict=True,
      )
    )
    response_change = max(changes[:4], default=float('inf'))
    frame_change = changes[4]
    maximum_response = (
      response_change
      if maximum_response is None
      else max(maximum_response, response_change)
    )
    maximum_frame = (
      frame_change
      if maximum_frame is None
      else max(maximum_frame, frame_change)
    )
    response_stable = response_stable and response_change <= response_stability_fraction
    frame_stable = frame_stable and frame_change <= response_stability_fraction
  ####
  return response_stable, frame_stable, maximum_response, maximum_frame
####


def _boundary_flux_audits(
  run: MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRun,
) -> tuple[MocReflectedDomainCoupledEulerBoundaryFluxAudit, ...]:
  """Audit the final retained coupled field for every outer feedback step."""

  audits: list[MocReflectedDomainCoupledEulerBoundaryFluxAudit] = []
  for iteration in run.iterations:
    downstream = iteration.downstream_feedback
    if downstream is None or not downstream.iterations:
      return ()
    ####
    candidate = downstream.iterations[-1].result.coupled_field
    if candidate is None:
      return ()
    ####
    try:
      audits.append(measure_reflected_domain_coupled_euler_boundary_fluxes(candidate))
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      return ()
    ####
  ####
  return tuple(audits)
####


def _measurement(
  cases: tuple[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase, ...
  ],
  *,
  response_stability_fraction: float,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementMeasurement:
  case_ids = tuple(case.case_id for case in cases)
  fingerprints = tuple(case.source_closure_fingerprint for case in cases)
  resolutions = tuple(case.resolution for case in cases)
  resolution_order = bool(
    len(resolutions) >= 2
    and all(
      all(right[index] > left[index] for index in range(3))
      for left, right in zip(resolutions, resolutions[1:])
    )
  )
  distinct = bool(len(fingerprints) >= 2 and len(set(fingerprints)) == len(fingerprints))
  bindings = bool(
    len(case_ids) == len(cases)
    and len(set(case_ids)) == len(case_ids)
    and all(case.run.source_closure is case.source_closure for case in cases)
  )
  fresh = bool(
    cases and all(case.fresh_solver_invocations_verified for case in cases)
  )
  lineage = bool(cases and all(case.target_lineage_verified for case in cases))
  frame = bool(cases and all(case.frame_coverage_verified for case in cases))
  residuals = bool(cases and all(case.residuals_finite for case in cases))
  geometry = bool(
    cases and all(case.geometry_profile_injection_blocked for case in cases)
  )
  fidelity = bool(cases and all(case.fidelity_isolation_verified for case in cases))
  response_stable, frame_stable, maximum_response, maximum_frame = (
    _adjacent_stability(
      cases,
      response_stability_fraction=response_stability_fraction,
    )
  )
  fluxes = bool(
    cases and all(case.conservative_boundary_fluxes_verified for case in cases)
  )
  local = bool(
    resolution_order
    and distinct
    and bindings
    and fresh
    and lineage
    and frame
    and residuals
    and geometry
    and fidelity
    and response_stable
    and frame_stable
    and fluxes
    and all(case.local_research_verified for case in cases)
  )
  if local:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
    )
    message = (
      'disjoint solver-owned boundary feedback passed local refinement and '
      'conservative boundary-flux evidence gates; canonical closure and '
      'external validation remain open'
    )
  elif not resolution_order or not distinct or not bindings:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .RESOLUTION_FAILURE
    )
    message = (
      'cross-case source identities or mesh/frame resolutions are not a '
      'strict disjoint ladder'
    )
  elif not all(case.local_research_verified for case in cases):
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .FEEDBACK_FAILURE
    )
    message = (
      'one or more fresh boundary-feedback cases did not complete every '
      'research-only solver gate'
    )
  elif not response_stable or not frame_stable:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .STABILITY_FAILURE
    )
    message = (
      'the bounded response or solver-observed frame demand changed beyond '
      f'the declared {response_stability_fraction:.3g} relative stability '
      'fraction; no refinement promotion was attempted'
    )
  elif not fluxes:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .BOUNDARY_FLUX_EVIDENCE_REQUIRED
    )
    message = (
      'cell Euler evidence is present, but an explicit conservative boundary '
      'flux audit from retained states is still required'
    )
  else:
    status = (
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementStatus
      .FIDELITY_FAILURE
    )
    message = (
      'feedback refinement did not pass every lineage, residual, geometry, '
      'or fidelity-isolation gate'
    )
  ####
  return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementMeasurement(
    status=status,
    cases=cases,
    case_ids=case_ids,
    source_closure_fingerprints=fingerprints,
    resolution_order_verified=resolution_order,
    distinct_source_closures_verified=distinct,
    case_bindings_verified=bindings,
    fresh_solver_invocations_verified=fresh,
    target_lineage_verified=lineage,
    frame_coverage_verified=frame,
    residuals_finite=residuals,
    geometry_profile_injection_blocked=geometry,
    fidelity_isolation_verified=fidelity,
    response_stability_verified=response_stable,
    frame_extension_stability_verified=frame_stable,
    conservative_boundary_fluxes_verified=fluxes,
    maximum_relative_response_change=maximum_response,
    maximum_relative_frame_extension_change=maximum_frame,
    message=message,
  )
####


def run_reflected_domain_global_coupled_boundary_condition_feedback_cross_case_refinement(
  cases: Sequence[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackCrossCase
  ],
  *,
  reference_total_temperature_K: float,
  maximum_iterations: int = 1,
  downstream_feedback_iterations: int = 2,
  maximum_frame_extension_m: float = 0.5,
  response_stability_fraction: float = 0.75,
) -> MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun:
  """Fresh-solve a disjoint source/mesh ladder through boundary feedback."""

  requested_cases = tuple(cases)
  if len(requested_cases) < 2:
    raise ValueError('cases must contain at least two disjoint source cases')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackCrossCase,
    )
    for case in requested_cases
  ):
    raise TypeError('cases must contain typed cross-case refinement inputs')
  ####
  if len({case.case_id for case in requested_cases}) != len(requested_cases):
    raise ValueError('cases must have unique case IDs')
  ####
  fingerprints = tuple(case.source_closure_fingerprint for case in requested_cases)
  if len(set(fingerprints)) != len(fingerprints):
    raise ValueError('cases must retain distinct source closure fingerprints')
  ####
  resolutions = tuple(case.resolution for case in requested_cases)
  if any(
    not all(right[index] > left[index] for index in range(3))
    for left, right in zip(resolutions, resolutions[1:])
  ):
    raise ValueError('cases must use strictly increasing mesh/frame resolutions')
  ####
  stability_fraction = float(response_stability_fraction)
  if not isfinite(stability_fraction) or stability_fraction <= 0.0:
    raise ValueError('response_stability_fraction must be finite and positive')
  ####
  configuration: dict[str, Any] = {
    'case_ids': tuple(case.case_id for case in requested_cases),
    'source_closure_fingerprints': fingerprints,
    'resolutions': resolutions,
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'maximum_iterations': int(maximum_iterations),
    'downstream_feedback_iterations': int(downstream_feedback_iterations),
    'maximum_frame_extension_m': float(maximum_frame_extension_m),
    'response_stability_fraction': stability_fraction,
    'profile_policy': _GEOMETRY_POLICY,
    'boundary_flux_policy': 'explicit-retained-state-audit-required-v1',
  }
  retained: list[
    MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase
  ] = []
  for requested in requested_cases:
    handoff = build_reflected_domain_global_solver_owned_physical_field_handoff(
      requested.source_closure
    )
    options = dict(requested.downstream_options)
    options.update({
      'axial_station_count': requested.resolution[0],
      'axial_cell_count': requested.resolution[1],
      'transverse_cell_count': requested.resolution[2],
      'inlet_boundary_mode': (
        MocReflectedDomainCoupledEulerInletBoundaryMode
        .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
      ),
      'physical_field_continuation_profile': handoff.continuation_profile,
      'physical_field_shock_front_condition': handoff.shock_front_condition,
    })
    feedback = run_reflected_domain_global_coupled_boundary_condition_feedback(
      requested.source_closure,
      reference_total_temperature_K=reference_total_temperature_K,
      maximum_iterations=maximum_iterations,
      downstream_feedback_iterations=downstream_feedback_iterations,
      consumer_id=(
        'moc-global-coupled-boundary-condition-feedback-refinement:'
        f'{requested.case_id}'
      ),
      downstream_options=options,
      maximum_frame_extension_m=maximum_frame_extension_m,
    )
    source_lineage = bool(
      feedback.source_closure is requested.source_closure
      and feedback.source_lineage_verified
      and feedback.configuration.get('source_closure_fingerprint')
      == requested.source_closure_fingerprint
    )
    target_lineage = bool(
      feedback.target_lineage_verified
      and feedback.frame_negotiation_verified
      and feedback.frame_extension_verified
    )
    frame_coverage = bool(
      feedback.frame_coverage_verified
      and feedback.target_coverage_verified
    )
    boundary_flux_audits = _boundary_flux_audits(feedback)
    conservative_boundary_fluxes_verified = bool(
      boundary_flux_audits
      and all(audit.converged for audit in boundary_flux_audits)
    )
    retained.append(
      MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementCase(
        case_id=requested.case_id,
        regime=requested.regime,
        source_closure=requested.source_closure,
        resolution=requested.resolution,
        run=feedback,
        response_signature=_response_signature(feedback),
        boundary_flux_audits=boundary_flux_audits,
        source_lineage_verified=source_lineage,
        fresh_solver_invocations_verified=bool(
          feedback.fresh_global_solve_attempted
          and feedback.fresh_global_solve_verified
        ),
        target_lineage_verified=target_lineage,
        frame_coverage_verified=frame_coverage,
        residuals_finite=_response_channels_finite(feedback),
        geometry_profile_injection_blocked=_geometry_profile_injection_blocked(
          feedback,
          # ``options`` contains the exact solver-owned handoff profiles
          # installed above.  Check only the caller-owned options here so
          # those generated profiles are not mistaken for injection.
          requested.downstream_options,
        ),
        fidelity_isolation_verified=feedback.fidelity_isolation_verified,
        conservative_boundary_fluxes_verified=(
          conservative_boundary_fluxes_verified
        ),
        message=feedback.message,
      )
    )
  ####
  retained_cases = tuple(retained)
  measurement = _measurement(
    retained_cases,
    response_stability_fraction=stability_fraction,
  )
  fidelity = bool(
    retained_cases and all(case.fidelity_isolation_verified for case in retained_cases)
  )
  fresh = bool(
    retained_cases
    and all(case.fresh_solver_invocations_verified for case in retained_cases)
  )
  return MocReflectedDomainGlobalCoupledBoundaryConditionFeedbackRefinementRun(
    requested_cases=requested_cases,
    cases=retained_cases,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    fresh_solver_invocation_verified=fresh,
    fidelity_isolation_verified=fidelity,
    message=measurement.message,
  )
####
