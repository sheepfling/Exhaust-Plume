"""Fail-closed consumption of the global mixed-regime conservative trace.

The global physical field and the coupled downstream field are deliberately
different solver products.  The coupled field already exposes a full
conservative-state trace, but retaining that trace alone is not feedback into
the global solver.  This module is the explicit model-side consumer seam: it
rebuilds the trace from the retained coupled field, checks exact closure
lineage, and derives a conservative boundary-flux record from every adjacent
state pair.

The consumer is useful evidence for the next mixed-regime solver slice.  It
does not claim that the upstream global equations were re-solved, that the
free boundary is canonical, or that the candidate is suitable for a product
claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  GLOBAL_COUPLED_DOWNSTREAM_BOUNDARY_TRACE_MODEL,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace,
  MocReflectedDomainGlobalCoupledDownstreamResult,
  build_reflected_domain_global_coupled_downstream_boundary_trace,
)
from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryFluxMode,
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  solve_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_MODEL',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerStatus',
  'MocReflectedDomainGlobalMixedRegimeConservativeFluxSample',
  'MocReflectedDomainGlobalMixedRegimeStateConsumerResult',
  'consume_reflected_domain_global_mixed_regime_state',
  'MocReflectedDomainGlobalMixedRegimeStateResolveStatus',
  'MocReflectedDomainGlobalMixedRegimeStateResolveResult',
  'build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame',
  'build_reflected_domain_global_mixed_regime_conservative_boundary_profile',
  'solve_reflected_domain_global_mixed_regime_state_consumer',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_MODEL = (
  'research-global-mixed-regime-state-consumer-v1'
)


class MocReflectedDomainGlobalMixedRegimeStateConsumerStatus(str, Enum):
  """Typed outcomes of one full-state downstream consumption attempt."""

  CONSUMED_LOCAL_RESEARCH_STATE = (
    'consumed-local-global-mixed-regime-research-state'
  )
  INVALID_INPUT = 'invalid_input'
  CLOSURE_LINEAGE_FAILURE = 'global-mixed-regime-consumer-lineage-failure'
  TRACE_NOT_READY = 'global-mixed-regime-consumer-trace-not-ready'
  TRACE_REPLAY_FAILURE = 'global-mixed-regime-consumer-trace-replay-failure'
  STATE_AUDIT_FAILURE = 'global-mixed-regime-consumer-state-audit-failure'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeConservativeFluxSample:
  """Conservative flux through one oriented trace segment.

  The normal is the deterministic left normal of the retained boundary
  segment.  Its orientation is a reporting convention; no wall direction or
  physical sign is inferred from the downstream mesh.
  """

  segment_index: int
  midpoint_m: tuple[float, float]
  normal_m: tuple[float, float]
  segment_length_m: float
  mass_flux_kg_m2_s: float
  streamwise_momentum_flux_Pa: float
  transverse_momentum_flux_Pa: float
  energy_flux_W_m2: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.segment_index, bool)
      or not isinstance(self.segment_index, int)
      or self.segment_index < 0
    ):
      raise ValueError('segment_index must be a nonnegative integer')
    midpoint = tuple(float(value) for value in self.midpoint_m)
    normal = tuple(float(value) for value in self.normal_m)
    if len(midpoint) != 2 or any(not isfinite(value) for value in midpoint):
      raise ValueError('midpoint_m must contain two finite coordinates')
    if len(normal) != 2 or any(not isfinite(value) for value in normal):
      raise ValueError('normal_m must contain two finite components')
    normal_norm = hypot(normal[0], normal[1])
    if abs(normal_norm - 1.0) > 1.0e-9:
      raise ValueError('normal_m must be a unit vector')
    object.__setattr__(self, 'midpoint_m', midpoint)
    object.__setattr__(self, 'normal_m', normal)
    for name in (
      'segment_length_m',
      'mass_flux_kg_m2_s',
      'streamwise_momentum_flux_Pa',
      'transverse_momentum_flux_Pa',
      'energy_flux_W_m2',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      if name == 'segment_length_m' and value <= 0.0:
        raise ValueError('segment_length_m must be positive')
      object.__setattr__(self, name, value)
    ####

  def as_report(self) -> dict[str, Any]:
    return {
      'segment_index': self.segment_index,
      'midpoint_m': self.midpoint_m,
      'normal_m': self.normal_m,
      'segment_length_m': self.segment_length_m,
      'mass_flux_kg_m2_s': self.mass_flux_kg_m2_s,
      'streamwise_momentum_flux_Pa': self.streamwise_momentum_flux_Pa,
      'transverse_momentum_flux_Pa': self.transverse_momentum_flux_Pa,
      'energy_flux_W_m2': self.energy_flux_W_m2,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateConsumerResult:
  """Audited evidence produced by the explicit full-state consumer seam."""

  status: MocReflectedDomainGlobalMixedRegimeStateConsumerStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  trace: MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace | None = None
  conservative_flux_samples: (
    tuple[MocReflectedDomainGlobalMixedRegimeConservativeFluxSample, ...]
  ) = ()
  entropy_proxy_range: tuple[float, float] | None = None
  source_closure_fingerprint: str | None = None
  closure_lineage_verified: bool = False
  global_field_consumed: bool = False
  full_state_trace_consumed: bool = False
  frame_coverage_verified: bool = False
  mass_channel_verified: bool = False
  streamwise_momentum_channel_verified: bool = False
  transverse_momentum_channel_verified: bool = False
  energy_channel_verified: bool = False
  entropy_channel_verified: bool = False
  ambient_channel_verified: bool = False
  centerline_channel_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus,
    ):
      raise TypeError('status must be a typed mixed-regime consumer status')
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('closure must be a typed global physical closure or None')
    if self.downstream is not None and not isinstance(
      self.downstream,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError('downstream must be a typed coupled result or None')
    if self.trace is not None and not isinstance(
      self.trace,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace,
    ):
      raise TypeError('trace must be a typed coupled boundary trace or None')
    flux_samples = tuple(self.conservative_flux_samples)
    if any(
      not isinstance(
        sample,
        MocReflectedDomainGlobalMixedRegimeConservativeFluxSample,
      )
      for sample in flux_samples
    ):
      raise TypeError('conservative_flux_samples must contain typed flux samples')
    if any(
      sample.segment_index != index
      for index, sample in enumerate(flux_samples)
    ):
      raise ValueError('conservative_flux_samples must be segment ordered')
    object.__setattr__(self, 'conservative_flux_samples', flux_samples)
    if self.entropy_proxy_range is not None:
      entropy_range = tuple(float(value) for value in self.entropy_proxy_range)
      if len(entropy_range) != 2 or any(
        not isfinite(value) or value <= 0.0 for value in entropy_range
      ):
        raise ValueError('entropy_proxy_range must contain two finite positives')
      if entropy_range[1] < entropy_range[0]:
        raise ValueError('entropy_proxy_range must be ordered')
      object.__setattr__(self, 'entropy_proxy_range', entropy_range)
    if self.source_closure_fingerprint is not None:
      fingerprint = str(self.source_closure_fingerprint)
      if not fingerprint:
        raise ValueError('source_closure_fingerprint must be non-empty')
      object.__setattr__(self, 'source_closure_fingerprint', fingerprint)
    for name in (
      'closure_lineage_verified',
      'global_field_consumed',
      'full_state_trace_consumed',
      'frame_coverage_verified',
      'mass_channel_verified',
      'streamwise_momentum_channel_verified',
      'transverse_momentum_channel_verified',
      'energy_channel_verified',
      'entropy_channel_verified',
      'ambient_channel_verified',
      'centerline_channel_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('research state consumer cannot claim canonical coupling')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('research state consumer must remain promotion-blocked')
    if self.status is (
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus
      .CONSUMED_LOCAL_RESEARCH_STATE
    ) and not self.consumed_local_research_state:
      raise ValueError('consumed state must pass every local channel gate')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def consumed_local_research_state(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeStateConsumerStatus
      .CONSUMED_LOCAL_RESEARCH_STATE
      and self.closure_lineage_verified
      and self.global_field_consumed
      and self.full_state_trace_consumed
      and self.frame_coverage_verified
      and self.mass_channel_verified
      and self.streamwise_momentum_channel_verified
      and self.transverse_momentum_channel_verified
      and self.energy_channel_verified
      and self.entropy_channel_verified
      and self.ambient_channel_verified
      and self.centerline_channel_verified
    )

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.consumed_local_research_state
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_MODEL,
        'status': self.status.value,
        'source_closure_fingerprint': self.source_closure_fingerprint,
        'consumed_local_research_state': self.consumed_local_research_state,
        'canonical_free_boundary_verified': False,
        'global_coupling_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_STATE_CONSUMER_MODEL,
      'trace_model': GLOBAL_COUPLED_DOWNSTREAM_BOUNDARY_TRACE_MODEL,
      'status': self.status.value,
      'consumed_local_research_state': self.consumed_local_research_state,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'closure_lineage_verified': self.closure_lineage_verified,
      'global_field_consumed': self.global_field_consumed,
      'full_state_trace_consumed': self.full_state_trace_consumed,
      'frame_coverage_verified': self.frame_coverage_verified,
      'mass_channel_verified': self.mass_channel_verified,
      'streamwise_momentum_channel_verified': (
        self.streamwise_momentum_channel_verified
      ),
      'transverse_momentum_channel_verified': (
        self.transverse_momentum_channel_verified
      ),
      'energy_channel_verified': self.energy_channel_verified,
      'entropy_channel_verified': self.entropy_channel_verified,
      'ambient_channel_verified': self.ambient_channel_verified,
      'centerline_channel_verified': self.centerline_channel_verified,
      'entropy_proxy_range': self.entropy_proxy_range,
      'conservative_flux_samples': [
        sample.as_report() for sample in self.conservative_flux_samples
      ],
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeStateConsumerStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  trace: MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace | None = None,
  source_closure_fingerprint: str | None = None,
  closure_lineage_verified: bool = False,
  global_field_consumed: bool = False,
) -> MocReflectedDomainGlobalMixedRegimeStateConsumerResult:
  return MocReflectedDomainGlobalMixedRegimeStateConsumerResult(
    status=status,
    closure=closure,
    downstream=downstream,
    trace=trace,
    source_closure_fingerprint=source_closure_fingerprint,
    closure_lineage_verified=closure_lineage_verified,
    global_field_consumed=global_field_consumed,
    message=message,
  )


def _build_flux_samples(
  trace: MocReflectedDomainGlobalCoupledDownstreamBoundaryTrace,
) -> tuple[MocReflectedDomainGlobalMixedRegimeConservativeFluxSample, ...]:
  samples = trace.samples
  flux_samples: list[MocReflectedDomainGlobalMixedRegimeConservativeFluxSample] = []
  for index, (left, right) in enumerate(zip(samples, samples[1:])):
    dx = float(right.point_m[0] - left.point_m[0])
    dy = float(right.point_m[1] - left.point_m[1])
    length = hypot(dx, dy)
    if not isfinite(length) or length <= 0.0:
      raise ValueError('trace contains a non-positive segment length')
    nx = -dy / length
    ny = dx / length
    conservative = tuple(
      0.5 * (float(left.conservative_state[channel])
             + float(right.conservative_state[channel]))
      for channel in range(4)
    )
    density, momentum_x, momentum_y, energy = conservative
    if density <= 0.0 or not isfinite(density):
      raise ValueError('trace segment has a non-positive averaged density')
    velocity_u = momentum_x / density
    velocity_v = momentum_y / density
    gamma = 0.5 * (float(left.gamma) + float(right.gamma))
    pressure = (gamma - 1.0) * (
      energy - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
    )
    if gamma <= 1.0 or not isfinite(gamma) or pressure <= 0.0:
      raise ValueError('trace segment has an invalid averaged thermodynamic state')
    normal_velocity = velocity_u * nx + velocity_v * ny
    flux_samples.append(
      MocReflectedDomainGlobalMixedRegimeConservativeFluxSample(
        segment_index=index,
        midpoint_m=(
          0.5 * (left.point_m[0] + right.point_m[0]),
          0.5 * (left.point_m[1] + right.point_m[1]),
        ),
        normal_m=(nx, ny),
        segment_length_m=length,
        mass_flux_kg_m2_s=density * normal_velocity,
        streamwise_momentum_flux_Pa=(
          density * velocity_u * normal_velocity + pressure * nx
        ),
        transverse_momentum_flux_Pa=(
          density * velocity_v * normal_velocity + pressure * ny
        ),
        energy_flux_W_m2=(energy + pressure) * normal_velocity,
      )
    )
  return tuple(flux_samples)


def consume_reflected_domain_global_mixed_regime_state(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> MocReflectedDomainGlobalMixedRegimeStateConsumerResult:
  """Consume and independently replay one exact full-state downstream trace.

  The function intentionally accepts a complete coupled result rather than a
  bare trace.  That forces the consumer to verify the global closure identity,
  the coupled request lineage, and the retained global physical field before
  reading any conservative state.  It does not alter either input.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.INVALID_INPUT,
      'downstream must be a MocReflectedDomainGlobalCoupledDownstreamResult',
      closure=closure,
    )
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.CLOSURE_LINEAGE_FAILURE,
      'mixed-regime state consumption requires a locally verified global '
      'physical closure',
      closure=closure,
      downstream=downstream,
      source_closure_fingerprint=fingerprint,
    )
  if not downstream.closure_lineage_verified or downstream.source_closure_fingerprint != fingerprint:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.CLOSURE_LINEAGE_FAILURE,
      'downstream result does not retain the exact global closure lineage',
      closure=closure,
      downstream=downstream,
      source_closure_fingerprint=fingerprint,
    )
  ####
  global_euler = closure.global_euler
  physical_field = None if global_euler is None else global_euler.physical_field
  exact_field = None if physical_field is None else physical_field.field
  if (
    exact_field is None
    or not physical_field.converged
    or not physical_field.physical_closure_verified
    or not physical_field.state_sampling_available
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.CLOSURE_LINEAGE_FAILURE,
      'exact global physical-field state sampling is not ready for consumption',
      closure=closure,
      downstream=downstream,
      source_closure_fingerprint=fingerprint,
    )
  try:
    global_cell_samples = exact_field.cell_state_samples()
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.STATE_AUDIT_FAILURE,
      f'exact global physical-field state sampling failed: {error}',
      closure=closure,
      downstream=downstream,
      source_closure_fingerprint=fingerprint,
      global_field_consumed=False,
    )
  global_field_consumed = bool(
    len(global_cell_samples) == len(exact_field.cells)
    and len(global_cell_samples) > 0
  )
  if not global_field_consumed:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.STATE_AUDIT_FAILURE,
      'exact global physical field did not expose complete retained cell state '
      'coverage; no downstream state was consumed',
      closure=closure,
      downstream=downstream,
      source_closure_fingerprint=fingerprint,
    )
  ####
  trace = downstream.downstream_boundary_trace
  if trace is None or not trace.local_trace_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.TRACE_NOT_READY,
      'mixed-regime state consumption requires a locally verified full-state '
      'downstream trace',
      closure=closure,
      downstream=downstream,
      source_closure_fingerprint=fingerprint,
      global_field_consumed=True,
    )
  if trace.source_closure_fingerprint != fingerprint:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.CLOSURE_LINEAGE_FAILURE,
      'downstream trace does not retain the exact global closure fingerprint',
      closure=closure,
      downstream=downstream,
      trace=trace,
      source_closure_fingerprint=fingerprint,
      global_field_consumed=True,
    )
  ####
  try:
    replayed_trace = build_reflected_domain_global_coupled_downstream_boundary_trace(
      downstream
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.TRACE_REPLAY_FAILURE,
      f'full-state downstream trace replay failed: {error}',
      closure=closure,
      downstream=downstream,
      trace=trace,
      source_closure_fingerprint=fingerprint,
      global_field_consumed=True,
    )
  if replayed_trace != trace or not replayed_trace.local_trace_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.TRACE_REPLAY_FAILURE,
      'retained downstream trace did not exactly match a fresh replay from '
      'the coupled conservative field',
      closure=closure,
      downstream=downstream,
      trace=trace,
      source_closure_fingerprint=fingerprint,
      closure_lineage_verified=True,
      global_field_consumed=True,
    )
  ####
  if trace.sample_count < 2:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.STATE_AUDIT_FAILURE,
      'full-state downstream trace requires at least two ordered samples',
      closure=closure,
      downstream=downstream,
      trace=trace,
      source_closure_fingerprint=fingerprint,
      closure_lineage_verified=True,
      global_field_consumed=True,
    )
  ####
  try:
    flux_samples = _build_flux_samples(trace)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.STATE_AUDIT_FAILURE,
      f'full-state conservative flux audit failed: {error}',
      closure=closure,
      downstream=downstream,
      trace=trace,
      source_closure_fingerprint=fingerprint,
      closure_lineage_verified=True,
      global_field_consumed=True,
    )
  ####
  entropy_values = tuple(float(sample.entropy_proxy) for sample in trace.samples)
  entropy_verified = bool(
    entropy_values and all(isfinite(value) and value > 0.0 for value in entropy_values)
  )
  frame_verified = bool(
    all(
      second.point_m[0] > first.point_m[0]
      for first, second in zip(trace.samples, trace.samples[1:])
    )
    and downstream.coupled_field is not None
    and tuple(sample.point_m for sample in trace.samples)
    == tuple(downstream.coupled_field.free_boundary_points_m)
  )
  full_state_verified = bool(
    len(trace.samples) == len(downstream.coupled_field.free_boundary_points_m)
    if downstream.coupled_field is not None
    else False
  )
  mass_verified = bool(flux_samples and all(isfinite(sample.mass_flux_kg_m2_s) for sample in flux_samples))
  streamwise_verified = bool(
    flux_samples
    and all(isfinite(sample.streamwise_momentum_flux_Pa) for sample in flux_samples)
  )
  transverse_verified = bool(
    flux_samples
    and all(isfinite(sample.transverse_momentum_flux_Pa) for sample in flux_samples)
  )
  energy_verified = bool(flux_samples and all(isfinite(sample.energy_flux_W_m2) for sample in flux_samples))
  ambient_verified = bool(
    trace.boundary_condition_verified
    and all(
      value <= trace.pressure_tolerance_fraction
      for value in trace.pressure_residual_fractions
    )
  )
  centerline_verified = bool(
    trace.centerline_condition_verified
    and len(trace.centerline_normal_velocity_residuals_m_s) == trace.sample_count - 1
  )
  consumed = bool(
    frame_verified
    and full_state_verified
    and mass_verified
    and streamwise_verified
    and transverse_verified
    and energy_verified
    and entropy_verified
    and ambient_verified
    and centerline_verified
  )
  status = (
    MocReflectedDomainGlobalMixedRegimeStateConsumerStatus
    .CONSUMED_LOCAL_RESEARCH_STATE
    if consumed
    else MocReflectedDomainGlobalMixedRegimeStateConsumerStatus.STATE_AUDIT_FAILURE
  )
  return MocReflectedDomainGlobalMixedRegimeStateConsumerResult(
    status=status,
    closure=closure,
    downstream=downstream,
    trace=trace,
    conservative_flux_samples=flux_samples,
    entropy_proxy_range=(min(entropy_values), max(entropy_values))
    if entropy_values
    else None,
    source_closure_fingerprint=fingerprint,
    closure_lineage_verified=True,
    global_field_consumed=True,
    full_state_trace_consumed=full_state_verified,
    frame_coverage_verified=frame_verified,
    mass_channel_verified=mass_verified,
    streamwise_momentum_channel_verified=streamwise_verified,
    transverse_momentum_channel_verified=transverse_verified,
    energy_channel_verified=energy_verified,
    entropy_channel_verified=entropy_verified,
    ambient_channel_verified=ambient_verified,
    centerline_channel_verified=centerline_verified,
    message=(
      'full conservative downstream trace was replayed and consumed as a '
      'research state record; upstream global feedback, canonical mixed-regime '
      'closure, refinement, external validation, and production promotion '
      'remain open'
    )
    if consumed
    else (
      'full conservative downstream trace replayed, but one or more state '
      'channels failed their independent consumer audit'
    ),
  )


