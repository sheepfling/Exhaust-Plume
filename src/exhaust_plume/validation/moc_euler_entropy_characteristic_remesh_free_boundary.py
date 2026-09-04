"""Independent audit for bounded remesh reflected/free-boundary probes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_entropy_characteristic_remesh_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_frontier import (
  audit_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier_path,
  extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.free_boundary import MocFreeBoundaryShockStatus
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState, inverse_prandtl_meyer_angle_rad
from exhaust_plume.validation.moc_euler import (
  MocPhysicalFieldEulerAudit,
  measure_moc_physical_field_euler_audit,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_REMESH_FREE_BOUNDARY_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_REMESH_FREE_BOUNDARY_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-remesh-free-boundary-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent bounded closure-probe audit."""

  CONVERGED_LOCAL_BOUNDARY_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary_boundary_audit'
  )
  CONVERGED_LOCAL_CLOSED_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary_closed_audit'
  )
  INVALID_INPUT = 'invalid_input'
  REMESH_FAILURE = 'entropy_characteristic_remesh_free_boundary_remesh_failure'
  HANDOFF_FAILURE = 'entropy_characteristic_remesh_free_boundary_handoff_failure'
  PATH_COVERAGE_FAILURE = (
    'entropy_characteristic_remesh_free_boundary_path_coverage_failure'
  )
  ATTACHMENT_FAILURE = (
    'entropy_characteristic_remesh_free_boundary_attachment_failure'
  )
  REFLECTED_FIELD_FAILURE = (
    'entropy_characteristic_remesh_free_boundary_reflected_field_failure'
  )
  STATUS_FAILURE = 'entropy_characteristic_remesh_free_boundary_status_failure'
  FLAG_FAILURE = 'entropy_characteristic_remesh_free_boundary_flag_failure'
####


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
  ####
####


def _triangle_weights(
  point: tuple[float, float],
  vertices: Sequence[tuple[float, float]],
  tolerance_m: float,
) -> tuple[float, float, float] | None:
  """Recompute barycentric weights for the bounded audit sampler."""

  if len(vertices) != 3:
    return None
  ####
  (ax, ay), (bx, by), (cx, cy) = vertices
  denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
  if not isfinite(denominator) or abs(denominator) <= max(
    tolerance_m * tolerance_m,
    1.0e-24,
  ):
    return None
  ####
  px, py = point
  first = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
  second = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10:
    return None
  ####
  if max(first, second, third) > 1.0 + 1.0e-10:
    return None
  ####
  return first, second, third
####


