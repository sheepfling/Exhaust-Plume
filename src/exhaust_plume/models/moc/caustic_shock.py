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
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.source_strip import (
  MocSourceStripCausticEdgeStateResult,
  MocSourceStripCausticShockSeedResult,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocCausticShockCandidateStatus',
  'MocCausticShockResolutionStatus',
  'MocCausticShockBridgeStatus',
  'MocSourceStripCausticShockCandidateResult',
  'MocSourceStripCausticShockResolutionResult',
  'MocCausticShockBridgeResult',
  'resolve_caustic_shock_seed',
  'solve_caustic_shock_bridge',
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


class MocCausticShockBridgeStatus(str, Enum):
  """Outcome of an invariant-conditioned local caustic shock solve."""

  CONVERGED_LOCAL_COMPATIBILITY = (
    'converged_local_caustic_shock_compatibility'
  )
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'caustic_seed_failure'
  ATTACHED_BRANCH_FAILURE = 'caustic_shock_attached_branch_failure'
  INVARIANT_BRACKET_FAILURE = 'caustic_shock_invariant_bracket_failure'
  INVARIANT_SOLVE_FAILURE = 'caustic_shock_invariant_solve_failure'
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
####


@dataclass(frozen=True, slots=True)
class MocCausticShockBridgeResult:
  """A local shock state solved from one-sided data and one explicit invariant.

  The two states at a characteristic caustic are both pre-shock
  reconstructions.  They are therefore not silently assigned upstream and
  downstream roles.  This result instead takes one selected one-sided state as
  the upstream state and solves the attached compression turn required for an
  explicitly supplied downstream characteristic invariant.  It is a local
  Rankine--Hugoniot/compatibility result only: no shock curve, downstream
  characteristic mesh, or closed chain cell is implied.
  """

  status: MocCausticShockBridgeStatus
  seed: MocSourceStripCausticShockSeedResult | None
  upstream_edge_index: int | None
  downstream_invariant_family: CharacteristicFamily | None
  downstream_invariant_target: float | None
  upstream_state: CharacteristicState | None
  downstream_state: CharacteristicState | None
  compression: MocTurnCompressionResult | None
  shock_angle_rad: float | None
  flow_turn_rad: float | None
  invariant_residual: float | None
  turn_bracket_rad: tuple[float, float] | None
  iterations: int
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCausticShockBridgeStatus.CONVERGED_LOCAL_COMPATIBILITY
  ####

  @property
  def entropy_admissible(self) -> bool:
    """Whether the local compression has a strict total-pressure loss."""

    ratio = None if self.compression is None else self.compression.total_pressure_ratio
    return bool(
      self.converged
      and ratio is not None
      and isfinite(float(ratio))
      and 0.0 < float(ratio) < 1.0
      and self.downstream_state is not None
      and self.downstream_state.mach > 1.0
    )
  ####

  @property
  def shock_curve_verified(self) -> bool:
    """A local shock angle is not a fitted downstream shock curve."""

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

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'entropy_admissible': self.entropy_admissible,
      'shock_curve_verified': self.shock_curve_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'upstream_edge_index': self.upstream_edge_index,
      'downstream_invariant_family': (
        None
        if self.downstream_invariant_family is None
        else self.downstream_invariant_family.value
      ),
      'downstream_invariant_target': self.downstream_invariant_target,
      'upstream_state': (
        None
        if self.upstream_state is None
        else {
          'x_m': self.upstream_state.x_m,
          'y_m': self.upstream_state.y_m,
          'theta_rad': self.upstream_state.theta_rad,
          'mach': self.upstream_state.mach,
          'gamma': self.upstream_state.gamma,
        }
      ),
      'downstream_state': (
        None
        if self.downstream_state is None
        else {
          'x_m': self.downstream_state.x_m,
          'y_m': self.downstream_state.y_m,
          'theta_rad': self.downstream_state.theta_rad,
          'mach': self.downstream_state.mach,
          'gamma': self.downstream_state.gamma,
        }
      ),
      'compression': None if self.compression is None else {
        'status': self.compression.status.value,
        'shock_status': self.compression.shock_status.value,
        'converged': self.compression.converged,
        'target_turn_rad': self.compression.target_turn_rad,
        'beta_rad': self.compression.beta_rad,
        'downstream_mach': self.compression.downstream_mach,
        'downstream_pressure_Pa': self.compression.downstream_pressure_Pa,
        'downstream_total_pressure_Pa': self.compression.downstream_total_pressure_Pa,
        'total_pressure_ratio': self.compression.total_pressure_ratio,
        'message': self.compression.message,
      },
      'shock_angle_rad': self.shock_angle_rad,
      'flow_turn_rad': self.flow_turn_rad,
      'invariant_residual': self.invariant_residual,
      'turn_bracket_rad': self.turn_bracket_rad,
      'iterations': self.iterations,
      'message': self.message,
    }
  ####
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
####


