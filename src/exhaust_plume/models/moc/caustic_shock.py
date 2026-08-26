"""Rankine--Hugoniot probes for a source-strip caustic handoff.

The source-strip caustic primitive supplies two one-sided pre-shock state
reconstructions at a bounded characteristic crossing.  This module tests
whether either orientation can be connected by an attached compression with
the existing theta-beta-Mach solver.  It is deliberately a local candidate
probe: a matched state pair is not a shock curve, a new characteristic mesh,
or a physically closed chain cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.compression import (
  MocTurnCompressionResult,
  solve_attached_compression_to_turn,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.source_strip import (
  MocSourceStripCausticEdgeStateResult,
  MocSourceStripCausticShockSeedResult,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocCausticShockCandidateStatus',
  'MocCausticShockResolutionStatus',
  'MocSourceStripCausticShockCandidateResult',
  'MocSourceStripCausticShockResolutionResult',
  'resolve_caustic_shock_seed',
)


class MocCausticShockCandidateStatus(str, Enum):
  """Outcome for one orientation of the local shock-state probe."""

  CONVERGED_ENTROPY_ADMISSIBLE = 'converged_entropy_admissible_caustic_shock'
  INVALID_INPUT = 'invalid_input'
  NO_POSITIVE_COMPRESSION_TURN = 'no_positive_compression_turn'
  OUTSIDE_DOMAIN = 'caustic_shock_outside_attached_domain'
  STATE_MISMATCH = 'caustic_shock_state_mismatch'
####


class MocCausticShockResolutionStatus(str, Enum):
  """Outcome for both orientations of the caustic shock probe."""

  CONVERGED_CANDIDATE = 'converged_caustic_shock_candidate'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'caustic_seed_failure'
  NO_ENTROPY_ADMISSIBLE_CANDIDATE = (
    'no_entropy_admissible_caustic_shock_candidate'
  )
####


@dataclass(frozen=True, slots=True)
class MocSourceStripCausticShockCandidateResult:
  """One orientation of a local caustic Rankine--Hugoniot candidate."""

  status: MocCausticShockCandidateStatus
  upstream_edge_index: int | None
  downstream_edge_index: int | None
  upstream_state: CharacteristicState | None
  downstream_one_sided_state: CharacteristicState | None
  compression: MocTurnCompressionResult | None
  flow_turn_rad: float | None
  mach_residual_relative: float | None
  static_pressure_residual_relative: float | None
  total_pressure_residual_relative: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCausticShockCandidateStatus.CONVERGED_ENTROPY_ADMISSIBLE
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'upstream_edge_index': self.upstream_edge_index,
      'downstream_edge_index': self.downstream_edge_index,
      'flow_turn_rad': self.flow_turn_rad,
      'mach_residual_relative': self.mach_residual_relative,
      'static_pressure_residual_relative': self.static_pressure_residual_relative,
      'total_pressure_residual_relative': self.total_pressure_residual_relative,
      'compression': None if self.compression is None else {
        'status': self.compression.status.value,
        'shock_status': self.compression.shock_status.value,
        'converged': self.compression.converged,
        'downstream_mach': self.compression.downstream_mach,
        'downstream_pressure_Pa': self.compression.downstream_pressure_Pa,
        'downstream_total_pressure_Pa': self.compression.downstream_total_pressure_Pa,
        'total_pressure_ratio': self.compression.total_pressure_ratio,
        'message': self.compression.message,
      },
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class MocSourceStripCausticShockResolutionResult:
  """Both local shock orientations and their promotion-safe outcome."""

  status: MocCausticShockResolutionStatus
  seed: MocSourceStripCausticShockSeedResult | None
  candidates: tuple[MocSourceStripCausticShockCandidateResult, ...]
  selected_candidate: MocSourceStripCausticShockCandidateResult | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCausticShockResolutionStatus.CONVERGED_CANDIDATE
  ####

  @property
  def shock_state_solved(self) -> bool:
    return self.selected_candidate is not None and self.selected_candidate.converged
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'shock_state_solved': self.shock_state_solved,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'seed': None if self.seed is None else self.seed.as_report(),
      'candidates': [candidate.as_report() for candidate in self.candidates],
      'selected_candidate': (
        None
        if self.selected_candidate is None
        else self.selected_candidate.as_report()
      ),
      'message': self.message,
    }
####


def _candidate_failure(
  status: MocCausticShockCandidateStatus,
  *,
  upstream_edge_index: int | None,
  downstream_edge_index: int | None,
  upstream_state: CharacteristicState | None = None,
  downstream_one_sided_state: CharacteristicState | None = None,
  compression: MocTurnCompressionResult | None = None,
  flow_turn_rad: float | None = None,
  mach_residual_relative: float | None = None,
  static_pressure_residual_relative: float | None = None,
  total_pressure_residual_relative: float | None = None,
  message: str,
) -> MocSourceStripCausticShockCandidateResult:
  return MocSourceStripCausticShockCandidateResult(
    status=status,
    upstream_edge_index=upstream_edge_index,
    downstream_edge_index=downstream_edge_index,
    upstream_state=upstream_state,
    downstream_one_sided_state=downstream_one_sided_state,
    compression=compression,
    flow_turn_rad=flow_turn_rad,
    mach_residual_relative=mach_residual_relative,
    static_pressure_residual_relative=static_pressure_residual_relative,
    total_pressure_residual_relative=total_pressure_residual_relative,
    message=message,
  )
####


def _solve_orientation(
  seed: MocSourceStripCausticShockSeedResult,
  upstream_edge: MocSourceStripCausticEdgeStateResult,
  downstream_edge: MocSourceStripCausticEdgeStateResult,
  *,
  branch: ShockBranch,
  state_tolerance: float,
) -> MocSourceStripCausticShockCandidateResult:
  upstream_index = upstream_edge.edge_index
  downstream_index = downstream_edge.edge_index
  if (
    upstream_index is None
    or downstream_index is None
    or upstream_edge.state is None
    or downstream_edge.state is None
    or upstream_edge.static_pressure_Pa is None
    or downstream_edge.static_pressure_Pa is None
  ):
    return _candidate_failure(
      MocCausticShockCandidateStatus.INVALID_INPUT,
      upstream_edge_index=upstream_index,
      downstream_edge_index=downstream_index,
      message='caustic shock orientation lacks two reconstructed states and pressures',
    )
  if (
    seed.total_pressure_Pa is None
    or not isfinite(seed.total_pressure_Pa)
    or seed.total_pressure_Pa <= 0.0
  ):
    return _candidate_failure(
      MocCausticShockCandidateStatus.INVALID_INPUT,
      upstream_edge_index=upstream_index,
      downstream_edge_index=downstream_index,
      upstream_state=upstream_edge.state,
      downstream_one_sided_state=downstream_edge.state,
      message='caustic shock seed lacks a finite positive total pressure',
    )
  upstream = upstream_edge.state
  downstream = downstream_edge.state
  flow_turn = downstream.theta_rad - upstream.theta_rad
  if flow_turn <= 0.0:
    return _candidate_failure(
      MocCausticShockCandidateStatus.NO_POSITIVE_COMPRESSION_TURN,
      upstream_edge_index=upstream_index,
      downstream_edge_index=downstream_index,
      upstream_state=upstream,
      downstream_one_sided_state=downstream,
      flow_turn_rad=flow_turn,
      message='orientation does not provide a positive compression turn',
    )
  compression = solve_attached_compression_to_turn(
    upstream_mach=upstream.mach,
    gamma=upstream.gamma,
    upstream_pressure_Pa=upstream_edge.static_pressure_Pa,
    target_turn_rad=flow_turn,
    branch=branch,
  )
  if (
    not compression.converged
    or compression.downstream_mach is None
    or compression.downstream_pressure_Pa is None
    or compression.downstream_total_pressure_Pa is None
    or compression.total_pressure_ratio is None
  ):
    return _candidate_failure(
      MocCausticShockCandidateStatus.OUTSIDE_DOMAIN,
      upstream_edge_index=upstream_index,
      downstream_edge_index=downstream_index,
      upstream_state=upstream,
      downstream_one_sided_state=downstream,
      compression=compression,
      flow_turn_rad=flow_turn,
      message=f'attached compression candidate failed: {compression.message}',
    )
  mach_residual = (
    compression.downstream_mach - downstream.mach
  ) / max(1.0, abs(downstream.mach))
  static_pressure_residual = (
    compression.downstream_pressure_Pa - downstream_edge.static_pressure_Pa
  ) / max(1.0, abs(downstream_edge.static_pressure_Pa))
  observed_total_pressure = seed.total_pressure_Pa
  total_pressure_residual = (
    compression.downstream_total_pressure_Pa - observed_total_pressure
  ) / max(1.0, abs(observed_total_pressure))
  if any(
    abs(residual) > state_tolerance
    for residual in (
      mach_residual,
      static_pressure_residual,
      total_pressure_residual,
    )
  ):
    return _candidate_failure(
      MocCausticShockCandidateStatus.STATE_MISMATCH,
      upstream_edge_index=upstream_index,
      downstream_edge_index=downstream_index,
      upstream_state=upstream,
      downstream_one_sided_state=downstream,
      compression=compression,
      flow_turn_rad=flow_turn,
      mach_residual_relative=mach_residual,
      static_pressure_residual_relative=static_pressure_residual,
      total_pressure_residual_relative=total_pressure_residual,
      message=(
        'attached compression is mathematically valid, but its downstream '
        'Mach/pressure state does not match the opposite one-sided caustic '
        'state'
      ),
    )
  return MocSourceStripCausticShockCandidateResult(
    status=MocCausticShockCandidateStatus.CONVERGED_ENTROPY_ADMISSIBLE,
    upstream_edge_index=upstream_index,
    downstream_edge_index=downstream_index,
    upstream_state=upstream,
    downstream_one_sided_state=downstream,
    compression=compression,
    flow_turn_rad=flow_turn,
    mach_residual_relative=mach_residual,
    static_pressure_residual_relative=static_pressure_residual,
    total_pressure_residual_relative=total_pressure_residual,
    message=(
      'local attached compression matches both one-sided caustic states; '
      'shock geometry and new-family field remain pending'
    ),
  )
####


def resolve_caustic_shock_seed(
  seed: MocSourceStripCausticShockSeedResult,
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  state_tolerance: float = 1.0e-8,
) -> MocSourceStripCausticShockResolutionResult:
  """Test both orientations of a local caustic shock-state connection.

  The opposite one-sided state is treated as a candidate downstream state
  only for this diagnostic.  A converged candidate still needs a shock curve,
  a downstream characteristic-family remesh, and an external/free-boundary
  closure before it can enter the chain.
  """

  if not isinstance(seed, MocSourceStripCausticShockSeedResult):
    return MocSourceStripCausticShockResolutionResult(
      status=MocCausticShockResolutionStatus.INVALID_INPUT,
      seed=None,
      candidates=(),
      selected_candidate=None,
      message='seed must be a MocSourceStripCausticShockSeedResult',
    )
  if not isinstance(branch, ShockBranch):
    return MocSourceStripCausticShockResolutionResult(
      status=MocCausticShockResolutionStatus.INVALID_INPUT,
      seed=seed,
      candidates=(),
      selected_candidate=None,
      message='branch must be a ShockBranch',
    )
  if not isfinite(float(state_tolerance)) or state_tolerance <= 0.0:
    raise ValueError('state_tolerance must be finite and positive')
  if not seed.converged or len(seed.edge_states) != 2:
    return MocSourceStripCausticShockResolutionResult(
      status=MocCausticShockResolutionStatus.SEED_FAILURE,
      seed=seed,
      candidates=(),
      selected_candidate=None,
      message=f'caustic seed is not usable: {seed.message}',
    )
  first, second = seed.edge_states
  candidates = (
    _solve_orientation(
      seed,
      first,
      second,
      branch=branch,
      state_tolerance=state_tolerance,
    ),
    _solve_orientation(
      seed,
      second,
      first,
      branch=branch,
      state_tolerance=state_tolerance,
    ),
  )
  selected = next((candidate for candidate in candidates if candidate.converged), None)
  if selected is not None:
    return MocSourceStripCausticShockResolutionResult(
      status=MocCausticShockResolutionStatus.CONVERGED_CANDIDATE,
      seed=seed,
      candidates=candidates,
      selected_candidate=selected,
      message=(
        'one local Rankine-Hugoniot caustic shock-state candidate converged; '
        'shock geometry and downstream field remain unclosed'
      ),
    )
  return MocSourceStripCausticShockResolutionResult(
    status=MocCausticShockResolutionStatus.NO_ENTROPY_ADMISSIBLE_CANDIDATE,
    seed=seed,
    candidates=candidates,
    selected_candidate=None,
    message=(
      'neither one-sided orientation supplies an entropy-admissible matched '
      'shock state; a new-family/remesh solve is required'
    ),
  )
####
