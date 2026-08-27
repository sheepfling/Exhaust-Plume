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

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.caustic_shock import (
  MocCausticShockBridgeResult,
  MocCausticShockBridgeStatus,
  solve_caustic_shock_bridge,
)
from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
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
  'prepare_caustic_shock_remesh',
)


class MocCausticShockRemeshPreparationStatus(str, Enum):
  """Outcome of preparing the physical caustic-remesh solver boundary."""

  READY_FOR_COUPLED_REMESH = 'ready_for_coupled_caustic_shock_remesh'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'caustic_remesh_seed_failure'
  LOCAL_SHOCK_FAILURE = 'caustic_remesh_local_shock_failure'


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