def build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame(
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
) -> tuple[
  tuple[tuple[float, float, float, float], ...],
  tuple[tuple[float, float], ...],
]:
  """Build exact conservative targets and their retained 2-D trace frame.

  Each target is a conservative average on one retained trace segment, and
  each point is that segment's geometric midpoint.  The frame is intentionally
  not interpolated or projected onto a new grid.  The downstream Rusanov
  request still consumes the x projection through the compatibility helper
  below, while the full 2-D frame remains available for the future upstream
  state equation.
  """

  if not isinstance(
    consumer,
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  ):
    raise TypeError(
      'consumer must be a '
      'MocReflectedDomainGlobalMixedRegimeStateConsumerResult'
    )
  if not consumer.consumed_local_research_state or consumer.trace is None:
    raise ValueError(
      'conservative boundary profile requires a locally consumed full-state '
      'trace'
    )
  ####
  trace = consumer.trace
  states: list[tuple[float, float, float, float]] = []
  points: list[tuple[float, float]] = []
  for left, right in zip(trace.samples, trace.samples[1:]):
    states.append(
      tuple(
        0.5 * (float(left.conservative_state[index])
               + float(right.conservative_state[index]))
        for index in range(4)
      )
    )
    points.append(
      (
        0.5 * (left.point_m[0] + right.point_m[0]),
        0.5 * (left.point_m[1] + right.point_m[1]),
      )
    )
  ####
  if not states or len(states) != trace.sample_count - 1:
    raise ValueError(
      'conservative boundary profile retained no complete trace segments'
    )
  return tuple(states), tuple(points)


