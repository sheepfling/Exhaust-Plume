"""Research-only downstream pressure-feedback iteration evidence.

The boundary-pressure consumer can now apply a measured downstream response to
another coupled solve.  This module makes that handoff repeatable across fresh
solver calls, records the exact profile lineage, and reports pressure-update
convergence separately from physical closure.  It never re-solves the upstream
global field and therefore cannot authorize a global-coupling or production
claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
  MocReflectedDomainGlobalCoupledDownstreamResult,
  MocReflectedDomainGlobalCoupledDownstreamStatus,
  build_reflected_domain_global_coupled_downstream_feedback_pressure_profile,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration',
  'MocReflectedDomainGlobalCoupledDownstreamFeedbackRun',
  'run_reflected_domain_global_coupled_downstream_feedback',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-feedback'
)


class MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus(str, Enum):
  """Outcome of a fresh downstream pressure-feedback iteration study."""

  CONVERGED_RESEARCH_PRESSURE_UPDATE = (
    'converged-research-global-coupled-downstream-pressure-update'
  )
  INVALID_INPUT = 'invalid_input'
  SOLVER_FAILURE = 'global-coupled-downstream-feedback-solver-failure'
  PROFILE_FAILURE = 'global-coupled-downstream-feedback-profile-failure'
  RESPONSE_FAILURE = 'global-coupled-downstream-feedback-response-failure'
  ITERATION_LIMIT = 'global-coupled-downstream-feedback-iteration-limit'
  FIDELITY_FAILURE = 'global-coupled-downstream-feedback-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration:
  """One fresh solve, independent response measure, and next profile."""

  iteration_index: int
  input_pressure_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  )
  result: MocReflectedDomainGlobalCoupledDownstreamResult
  solver_response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  next_pressure_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  ) = None
  maximum_pressure_update_Pa: float | None = None
  pressure_profile_lineage_verified: bool = False
  response_lineage_verified: bool = False
  pressure_profile_consumption_verified: bool = False

  def __post_init__(self) -> None:
    index = self.iteration_index
    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    if self.input_pressure_profile is not None and not isinstance(
      self.input_pressure_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
    ):
      raise TypeError(
        'input_pressure_profile must be a typed downstream pressure profile '
        'or None'
      )
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalCoupledDownstreamResult'
      )
    ####
    for name in ('solver_response', 'response'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
      ):
        raise TypeError(
          f'{name} must be a typed downstream boundary response or None'
        )
      ####
    ####
    if self.next_pressure_profile is not None and not isinstance(
      self.next_pressure_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
    ):
      raise TypeError(
        'next_pressure_profile must be a typed downstream pressure profile '
        'or None'
      )
    ####
    if self.maximum_pressure_update_Pa is not None:
      update = float(self.maximum_pressure_update_Pa)
      if not isfinite(update) or update < 0.0:
        raise ValueError(
          'maximum_pressure_update_Pa must be finite and nonnegative when '
          'supplied'
        )
      ####
      object.__setattr__(self, 'maximum_pressure_update_Pa', update)
    ####
    for name in (
      'pressure_profile_lineage_verified',
      'response_lineage_verified',
      'pressure_profile_consumption_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'iteration_index', index)
  ####

  @property
  def local_coupled_field_verified(self) -> bool:
    return bool(self.result.local_coupled_field_verified)
  ####

  @property
  def response_coverage_verified(self) -> bool:
    return bool(
      self.response is not None and self.response.overlap_coverage_verified
    )
  ####

  @property
  def response_residuals_verified(self) -> bool:
    return bool(self.response is not None and self.response.residuals_verified)
  ####

  @property
  def response_channels_finite(self) -> bool:
    response = self.response
    if response is None:
      return False
    ####
    return all(
      isfinite(value)
      for channel in (
        response.coordinate_residuals_m,
        response.tangent_residuals_rad,
        response.pressure_residuals_Pa,
        response.normal_velocity_residuals_m_s,
        response.coordinate_offsets_m,
        response.tangent_offsets_rad,
        response.pressure_offsets_Pa,
        response.normal_velocity_values_m_s,
      )
      for value in channel
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      not self.result.global_coupling_verified
      and not self.result.downstream_boundary_closure_verified
      and self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and (
        self.input_pressure_profile is None
        or not self.input_pressure_profile.production_claim_allowed
      )
      and (
        self.next_pressure_profile is None
        or not self.next_pressure_profile.production_claim_allowed
      )
      and (
        self.response is None or not self.response.production_claim_allowed
      )
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'input_pressure_profile': (
        None
        if self.input_pressure_profile is None
        else self.input_pressure_profile.as_report()
      ),
      'solver_status': self.result.status.value,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'pressure_profile_lineage_verified': self.pressure_profile_lineage_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'pressure_profile_consumption_verified': (
        self.pressure_profile_consumption_verified
      ),
      'response_coverage_verified': self.response_coverage_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'response_channels_finite': self.response_channels_finite,
      'maximum_pressure_update_Pa': self.maximum_pressure_update_Pa,
      'next_pressure_profile': (
        None
        if self.next_pressure_profile is None
        else self.next_pressure_profile.as_report()
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'result': self.result.as_report(),
      'solver_response': (
        None if self.solver_response is None else self.solver_response.as_report()
      ),
      'response': None if self.response is None else self.response.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamFeedbackRun:
  """Audited downstream pressure updates below the global-closure gate."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_iterations: int
  iterations: tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration, ...]
  status: MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
  pressure_update_tolerance_Pa: float
  pressure_correction_fraction: float
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  closure_lineage_verified: bool = False
  pressure_profile_lineage_verified: bool = False
  pressure_profile_alignment_verified: bool = False
  response_lineage_verified: bool = False
  response_channels_finite: bool = False
  response_coverage_verified: bool = False
  response_residuals_verified: bool = False
  local_coupled_field_verified: bool = False
  pressure_update_convergence_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    requested = self.requested_iterations
    if isinstance(requested, bool) or not isinstance(requested, int):
      raise TypeError('requested_iterations must be an integer')
    ####
    if requested < 2:
      raise ValueError('requested_iterations must be at least two')
    ####
    iterations = tuple(self.iterations)
    if any(
      not isinstance(
        item,
        MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration,
      )
      for item in iterations
    ):
      raise TypeError('iterations must contain typed feedback iterations')
    ####
    if len(iterations) > requested:
      raise ValueError('iterations cannot exceed requested_iterations')
    ####
    if tuple(item.iteration_index for item in iterations) != tuple(
      range(len(iterations))
    ):
      raise ValueError('iterations must have contiguous zero-based indices')
    ####
    tolerance = float(self.pressure_update_tolerance_Pa)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('pressure_update_tolerance_Pa must be finite and positive')
    ####
    fraction = float(self.pressure_correction_fraction)
    if not isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
      raise ValueError('pressure_correction_fraction must be in (0, 1]')
    ####
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus'
      )
    ####
    if len(self.configuration_fingerprint) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    for name in (
      'fresh_solver_invocation_verified',
      'closure_lineage_verified',
      'pressure_profile_lineage_verified',
      'pressure_profile_alignment_verified',
      'response_lineage_verified',
      'response_channels_finite',
      'response_coverage_verified',
      'response_residuals_verified',
      'local_coupled_field_verified',
      'pressure_update_convergence_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'downstream pressure feedback cannot claim global or boundary closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'downstream pressure feedback must retain its promotion block'
      )
    ####
    object.__setattr__(self, 'requested_iterations', requested)
    object.__setattr__(self, 'iterations', iterations)
    object.__setattr__(self, 'pressure_update_tolerance_Pa', tolerance)
    object.__setattr__(self, 'pressure_correction_fraction', fraction)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
      .CONVERGED_RESEARCH_PRESSURE_UPDATE
      and self.fresh_solver_invocation_verified
      and self.closure_lineage_verified
      and self.pressure_profile_lineage_verified
      and self.pressure_profile_alignment_verified
      and self.response_lineage_verified
      and self.response_channels_finite
      and self.response_coverage_verified
      and self.response_residuals_verified
      and self.local_coupled_field_verified
      and self.pressure_update_convergence_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def pressure_update_converged(self) -> bool:
    """Whether the relaxed pressure profile itself reached its tolerance."""

    return self.pressure_update_convergence_verified
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_FEEDBACK_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'requested_iterations': self.requested_iterations,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'closure_lineage_verified': self.closure_lineage_verified,
      'pressure_profile_lineage_verified': self.pressure_profile_lineage_verified,
      'pressure_profile_alignment_verified': self.pressure_profile_alignment_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'response_channels_finite': self.response_channels_finite,
      'response_coverage_verified': self.response_coverage_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'pressure_update_convergence_verified': (
        self.pressure_update_convergence_verified
      ),
      'pressure_update_tolerance_Pa': self.pressure_update_tolerance_Pa,
      'pressure_correction_fraction': self.pressure_correction_fraction,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'iterations': tuple(item.as_report() for item in self.iterations),
      'message': self.message,
    }
  ####
