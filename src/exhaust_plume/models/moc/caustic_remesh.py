"""Contract for a shock-conditioned remesh at a planar-MOC caustic.

The source-strip caustic exposes two one-sided pre-shock states.  A local
Rankine--Hugoniot/invariant solve can turn one selected state into a candidate
downstream state, but it does not identify a shock curve or a downstream
characteristic mesh.  This module makes the next solver boundary explicit:
prepare a request containing the exact caustic evidence, then require a future
remesher to return the shock curve, carried upstream samples, and a closed
post-shock field before the chain can advance.

The preparation result is intentionally non-promotable.  It is useful to
planners and validation reports without allowing local compatibility evidence
to masquerade as a resolved shock-cell transition.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Callable, Sequence

from exhaust_plume.models.moc.caustic_shock import (
  MocCausticShockBridgeResult,
  MocCausticShockBridgeStatus,
  solve_caustic_shock_bridge,
)
from exhaust_plume.models.moc.caustic_bridge import (
  MocCausticBridgeResult,
  MocCausticBridgeStatus,
  MocCausticUpstreamBridge,
  sample_caustic_upstream_bridge,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_with_invariant_boundary,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockCharacteristicFieldResult,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.source_strip import (
  MocSourceStripCausticShockSeedResult,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocCausticShockRemeshPreparationStatus',
  'MocCausticShockRemeshRequest',
  'MocCausticShockRemeshPreparationResult',
  'MocCausticShockRemeshStatus',
  'MocCausticShockRemeshResult',
  'prepare_caustic_shock_remesh',
  'solve_caustic_shock_remesh',
  'solve_caustic_shock_remesh_from_upstream_bridge',
)


class MocCausticShockRemeshPreparationStatus(str, Enum):
  """Outcome of preparing the physical caustic-remesh solver boundary."""

  READY_FOR_COUPLED_REMESH = 'ready_for_coupled_caustic_shock_remesh'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'caustic_remesh_seed_failure'
  LOCAL_SHOCK_FAILURE = 'caustic_remesh_local_shock_failure'


class MocCausticShockRemeshStatus(str, Enum):
  """Outcome of executing the coupled caustic remesh boundary."""

  CONVERGED_COUPLED_REMESH = 'converged_coupled_caustic_shock_remesh'
  INVALID_INPUT = 'invalid_input'
  EVENT_SEAM_FAILURE = 'caustic_remesh_event_seam_failure'
  UPSTREAM_FIELD_FAILURE = 'caustic_remesh_upstream_field_failure'
  INVARIANT_BOUNDARY_FAILURE = 'caustic_remesh_invariant_boundary_failure'
  SHOCK_CURVE_FAILURE = 'caustic_remesh_shock_curve_failure'
  DOWNSTREAM_FIELD_FAILURE = 'caustic_remesh_downstream_field_failure'
  REMESH_SEAM_FAILURE = 'caustic_remesh_new_family_seam_failure'


_DEFAULT_REQUIRED_OUTPUTS = (
  'shock_boundary_points_m',
  'shock_boundary_upstream_states',
  'shock_boundary_downstream_states',
  'shock_boundary_total_pressure_loss',
  'post_shock_characteristic_field',
  'exact_incoming_handoff',
)


@dataclass(frozen=True, slots=True)
class MocCausticShockRemeshRequest:
  """Exact local evidence a coupled caustic remesher must consume.

  ``local_bridge`` is only a compatibility seed.  The required output list
  is deliberately part of the request so a future solver cannot return a
  local shock state and silently call it a completed remesh.
  """

  seed: MocSourceStripCausticShockSeedResult
  local_bridge: MocCausticShockBridgeResult
  event_point_m: tuple[float, float]
  upstream_edge_index: int
  upstream_state: CharacteristicState
  upstream_static_pressure_Pa: float
  downstream_invariant_family: CharacteristicFamily
  downstream_invariant_target: float
  required_outputs: tuple[str, ...] = _DEFAULT_REQUIRED_OUTPUTS

  def __post_init__(self) -> None:
    if not isinstance(self.seed, MocSourceStripCausticShockSeedResult):
      raise TypeError('seed must be a MocSourceStripCausticShockSeedResult')
    if not isinstance(self.local_bridge, MocCausticShockBridgeResult):
      raise TypeError('local_bridge must be a MocCausticShockBridgeResult')
    if not self.seed.converged:
      raise ValueError('caustic remesh request requires a converged one-sided seed')
    if (
      not self.local_bridge.converged
      or not self.local_bridge.entropy_admissible
      or self.local_bridge.seed is not self.seed
    ):
      raise ValueError(
        'caustic remesh request requires the entropy-admissible bridge built '
        'from the exact seed'
      )
    event = self.seed.event
    if event is None or event.caustic_point_m is None:
      raise ValueError('caustic remesh request requires a bounded caustic point')
    if len(self.event_point_m) != 2 or not all(
      isfinite(float(value)) for value in self.event_point_m
    ):
      raise ValueError('event_point_m must contain two finite coordinates')
    if any(
      abs(float(first) - float(second)) > 1.0e-12
      for first, second in zip(self.event_point_m, event.caustic_point_m, strict=True)
    ):
      raise ValueError('event_point_m must match the seed caustic point exactly')
    if (
      isinstance(self.upstream_edge_index, bool)
      or not isinstance(self.upstream_edge_index, int)
      or self.upstream_edge_index not in (0, 1)
    ):
      raise ValueError('upstream_edge_index must be 0 or 1')
    if self.local_bridge.upstream_edge_index != self.upstream_edge_index:
      raise ValueError('local bridge upstream edge does not match the request')
    if not isinstance(self.upstream_state, CharacteristicState):
      raise TypeError('upstream_state must be a CharacteristicState')
    edge = self.seed.edge_states[self.upstream_edge_index]
    if edge.state is None or edge.static_pressure_Pa is None:
      raise ValueError('selected seed edge must carry a state and static pressure')
    if self.upstream_state != edge.state:
      raise ValueError('upstream_state must match the selected one-sided seed state')
    pressure = float(self.upstream_static_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('upstream_static_pressure_Pa must be finite and positive')
    if abs(pressure - float(edge.static_pressure_Pa)) > 1.0e-12 * max(
      1.0,
      abs(pressure),
      abs(float(edge.static_pressure_Pa)),
    ):
      raise ValueError(
        'upstream_static_pressure_Pa must match the selected one-sided seed state'
      )
    if not isinstance(self.downstream_invariant_family, CharacteristicFamily):
      raise TypeError(
        'downstream_invariant_family must be a CharacteristicFamily'
      )
    if self.local_bridge.downstream_invariant_family is not self.downstream_invariant_family:
      raise ValueError(
        'local bridge downstream invariant family does not match the request'
      )
    target = float(self.downstream_invariant_target)
    if not isfinite(target):
      raise ValueError('downstream_invariant_target must be finite')
    if self.local_bridge.downstream_invariant_target is None or abs(
      target - float(self.local_bridge.downstream_invariant_target)
    ) > 1.0e-12 * max(1.0, abs(target)):
      raise ValueError(
        'downstream_invariant_target must match the local bridge target'
      )
    outputs = tuple(self.required_outputs)
    if not outputs or any(not isinstance(value, str) or not value for value in outputs):
      raise ValueError('required_outputs must contain non-empty strings')
    if len(set(outputs)) != len(outputs):
      raise ValueError('required_outputs must not contain duplicates')
    object.__setattr__(self, 'event_point_m', tuple(float(value) for value in self.event_point_m))
    object.__setattr__(self, 'upstream_static_pressure_Pa', pressure)
    object.__setattr__(self, 'downstream_invariant_target', target)
    object.__setattr__(self, 'required_outputs', outputs)
  ####

  @property
  def local_shock_state_ready(self) -> bool:
    """Whether the selected one-sided state has a strict local shock bridge."""

    return self.local_bridge.entropy_admissible
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'event_point_m': self.event_point_m,
      'upstream_edge_index': self.upstream_edge_index,
      'upstream_state': {
        'x_m': self.upstream_state.x_m,
        'y_m': self.upstream_state.y_m,
        'theta_rad': self.upstream_state.theta_rad,
        'mach': self.upstream_state.mach,
        'gamma': self.upstream_state.gamma,
      },
      'upstream_static_pressure_Pa': self.upstream_static_pressure_Pa,
      'downstream_invariant_family': self.downstream_invariant_family.value,
      'downstream_invariant_target': self.downstream_invariant_target,
      'local_shock_state_ready': self.local_shock_state_ready,
      'required_outputs': list(self.required_outputs),
      'local_bridge_status': self.local_bridge.status.value,
      'shock_curve_verified': False,
      'downstream_field_verified': False,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocCausticShockRemeshPreparationResult:
  """Promotion-safe result for the caustic remesh handoff preparation."""

  status: MocCausticShockRemeshPreparationStatus
  seed: MocSourceStripCausticShockSeedResult | None
  local_bridge: MocCausticShockBridgeResult | None
  request: MocCausticShockRemeshRequest | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCausticShockRemeshPreparationStatus.READY_FOR_COUPLED_REMESH
  ####

  @property
  def local_shock_state_ready(self) -> bool:
    return bool(self.local_bridge is not None and self.local_bridge.entropy_admissible)
  ####

  @property
  def shock_curve_verified(self) -> bool:
    return False
  ####

  @property
  def downstream_field_verified(self) -> bool:
    return False
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit stop until a coupled remesher consumes the request."""

    if self.status is MocCausticShockRemeshPreparationStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    else:
      reason = MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    event_point = (
      None
      if self.seed is None or self.seed.event is None
      else self.seed.event.caustic_point_m
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'caustic shock remesh requires a coupled shock curve and '
        'downstream characteristic field'
      ),
      diagnostics={
        'termination_model': 'caustic-shock-remesh-contract',
        'remesh_request_ready': self.converged,
        'local_shock_state_ready': self.local_shock_state_ready,
        'shock_curve_verified': self.shock_curve_verified,
        'downstream_field_verified': self.downstream_field_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'caustic_point_m': event_point,
        'upstream_edge_index': (
          None if self.request is None else self.request.upstream_edge_index
        ),
        'downstream_invariant_family': (
          None
          if self.request is None
          else self.request.downstream_invariant_family.value
        ),
        'required_outputs': (
          [] if self.request is None else list(self.request.required_outputs)
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_shock_state_ready': self.local_shock_state_ready,
      'shock_curve_verified': self.shock_curve_verified,
      'downstream_field_verified': self.downstream_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'seed_status': None if self.seed is None else self.seed.status.value,
      'local_bridge': (
        None if self.local_bridge is None else self.local_bridge.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocCausticShockRemeshResult:
  """A bounded shock-curve/new-family remesh result.

  The local caustic bridge is consumed at the exact event point, then a
  solver-owned upstream field is used to march a new shock and assemble its
  downstream characteristic field.  This result deliberately stops one gate
  short of a physical chain cell: the old-family/new-family seam is audited,
  but ambient closure for the new cell is still a separate boundary solve.
  """

  status: MocCausticShockRemeshStatus
  request: MocCausticShockRemeshRequest | None
  shock: MocFreeBoundaryShockResult | None
  event_point_m: tuple[float, float] | None
  event_seam_verified: bool
  local_bridge_state_verified: bool
  upstream_coupling_verified: bool
  shock_curve_verified: bool
  downstream_field_verified: bool
  message: str = ''
  upstream_bridge_audit: MocCausticBridgeResult | None = None

  def __post_init__(self) -> None:
    if self.event_point_m is not None:
      if len(self.event_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.event_point_m
      ):
        raise ValueError('event_point_m must contain two finite coordinates')
      object.__setattr__(
        self,
        'event_point_m',
        (float(self.event_point_m[0]), float(self.event_point_m[1])),
      )
    for name in (
      'event_seam_verified',
      'local_bridge_state_verified',
      'upstream_coupling_verified',
      'shock_curve_verified',
      'downstream_field_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.upstream_bridge_audit is not None and not isinstance(
      self.upstream_bridge_audit,
      MocCausticBridgeResult,
    ):
      raise TypeError(
        'upstream_bridge_audit must be a MocCausticBridgeResult when supplied'
      )
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocCausticShockRemeshStatus.CONVERGED_COUPLED_REMESH
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Ambient/terminal closure is intentionally outside this remesh result."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def upstream_bridge_verified(self) -> bool:
    """Whether an explicit old/restarted-family bridge covered the path."""

    return bool(
      self.upstream_bridge_audit is not None
      and self.upstream_bridge_audit.converged
    )

  @property
  def bounded_downstream_field_available(self) -> bool:
    """Whether the remesh field is safe to use as a bounded solver input.

    This is deliberately weaker than a chain-cell promotion gate.  The
    remesh result still lacks the physical old-family/new-family closure
    required for production claims, but a completely coupled downstream
    characteristic field can be useful to a later research shock solve.
    """

    field = None if self.shock is None else self.shock.field
    return bool(
      self.converged
      and self.remesh_seam_verified
      and self.shock is not None
      and field is not None
      and field.converged
      and field.state_sampling_available
      and field.domain_x_extent_m is not None
      and field.domain_y_extent_m is not None
    )

  def as_bounded_downstream_field(self) -> MocPostShockCharacteristicFieldResult:
    """Expose the remesh field for an explicit research continuation.

    The returned field remains finite-domain and is not a promotion of this
    remesh result into a physical chain cell.  Callers that want to continue
    it must use the research-only field planner, which retains this result's
    unresolved closure diagnostics in its report.
    """

    if not self.bounded_downstream_field_available:
      raise ValueError(
        'a bounded downstream continuation field requires a converged caustic '
        'remesh with every event, upstream, shock, and field seam gate passed'
      )
    assert self.shock is not None
    assert self.shock.field is not None
    return self.shock.field

  @property
  def remesh_seam_verified(self) -> bool:
    """Whether every local event, shock, and field seam gate passed."""

    return bool(
      self.event_seam_verified
      and self.local_bridge_state_verified
      and self.upstream_coupling_verified
      and self.shock_curve_verified
      and self.downstream_field_verified
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Map the remesh gate to a non-physical, typed chain stop."""

    if self.status is MocCausticShockRemeshStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE,
    ):
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status in (
      MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE,
      MocCausticShockRemeshStatus.INVARIANT_BOUNDARY_FAILURE,
      MocCausticShockRemeshStatus.REMESH_SEAM_FAILURE,
    ):
      reason = MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    elif self.status is MocCausticShockRemeshStatus.DOWNSTREAM_FIELD_FAILURE:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    elif self.status is MocCausticShockRemeshStatus.SHOCK_CURVE_FAILURE:
      reason = MocChainTerminationReason.SOLVER_ERROR
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'caustic remesh did not produce a promotable physical chain cell'
      ),
      diagnostics={
        'termination_model': 'caustic-shock-remesh-fidelity-boundary',
        'remesh_status': self.status.value,
        'event_point_m': self.event_point_m,
        'event_seam_verified': self.event_seam_verified,
        'local_bridge_state_verified': self.local_bridge_state_verified,
        'upstream_coupling_verified': self.upstream_coupling_verified,
        'shock_curve_verified': self.shock_curve_verified,
        'downstream_field_verified': self.downstream_field_verified,
        'remesh_seam_verified': self.remesh_seam_verified,
        'upstream_bridge_verified': self.upstream_bridge_verified,
        'upstream_bridge_audit_status': (
          None
          if self.upstream_bridge_audit is None
          else self.upstream_bridge_audit.status.value
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'event_point_m': self.event_point_m,
      'event_seam_verified': self.event_seam_verified,
      'local_bridge_state_verified': self.local_bridge_state_verified,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'shock_curve_verified': self.shock_curve_verified,
      'downstream_field_verified': self.downstream_field_verified,
      'remesh_seam_verified': self.remesh_seam_verified,
      'bounded_downstream_field_available': self.bounded_downstream_field_available,
      'downstream_field_state_sampling_available': (
        False
        if self.shock is None or self.shock.field is None
        else self.shock.field.state_sampling_available
      ),
      'downstream_field_domain_x_extent_m': (
        None
        if self.shock is None or self.shock.field is None
        else self.shock.field.domain_x_extent_m
      ),
      'downstream_field_domain_y_extent_m': (
        None
        if self.shock is None or self.shock.field is None
        else self.shock.field.domain_y_extent_m
      ),
      'upstream_bridge_verified': self.upstream_bridge_verified,
      'upstream_bridge_audit': (
        None
        if self.upstream_bridge_audit is None
        else self.upstream_bridge_audit.as_report()
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'shock': None if self.shock is None else self.shock.as_report(),
      'request': None if self.request is None else self.request.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####


def _state_matches(
  actual: CharacteristicState,
  expected: CharacteristicState,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
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


def _pressure_matches(
  actual: float,
  expected: float,
  *,
  pressure_tolerance: float,
) -> bool:
  return abs(float(actual) - float(expected)) <= pressure_tolerance * max(
    1.0,
    abs(float(actual)),
    abs(float(expected)),
  )


def _caustic_bridge_audit_for_shock(
  bridge: MocCausticUpstreamBridge,
  shock: MocFreeBoundaryShockResult,
  *,
  position_tolerance_m: float,
) -> MocCausticBridgeResult:
  """Audit the retained shock path against the two-sided upstream bridge."""

  audit = sample_caustic_upstream_bridge(
    bridge,
    shock.shock_points_m,
    position_tolerance_m=position_tolerance_m,
  )
  if (
    shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
    and audit.converged
  ):
    missing_index = shock.failed_sample_index
    if missing_index is None:
      missing_index = shock.sample_count
    return replace(
      audit,
      status=MocCausticBridgeStatus.DOMAIN_GAP,
      first_missing_sample_index=missing_index,
      first_missing_point_m=shock.failed_point_m,
      message=(
        'caustic remesh shock march stopped before the next candidate point '
        'could be sampled from the bounded old/restarted-family bridge; no '
        'extrapolation was used'
      ),
    )
  return audit


def _remesh_result(
  status: MocCausticShockRemeshStatus,
  *,
  request: MocCausticShockRemeshRequest | None = None,
  shock: MocFreeBoundaryShockResult | None = None,
  event_seam_verified: bool = False,
  local_bridge_state_verified: bool = False,
  upstream_coupling_verified: bool = False,
  shock_curve_verified: bool = False,
  downstream_field_verified: bool = False,
  upstream_bridge_audit: MocCausticBridgeResult | None = None,
  message: str,
) -> MocCausticShockRemeshResult:
  return MocCausticShockRemeshResult(
    status=status,
    request=request,
    shock=shock,
    event_point_m=None if request is None else request.event_point_m,
    event_seam_verified=event_seam_verified,
    local_bridge_state_verified=local_bridge_state_verified,
    upstream_coupling_verified=upstream_coupling_verified,
    shock_curve_verified=shock_curve_verified,
    downstream_field_verified=downstream_field_verified,
    message=message,
    upstream_bridge_audit=upstream_bridge_audit,
  )


def solve_caustic_shock_remesh(
  request: MocCausticShockRemeshRequest,
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  incoming_handoff: Sequence[MocChainBoundarySample],
  *,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
) -> MocCausticShockRemeshResult:
  """Execute the coupled shock-curve/new-family caustic remesh.

  The two callbacks are the only allowed source of upstream data.  The exact
  event sample is checked against the preparation request, every generated
  shock sample is checked against the callbacks, and the returned field must
  retain the incoming chain handoff.  A constant invariant target is used
  when no law is supplied; callers may provide a varying law, but its first
  value must reproduce the request's local bridge target.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      message='request must be a MocCausticShockRemeshRequest',
    )
  if not callable(upstream_state_at) or not callable(upstream_pressure_at):
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      request=request,
      message='upstream state and pressure providers must be callable',
    )
  if downstream_invariant_at is not None and not callable(downstream_invariant_at):
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      request=request,
      message='downstream_invariant_at must be callable when supplied',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      request=request,
      message='incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  if len(handoff) < 3 or any(
    not isinstance(sample, MocChainBoundarySample) for sample in handoff
  ):
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      request=request,
      message='caustic remesh requires at least three typed incoming handoff samples',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')

  event_point = request.event_point_m
  try:
    event_state = upstream_state_at(event_point)
    event_pressure = upstream_pressure_at(event_point)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _remesh_result(
      MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE,
      request=request,
      message=f'caustic remesh upstream event sample failed: {error}',
    )
  if not isinstance(event_state, CharacteristicState):
    return _remesh_result(
      MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE,
      request=request,
      message='caustic remesh upstream event provider returned no CharacteristicState',
    )
  if event_pressure is None or not isfinite(float(event_pressure)) or float(event_pressure) <= 0.0:
    return _remesh_result(
      MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE,
      request=request,
      message='caustic remesh upstream event provider returned invalid pressure',
    )
  event_state_verified = _state_matches(
    event_state,
    request.upstream_state,
    position_tolerance_m=float(position_tolerance_m),
    state_tolerance=float(invariant_tolerance),
  )
  event_pressure_verified = _pressure_matches(
    float(event_pressure),
    request.upstream_static_pressure_Pa,
    pressure_tolerance=float(pressure_tolerance),
  )
  if not event_state_verified or not event_pressure_verified:
    return _remesh_result(
      MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE,
      request=request,
      message=(
        'caustic remesh upstream event sample does not reproduce the exact '
        'one-sided request state and static pressure'
      ),
    )

  law_target_verified = True

  def invariant_at(index: int, point_m: tuple[float, float]) -> float:
    nonlocal law_target_verified
    if downstream_invariant_at is None:
      target = request.downstream_invariant_target
    else:
      target = downstream_invariant_at(index, point_m)
    try:
      target_value = float(target)
    except (TypeError, ValueError) as error:
      law_target_verified = False
      raise ValueError(f'downstream invariant law returned a nonnumeric value: {error}') from error
    if not isfinite(target_value):
      law_target_verified = False
      raise ValueError('downstream invariant law returned a non-finite value')
    if index == 0 and abs(target_value - request.downstream_invariant_target) > float(invariant_tolerance) * max(
      1.0,
      abs(target_value),
      abs(request.downstream_invariant_target),
    ):
      law_target_verified = False
      raise ValueError(
        'downstream invariant law does not reproduce the prepared local '
        'caustic bridge target at the remesh event'
      )
    return target_value

  try:
    shock = solve_marched_attached_shock_with_invariant_boundary(
      upstream_state_at,
      upstream_pressure_at,
      event_point,
      request.downstream_invariant_family,
      invariant_at,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _remesh_result(
      MocCausticShockRemeshStatus.SHOCK_CURVE_FAILURE,
      request=request,
      message=f'caustic remesh shock solve raised: {error}',
    )

  shock_curve_verified = bool(
    shock.converged
    and law_target_verified
    and shock.shock_fit is not None
    and shock.shock_fit.converged
    and len(shock.shock_points_m) >= 3
    and len(shock.shock_points_m) == len(shock.upstream_states)
    and len(shock.shock_points_m) == len(shock.upstream_pressure_Pa)
  )
  downstream_field_verified = bool(
    shock.field is not None and shock.field.converged
  )

  upstream_coupling_verified = False
  if shock_curve_verified:
    try:
      callback_samples = tuple(
        (upstream_state_at(point), upstream_pressure_at(point))
        for point in shock.shock_points_m
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      callback_samples = ()
    upstream_coupling_verified = len(callback_samples) == len(shock.shock_points_m) and all(
      isinstance(state, CharacteristicState)
      and pressure is not None
      and isfinite(float(pressure))
      and _state_matches(
        state,
        expected_state,
        position_tolerance_m=float(position_tolerance_m),
        state_tolerance=float(invariant_tolerance),
      )
      and _pressure_matches(
        float(pressure),
        expected_pressure,
        pressure_tolerance=float(pressure_tolerance),
      )
      for (state, pressure), expected_state, expected_pressure in zip(
        callback_samples,
        shock.upstream_states,
        shock.upstream_pressure_Pa,
        strict=True,
      )
    )
    if shock.field is not None:
      upstream_coupling_verified = upstream_coupling_verified and (
        shock.field.incoming_handoff_states == tuple(sample.state for sample in handoff)
        and shock.field.incoming_handoff_total_pressure_Pa == tuple(
          sample.total_pressure_Pa for sample in handoff
        )
      )

  local_bridge_state_verified = False
  if shock_curve_verified and shock.shock_fit is not None and shock.shock_fit.boundary_states:
    first_boundary = shock.shock_fit.boundary_states[0]
    bridge_state = request.local_bridge.downstream_state
    compression = request.local_bridge.compression
    compression_pressure = (
      None
      if compression is None
      else compression.downstream_total_pressure_Pa
    )
    local_bridge_state_verified = bool(
      bridge_state is not None
      and compression is not None
      and compression_pressure is not None
      and _state_matches(
        first_boundary.state,
        bridge_state,
        position_tolerance_m=float(position_tolerance_m),
        state_tolerance=float(invariant_tolerance),
      )
      and _state_matches(
        shock.upstream_states[0],
        request.upstream_state,
        position_tolerance_m=float(position_tolerance_m),
        state_tolerance=float(invariant_tolerance),
      )
      and _pressure_matches(
        shock.upstream_pressure_Pa[0],
        request.upstream_static_pressure_Pa,
        pressure_tolerance=float(pressure_tolerance),
      )
      and _pressure_matches(
        first_boundary.downstream_total_pressure_Pa,
        compression_pressure,
        pressure_tolerance=float(pressure_tolerance),
      )
    )
  remesh_seam_verified = bool(
    event_state_verified
    and event_pressure_verified
    and law_target_verified
    and local_bridge_state_verified
  )

  if not shock_curve_verified:
    status = (
      MocCausticShockRemeshStatus.INVARIANT_BOUNDARY_FAILURE
      if not law_target_verified or shock.status is MocFreeBoundaryShockStatus.INVARIANT_BOUNDARY_FAILURE
      else (
        MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE
        if shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
        else MocCausticShockRemeshStatus.SHOCK_CURVE_FAILURE
      )
    )
    message = f'caustic remesh did not generate a complete shock curve: {shock.message}'
  elif not upstream_coupling_verified:
    status = MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE
    message = 'caustic remesh shock path did not retain the exact bounded upstream field or incoming handoff'
  elif not downstream_field_verified:
    status = MocCausticShockRemeshStatus.DOWNSTREAM_FIELD_FAILURE
    message = 'caustic remesh shock curve converged, but its downstream characteristic field did not close'
  elif not remesh_seam_verified:
    status = MocCausticShockRemeshStatus.REMESH_SEAM_FAILURE
    message = 'caustic remesh did not reproduce the prepared local bridge at its event seam'
  else:
    status = MocCausticShockRemeshStatus.CONVERGED_COUPLED_REMESH
    message = (
      'caustic remesh generated a bounded attached shock and closed downstream '
      'characteristic field with exact event/upstream coupling; ambient physical '
      'closure remains a separate first-cell gate'
    )
  return _remesh_result(
    status,
    request=request,
    shock=shock,
    event_seam_verified=bool(event_state_verified and event_pressure_verified and law_target_verified),
    local_bridge_state_verified=local_bridge_state_verified,
    upstream_coupling_verified=upstream_coupling_verified,
    shock_curve_verified=shock_curve_verified,
    downstream_field_verified=downstream_field_verified,
    message=message,
  )
  ####


def solve_caustic_shock_remesh_from_upstream_bridge(
  request: MocCausticShockRemeshRequest,
  bridge: MocCausticUpstreamBridge,
  incoming_handoff: Sequence[MocChainBoundarySample],
  *,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float] | None = None,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
) -> MocCausticShockRemeshResult:
  """Run the caustic remesh against an explicit old/restarted-family bridge.

  This adapter is the strict upstream-coupled remesh boundary.  It samples
  the bridge at the exact prepared event and along the generated shock path;
  a gap, ambiguous overlap, or selected-side mismatch is retained as a typed
  upstream/event failure.  The bridge is never replaced by a last valid state
  or by a callback-owned extrapolation.
  """

  if not isinstance(request, MocCausticShockRemeshRequest):
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      message='request must be a MocCausticShockRemeshRequest',
    )
  if not isinstance(bridge, MocCausticUpstreamBridge):
    return _remesh_result(
      MocCausticShockRemeshStatus.INVALID_INPUT,
      request=request,
      message='bridge must be a MocCausticUpstreamBridge',
    )

  event_audit = sample_caustic_upstream_bridge(
    bridge,
    (request.event_point_m,),
    position_tolerance_m=position_tolerance_m,
  )
  if not event_audit.converged:
    status = (
      MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE
      if event_audit.status is MocCausticBridgeStatus.FIELD_INPUT_FAILURE
      else MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE
    )
    return _remesh_result(
      status,
      request=request,
      upstream_bridge_audit=event_audit,
      message=(
        'caustic remesh explicit upstream bridge did not cover the prepared '
        f'event: {event_audit.message}'
      ),
    )
  assert event_audit.samples
  event_sample = event_audit.samples[0]
  if not _state_matches(
    event_sample.state,
    request.upstream_state,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=invariant_tolerance,
  ) or not _pressure_matches(
    event_sample.static_pressure_Pa,
    request.upstream_static_pressure_Pa,
    pressure_tolerance=pressure_tolerance,
  ):
    return _remesh_result(
      MocCausticShockRemeshStatus.EVENT_SEAM_FAILURE,
      request=request,
      upstream_bridge_audit=event_audit,
      message=(
        'caustic remesh explicit upstream bridge event sample does not '
        'reproduce the prepared one-sided state and static pressure'
      ),
    )

  result = solve_caustic_shock_remesh(
    request,
    bridge.state_at,
    bridge.static_pressure_at,
    incoming_handoff,
    downstream_invariant_at=downstream_invariant_at,
    target_centerline_y_m=target_centerline_y_m,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    maximum_invariant_iterations=maximum_invariant_iterations,
  )
  if result.shock is None:
    return replace(result, upstream_bridge_audit=event_audit)
  path_audit = _caustic_bridge_audit_for_shock(
    bridge,
    result.shock,
    position_tolerance_m=position_tolerance_m,
  )
  if result.converged and not path_audit.converged:
    return replace(
      result,
      status=MocCausticShockRemeshStatus.UPSTREAM_FIELD_FAILURE,
      upstream_coupling_verified=False,
      upstream_bridge_audit=path_audit,
      message=(
        'caustic remesh generated a field, but the explicit old/restarted-'
        'family bridge did not cover the complete shock path'
      ),
    )
  return replace(result, upstream_bridge_audit=path_audit)
  ####


def _failure(
  status: MocCausticShockRemeshPreparationStatus,
  *,
  seed: MocSourceStripCausticShockSeedResult | None = None,
  local_bridge: MocCausticShockBridgeResult | None = None,
  message: str,
) -> MocCausticShockRemeshPreparationResult:
  return MocCausticShockRemeshPreparationResult(
    status=status,
    seed=seed,
    local_bridge=local_bridge,
    request=None,
    message=message,
  )


def prepare_caustic_shock_remesh(
  seed: MocSourceStripCausticShockSeedResult,
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_target: float,
  *,
  upstream_edge_index: int = 0,
  branch: ShockBranch = ShockBranch.WEAK,
  invariant_tolerance: float = 1.0e-10,
  maximum_turn_rad: float = 0.9,
  scan_samples: int = 64,
  maximum_iterations: int = 80,
) -> MocCausticShockRemeshPreparationResult:
  """Prepare an exact caustic shock/new-family remesh request.

  The function solves only the existing local invariant bridge.  A ready
  result means that a future coupled remesher has valid local input; it does
  not mean that the shock curve, characteristic field, or chain cell exists.
  """

  if not isinstance(seed, MocSourceStripCausticShockSeedResult):
    return _failure(
      MocCausticShockRemeshPreparationStatus.INVALID_INPUT,
      message='seed must be a MocSourceStripCausticShockSeedResult',
    )
  if not isinstance(downstream_invariant_family, CharacteristicFamily):
    return _failure(
      MocCausticShockRemeshPreparationStatus.INVALID_INPUT,
      seed=seed,
      message='downstream_invariant_family must be a CharacteristicFamily',
    )
  try:
    target = float(downstream_invariant_target)
  except (TypeError, ValueError):
    target = float('nan')
  if not isfinite(target):
    return _failure(
      MocCausticShockRemeshPreparationStatus.INVALID_INPUT,
      seed=seed,
      message='downstream_invariant_target must be finite',
    )
  if (
    isinstance(upstream_edge_index, bool)
    or not isinstance(upstream_edge_index, int)
    or upstream_edge_index not in (0, 1)
  ):
    return _failure(
      MocCausticShockRemeshPreparationStatus.INVALID_INPUT,
      seed=seed,
      message='upstream_edge_index must be 0 or 1',
    )
  if not seed.converged or len(seed.edge_states) != 2 or seed.event is None:
    return _failure(
      MocCausticShockRemeshPreparationStatus.SEED_FAILURE,
      seed=seed,
      message=f'caustic seed is not usable: {seed.message}',
    )
  edge = seed.edge_states[upstream_edge_index]
  if edge.state is None or edge.static_pressure_Pa is None:
    return _failure(
      MocCausticShockRemeshPreparationStatus.SEED_FAILURE,
      seed=seed,
      message='selected caustic edge lacks a state and static pressure',
    )
  try:
    bridge = solve_caustic_shock_bridge(
      seed,
      downstream_invariant_family,
      target,
      upstream_edge_index=upstream_edge_index,
      branch=branch,
      invariant_tolerance=invariant_tolerance,
      maximum_turn_rad=maximum_turn_rad,
      scan_samples=scan_samples,
      maximum_iterations=maximum_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticShockRemeshPreparationStatus.LOCAL_SHOCK_FAILURE,
      seed=seed,
      message=f'local caustic shock bridge raised: {error}',
    )
  if (
    bridge.status is not MocCausticShockBridgeStatus.CONVERGED_LOCAL_COMPATIBILITY
    or not bridge.entropy_admissible
  ):
    return _failure(
      MocCausticShockRemeshPreparationStatus.LOCAL_SHOCK_FAILURE,
      seed=seed,
      local_bridge=bridge,
      message=(
        'local caustic shock bridge did not produce an entropy-admissible '
        f'compatibility state: {bridge.message}'
      ),
    )
  event_point = seed.event.caustic_point_m
  if event_point is None:
    return _failure(
      MocCausticShockRemeshPreparationStatus.SEED_FAILURE,
      seed=seed,
      local_bridge=bridge,
      message='caustic event does not expose a bounded crossing point',
    )
  try:
    request = MocCausticShockRemeshRequest(
      seed=seed,
      local_bridge=bridge,
      event_point_m=event_point,
      upstream_edge_index=upstream_edge_index,
      upstream_state=edge.state,
      upstream_static_pressure_Pa=float(edge.static_pressure_Pa),
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_target=target,
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocCausticShockRemeshPreparationStatus.LOCAL_SHOCK_FAILURE,
      seed=seed,
      local_bridge=bridge,
      message=f'caustic remesh request failed validation: {error}',
    )
  return MocCausticShockRemeshPreparationResult(
    status=MocCausticShockRemeshPreparationStatus.READY_FOR_COUPLED_REMESH,
    seed=seed,
    local_bridge=bridge,
    request=request,
    message=(
      'local entropy-admissible caustic shock state is ready for a coupled '
      'shock-curve/new-family remesh; no curve or downstream field is solved'
    ),
  )