def _sample_bridge_cell(
  sample: MocEulerAmbientFirstWedgeCellSample,
  point_m: tuple[float, float],
  *,
  position_tolerance_m: float,
) -> tuple[CharacteristicState, float] | None:
  weights = _triangle_weights(
    point_m,
    sample.vertices_xr_m,
    position_tolerance_m,
  )
  if weights is None:
    return None
  ####
  try:
    theta = sum(
      weight * state.theta_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    nu = sum(
      weight * state.nu_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    inversion = inverse_prandtl_meyer_angle_rad(nu, sample.states[0].gamma)
    if not inversion.converged or inversion.value is None:
      return None
    ####
    state = CharacteristicState(
      x_m=point_m[0],
      y_m=point_m[1],
      theta_rad=theta,
      mach=inversion.value,
      gamma=sample.states[0].gamma,
    )
    total_pressure = exp(
      sum(
        weight * log(pressure)
        for weight, pressure in zip(
          weights,
          sample.total_pressure_Pa,
          strict=True,
        )
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  ####
  try:
    static_pressure = total_pressure / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  ####
  return state, static_pressure
####


def _combined_diagnostic_sample(
  remesh: Any,
  bridge_sample: MocEulerAmbientFirstWedgeCellSample | None,
  point_m: tuple[float, float],
  *,
  position_tolerance_m: float,
) -> tuple[CharacteristicState, float] | None:
  if bridge_sample is not None:
    sampled = _sample_bridge_cell(
      bridge_sample,
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is not None:
      return sampled
    ####
  ####
  state = remesh.diagnostic_state_at(
    point_m,
    position_tolerance_m=position_tolerance_m,
  )
  total_pressure = remesh.diagnostic_total_pressure_at(
    point_m,
    position_tolerance_m=position_tolerance_m,
  )
  if state is None or total_pressure is None:
    return None
  ####
  try:
    static_pressure = total_pressure / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  ####
  return state, static_pressure
####


def _independent_frontier_bridge(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
  frontier: Any,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> tuple[bool, MocEulerAmbientFirstWedgeCellSample | None, str | None]:
  """Audit the cached C+ bridge using independent residual equations."""

  if not result.outgoing_frontier_bridge_enabled:
    return True, None, None
  ####
  segment = result.outgoing_frontier_bridge
  if (
    not frontier.converged
    or len(frontier.samples) < 2
    or segment is None
    or not segment.converged
    or segment.family is not CharacteristicFamily.PLUS
    or segment.start_state is None
    or segment.end_state is None
    or segment.start_total_pressure_Pa is None
    or segment.end_total_pressure_Pa is None
  ):
    return (
      False,
      None,
      None if segment is None else segment.status.value,
    )
  ####
  remesh = result.remesh
  gradient = None if remesh is None else remesh.source_pressure_gradient
  ambient_pressure = result.ambient_pressure_Pa
  if gradient is None or ambient_pressure is None:
    return False, None, segment.status.value
  ####
  outer = frontier.samples[0]
  axis = frontier.samples[-1]
  start = segment.start_state
  endpoint = segment.end_state
  try:
    displacement = (endpoint.x_m - start.x_m, endpoint.y_m - start.y_m)
    length = hypot(*displacement)
    start_direction = start.direction(CharacteristicFamily.PLUS)
    end_direction = endpoint.direction(CharacteristicFamily.PLUS)
    average_direction = (
      0.5 * (start_direction[0] + end_direction[0]),
      0.5 * (start_direction[1] + end_direction[1]),
    )
    average_length = hypot(*average_direction)
    geometry = (
      float('inf')
      if length <= 0.0 or average_length <= 0.0
      else (
        displacement[0] * average_direction[1]
        - displacement[1] * average_direction[0]
      ) / (length * average_length)
    )
    boundary_displacement = (
      endpoint.x_m - outer.state.x_m,
      endpoint.y_m - outer.state.y_m,
    )
    boundary_length = hypot(*boundary_displacement)
    boundary_angle = 0.5 * (outer.state.theta_rad + endpoint.theta_rad)
    boundary = (
      float('inf')
      if boundary_length <= 0.0
      else (
        boundary_displacement[0] * sin(boundary_angle)
        - boundary_displacement[1] * cos(boundary_angle)
      ) / boundary_length
    )
    average_theta = 0.5 * (start.theta_rad + endpoint.theta_rad)
    normal_gradient = (
      gradient[0] * -sin(average_theta)
      + gradient[1] * cos(average_theta)
    )
    average_mach = 0.5 * (start.mach + endpoint.mach)
    average_gamma = 0.5 * (start.gamma + endpoint.gamma)
    compatibility_source = (
      -sqrt(max(average_mach * average_mach - 1.0, 0.0))
      / (average_gamma * average_mach**3)
      * normal_gradient
      * length
    )
    compatibility = endpoint.k_plus - start.k_plus - compatibility_source
    transported_pressure = segment.start_total_pressure_Pa * exp(
      gradient[0] * (endpoint.x_m - start.x_m)
      + gradient[1] * (endpoint.y_m - start.y_m)
    )
    static_pressure = transported_pressure / (
      1.0 + 0.5 * (endpoint.gamma - 1.0) * endpoint.mach * endpoint.mach
    ) ** (endpoint.gamma / (endpoint.gamma - 1.0))
    pressure = log(static_pressure / ambient_pressure)
    geometry_residual = max(abs(geometry), abs(boundary))
    cached_residuals = (
      segment.geometry_residual,
      segment.compatibility_residual,
      segment.pressure_residual,
    )
    recomputed_residuals = (
      geometry_residual,
      abs(compatibility),
      abs(pressure),
    )
    residuals_match = all(
      cached is not None
      and isfinite(float(cached))
      and abs(float(cached) - recomputed) <= state_tolerance * max(
        1.0,
        abs(float(cached)),
        abs(recomputed),
      )
      for cached, recomputed in zip(
        cached_residuals,
        recomputed_residuals,
        strict=True,
      )
    )
    endpoints_match = bool(
      _state_matches(
        start,
        axis.state,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
      )
      and abs(segment.start_total_pressure_Pa - axis.total_pressure_Pa)
      <= state_tolerance * max(
        1.0,
        abs(segment.start_total_pressure_Pa),
        abs(axis.total_pressure_Pa),
      )
      and abs(segment.end_total_pressure_Pa - transported_pressure)
      <= state_tolerance * max(
        1.0,
        abs(segment.end_total_pressure_Pa),
        abs(transported_pressure),
      )
    )
    residuals_pass = bool(
      geometry_residual <= remesh.characteristic_residual_tolerance
      and abs(compatibility) <= remesh.characteristic_residual_tolerance
      and abs(pressure) <= remesh.pressure_lineage_tolerance
    )
    bridge_sample = MocEulerAmbientFirstWedgeCellSample(
      vertices_xr_m=(
        outer.point_m,
        axis.point_m,
        (endpoint.x_m, endpoint.y_m),
      ),
      states=(outer.state, axis.state, endpoint),
      total_pressure_Pa=(
        outer.total_pressure_Pa,
        axis.total_pressure_Pa,
        segment.end_total_pressure_Pa,
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return False, None, segment.status.value
  ####
  return (
    bool(endpoints_match and residuals_match and residuals_pass),
    bridge_sample if endpoints_match and residuals_match else None,
    segment.status.value,
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit:
  """Independent evidence for one remesh closure-probe attempt."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
  operator_id: str
  result_status: str | None
  physical_field_status: str | None
  attachment_status: str | None
  shock_status: str | None
  remesh_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit | None
  physical_field_euler_audit: MocPhysicalFieldEulerAudit | None
  incoming_handoff_verified: bool
  source_remesh_verified: bool
  source_cell_euler_residuals_verified: bool
  source_cell_euler_residuals_flag_consistent: bool
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
  maximum_state_residual: float | None
  maximum_pressure_residual: float | None
  termination_reason: str | None
  message: str = ''
  frontier_coverage_status: str | None = None
  frontier_coverage_verified: bool = False
  frontier_sample_count: int = 0
  frontier_first_exterior_sample_index: int | None = None
  frontier_first_exterior_signed_offset_m: float | None = None
  outgoing_frontier_bridge_enabled: bool = False
  outgoing_frontier_bridge_verified: bool = False
  outgoing_frontier_bridge_status: str | None = None
  coupled_handoff_consumption_verified: bool = False

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus,
    ):
      raise TypeError('status must be a remesh free-boundary audit status')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
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
      ####
    ####
    if self.remesh_audit is not None and not isinstance(
      self.remesh_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit,
    ):
      raise TypeError('remesh_audit must be typed or None')
    ####
    if self.physical_field_euler_audit is not None and not isinstance(
      self.physical_field_euler_audit,
      MocPhysicalFieldEulerAudit,
    ):
      raise TypeError('physical_field_euler_audit must be typed or None')
    ####
    for name in ('shock_sample_count', 'covered_sample_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError(
        'first_missing_sample_index must be a nonnegative integer or None'
      )
    ####
    for name in ('maximum_state_residual', 'maximum_pressure_residual'):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    if self.frontier_coverage_status is not None and not isinstance(
      self.frontier_coverage_status,
      str,
    ):
      raise TypeError('frontier_coverage_status must be a string or None')
    ####
    if not isinstance(self.frontier_coverage_verified, bool):
      raise TypeError('frontier_coverage_verified must be a bool')
    ####
    if (
      isinstance(self.frontier_sample_count, bool)
      or not isinstance(self.frontier_sample_count, int)
      or self.frontier_sample_count < 0
    ):
      raise ValueError('frontier_sample_count must be a nonnegative integer')
    ####
    if self.frontier_first_exterior_sample_index is not None and (
      isinstance(self.frontier_first_exterior_sample_index, bool)
      or not isinstance(self.frontier_first_exterior_sample_index, int)
      or self.frontier_first_exterior_sample_index < 0
    ):
      raise ValueError(
        'frontier_first_exterior_sample_index must be a nonnegative integer or None'
      )
    ####
    if self.frontier_first_exterior_signed_offset_m is not None:
      offset = float(self.frontier_first_exterior_signed_offset_m)
      if not isfinite(offset):
        raise ValueError('frontier_first_exterior_signed_offset_m must be finite')
      ####
      object.__setattr__(
        self,
        'frontier_first_exterior_signed_offset_m',
        offset,
      )
    ####
    if not isinstance(self.outgoing_frontier_bridge_enabled, bool):
      raise TypeError('outgoing_frontier_bridge_enabled must be a bool')
    ####
    if not isinstance(self.outgoing_frontier_bridge_verified, bool):
      raise TypeError('outgoing_frontier_bridge_verified must be a bool')
    ####
    if self.outgoing_frontier_bridge_status is not None and not isinstance(
      self.outgoing_frontier_bridge_status,
      str,
    ):
      raise TypeError('outgoing_frontier_bridge_status must be a string or None')
    ####
    if not isinstance(self.coupled_handoff_consumption_verified, bool):
      raise TypeError('coupled_handoff_consumption_verified must be a bool')
    ####
    for name in (
      'incoming_handoff_verified',
      'source_remesh_verified',
      'source_cell_euler_residuals_verified',
      'source_cell_euler_residuals_flag_consistent',
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
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('remesh free-boundary audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('remesh free-boundary audit must retain promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError('remesh free-boundary audit cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_CLOSED_AUDIT,
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.remesh_audit is not None
      and self.remesh_audit.local_consistency_verified
      and self.incoming_handoff_verified
      and self.source_remesh_verified
      and self.source_cell_euler_residuals_flag_consistent
      and self.status_consistent
      and self.frontier_coverage_verified
      and (
        not self.outgoing_frontier_bridge_enabled
        or self.outgoing_frontier_bridge_verified
      )
      and (self.path_coverage_verified or self.shock_status == MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE.value)
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and self.external_validation_required
      and self.fidelity_flags_verified
    )
  ####

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
      'remesh_audit': None if self.remesh_audit is None else self.remesh_audit.as_report(),
      'physical_field_euler_audit': (
        None
        if self.physical_field_euler_audit is None
        else self.physical_field_euler_audit.as_report()
      ),
      'incoming_handoff_verified': self.incoming_handoff_verified,
      'source_remesh_verified': self.source_remesh_verified,
      'source_cell_euler_residuals_verified': self.source_cell_euler_residuals_verified,
      'source_cell_euler_residuals_flag_consistent': (
        self.source_cell_euler_residuals_flag_consistent
      ),
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
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'termination_reason': self.termination_reason,
      'frontier_coverage_status': self.frontier_coverage_status,
      'frontier_coverage_verified': self.frontier_coverage_verified,
      'frontier_sample_count': self.frontier_sample_count,
      'frontier_first_exterior_sample_index': (
        self.frontier_first_exterior_sample_index
      ),
      'frontier_first_exterior_signed_offset_m': (
        self.frontier_first_exterior_signed_offset_m
      ),
      'outgoing_frontier_bridge_enabled': self.outgoing_frontier_bridge_enabled,
      'outgoing_frontier_bridge_verified': self.outgoing_frontier_bridge_verified,
      'outgoing_frontier_bridge_status': self.outgoing_frontier_bridge_status,
      'coupled_handoff_consumption_verified': (
        self.coupled_handoff_consumption_verified
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  physical_field_status: str | None = None,
  attachment_status: str | None = None,
  shock_status: str | None = None,
  remesh_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit | None = None,
  physical_field_euler_audit: MocPhysicalFieldEulerAudit | None = None,
  incoming_handoff_verified: bool = False,
  source_remesh_verified: bool = False,
  source_cell_euler_residuals_verified: bool = False,
  source_cell_euler_residuals_flag_consistent: bool = False,
  path_coverage_verified: bool = False,
  status_consistent: bool = False,
  reflected_free_boundary_verified: bool = False,
  fidelity_flags_verified: bool = False,
  shock_sample_count: int = 0,
  covered_sample_count: int = 0,
  first_missing_sample_index: int | None = None,
  maximum_state_residual: float | None = None,
  maximum_pressure_residual: float | None = None,
  termination_reason: str | None = None,
  frontier_coverage_status: str | None = None,
  frontier_coverage_verified: bool = False,
  frontier_sample_count: int = 0,
  frontier_first_exterior_sample_index: int | None = None,
  frontier_first_exterior_signed_offset_m: float | None = None,
  outgoing_frontier_bridge_enabled: bool = False,
  outgoing_frontier_bridge_verified: bool = False,
  outgoing_frontier_bridge_status: str | None = None,
  coupled_handoff_consumption_verified: bool = False,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_REMESH_FREE_BOUNDARY_AUDIT_OPERATOR_ID
    ),
    result_status=result_status,
    physical_field_status=physical_field_status,
    attachment_status=attachment_status,
    shock_status=shock_status,
    remesh_audit=remesh_audit,
    physical_field_euler_audit=physical_field_euler_audit,
    incoming_handoff_verified=incoming_handoff_verified,
    source_remesh_verified=source_remesh_verified,
    source_cell_euler_residuals_verified=source_cell_euler_residuals_verified,
    source_cell_euler_residuals_flag_consistent=(
      source_cell_euler_residuals_flag_consistent
    ),
    path_coverage_verified=path_coverage_verified,
    status_consistent=status_consistent,
    reflected_free_boundary_verified=reflected_free_boundary_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    fidelity_flags_verified=fidelity_flags_verified,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_sample_count,
    first_missing_sample_index=first_missing_sample_index,
    maximum_state_residual=maximum_state_residual,
    maximum_pressure_residual=maximum_pressure_residual,
    termination_reason=termination_reason,
    frontier_coverage_status=frontier_coverage_status,
    frontier_coverage_verified=frontier_coverage_verified,
    frontier_sample_count=frontier_sample_count,
    frontier_first_exterior_sample_index=frontier_first_exterior_sample_index,
    frontier_first_exterior_signed_offset_m=(
      frontier_first_exterior_signed_offset_m
    ),
    outgoing_frontier_bridge_enabled=outgoing_frontier_bridge_enabled,
    outgoing_frontier_bridge_verified=outgoing_frontier_bridge_verified,
    outgoing_frontier_bridge_status=outgoing_frontier_bridge_status,
    coupled_handoff_consumption_verified=coupled_handoff_consumption_verified,
    message=message,
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  shock_residual_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit:
  """Recompute remesh, path, closure, and fidelity evidence independently."""

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .INVALID_INPUT,
      'result must be a typed remesh free-boundary result',
    )
  ####
  tolerances = (
    float(position_tolerance_m),
    float(state_tolerance),
    float(shock_residual_tolerance),
    float(cell_residual_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('remesh free-boundary audit tolerances must be positive')
  ####
  remesh = result.remesh
  if remesh is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .REMESH_FAILURE,
      'result did not retain its source remesh',
      result_status=result.status.value,
    )
  ####
  try:
    remesh_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh(
      remesh,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=remesh.characteristic_residual_tolerance,
      pressure_lineage_tolerance=remesh.pressure_lineage_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .REMESH_FAILURE,
      f'independent source-remesh audit raised: {error}',
      result_status=result.status.value,
    )
  ####
  if not remesh_audit.local_consistency_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .REMESH_FAILURE,
      'source remesh failed its independent local audit',
      result_status=result.status.value,
      remesh_audit=remesh_audit,
    )
  ####
  incoming_handoff_verified = result.incoming_handoff == remesh.continuation_boundary
  if not incoming_handoff_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .HANDOFF_FAILURE,
      'result did not retain the exact remesh continuation boundary',
      result_status=result.status.value,
      physical_field_status=result.physical_field_status,
      attachment_status=result.attachment_status,
      remesh_audit=remesh_audit,
    )
  ####
  frontier = extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier(
    remesh,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
  )
  bridge_verified, bridge_sample, bridge_status = (
    _independent_frontier_bridge(
      result,
      frontier,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
    )
  )
  shock = result.shock
  shock_status = None if shock is None else shock.status.value
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
        sampled = _combined_diagnostic_sample(
          remesh,
          bridge_sample,
          point,
          position_tolerance_m=position_tolerance_m,
        )
        if sampled is None:
          first_missing = index
          break
        ####
        actual_state, actual_pressure = sampled
        state_residuals.append(max(
          abs(actual_state.x_m - expected_state.x_m),
          abs(actual_state.y_m - expected_state.y_m),
          abs(actual_state.theta_rad - expected_state.theta_rad),
          abs(actual_state.mach - expected_state.mach),
          abs(actual_state.gamma - expected_state.gamma),
        ))
        pressure_residuals.append(abs(actual_pressure - expected_pressure))
        if not _state_matches(
          actual_state,
          expected_state,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        ) or pressure_residuals[-1] > state_tolerance * max(
          1.0,
          abs(actual_pressure),
          abs(expected_pressure),
        ):
          first_missing = index
          break
        ####
        covered_count += 1
      ####
    except (TypeError, ValueError):
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
        .PATH_COVERAGE_FAILURE,
        'retained shock path arrays do not have matching typed lengths',
        result_status=result.status.value,
        physical_field_status=result.physical_field_status,
        attachment_status=result.attachment_status,
        shock_status=shock_status,
        remesh_audit=remesh_audit,
        incoming_handoff_verified=True,
      )
    ####
  ####
  shock_sample_count = 0 if shock is None else len(shock.shock_points_m)
  if (
    shock is not None
    and shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
    and first_missing is None
  ):
    first_missing = shock.failed_sample_index
  ####
  path_coverage_verified = bool(
    shock is not None
    and shock.converged
    and covered_count == shock_sample_count
    and first_missing is None
  )
  frontier_coverage_status: str | None = None
  frontier_coverage_verified = False
  frontier_sample_count = 0
  frontier_first_exterior_sample_index: int | None = None
  frontier_first_exterior_signed_offset_m: float | None = None
  frontier_path_points: list[tuple[float, float]] = (
    [] if shock is None else list(shock.shock_points_m)
  )
  if shock is not None and shock.failed_point_m is not None:
    failed_point = shock.failed_point_m
    if not frontier_path_points or any(
      abs(failed_point[index] - frontier_path_points[-1][index])
      > position_tolerance_m
      for index in (0, 1)
    ):
      frontier_path_points.append(failed_point)
    ####
  ####
  if not frontier_path_points and result.start_point_m is not None:
    frontier_path_points.append(result.start_point_m)
  ####
  if frontier_path_points:
    frontier_path_audit = (
      audit_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier_path(
        frontier,
        tuple(frontier_path_points),
        position_tolerance_m=position_tolerance_m,
      )
    )
    frontier_coverage_status = frontier_path_audit.status.value
    frontier_sample_count = frontier.sample_count
    frontier_first_exterior_sample_index = (
      frontier_path_audit.first_exterior_sample_index
    )
    frontier_first_exterior_signed_offset_m = (
      frontier_path_audit.first_exterior_signed_offset_m
    )
    cached_frontier_coverage = result.frontier_coverage
    frontier_coverage_verified = bool(
      frontier.converged
      and frontier_path_audit.frontier is not None
      and frontier_path_audit.frontier.converged
      and cached_frontier_coverage is not None
      and cached_frontier_coverage.frontier is not None
      and cached_frontier_coverage.frontier.converged
      and cached_frontier_coverage.frontier.edge_index == frontier.edge_index
      and cached_frontier_coverage.frontier.sample_count == frontier.sample_count
      and cached_frontier_coverage.status is frontier_path_audit.status
      and cached_frontier_coverage.first_missing_sample_index
      == frontier_path_audit.first_missing_sample_index
      and cached_frontier_coverage.first_exterior_sample_index
      == frontier_path_audit.first_exterior_sample_index
    )
  ####
  physical_field_euler_audit: MocPhysicalFieldEulerAudit | None = None
  if result.physical_field is not None and result.physical_field.field is not None:
    try:
      physical_field_euler_audit = measure_moc_physical_field_euler_audit(
        result.physical_field.field,
        shock_residual_tolerance=shock_residual_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
        position_tolerance_m=position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
        .REFLECTED_FIELD_FAILURE,
        f'independent physical-field Euler audit raised: {error}',
        result_status=result.status.value,
        physical_field_status=result.physical_field_status,
        attachment_status=result.attachment_status,
        shock_status=shock_status,
        remesh_audit=remesh_audit,
        incoming_handoff_verified=True,
        path_coverage_verified=path_coverage_verified,
        shock_sample_count=shock_sample_count,
        covered_sample_count=covered_count,
        first_missing_sample_index=first_missing,
      )
    ####
  ####
  expected_physical_handoff = (
    frontier.samples
    if result.outgoing_frontier_bridge_enabled
    else remesh.continuation_boundary
  )
  coupled_handoff_consumption_verified = bool(
    result.physical_field is not None
    and result.physical_field.field is not None
    and result.physical_field.field.incoming_handoff_states == tuple(
      sample.state for sample in expected_physical_handoff
    )
    and result.physical_field.field.incoming_handoff_total_pressure_Pa == tuple(
      sample.total_pressure_Pa for sample in expected_physical_handoff
    )
  )
  reflected_verified = bool(
    result.physical_field is not None
    and result.physical_field.physical_closure_verified
    and coupled_handoff_consumption_verified
  )
  source_remesh_verified = bool(
    remesh_audit.local_consistency_verified
    and result.source_remesh_verified
  )
  source_euler_verified = result.source_cell_euler_residuals_verified
  source_euler_flag_consistent = bool(
    result.source_cell_euler_residuals_verified
    == remesh.cell_euler_residuals_verified
  )
  expected_boundary = (
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .UPSTREAM_REMESH_BOUNDARY
  )
  expected_closed = (
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .CONVERGED_CLOSURE_PROBE
  )
  status_consistent = bool(
    (expected_boundary and shock_status == MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE.value and not path_coverage_verified)
    or (
      expected_closed
      and path_coverage_verified
      and reflected_verified
      and bridge_verified
    )
    or (
      not expected_boundary
      and not expected_closed
      and result.status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .REFLECTED_FIELD_FAILURE
    )
  )
  fidelity_flags_verified = bool(
    result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.external_validation_required
  )
  common = {
    'result_status': result.status.value,
    'physical_field_status': result.physical_field_status,
    'attachment_status': result.attachment_status,
    'shock_status': shock_status,
    'remesh_audit': remesh_audit,
    'physical_field_euler_audit': physical_field_euler_audit,
    'incoming_handoff_verified': incoming_handoff_verified,
    'source_remesh_verified': source_remesh_verified,
    'source_cell_euler_residuals_verified': source_euler_verified,
    'source_cell_euler_residuals_flag_consistent': source_euler_flag_consistent,
    'path_coverage_verified': path_coverage_verified,
    'status_consistent': status_consistent,
    'reflected_free_boundary_verified': reflected_verified,
    'fidelity_flags_verified': fidelity_flags_verified,
    'shock_sample_count': shock_sample_count,
    'covered_sample_count': covered_count,
    'first_missing_sample_index': first_missing,
    'maximum_state_residual': max(state_residuals, default=None),
    'maximum_pressure_residual': max(pressure_residuals, default=None),
    'termination_reason': result.as_chain_termination_decision().reason.value,
    'frontier_coverage_status': frontier_coverage_status,
    'frontier_coverage_verified': frontier_coverage_verified,
    'frontier_sample_count': frontier_sample_count,
    'frontier_first_exterior_sample_index': (
      frontier_first_exterior_sample_index
    ),
    'frontier_first_exterior_signed_offset_m': (
      frontier_first_exterior_signed_offset_m
    ),
    'outgoing_frontier_bridge_enabled': (
      result.outgoing_frontier_bridge_enabled
    ),
    'outgoing_frontier_bridge_verified': bridge_verified,
    'outgoing_frontier_bridge_status': bridge_status,
    'coupled_handoff_consumption_verified': (
      coupled_handoff_consumption_verified
    ),
  }
  if (
    expected_boundary
    and status_consistent
    and fidelity_flags_verified
    and frontier_coverage_verified
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_BOUNDARY_AUDIT,
      'independent audit confirmed the bounded remesh probe stopped at its upstream remesh boundary',
      **common,
    )
  ####
  if (
    expected_closed
    and status_consistent
    and fidelity_flags_verified
    and bridge_verified
    and frontier_coverage_verified
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
      .CONVERGED_LOCAL_CLOSED_AUDIT,
      'independent audit confirmed the local reflected closure probe; source Euler and external validation remain required',
      **common,
    )
  ####
  audit_status = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
    .ATTACHMENT_FAILURE
    if result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .AMBIENT_ATTACHMENT_FAILURE
    else MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
    .REFLECTED_FIELD_FAILURE
    if result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .REFLECTED_FIELD_FAILURE
    else MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAuditStatus
    .FLAG_FAILURE
  )
  return _failure(
    audit_status,
    'remesh free-boundary result did not pass independent closure-probe evidence gates',
    **common,
  )
####