####


def _failed_result(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  message: str,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE,
    closure=closure,
    mixed_regime_request=None,
    coupled_request=None,
    coupled_field=None,
    coupled_field_audit=None,
    message=message,
  )
####


def _profiles_aligned(
  first: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  second: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  *,
  position_tolerance_m: float,
) -> bool:
  return bool(
    first.source_closure_fingerprint == second.source_closure_fingerprint
    and len(first.x_stations_m) == len(second.x_stations_m)
    and all(
      abs(left - right) <= position_tolerance_m
      for left, right in zip(first.x_stations_m, second.x_stations_m)
    )
  )
####


def _maximum_profile_update(
  first: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  second: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
) -> float:
  if len(first.pressure_Pa) != len(second.pressure_Pa):
    return float('inf')
  ####
  return max(
    (abs(left - right) for left, right in zip(first.pressure_Pa, second.pressure_Pa)),
    default=float('inf'),
  )
####


def _status_for_run(
  *,
  iterations: tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration, ...],
  fresh_solver_invocation_verified: bool,
  closure_lineage_verified: bool,
  pressure_profile_lineage_verified: bool,
  pressure_profile_alignment_verified: bool,
  response_lineage_verified: bool,
  response_channels_finite: bool,
  response_coverage_verified: bool,
  response_residuals_verified: bool,
  local_coupled_field_verified: bool,
  pressure_update_convergence_verified: bool,
  fidelity_isolation_verified: bool,
) -> tuple[MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus, str]:
  if not fresh_solver_invocation_verified or not local_coupled_field_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.SOLVER_FAILURE,
      'the feedback ladder did not retain a locally audited fresh coupled '
      'field for every attempted step',
    )
  ####
  if not fidelity_isolation_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.FIDELITY_FAILURE,
      'a feedback iteration changed the global or production claim ceiling',
    )
  ####
  if not (
    closure_lineage_verified
    and pressure_profile_lineage_verified
    and pressure_profile_alignment_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.PROFILE_FAILURE,
      'pressure-profile lineage or exact cell-center alignment was not '
      'verified across the feedback steps',
    )
  ####
  if not (
    response_lineage_verified
    and response_channels_finite
    and response_coverage_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.RESPONSE_FAILURE,
      'the independently measured downstream response is incomplete or '
      'cannot be tied to the solver-retained response',
    )
  ####
  if not pressure_update_convergence_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.ITERATION_LIMIT,
      'the bounded feedback ladder reached its iteration limit before the '
      'relaxed pressure update tolerance was met',
    )
  ####
  if not response_residuals_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus.RESPONSE_FAILURE,
      'the pressure update reached a research fixed point, but the retained '
      'global/coupled overlap residual gate remains open',
    )
  ####
  return (
    MocReflectedDomainGlobalCoupledDownstreamFeedbackStatus
    .CONVERGED_RESEARCH_PRESSURE_UPDATE,
    'fresh downstream pressure feedback reached its declared research '
    'tolerance; upstream global feedback, canonical closure, external '
    'validation, and production promotion remain closed',
  )
