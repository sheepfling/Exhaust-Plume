"""Independent audit for exact physical-field continuation profiles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfile,
  MocPhysicalFieldContinuationProfileResult,
  MocPhysicalFieldContinuationProfileStatus,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceSample,
)

__all__ = (
  'MOC_PHYSICAL_FIELD_CONTINUATION_PROFILE_OPERATOR_ID',
  'MocPhysicalFieldContinuationProfileAuditStatus',
  'MocPhysicalFieldContinuationProfileAudit',
  'measure_moc_physical_field_continuation_profile',
)


MOC_PHYSICAL_FIELD_CONTINUATION_PROFILE_OPERATOR_ID = (
  'op.moc.physical-field.continuation-profile-audit'
)


class MocPhysicalFieldContinuationProfileAuditStatus(str, Enum):
  """Outcome of independently re-sampling a continuation profile."""

  VERIFIED = 'verified'
  RESULT_FAILURE = 'result_failure'
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldContinuationProfileAudit:
  """Independent evidence for one exact physical-field section handoff."""

  status: MocPhysicalFieldContinuationProfileAuditStatus
  result_status: MocPhysicalFieldContinuationProfileStatus
  operator_id: str = MOC_PHYSICAL_FIELD_CONTINUATION_PROFILE_OPERATOR_ID
  rederived: bool = False
  field_lineage_verified: bool = False
  field_sampling_verified: bool = False
  sample_count: int = 0
  maximum_state_residual: float | None = None
  maximum_static_pressure_residual_Pa: float | None = None
  maximum_total_pressure_residual_Pa: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldContinuationProfileAuditStatus,
    ):
      raise TypeError(
        'status must be a MocPhysicalFieldContinuationProfileAuditStatus'
      )
    ####
    if not isinstance(
      self.result_status,
      MocPhysicalFieldContinuationProfileStatus,
    ):
      raise TypeError(
        'result_status must be a MocPhysicalFieldContinuationProfileStatus'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 0
    ):
      raise ValueError('sample_count must be a nonnegative integer')
    ####
    for name in (
      'maximum_state_residual',
      'maximum_static_pressure_residual_Pa',
      'maximum_total_pressure_residual_Pa',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'rederived',
      'field_lineage_verified',
      'field_sampling_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the retained profile matches independently sampled states."""

    return self.status is MocPhysicalFieldContinuationProfileAuditStatus.VERIFIED
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'result_status': self.result_status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'rederived': self.rederived,
      'field_lineage_verified': self.field_lineage_verified,
      'field_sampling_verified': self.field_sampling_verified,
      'sample_count': self.sample_count,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_static_pressure_residual_Pa': (
        self.maximum_static_pressure_residual_Pa
      ),
      'maximum_total_pressure_residual_Pa': (
        self.maximum_total_pressure_residual_Pa
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'message': self.message,
    }
  ####
####


