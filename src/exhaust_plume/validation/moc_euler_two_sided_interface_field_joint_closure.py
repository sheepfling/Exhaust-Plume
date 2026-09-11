"""Independent joint audit for the moving two-sided Euler research seam.

The moving-interface audit, the bounded two-sided field audit, and the
variable-entropy audit each answer a narrower question.  This operator
composes their independently remeasured evidence and adds one explicit
centerline compatibility check for the final physical field.  It is a
research convergence report only: canonical free-boundary closure,
continued shock-cell promotion, and production claims remain blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedMovingInterfaceResult,
)
from exhaust_plume.validation.moc_euler import (
  MocEulerAmbientPhysicalFieldAudit,
  measure_moc_euler_ambient_physical_field,
)
from exhaust_plume.validation.moc_euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationAudit,
  measure_moc_euler_two_sided_field_iteration,
)
from exhaust_plume.validation.moc_euler_two_sided_moving_interface import (
  MocEulerTwoSidedMovingInterfaceAudit,
  measure_moc_euler_two_sided_moving_interface,
)
from exhaust_plume.validation.moc_euler_variable_entropy_lineage import (
  MocEulerVariableEntropyLineageAudit,
  measure_moc_euler_variable_entropy_lineage,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_INTERFACE_FIELD_JOINT_CLOSURE_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus',
  'MocEulerTwoSidedInterfaceFieldJointClosureAudit',
  'measure_moc_euler_two_sided_interface_field_joint_closure',
)


MOC_EULER_TWO_SIDED_INTERFACE_FIELD_JOINT_CLOSURE_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-interface-field-joint-closure-audit'
)


class MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus(str, Enum):
  """Typed outcomes for the joint research closure audit."""

  CONVERGED_RESEARCH_JOINT_CLOSURE = (
    'converged_research_two_sided_interface_field_joint_closure'
  )
  INVALID_INPUT = 'invalid_input'
  MOVING_INTERFACE_FAILURE = (
    'two_sided_interface_field_joint_closure_moving_interface_failure'
  )
  FIELD_ITERATION_FAILURE = (
    'two_sided_interface_field_joint_closure_field_iteration_failure'
  )
  PHYSICAL_FIELD_FAILURE = (
    'two_sided_interface_field_joint_closure_physical_field_failure'
  )
  CENTERLINE_FAILURE = (
    'two_sided_interface_field_joint_closure_centerline_failure'
  )
  ENTROPY_FAILURE = (
    'two_sided_interface_field_joint_closure_entropy_failure'
  )
  AMBIENT_BOUNDARY_FAILURE = (
    'two_sided_interface_field_joint_closure_ambient_boundary_failure'
  )
  RESIDUAL_FAILURE = (
    'two_sided_interface_field_joint_closure_residual_failure'
  )
  FLAG_FAILURE = 'two_sided_interface_field_joint_closure_flag_failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceFieldJointClosureAudit:
  """Independent evidence for one moving-interface/field joint result."""

  status: MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus
  result_status: str | None
  moving_interface_audit: MocEulerTwoSidedMovingInterfaceAudit | None
  field_iteration_audit: MocEulerTwoSidedFieldIterationAudit | None
  ambient_field_audit: MocEulerAmbientPhysicalFieldAudit | None
  entropy_audit: MocEulerVariableEntropyLineageAudit | None
  moving_interface_verified: bool
  response_lineage_verified: bool
  field_re_solve_verified: bool
  field_iteration_verified: bool
  physical_field_verified: bool
  centerline_boundary_verified: bool
  entropy_transport_verified: bool
  ambient_boundary_verified: bool
  momentum_residual_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  maximum_normal_momentum_residual_Pa: float = 0.0
  normal_momentum_tolerance_Pa: float = 1.0
  maximum_entropy_advection_residual: float | None = None
  maximum_centerline_invariant_residual: float | None = None
  message: str = ''
  operator_id: str = (
    MOC_EULER_TWO_SIDED_INTERFACE_FIELD_JOINT_CLOSURE_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus,
    ):
      raise TypeError('status must be a joint-closure audit status')
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    for name in (
      'moving_interface_verified',
      'response_lineage_verified',
      'field_re_solve_verified',
      'field_iteration_verified',
      'physical_field_verified',
      'centerline_boundary_verified',
      'entropy_transport_verified',
      'ambient_boundary_verified',
      'momentum_residual_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'maximum_normal_momentum_residual_Pa',
      'normal_momentum_tolerance_Pa',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'maximum_entropy_advection_residual',
      'maximum_centerline_invariant_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
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
    return self.status is (
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus
      .CONVERGED_RESEARCH_JOINT_CLOSURE
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether all local gates pass without crossing the research ceiling."""

    return bool(
      self.converged
      and self.moving_interface_verified
      and self.response_lineage_verified
      and self.field_re_solve_verified
      and self.field_iteration_verified
      and self.physical_field_verified
      and self.centerline_boundary_verified
      and self.entropy_transport_verified
      and self.ambient_boundary_verified
      and self.momentum_residual_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'audits': {
        'moving_interface': (
          None
          if self.moving_interface_audit is None
          else self.moving_interface_audit.as_report()
        ),
        'field_iteration': (
          None
          if self.field_iteration_audit is None
          else self.field_iteration_audit.as_report()
        ),
        'ambient_field': (
          None
          if self.ambient_field_audit is None
          else self.ambient_field_audit.as_report()
        ),
        'entropy': (
          None
          if self.entropy_audit is None
          else self.entropy_audit.as_report()
        ),
      },
      'checks': {
        'moving_interface_verified': self.moving_interface_verified,
        'response_lineage_verified': self.response_lineage_verified,
        'field_re_solve_verified': self.field_re_solve_verified,
        'field_iteration_verified': self.field_iteration_verified,
        'physical_field_verified': self.physical_field_verified,
        'centerline_boundary_verified': self.centerline_boundary_verified,
        'entropy_transport_verified': self.entropy_transport_verified,
        'ambient_boundary_verified': self.ambient_boundary_verified,
        'momentum_residual_verified': self.momentum_residual_verified,
        'canonical_free_boundary_verified': False,
        'canonical_euler_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'maximum_normal_momentum_residual_Pa': (
        self.maximum_normal_momentum_residual_Pa
      ),
      'normal_momentum_tolerance_Pa': self.normal_momentum_tolerance_Pa,
      'maximum_entropy_advection_residual': (
        self.maximum_entropy_advection_residual
      ),
      'maximum_centerline_invariant_residual': (
        self.maximum_centerline_invariant_residual
      ),
      'claim_status': (
        'research-only joint moving-interface/field closure; canonical '
        'free-boundary, continued shock-cell, external validation, and '
        'production claims remain blocked'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  moving_interface_audit: MocEulerTwoSidedMovingInterfaceAudit | None = None,
  field_iteration_audit: MocEulerTwoSidedFieldIterationAudit | None = None,
  ambient_field_audit: MocEulerAmbientPhysicalFieldAudit | None = None,
  entropy_audit: MocEulerVariableEntropyLineageAudit | None = None,
  moving_interface_verified: bool = False,
  response_lineage_verified: bool = False,
  field_re_solve_verified: bool = False,
  field_iteration_verified: bool = False,
  physical_field_verified: bool = False,
  centerline_boundary_verified: bool = False,
  entropy_transport_verified: bool = False,
  ambient_boundary_verified: bool = False,
  momentum_residual_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  maximum_normal_momentum_residual_Pa: float = 0.0,
  normal_momentum_tolerance_Pa: float = 1.0,
  maximum_entropy_advection_residual: float | None = None,
  maximum_centerline_invariant_residual: float | None = None,
) -> MocEulerTwoSidedInterfaceFieldJointClosureAudit:
  return MocEulerTwoSidedInterfaceFieldJointClosureAudit(
    status=status,
    result_status=result_status,
    moving_interface_audit=moving_interface_audit,
    field_iteration_audit=field_iteration_audit,
    ambient_field_audit=ambient_field_audit,
    entropy_audit=entropy_audit,
    moving_interface_verified=moving_interface_verified,
    response_lineage_verified=response_lineage_verified,
    field_re_solve_verified=field_re_solve_verified,
    field_iteration_verified=field_iteration_verified,
    physical_field_verified=physical_field_verified,
    centerline_boundary_verified=centerline_boundary_verified,
    entropy_transport_verified=entropy_transport_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    momentum_residual_verified=momentum_residual_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    maximum_normal_momentum_residual_Pa=maximum_normal_momentum_residual_Pa,
    normal_momentum_tolerance_Pa=normal_momentum_tolerance_Pa,
    maximum_entropy_advection_residual=maximum_entropy_advection_residual,
    maximum_centerline_invariant_residual=maximum_centerline_invariant_residual,
    message=message,
  )
####


def _centerline_compatibility(
  field: Any,
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> tuple[bool, float | None]:
  """Remeasure centerline geometry and the retained ``K-`` seam."""

  try:
    shock_points = tuple(field.shock_boundary_points_m)
    shock_states = tuple(field.post_shock_boundary_states)
    centerline_points = tuple(field.centerline_boundary_points_m)
    centerline_states = tuple(field.centerline_boundary_states)
    centerline_pressures = tuple(field.centerline_boundary_total_pressure_Pa)
  except (AttributeError, TypeError, ValueError):
    return False, None
  ####
  if not shock_points or len(shock_points) != len(shock_states):
    return False, None
  if not (
    len(centerline_points) == len(centerline_states)
    and len(centerline_points) == len(centerline_pressures)
    and centerline_points
  ):
    return False, None
  ####
  try:
    invariant_residuals = (
      abs(
        float(centerline_states[0].k_minus)
        - float(shock_states[-1].k_minus)
      ),
    )
  except (AttributeError, TypeError, ValueError):
    return False, None
  ####
  maximum_invariant_residual = max(invariant_residuals, default=None)
  if maximum_invariant_residual is None:
    return False, None
  ####
  try:
    finite_geometry = all(
      isfinite(float(value))
      for point in (*shock_points, *centerline_points)
      for value in point
    )
    finite_pressures = all(
      isfinite(float(value)) and float(value) > 0.0
      for value in centerline_pressures
    )
    on_centerline = all(
      abs(float(point[1])) <= 10.0 * position_tolerance_m
      for point in centerline_points
    )
    states_on_points = all(
      hypot(
        float(state.x_m) - float(point[0]),
        float(state.y_m) - float(point[1]),
      )
      <= 10.0 * position_tolerance_m
      for point, state in zip(centerline_points, centerline_states, strict=True)
    )
    increasing = all(
      current[0] > previous[0] + position_tolerance_m
      for previous, current in zip(
        centerline_points[:-1],
        centerline_points[1:],
        strict=True,
      )
    )
    shock_seam_match = (
      hypot(
        float(centerline_points[0][0]) - float(shock_points[-1][0]),
        float(centerline_points[0][1]) - float(shock_points[-1][1]),
      )
      <= 10.0 * position_tolerance_m
    )
  except (IndexError, TypeError, ValueError):
    return False, maximum_invariant_residual
  ####
  return bool(
    finite_geometry
    and finite_pressures
    and on_centerline
    and states_on_points
    and increasing
    and shock_seam_match
    and isfinite(maximum_invariant_residual)
    and maximum_invariant_residual <= invariant_tolerance
  ), maximum_invariant_residual
####


def measure_moc_euler_two_sided_interface_field_joint_closure(
  result: MocEulerTwoSidedMovingInterfaceResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  centerline_invariant_tolerance: float = 1.0e-8,
) -> MocEulerTwoSidedInterfaceFieldJointClosureAudit:
  """Remeasure the moving-interface and final-field evidence together."""

  if not isinstance(result, MocEulerTwoSidedMovingInterfaceResult):
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.INVALID_INPUT,
      'result must be a MocEulerTwoSidedMovingInterfaceResult',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance = float(centerline_invariant_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.INVALID_INPUT,
      'joint-closure tolerances must be numeric',
      result_status=result.status.value,
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (position_tolerance, invariant_tolerance)
  ):
    raise ValueError('joint-closure tolerances must be finite and positive')
  ####
  request = result.request
  if request is None:
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.INVALID_INPUT,
      'moving-interface result retained no request',
      result_status=result.status.value,
    )
  ####
  try:
    moving_audit = measure_moc_euler_two_sided_moving_interface(result)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.MOVING_INTERFACE_FAILURE,
      f'independent moving-interface audit raised: {error}',
      result_status=result.status.value,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
    )
  ####
  maximum_momentum = moving_audit.maximum_normal_momentum_residual_Pa
  momentum_verified = bool(
    maximum_momentum <= request.normal_momentum_tolerance_Pa
  )
  moving_verified = moving_audit.local_consistency_verified
  response_lineage_verified = bool(
    moving_audit.response_lineage_verified
    and (
      moving_audit.interface_motion_verified
      or moving_audit.stationary_equilibrium_verified
    )
    and moving_audit.response_residuals_verified
  )
  field_re_solve_verified = moving_audit.field_re_solve_verified
  ####
  final_field_iteration = result.final_field_iteration
  if final_field_iteration is None:
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.FIELD_ITERATION_FAILURE,
      'moving-interface result retained no final exact field re-solve',
      result_status=result.status.value,
      moving_interface_audit=moving_audit,
      moving_interface_verified=moving_verified,
      response_lineage_verified=response_lineage_verified,
      field_re_solve_verified=field_re_solve_verified,
      momentum_residual_verified=momentum_verified,
      maximum_normal_momentum_residual_Pa=maximum_momentum,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
    )
  ####
  try:
    field_iteration_audit = measure_moc_euler_two_sided_field_iteration(
      final_field_iteration
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.FIELD_ITERATION_FAILURE,
      f'independent final field-iteration audit raised: {error}',
      result_status=result.status.value,
      moving_interface_audit=moving_audit,
      moving_interface_verified=moving_verified,
      response_lineage_verified=response_lineage_verified,
      field_re_solve_verified=field_re_solve_verified,
      momentum_residual_verified=momentum_verified,
      maximum_normal_momentum_residual_Pa=maximum_momentum,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
    )
  ####
  field_iteration_verified = field_iteration_audit.local_consistency_verified
  final_physical_field = final_field_iteration.final_physical_field
  if final_physical_field is None:
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.PHYSICAL_FIELD_FAILURE,
      'final field iteration retained no physical field for joint closure',
      result_status=result.status.value,
      moving_interface_audit=moving_audit,
      field_iteration_audit=field_iteration_audit,
      moving_interface_verified=moving_verified,
      response_lineage_verified=response_lineage_verified,
      field_re_solve_verified=field_re_solve_verified,
      field_iteration_verified=field_iteration_verified,
      momentum_residual_verified=momentum_verified,
      maximum_normal_momentum_residual_Pa=maximum_momentum,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
    )
  ####
  try:
    ambient_audit = measure_moc_euler_ambient_physical_field(
      final_physical_field
    )
    entropy_audit = measure_moc_euler_variable_entropy_lineage(
      final_physical_field
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.PHYSICAL_FIELD_FAILURE,
      f'independent final physical-field audit raised: {error}',
      result_status=result.status.value,
      moving_interface_audit=moving_audit,
      field_iteration_audit=field_iteration_audit,
      moving_interface_verified=moving_verified,
      response_lineage_verified=response_lineage_verified,
      field_re_solve_verified=field_re_solve_verified,
      field_iteration_verified=field_iteration_verified,
      momentum_residual_verified=momentum_verified,
      maximum_normal_momentum_residual_Pa=maximum_momentum,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
    )
  ####
  centerline_verified, maximum_centerline = _centerline_compatibility(
    final_physical_field.field,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance,
  )
  physical_verified = bool(
    ambient_audit.shock_jump_verified
    and ambient_audit.cell_euler_residuals_verified
    and ambient_audit.physical_field_verified
    and ambient_audit.physical_closure_verified
    and ambient_audit.chain_promotion_blocked
    and not ambient_audit.production_claim_allowed
    and final_physical_field.physical_field_verified
    and final_physical_field.physical_closure_verified
  )
  entropy_verified = bool(
    entropy_audit.local_consistency_verified
    and entropy_audit.entropy_advection_verified
  )
  ambient_verified = bool(
    entropy_audit.ambient_geometry_verified
    and entropy_audit.ambient_pressure_lineage_verified
  )
  flags_verified = bool(
    result.canonical_free_boundary_verified is False
    and result.canonical_euler_verified is False
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and final_field_iteration.canonical_free_boundary_verified is False
    and final_field_iteration.canonical_euler_verified is False
    and final_field_iteration.chain_promotion_blocked
    and not final_field_iteration.production_claim_allowed
  )
  common = dict(
    result_status=result.status.value,
    moving_interface_audit=moving_audit,
    field_iteration_audit=field_iteration_audit,
    ambient_field_audit=ambient_audit,
    entropy_audit=entropy_audit,
    moving_interface_verified=moving_verified,
    response_lineage_verified=response_lineage_verified,
    field_re_solve_verified=field_re_solve_verified,
    field_iteration_verified=field_iteration_verified,
    physical_field_verified=physical_verified,
    centerline_boundary_verified=centerline_verified,
    entropy_transport_verified=entropy_verified,
    ambient_boundary_verified=ambient_verified,
    momentum_residual_verified=momentum_verified,
    chain_promotion_blocked=result.chain_promotion_blocked,
    production_claim_allowed=result.production_claim_allowed,
    maximum_normal_momentum_residual_Pa=maximum_momentum,
    normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
    maximum_entropy_advection_residual=(
      entropy_audit.maximum_entropy_advection_residual
    ),
    maximum_centerline_invariant_residual=maximum_centerline,
  )
  ####
  if not moving_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.MOVING_INTERFACE_FAILURE
    message = 'independent moving-interface response or re-solve gates failed'
  elif not field_iteration_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.FIELD_ITERATION_FAILURE
    message = 'independent final two-sided field-iteration gates failed'
  elif not physical_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.PHYSICAL_FIELD_FAILURE
    message = 'independent final physical-field or conservative-cell gates failed'
  elif not centerline_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.CENTERLINE_FAILURE
    message = 'independent centerline geometry or characteristic invariant gate failed'
  elif not entropy_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.ENTROPY_FAILURE
    message = 'independent variable-entropy transport or lineage gate failed'
  elif not ambient_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.AMBIENT_BOUNDARY_FAILURE
    message = 'independent ambient geometry or pressure-lineage gate failed'
  elif not momentum_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.RESIDUAL_FAILURE
    message = 'moving-interface normal-momentum residual exceeds its declared research tolerance'
  elif not flags_verified:
    status = MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus.FLAG_FAILURE
    message = 'joint result weakened its canonical or production claim boundary'
  else:
    status = (
      MocEulerTwoSidedInterfaceFieldJointClosureAuditStatus
      .CONVERGED_RESEARCH_JOINT_CLOSURE
    )
    message = (
      'independent joint audit passed moving response, exact field re-solve, '
      'physical field, centerline, entropy transport, ambient, and residual '
      'gates; canonical and production promotion remain blocked'
    )
  ####
  return _failure(status, message, **common)
####
