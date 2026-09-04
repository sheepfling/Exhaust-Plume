"""Independent audit for the bounded variable-entropy MOC continuation.

The continuation solver owns a bounded alternating ``C-``/``C+`` source band
whose pressure lineage follows the entropy gradient exposed by the first
local field.  This operator deliberately recomputes the characteristic
geometry, variable-entropy compatibility, pressure transport, ambient
boundary condition, topology, and conservative cell residuals from the
returned raw states.  Passing this audit is local research evidence only; it
does not close a downstream shock or authorize a physical shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell
from exhaust_plume.validation.moc_euler import _cell_flux_residual
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent bounded-continuation audit."""

  CONVERGED_LOCAL_CONTINUATION_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_continuation_audit'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'entropy_characteristic_continuation_field_failure'
  HANDOFF_FAILURE = 'entropy_characteristic_continuation_handoff_failure'
  SEGMENT_FAILURE = 'entropy_characteristic_continuation_segment_failure'
  TOPOLOGY_FAILURE = 'entropy_characteristic_continuation_topology_failure'
  PRESSURE_LINEAGE_FAILURE = (
    'entropy_characteristic_continuation_pressure_lineage_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'entropy_characteristic_continuation_euler_residual_failure'
  )
  STATUS_FAILURE = 'entropy_characteristic_continuation_status_failure'
  FLAG_FAILURE = 'entropy_characteristic_continuation_flag_failure'
####


def _finite_state(state: Any) -> bool:
  return bool(
    isinstance(state, CharacteristicState)
    and state.mach > 1.0
    and state.gamma > 1.0
    and all(
      isfinite(value)
      for value in (
        state.x_m,
        state.y_m,
        state.theta_rad,
        state.mach,
        state.gamma,
      )
    )
  )
####


def _state_matches(
  actual: Any,
  expected: Any,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  if not _finite_state(actual) or not _finite_state(expected):
    return False
  ####
  return bool(
    abs(actual.x_m - expected.x_m) <= position_tolerance_m
    and abs(actual.y_m - expected.y_m) <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad)
    <= state_tolerance * max(1.0, abs(actual.theta_rad), abs(expected.theta_rad))
    and abs(actual.mach - expected.mach)
    <= state_tolerance * max(1.0, abs(actual.mach), abs(expected.mach))
    and abs(actual.gamma - expected.gamma)
    <= state_tolerance * max(1.0, abs(actual.gamma), abs(expected.gamma))
  )
####


def _pressure_matches(
  actual: Any,
  expected: Any,
  *,
  pressure_tolerance: float,
) -> bool:
  try:
    actual_value = float(actual)
    expected_value = float(expected)
  except (TypeError, ValueError):
    return False
  ####
  if (
    not isfinite(actual_value)
    or not isfinite(expected_value)
    or actual_value <= 0.0
    or expected_value <= 0.0
  ):
    return False
  ####
  return abs(log(actual_value / expected_value)) <= pressure_tolerance
####


def _transport_total_pressure(
  start: CharacteristicState,
  start_total_pressure_Pa: float,
  end: CharacteristicState,
  gradient: tuple[float, float],
) -> float:
  return float(start_total_pressure_Pa) * exp(
    gradient[0] * (end.x_m - start.x_m)
    + gradient[1] * (end.y_m - start.y_m)
  )
####


def _compatibility_source(
  start: CharacteristicState,
  end: CharacteristicState,
  gradient: tuple[float, float],
) -> float:
  length = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
  average_theta = 0.5 * (start.theta_rad + end.theta_rad)
  normal_gradient = (
    gradient[0] * -sin(average_theta)
    + gradient[1] * cos(average_theta)
  )
  average_mach = 0.5 * (start.mach + end.mach)
  average_gamma = 0.5 * (start.gamma + end.gamma)
  return (
    -sqrt(max(average_mach * average_mach - 1.0, 0.0))
    / (average_gamma * average_mach**3)
    * normal_gradient
    * length
  )
####


