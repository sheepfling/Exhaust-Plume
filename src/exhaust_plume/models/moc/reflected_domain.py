"""Explicit reflected-domain remeshing for continued planar-MOC cells.

The outgoing front of a terminal reflection patch is a single ``C-``
characteristic.  Reusing that line as an entire new source boundary makes a
triangular source mesh degenerate, so a continued reflected domain needs two
different pieces of data:

* the exact prior ``C-`` front, used as the reflection/alternating-family
  anchor; and
* a newly solved centerline ``C+`` source row and outer source curve.

This module validates that seam and assembles the bounded source field from
the explicit Cauchy data.  It does not invent the free boundary, infer entropy
losses, fit a shock, or promote an open field to a physical chain cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCharacteristicTraceResult,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  MocSourceStripContinuationResult,
  MocSourceStripContinuationStatus,
  assemble_source_characteristic_strip,
  assemble_source_characteristic_strip_with_source_pressures,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocReflectedTracePolarity,
  MocReflectedTracePolarityResult,
  MocTerminalReflectionPatchResult,
  classify_reflected_trace_polarity,
)

__all__ = (
  'MocReflectedDomainRemeshStatus',
  'MocReflectedDomainRemeshRequest',
  'MocReflectedDomainRemeshResult',
  'solve_reflected_domain_remesh',
)


class MocReflectedDomainRemeshStatus(str, Enum):
  """Outcome of an explicit reflected-domain source remesh."""

  CONVERGED_BOUNDED_FIELD = 'converged_bounded_reflected_domain_field'
  INVALID_INPUT = 'invalid_input'
  INCOMING_TRACE_FAILURE = 'reflected_domain_incoming_trace_failure'
  REFLECTION_SEAM_FAILURE = 'reflected_domain_reflection_seam_failure'
  CENTERLINE_SOURCE_FAILURE = 'reflected_domain_centerline_source_failure'
  OUTER_SOURCE_FAILURE = 'reflected_domain_outer_source_failure'
  POLARITY_FAILURE = 'reflected_domain_polarity_failure'
  FIELD_FAILURE = 'reflected_domain_field_failure'


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  """Compare a state at a seam without replacing caller-owned data."""

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


def _pressure_matches(actual: float, expected: float, tolerance: float) -> bool:
  return abs(float(actual) - float(expected)) <= tolerance * max(
    1.0,
    abs(float(actual)),
    abs(float(expected)),
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainRemeshRequest:
  """Cauchy data for one new reflected-domain source field.

  ``reflection_patch.outgoing_trace_samples`` is intentionally retained as a
  separate incoming characteristic.  It is not used as ``outer_source_states``
  because it is one invariant-preserving line, not a two-dimensional source
  curve.  The first centerline source state must be the exact state obtained
  when that incoming line reaches the target centerline.  The remaining
  centerline row and the outer source curve are the coupled remesher's inputs.

  The legacy scalar source-strip path uses one uniform total pressure.  The
  optional source-row pressure arrays preserve a nonuniform entropy lineage
  through the bounded remesh: a node receives the pressure carried by its
  ``C-`` source family.  Those arrays are explicit solver inputs; this request
  still does not infer shock loss or solve an ambient free boundary.
  """

  reflection_patch: MocTerminalReflectionPatchResult
  centerline_source_states: tuple[CharacteristicState, ...]
  outer_source_states: tuple[CharacteristicState, ...]
  total_pressure_Pa: float
  incoming_handoff: tuple[MocChainBoundarySample, ...] = ()
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  declared_polarity: MocReflectedTracePolarity | None = None
  position_tolerance_m: float = 1.0e-3
  trace_forward_tolerance_m: float = 1.0e-4
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  centerline_total_pressure_Pa: tuple[float, ...] = ()
  outer_total_pressure_Pa: tuple[float, ...] = ()

  def __post_init__(self) -> None:
    if not isinstance(
      self.reflection_patch,
      MocTerminalReflectionPatchResult,
    ):
      raise TypeError(
        'reflection_patch must be a MocTerminalReflectionPatchResult'
      )
    try:
      centerline = tuple(self.centerline_source_states)
      outer = tuple(self.outer_source_states)
      handoff = tuple(self.incoming_handoff)
    except TypeError as error:
      raise TypeError(
        'reflected-domain source rows and incoming_handoff must be iterable'
      ) from error
    if len(centerline) < 3 or len(outer) < 3:
      raise ValueError(
        'reflected-domain source rows require at least three samples'
      )
    if len(centerline) != len(outer):
      raise ValueError(
        'reflected-domain centerline and outer source rows must have equal lengths'
      )
    if any(
      not isinstance(state, CharacteristicState)
      for state in (*centerline, *outer)
    ):
      raise TypeError(
        'reflected-domain source rows must contain CharacteristicState values'
      )
    if any(
      not isinstance(sample, MocChainBoundarySample) for sample in handoff
    ):
      raise TypeError(
        'incoming_handoff must contain MocChainBoundarySample values'
      )
    if handoff and len(handoff) < 3:
      raise ValueError(
        'incoming_handoff requires at least three samples when supplied'
      )
    pressure = float(self.total_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('total_pressure_Pa must be finite and positive')
    try:
      centerline_pressures = tuple(
        float(value) for value in self.centerline_total_pressure_Pa
      )
      outer_pressures = tuple(
        float(value) for value in self.outer_total_pressure_Pa
      )
    except (TypeError, ValueError) as error:
      raise ValueError(
        'source-row total pressures must contain finite positive values'
      ) from error
    if not centerline_pressures:
      centerline_pressures = (pressure,) * len(centerline)
    if not outer_pressures:
      outer_pressures = (pressure,) * len(outer)
    if len(centerline_pressures) != len(centerline):
      raise ValueError(
        'centerline_total_pressure_Pa must match centerline_source_states'
      )
    if len(outer_pressures) != len(outer):
      raise ValueError(
        'outer_total_pressure_Pa must match outer_source_states'
      )
    if any(
      not isfinite(value) or value <= 0.0
      for value in (*centerline_pressures, *outer_pressures)
    ):
      raise ValueError(
        'source-row total pressures must contain finite positive values'
      )
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'position_tolerance_m',
      'trace_forward_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or (
        value <= 0.0
        and name in (
          'position_tolerance_m',
          'trace_forward_tolerance_m',
          'invariant_tolerance',
          'pressure_tolerance',
        )
      ):
        raise ValueError(f'{name} must be finite and valid')
    if self.declared_polarity is not None and not isinstance(
      self.declared_polarity,
      MocReflectedTracePolarity,
    ):
      raise TypeError(
        'declared_polarity must be a MocReflectedTracePolarity or None'
      )
    object.__setattr__(self, 'centerline_source_states', centerline)
    object.__setattr__(self, 'outer_source_states', outer)
    object.__setattr__(self, 'incoming_handoff', handoff)
    object.__setattr__(self, 'total_pressure_Pa', pressure)
    object.__setattr__(
      self,
      'centerline_total_pressure_Pa',
      centerline_pressures,
    )
    object.__setattr__(self, 'outer_total_pressure_Pa', outer_pressures)
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
      'position_tolerance_m',
      'trace_forward_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      object.__setattr__(self, name, float(getattr(self, name)))
  ####

  @property
  def incoming_trace(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the exact prior patch front used at the reflection seam."""

    return self.reflection_patch.outgoing_trace_samples
  ####

  @property
  def incoming_anchor(self) -> MocChainBoundarySample:
    """Return the centerline endpoint of the prior reflected ``C-`` front."""

    return self.incoming_trace[-1]
  ####

  @property
  def source_model(self) -> str:
    return (
      'explicit-reflected-domain-variable-entropy-cauchy-remesh'
      if self.variable_total_pressure
      else 'explicit-reflected-domain-cauchy-remesh'
    )
  ####

  @property
  def variable_total_pressure(self) -> bool:
    """Whether source-family pressure differs from the legacy scalar value."""

    values = (
      *self.centerline_total_pressure_Pa,
      *self.outer_total_pressure_Pa,
    )
    return any(
      not _pressure_matches(value, self.total_pressure_Pa, self.pressure_tolerance)
      for value in values
    )
  ####

  def as_report(self) -> dict[str, object]:
    incoming = self.incoming_trace
    return {
      'source_model': self.source_model,
      'reflection_patch_status': self.reflection_patch.status.value,
      'incoming_trace_family': CharacteristicFamily.MINUS.value,
      'incoming_trace_kind': 'prior-single-c-minus-reflection-front',
      'incoming_trace_sample_count': len(incoming),
      'incoming_trace_start_m': incoming[0].point_m if incoming else None,
      'incoming_trace_end_m': incoming[-1].point_m if incoming else None,
      'incoming_anchor_state': (
        None
        if not incoming
        else {
          'theta_rad': self.incoming_anchor.state.theta_rad,
          'mach': self.incoming_anchor.state.mach,
          'gamma': self.incoming_anchor.state.gamma,
        }
      ),
      'centerline_source_family': CharacteristicFamily.PLUS.value,
      'centerline_source_count': len(self.centerline_source_states),
      'outer_source_family': CharacteristicFamily.MINUS.value,
      'outer_source_count': len(self.outer_source_states),
      'outer_source_is_new_curve': True,
      'incoming_trace_reused_as_outer_source': False,
      'total_pressure_Pa': self.total_pressure_Pa,
      'centerline_total_pressure_Pa': list(self.centerline_total_pressure_Pa),
      'outer_total_pressure_Pa': list(self.outer_total_pressure_Pa),
      'variable_total_pressure': self.variable_total_pressure,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'declared_polarity': (
        None if self.declared_polarity is None else self.declared_polarity.value
      ),
      'position_tolerance_m': self.position_tolerance_m,
      'trace_forward_tolerance_m': self.trace_forward_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'entropy_model': (
        'source-family-carried-total-pressure'
        if self.variable_total_pressure
        else 'single-uniform-total-pressure-source-strip'
      ),
      'nonuniform_entropy_data_carried': self.variable_total_pressure,
      'nonuniform_entropy_remesh_solved': False,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainRemeshResult:
  """A bounded source field with an audited reflected-family seam."""

  status: MocReflectedDomainRemeshStatus
  request: MocReflectedDomainRemeshRequest | None
  source_strip: MocSourceCharacteristicStripResult | None
  incoming_trace_validation: MocCharacteristicTraceResult | None
  incoming_trace_polarity: MocReflectedTracePolarityResult | None
  reflection_seam_verified: bool
  centerline_source_verified: bool
  outer_source_verified: bool
  source_field_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainRemeshStatus):
      raise TypeError('status must be a MocReflectedDomainRemeshStatus')
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainRemeshRequest,
    ):
      raise TypeError(
        'request must be a MocReflectedDomainRemeshRequest or None'
      )
    if self.source_strip is not None and not isinstance(
      self.source_strip,
      MocSourceCharacteristicStripResult,
    ):
      raise TypeError(
        'source_strip must be a MocSourceCharacteristicStripResult or None'
      )
    if self.incoming_trace_validation is not None and not isinstance(
      self.incoming_trace_validation,
      MocCharacteristicTraceResult,
    ):
      raise TypeError(
        'incoming_trace_validation must be a MocCharacteristicTraceResult or None'
      )
    if self.incoming_trace_polarity is not None and not isinstance(
      self.incoming_trace_polarity,
      MocReflectedTracePolarityResult,
    ):
      raise TypeError(
        'incoming_trace_polarity must be a MocReflectedTracePolarityResult or None'
      )
    for name in (
      'reflection_seam_verified',
      'centerline_source_verified',
      'outer_source_verified',
      'source_field_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD
  ####

  @property
  def state_sampling_available(self) -> bool:
    return bool(
      self.converged
      and self.source_field_verified
      and self.source_strip is not None
      and self.source_strip.converged
      and self.source_strip.topology.connected
      and self.source_strip.topology.forms_closed_zone
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The source remesh has no shock or downstream physical closure."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_source_continuation(self) -> MocSourceStripContinuationResult:
    """Adapt the bounded domain to the existing source-chain planner."""

    if not self.state_sampling_available or self.source_strip is None:
      raise ValueError(
        'a reflected-domain source continuation requires a converged bounded '
        'source field'
      )
    request = self.request
    assert request is not None
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.CONVERGED_EXTENDED,
      strip=self.source_strip,
      plus_source_states=request.centerline_source_states,
      minus_source_states=request.outer_source_states,
      added_sample_count=0,
      axis_step_m=None,
      continuation_k_plus=None,
      message=(
        'reflected-domain Cauchy remesh adapted to the bounded source-strip '
        'planner; shock and physical closure remain separate'
      ),
      full_strip=self.source_strip,
      continuation_law=self.request.source_model,
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the remesh gate to a non-physical planner stop."""

    if self.status is MocReflectedDomainRemeshStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocReflectedDomainRemeshStatus.INCOMING_TRACE_FAILURE,
      MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE,
      MocReflectedDomainRemeshStatus.CENTERLINE_SOURCE_FAILURE,
      MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE,
      MocReflectedDomainRemeshStatus.POLARITY_FAILURE,
    ):
      reason = MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    elif self.status is MocReflectedDomainRemeshStatus.FIELD_FAILURE:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'reflected-domain remesh is a bounded source field, not a '
        'promotable physical shock-cell closure'
      ),
      diagnostics={
        'termination_model': 'reflected-domain-cauchy-remesh',
        'remesh_status': self.status.value,
        'reflection_seam_verified': self.reflection_seam_verified,
        'centerline_source_verified': self.centerline_source_verified,
        'outer_source_verified': self.outer_source_verified,
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
      'reflection_seam_verified': self.reflection_seam_verified,
      'centerline_source_verified': self.centerline_source_verified,
      'outer_source_verified': self.outer_source_verified,
      'source_field_verified': self.source_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'request': None if self.request is None else self.request.as_report(),
      'incoming_trace_validation': (
        None
        if self.incoming_trace_validation is None
        else self.incoming_trace_validation.as_report()
      ),
      'incoming_trace_polarity': (
        None
        if self.incoming_trace_polarity is None
        else self.incoming_trace_polarity.as_report()
      ),
      'source_strip': (
        None if self.source_strip is None else self.source_strip.as_report()
      ),
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
  ####


def _failure(
  status: MocReflectedDomainRemeshStatus,
  *,
  request: MocReflectedDomainRemeshRequest | None = None,
  incoming_trace_validation: MocCharacteristicTraceResult | None = None,
  incoming_trace_polarity: MocReflectedTracePolarityResult | None = None,
  source_strip: MocSourceCharacteristicStripResult | None = None,
  reflection_seam_verified: bool = False,
  centerline_source_verified: bool = False,
  outer_source_verified: bool = False,
  source_field_verified: bool = False,
  message: str,
) -> MocReflectedDomainRemeshResult:
  return MocReflectedDomainRemeshResult(
    status=status,
    request=request,
    source_strip=source_strip,
    incoming_trace_validation=incoming_trace_validation,
    incoming_trace_polarity=incoming_trace_polarity,
    reflection_seam_verified=reflection_seam_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    source_field_verified=source_field_verified,
    message=message,
  )


def solve_reflected_domain_remesh(
  request: MocReflectedDomainRemeshRequest,
) -> MocReflectedDomainRemeshResult:
  """Validate and assemble one explicit reflected-domain source patch.

  The incoming patch front is validated as a single ``C-`` characteristic.
  The first centerline source state must reproduce its exact centerline
  endpoint.  The new source rows then pass through the ordinary compatibility
  assembler, which is the gate that verifies every diagonal seam.  No source
  row is inferred from the old front and no extrapolation is used.
  """

  if not isinstance(request, MocReflectedDomainRemeshRequest):
    return _failure(
      MocReflectedDomainRemeshStatus.INVALID_INPUT,
      message='request must be a MocReflectedDomainRemeshRequest',
    )
  patch = request.reflection_patch
  if not patch.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.INVALID_INPUT,
      request=request,
      message='reflected-domain remesh requires a converged reflection patch',
    )
  incoming = request.incoming_trace
  incoming_validation = validate_characteristic_trace(
    incoming,
    CharacteristicFamily.MINUS,
    position_tolerance_m=request.position_tolerance_m,
    forward_position_tolerance_m=request.trace_forward_tolerance_m,
    invariant_tolerance=request.invariant_tolerance,
  )
  if not incoming_validation.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.INCOMING_TRACE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      message=f'incoming reflected C- trace failed: {incoming_validation.message}',
    )
  polarity = classify_reflected_trace_polarity(
    incoming,
    target_centerline_y_m=request.target_centerline_y_m,
    target_centerline_flow_angle_rad=request.target_centerline_flow_angle_rad,
    position_tolerance_m=request.position_tolerance_m,
    forward_position_tolerance_m=request.trace_forward_tolerance_m,
    invariant_tolerance=request.invariant_tolerance,
  )
  if not polarity.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.INCOMING_TRACE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      message=f'incoming reflected trace polarity failed: {polarity.message}',
    )
  if (
    request.declared_polarity is not None
    and request.declared_polarity is not polarity.status
  ):
    return _failure(
      MocReflectedDomainRemeshStatus.POLARITY_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      message=(
        'declared reflected trace polarity does not match the exact incoming '
        f'trace evidence: declared={request.declared_polarity.value}, '
        f'observed={polarity.status.value}'
      ),
    )

  anchor = request.incoming_anchor
  centerline = request.centerline_source_states
  first_centerline = centerline[0]
  reflection_seam_verified = bool(
    abs(anchor.state.y_m - request.target_centerline_y_m)
    <= request.position_tolerance_m
    and abs(anchor.state.theta_rad - request.target_centerline_flow_angle_rad)
    <= request.invariant_tolerance
    and _state_matches(
      first_centerline,
      anchor.state,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.invariant_tolerance,
    )
    and _pressure_matches(
      anchor.total_pressure_Pa,
      request.total_pressure_Pa,
      request.pressure_tolerance,
    )
  )
  if not reflection_seam_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.REFLECTION_SEAM_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      message=(
        'the first new centerline C+ source state must reproduce the exact '
        'incoming C- reflection endpoint and total pressure'
      ),
    )

  common_gamma = first_centerline.gamma
  centerline_source_verified = bool(
    all(
      abs(state.gamma - common_gamma) <= request.invariant_tolerance
      and abs(state.y_m - request.target_centerline_y_m)
      <= request.position_tolerance_m
      and abs(state.theta_rad - request.target_centerline_flow_angle_rad)
      <= request.invariant_tolerance
      for state in centerline
    )
    and _pressure_matches(
      request.centerline_total_pressure_Pa[0],
      anchor.total_pressure_Pa,
      request.pressure_tolerance,
    )
    and all(
      next_state.x_m > state.x_m + request.position_tolerance_m
      for state, next_state in zip(centerline, centerline[1:])
    )
  )
  if not centerline_source_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.CENTERLINE_SOURCE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      reflection_seam_verified=reflection_seam_verified,
      message=(
        'new centerline C+ source states must remain on the target centerline, '
        'match its flow angle, and progress strictly downstream'
      ),
    )

  outer = request.outer_source_states
  outer_source_verified = bool(
    all(
      abs(state.gamma - common_gamma) <= request.invariant_tolerance
      and state.y_m > request.target_centerline_y_m + request.position_tolerance_m
      for state in outer
    )
    and all(
      next_state.x_m > state.x_m + request.position_tolerance_m
      for state, next_state in zip(outer, outer[1:])
    )
    and outer[0].x_m > first_centerline.x_m + request.position_tolerance_m
    and max(state.k_minus for state in outer)
    - min(state.k_minus for state in outer)
    > request.invariant_tolerance
  )
  if not outer_source_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.OUTER_SOURCE_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      message=(
        'new outer source data must be a downstream, above-centerline curve '
        'with varying C- invariant; the prior single C- front cannot be reused'
      ),
    )

  incoming_pressure_uniform = all(
    _pressure_matches(
      sample.total_pressure_Pa,
      request.total_pressure_Pa,
      request.pressure_tolerance,
    )
    for sample in incoming
  )
  if not incoming_pressure_uniform and not request.variable_total_pressure:
    return _failure(
      MocReflectedDomainRemeshStatus.FIELD_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      outer_source_verified=outer_source_verified,
      message=(
        'the uniform source-strip remesh requires one uniform total pressure; '
        'provide source-row pressure data for variable-entropy transport'
      ),
    )

  if request.variable_total_pressure:
    strip = assemble_source_characteristic_strip_with_source_pressures(
      centerline,
      outer,
      request.centerline_total_pressure_Pa,
      request.outer_total_pressure_Pa,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
    )
  else:
    strip = assemble_source_characteristic_strip(
      centerline,
      outer,
      request.total_pressure_Pa,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
    )
  if not strip.converged:
    return _failure(
      MocReflectedDomainRemeshStatus.FIELD_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      source_strip=strip,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      outer_source_verified=outer_source_verified,
      message=f'reflected-domain source field failed: {strip.message}',
    )
  sampled_anchor = strip.state_at(
    (first_centerline.x_m, first_centerline.y_m),
    position_tolerance_m=request.position_tolerance_m,
  )
  sampled_static_pressure = strip.static_pressure_at(
    (first_centerline.x_m, first_centerline.y_m),
    position_tolerance_m=request.position_tolerance_m,
  )
  sampled_total_pressure = strip.total_pressure_at(
    (first_centerline.x_m, first_centerline.y_m),
    position_tolerance_m=request.position_tolerance_m,
  )
  source_field_verified = bool(
    isinstance(sampled_anchor, CharacteristicState)
    and _state_matches(
      sampled_anchor,
      anchor.state,
      position_tolerance_m=request.position_tolerance_m,
      state_tolerance=request.invariant_tolerance,
    )
    and sampled_static_pressure is not None
    and isfinite(float(sampled_static_pressure))
    and sampled_static_pressure > 0.0
    and sampled_total_pressure is not None
    and isfinite(float(sampled_total_pressure))
    and sampled_total_pressure > 0.0
    and _pressure_matches(
      sampled_total_pressure,
      request.centerline_total_pressure_Pa[0],
      request.pressure_tolerance,
    )
  )
  if not source_field_verified:
    return _failure(
      MocReflectedDomainRemeshStatus.FIELD_FAILURE,
      request=request,
      incoming_trace_validation=incoming_validation,
      incoming_trace_polarity=polarity,
      source_strip=strip,
      reflection_seam_verified=reflection_seam_verified,
      centerline_source_verified=centerline_source_verified,
      outer_source_verified=outer_source_verified,
      message=(
        'reflected-domain source field did not reproduce the exact reflection '
        'anchor state and total pressure'
      ),
    )
  return MocReflectedDomainRemeshResult(
    status=MocReflectedDomainRemeshStatus.CONVERGED_BOUNDED_FIELD,
    request=request,
    source_strip=strip,
    incoming_trace_validation=incoming_validation,
    incoming_trace_polarity=polarity,
    reflection_seam_verified=reflection_seam_verified,
    centerline_source_verified=centerline_source_verified,
    outer_source_verified=outer_source_verified,
    source_field_verified=True,
    message=(
      'explicit reflected-domain Cauchy remesh converged as a bounded source '
      'field; shock-loss inference, ambient closure, and promotion remain '
      'separate gates'
    ),
  )
