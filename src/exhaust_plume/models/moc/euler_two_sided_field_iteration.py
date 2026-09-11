"""Research-only iteration for the exact two-sided Euler field seam.

The open companion characteristic field and the ambient-closed physical field
are different fidelity objects.  This module joins them without pretending
that an ambient boundary is itself a companion strip: the first iteration
consumes the verified companion handoff, the physical field exposes its open
shock/ambient terminal trace, and later iterations consume that trace as the
next solver-owned handoff.

The iteration is useful evidence for the higher-fidelity research lane.  It
does not solve the moving shock/free-boundary problem, does not perform a
conservative refinement audit, and never authorizes production chain-cell
promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockStripResult,
)
from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerCompanionFieldResult,
)
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
  assemble_euler_ambient_physical_field,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)

__all__ = (
  'MocEulerTwoSidedFieldIterationStatus',
  'MocEulerTwoSidedFieldIterationRequest',
  'MocEulerTwoSidedFieldIterationRecord',
  'MocEulerTwoSidedFieldIterationResult',
  'solve_euler_two_sided_field_iteration',
)


class MocEulerTwoSidedFieldIterationStatus(str, Enum):
  """Typed outcomes for the two-sided exact-Euler research iteration."""

  CONVERGED_FIXED_POINT = 'converged_two_sided_euler_field_iteration'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'two_sided_iteration_shock_boundary_required'
  COMPANION_FIELD_REQUIRED = 'two_sided_iteration_companion_field_required'
  PHYSICAL_FIELD_FAILURE = 'two_sided_iteration_physical_field_failure'
  SOURCE_STRIP_FAILURE = 'two_sided_iteration_source_strip_failure'
  ITERATION_LIMIT = 'two_sided_iteration_limit'
####


def _positive_float(value: Any, name: str) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedFieldIterationRequest:
  """Inputs for a bounded research iteration across the two-sided seam."""

  shock_boundary: MocEulerShockBoundaryCurveResult
  companion_field: MocEulerCompanionFieldResult
  ambient_pressure_Pa: float
  target_centerline_y_m: float = 0.0
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance: float = 1.0e-8
  handoff_position_tolerance_m: float = 1.0e-8
  handoff_state_tolerance: float = 1.0e-8
  handoff_pressure_tolerance_Pa: float = 1.0e-8
  source_trace_position_tolerance_m: float = 1.0e-3
  source_trace_forward_tolerance_m: float = 1.0e-3
  maximum_field_iterations: int = 4
  maximum_boundary_iterations: int = 16

  def __post_init__(self) -> None:
    if not isinstance(self.shock_boundary, MocEulerShockBoundaryCurveResult):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult'
      )
    ####
    if not isinstance(self.companion_field, MocEulerCompanionFieldResult):
      raise TypeError(
        'companion_field must be a MocEulerCompanionFieldResult'
      )
    ####
    if self.companion_field.shock_boundary is not self.shock_boundary:
      raise ValueError(
        'companion_field must retain the exact supplied shock boundary object'
      )
    ####
    if not self.shock_boundary.converged or not self.shock_boundary.local_euler_verified:
      raise ValueError(
        'two-sided iteration requires a converged locally Euler-verified shock boundary'
      )
    ####
    if not (
      self.companion_field.converged
      and self.companion_field.state_sampling_available
      and self.companion_field.shock_boundary_local_euler_verified
      and self.companion_field.companion_boundary_contract_verified
      and self.companion_field.pressure_lineage_verified
      and not self.companion_field.physical_closure_verified
      and self.companion_field.chain_promotion_blocked
      and not self.companion_field.production_claim_allowed
    ):
      raise ValueError(
        'two-sided iteration requires a verified open companion field with '
        'physical and production promotion blocked'
      )
    ####
    if len(self.companion_field.downstream_handoff) < 3:
      raise ValueError(
        'two-sided iteration requires at least three companion handoff samples'
      )
    ####
    ambient_pressure = _positive_float(
      self.ambient_pressure_Pa,
      'ambient_pressure_Pa',
    )
    target_y = float(self.target_centerline_y_m)
    if not isfinite(target_y):
      raise ValueError('target_centerline_y_m must be finite')
    ####
    object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    object.__setattr__(self, 'target_centerline_y_m', target_y)
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'handoff_position_tolerance_m',
      'handoff_state_tolerance',
      'handoff_pressure_tolerance_Pa',
      'source_trace_position_tolerance_m',
      'source_trace_forward_tolerance_m',
    ):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    for name in ('maximum_field_iterations', 'maximum_boundary_iterations'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
      ####
    ####
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'shock_boundary_status': self.shock_boundary.status.value,
      'companion_field_status': self.companion_field.status.value,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'target_centerline_y_m': self.target_centerline_y_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'handoff_position_tolerance_m': self.handoff_position_tolerance_m,
      'handoff_state_tolerance': self.handoff_state_tolerance,
      'handoff_pressure_tolerance_Pa': self.handoff_pressure_tolerance_Pa,
      'source_trace_position_tolerance_m': self.source_trace_position_tolerance_m,
      'source_trace_forward_tolerance_m': self.source_trace_forward_tolerance_m,
      'maximum_field_iterations': self.maximum_field_iterations,
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'initial_companion_handoff_sample_count': len(
        self.companion_field.downstream_handoff
      ),
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedFieldIterationRecord:
  """Independent evidence retained for one field/trace iteration."""

  iteration_index: int
  incoming_handoff_sample_count: int
  physical_field: MocEulerAmbientPhysicalFieldResult | None
  source_strip: MocAmbientShockStripResult | None
  outgoing_handoff_sample_count: int
  maximum_coordinate_residual_m: float | None
  maximum_state_residual: float | None
  maximum_pressure_residual_Pa: float | None
  fixed_point_converged: bool
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.iteration_index, bool)
      or not isinstance(self.iteration_index, int)
      or self.iteration_index < 0
    ):
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    for name in (
      'incoming_handoff_sample_count',
      'outgoing_handoff_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'physical_field must be a MocEulerAmbientPhysicalFieldResult or None'
      )
    ####
    if self.source_strip is not None and not isinstance(
      self.source_strip,
      MocAmbientShockStripResult,
    ):
      raise TypeError(
        'source_strip must be a MocAmbientShockStripResult or None'
      )
    ####
    for name in (
      'maximum_coordinate_residual_m',
      'maximum_state_residual',
      'maximum_pressure_residual_Pa',
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
    if not isinstance(self.fixed_point_converged, bool):
      raise TypeError('fixed_point_converged must be a bool')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'iteration_index': self.iteration_index,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'outgoing_handoff_sample_count': self.outgoing_handoff_sample_count,
      'maximum_coordinate_residual_m': self.maximum_coordinate_residual_m,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_pressure_residual_Pa': self.maximum_pressure_residual_Pa,
      'fixed_point_converged': self.fixed_point_converged,
      'physical_field_status': (
        None if self.physical_field is None else self.physical_field.status.value
      ),
      'source_strip_status': (
        None if self.source_strip is None else self.source_strip.status.value
      ),
      'physical_field_verified': bool(
        self.physical_field is not None
        and self.physical_field.physical_field_verified
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedFieldIterationResult:
  """Result of the bounded two-sided field/terminal-trace iteration."""

  status: MocEulerTwoSidedFieldIterationStatus
  request: MocEulerTwoSidedFieldIterationRequest | None
  shock_boundary: MocEulerShockBoundaryCurveResult | None
  initial_companion_field: MocEulerCompanionFieldResult | None
  records: tuple[MocEulerTwoSidedFieldIterationRecord, ...]
  final_physical_field: MocEulerAmbientPhysicalFieldResult | None
  final_source_strip: MocAmbientShockStripResult | None
  fixed_point_converged: bool
  field_iteration_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedFieldIterationStatus):
      raise TypeError(
        'status must be a MocEulerTwoSidedFieldIterationStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocEulerTwoSidedFieldIterationRequest,
    ):
      raise TypeError(
        'request must be a MocEulerTwoSidedFieldIterationRequest or None'
      )
    ####
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    ####
    if self.initial_companion_field is not None and not isinstance(
      self.initial_companion_field,
      MocEulerCompanionFieldResult,
    ):
      raise TypeError(
        'initial_companion_field must be a MocEulerCompanionFieldResult or None'
      )
    ####
    records = tuple(self.records)
    if any(
      not isinstance(record, MocEulerTwoSidedFieldIterationRecord)
      for record in records
    ):
      raise TypeError(
        'records must contain MocEulerTwoSidedFieldIterationRecord values'
      )
    ####
    if self.final_physical_field is not None and not isinstance(
      self.final_physical_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'final_physical_field must be a '
        'MocEulerAmbientPhysicalFieldResult or None'
      )
    ####
    if self.final_source_strip is not None and not isinstance(
      self.final_source_strip,
      MocAmbientShockStripResult,
    ):
      raise TypeError(
        'final_source_strip must be a MocAmbientShockStripResult or None'
      )
    ####
    for name in (
      'fixed_point_converged',
      'field_iteration_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.field_iteration_verified and not (
      self.fixed_point_converged
      and self.final_physical_field is not None
      and self.final_physical_field.physical_field_verified
      and self.final_source_strip is not None
      and self.final_source_strip.converged
      and self.final_source_strip.terminal_trace_validation.converged
    ):
      raise ValueError(
        'field_iteration_verified requires a converged fixed-point trace and '
        'verified final physical field'
      )
    ####
    object.__setattr__(self, 'records', records)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedFieldIterationStatus.CONVERGED_FIXED_POINT
  ####

  @property
  def bounded_physical_field_verified(self) -> bool:
    return bool(
      self.final_physical_field is not None
      and self.final_physical_field.physical_field_verified
    )
  ####

  @property
  def terminal_trace_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    if self.final_source_strip is None or not self.final_source_strip.converged:
      return ()
    ####
    return self.final_source_strip.terminal_trace_samples
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'bounded_physical_field_verified': self.bounded_physical_field_verified,
      'fixed_point_converged': self.fixed_point_converged,
      'field_iteration_verified': self.field_iteration_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': None if self.request is None else self.request.as_report(),
      'records': tuple(record.as_report() for record in self.records),
      'final_physical_field': (
        None
        if self.final_physical_field is None
        else self.final_physical_field.as_report()
      ),
      'final_source_strip': (
        None
        if self.final_source_strip is None
        else self.final_source_strip.as_report()
      ),
      'terminal_trace_handoff_sample_count': len(self.terminal_trace_handoff),
      'message': self.message,
    }
  ####
####


def _handoff_residuals(
  incoming: tuple[MocChainBoundarySample, ...],
  outgoing: tuple[MocChainBoundarySample, ...],
) -> tuple[float | None, float | None, float | None]:
  pair_count = min(len(incoming), len(outgoing))
  if pair_count == 0:
    return None, None, None
  ####
  maximum_coordinate = max(
    (
      hypot(
        outgoing[index].state.x_m - incoming[index].state.x_m,
        outgoing[index].state.y_m - incoming[index].state.y_m,
      )
      for index in range(pair_count)
    ),
    default=None,
  )
  maximum_state = max(
    (
      max(
        abs(outgoing[index].state.theta_rad - incoming[index].state.theta_rad),
        abs(outgoing[index].state.mach - incoming[index].state.mach),
        abs(outgoing[index].state.gamma - incoming[index].state.gamma),
      )
      for index in range(pair_count)
    ),
    default=None,
  )
  maximum_pressure = max(
    (
      abs(
        outgoing[index].total_pressure_Pa
        - incoming[index].total_pressure_Pa
      )
      for index in range(pair_count)
    ),
    default=None,
  )
  return maximum_coordinate, maximum_state, maximum_pressure
####


def _handoff_converged(
  incoming: tuple[MocChainBoundarySample, ...],
  outgoing: tuple[MocChainBoundarySample, ...],
  request: MocEulerTwoSidedFieldIterationRequest,
) -> bool:
  if len(incoming) != len(outgoing) or not outgoing:
    return False
  ####
  coordinate, state, pressure = _handoff_residuals(incoming, outgoing)
  return bool(
    coordinate is not None
    and state is not None
    and pressure is not None
    and coordinate <= request.handoff_position_tolerance_m
    and state <= request.handoff_state_tolerance
    and pressure <= request.handoff_pressure_tolerance_Pa
  )
####


def _failure(
  status: MocEulerTwoSidedFieldIterationStatus,
  message: str,
  *,
  request: MocEulerTwoSidedFieldIterationRequest | None = None,
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None,
  companion_field: MocEulerCompanionFieldResult | None = None,
  records: tuple[MocEulerTwoSidedFieldIterationRecord, ...] = (),
  final_physical_field: MocEulerAmbientPhysicalFieldResult | None = None,
  final_source_strip: MocAmbientShockStripResult | None = None,
  fixed_point_converged: bool = False,
  field_iteration_verified: bool = False,
) -> MocEulerTwoSidedFieldIterationResult:
  return MocEulerTwoSidedFieldIterationResult(
    status=status,
    request=request,
    shock_boundary=shock_boundary,
    initial_companion_field=companion_field,
    records=records,
    final_physical_field=final_physical_field,
    final_source_strip=final_source_strip,
    fixed_point_converged=fixed_point_converged,
    field_iteration_verified=field_iteration_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )
####


def solve_euler_two_sided_field_iteration(
  request: MocEulerTwoSidedFieldIterationRequest,
) -> MocEulerTwoSidedFieldIterationResult:
  """Iterate an exact physical field against its retained open trace.

  The initial handoff is the downstream frontier of the open companion field.
  Once a bounded physical field is assembled, its explicit open
  shock/ambient source strip supplies the next terminal trace.  No geometry is
  interpolated and no failed iteration is replaced by a lower-fidelity field.
  """

  if not isinstance(request, MocEulerTwoSidedFieldIterationRequest):
    return _failure(
      MocEulerTwoSidedFieldIterationStatus.INVALID_INPUT,
      'request must be a MocEulerTwoSidedFieldIterationRequest',
    )
  ####
  incoming = request.companion_field.downstream_handoff
  records: list[MocEulerTwoSidedFieldIterationRecord] = []
  final_physical_field: MocEulerAmbientPhysicalFieldResult | None = None
  final_source_strip: MocAmbientShockStripResult | None = None
  for iteration_index in range(request.maximum_field_iterations):
    try:
      physical = assemble_euler_ambient_physical_field(
        request.shock_boundary,
        request.ambient_pressure_Pa,
        incoming_handoff=incoming,
        target_centerline_y_m=request.target_centerline_y_m,
        position_tolerance_m=request.position_tolerance_m,
        invariant_tolerance=request.invariant_tolerance,
        pressure_tolerance=request.pressure_tolerance,
        tangent_tolerance=request.tangent_tolerance,
        maximum_boundary_iterations=request.maximum_boundary_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      record = MocEulerTwoSidedFieldIterationRecord(
        iteration_index=iteration_index,
        incoming_handoff_sample_count=len(incoming),
        physical_field=None,
        source_strip=None,
        outgoing_handoff_sample_count=0,
        maximum_coordinate_residual_m=None,
        maximum_state_residual=None,
        maximum_pressure_residual_Pa=None,
        fixed_point_converged=False,
        message=f'exact physical-field iteration raised: {error}',
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedFieldIterationStatus.PHYSICAL_FIELD_FAILURE,
        record.message,
        request=request,
        shock_boundary=request.shock_boundary,
        companion_field=request.companion_field,
        records=tuple(records),
      )
    ####
    final_physical_field = physical
    if not physical.physical_field_verified or physical.field is None:
      record = MocEulerTwoSidedFieldIterationRecord(
        iteration_index=iteration_index,
        incoming_handoff_sample_count=len(incoming),
        physical_field=physical,
        source_strip=None,
        outgoing_handoff_sample_count=0,
        maximum_coordinate_residual_m=None,
        maximum_state_residual=None,
        maximum_pressure_residual_Pa=None,
        fixed_point_converged=False,
        message=(
          'bounded physical-field iteration did not pass its independent '
          f'local gates: {physical.message}'
        ),
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedFieldIterationStatus.PHYSICAL_FIELD_FAILURE,
        record.message,
        request=request,
        shock_boundary=request.shock_boundary,
        companion_field=request.companion_field,
        records=tuple(records),
        final_physical_field=physical,
      )
    ####
    try:
      source_strip = physical.field.as_open_shock_ambient_strip(
        trace_position_tolerance_m=request.source_trace_position_tolerance_m,
        trace_forward_tolerance_m=request.source_trace_forward_tolerance_m,
        trace_invariant_tolerance=request.invariant_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      record = MocEulerTwoSidedFieldIterationRecord(
        iteration_index=iteration_index,
        incoming_handoff_sample_count=len(incoming),
        physical_field=physical,
        source_strip=None,
        outgoing_handoff_sample_count=0,
        maximum_coordinate_residual_m=None,
        maximum_state_residual=None,
        maximum_pressure_residual_Pa=None,
        fixed_point_converged=False,
        message=f'open physical source-strip projection raised: {error}',
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedFieldIterationStatus.SOURCE_STRIP_FAILURE,
        record.message,
        request=request,
        shock_boundary=request.shock_boundary,
        companion_field=request.companion_field,
        records=tuple(records),
        final_physical_field=physical,
      )
    ####
    final_source_strip = source_strip
    outgoing = source_strip.terminal_trace_samples
    coordinate_residual, state_residual, pressure_residual = _handoff_residuals(
      incoming,
      outgoing,
    )
    fixed_point = _handoff_converged(incoming, outgoing, request)
    record = MocEulerTwoSidedFieldIterationRecord(
      iteration_index=iteration_index,
      incoming_handoff_sample_count=len(incoming),
      physical_field=physical,
      source_strip=source_strip,
      outgoing_handoff_sample_count=len(outgoing),
      maximum_coordinate_residual_m=coordinate_residual,
      maximum_state_residual=state_residual,
      maximum_pressure_residual_Pa=pressure_residual,
      fixed_point_converged=fixed_point,
      message=(
        'solver-owned physical field projected to an open terminal trace; '
        + (
          'trace fixed point reached'
          if fixed_point
          else 'trace retained for the next field iteration'
        )
      ),
    )
    records.append(record)
    if fixed_point:
      return _failure(
        MocEulerTwoSidedFieldIterationStatus.CONVERGED_FIXED_POINT,
        'two-sided exact-Euler field iteration reached a retained terminal-trace fixed point; canonical moving free-boundary closure, conservative refinement, and external validation remain pending',
        request=request,
        shock_boundary=request.shock_boundary,
        companion_field=request.companion_field,
        records=tuple(records),
        final_physical_field=physical,
        final_source_strip=source_strip,
        fixed_point_converged=True,
        field_iteration_verified=True,
      )
    ####
    incoming = outgoing
  ####
  return _failure(
    MocEulerTwoSidedFieldIterationStatus.ITERATION_LIMIT,
    'two-sided exact-Euler field iteration retained a bounded physical field but did not reach a terminal-trace fixed point before the iteration limit',
    request=request,
    shock_boundary=request.shock_boundary,
    companion_field=request.companion_field,
    records=tuple(records),
    final_physical_field=final_physical_field,
    final_source_strip=final_source_strip,
  )
####