####


def run_reflected_domain_global_coupled_downstream_feedback(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  maximum_iterations: int = 3,
  pressure_correction_fraction: float = 0.25,
  pressure_update_tolerance_Pa: float = 1.0e3,
  position_tolerance_m: float = 1.0e-9,
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  axial_station_count: int = 7,
  axial_cell_count: int = 12,
  transverse_cell_count: int = 6,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: Any | None = None,
  physical_field_shock_front_condition: Any | None = None,
) -> MocReflectedDomainGlobalCoupledDownstreamFeedbackRun:
  """Run bounded downstream pressure feedback without an upstream re-solve."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if isinstance(maximum_iterations, bool) or not isinstance(
    maximum_iterations,
    int,
  ):
    raise TypeError('maximum_iterations must be an integer')
  ####
  if maximum_iterations < 2:
    raise ValueError('maximum_iterations must be at least two')
  ####
  fraction = float(pressure_correction_fraction)
  if not isfinite(fraction) or fraction <= 0.0 or fraction > 1.0:
    raise ValueError('pressure_correction_fraction must be in (0, 1]')
  ####
  update_tolerance = float(pressure_update_tolerance_Pa)
  if not isfinite(update_tolerance) or update_tolerance <= 0.0:
    raise ValueError('pressure_update_tolerance_Pa must be finite and positive')
  ####
  position_tolerance = float(position_tolerance_m)
  if not isfinite(position_tolerance) or position_tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  configuration = {
    'closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
      closure
    ),
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'maximum_iterations': maximum_iterations,
    'pressure_correction_fraction': fraction,
    'pressure_update_tolerance_Pa': update_tolerance,
    'position_tolerance_m': position_tolerance,
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'axial_station_count': int(axial_station_count),
    'axial_cell_count': int(axial_cell_count),
    'transverse_cell_count': int(transverse_cell_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'inlet_boundary_mode': inlet_boundary_mode.value,
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'physical_field_continuation_profile_supplied': (
      physical_field_continuation_profile is not None
    ),
    'physical_field_shock_front_condition_supplied': (
      physical_field_shock_front_condition is not None
    ),
  }
  configuration_fingerprint = sha256(
    json.dumps(
      configuration,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  iterations: list[
    MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration
  ] = []
  input_profile: (
    MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  ) = None
  pressure_update_convergence_verified = False
  pressure_profile_alignment_verified = True
  stop_reason: str | None = None
  for iteration_index in range(maximum_iterations):
    try:
      result = solve_reflected_domain_global_coupled_downstream(
        closure,
        reference_total_temperature_K=reference_total_temperature_K,
        ambient_pressure_Pa=ambient_pressure_Pa,
        downstream_length_m=downstream_length_m,
        initial_outlet_height_m=initial_outlet_height_m,
        control_section_x_offset_m=control_section_x_offset_m,
        control_section_height_m=control_section_height_m,
        control_section_sample_count=control_section_sample_count,
        axial_station_count=axial_station_count,
        axial_cell_count=axial_cell_count,
        transverse_cell_count=transverse_cell_count,
        max_pseudo_iterations=max_pseudo_iterations,
        max_shape_iterations=max_shape_iterations,
        inlet_boundary_mode=inlet_boundary_mode,
        outlet_static_pressure_Pa=outlet_static_pressure_Pa,
        physical_field_continuation_profile=physical_field_continuation_profile,
        physical_field_shock_front_condition=physical_field_shock_front_condition,
        boundary_pressure_profile=input_profile,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      result = _failed_result(
        closure,
        f'fresh global/coupled downstream feedback solve raised: {error}',
      )
    ####
    solver_response = result.downstream_boundary_response
    response = None
    if result.coupled_field is not None:
      try:
        response = measure_reflected_domain_global_coupled_downstream_boundary_response(
          closure,
          result.coupled_field,
          position_tolerance_m=position_tolerance,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        response = None
      ####
    ####
    response_lineage_verified = bool(
      solver_response is not None
      and response is not None
      and solver_response.as_report() == response.as_report()
    )
    next_profile = None
    pressure_profile_lineage_verified = bool(
      result.closure_lineage_verified
      and (
        input_profile is None
        or result.boundary_pressure_profile == input_profile
      )
    )
    pressure_profile_consumption_verified = bool(
      (
        input_profile is None
        and result.boundary_pressure_profile is None
        and (
          result.coupled_request is None
          or (
            result.coupled_request.free_boundary_pressure_profile_Pa is None
            and result.coupled_request.free_boundary_pressure_profile_x_stations_m
            is None
            and result.coupled_request.free_boundary_pressure_profile_source
            is None
          )
        )
      )
      or (
        input_profile is not None
        and result.boundary_pressure_profile == input_profile
        and result.coupled_field is not None
        and result.coupled_field.free_boundary_pressure_profile_consumed
      )
    )
    maximum_pressure_update = None
    if response is not None:
      try:
        next_profile = (
          build_reflected_domain_global_coupled_downstream_feedback_pressure_profile(
            closure,
            response,
            pressure_correction_fraction=fraction,
            position_tolerance_m=position_tolerance,
          )
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        stop_reason = f'pressure feedback profile construction failed: {error}'
      ####
    ####
    if next_profile is not None and not (
      next_profile.profile_verified
      and next_profile.source_closure_fingerprint
      == moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ):
      pressure_profile_lineage_verified = False
    ####
    if input_profile is not None and next_profile is not None:
      if not _profiles_aligned(
        input_profile,
        next_profile,
        position_tolerance_m=position_tolerance,
      ):
        pressure_profile_alignment_verified = False
        stop_reason = (
          'pressure feedback profile cell-center stations changed between '
          'fresh solves; no regridding or extrapolation was attempted'
        )
      else:
        maximum_pressure_update = _maximum_profile_update(
          input_profile,
          next_profile,
        )
        if (
          result.local_coupled_field_verified
          and maximum_pressure_update <= update_tolerance
        ):
          pressure_update_convergence_verified = True
        ####
      ####
    ####
    iterations.append(
      MocReflectedDomainGlobalCoupledDownstreamFeedbackIteration(
        iteration_index=iteration_index,
        input_pressure_profile=input_profile,
        result=result,
        solver_response=solver_response,
        response=response,
        next_pressure_profile=next_profile,
        maximum_pressure_update_Pa=maximum_pressure_update,
        pressure_profile_lineage_verified=pressure_profile_lineage_verified,
        response_lineage_verified=response_lineage_verified,
        pressure_profile_consumption_verified=(
          pressure_profile_consumption_verified
        ),
      )
    )
    if not result.local_coupled_field_verified:
      stop_reason = stop_reason or (
        'fresh coupled field did not pass its local solver and independent '
        'audit; no lower-fidelity fallback was attempted'
      )
      break
    ####
    if next_profile is None:
      stop_reason = stop_reason or (
        'independently measured response did not produce a covered pressure '
        'profile for the next fresh solve'
      )
      break
    ####
    if pressure_update_convergence_verified:
      break
    ####
    input_profile = next_profile
  ####
  retained_iterations = tuple(iterations)
  fresh_solver_invocation_verified = bool(
    retained_iterations
    and len({id(item.result) for item in retained_iterations})
    == len(retained_iterations)
  )
  closure_lineage_verified = bool(
    retained_iterations
    and all(item.result.closure_lineage_verified for item in retained_iterations)
  )
  pressure_profile_lineage_verified = bool(
    retained_iterations
    and all(
      item.pressure_profile_lineage_verified
      and item.pressure_profile_consumption_verified
      for item in retained_iterations
    )
  )
  response_lineage_verified = bool(
    retained_iterations
    and all(item.response_lineage_verified for item in retained_iterations)
  )
  response_channels_finite = bool(
    retained_iterations
    and all(item.response_channels_finite for item in retained_iterations)
  )
  response_coverage_verified = bool(
    retained_iterations
    and all(item.response_coverage_verified for item in retained_iterations)
  )
  response_residuals_verified = bool(
    retained_iterations
    and all(item.response_residuals_verified for item in retained_iterations)
  )
  local_coupled_field_verified = bool(
    retained_iterations
    and all(item.local_coupled_field_verified for item in retained_iterations)
  )
  fidelity_isolation_verified = bool(
    retained_iterations
    and all(item.fidelity_isolation_verified for item in retained_iterations)
  )
  status, message = _status_for_run(
    iterations=retained_iterations,
    fresh_solver_invocation_verified=fresh_solver_invocation_verified,
    closure_lineage_verified=closure_lineage_verified,
    pressure_profile_lineage_verified=pressure_profile_lineage_verified,
    pressure_profile_alignment_verified=pressure_profile_alignment_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    response_coverage_verified=response_coverage_verified,
    response_residuals_verified=response_residuals_verified,
    local_coupled_field_verified=local_coupled_field_verified,
    pressure_update_convergence_verified=pressure_update_convergence_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
  )
  if stop_reason is not None:
    message = f'{message}; {stop_reason}'
  ####
  return MocReflectedDomainGlobalCoupledDownstreamFeedbackRun(
    closure=closure,
    requested_iterations=maximum_iterations,
    iterations=retained_iterations,
    status=status,
    pressure_update_tolerance_Pa=update_tolerance,
    pressure_correction_fraction=fraction,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=fresh_solver_invocation_verified,
    closure_lineage_verified=closure_lineage_verified,
    pressure_profile_lineage_verified=pressure_profile_lineage_verified,
    pressure_profile_alignment_verified=pressure_profile_alignment_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    response_coverage_verified=response_coverage_verified,
    response_residuals_verified=response_residuals_verified,
    local_coupled_field_verified=local_coupled_field_verified,
    pressure_update_convergence_verified=pressure_update_convergence_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####
