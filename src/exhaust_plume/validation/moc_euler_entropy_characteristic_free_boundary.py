"""Independent audit for entropy-field reflected/free-boundary coupling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.euler_entropy_characteristic_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus,
)
from exhaust_plume.models.moc.free_boundary import MocFreeBoundaryShockStatus
from exhaust_plume.validation.moc_euler import (
  MocPhysicalFieldEulerAudit,
  measure_moc_physical_field_euler_audit,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FREE_BOUNDARY_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_free_boundary',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FREE_BOUNDARY_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-free-boundary-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent reflected/free-boundary audit."""

  CONVERGED_LOCAL_BOUNDARY_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_free_boundary_boundary_audit'
  )
  CONVERGED_LOCAL_CLOSED_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_free_boundary_closed_audit'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'entropy_characteristic_free_boundary_field_failure'
  HANDOFF_FAILURE = 'entropy_characteristic_free_boundary_handoff_failure'
  PATH_COVERAGE_FAILURE = (
    'entropy_characteristic_free_boundary_path_coverage_failure'
  )
  ATTACHMENT_FAILURE = (
    'entropy_characteristic_free_boundary_attachment_failure'
  )
  REFLECTED_FIELD_FAILURE = (
    'entropy_characteristic_free_boundary_reflected_field_failure'
  )
  STATUS_FAILURE = 'entropy_characteristic_free_boundary_status_failure'
  FLAG_FAILURE = 'entropy_characteristic_free_boundary_flag_failure'


