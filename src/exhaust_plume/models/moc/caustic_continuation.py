"""Solver-owned upstream continuation at a planar-MOC caustic.

The reflected source strip ends when its next characteristic row develops a
caustic.  A one-sided family restart is a useful local remesh, but it is not
safe to let a caller silently choose one of the two crossing states or splice
the old and restarted fields together.  This module owns that orchestration
boundary: it validates the exact event, runs the selected one-sided restart,
and exposes a branch-explicit, bounded bridge for a later shock solver.

The returned bridge is still an upstream research field.  It does not solve a
shock curve, a downstream mixed-regime boundary, or a production chain cell.
Missing coverage and branch ambiguity remain typed outcomes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.caustic_bridge import (
  MocCausticBridgeSide,
  MocCausticUpstreamBridge,
  build_caustic_upstream_bridge,
)
from exhaust_plume.models.moc.caustic_restart import (
  MocCausticFamilyRestartResult,
  restart_characteristic_family_from_caustic,
)
from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  MocSourceStripCausticShockSeedResult,
)

__all__ = (
  'MocCausticUpstreamContinuationStatus',
  'MocCausticUpstreamContinuationResult',
  'solve_caustic_upstream_continuation',
)

Point = tuple[float, float]


class MocCausticUpstreamContinuationStatus(str, Enum):
  """Outcome of the bounded caustic upstream continuation controller."""

  CONVERGED_BOUNDED_CONTINUATION = (
    'converged_bounded_caustic_upstream_continuation'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FIELD_FAILURE = 'caustic_continuation_source_field_failure'
  SEED_FAILURE = 'caustic_continuation_seed_failure'
  BRANCH_SELECTION_REQUIRED = 'caustic_continuation_branch_selection_required'
  RESTART_FAILURE = 'caustic_continuation_restart_failure'
  SEAM_FAILURE = 'caustic_continuation_seam_failure'


@dataclass(frozen=True, slots=True)
class MocCausticUpstreamContinuationResult:
  """A branch-explicit, finite-domain continuation across a caustic.

  ``converged`` means that the old family, selected new family, exact event,
  and bounded bridge all passed their local checks.  It intentionally does not
  mean that the two fields are physically stitched or that the bridge can be
  promoted to a shock-cell upstream domain.
  """

  status: MocCausticUpstreamContinuationStatus
  old_family: MocSourceCharacteristicStripResult | None
  seed: MocSourceStripCausticShockSeedResult | None
  restart_results: tuple[MocCausticFamilyRestartResult, ...]
  selected_anchor_edge_index: int | None
  bridge: MocCausticUpstreamBridge | None
  seam_verified: bool
  message: str = ''
  side_selection_model: str = 'x-split-at-caustic-event'

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocCausticUpstreamContinuationStatus):
      raise TypeError('status must be a MocCausticUpstreamContinuationStatus')
    if self.old_family is not None and not isinstance(
      self.old_family,
      MocSourceCharacteristicStripResult,
    ):
      raise TypeError(
        'old_family must be a MocSourceCharacteristicStripResult when supplied'
      )
    if self.seed is not None and not isinstance(
      self.seed,
      MocSourceStripCausticShockSeedResult,
    ):
      raise TypeError(
        'seed must be a MocSourceStripCausticShockSeedResult when supplied'
      )
    if any(
      not isinstance(result, MocCausticFamilyRestartResult)
      for result in self.restart_results
    ):
      raise TypeError(
        'restart_results must contain MocCausticFamilyRestartResult values'
      )
    if self.selected_anchor_edge_index not in (None, 0, 1):
      raise ValueError('selected_anchor_edge_index must be None, 0, or 1')
    if self.bridge is not None and not isinstance(
      self.bridge,
      MocCausticUpstreamBridge,
    ):
      raise TypeError(
        'bridge must be a MocCausticUpstreamBridge when supplied'
      )
    if not isinstance(self.seam_verified, bool):
      raise TypeError('seam_verified must be a bool')

  @property
  def converged(self) -> bool:
    return self.status is (
      MocCausticUpstreamContinuationStatus.CONVERGED_BOUNDED_CONTINUATION
    )

  @property
  def physical_closure_verified(self) -> bool:
    """The upstream continuation has no shock or downstream closure."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def selected_restart(self) -> MocCausticFamilyRestartResult | None:
    """Return the restart selected for the current bounded bridge."""

    if self.selected_anchor_edge_index is None:
      return None
    return next(
      (
        result
        for result in self.restart_results
        if result.anchor_edge_index == self.selected_anchor_edge_index
      ),
      None,
    )

  @property
  def state_sampling_available(self) -> bool:
    """Whether the selected old/new bridge can be sampled in bounded cells."""

    selected = self.selected_restart
    return bool(
      self.converged
      and self.seam_verified
      and self.old_family is not None
      and self.old_family.converged
      and self.bridge is not None
      and self.bridge.fields_converged
      and selected is not None
      and selected.family_band is not None
      and selected.family_band.state_sampling_available
    )

  @property
  def event_point_m(self) -> Point | None:
    if self.seed is None or self.seed.event is None:
      return None
    return self.seed.event.caustic_point_m

  def state_at(
    self,
    point_m: Point,
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Sample the selected bounded bridge, without extrapolation."""

    if self.bridge is None:
      return None
    return self.bridge.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )

  def static_pressure_at(
    self,
    point_m: Point,
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Sample the selected bounded bridge pressure, without extrapolation."""

    if self.bridge is None:
      return None
    return self.bridge.static_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit non-physical stop at the unresolved caustic seam."""

    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocCausticUpstreamContinuationStatus.INVALID_INPUT
      else MocChainTerminationReason.CHARACTERISTIC_CAUSTIC
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'caustic upstream continuation did not produce a promotable '
        'physical chain boundary'
      ),
      diagnostics={
        'termination_model': 'caustic-upstream-continuation-boundary',
        'continuation_status': self.status.value,
        'event_point_m': self.event_point_m,
        'selected_anchor_edge_index': self.selected_anchor_edge_index,
        'restart_count': len(self.restart_results),
        'restart_statuses': [
          result.status.value for result in self.restart_results
        ],
        'seam_verified': self.seam_verified,
        'state_sampling_available': self.state_sampling_available,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'seam_verified': self.seam_verified,
      'state_sampling_available': self.state_sampling_available,
      'event_point_m': self.event_point_m,
      'selected_anchor_edge_index': self.selected_anchor_edge_index,
      'side_selection_model': self.side_selection_model,
      'old_family': (
        None
        if self.old_family is None
        else self.old_family.as_report()
      ),
      'seed': None if self.seed is None else self.seed.as_report(),
      'restart_count': len(self.restart_results),
      'restart_results': [
        result.as_report() for result in self.restart_results
      ],
      'bridge': None if self.bridge is None else self.bridge.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _failure(
  status: MocCausticUpstreamContinuationStatus,
  *,
  old_family: MocSourceCharacteristicStripResult | None = None,
  seed: MocSourceStripCausticShockSeedResult | None = None,
  restart_results: tuple[MocCausticFamilyRestartResult, ...] = (),
  selected_anchor_edge_index: int | None = None,
  bridge: MocCausticUpstreamBridge | None = None,
  seam_verified: bool = False,
  message: str,
  side_selection_model: str = 'x-split-at-caustic-event',
) -> MocCausticUpstreamContinuationResult:
  return MocCausticUpstreamContinuationResult(
    status=status,
    old_family=old_family,
    seed=seed,
    restart_results=restart_results,
    selected_anchor_edge_index=selected_anchor_edge_index,
    bridge=bridge,
    seam_verified=seam_verified,
    message=message,
    side_selection_model=side_selection_model,
  )


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


def solve_caustic_upstream_continuation(
  old_family: MocSourceCharacteristicStripResult,
  seed: MocSourceStripCausticShockSeedResult,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  *,
  anchor_edge_index: int | None = None,
  sample_count: int = 6,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
  side_at: Callable[[Point], MocCausticBridgeSide] | None = None,
) -> MocCausticUpstreamContinuationResult:
  """Continue a converged source strip through a detected caustic.

  ``anchor_edge_index`` is intentionally optional only to support an audit of
  both one-sided candidates.  When it is omitted, both restarts are solved
  but the result remains ``BRANCH_SELECTION_REQUIRED`` and exposes no bridge.
  A selected branch receives a deterministic x-split bridge: the old family
  is authoritative before the event and the restarted family at/after it.
  Callers may provide a stricter explicit selector, but it must still cover
  the exact event with the selected restart state.
  """

  if not isinstance(old_family, MocSourceCharacteristicStripResult):
    return _failure(
      MocCausticUpstreamContinuationStatus.INVALID_INPUT,
      message='old_family must be a MocSourceCharacteristicStripResult',
    )
  if not isinstance(seed, MocSourceStripCausticShockSeedResult):
    return _failure(
      MocCausticUpstreamContinuationStatus.INVALID_INPUT,
      old_family=old_family,
      message='seed must be a MocSourceStripCausticShockSeedResult',
    )
  if (
    isinstance(anchor_edge_index, bool)
    or anchor_edge_index not in (None, 0, 1)
  ):
    return _failure(
      MocCausticUpstreamContinuationStatus.INVALID_INPUT,
      old_family=old_family,
      seed=seed,
      message='anchor_edge_index must be None, 0, or 1',
    )
  if side_at is not None and not callable(side_at):
    return _failure(
      MocCausticUpstreamContinuationStatus.INVALID_INPUT,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message='side_at must be callable when supplied',
      side_selection_model='caller-supplied-explicit-side-selector',
    )
  try:
    total_pressure = float(total_pressure_Pa)
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    return _failure(
      MocCausticUpstreamContinuationStatus.INVALID_INPUT,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message='pressures must be finite numeric values',
    )
  if (
    not isfinite(total_pressure)
    or total_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or total_pressure <= ambient_pressure
  ):
    return _failure(
      MocCausticUpstreamContinuationStatus.INVALID_INPUT,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message='total pressure must exceed finite positive ambient pressure',
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
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  if not old_family.converged:
    return _failure(
      MocCausticUpstreamContinuationStatus.SOURCE_FIELD_FAILURE,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message=f'old source family is not converged: {old_family.message}',
    )
  if (
    not seed.converged
    or seed.event is None
    or not seed.event.detected
    or seed.event.caustic_point_m is None
    or len(seed.edge_states) != 2
  ):
    return _failure(
      MocCausticUpstreamContinuationStatus.SEED_FAILURE,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message=f'caustic seed is not usable: {seed.message}',
    )
  if seed.total_pressure_Pa is None or not isfinite(float(seed.total_pressure_Pa)):
    return _failure(
      MocCausticUpstreamContinuationStatus.SEED_FAILURE,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message='caustic seed lacks a finite total-pressure lineage',
    )
  if not _pressure_matches(
    total_pressure,
    float(seed.total_pressure_Pa),
    pressure_tolerance=pressure_tolerance,
  ) or not _pressure_matches(
    total_pressure,
    old_family.total_pressure_Pa,
    pressure_tolerance=pressure_tolerance,
  ):
    return _failure(
      MocCausticUpstreamContinuationStatus.SEAM_FAILURE,
      old_family=old_family,
      seed=seed,
      selected_anchor_edge_index=anchor_edge_index,
      message=(
        'old source family, caustic seed, and continuation total pressures '
        'do not share one exact lineage'
      ),
    )

  indices = (
    (anchor_edge_index,)
    if anchor_edge_index is not None
    else (0, 1)
  )
  restarts: list[MocCausticFamilyRestartResult] = []
  for edge_index in indices:
    try:
      restart = restart_characteristic_family_from_caustic(
        seed,
        total_pressure,
        ambient_pressure,
        anchor_edge_index=edge_index,
        sample_count=sample_count,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
        maximum_iterations=maximum_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocCausticUpstreamContinuationStatus.RESTART_FAILURE,
        old_family=old_family,
        seed=seed,
        restart_results=tuple(restarts),
        selected_anchor_edge_index=anchor_edge_index,
        message=f'caustic family restart raised at edge {edge_index}: {error}',
      )
    restarts.append(restart)

  if anchor_edge_index is None:
    if not all(
      result.converged
      and result.caustic_handoff_verified
      and result.family_band is not None
      and result.family_band.converged
      for result in restarts
    ):
      return _failure(
        MocCausticUpstreamContinuationStatus.RESTART_FAILURE,
        old_family=old_family,
        seed=seed,
        restart_results=tuple(restarts),
        message=(
          'one or more one-sided caustic restarts failed; branch selection '
          'cannot be audited from an incomplete candidate set'
        ),
      )
    return _failure(
      MocCausticUpstreamContinuationStatus.BRANCH_SELECTION_REQUIRED,
      old_family=old_family,
      seed=seed,
      restart_results=tuple(restarts),
      message=(
        'both one-sided caustic restarts converged, but no physical branch '
        'selector was supplied; no upstream bridge was assembled'
      ),
    )

  restart = restarts[0]
  band = restart.family_band
  if not (
    restart.converged
    and restart.caustic_handoff_verified
    and band is not None
    and band.converged
    and band.caustic_handoff_verified
  ):
    return _failure(
      MocCausticUpstreamContinuationStatus.RESTART_FAILURE,
      old_family=old_family,
      seed=seed,
      restart_results=tuple(restarts),
      selected_anchor_edge_index=anchor_edge_index,
      message=(
        'selected one-sided caustic restart did not produce a converged '
        f'bounded family band: {restart.message}'
      ),
    )
  event_point = seed.event.caustic_point_m
  assert event_point is not None
  selected_edge = seed.edge_states[anchor_edge_index]
  if selected_edge.state is None or selected_edge.static_pressure_Pa is None:
    return _failure(
      MocCausticUpstreamContinuationStatus.SEED_FAILURE,
      old_family=old_family,
      seed=seed,
      restart_results=tuple(restarts),
      selected_anchor_edge_index=anchor_edge_index,
      message='selected caustic edge has no state/pressure for the bridge seam',
    )
  if side_at is None:
    event_x = float(event_point[0])

    def selector(point: Point) -> MocCausticBridgeSide:
      return (
        MocCausticBridgeSide.OLD_FAMILY
        if point[0] < event_x - float(position_tolerance_m)
        else MocCausticBridgeSide.RESTARTED_FAMILY
      )

    side_selection_model = 'x-split-at-caustic-event'
  else:
    selector = side_at
    side_selection_model = 'caller-supplied-explicit-side-selector'
  bridge = build_caustic_upstream_bridge(
    old_family,
    band,
    side_at=selector,
  )
  event_state = bridge.state_at(
    event_point,
    position_tolerance_m=position_tolerance_m,
  )
  event_pressure = bridge.static_pressure_at(
    event_point,
    position_tolerance_m=position_tolerance_m,
  )
  seam_verified = bool(
    bridge.fields_converged
    and event_state is not None
    and event_pressure is not None
    and _state_matches(
      event_state,
      selected_edge.state,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=invariant_tolerance,
    )
    and _pressure_matches(
      event_pressure,
      float(selected_edge.static_pressure_Pa),
      pressure_tolerance=pressure_tolerance,
    )
    and restart.anchor_point_m == event_point
    and restart.anchor_state == selected_edge.state
    and band.anchor_point_m == event_point
    and band.anchor_state == selected_edge.state
    and _pressure_matches(
      band.total_pressure_Pa,
      total_pressure,
      pressure_tolerance=pressure_tolerance,
    )
  )
  if not seam_verified:
    return _failure(
      MocCausticUpstreamContinuationStatus.SEAM_FAILURE,
      old_family=old_family,
      seed=seed,
      restart_results=tuple(restarts),
      selected_anchor_edge_index=anchor_edge_index,
      bridge=bridge,
      message=(
        'selected one-sided restart and exact caustic bridge did not '
        'reproduce the event state and total-pressure seam'
      ),
      side_selection_model=side_selection_model,
    )
  return MocCausticUpstreamContinuationResult(
    status=MocCausticUpstreamContinuationStatus.CONVERGED_BOUNDED_CONTINUATION,
    old_family=old_family,
    seed=seed,
    restart_results=tuple(restarts),
    selected_anchor_edge_index=anchor_edge_index,
    bridge=bridge,
    seam_verified=True,
    message=(
      'solver-owned one-sided caustic continuation produced a bounded '
      'old-family/restarted-family bridge with an exact event seam; shock '
      'curve, branch physics, and downstream closure remain pending'
    ),
    side_selection_model=side_selection_model,
  )
