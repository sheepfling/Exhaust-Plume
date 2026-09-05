"""Independent measurement for the bounded transonic field attachment seam."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isclose, isfinite
from typing import Any

from exhaust_plume.models.moc.transonic_attachment import (
  MocTransonicShockFieldAttachmentResult,
  MocTransonicShockFieldAttachmentStatus,
  solve_moc_transonic_shock_field_attachment,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicShockGeometryAudit,
  measure_moc_transonic_shock_geometry,
)

__all__ = (
  'MocTransonicShockFieldAttachmentAuditStatus',
  'MocTransonicShockFieldAttachmentAudit',
  'measure_moc_transonic_shock_field_attachment',
)


class MocTransonicShockFieldAttachmentAuditStatus(str, Enum):
  """Independent audit outcome for a bounded transonic attachment."""

  VERIFIED = 'verified-transonic-shock-field-attachment-audit'
  RESULT_FAILURE = 'transonic-shock-field-attachment-result-failure'
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockFieldAttachmentAudit:
  """Re-derived candidate selection and scalar geometry evidence."""

  status: MocTransonicShockFieldAttachmentAuditStatus
  result_status: MocTransonicShockFieldAttachmentStatus
  rederived: bool
  selected_point_residual_m: float | None
  field_match_verified: bool
  geometry_binding_verified: bool
  geometry_audit: MocTransonicShockGeometryAudit | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocTransonicShockFieldAttachmentAuditStatus,
    ):
      raise TypeError(
        'status must be a MocTransonicShockFieldAttachmentAuditStatus'
      )
    ####
    if not isinstance(
      self.result_status,
      MocTransonicShockFieldAttachmentStatus,
    ):
      raise TypeError(
        'result_status must be a MocTransonicShockFieldAttachmentStatus'
      )
    ####
    if self.selected_point_residual_m is not None:
      residual = float(self.selected_point_residual_m)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'selected_point_residual_m must be finite and nonnegative when supplied'
        )
      ####
      object.__setattr__(self, 'selected_point_residual_m', residual)
    ####
    for name in ('rederived', 'field_match_verified', 'geometry_binding_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.geometry_audit is not None and not isinstance(
      self.geometry_audit,
      MocTransonicShockGeometryAudit,
    ):
      raise TypeError(
        'geometry_audit must be a MocTransonicShockGeometryAudit or None'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicShockFieldAttachmentAuditStatus.VERIFIED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'result_status': self.result_status.value,
      'converged': self.converged,
      'rederived': self.rederived,
      'selected_point_residual_m': self.selected_point_residual_m,
      'field_match_verified': self.field_match_verified,
      'geometry_binding_verified': self.geometry_binding_verified,
      'geometry_audit': (
        None if self.geometry_audit is None else self.geometry_audit.as_report()
      ),
      'physical_closure_verified': False,
      'production_claim_allowed': False,
      'claim_status': (
        'research-only-bounded-attachment-audit; mixed-regime closure, '
        'shock-cell promotion, and external validation remain open'
      ),
      'message': self.message,
    }
  ####
####


def _close(actual: float | None, expected: float | None) -> bool:
  if actual is None or expected is None:
    return actual is expected
  ####
  return bool(isclose(float(actual), float(expected), rel_tol=3.0e-6, abs_tol=1.0e-10))
####


def _geometry_matches(
  reported: MocTransonicShockGeometryAudit | None,
  expected: MocTransonicShockGeometryAudit | None,
) -> bool:
  if reported is None or expected is None:
    return reported is expected
  ####
  return bool(
    reported.status is expected.status
    and reported.result_status is expected.result_status
    and reported.rederived == expected.rederived
    and _close(reported.point_residual_m, expected.point_residual_m)
    and _close(reported.normal_angle_residual_rad, expected.normal_angle_residual_rad)
    and _close(reported.tangent_angle_residual_rad, expected.tangent_angle_residual_rad)
    and _close(reported.mass_flux_residual, expected.mass_flux_residual)
    and _close(reported.momentum_flux_residual, expected.momentum_flux_residual)
    and _close(reported.energy_flux_residual, expected.energy_flux_residual)
    and reported.geometry_binding_verified == expected.geometry_binding_verified
  )
####


def measure_moc_transonic_shock_field_attachment(
  result: MocTransonicShockFieldAttachmentResult,
) -> MocTransonicShockFieldAttachmentAudit:
  """Re-select the field node and independently remeasure scalar geometry."""

  if not isinstance(result, MocTransonicShockFieldAttachmentResult):
    raise TypeError(
      'result must be a MocTransonicShockFieldAttachmentResult'
    )
  ####
  expected = solve_moc_transonic_shock_field_attachment(result.request)
  field_match_verified = bool(
    result.status is expected.status
    and result.selected_node_index == expected.selected_node_index
    and (
      result.selected_point_m is None
      or expected.selected_point_m is None
      or hypot(
        result.selected_point_m[0] - expected.selected_point_m[0],
        result.selected_point_m[1] - expected.selected_point_m[1],
      ) <= 1.0e-10
    )
    and _close(result.sampled_upstream_static_pressure_Pa, expected.sampled_upstream_static_pressure_Pa)
    and _close(result.sampled_upstream_total_pressure_Pa, expected.sampled_upstream_total_pressure_Pa)
    and _close(result.mach_residual, expected.mach_residual)
    and _close(result.flow_angle_residual_rad, expected.flow_angle_residual_rad)
    and _close(result.gamma_residual, expected.gamma_residual)
    and _close(result.static_pressure_residual, expected.static_pressure_residual)
    and _close(result.total_pressure_residual, expected.total_pressure_residual)
  )
  if result.geometry is None:
    reported_geometry_audit = None
  else:
    reported_geometry_audit = measure_moc_transonic_shock_geometry(result.geometry)
  ####
  geometry_binding_verified = bool(
    result.geometry is not None
    and expected.geometry is not None
    and reported_geometry_audit is not None
    and reported_geometry_audit.geometry_binding_verified
    and _close(
      result.geometry.shock_point_m[0],
      expected.geometry.shock_point_m[0],
    )
    and _close(
      result.geometry.shock_point_m[1],
      expected.geometry.shock_point_m[1],
    )
    and _close(
      result.geometry.normal_alignment_residual_rad,
      expected.geometry.normal_alignment_residual_rad,
    )
    and _close(
      result.geometry.mass_flux_residual,
      expected.geometry.mass_flux_residual,
    )
    and _close(
      result.geometry.momentum_flux_residual,
      expected.geometry.momentum_flux_residual,
    )
    and _close(
      result.geometry.energy_flux_residual,
      expected.geometry.energy_flux_residual,
    )
  )
  verified = bool(
    expected.status is MocTransonicShockFieldAttachmentStatus
    .CONVERGED_BOUNDED_ATTACHMENT
    and field_match_verified
    and geometry_binding_verified
  )
  return MocTransonicShockFieldAttachmentAudit(
    status=(
      MocTransonicShockFieldAttachmentAuditStatus.VERIFIED
      if verified
      else MocTransonicShockFieldAttachmentAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=True,
    selected_point_residual_m=(
      None
      if result.selected_point_m is None or expected.selected_point_m is None
      else hypot(
        result.selected_point_m[0] - expected.selected_point_m[0],
        result.selected_point_m[1] - expected.selected_point_m[1],
      )
    ),
    field_match_verified=field_match_verified,
    geometry_binding_verified=geometry_binding_verified,
    geometry_audit=reported_geometry_audit,
    message=(
      'solver-owned field selection and scalar geometry were independently '
      'remeasured'
      if verified
      else 'reported transonic field attachment does not match independent re-measurement'
    ),
  )
####
