"""Solver-owned upstream remeshing at a planar-MOC caustic.

The reflected source strip can terminate at a characteristic caustic before
the next shock has a bounded upstream field.  A valid continuation needs a
new Cauchy patch, not a branch switch or an extrapolated last state.  This
module owns the narrow numerical seam for that patch: a caller supplies a
centerline ``C+`` trace and an outer/pre-shock ``C-`` trace, and the solver
assembles and checks the compatible source-boundary field between them.

The result is an open upstream field.  It is suitable as the bounded source
for one explicitly planned next-shock attempt, but it is not a shock closure,
an ambient boundary, or a promoted physical chain cell.  The two source
traces are intentionally inputs because finding the outer trace is the
remaining coupled free-boundary problem for the canonical reflected plume.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  MocSourceStripCausticShockSeedResult,
  assemble_source_characteristic_strip,
)

__all__ = (
  'MocCausticUpstreamRemeshStatus',
  'MocCausticUpstreamRemeshRequest',
  'MocCausticUpstreamRemeshResult',
  'solve_caustic_upstream_remesh',
)


class MocCausticUpstreamRemeshStatus(str, Enum):
  """Outcome of the centerline-conditioned upstream remesh."""

  CONVERGED_BOUNDED_FIELD = 'converged_bounded_caustic_upstream_field'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'caustic_upstream_remesh_seed_failure'
  EVENT_SEAM_FAILURE = 'caustic_upstream_remesh_event_seam_failure'
  CENTERLINE_TRACE_FAILURE = 'caustic_upstream_remesh_centerline_trace_failure'
  OUTER_TRACE_FAILURE = 'caustic_upstream_remesh_outer_trace_failure'
  FIELD_FAILURE = 'caustic_upstream_remesh_field_failure'
####


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  """Compare a trace state without replacing the supplied source state."""

  return (
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


@dataclass(frozen=True, slots=True)
class MocCausticUpstreamRemeshRequest:
  """Explicit Cauchy data for a new upstream characteristic patch.

  ``outer_source_states[0]`` is the selected one-sided pre-shock state at the
  caustic event.  Later outer samples are the trace that a coupled physical
  remesher must provide.  No default outer trace is generated here.
  """

  seed: MocSourceStripCausticShockSeedResult
  upstream_edge_index: int
  centerline_source_states: tuple[CharacteristicState, ...]
  outer_source_states: tuple[CharacteristicState, ...]
  total_pressure_Pa: float
  centerline_y_m: float = 0.0
  outer_boundary_kind: str = 'caustic-conditioned-pre-shock-boundary'
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  # Keep this optional provenance field after the established defaulted
  # arguments so existing positional request construction remains compatible.
  # Continued-cell sequences require later provider results to echo the exact
  # prior chain handoff so the upstream-domain solve cannot be detached from
  # the cell being continued.
  incoming_handoff: tuple[MocChainBoundarySample, ...] = ()

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocSourceStripCausticShockSeedResult):
      raise TypeError(
        'seed must be a MocSourceStripCausticShockSeedResult'
      )
    ####
    if not self.seed.converged:
      raise ValueError(
        'caustic upstream remesh requires a converged one-sided seed'
      )
    ####
    if (
      isinstance(self.upstream_edge_index, bool)
      or not isinstance(self.upstream_edge_index, int)
      or self.upstream_edge_index not in (0, 1)
    ):
      raise ValueError('upstream_edge_index must be 0 or 1')
    ####
    try:
      centerline = tuple(self.centerline_source_states)
      outer = tuple(self.outer_source_states)
    except TypeError as error:
      raise TypeError('source traces must be iterable') from error
    ####
    if len(centerline) < 3 or len(outer) < 3:
      raise ValueError(
        'caustic upstream remesh requires at least three samples on each trace'
      )
    ####
    if len(centerline) != len(outer):
      raise ValueError(
        'caustic upstream remesh requires equal-length source traces'
      )
    ####
    if any(
      not isinstance(state, CharacteristicState)
      for state in (*centerline, *outer)
    ):
      raise TypeError('source traces must contain CharacteristicState values')
    ####
    event = self.seed.event
    if event is None or event.caustic_point_m is None:
      raise ValueError(
        'caustic upstream remesh requires a bounded detected caustic event'
      )
    ####
    pressure = float(self.total_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('total_pressure_Pa must be finite and positive')
    ####
    seed_pressure = self.seed.total_pressure_Pa
    if seed_pressure is None or not isfinite(float(seed_pressure)) or seed_pressure <= 0.0:
      raise ValueError('seed must retain a finite positive total pressure')
    ####
    if abs(pressure - float(seed_pressure)) > 1.0e-12 * max(
      1.0,
      abs(pressure),
      abs(float(seed_pressure)),
    ):
      raise ValueError(
        'total_pressure_Pa must match the caustic seed total pressure'
      )
    ####
    try:
      incoming_handoff = tuple(self.incoming_handoff)
    except TypeError as error:
      raise TypeError('incoming_handoff must be iterable') from error
    ####
    if any(
      not isinstance(sample, MocChainBoundarySample)
      for sample in incoming_handoff
    ):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    ####
    if incoming_handoff and len(incoming_handoff) < 3:
      raise ValueError(
        'incoming_handoff requires at least three samples when supplied'
      )
    ####
    centerline_y = float(self.centerline_y_m)
    if not isfinite(centerline_y):
      raise ValueError('centerline_y_m must be finite')
    ####
    tolerance = float(self.position_tolerance_m)
    invariant_tolerance = float(self.invariant_tolerance)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    if not isfinite(invariant_tolerance) or invariant_tolerance <= 0.0:
      raise ValueError('invariant_tolerance must be finite and positive')
    ####
    if abs(centerline_y) > tolerance:
      raise ValueError(
        'the current planar source-strip assembler requires centerline_y_m=0'
      )
    ####
    boundary_kind = str(self.outer_boundary_kind)
    if not boundary_kind:
      raise ValueError('outer_boundary_kind must be a non-empty string')
    ####
    edge = self.seed.edge_states[self.upstream_edge_index]
    if edge.state is None or edge.static_pressure_Pa is None:
      raise ValueError('selected seed edge must retain state and pressure')
    ####
    object.__setattr__(self, 'centerline_source_states', centerline)
    object.__setattr__(self, 'outer_source_states', outer)
    object.__setattr__(self, 'total_pressure_Pa', pressure)
    object.__setattr__(self, 'incoming_handoff', incoming_handoff)
    object.__setattr__(self, 'centerline_y_m', centerline_y)
    object.__setattr__(self, 'outer_boundary_kind', boundary_kind)
    object.__setattr__(self, 'position_tolerance_m', tolerance)
    object.__setattr__(self, 'invariant_tolerance', invariant_tolerance)
  ####

  @property
  def event_point_m(self) -> tuple[float, float]:
    """Return the exact caustic point retained by the seed."""

    assert self.seed.event is not None
    assert self.seed.event.caustic_point_m is not None
    return self.seed.event.caustic_point_m
  ####

  @property
  def selected_upstream_state(self) -> CharacteristicState:
    """Return the selected one-sided state at the event."""

    state = self.seed.edge_states[self.upstream_edge_index].state
    assert state is not None
    return state
  ####

  @property
  def selected_upstream_static_pressure_Pa(self) -> float:
    """Return the selected one-sided static pressure at the event."""

    pressure = self.seed.edge_states[self.upstream_edge_index].static_pressure_Pa
    assert pressure is not None
    return float(pressure)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'event_point_m': self.event_point_m,
      'upstream_edge_index': self.upstream_edge_index,
      'centerline_source_count': len(self.centerline_source_states),
      'outer_source_count': len(self.outer_source_states),
      'total_pressure_Pa': self.total_pressure_Pa,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'incoming_handoff_points_m': [
        list(sample.point_m) for sample in self.incoming_handoff
      ],
      'incoming_handoff_total_pressure_Pa': [
        sample.total_pressure_Pa for sample in self.incoming_handoff
      ],
      'centerline_y_m': self.centerline_y_m,
      'outer_boundary_kind': self.outer_boundary_kind,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'source_data_model': (
        'explicit-centerline-c-plus-and-outer-pre-shock-c-minus-traces'
      ),
      'outer_trace_generation': 'caller-supplied-coupled-remesher-data',
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocCausticUpstreamRemeshResult:
  """A bounded characteristic field assembled from explicit Cauchy traces."""

  status: MocCausticUpstreamRemeshStatus
  request: MocCausticUpstreamRemeshRequest | None
  strip: MocSourceCharacteristicStripResult | None
  event_seam_verified: bool
  centerline_trace_verified: bool
  outer_trace_verified: bool
  source_field_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocCausticUpstreamRemeshStatus):
      raise TypeError('status must be a MocCausticUpstreamRemeshStatus')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocCausticUpstreamRemeshRequest,
    ):
      raise TypeError(
        'request must be a MocCausticUpstreamRemeshRequest or None'
      )
    ####
    if self.strip is not None and not isinstance(
      self.strip,
      MocSourceCharacteristicStripResult,
    ):
      raise TypeError(
        'strip must be a MocSourceCharacteristicStripResult or None'
      )
    ####
    for name in (
      'event_seam_verified',
      'centerline_trace_verified',
      'outer_trace_verified',
      'source_field_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocCausticUpstreamRemeshStatus.CONVERGED_BOUNDED_FIELD
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether the result exposes a finite state/pressure source domain."""

    return bool(
      self.converged
      and self.strip is not None
      and self.strip.converged
      and self.source_field_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The source remesh has no shock, ambient, or downstream closure."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the bounded source result to a non-physical planner stop."""

    if self.status is MocCausticUpstreamRemeshStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocCausticUpstreamRemeshStatus.CENTERLINE_TRACE_FAILURE,
      MocCausticUpstreamRemeshStatus.OUTER_TRACE_FAILURE,
    ):
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is MocCausticUpstreamRemeshStatus.CONVERGED_BOUNDED_FIELD:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    else:
      reason = MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'caustic upstream remesh is a bounded source field, not a '
        'promotable shock-cell closure'
      ),
      diagnostics={
        'termination_model': 'caustic-upstream-cauchy-remesh',
        'remesh_status': self.status.value,
        'event_point_m': (
          None if self.request is None else self.request.event_point_m
        ),
        'event_seam_verified': self.event_seam_verified,
        'centerline_trace_verified': self.centerline_trace_verified,
        'outer_trace_verified': self.outer_trace_verified,
        'source_field_verified': self.source_field_verified,
        'state_sampling_available': self.state_sampling_available,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'event_seam_verified': self.event_seam_verified,
      'centerline_trace_verified': self.centerline_trace_verified,
      'outer_trace_verified': self.outer_trace_verified,
      'source_field_verified': self.source_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'request': None if self.request is None else self.request.as_report(),
      'strip': None if self.strip is None else self.strip.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocCausticUpstreamRemeshStatus,
  *,
  request: MocCausticUpstreamRemeshRequest | None = None,
  strip: MocSourceCharacteristicStripResult | None = None,
  event_seam_verified: bool = False,
  centerline_trace_verified: bool = False,
  outer_trace_verified: bool = False,
  source_field_verified: bool = False,
  message: str,
) -> MocCausticUpstreamRemeshResult:
  return MocCausticUpstreamRemeshResult(
    status=status,
    request=request,
    strip=strip,
    event_seam_verified=event_seam_verified,
    centerline_trace_verified=centerline_trace_verified,
    outer_trace_verified=outer_trace_verified,
    source_field_verified=source_field_verified,
    message=message,
  )