def solve_caustic_shock_bridge(
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
) -> MocCausticShockBridgeResult:
  """Solve a local caustic shock state against one explicit invariant.

  A caustic supplies two one-sided states from the same pre-shock field.  It
  does not identify an upstream/downstream pair.  This primitive therefore
  selects one edge state as upstream and treats the requested downstream
  characteristic invariant as an independent boundary condition.  The
  resulting state is useful for a later shock-curve/field solve, but it never
  promotes itself to a physical chain cell.
  """

  seed_value = seed if isinstance(seed, MocSourceStripCausticShockSeedResult) else None

  def failure(
    status: MocCausticShockBridgeStatus,
    message: str,
    *,
    upstream_state: CharacteristicState | None = None,
    compression: MocTurnCompressionResult | None = None,
    shock_angle_rad: float | None = None,
    flow_turn_rad: float | None = None,
    invariant_residual: float | None = None,
    turn_bracket_rad: tuple[float, float] | None = None,
    iterations: int = 0,
  ) -> MocCausticShockBridgeResult:
    return MocCausticShockBridgeResult(
      status=status,
      seed=seed_value,
      upstream_edge_index=(
        upstream_edge_index if isinstance(upstream_edge_index, int) else None
      ),
      downstream_invariant_family=(
        downstream_invariant_family
        if isinstance(downstream_invariant_family, CharacteristicFamily)
        else None
      ),
      downstream_invariant_target=(
        float(downstream_invariant_target)
        if isinstance(downstream_invariant_target, (int, float))
        and isfinite(float(downstream_invariant_target))
        else None
      ),
      upstream_state=upstream_state,
      downstream_state=None,
      compression=compression,
      shock_angle_rad=shock_angle_rad,
      flow_turn_rad=flow_turn_rad,
      invariant_residual=invariant_residual,
      turn_bracket_rad=turn_bracket_rad,
      iterations=iterations,
      message=message,
    )
  ####

  if seed_value is None:
    return failure(
      MocCausticShockBridgeStatus.INVALID_INPUT,
      'seed must be a MocSourceStripCausticShockSeedResult',
    )
  ####
  if not isinstance(downstream_invariant_family, CharacteristicFamily):
    return failure(
      MocCausticShockBridgeStatus.INVALID_INPUT,
      'downstream_invariant_family must be a CharacteristicFamily',
    )
  ####
  try:
    invariant_target = float(downstream_invariant_target)
  except (TypeError, ValueError):
    invariant_target = float('nan')
  ####
  if not isfinite(invariant_target):
    return failure(
      MocCausticShockBridgeStatus.INVALID_INPUT,
      'downstream_invariant_target must be finite',
    )
  ####
  if not isinstance(upstream_edge_index, int) or isinstance(upstream_edge_index, bool):
    return failure(
      MocCausticShockBridgeStatus.INVALID_INPUT,
      'upstream_edge_index must be 0 or 1',
    )
  ####
  if upstream_edge_index not in (0, 1):
    return failure(
      MocCausticShockBridgeStatus.INVALID_INPUT,
      'upstream_edge_index must be 0 or 1',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return failure(
      MocCausticShockBridgeStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
    )
  ####
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  ####
  if not isfinite(float(maximum_turn_rad)) or maximum_turn_rad <= 0.0:
    raise ValueError('maximum_turn_rad must be finite and positive')
  ####
  if (
    isinstance(scan_samples, bool)
    or not isinstance(scan_samples, int)
    or scan_samples < 4
  ):
    raise ValueError('scan_samples must be an integer greater than or equal to four')
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  if not seed_value.converged or len(seed_value.edge_states) != 2:
    return failure(
      MocCausticShockBridgeStatus.SEED_FAILURE,
      f'caustic seed is not usable: {seed_value.message}',
    )
  ####

  upstream_edge = seed_value.edge_states[upstream_edge_index]
  if (
    not upstream_edge.converged
    or upstream_edge.state is None
    or upstream_edge.static_pressure_Pa is None
  ):
    return failure(
      MocCausticShockBridgeStatus.SEED_FAILURE,
      'selected caustic edge lacks a converged state and static pressure',
    )
  ####
  upstream = upstream_edge.state
  upstream_pressure = float(upstream_edge.static_pressure_Pa)
  if not isfinite(upstream_pressure) or upstream_pressure <= 0.0:
    return failure(
      MocCausticShockBridgeStatus.SEED_FAILURE,
      'selected caustic edge lacks a finite positive static pressure',
      upstream_state=upstream,
    )
  ####

  lower_turn = max(1.0e-8, float(invariant_tolerance))
  upper_turn = float(maximum_turn_rad)
  if upper_turn <= lower_turn:
    return failure(
      MocCausticShockBridgeStatus.INVARIANT_BRACKET_FAILURE,
      'invariant search interval is empty for the selected caustic state',
      upstream_state=upstream,
      turn_bracket_rad=(lower_turn, upper_turn),
    )
  ####

  def evaluate(
    turn_rad: float,
  ) -> tuple[float, MocTurnCompressionResult] | None:
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=upstream.mach,
        gamma=upstream.gamma,
        upstream_pressure_Pa=upstream_pressure,
        target_turn_rad=turn_rad,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      return None
    ####
    if (
      not compression.converged
      or compression.downstream_mach is None
      or compression.beta_rad is None
      or compression.total_pressure_ratio is None
    ):
      return None
    ####
    downstream_theta = upstream.theta_rad + turn_rad
    downstream_nu = prandtl_meyer_angle_rad(
      compression.downstream_mach,
      upstream.gamma,
    )
    invariant_value = (
      downstream_theta - downstream_nu
      if downstream_invariant_family is CharacteristicFamily.PLUS
      else downstream_theta + downstream_nu
    )
    residual = invariant_value - invariant_target
    if not isfinite(residual):
      return None
    ####
    return residual, compression
  ####

  lower_evaluation = evaluate(lower_turn)
  if lower_evaluation is None:
    return failure(
      MocCausticShockBridgeStatus.ATTACHED_BRANCH_FAILURE,
      'the selected caustic state has no valid positive attached-compression branch',
      upstream_state=upstream,
      turn_bracket_rad=(lower_turn, upper_turn),
    )
  ####

  def success(
    turn_rad: float,
    evaluation: tuple[float, MocTurnCompressionResult],
    *,
    bracket: tuple[float, float],
    iterations: int,
  ) -> MocCausticShockBridgeResult | None:
    residual, compression = evaluation
    ratio = compression.total_pressure_ratio
    if (
      ratio is None
      or not isfinite(float(ratio))
      or not 0.0 < float(ratio) < 1.0
      or compression.downstream_mach is None
      or compression.downstream_mach <= 1.0
      or compression.beta_rad is None
    ):
      return None
    ####
    downstream_state = CharacteristicState(
      x_m=upstream.x_m,
      y_m=upstream.y_m,
      theta_rad=upstream.theta_rad + turn_rad,
      mach=compression.downstream_mach,
      gamma=upstream.gamma,
    )
    return MocCausticShockBridgeResult(
      status=MocCausticShockBridgeStatus.CONVERGED_LOCAL_COMPATIBILITY,
      seed=seed_value,
      upstream_edge_index=upstream_edge_index,
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_target=invariant_target,
      upstream_state=upstream,
      downstream_state=downstream_state,
      compression=compression,
      shock_angle_rad=upstream.theta_rad - compression.beta_rad,
      flow_turn_rad=turn_rad,
      invariant_residual=residual,
      turn_bracket_rad=bracket,
      iterations=iterations,
      message=(
        'explicit downstream characteristic invariant produced an '
        'entropy-admissible local shock state; shock curve, downstream field, '
        'and physical closure remain pending'
      ),
    )
  ####

  if abs(lower_evaluation[0]) <= invariant_tolerance:
    result = success(
      lower_turn,
      lower_evaluation,
      bracket=(lower_turn, lower_turn),
      iterations=0,
    )
    if result is not None:
      return result
    ####
    return failure(
      MocCausticShockBridgeStatus.ATTACHED_BRANCH_FAILURE,
      'the lower invariant match did not pass the strict entropy gate',
      upstream_state=upstream,
      compression=lower_evaluation[1],
      flow_turn_rad=lower_turn,
      invariant_residual=lower_evaluation[0],
      turn_bracket_rad=(lower_turn, lower_turn),
    )
  ####

  previous_turn = lower_turn
  previous_evaluation = lower_evaluation
  last_valid_turn = lower_turn
  for scan_index in range(1, scan_samples + 1):
    current_turn = lower_turn + (upper_turn - lower_turn) * scan_index / scan_samples
    current_evaluation = evaluate(current_turn)
    if current_evaluation is None:
      break
    ####
    last_valid_turn = current_turn
    if abs(current_evaluation[0]) <= invariant_tolerance:
      result = success(
        current_turn,
        current_evaluation,
        bracket=(current_turn, current_turn),
        iterations=0,
      )
      if result is not None:
        return result
      ####
      return failure(
        MocCausticShockBridgeStatus.ATTACHED_BRANCH_FAILURE,
        'the scan-point invariant match did not pass the strict entropy gate',
        upstream_state=upstream,
        compression=current_evaluation[1],
        flow_turn_rad=current_turn,
        invariant_residual=current_evaluation[0],
        turn_bracket_rad=(current_turn, current_turn),
      )
    ####
    if previous_evaluation[0] * current_evaluation[0] < 0.0:
      bracket_lower = previous_turn
      bracket_upper = current_turn
      lower_residual = previous_evaluation[0]
      upper_evaluation = current_evaluation
      for iteration in range(1, maximum_iterations + 1):
        midpoint = 0.5 * (bracket_lower + bracket_upper)
        midpoint_evaluation = evaluate(midpoint)
        if midpoint_evaluation is None:
          return failure(
            MocCausticShockBridgeStatus.INVARIANT_SOLVE_FAILURE,
            'invariant bisection left the attached-compression branch',
            upstream_state=upstream,
            turn_bracket_rad=(bracket_lower, bracket_upper),
            iterations=iteration,
          )
        ####
        midpoint_residual = midpoint_evaluation[0]
        if abs(midpoint_residual) <= invariant_tolerance:
          result = success(
            midpoint,
            midpoint_evaluation,
            bracket=(bracket_lower, bracket_upper),
            iterations=iteration,
          )
          if result is not None:
            return result
          ####
          return failure(
            MocCausticShockBridgeStatus.ATTACHED_BRANCH_FAILURE,
            'invariant bisection match did not pass the strict entropy gate',
            upstream_state=upstream,
            compression=midpoint_evaluation[1],
            flow_turn_rad=midpoint,
            invariant_residual=midpoint_residual,
            turn_bracket_rad=(bracket_lower, bracket_upper),
            iterations=iteration,
          )
        ####
        if lower_residual * midpoint_residual <= 0.0:
          bracket_upper = midpoint
          upper_evaluation = midpoint_evaluation
        else:
          bracket_lower = midpoint
          lower_residual = midpoint_residual
        ####
      ####
      return failure(
        MocCausticShockBridgeStatus.INVARIANT_SOLVE_FAILURE,
        'invariant bisection did not meet its residual tolerance',
        upstream_state=upstream,
        compression=upper_evaluation[1],
        flow_turn_rad=0.5 * (bracket_lower + bracket_upper),
        invariant_residual=upper_evaluation[0],
        turn_bracket_rad=(bracket_lower, bracket_upper),
        iterations=maximum_iterations,
      )
    ####
    previous_turn = current_turn
    previous_evaluation = current_evaluation
  ####

  return failure(
    MocCausticShockBridgeStatus.INVARIANT_BRACKET_FAILURE,
    'the explicit downstream invariant was not reached on the attached branch',
    upstream_state=upstream,
    compression=previous_evaluation[1],
    flow_turn_rad=last_valid_turn,
    invariant_residual=previous_evaluation[0],
    turn_bracket_rad=(lower_turn, last_valid_turn),
  )
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
  ####
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
  ####
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
  ####
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
  ####
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
  ####
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
  ####
  if not isinstance(branch, ShockBranch):
    return MocSourceStripCausticShockResolutionResult(
      status=MocCausticShockResolutionStatus.INVALID_INPUT,
      seed=seed,
      candidates=(),
      selected_candidate=None,
      message='branch must be a ShockBranch',
    )
  ####
  if not isfinite(float(state_tolerance)) or state_tolerance <= 0.0:
    raise ValueError('state_tolerance must be finite and positive')
  ####
  if not seed.converged or len(seed.edge_states) != 2:
    return MocSourceStripCausticShockResolutionResult(
      status=MocCausticShockResolutionStatus.SEED_FAILURE,
      seed=seed,
      candidates=(),
      selected_candidate=None,
      message=f'caustic seed is not usable: {seed.message}',
    )
  ####
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
  ####
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
