"""Independent audit for bounded entropy-field shock coupling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.euler_entropy_characteristic_coupling import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus,
)
from exhaust_plume.models.moc.free_boundary import MocFreeBoundaryShockStatus
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_SHOCK_COUPLING_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_shock_coupling',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_SHOCK_COUPLING_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-shock-coupling-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent bounded shock-coupling audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_audit'
  )
  CONVERGED_LOCAL_BOUNDARY_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_shock_coupling_boundary_audit'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'entropy_characteristic_shock_coupling_field_failure'
  HANDOFF_FAILURE = 'entropy_characteristic_shock_coupling_handoff_failure'
  SHOCK_FAILURE = 'entropy_characteristic_shock_coupling_shock_failure'
  PATH_COVERAGE_FAILURE = (
    'entropy_characteristic_shock_coupling_path_coverage_failure'
  )
  STATUS_FAILURE = 'entropy_characteristic_shock_coupling_status_failure'
  FLAG_FAILURE = 'entropy_characteristic_shock_coupling_flag_failure'


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAudit:
  """Independent field, path-coverage, status, and fidelity evidence."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
  operator_id: str
  coupling_status: str | None
  shock_status: str | None
  field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None
  incoming_handoff_verified: bool
  path_coverage_verified: bool
  status_consistent: bool
  covered_sample_count: int
  first_missing_sample_index: int | None
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  termination_reason: str | None
  maximum_state_residual: float | None = None
  maximum_pressure_residual: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus'
      )
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    if self.field_audit is not None and not isinstance(
      self.field_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
    ):
      raise TypeError(
        'field_audit must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit or None'
      )
    for name in (
      'coupling_status',
      'shock_status',
      'termination_reason',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
    if (
      isinstance(self.covered_sample_count, bool)
      or not isinstance(self.covered_sample_count, int)
      or self.covered_sample_count < 0
    ):
      raise ValueError('covered_sample_count must be a nonnegative integer')
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError(
        'first_missing_sample_index must be a nonnegative integer or None'
      )
    for name in (
      'incoming_handoff_verified',
      'path_coverage_verified',
      'status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    for name in ('maximum_state_residual', 'maximum_pressure_residual'):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      object.__setattr__(self, name, numeric)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .CONVERGED_LOCAL_AUDIT,
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT,
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.field_audit is not None
      and self.field_audit.local_consistency_verified
      and self.incoming_handoff_verified
      and (
        self.path_coverage_verified
        or (
          self.status
          is MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
          .CONVERGED_LOCAL_BOUNDARY_AUDIT
          and self.status_consistent
        )
      )
      and self.status_consistent
      and self.fidelity_flags_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'coupling_status': self.coupling_status,
      'shock_status': self.shock_status,
      'field_audit': (
        None if self.field_audit is None else self.field_audit.as_report()
      ),
      'incoming_handoff_verified': self.incoming_handoff_verified,
      'path_coverage_verified': self.path_coverage_verified,
      'status_consistent': self.status_consistent,
      'covered_sample_count': self.covered_sample_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'termination_reason': self.termination_reason,
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus,
  message: str,
  *,
  coupling_status: str | None = None,
  shock_status: str | None = None,
  field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None = None,
  incoming_handoff_verified: bool = False,
  path_coverage_verified: bool = False,
  status_consistent: bool = False,
  covered_sample_count: int = 0,
  first_missing_sample_index: int | None = None,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  fidelity_flags_verified: bool = False,
  termination_reason: str | None = None,
  maximum_state_residual: float | None = None,
  maximum_pressure_residual: float | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_SHOCK_COUPLING_AUDIT_OPERATOR_ID
    ),
    coupling_status=coupling_status,
    shock_status=shock_status,
    field_audit=field_audit,
    incoming_handoff_verified=incoming_handoff_verified,
    path_coverage_verified=path_coverage_verified,
    status_consistent=status_consistent,
    covered_sample_count=covered_sample_count,
    first_missing_sample_index=first_missing_sample_index,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    fidelity_flags_verified=fidelity_flags_verified,
    termination_reason=termination_reason,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_shock_coupling(
  coupling: MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAudit:
  """Recompute field and shock-path coverage without rerunning the solver."""

  if not isinstance(
    coupling,
    MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .INVALID_INPUT,
      'coupling must be a MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingResult',
    )
  position_tolerance_value = float(position_tolerance_m)
  state_tolerance_value = float(state_tolerance)
  if (
    not isfinite(position_tolerance_value)
    or position_tolerance_value <= 0.0
    or not isfinite(state_tolerance_value)
    or state_tolerance_value <= 0.0
  ):
    raise ValueError('coupling audit tolerances must be finite and positive')
  field = coupling.field
  if field is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .FIELD_FAILURE,
      'coupling did not retain an entropy-characteristic field',
      coupling_status=coupling.status.value,
    )
  field_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
    field,
    position_tolerance_m=position_tolerance_value,
  )
  if not field_audit.local_consistency_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .FIELD_FAILURE,
      'the retained entropy-characteristic field failed its independent audit',
      coupling_status=coupling.status.value,
      field_audit=field_audit,
    )
  fidelity_flags_verified = bool(
    coupling.physical_closure_verified is False
    and coupling.chain_promotion_blocked
    and coupling.production_claim_allowed is False
  )
  if not fidelity_flags_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .FLAG_FAILURE,
      'bounded entropy-characteristic shock coupling weakened its fidelity boundary',
      coupling_status=coupling.status.value,
      field_audit=field_audit,
      fidelity_flags_verified=False,
    )
  incoming_handoff_verified = coupling.incoming_handoff == field.continuation_boundary
  if not incoming_handoff_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .HANDOFF_FAILURE,
      'coupling did not retain the exact solver-owned continuation perimeter',
      coupling_status=coupling.status.value,
      field_audit=field_audit,
      incoming_handoff_verified=False,
    )
  shock = coupling.shock
  if shock is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .SHOCK_FAILURE,
      'coupling did not retain the attached-shock attempt',
      coupling_status=coupling.status.value,
      field_audit=field_audit,
      incoming_handoff_verified=True,
    )

  state_residuals: list[float] = []
  pressure_residuals: list[float] = []
  covered_count = 0
  first_missing: int | None = None
  for index, (point, expected_state, expected_pressure) in enumerate(
    zip(
      shock.shock_points_m,
      shock.upstream_states,
      shock.upstream_pressure_Pa,
      strict=True,
    )
  ):
    actual_state = field.state_at(
      point,
      position_tolerance_m=position_tolerance_value,
    )
    actual_pressure = field.static_pressure_at(
      point,
      position_tolerance_m=position_tolerance_value,
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
    if (
      state_residuals[-1] > state_tolerance_value * max(
        1.0,
        abs(actual_state.theta_rad),
        abs(expected_state.theta_rad),
        abs(actual_state.mach),
        abs(expected_state.mach),
        abs(actual_state.gamma),
        abs(expected_state.gamma),
      )
      or pressure_residuals[-1] > state_tolerance_value * max(
        1.0,
        abs(actual_pressure),
        abs(expected_pressure),
      )
    ):
      first_missing = index
      break
    covered_count += 1
  if (
    first_missing is None
    and shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  ):
    first_missing = shock.failed_sample_index
  expected_count = shock.sample_count
  path_coverage_verified = bool(
    covered_count == expected_count
    and first_missing is None
    and shock.converged
  )
  if coupling.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
    .UPSTREAM_FIELD_BOUNDARY
  ):
    status_consistent = bool(
      shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
      and first_missing == coupling.first_missing_sample_index
      and not path_coverage_verified
    )
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT
      if status_consistent
      else MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .STATUS_FAILURE
    )
    message = (
      'independent audit reproduced the exact entropy-field handoff and the '
      'typed bounded upstream-field stop; physical reflected closure remains '
      'pending'
      if status_consistent
      else 'coupling boundary status did not match the independently measured shock path'
    )
  elif coupling.status is (
    MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
    .CONVERGED_BOUNDED_ATTEMPT
  ):
    status_consistent = bool(shock.converged and path_coverage_verified)
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .CONVERGED_LOCAL_AUDIT
      if status_consistent
      else MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .PATH_COVERAGE_FAILURE
    )
    message = (
      'independent audit reproduced complete bounded upstream coverage for '
      'the attached-shock attempt; physical reflected closure remains pending'
      if status_consistent
      else 'independent shock-path sampling did not reproduce complete bounded coverage'
    )
  else:
    status_consistent = bool(
      not shock.converged
      and coupling.status is (
        MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingStatus
        .SHOCK_SOLVER_FAILURE
      )
    )
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT
      if status_consistent
      else MocEulerAmbientFirstWedgeEntropyCharacteristicShockCouplingAuditStatus
      .STATUS_FAILURE
    )
    message = (
      'independent audit reproduced the bounded shock-solver failure without '
      'weakening the promotion barrier'
      if status_consistent
      else 'coupling status did not match the retained shock result'
    )
  maximum_state_residual = max(state_residuals, default=None)
  maximum_pressure_residual = max(pressure_residuals, default=None)
  if not status_consistent:
    return _failure(
      audit_status,
      message,
      coupling_status=coupling.status.value,
      shock_status=shock.status.value,
      field_audit=field_audit,
      incoming_handoff_verified=True,
      path_coverage_verified=path_coverage_verified,
      status_consistent=False,
      fidelity_flags_verified=True,
      covered_sample_count=covered_count,
      first_missing_sample_index=first_missing,
      termination_reason=coupling.as_chain_termination_decision().reason.value,
      maximum_state_residual=maximum_state_residual,
      maximum_pressure_residual=maximum_pressure_residual,
    )
  return _failure(
    audit_status,
    message,
    coupling_status=coupling.status.value,
    shock_status=shock.status.value,
    field_audit=field_audit,
    incoming_handoff_verified=True,
    path_coverage_verified=path_coverage_verified,
    status_consistent=True,
    fidelity_flags_verified=True,
    covered_sample_count=covered_count,
    first_missing_sample_index=first_missing,
    termination_reason=coupling.as_chain_termination_decision().reason.value,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
  )