def _static_pressure(
  mach: float,
  gamma: float,
  total_pressure_Pa: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  return total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
####


def _sample_residual(
  actual: MocTransonicShockInterfaceSample,
  expected: MocTransonicShockInterfaceSample,
) -> tuple[float, float, float]:
  state_residual = max(
    abs(actual.point_m[0] - expected.point_m[0]),
    abs(actual.point_m[1] - expected.point_m[1]),
    abs(actual.mach - expected.mach),
    abs(actual.flow_angle_rad - expected.flow_angle_rad),
    abs(actual.gamma - expected.gamma),
  )
  static_residual = abs(
    actual.static_pressure_Pa - expected.static_pressure_Pa
  )
  total_residual = abs(actual.total_pressure_Pa - expected.total_pressure_Pa)
  return state_residual, static_residual, total_residual
####


def _failure(
  result: MocPhysicalFieldContinuationProfileResult,
  message: str,
  *,
  field_lineage_verified: bool = False,
  field_sampling_verified: bool = False,
  sample_count: int = 0,
  maximum_state_residual: float | None = None,
  maximum_static_pressure_residual_Pa: float | None = None,
  maximum_total_pressure_residual_Pa: float | None = None,
) -> MocPhysicalFieldContinuationProfileAudit:
  return MocPhysicalFieldContinuationProfileAudit(
    status=MocPhysicalFieldContinuationProfileAuditStatus.RESULT_FAILURE,
    result_status=result.status,
    rederived=False,
    field_lineage_verified=field_lineage_verified,
    field_sampling_verified=field_sampling_verified,
    sample_count=sample_count,
    maximum_state_residual=maximum_state_residual,
    maximum_static_pressure_residual_Pa=maximum_static_pressure_residual_Pa,
    maximum_total_pressure_residual_Pa=maximum_total_pressure_residual_Pa,
    message=message,
  )
####


def measure_moc_physical_field_continuation_profile(
  result: MocPhysicalFieldContinuationProfileResult,
) -> MocPhysicalFieldContinuationProfileAudit:
  """Re-sample the retained field and rederive the section profile."""

  if not isinstance(
    result,
    MocPhysicalFieldContinuationProfileResult,
  ):
    raise TypeError(
      'result must be a MocPhysicalFieldContinuationProfileResult'
    )
  ####
  field = result.field
  request = result.request
  profile = result.profile
  field_lineage_verified = bool(
    field is request.field
    and field is not None
    and field.converged
    and field.physical_closure_verified
    and field.state_sampling_available
  )
  if not field_lineage_verified:
    return _failure(
      result,
      'continuation result does not retain the requested closed physical field',
    )
  ####
  if profile is None or not isinstance(
    profile,
    MocPhysicalFieldContinuationProfile,
  ):
    return _failure(
      result,
      'continuation result retained no profile to remeasure',
      field_lineage_verified=True,
    )
  ####
  if profile != result.profile or profile.profile_id != request.profile_id:
    return _failure(
      result,
      'continuation profile identity does not match its request',
      field_lineage_verified=True,
    )
  ####
  expected_samples: list[MocTransonicShockInterfaceSample] = []
  try:
    for point in request.sample_points_m:
      state = field.state_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      total_pressure = field.total_pressure_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      if state is None or total_pressure is None:
        return _failure(
          result,
          f'independent field resampling returned no state at {point}',
          field_lineage_verified=True,
          field_sampling_verified=False,
          sample_count=len(expected_samples),
        )
      ####
      expected_samples.append(
        MocTransonicShockInterfaceSample(
          point_m=point,
          mach=state.mach,
          flow_angle_rad=state.theta_rad,
          static_pressure_Pa=_static_pressure(
            state.mach,
            state.gamma,
            total_pressure,
          ),
          total_pressure_Pa=total_pressure,
          gamma=state.gamma,
        )
      )
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      result,
      f'independent physical-field resampling raised: {error}',
      field_lineage_verified=True,
      field_sampling_verified=False,
      sample_count=len(expected_samples),
    )
  ####
  actual_samples = profile.samples
  if len(actual_samples) != len(expected_samples):
    return _failure(
      result,
      'continuation profile sample count does not match independent resampling',
      field_lineage_verified=True,
      field_sampling_verified=True,
      sample_count=len(expected_samples),
    )
  ####
  residuals = tuple(
    _sample_residual(actual, expected)
    for actual, expected in zip(actual_samples, expected_samples, strict=True)
  )
  maximum_state = max(residual[0] for residual in residuals)
  maximum_static = max(residual[1] for residual in residuals)
  maximum_total = max(residual[2] for residual in residuals)
  scale_static = max(
    max(sample.static_pressure_Pa for sample in expected_samples),
    1.0,
  )
  scale_total = max(
    max(sample.total_pressure_Pa for sample in expected_samples),
    1.0,
  )
  rederived = bool(
    all(
      residual[0] <= request.state_tolerance
      and residual[1] / scale_static <= request.pressure_tolerance
      and residual[2] / scale_total <= request.pressure_tolerance
      for residual in residuals
    )
    and result.status is (
      MocPhysicalFieldContinuationProfileStatus
      .CONVERGED_FIELD_CONTINUATION_PROFILE
    )
    and result.field_lineage_verified
    and result.field_sampling_verified
  )
  return MocPhysicalFieldContinuationProfileAudit(
    status=(
      MocPhysicalFieldContinuationProfileAuditStatus.VERIFIED
      if rederived
      else MocPhysicalFieldContinuationProfileAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=rederived,
    field_lineage_verified=True,
    field_sampling_verified=True,
    sample_count=len(expected_samples),
    maximum_state_residual=maximum_state,
    maximum_static_pressure_residual_Pa=maximum_static,
    maximum_total_pressure_residual_Pa=maximum_total,
    message=(
      'exact physical-field state, static-pressure, and total-pressure samples '
      'were independently rederived'
      if rederived
      else 'reported continuation profile does not match independent field samples'
    ),
  )
####