def _characteristic_geometry_residual(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
) -> float:
  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  length = hypot(*displacement)
  start_direction = start.direction(family)
  end_direction = end.direction(family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  average_length = hypot(*average_direction)
  if length <= 0.0 or average_length <= 0.0:
    return float('inf')
  ####
  return abs(
    displacement[0] * average_direction[1]
    - displacement[1] * average_direction[0]
  ) / (length * average_length)
####


def _boundary_geometry_residual(
  previous: CharacteristicState,
  current: CharacteristicState,
) -> float:
  displacement = (current.x_m - previous.x_m, current.y_m - previous.y_m)
  length = hypot(*displacement)
  if length <= 0.0:
    return float('inf')
  ####
  angle = 0.5 * (previous.theta_rad + current.theta_rad)
  return abs(
    displacement[0] * sin(angle) - displacement[1] * cos(angle)
  ) / length
####


def _static_pressure(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> float:
  temperature_ratio = 1.0 / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  )
  return float(total_pressure_Pa) * temperature_ratio ** (
    state.gamma / (state.gamma - 1.0)
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit:
  """Independent residuals for one returned characteristic segment."""

  segment_index: int
  family: CharacteristicFamily | None
  declared_status: str | None
  state_data_verified: bool
  family_verified: bool
  geometry_residual: float | None
  compatibility_residual: float | None
  pressure_lineage_residual: float | None
  ambient_pressure_residual: float | None
  boundary_geometry_residual: float | None
  geometry_verified: bool
  compatibility_verified: bool
  pressure_lineage_verified: bool
  ambient_pressure_verified: bool
  boundary_geometry_verified: bool
  declared_status_consistent: bool
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.segment_index, bool)
      or not isinstance(self.segment_index, int)
      or self.segment_index < 0
    ):
      raise ValueError('segment_index must be a nonnegative integer')
    ####
    if self.family is not None and not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily or None')
    ####
    for name in (
      'declared_status',
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, str):
        raise TypeError(f'{name} must be a string or None')
      ####
    ####
    for name in (
      'geometry_residual',
      'compatibility_residual',
      'pressure_lineage_residual',
      'ambient_pressure_residual',
      'boundary_geometry_residual',
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
    for name in (
      'state_data_verified',
      'family_verified',
      'geometry_verified',
      'compatibility_verified',
      'pressure_lineage_verified',
      'ambient_pressure_verified',
      'boundary_geometry_verified',
      'declared_status_consistent',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.state_data_verified
      and self.family_verified
      and self.geometry_verified
      and self.compatibility_verified
      and self.pressure_lineage_verified
      and self.ambient_pressure_verified
      and self.boundary_geometry_verified
      and self.declared_status_consistent
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'segment_index': self.segment_index,
      'family': None if self.family is None else self.family.value,
      'declared_status': self.declared_status,
      'state_data_verified': self.state_data_verified,
      'family_verified': self.family_verified,
      'geometry_residual': self.geometry_residual,
      'compatibility_residual': self.compatibility_residual,
      'pressure_lineage_residual': self.pressure_lineage_residual,
      'ambient_pressure_residual': self.ambient_pressure_residual,
      'boundary_geometry_residual': self.boundary_geometry_residual,
      'geometry_verified': self.geometry_verified,
      'compatibility_verified': self.compatibility_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'ambient_pressure_verified': self.ambient_pressure_verified,
      'boundary_geometry_verified': self.boundary_geometry_verified,
      'declared_status_consistent': self.declared_status_consistent,
      'converged': self.converged,
      'message': self.message,
    }
  ####
####


def _missing_segment_audit(
  index: int,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit(
    segment_index=index,
    family=None,
    declared_status=None,
    state_data_verified=False,
    family_verified=False,
    geometry_residual=None,
    compatibility_residual=None,
    pressure_lineage_residual=None,
    ambient_pressure_residual=None,
    boundary_geometry_residual=None,
    geometry_verified=False,
    compatibility_verified=False,
    pressure_lineage_verified=False,
    ambient_pressure_verified=False,
    boundary_geometry_verified=False,
    declared_status_consistent=False,
    message=message,
  )
####


def _audit_segment(
  segment: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult,
  index: int,
  expected_family: CharacteristicFamily,
  gradient: tuple[float, float] | None,
  ambient_pressure_Pa: float | None,
  previous_boundary: CharacteristicState | None,
  *,
  characteristic_tolerance: float,
  pressure_tolerance: float,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit:
  if not isinstance(
    segment,
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentResult,
  ):
    return _missing_segment_audit(index, 'segment result has the wrong type')
  ####
  family = segment.family
  start = segment.start_state
  end = segment.end_state
  state_data_verified = bool(
    _finite_state(start)
    and _finite_state(end)
    and segment.start_total_pressure_Pa is not None
    and segment.end_total_pressure_Pa is not None
    and isfinite(segment.start_total_pressure_Pa)
    and isfinite(segment.end_total_pressure_Pa)
    and segment.start_total_pressure_Pa > 0.0
    and segment.end_total_pressure_Pa > 0.0
  )
  family_verified = family is expected_family
  geometry: float | None = None
  compatibility: float | None = None
  pressure_lineage: float | None = None
  ambient_residual: float | None = None
  boundary_residual: float | None = None
  if state_data_verified and gradient is not None:
    assert start is not None
    assert end is not None
    assert segment.start_total_pressure_Pa is not None
    assert segment.end_total_pressure_Pa is not None
    geometry = _characteristic_geometry_residual(start, end, family)
    actual_invariant = (
      end.k_plus - start.k_plus
      if family is CharacteristicFamily.PLUS
      else end.k_minus - start.k_minus
    )
    compatibility = abs(
      actual_invariant - _compatibility_source(start, end, gradient)
    )
    expected_pressure = _transport_total_pressure(
      start,
      segment.start_total_pressure_Pa,
      end,
      gradient,
    )
    pressure_lineage = abs(
      log(segment.end_total_pressure_Pa / expected_pressure)
    )
    if family is CharacteristicFamily.PLUS and ambient_pressure_Pa is not None:
      static_pressure = _static_pressure(end, segment.end_total_pressure_Pa)
      ambient_residual = abs(log(static_pressure / ambient_pressure_Pa))
    ####
  ####
  if (
    state_data_verified
    and previous_boundary is not None
    and end is not None
  ):
    boundary_residual = _boundary_geometry_residual(previous_boundary, end)
  ####
  geometry_verified = bool(
    geometry is not None and geometry <= characteristic_tolerance
  )
  compatibility_verified = bool(
    compatibility is not None and compatibility <= characteristic_tolerance
  )
  pressure_verified = bool(
    pressure_lineage is not None and pressure_lineage <= pressure_tolerance
  )
  ambient_verified = bool(
    family is CharacteristicFamily.MINUS
    or (
      ambient_residual is not None
      and ambient_residual <= pressure_tolerance
    )
  )
  boundary_verified = bool(
    previous_boundary is None
    or (
      boundary_residual is not None
      and boundary_residual <= characteristic_tolerance
    )
  )
  independent_converged = bool(
    state_data_verified
    and family_verified
    and geometry_verified
    and compatibility_verified
    and pressure_verified
    and ambient_verified
    and boundary_verified
  )
  declared_status_consistent = bool(segment.converged == independent_converged)
  return MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit(
    segment_index=index,
    family=family,
    declared_status=segment.status.value,
    state_data_verified=state_data_verified,
    family_verified=family_verified,
    geometry_residual=geometry,
    compatibility_residual=compatibility,
    pressure_lineage_residual=pressure_lineage,
    ambient_pressure_residual=ambient_residual,
    boundary_geometry_residual=boundary_residual,
    geometry_verified=geometry_verified,
    compatibility_verified=compatibility_verified,
    pressure_lineage_verified=pressure_verified,
    ambient_pressure_verified=ambient_verified,
    boundary_geometry_verified=boundary_verified,
    declared_status_consistent=declared_status_consistent,
    message=(
      ''
      if independent_converged
      else 'independent characteristic, entropy, pressure, or boundary gate failed'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit:
  """Independent local evidence for a bounded entropy continuation."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
  operator_id: str
  result_status: str | None
  field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None
  segment_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit, ...
  ]
  terminal_segment_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit | None
  incoming_handoff_verified: bool
  segment_links_verified: bool
  reflection_anchor_verified: bool
  alternating_seams_verified: bool
  pressure_lineage_verified: bool
  ambient_boundary_verified: bool
  continuation_boundary_verified: bool
  topology_verified: bool
  cell_samples_verified: bool
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  status_consistent: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  external_validation_required: bool
  fidelity_flags_verified: bool
  topology: MocTopologyResult
  ambient_pressure_Pa: float | None
  source_continuation_audit: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit | None
  ) = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus,
    ):
      raise TypeError('status must be a continuation audit status')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    if self.field_audit is not None and not isinstance(
      self.field_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
    ):
      raise TypeError('field_audit must be a typed field audit or None')
    ####
    if self.source_continuation_audit is not None and not isinstance(
      self.source_continuation_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
    ):
      raise TypeError(
        'source_continuation_audit must be a typed continuation audit or None'
      )
    ####
    segment_audits = tuple(self.segment_audits)
    if any(
      not isinstance(
        value,
        MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit,
      )
      for value in segment_audits
    ):
      raise TypeError('segment_audits must contain typed segment audits')
    ####
    object.__setattr__(self, 'segment_audits', segment_audits)
    if self.terminal_segment_audit is not None and not isinstance(
      self.terminal_segment_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit,
    ):
      raise TypeError('terminal_segment_audit must be typed or None')
    ####
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('cell_euler_residuals must be finite and nonnegative')
    ####
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    if self.maximum_cell_euler_residual is not None:
      maximum = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'maximum_cell_euler_residual', maximum)
    ####
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    if self.ambient_pressure_Pa is not None:
      ambient = float(self.ambient_pressure_Pa)
      if not isfinite(ambient) or ambient <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', ambient)
    ####
    for name in (
      'incoming_handoff_verified',
      'segment_links_verified',
      'reflection_anchor_verified',
      'alternating_seams_verified',
      'pressure_lineage_verified',
      'ambient_boundary_verified',
      'continuation_boundary_verified',
      'topology_verified',
      'cell_samples_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'status_consistent',
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
      raise ValueError('continuation audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('continuation audit must retain the promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError('continuation audit cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .CONVERGED_LOCAL_CONTINUATION_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    source_audit_verified = bool(
      self.field_audit is not None
      and self.field_audit.local_consistency_verified
    ) or bool(
      self.source_continuation_audit is not None
      and self.source_continuation_audit.local_consistency_verified
    )
    return bool(
      self.converged
      and source_audit_verified
      and self.incoming_handoff_verified
      and self.segment_links_verified
      and self.reflection_anchor_verified
      and self.alternating_seams_verified
      and self.pressure_lineage_verified
      and self.ambient_boundary_verified
      and self.continuation_boundary_verified
      and self.topology_verified
      and self.cell_samples_verified
      and self.cell_euler_residuals_finite
      and self.status_consistent
      and self.fidelity_flags_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
      and not self.physical_closure_verified
      and self.external_validation_required
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'field_audit': (
        None if self.field_audit is None else self.field_audit.as_report()
      ),
      'source_continuation_audit': (
        None
        if self.source_continuation_audit is None
        else self.source_continuation_audit.as_report()
      ),
      'segment_audits': [
        audit.as_report() for audit in self.segment_audits
      ],
      'terminal_segment_audit': (
        None
        if self.terminal_segment_audit is None
        else self.terminal_segment_audit.as_report()
      ),
      'incoming_handoff_verified': self.incoming_handoff_verified,
      'segment_links_verified': self.segment_links_verified,
      'reflection_anchor_verified': self.reflection_anchor_verified,
      'alternating_seams_verified': self.alternating_seams_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'continuation_boundary_verified': self.continuation_boundary_verified,
      'topology_verified': self.topology_verified,
      'cell_samples_verified': self.cell_samples_verified,
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
      'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
      'status_consistent': self.status_consistent,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None = None,
  segment_audits: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit
  ] = (),
  terminal_segment_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit | None = None,
  incoming_handoff_verified: bool = False,
  segment_links_verified: bool = False,
  reflection_anchor_verified: bool = False,
  alternating_seams_verified: bool = False,
  pressure_lineage_verified: bool = False,
  ambient_boundary_verified: bool = False,
  continuation_boundary_verified: bool = False,
  topology_verified: bool = False,
  cell_samples_verified: bool = False,
  cell_euler_residuals: Sequence[float] = (),
  maximum_cell_euler_residual: float | None = None,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  status_consistent: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  external_validation_required: bool = True,
  fidelity_flags_verified: bool = False,
  topology: MocTopologyResult | None = None,
  ambient_pressure_Pa: float | None = None,
  source_continuation_audit: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit | None
  ) = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_AUDIT_OPERATOR_ID
    ),
    result_status=result_status,
    field_audit=field_audit,
    segment_audits=tuple(segment_audits),
    terminal_segment_audit=terminal_segment_audit,
    incoming_handoff_verified=incoming_handoff_verified,
    segment_links_verified=segment_links_verified,
    reflection_anchor_verified=reflection_anchor_verified,
    alternating_seams_verified=alternating_seams_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    continuation_boundary_verified=continuation_boundary_verified,
    topology_verified=topology_verified,
    cell_samples_verified=cell_samples_verified,
    cell_euler_residuals=tuple(cell_euler_residuals),
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    status_consistent=status_consistent,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    external_validation_required=external_validation_required,
    fidelity_flags_verified=fidelity_flags_verified,
    topology=validate_moc_mesh(()) if topology is None else topology,
    ambient_pressure_Pa=ambient_pressure_Pa,
    source_continuation_audit=source_continuation_audit,
    message=message,
  )
####


def _topology_matches(
  declared: MocTopologyResult,
  measured: MocTopologyResult,
) -> bool:
  return bool(
    declared.status is measured.status
    and declared.cell_count == measured.cell_count
    and declared.edge_count == measured.edge_count
    and declared.boundary_edge_count == measured.boundary_edge_count
    and declared.boundary_component_count == measured.boundary_component_count
    and declared.boundary_is_closed_cycle == measured.boundary_is_closed_cycle
    and declared.nonmanifold_edge_count == measured.nonmanifold_edge_count
    and declared.connected == measured.connected
  )
####


def _sample_data_verified(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
) -> bool:
  if len(result.cells) != len(result.cell_samples):
    return False
  ####
  for cell, sample in zip(result.cells, result.cell_samples, strict=True):
    if not isinstance(cell, MocCharacteristicCell) or not isinstance(
      sample,
      MocEulerAmbientFirstWedgeCellSample,
    ):
      return False
    ####
    if tuple(cell.vertices_xr_m) != tuple(sample.vertices_xr_m):
      return False
    ####
    if len(sample.vertices_xr_m) != len(sample.states):
      return False
    ####
    if len(sample.vertices_xr_m) != len(sample.total_pressure_Pa):
      return False
    ####
    if len(sample.vertices_xr_m) < 3:
      return False
    ####
    if any(
      not all(isfinite(value) for value in point)
      for point in sample.vertices_xr_m
    ):
      return False
    ####
    if any(not _finite_state(state) for state in sample.states):
      return False
    ####
    if any(
      not isfinite(pressure) or pressure <= 0.0
      for pressure in sample.total_pressure_Pa
    ):
      return False
    ####
  ####
  return bool(result.cell_samples)
####


def _boundary_matches(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
  pressure_tolerance: float,
) -> bool:
  boundary = result.continuation_boundary
  if (
    len(boundary) != 2
    or not result.outer_states
    or result.terminal_centerline_state is None
    or result.terminal_centerline_total_pressure_Pa is None
  ):
    return False
  ####
  return bool(
    _state_matches(
      boundary[0].state,
      result.outer_states[-1],
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
    )
    and _pressure_matches(
      boundary[0].total_pressure_Pa,
      result.outer_total_pressure_Pa[-1],
      pressure_tolerance=pressure_tolerance,
    )
    and _state_matches(
      boundary[1].state,
      result.terminal_centerline_state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
    )
    and _pressure_matches(
      boundary[1].total_pressure_Pa,
      result.terminal_centerline_total_pressure_Pa,
      pressure_tolerance=pressure_tolerance,
    )
    and boundary[1].state.x_m > boundary[0].state.x_m + position_tolerance_m
    and boundary[1].state.y_m < boundary[0].state.y_m - position_tolerance_m
    and boundary[0].state.y_m > result.target_centerline_y_m
    and abs(boundary[1].state.y_m - result.target_centerline_y_m)
    <= position_tolerance_m
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit:
  """Recompute continuation evidence independently from returned primitives."""

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .INVALID_INPUT,
      'result must be a typed entropy-characteristic continuation result',
    )
  ####
  tolerances = (
    float(position_tolerance_m),
    float(state_tolerance),
    float(characteristic_residual_tolerance),
    float(pressure_lineage_tolerance),
    float(cell_residual_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('continuation audit tolerances must be finite and positive')
  ####

  source = result.source_field
  if source is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .FIELD_FAILURE,
      'continuation result did not retain its source entropy result',
      result_status=result.status.value,
      ambient_pressure_Pa=result.ambient_pressure_Pa,
    )
  ####
  field_audit = None
  source_continuation_audit = None
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult):
    try:
      field_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
        source,
        position_tolerance_m=position_tolerance_m,
        characteristic_residual_tolerance=characteristic_residual_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
        pressure_lineage_tolerance=pressure_lineage_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .FIELD_FAILURE,
        f'independent source-field audit raised: {error}',
        result_status=result.status.value,
        ambient_pressure_Pa=result.ambient_pressure_Pa,
      )
    ####
    if not field_audit.local_consistency_verified:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .FIELD_FAILURE,
        'retained source field failed its independent audit',
        result_status=result.status.value,
        field_audit=field_audit,
        ambient_pressure_Pa=result.ambient_pressure_Pa,
      )
    ####
  elif isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
    try:
      source_continuation_audit = (
        measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
          source,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
          characteristic_residual_tolerance=characteristic_residual_tolerance,
          pressure_lineage_tolerance=pressure_lineage_tolerance,
          cell_residual_tolerance=cell_residual_tolerance,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .FIELD_FAILURE,
        f'independent source-continuation audit raised: {error}',
        result_status=result.status.value,
        ambient_pressure_Pa=result.ambient_pressure_Pa,
      )
    ####
    if not source_continuation_audit.local_consistency_verified:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .FIELD_FAILURE,
        'retained source continuation failed its independent audit',
        result_status=result.status.value,
        source_continuation_audit=source_continuation_audit,
        ambient_pressure_Pa=result.ambient_pressure_Pa,
      )
    ####
  else:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .FIELD_FAILURE,
      'continuation result retained an unsupported source result type',
      result_status=result.status.value,
      ambient_pressure_Pa=result.ambient_pressure_Pa,
    )
  ####

  incoming_handoff_verified = bool(
    result.incoming_handoff == source.continuation_boundary
  )
  if not incoming_handoff_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .HANDOFF_FAILURE,
      'continuation did not retain the exact source-result perimeter',
      result_status=result.status.value,
      field_audit=field_audit,
      source_continuation_audit=source_continuation_audit,
      ambient_pressure_Pa=result.ambient_pressure_Pa,
    )
  ####
  gradient = result.source_pressure_gradient
  ambient_pressure = result.ambient_pressure_Pa
  if gradient is None or len(gradient) != 2 or not all(isfinite(value) for value in gradient):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .PRESSURE_LINEAGE_FAILURE,
      'continuation did not retain a finite entropy pressure gradient',
      result_status=result.status.value,
      field_audit=field_audit,
      source_continuation_audit=source_continuation_audit,
      incoming_handoff_verified=True,
      ambient_pressure_Pa=ambient_pressure,
    )
  ####
  if ambient_pressure is None or not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .PRESSURE_LINEAGE_FAILURE,
      'continuation did not retain a finite positive ambient pressure',
      result_status=result.status.value,
      field_audit=field_audit,
      source_continuation_audit=source_continuation_audit,
      incoming_handoff_verified=True,
      ambient_pressure_Pa=ambient_pressure,
    )
  ####

  segment_audits: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicSegmentAudit
  ] = []
  segment_links_verified = True
  reflection_anchor_verified = False
  alternating_seams_verified = bool(
    len(result.centerline_states) == result.cycle_count
    and len(result.outer_states) == result.cycle_count
    and len(result.centerline_segments) == result.cycle_count
    and len(result.outer_segments) == result.cycle_count
    and result.cycle_count > 0
  )
  if len(result.incoming_handoff) < 2 or not result.centerline_segments:
    alternating_seams_verified = False
  ####

  for index, segment in enumerate(result.centerline_segments):
    if index == 0:
      previous_state = result.incoming_handoff[0].state
      previous_pressure = result.incoming_handoff[0].total_pressure_Pa
    elif index - 1 < len(result.outer_states):
      previous_state = result.outer_states[index - 1]
      previous_pressure = result.outer_total_pressure_Pa[index - 1]
    else:
      previous_state = None
      previous_pressure = None
    ####
    audit = _audit_segment(
      segment,
      index,
      CharacteristicFamily.MINUS,
      gradient,
      ambient_pressure,
      None,
      characteristic_tolerance=characteristic_residual_tolerance,
      pressure_tolerance=pressure_lineage_tolerance,
    )
    segment_audits.append(audit)
    if previous_state is None or previous_pressure is None:
      segment_links_verified = False
    else:
      segment_links_verified = bool(
        segment_links_verified
        and _state_matches(
          segment.start_state,
          previous_state,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        )
        and _pressure_matches(
          segment.start_total_pressure_Pa,
          previous_pressure,
          pressure_tolerance=pressure_lineage_tolerance,
        )
      )
    ####
    if index == 0 and len(result.incoming_handoff) >= 2:
      reflection_anchor_verified = bool(
        audit.converged
        and _state_matches(
          segment.end_state,
          result.incoming_handoff[-1].state,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        )
        and _pressure_matches(
          segment.end_total_pressure_Pa,
          result.incoming_handoff[-1].total_pressure_Pa,
          pressure_tolerance=pressure_lineage_tolerance,
        )
      )
    ####
  ####
  for index, segment in enumerate(result.outer_segments):
    if index < len(result.centerline_states):
      previous_state = result.centerline_states[index]
      previous_pressure = result.centerline_total_pressure_Pa[index]
    else:
      previous_state = None
      previous_pressure = None
    ####
    boundary_state = (
      result.incoming_handoff[0].state
      if index == 0 and result.incoming_handoff
      else result.outer_states[index - 1]
      if index > 0 and index - 1 < len(result.outer_states)
      else None
    )
    audit = _audit_segment(
      segment,
      index,
      CharacteristicFamily.PLUS,
      gradient,
      ambient_pressure,
      boundary_state,
      characteristic_tolerance=characteristic_residual_tolerance,
      pressure_tolerance=pressure_lineage_tolerance,
    )
    segment_audits.append(audit)
    if previous_state is None or previous_pressure is None:
      segment_links_verified = False
    else:
      segment_links_verified = bool(
        segment_links_verified
        and _state_matches(
          segment.start_state,
          previous_state,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        )
        and _pressure_matches(
          segment.start_total_pressure_Pa,
          previous_pressure,
          pressure_tolerance=pressure_lineage_tolerance,
        )
      )
    ####
  ####
  terminal_audit = None
  if result.terminal_segment is not None:
    if result.outer_states and result.outer_total_pressure_Pa:
      terminal_start = result.outer_states[-1]
      terminal_pressure = result.outer_total_pressure_Pa[-1]
    else:
      terminal_start = None
      terminal_pressure = None
    ####
    terminal_audit = _audit_segment(
      result.terminal_segment,
      len(result.centerline_segments),
      CharacteristicFamily.MINUS,
      gradient,
      ambient_pressure,
      None,
      characteristic_tolerance=characteristic_residual_tolerance,
      pressure_tolerance=pressure_lineage_tolerance,
    )
    if terminal_start is None or terminal_pressure is None:
      segment_links_verified = False
    else:
      segment_links_verified = bool(
        segment_links_verified
        and _state_matches(
          result.terminal_segment.start_state,
          terminal_start,
          position_tolerance_m=position_tolerance_m,
          state_tolerance=state_tolerance,
        )
        and _pressure_matches(
          result.terminal_segment.start_total_pressure_Pa,
          terminal_pressure,
          pressure_tolerance=pressure_lineage_tolerance,
        )
      )
    ####
  else:
    segment_links_verified = False
  ####

  all_segment_audits = [*segment_audits]
  if terminal_audit is not None:
    all_segment_audits.append(terminal_audit)
  ####
  segment_gates_verified = bool(
    all_segment_audits and all(audit.converged for audit in all_segment_audits)
  )
  if result.centerline_states and result.outer_states:
    alternating_seams_verified = bool(
      alternating_seams_verified
      and all(
        current.x_m > previous.x_m + position_tolerance_m
        for previous, current in zip(
          result.centerline_states,
          result.centerline_states[1:],
        )
      )
      and all(
        current.x_m > previous.x_m + position_tolerance_m
        for previous, current in zip(
          result.outer_states,
          result.outer_states[1:],
        )
      )
      and all(
        abs(state.y_m - result.target_centerline_y_m) <= position_tolerance_m
        and abs(state.theta_rad - result.target_centerline_flow_angle_rad)
        <= characteristic_residual_tolerance
        for state in result.centerline_states
      )
      and all(
        state.y_m > result.target_centerline_y_m + position_tolerance_m
        for state in result.outer_states
      )
    )
  ####
  reflection_anchor_verified = bool(
    reflection_anchor_verified
    and result.terminal_segment is not None
    and result.outer_states
    and result.terminal_centerline_state is not None
    and _state_matches(
      result.terminal_segment.end_state,
      result.terminal_centerline_state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
    )
    and _pressure_matches(
      result.terminal_segment.end_total_pressure_Pa,
      result.terminal_centerline_total_pressure_Pa,
      pressure_tolerance=pressure_lineage_tolerance,
    )
  )
  pressure_lineage_verified = bool(
    segment_gates_verified
    and all(
      audit.pressure_lineage_verified for audit in all_segment_audits
    )
  )
  ambient_boundary_verified = bool(
    result.outer_segments
    and all(
      audit.ambient_pressure_verified
      and audit.boundary_geometry_verified
      for audit in segment_audits[len(result.centerline_segments):]
    )
  )
  continuation_boundary_verified = _boundary_matches(
    result,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_lineage_tolerance,
  )

  try:
    measured_topology = validate_moc_mesh(result.cells)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    measured_topology = validate_moc_mesh(())
  ####
  topology_verified = bool(
    result.cells
    and measured_topology.forms_closed_zone
    and measured_topology.nonmanifold_edge_count == 0
    and _topology_matches(result.topology, measured_topology)
  )
  samples_verified = _sample_data_verified(result)
  measured_residuals: list[float] = []
  residual_evaluation_failed = False
  if samples_verified:
    try:
      measured_residuals = [
        _cell_flux_residual(
          tuple(sample.vertices_xr_m),
          tuple(sample.states),
          tuple(sample.total_pressure_Pa),
        )
        for sample in result.cell_samples
      ]
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      residual_evaluation_failed = True
    ####
  ####
  declared_residuals_verified = bool(
    len(measured_residuals) == len(result.cell_euler_residuals)
    and all(
      abs(actual - declared) <= max(1.0e-12, cell_residual_tolerance * 1.0e-6)
      for actual, declared in zip(
        measured_residuals,
        result.cell_euler_residuals,
        strict=True,
      )
    )
  )
  residuals_finite = bool(
    measured_residuals
    and all(isfinite(value) and value >= 0.0 for value in measured_residuals)
  )
  maximum_residual = max(measured_residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= cell_residual_tolerance
  )
  cell_samples_verified = bool(
    samples_verified and declared_residuals_verified and not residual_evaluation_failed
  )

  expected_success = bool(
    segment_gates_verified
    and segment_links_verified
    and reflection_anchor_verified
    and alternating_seams_verified
    and pressure_lineage_verified
    and ambient_boundary_verified
    and continuation_boundary_verified
    and topology_verified
    and cell_samples_verified
    and residuals_finite
  )
  result_success = (
    result.status
    is MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationStatus
    .CONVERGED_BOUNDED_CONTINUATION
  )
  status_consistent = bool(result_success == expected_success)
  flags_verified = bool(
    not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.external_validation_required
  )
  common = dict(
    result_status=result.status.value,
    field_audit=field_audit,
    source_continuation_audit=source_continuation_audit,
    segment_audits=segment_audits,
    terminal_segment_audit=terminal_audit,
    incoming_handoff_verified=True,
    segment_links_verified=segment_links_verified,
    reflection_anchor_verified=reflection_anchor_verified,
    alternating_seams_verified=alternating_seams_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    continuation_boundary_verified=continuation_boundary_verified,
    topology_verified=topology_verified,
    cell_samples_verified=cell_samples_verified,
    cell_euler_residuals=measured_residuals,
    maximum_cell_euler_residual=maximum_residual,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    status_consistent=status_consistent,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    fidelity_flags_verified=flags_verified,
    topology=measured_topology,
    ambient_pressure_Pa=ambient_pressure,
  )
  if not flags_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .FLAG_FAILURE,
      'continuation weakened its explicit non-promotion fidelity boundary',
      **common,
    )
  ####
  if result_success and not expected_success:
    if not segment_gates_verified or not alternating_seams_verified:
      audit_status = (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .SEGMENT_FAILURE
      )
    elif not pressure_lineage_verified or not ambient_boundary_verified:
      audit_status = (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .PRESSURE_LINEAGE_FAILURE
      )
    elif not topology_verified:
      audit_status = (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .TOPOLOGY_FAILURE
      )
    elif residual_evaluation_failed or not residuals_finite:
      audit_status = (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .EULER_RESIDUAL_FAILURE
      )
    else:
      audit_status = (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
        .STATUS_FAILURE
      )
    ####
    return _failure(
      audit_status,
      'successful continuation did not reproduce all independent local gates',
      **common,
    )
  ####
  if result_success and expected_success and status_consistent:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .CONVERGED_LOCAL_CONTINUATION_AUDIT,
      'independent audit confirmed the bounded alternating entropy source band; Euler refinement and physical shock closure remain pending',
      **common,
    )
  ####
  if not status_consistent:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .STATUS_FAILURE,
      'continuation status does not match independently measured local evidence',
      **common,
    )
  ####
  if residual_evaluation_failed:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .EULER_RESIDUAL_FAILURE
    )
  elif not topology_verified:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .TOPOLOGY_FAILURE
    )
  elif not pressure_lineage_verified:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .PRESSURE_LINEAGE_FAILURE
    )
  else:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAuditStatus
      .SEGMENT_FAILURE
    )
  ####
  return _failure(
    audit_status,
    'continuation did not pass the independent local evidence gates',
    **common,
  )
####