def _state_matches(
  actual: Any,
  expected: Any,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  try:
    return bool(
      abs(actual.x_m - expected.x_m) <= position_tolerance_m
      and abs(actual.y_m - expected.y_m) <= position_tolerance_m
      and abs(actual.theta_rad - expected.theta_rad)
      <= state_tolerance * max(
        1.0,
        abs(actual.theta_rad),
        abs(expected.theta_rad),
      )
      and abs(actual.mach - expected.mach)
      <= state_tolerance * max(1.0, abs(actual.mach), abs(expected.mach))
      and abs(actual.gamma - expected.gamma)
      <= state_tolerance * max(1.0, abs(actual.gamma), abs(expected.gamma))
    )
  except (AttributeError, TypeError, ValueError):
    return False


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit:
  """Independent evidence for the bounded reflected/free-boundary attempt."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
  operator_id: str
  result_status: str | None
  physical_field_status: str | None
  attachment_status: str | None
  shock_status: str | None
  field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None
  physical_field_euler_audit: MocPhysicalFieldEulerAudit | None
  incoming_handoff_verified: bool
  path_coverage_verified: bool
  status_consistent: bool
  reflected_free_boundary_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  external_validation_required: bool
  fidelity_flags_verified: bool
  shock_sample_count: int
  covered_sample_count: int
  first_missing_sample_index: int | None
  ambient_boundary_sample_count: int
  maximum_state_residual: float | None
  maximum_pressure_residual: float | None
  termination_reason: str | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus'
      )
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    for name in (
      'result_status',
      'physical_field_status',
      'attachment_status',
      'shock_status',
      'termination_reason',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
    if self.field_audit is not None and not isinstance(
      self.field_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
    ):
      raise TypeError(
        'field_audit must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit or None'
      )
    if self.physical_field_euler_audit is not None and not isinstance(
      self.physical_field_euler_audit,
      MocPhysicalFieldEulerAudit,
    ):
      raise TypeError(
        'physical_field_euler_audit must be a MocPhysicalFieldEulerAudit or None'
      )
    for name in (
      'shock_sample_count',
      'covered_sample_count',
      'ambient_boundary_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError(
        'first_missing_sample_index must be a nonnegative integer or None'
      )
    for name in ('maximum_state_residual', 'maximum_pressure_residual'):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    for name in (
      'incoming_handoff_verified',
      'path_coverage_verified',
      'status_consistent',
      'reflected_free_boundary_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_CLOSED_AUDIT,
    )

  @property
  def local_consistency_verified(self) -> bool:
    closed_gate = (
      self.status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_CLOSED_AUDIT
    )
    return bool(
      self.converged
      and self.field_audit is not None
      and self.field_audit.local_consistency_verified
      and self.incoming_handoff_verified
      and self.status_consistent
      and (self.path_coverage_verified or not closed_gate)
      and (not closed_gate or self.reflected_free_boundary_verified)
      and (not closed_gate or self.physical_field_euler_audit is not None)
      and (not closed_gate or self.physical_field_euler_audit.local_euler_consistency_verified)
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and self.external_validation_required
      and self.fidelity_flags_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'physical_field_status': self.physical_field_status,
      'attachment_status': self.attachment_status,
      'shock_status': self.shock_status,
      'field_audit': None if self.field_audit is None else self.field_audit.as_report(),
      'physical_field_euler_audit': (
        None
        if self.physical_field_euler_audit is None
        else self.physical_field_euler_audit.as_report()
      ),
      'incoming_handoff_verified': self.incoming_handoff_verified,
      'path_coverage_verified': self.path_coverage_verified,
      'status_consistent': self.status_consistent,
      'reflected_free_boundary_verified': self.reflected_free_boundary_verified,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'shock_sample_count': self.shock_sample_count,
      'covered_sample_count': self.covered_sample_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'ambient_boundary_sample_count': self.ambient_boundary_sample_count,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'termination_reason': self.termination_reason,
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  physical_field_status: str | None = None,
  attachment_status: str | None = None,
  shock_status: str | None = None,
  field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None = None,
  physical_field_euler_audit: MocPhysicalFieldEulerAudit | None = None,
  incoming_handoff_verified: bool = False,
  path_coverage_verified: bool = False,
  status_consistent: bool = False,
  reflected_free_boundary_verified: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  external_validation_required: bool = True,
  fidelity_flags_verified: bool = False,
  shock_sample_count: int = 0,
  covered_sample_count: int = 0,
  first_missing_sample_index: int | None = None,
  ambient_boundary_sample_count: int = 0,
  maximum_state_residual: float | None = None,
  maximum_pressure_residual: float | None = None,
  termination_reason: str | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FREE_BOUNDARY_AUDIT_OPERATOR_ID
    ),
    result_status=result_status,
    physical_field_status=physical_field_status,
    attachment_status=attachment_status,
    shock_status=shock_status,
    field_audit=field_audit,
    physical_field_euler_audit=physical_field_euler_audit,
    incoming_handoff_verified=incoming_handoff_verified,
    path_coverage_verified=path_coverage_verified,
    status_consistent=status_consistent,
    reflected_free_boundary_verified=reflected_free_boundary_verified,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    external_validation_required=external_validation_required,
    fidelity_flags_verified=fidelity_flags_verified,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_sample_count,
    first_missing_sample_index=first_missing_sample_index,
    ambient_boundary_sample_count=ambient_boundary_sample_count,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    termination_reason=termination_reason,
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_free_boundary(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAudit:
  """Recompute field, path, closure, and fidelity evidence independently."""

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .INVALID_INPUT,
      'result must be a MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryResult',
    )
  tolerances = (
    float(position_tolerance_m),
    float(state_tolerance),
    float(shock_residual_tolerance),
    float(cell_residual_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('free-boundary audit tolerances must be finite and positive')
  field = result.field
  if field is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .FIELD_FAILURE,
      'free-boundary result did not retain its entropy-characteristic field',
      result_status=result.status.value,
    )
  field_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
    field,
    position_tolerance_m=position_tolerance_m,
  )
  if not field_audit.local_consistency_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .FIELD_FAILURE,
      'retained entropy-characteristic field failed its independent audit',
      result_status=result.status.value,
      physical_field_status=result.physical_field_status,
      attachment_status=result.attachment_status,
      field_audit=field_audit,
    )
  incoming_handoff_verified = result.incoming_handoff == field.continuation_boundary
  if not incoming_handoff_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .HANDOFF_FAILURE,
      'free-boundary result did not retain the exact entropy-field perimeter',
      result_status=result.status.value,
      physical_field_status=result.physical_field_status,
      attachment_status=result.attachment_status,
      field_audit=field_audit,
    )
  shock = result.shock
  shock_status = None if shock is None else shock.status.value
  attachment_status = result.attachment_status
  state_residuals: list[float] = []
  pressure_residuals: list[float] = []
  covered_count = 0
  first_missing: int | None = None
  if shock is not None:
    try:
      path = zip(
        shock.shock_points_m,
        shock.upstream_states,
        shock.upstream_pressure_Pa,
        strict=True,
      )
      for index, (point, expected_state, expected_pressure) in enumerate(path):
        actual_state = field.state_at(
          point,
          position_tolerance_m=position_tolerance_m,
        )
        actual_pressure = field.static_pressure_at(
          point,
          position_tolerance_m=position_tolerance_m,
        )
        if actual_state is None or actual_pressure is None:
          first_missing = index
          break
        state_residuals.append(
          max(
            abs(actual_state.x_m - expected_state.x_m),
            abs(actual_state.y_m - expected_state.y_m),
            abs(actual_state.theta_rad - expected_state.theta_rad),
            abs(actual_state.mach - expected_state.mach),
            abs(actual_state.gamma - expected_state.gamma),
          )
        )
        pressure_residuals.append(abs(actual_pressure - expected_pressure))
        if not _state_matches(
          actual_state,
          expected_state,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        ) or abs(actual_pressure - expected_pressure) > state_tolerance * max(
          1.0,
          abs(actual_pressure),
          abs(expected_pressure),
        ):
          first_missing = index
          break
        covered_count += 1
    except (TypeError, ValueError):
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
        .PATH_COVERAGE_FAILURE,
        'retained shock path arrays do not have matching typed lengths',
        result_status=result.status.value,
        physical_field_status=result.physical_field_status,
        attachment_status=attachment_status,
        shock_status=shock_status,
        field_audit=field_audit,
        incoming_handoff_verified=True,
      )
  shock_sample_count = 0 if shock is None else len(shock.shock_points_m)
  if (
    shock is not None
    and shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
    and first_missing is None
  ):
    first_missing = shock.failed_sample_index
  path_coverage_verified = bool(
    shock is not None
    and shock.converged
    and covered_count == shock_sample_count
    and first_missing is None
  )
  ambient_boundary_sample_count = 0
  if result.physical_field is not None and result.physical_field.ambient_attachment is not None:
    ambient_march = result.physical_field.ambient_attachment.ambient_march
    if ambient_march is not None:
      ambient_boundary_sample_count = len(ambient_march.boundary_samples)

  physical_field_euler_audit: MocPhysicalFieldEulerAudit | None = None
  physical_field = (
    None if result.physical_field is None else result.physical_field.field
  )
  if physical_field is not None:
    try:
      physical_field_euler_audit = measure_moc_physical_field_euler_audit(
        physical_field,
        shock_residual_tolerance=shock_residual_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
        position_tolerance_m=position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
        .REFLECTED_FIELD_FAILURE,
        f'independent physical-field Euler audit raised: {error}',
        result_status=result.status.value,
        physical_field_status=result.physical_field_status,
        attachment_status=attachment_status,
        shock_status=shock_status,
        field_audit=field_audit,
        incoming_handoff_verified=True,
        path_coverage_verified=path_coverage_verified,
        shock_sample_count=shock_sample_count,
        covered_sample_count=covered_count,
        first_missing_sample_index=first_missing,
        ambient_boundary_sample_count=ambient_boundary_sample_count,
      )
  reflected_free_boundary_verified = bool(
    result.physical_field is not None
    and result.physical_field.physical_closure_verified
    and physical_field is not None
    and physical_field.physical_closure_verified
    and physical_field_euler_audit is not None
    and physical_field_euler_audit.local_euler_consistency_verified
  )
  expected_boundary = bool(
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .UPSTREAM_FIELD_BOUNDARY
    and shock_status == MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE.value
    and not path_coverage_verified
    and first_missing is not None
  )
  expected_closed = bool(
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_FIELD
    and path_coverage_verified
    and reflected_free_boundary_verified
  )
  expected_attachment_failure = bool(
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .AMBIENT_ATTACHMENT_FAILURE
    and not path_coverage_verified
  )
  expected_reflected_failure = bool(
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus
    .REFLECTED_FIELD_FAILURE
    and path_coverage_verified
    and not reflected_free_boundary_verified
  )
  status_consistent = bool(
    expected_boundary
    or expected_closed
    or expected_attachment_failure
    or expected_reflected_failure
  )
  flags_verified = bool(
    result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.external_validation_required
    and (
      result.physical_field is None
      or result.physical_field.production_claim_allowed is False
    )
  )
  termination = result.as_chain_termination_decision()
  common = dict(
    result_status=result.status.value,
    physical_field_status=result.physical_field_status,
    attachment_status=attachment_status,
    shock_status=shock_status,
    field_audit=field_audit,
    physical_field_euler_audit=physical_field_euler_audit,
    incoming_handoff_verified=True,
    path_coverage_verified=path_coverage_verified,
    status_consistent=status_consistent,
    reflected_free_boundary_verified=reflected_free_boundary_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    fidelity_flags_verified=flags_verified,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_count,
    first_missing_sample_index=first_missing,
    ambient_boundary_sample_count=ambient_boundary_sample_count,
    maximum_state_residual=max(state_residuals, default=None),
    maximum_pressure_residual=max(pressure_residuals, default=None),
    termination_reason=termination.reason.value,
  )
  if not status_consistent:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .STATUS_FAILURE,
      'free-boundary result status does not match its retained path/closure evidence',
      **common,
    )
  if not flags_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .FLAG_FAILURE,
      'free-boundary result weakened its explicit non-promotion fidelity boundary',
      **common,
    )
  if expected_boundary:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT,
      'independent audit confirmed the bounded reflected/free-boundary attempt stopped at the upstream field boundary',
      **common,
    )
  if expected_closed:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_CLOSED_AUDIT,
      'independent audit confirmed the local reflected physical field; external validation remains required',
      **common,
    )
  if result.status is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus.AMBIENT_ATTACHMENT_FAILURE:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .ATTACHMENT_FAILURE
    )
  elif result.status is MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryStatus.REFLECTED_FIELD_FAILURE:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .REFLECTED_FIELD_FAILURE
    )
  else:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFreeBoundaryAuditStatus
      .PATH_COVERAGE_FAILURE
    )
  return _failure(
    audit_status,
    'free-boundary result did not pass the independent closure evidence gates',
    **common,
  )
