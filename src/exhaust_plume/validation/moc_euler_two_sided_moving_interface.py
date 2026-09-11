"""Independent audit for the two-sided moving-interface research ladder.

The solver-side driver owns only orchestration: it accepts a solver-owned
interface response, re-solves the exact two-sided field on the returned shock
curve, and records the lineage.  This validator independently remeasures the
shock displacement channel, the declared flux residuals, every exact field
re-solve, and the promotion flags.  It does not supply an interface law and
does not turn a research result into canonical or production evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
  MocEulerTwoSidedMovingInterfaceRequest,
  MocEulerTwoSidedMovingInterfaceResult,
  MocEulerTwoSidedMovingInterfaceStatus,
  compute_moc_euler_two_sided_interface_normal_displacements,
)
from exhaust_plume.validation.moc_euler_two_sided_field_iteration import (
  measure_moc_euler_two_sided_field_iteration,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_MOVING_INTERFACE_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedMovingInterfaceAuditStatus',
  'MocEulerTwoSidedMovingInterfaceAudit',
  'measure_moc_euler_two_sided_moving_interface',
)


MOC_EULER_TWO_SIDED_MOVING_INTERFACE_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-moving-interface-audit'
)


class MocEulerTwoSidedMovingInterfaceAuditStatus(str, Enum):
  """Typed outcomes for the independent moving-interface audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_two_sided_moving_interface_audit'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'two_sided_moving_interface_audit_request_failure'
  INITIAL_FIELD_FAILURE = 'two_sided_moving_interface_audit_initial_field_failure'
  RECORD_FAILURE = 'two_sided_moving_interface_audit_record_failure'
  RESPONSE_FAILURE = 'two_sided_moving_interface_audit_response_failure'
  FIELD_RESOLVE_FAILURE = 'two_sided_moving_interface_audit_field_resolve_failure'
  FLAG_FAILURE = 'two_sided_moving_interface_audit_flag_failure'
  UPDATE_REQUIRED = 'two_sided_moving_interface_audit_update_required'
  CONSERVATIVE_FLUX_FAILURE = (
    'two_sided_moving_interface_audit_conservative_flux_failure'
  )
  ITERATION_LIMIT = 'two_sided_moving_interface_audit_iteration_limit'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedMovingInterfaceAudit:
  """Recomputed evidence for one bounded moving-interface ladder."""

  status: MocEulerTwoSidedMovingInterfaceAuditStatus
  result_status: str | None
  iteration_count: int
  request_verified: bool
  initial_field_verified: bool
  record_lineage_verified: bool
  response_lineage_verified: bool
  interface_motion_verified: bool
  stationary_equilibrium_verified: bool
  response_residuals_verified: bool
  field_re_solve_verified: bool
  moving_interface_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  conservative_flux_closure_required: bool = False
  conservative_flux_closure_verified: bool = False
  maximum_normal_displacement_m: float = 0.0
  maximum_mass_flux_residual_kg_m2_s: float = 0.0
  maximum_normal_momentum_residual_Pa: float = 0.0
  maximum_energy_flux_residual_W_m2: float = 0.0
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_MOVING_INTERFACE_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedMovingInterfaceAuditStatus,
    ):
      raise TypeError('status must be a moving-interface audit status')
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    if (
      isinstance(self.iteration_count, bool)
      or not isinstance(self.iteration_count, int)
      or self.iteration_count < 0
    ):
      raise ValueError('iteration_count must be a nonnegative integer')
    ####
    for name in (
      'request_verified',
      'initial_field_verified',
      'record_lineage_verified',
      'response_lineage_verified',
      'interface_motion_verified',
      'stationary_equilibrium_verified',
      'response_residuals_verified',
      'field_re_solve_verified',
      'moving_interface_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'conservative_flux_closure_required',
      'conservative_flux_closure_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'maximum_normal_displacement_m',
      'maximum_mass_flux_residual_kg_m2_s',
      'maximum_normal_momentum_residual_Pa',
      'maximum_energy_flux_residual_W_m2',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedMovingInterfaceAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether all local response, motion, and re-solve evidence agrees."""

    return bool(
      self.converged
      and self.request_verified
      and self.initial_field_verified
      and self.record_lineage_verified
      and self.response_lineage_verified
      and (
        self.interface_motion_verified
        or self.stationary_equilibrium_verified
      )
      and self.response_residuals_verified
      and self.field_re_solve_verified
      and self.moving_interface_verified
      and (
        not self.conservative_flux_closure_required
        or self.conservative_flux_closure_verified
      )
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'iteration_count': self.iteration_count,
      'request_verified': self.request_verified,
      'initial_field_verified': self.initial_field_verified,
      'record_lineage_verified': self.record_lineage_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'interface_motion_verified': self.interface_motion_verified,
      'stationary_equilibrium_verified': self.stationary_equilibrium_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'field_re_solve_verified': self.field_re_solve_verified,
      'moving_interface_verified': self.moving_interface_verified,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'conservative_flux_closure_required': (
        self.conservative_flux_closure_required
      ),
      'conservative_flux_closure_verified': (
        self.conservative_flux_closure_verified
      ),
      'maximum_normal_displacement_m': self.maximum_normal_displacement_m,
      'maximum_mass_flux_residual_kg_m2_s': (
        self.maximum_mass_flux_residual_kg_m2_s
      ),
      'maximum_normal_momentum_residual_Pa': (
        self.maximum_normal_momentum_residual_Pa
      ),
      'maximum_energy_flux_residual_W_m2': (
        self.maximum_energy_flux_residual_W_m2
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedMovingInterfaceAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  iteration_count: int = 0,
  request_verified: bool = False,
  initial_field_verified: bool = False,
  record_lineage_verified: bool = False,
  response_lineage_verified: bool = False,
  interface_motion_verified: bool = False,
  stationary_equilibrium_verified: bool = False,
  response_residuals_verified: bool = False,
  field_re_solve_verified: bool = False,
  moving_interface_verified: bool = False,
  conservative_flux_closure_required: bool = False,
  conservative_flux_closure_verified: bool = False,
  maximum_normal_displacement_m: float = 0.0,
  maximum_mass_flux_residual_kg_m2_s: float = 0.0,
  maximum_normal_momentum_residual_Pa: float = 0.0,
  maximum_energy_flux_residual_W_m2: float = 0.0,
) -> MocEulerTwoSidedMovingInterfaceAudit:
  return MocEulerTwoSidedMovingInterfaceAudit(
    status=status,
    result_status=result_status,
    iteration_count=iteration_count,
    request_verified=request_verified,
    initial_field_verified=initial_field_verified,
    record_lineage_verified=record_lineage_verified,
    response_lineage_verified=response_lineage_verified,
    interface_motion_verified=interface_motion_verified,
    stationary_equilibrium_verified=stationary_equilibrium_verified,
    response_residuals_verified=response_residuals_verified,
    field_re_solve_verified=field_re_solve_verified,
    moving_interface_verified=moving_interface_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    conservative_flux_closure_required=conservative_flux_closure_required,
    conservative_flux_closure_verified=conservative_flux_closure_verified,
    maximum_normal_displacement_m=maximum_normal_displacement_m,
    maximum_mass_flux_residual_kg_m2_s=maximum_mass_flux_residual_kg_m2_s,
    maximum_normal_momentum_residual_Pa=maximum_normal_momentum_residual_Pa,
    maximum_energy_flux_residual_W_m2=maximum_energy_flux_residual_W_m2,
    message=message,
  )


def _field_request_lineage_verified(
  current: MocEulerTwoSidedFieldIterationResult,
  next_field: MocEulerTwoSidedFieldIterationResult,
  response: MocEulerTwoSidedInterfaceResponse,
) -> bool:
  current_request = current.request
  next_request = next_field.request
  if current_request is None or next_request is None:
    return False
  ####
  scalar_fields = (
    'ambient_pressure_Pa',
    'target_centerline_y_m',
    'position_tolerance_m',
    'invariant_tolerance',
    'pressure_tolerance',
    'tangent_tolerance',
    'handoff_position_tolerance_m',
    'handoff_state_tolerance',
    'handoff_pressure_tolerance_Pa',
    'source_trace_position_tolerance_m',
    'source_trace_forward_tolerance_m',
    'maximum_field_iterations',
    'maximum_boundary_iterations',
  )
  return bool(
    next_request.shock_boundary is response.next_shock_boundary
    and next_request.companion_field is response.next_companion_field
    and next_field.shock_boundary is response.next_shock_boundary
    and next_field.initial_companion_field is response.next_companion_field
    and all(
      getattr(next_request, name) == getattr(current_request, name)
      for name in scalar_fields
    )
  )


def _response_measurements(
  current: MocEulerTwoSidedFieldIterationResult,
  response: MocEulerTwoSidedInterfaceResponse,
  request: MocEulerTwoSidedMovingInterfaceRequest,
) -> tuple[bool, bool, bool, float, float, float, float]:
  """Recompute response lineage, motion, and all declared residual channels."""

  if current.shock_boundary is None:
    return False, False, False, 0.0, 0.0, 0.0, 0.0
  ####
  if response.prior_shock_boundary is not current.shock_boundary:
    return False, False, False, 0.0, 0.0, 0.0, 0.0
  ####
  try:
    displacements = compute_moc_euler_two_sided_interface_normal_displacements(
      response.prior_shock_boundary,
      response.next_shock_boundary,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return False, False, False, 0.0, 0.0, 0.0, 0.0
  ####
  displacement_match = bool(
    len(displacements) == len(response.normal_displacements_m)
    and all(
      abs(actual - declared) <= request.position_tolerance_m
      for actual, declared in zip(
        displacements,
        response.normal_displacements_m,
        strict=True,
      )
    )
  )
  response_lineage_verified = bool(
    displacement_match
    and response.next_companion_field.shock_boundary
    is response.next_shock_boundary
  )
  maximum_displacement = max(
    (abs(value) for value in displacements),
    default=0.0,
  )
  moved = any(
    abs(value) > request.position_tolerance_m for value in displacements
  )
  maximum_mass = response.maximum_mass_flux_residual_kg_m2_s
  maximum_momentum = response.maximum_normal_momentum_residual_Pa
  maximum_energy = response.maximum_energy_flux_residual_W_m2
  residuals_verified = bool(
    maximum_mass <= request.mass_flux_tolerance_kg_m2_s
    and maximum_momentum <= request.normal_momentum_tolerance_Pa
    and maximum_energy <= request.energy_flux_tolerance_W_m2
  )
  return (
    response_lineage_verified,
    moved,
    residuals_verified,
    maximum_displacement,
    maximum_mass,
    maximum_momentum,
    maximum_energy,
  )


def measure_moc_euler_two_sided_moving_interface(
  result: MocEulerTwoSidedMovingInterfaceResult,
) -> MocEulerTwoSidedMovingInterfaceAudit:
  """Independently remeasure the moving-interface/re-solve contract."""

  if not isinstance(result, MocEulerTwoSidedMovingInterfaceResult):
    return _failure(
      MocEulerTwoSidedMovingInterfaceAuditStatus.INVALID_INPUT,
      'result must be a MocEulerTwoSidedMovingInterfaceResult',
    )
  ####
  request = result.request
  initial = result.initial_field_iteration
  request_verified = bool(
    request is not None
    and initial is not None
    and initial.request is request.field_request
    and initial.shock_boundary is request.field_request.shock_boundary
    and initial.initial_companion_field is request.field_request.companion_field
  )
  if not request_verified or request is None or initial is None:
    return _failure(
      MocEulerTwoSidedMovingInterfaceAuditStatus.REQUEST_FAILURE,
      'moving-interface result did not retain exact request and initial-field lineage',
      result_status=result.status.value,
      request_verified=request_verified,
    )
  ####
  try:
    initial_field_audit = measure_moc_euler_two_sided_field_iteration(initial)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedMovingInterfaceAuditStatus.INITIAL_FIELD_FAILURE,
      f'independent initial-field audit raised: {error}',
      result_status=result.status.value,
      request_verified=True,
    )
  ####
  initial_field_verified = bool(initial_field_audit.local_consistency_verified)
  if not initial_field_verified:
    return _failure(
      MocEulerTwoSidedMovingInterfaceAuditStatus.INITIAL_FIELD_FAILURE,
      'independent two-sided field audit did not verify the initial research field',
      result_status=result.status.value,
      request_verified=True,
      initial_field_verified=False,
    )
  ####
  records = tuple(result.records)
  if not records:
    flags_verified = bool(
      result.status is MocEulerTwoSidedMovingInterfaceStatus.INTERFACE_UPDATE_REQUIRED
      and not result.moving_interface_verified
      and not result.response_lineage_verified
      and not result.interface_motion_verified
      and not result.response_residuals_verified
      and not result.field_re_solve_verified
      and not result.canonical_free_boundary_verified
      and not result.canonical_euler_verified
      and result.chain_promotion_blocked
      and not result.production_claim_allowed
    )
    return _failure(
      MocEulerTwoSidedMovingInterfaceAuditStatus.UPDATE_REQUIRED
      if flags_verified
      else MocEulerTwoSidedMovingInterfaceAuditStatus.FLAG_FAILURE,
      'initial exact field is independently verified, but no solver-owned '
      'moving-interface update record was supplied',
      result_status=result.status.value,
      iteration_count=0,
      request_verified=True,
      initial_field_verified=True,
    )
  ####
  current = initial
  record_lineage_verified = True
  response_lineage_verified = True
  interface_motion_verified = True
  stationary_equilibrium_verified = True
  response_residuals_verified = True
  field_re_solve_verified = True
  maximum_displacement = 0.0
  maximum_mass = 0.0
  maximum_momentum = 0.0
  maximum_energy = 0.0
  conservative_flux_closure_verified = True
  failure_status: MocEulerTwoSidedMovingInterfaceAuditStatus | None = None
  failure_message = ''
  for expected_index, record in enumerate(records):
    if record.iteration_index != expected_index or record.field_iteration is not current:
      record_lineage_verified = False
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RECORD_FAILURE
      failure_message = 'moving-interface records did not retain exact sequential field lineage'
      break
    ####
    response = record.response
    if response is None:
      response_lineage_verified = False
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RESPONSE_FAILURE
      failure_message = 'moving-interface record retained no typed response packet'
      break
    ####
    try:
      (
        response_lineage,
        moved,
        residuals,
        displacement,
        mass,
        momentum,
        energy,
      ) = _response_measurements(current, response, request)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      response_lineage = False
      moved = False
      residuals = False
      displacement = mass = momentum = energy = 0.0
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RESPONSE_FAILURE
      failure_message = f'moving-interface response audit raised: {error}'
    ####
    maximum_displacement = max(maximum_displacement, displacement)
    maximum_mass = max(maximum_mass, mass)
    maximum_momentum = max(maximum_momentum, momentum)
    maximum_energy = max(maximum_energy, energy)
    response_conservative_flux_verified = bool(
      response.conservative_flux_closure_verified and residuals
    )
    conservative_flux_closure_verified = (
      conservative_flux_closure_verified
      and response_conservative_flux_verified
    )
    next_field = record.next_field_iteration
    field_resolve = False
    next_field_audit_verified = False
    if next_field is not None and response_lineage:
      try:
        next_field_audit = measure_moc_euler_two_sided_field_iteration(next_field)
        next_field_audit_verified = next_field_audit.local_consistency_verified
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        next_field_audit_verified = False
      ####
      field_resolve = bool(
        next_field_audit_verified
        and _field_request_lineage_verified(current, next_field, response)
      )
    ####
    expected_response_residuals = bool(
      next_field is not None
      and residuals
      and (
        not request.require_conservative_flux_closure
        or response_conservative_flux_verified
      )
    )
    expected_motion = moved
    expected_stationary = bool(
      next_field is not None
      and residuals
      and not moved
      and not request.require_interface_motion
      and request.allow_stationary_equilibrium
      and response.stationary_equilibrium_candidate
    )
    expected_response_lineage = response_lineage
    expected_field_resolve = field_resolve
    record_flags_match = bool(
      record.response_lineage_verified == expected_response_lineage
      and record.interface_motion_verified == expected_motion
      and record.stationary_equilibrium_verified == expected_stationary
      and record.response_residuals_verified == expected_response_residuals
      and record.field_re_solve_verified == expected_field_resolve
    )
    response_lineage_verified = response_lineage_verified and (
      response_lineage and record_flags_match
    )
    interface_motion_verified = interface_motion_verified and (
      moved and record_flags_match
    )
    stationary_equilibrium_verified = stationary_equilibrium_verified and (
      expected_stationary and record_flags_match
    )
    response_residuals_verified = response_residuals_verified and (
      expected_response_residuals and record_flags_match
    )
    field_re_solve_verified = field_re_solve_verified and (
      field_resolve and record_flags_match
    )
    if failure_status is not None:
      break
    ####
    if not response_lineage:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RESPONSE_FAILURE
      failure_message = 'response displacement or shock/companion lineage failed independent remeasurement'
      break
    ####
    if request.require_interface_motion and not moved:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RESPONSE_FAILURE
      failure_message = 'response retained the prior shock geometry; moving-interface evidence is absent'
      break
    ####
    if request.require_conservative_flux_closure and not response_conservative_flux_verified:
      failure_status = (
        MocEulerTwoSidedMovingInterfaceAuditStatus.CONSERVATIVE_FLUX_FAILURE
      )
      failure_message = (
        'strict moving-interface response did not retain independently '
        'verified conservative mass, normal-momentum, and energy closure'
      )
      break
    ####
    if next_field is None or not field_resolve:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.FIELD_RESOLVE_FAILURE
      failure_message = 'response was present but its exact two-sided field re-solve was not independently verified'
      break
    ####
    current = next_field
    if not record_flags_match:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.FLAG_FAILURE
      failure_message = 'moving-interface record flags did not match independently remeasured evidence'
      break
  ####
  final_lineage = bool(result.final_field_iteration is current)
  record_lineage_verified = record_lineage_verified and final_lineage
  expected_moving = bool(
    result.status in (
      MocEulerTwoSidedMovingInterfaceStatus.CONVERGED_RESEARCH_MOVING_INTERFACE,
      MocEulerTwoSidedMovingInterfaceStatus.CONVERGED_RESEARCH_STATIONARY_INTERFACE,
    )
    and record_lineage_verified
    and response_lineage_verified
    and (interface_motion_verified or stationary_equilibrium_verified)
    and response_residuals_verified
    and field_re_solve_verified
    and (
      not request.require_conservative_flux_closure
      or conservative_flux_closure_verified
    )
  )
  result_flags_verified = bool(
    result.moving_interface_verified == expected_moving
    and result.response_lineage_verified == response_lineage_verified
    and result.interface_motion_verified == interface_motion_verified
    and result.stationary_equilibrium_verified == stationary_equilibrium_verified
    and result.response_residuals_verified == response_residuals_verified
    and result.field_re_solve_verified == field_re_solve_verified
    and result.conservative_flux_closure_required
    == request.require_conservative_flux_closure
    and result.conservative_flux_closure_verified
    == conservative_flux_closure_verified
    and not result.canonical_free_boundary_verified
    and not result.canonical_euler_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
  )
  if failure_status is None:
    if not record_lineage_verified:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RECORD_FAILURE
      failure_message = 'final moving-interface result did not retain the exact last field object'
    elif not result_flags_verified:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.FLAG_FAILURE
      failure_message = 'moving-interface result flags did not match independent evidence'
    elif expected_moving:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.CONVERGED_LOCAL_AUDIT
      failure_message = (
        'independent moving-interface audit passed exact response lineage, '
        'interface condition, residual, and field re-solve gates; '
        'canonical closure and production promotion remain blocked'
      )
    elif result.status is MocEulerTwoSidedMovingInterfaceStatus.ITERATION_LIMIT:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.ITERATION_LIMIT
      failure_message = 'moving-interface ladder retained local field evidence but reached its declared iteration limit'
    else:
      failure_status = MocEulerTwoSidedMovingInterfaceAuditStatus.RESPONSE_FAILURE
      failure_message = 'moving-interface ladder did not produce a locally converged response sequence'
  ####
  return _failure(
    failure_status,
    failure_message,
    result_status=result.status.value,
    iteration_count=len(records),
    request_verified=True,
    initial_field_verified=True,
    record_lineage_verified=record_lineage_verified,
    response_lineage_verified=response_lineage_verified,
    interface_motion_verified=interface_motion_verified,
    stationary_equilibrium_verified=stationary_equilibrium_verified,
    response_residuals_verified=response_residuals_verified,
    field_re_solve_verified=field_re_solve_verified,
    moving_interface_verified=expected_moving,
    conservative_flux_closure_required=request.require_conservative_flux_closure,
    conservative_flux_closure_verified=conservative_flux_closure_verified,
    maximum_normal_displacement_m=maximum_displacement,
    maximum_mass_flux_residual_kg_m2_s=maximum_mass,
    maximum_normal_momentum_residual_Pa=maximum_momentum,
    maximum_energy_flux_residual_W_m2=maximum_energy,
  )