def build_reflected_domain_global_mixed_regime_conservative_boundary_profile(
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
) -> tuple[
  tuple[tuple[float, float, float, float], ...],
  tuple[float, ...],
]:
  """Build the exact x-projected profile required by the downstream solver.

  This compatibility view deliberately preserves the existing downstream
  request contract.  Call
  ``build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame``
  when the full physical trace frame is required.
  """

  profile, points = (
    build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame(
      consumer
    )
  )
  return profile, tuple(point[0] for point in points)


class MocReflectedDomainGlobalMixedRegimeStateResolveStatus(str, Enum):
  """Typed outcomes of a fresh downstream solve consuming the full trace."""

  CONVERGED_LOCAL_RESEARCH_STATE_RESOLVE = (
    'converged-local-global-mixed-regime-state-resolve'
  )
  INVALID_INPUT = 'invalid_input'
  CONSUMER_NOT_READY = 'global-mixed-regime-state-resolve-consumer-not-ready'
  REQUEST_FAILURE = 'global-mixed-regime-state-resolve-request-failure'
  FRESH_SOLVER_FAILURE = 'global-mixed-regime-state-resolve-solver-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'global-mixed-regime-state-resolve-independent-audit-failure'
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeStateResolveResult:
  """Research evidence from one fresh full-state downstream re-solve."""

  status: MocReflectedDomainGlobalMixedRegimeStateResolveStatus
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult | None
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None = None
  field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None
  field_audit: Any | None = None
  conservative_state_profile: (
    tuple[tuple[float, float, float, float], ...]
  ) = ()
  conservative_state_profile_x_stations_m: tuple[float, ...] = ()
  conservative_state_profile_points_m: tuple[tuple[float, float], ...] = ()
  consumer_lineage_verified: bool = False
  profile_frame_verified: bool = False
  fresh_solver_invoked: bool = False
  fresh_field_lineage_verified: bool = False
  independent_audit_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeStateResolveStatus,
    ):
      raise TypeError('status must be a typed state-resolve status')
    if self.consumer is not None and not isinstance(
      self.consumer,
      MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
    ):
      raise TypeError('consumer must be typed or None')
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    ):
      raise TypeError('request must be typed or None')
    if self.field is not None and not isinstance(
      self.field,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError('field must be typed or None')
    profile = tuple(
      tuple(float(value) for value in state)
      for state in self.conservative_state_profile
    )
    if any(
      len(state) != 4 or any(not isfinite(value) for value in state)
      for state in profile
    ):
      raise ValueError('conservative_state_profile must contain finite four-tuples')
    stations = tuple(float(value) for value in self.conservative_state_profile_x_stations_m)
    if any(not isfinite(value) for value in stations):
      raise ValueError('conservative_state_profile_x_stations_m must be finite')
    points = tuple(
      tuple(float(value) for value in point)
      for point in self.conservative_state_profile_points_m
    )
    if any(
      len(point) != 2 or any(not isfinite(value) for value in point)
      for point in points
    ):
      raise ValueError(
        'conservative_state_profile_points_m must contain finite 2-D points'
      )
    if len(profile) != len(stations) or len(profile) != len(points):
      raise ValueError(
        'conservative state profile, x stations, and 2-D points must align'
      )
    if any(second <= first for first, second in zip(stations, stations[1:])):
      raise ValueError('conservative state profile stations must be ordered')
    if any(
      second[0] <= first[0]
      for first, second in zip(points, points[1:])
    ):
      raise ValueError(
        'conservative state profile 2-D points must be ordered in x'
      )
    object.__setattr__(self, 'conservative_state_profile', profile)
    object.__setattr__(self, 'conservative_state_profile_x_stations_m', stations)
    object.__setattr__(self, 'conservative_state_profile_points_m', points)
    for name in (
      'consumer_lineage_verified',
      'profile_frame_verified',
      'fresh_solver_invoked',
      'fresh_field_lineage_verified',
      'independent_audit_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('state resolve cannot claim canonical global coupling')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('state resolve must remain promotion-blocked')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def fresh_local_research_state_resolve_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeStateResolveStatus
      .CONVERGED_LOCAL_RESEARCH_STATE_RESOLVE
      and self.consumer_lineage_verified
      and self.profile_frame_verified
      and self.fresh_solver_invoked
      and self.fresh_field_lineage_verified
      and self.independent_audit_verified
      and self.field is not None
      and self.field.converged
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'model': 'research-global-mixed-regime-state-resolve-v1',
      'status': self.status.value,
      'fresh_local_research_state_resolve_verified': (
        self.fresh_local_research_state_resolve_verified
      ),
      'consumer_lineage_verified': self.consumer_lineage_verified,
      'profile_frame_verified': self.profile_frame_verified,
      'fresh_solver_invoked': self.fresh_solver_invoked,
      'fresh_field_lineage_verified': self.fresh_field_lineage_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'conservative_state_profile': self.conservative_state_profile,
      'conservative_state_profile_x_stations_m': (
        self.conservative_state_profile_x_stations_m
      ),
      'conservative_state_profile_points_m': (
        self.conservative_state_profile_points_m
      ),
      'request': None if self.request is None else self.request.as_report(),
      'field': None if self.field is None else self.field.as_report(),
      'field_audit': (
        None
        if self.field_audit is None
        else self.field_audit.as_report()
      ),
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'message': self.message,
    }


def solve_reflected_domain_global_mixed_regime_state_consumer(
  consumer: MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
) -> MocReflectedDomainGlobalMixedRegimeStateResolveResult:
  """Fresh-solve the coupled field with the consumed full-state trace.

  This is the first numerical consumer of the full downstream state packet.
  It binds adjacent trace-state averages to the exact existing coupled
  cell-center frame and uses the explicit conservative Rusanov boundary flux.
  It does not change the upstream global closure, so it cannot claim a global
  fixed point or production validity.
  """

  if not isinstance(
    consumer,
    MocReflectedDomainGlobalMixedRegimeStateConsumerResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
      status=MocReflectedDomainGlobalMixedRegimeStateResolveStatus.INVALID_INPUT,
      consumer=None,
      message=(
        'consumer must be a '
        'MocReflectedDomainGlobalMixedRegimeStateConsumerResult'
      ),
    )
  if not consumer.consumed_local_research_state:
    return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
      status=MocReflectedDomainGlobalMixedRegimeStateResolveStatus.CONSUMER_NOT_READY,
      consumer=consumer,
      consumer_lineage_verified=consumer.closure_lineage_verified,
      message=(
        'fresh full-state solve requires a locally consumed conservative trace'
      ),
    )
  ####
  downstream = consumer.downstream
  baseline_request = None if downstream is None else downstream.coupled_request
  if baseline_request is None:
    return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
      status=MocReflectedDomainGlobalMixedRegimeStateResolveStatus.REQUEST_FAILURE,
      consumer=consumer,
      consumer_lineage_verified=True,
      message='consumed state retained no coupled-Euler request for re-solving',
    )
  ####
  try:
    profile, profile_points = (
      build_reflected_domain_global_mixed_regime_conservative_boundary_state_frame(
        consumer
      )
    )
    profile_x = tuple(point[0] for point in profile_points)
    request = replace(
      baseline_request,
      source=(f'{baseline_request.source}:global-mixed-regime-state-consumer-v1'),
      free_boundary_flux_mode=(
        MocReflectedDomainCoupledEulerFreeBoundaryFluxMode
        .CONSERVATIVE_STATE_TRACE_RUSANOV
      ),
      free_boundary_conservative_state_profile=profile,
      free_boundary_conservative_state_profile_x_stations_m=profile_x,
      free_boundary_conservative_state_profile_source=(
        'research-global-coupled-downstream-full-state-trace-v1'
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
      status=MocReflectedDomainGlobalMixedRegimeStateResolveStatus.REQUEST_FAILURE,
      consumer=consumer,
      consumer_lineage_verified=True,
      message=f'full-state coupled request construction failed: {error}',
    )
  ####
  try:
    field = solve_reflected_domain_coupled_euler_free_boundary(request)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
      status=MocReflectedDomainGlobalMixedRegimeStateResolveStatus.FRESH_SOLVER_FAILURE,
      consumer=consumer,
      request=request,
      conservative_state_profile=profile,
      conservative_state_profile_x_stations_m=profile_x,
      conservative_state_profile_points_m=profile_points,
      consumer_lineage_verified=True,
      profile_frame_verified=True,
      fresh_solver_invoked=True,
      message=f'full-state coupled solver raised: {error}',
    )
  ####
  try:
    from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
      measure_reflected_domain_coupled_euler_free_boundary,
    )

    field_audit = measure_reflected_domain_coupled_euler_free_boundary(field)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
      status=(
        MocReflectedDomainGlobalMixedRegimeStateResolveStatus
        .INDEPENDENT_AUDIT_FAILURE
      ),
      consumer=consumer,
      request=request,
      field=field,
      conservative_state_profile=profile,
      conservative_state_profile_x_stations_m=profile_x,
      conservative_state_profile_points_m=profile_points,
      consumer_lineage_verified=True,
      profile_frame_verified=True,
      fresh_solver_invoked=True,
      fresh_field_lineage_verified=field.request is request,
      message=f'full-state coupled independent audit raised: {error}',
    )
  ####
  field_lineage_verified = bool(
    field.request is request
    and request.free_boundary_flux_mode
    is MocReflectedDomainCoupledEulerFreeBoundaryFluxMode
    .CONSERVATIVE_STATE_TRACE_RUSANOV
    and field.free_boundary_conservative_state_profile_consumed
  )
  audit_verified = bool(
    getattr(field_audit, 'converged', False)
    and getattr(field_audit, 'local_consistency_verified', False)
  )
  local = bool(
    field.status
    is MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_CLOSURE
    and field.converged
    and field_lineage_verified
    and audit_verified
  )
  return MocReflectedDomainGlobalMixedRegimeStateResolveResult(
    status=(
      MocReflectedDomainGlobalMixedRegimeStateResolveStatus
      .CONVERGED_LOCAL_RESEARCH_STATE_RESOLVE
      if local
      else (
        MocReflectedDomainGlobalMixedRegimeStateResolveStatus
        .FRESH_SOLVER_FAILURE
        if not field.converged
        else MocReflectedDomainGlobalMixedRegimeStateResolveStatus
        .INDEPENDENT_AUDIT_FAILURE
      )
    ),
    consumer=consumer,
    request=request,
    field=field,
    field_audit=field_audit,
    conservative_state_profile=profile,
    conservative_state_profile_x_stations_m=profile_x,
    conservative_state_profile_points_m=profile_points,
    consumer_lineage_verified=True,
    profile_frame_verified=True,
    fresh_solver_invoked=True,
    fresh_field_lineage_verified=field_lineage_verified,
    independent_audit_verified=audit_verified,
    message=(
      'fresh coupled Euler solve consumed the full conservative downstream '
      'trace; canonical global feedback, free-boundary closure, refinement, '
      'external validation, and production promotion remain open'
    )
    if local
    else (
      'fresh coupled Euler solve consumed the full conservative downstream '
      f'trace but remained non-converged ({field.status.value}); no fallback '
      'boundary law was attempted'
      if not field.converged
      else (
        'fresh coupled Euler solve reported local closure, but its independent '
        f'audit failed ({getattr(field_audit, "status", "unknown")}); no '
        'fallback boundary law was attempted'
      )
    ),
  )