####


def solve_caustic_upstream_remesh(
  request: MocCausticUpstreamRemeshRequest,
) -> MocCausticUpstreamRemeshResult:
  """Assemble and verify the explicit Cauchy patch at a caustic.

  This function solves compatibility and topology only.  The outer trace is
  never generated, extended, or extrapolated.  Consequently a converged
  result supplies a bounded upstream field for research continuation while
  keeping shock/entropy and ambient closure as separate gates.
  """

  if not isinstance(request, MocCausticUpstreamRemeshRequest):
    return _failure(
      MocCausticUpstreamRemeshStatus.INVALID_INPUT,
      message='request must be a MocCausticUpstreamRemeshRequest',
    )
  ####
  event = request.event_point_m
  selected_state = request.selected_upstream_state
  outer = request.outer_source_states
  centerline = request.centerline_source_states
  position_tolerance = request.position_tolerance_m
  invariant_tolerance = request.invariant_tolerance

  first_outer = outer[0]
  event_point_verified = (
    abs(first_outer.x_m - event[0]) <= position_tolerance
    and abs(first_outer.y_m - event[1]) <= position_tolerance
  )
  event_state_verified = _state_matches(
    first_outer,
    selected_state,
    position_tolerance_m=position_tolerance,
    state_tolerance=invariant_tolerance,
  )
  event_seam_verified = event_point_verified and event_state_verified
  if not event_seam_verified:
    return _failure(
      MocCausticUpstreamRemeshStatus.EVENT_SEAM_FAILURE,
      request=request,
      outer_trace_verified=False,
      message=(
        'outer pre-shock trace must begin at the exact selected one-sided '
        'caustic point and state'
      ),
    )
  ####

  centerline_trace_verified = bool(
    all(
      abs(state.y_m - request.centerline_y_m) <= position_tolerance
      and abs(state.theta_rad) <= invariant_tolerance
      for state in centerline
    )
    and all(
      next_state.x_m > state.x_m + position_tolerance
      for state, next_state in zip(centerline, centerline[1:])
    )
    and centerline[-1].x_m < first_outer.x_m - position_tolerance
  )
  if not centerline_trace_verified:
    return _failure(
      MocCausticUpstreamRemeshStatus.CENTERLINE_TRACE_FAILURE,
      request=request,
      event_seam_verified=event_seam_verified,
      message=(
        'centerline C+ trace must be a strictly downstream, theta=0 trace '
        'whose final source remains upstream of the caustic outer trace'
      ),
    )
  ####

  outer_trace_verified = bool(
    all(
      state.y_m >= request.centerline_y_m - position_tolerance
      for state in outer
    )
    and all(
      next_state.x_m > state.x_m + position_tolerance
      for state, next_state in zip(outer, outer[1:])
    )
  )
  if not outer_trace_verified:
    return _failure(
      MocCausticUpstreamRemeshStatus.OUTER_TRACE_FAILURE,
      request=request,
      event_seam_verified=event_seam_verified,
      centerline_trace_verified=centerline_trace_verified,
      message=(
        'outer pre-shock trace must remain in the half-plane above the '
        'centerline and progress strictly downstream'
      ),
    )
  ####

  strip = assemble_source_characteristic_strip(
    centerline,
    outer,
    request.total_pressure_Pa,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance,
  )
  if not strip.converged:
    return _failure(
      MocCausticUpstreamRemeshStatus.FIELD_FAILURE,
      request=request,
      strip=strip,
      event_seam_verified=event_seam_verified,
      centerline_trace_verified=centerline_trace_verified,
      outer_trace_verified=outer_trace_verified,
      message=f'caustic upstream Cauchy remesh field failed: {strip.message}',
    )
  ####

  sampled_state = strip.state_at(
    event,
    position_tolerance_m=position_tolerance,
  )
  sampled_pressure = strip.static_pressure_at(
    event,
    position_tolerance_m=position_tolerance,
  )
  source_field_verified = bool(
    isinstance(sampled_state, CharacteristicState)
    and _state_matches(
      sampled_state,
      selected_state,
      position_tolerance_m=position_tolerance,
      state_tolerance=invariant_tolerance,
    )
    and sampled_pressure is not None
    and isfinite(float(sampled_pressure))
    and sampled_pressure > 0.0
    and abs(
      float(sampled_pressure) - request.selected_upstream_static_pressure_Pa
    )
    <= 1.0e-10 * max(
      1.0,
      abs(float(sampled_pressure)),
      abs(request.selected_upstream_static_pressure_Pa),
    )
  )
  if not source_field_verified:
    return _failure(
      MocCausticUpstreamRemeshStatus.FIELD_FAILURE,
      request=request,
      strip=strip,
      event_seam_verified=event_seam_verified,
      centerline_trace_verified=centerline_trace_verified,
      outer_trace_verified=outer_trace_verified,
      message=(
        'assembled caustic upstream field did not reproduce the selected '
        'event state and isentropic static pressure'
      ),
    )
  ####
  return MocCausticUpstreamRemeshResult(
    status=MocCausticUpstreamRemeshStatus.CONVERGED_BOUNDED_FIELD,
    request=request,
    strip=strip,
    event_seam_verified=event_seam_verified,
    centerline_trace_verified=centerline_trace_verified,
    outer_trace_verified=outer_trace_verified,
    source_field_verified=True,
    message=(
      'solver-owned caustic upstream Cauchy remesh converged as a bounded '
      'source-characteristic field; shock, entropy, and ambient closure '
      'remain separate gates'
    ),
  )
####
