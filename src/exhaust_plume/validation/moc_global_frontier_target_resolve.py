"""Bounded global-frontier target-guided re-solve evidence.

The downstream feedback lane can now produce an exact, solver-owned target
packet.  This module consumes that packet by re-solving the retained global
closure for each declared compression-envelope candidate and selecting the
candidate with the smallest measured target residual.

This is deliberately a bounded research seam.  The target guides candidate
selection; it is not yet imposed as a mixed-regime boundary condition inside
the global equations.  The result therefore records fresh global solves and
target residuals while keeping global-coupling, canonical-boundary, and
production gates closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  solve_reflected_domain_global_physical_closure,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.reflected_domain import ShockBranch

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_RESOLVE_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierTargetResolveStatus',
  'MocReflectedDomainGlobalFrontierTargetResolveCandidate',
  'MocReflectedDomainGlobalFrontierTargetResolveResult',
  'run_reflected_domain_global_frontier_target_guided_resolve',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_RESOLVE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-target-guided-resolve'
)


class MocReflectedDomainGlobalFrontierTargetResolveStatus(str, Enum):
  """Outcome of one bounded target-guided global re-solve ladder."""

  CONVERGED_TARGET_GUIDED_RESEARCH_RESOLVE = (
    'converged-target-guided-research-global-resolve'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-frontier-source-closure-failure'
  CANDIDATE_RESOLVE_FAILURE = 'global-frontier-candidate-resolve-failure'
  TARGET_COVERAGE_FAILURE = 'global-frontier-target-coverage-failure'
  TARGET_MISMATCH = 'global-frontier-target-mismatch'
  FIDELITY_FAILURE = 'global-frontier-fidelity-isolation-failure'
####


def _sample_boundary_at_x(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, float, float] | None:
  """Interpolate one retained global boundary sample without extrapolation."""

  boundary = closure.downstream_boundary
  if boundary is None or not boundary.samples_available:
    return None
  ####
  points = boundary.boundary_points_m
  states = boundary.boundary_states
  pressures = boundary.boundary_static_pressure_Pa
  if not (len(points) == len(states) == len(pressures) >= 2):
    return None
  ####
  if any(
    second[0] <= first[0] + position_tolerance_m
    for first, second in zip(points, points[1:])
  ):
    return None
  ####
  if (
    x_m < points[0][0] - position_tolerance_m
    or x_m > points[-1][0] + position_tolerance_m
  ):
    return None
  ####
  for index, (first, second) in enumerate(zip(points, points[1:])):
    if abs(x_m - first[0]) <= position_tolerance_m:
      return (
        float(first[1]),
        float(states[index].theta_rad),
        float(pressures[index]),
      )
    ####
    if x_m <= second[0] + position_tolerance_m:
      span = second[0] - first[0]
      if span <= position_tolerance_m:
        return None
      ####
      fraction = min(max((x_m - first[0]) / span, 0.0), 1.0)
      return (
        float(first[1] + fraction * (second[1] - first[1])),
        float(
          states[index].theta_rad
          + fraction * (states[index + 1].theta_rad - states[index].theta_rad)
        ),
        float(
          pressures[index]
          + fraction * (pressures[index + 1] - pressures[index])
        ),
      )
    ####
  ####
  if abs(x_m - points[-1][0]) <= position_tolerance_m:
    return (
      float(points[-1][1]),
      float(states[-1].theta_rad),
      float(pressures[-1]),
    )
  ####
  return None
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierTargetResolveCandidate:
  """One fresh global closure and its exact target residual measurement."""

  compression_envelope_skew: float
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  target_coordinate_residuals_m: tuple[float, ...] = ()
  target_tangent_residuals_rad: tuple[float, ...] = ()
  target_pressure_residuals_Pa: tuple[float, ...] = ()
  target_coverage_verified: bool = False
  target_residuals_finite: bool = False
  target_match_verified: bool = False
  fresh_global_solve_attempted: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    skew = float(self.compression_envelope_skew)
    if not isfinite(skew) or abs(skew) > 1.0:
      raise ValueError(
        'compression_envelope_skew must be finite and within [-1, 1]'
      )
    ####
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    for name in (
      'target_coordinate_residuals_m',
      'target_tangent_residuals_rad',
      'target_pressure_residuals_Pa',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    lengths = {
      len(self.target_coordinate_residuals_m),
      len(self.target_tangent_residuals_rad),
      len(self.target_pressure_residuals_Pa),
    }
    if len(lengths) != 1:
      raise ValueError('target residual channels must have equal lengths')
    ####
    for name in (
      'target_coverage_verified',
      'target_residuals_finite',
      'target_match_verified',
      'fresh_global_solve_attempted',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.target_match_verified and not (
      self.target_coverage_verified and self.target_residuals_finite
    ):
      raise ValueError(
        'target_match_verified requires covered finite target residuals'
      )
    ####
    object.__setattr__(self, 'compression_envelope_skew', skew)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def global_closure_verified(self) -> bool:
    return bool(
      self.closure is not None and self.closure.physical_closure_verified
    )
  ####

  @property
  def target_residual_magnitude(self) -> float:
    """Return the largest unscaled residual channel for inspection."""

    if not (
      self.target_coverage_verified
      and self.target_residuals_finite
      and self.target_coordinate_residuals_m
    ):
      return float('inf')
    ####
    return max(
      max(self.target_coordinate_residuals_m),
      max(self.target_tangent_residuals_rad),
      max(self.target_pressure_residuals_Pa),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'compression_envelope_skew': self.compression_envelope_skew,
      'global_closure_verified': self.global_closure_verified,
      'target_coordinate_residuals_m': self.target_coordinate_residuals_m,
      'target_tangent_residuals_rad': self.target_tangent_residuals_rad,
      'target_pressure_residuals_Pa': self.target_pressure_residuals_Pa,
      'maximum_coordinate_residual_m': max(
        self.target_coordinate_residuals_m,
        default=None,
      ),
      'maximum_tangent_residual_rad': max(
        self.target_tangent_residuals_rad,
        default=None,
      ),
      'maximum_pressure_residual_Pa': max(
        self.target_pressure_residuals_Pa,
        default=None,
      ),
      'target_residual_magnitude': self.target_residual_magnitude,
      'target_coverage_verified': self.target_coverage_verified,
      'target_residuals_finite': self.target_residuals_finite,
      'target_match_verified': self.target_match_verified,
      'fresh_global_solve_attempted': self.fresh_global_solve_attempted,
      'closure': None if self.closure is None else self.closure.as_report(),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierTargetResolveResult:
  """Measured result of a bounded target-guided global re-solve."""

  status: MocReflectedDomainGlobalFrontierTargetResolveStatus
  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  candidates: tuple[
    MocReflectedDomainGlobalFrontierTargetResolveCandidate,
    ...
  ] = ()
  selected_candidate_index: int | None = None
  target_lineage_verified: bool = False
  fresh_global_solve_invocation_verified: bool = False
  target_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_match_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierTargetResolveStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierTargetResolveStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest'
      )
    ####
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    candidates = tuple(self.candidates)
    if any(
      not isinstance(
        candidate,
        MocReflectedDomainGlobalFrontierTargetResolveCandidate,
      )
      for candidate in candidates
    ):
      raise TypeError(
        'candidates must contain typed target-resolve candidate values'
      )
    ####
    if self.selected_candidate_index is not None and (
      isinstance(self.selected_candidate_index, bool)
      or not isinstance(self.selected_candidate_index, int)
      or not 0 <= self.selected_candidate_index < len(candidates)
    ):
      raise ValueError('selected_candidate_index must select a retained candidate')
    ####
    for name in (
      'target_lineage_verified',
      'fresh_global_solve_invocation_verified',
      'target_consumption_verified',
      'target_coverage_verified',
      'target_match_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'target-guided research resolves cannot claim canonical global closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'target-guided research resolves must remain blocked from production'
      )
    ####
    if self.target_match_verified and not self.target_consumption_verified:
      raise ValueError(
        'target_match_verified requires a verified target consumption seam'
      )
    ####
    object.__setattr__(self, 'candidates', candidates)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def selected_candidate(self) -> (
    MocReflectedDomainGlobalFrontierTargetResolveCandidate | None
  ):
    if self.selected_candidate_index is None:
      return None
    ####
    return self.candidates[self.selected_candidate_index]
  ####

  @property
  def converged_research_resolve(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierTargetResolveStatus
      .CONVERGED_TARGET_GUIDED_RESEARCH_RESOLVE
      and self.target_lineage_verified
      and self.fresh_global_solve_invocation_verified
      and self.target_consumption_verified
      and self.target_coverage_verified
      and self.target_match_verified
      and self.selected_candidate is not None
      and self.selected_candidate.global_closure_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_TARGET_RESOLVE_OPERATOR_ID,
      'status': self.status.value,
      'converged_research_resolve': self.converged_research_resolve,
      'target_lineage_verified': self.target_lineage_verified,
      'fresh_global_solve_invocation_verified': (
        self.fresh_global_solve_invocation_verified
      ),
      'target_consumption_verified': self.target_consumption_verified,
      'target_coverage_verified': self.target_coverage_verified,
      'target_match_verified': self.target_match_verified,
      'selected_candidate_index': self.selected_candidate_index,
      'selected_candidate': (
        None
        if self.selected_candidate is None
        else self.selected_candidate.as_report()
      ),
      'candidate_count': len(self.candidates),
      'candidates': tuple(candidate.as_report() for candidate in self.candidates),
      'source_closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'source_proposal_fingerprint': (
        moc_reflected_domain_global_frontier_proposal_fingerprint(
          self.request.proposal
        )
      ),
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-target-guided-global-candidate-selection; the exact '
        'target guided fresh global solves but was not imposed as a canonical '
        'mixed-regime boundary condition'
      ),
      'request': self.request.as_report(),
      'message': self.message,
    }
  ####
####


def _invalid_result(
  status: MocReflectedDomainGlobalFrontierTargetResolveStatus,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  message: str,
) -> MocReflectedDomainGlobalFrontierTargetResolveResult:
  return MocReflectedDomainGlobalFrontierTargetResolveResult(
    status=status,
    request=request,
    source_closure=source_closure,
    target_lineage_verified=request.lineage_verified,
    message=message,
  )
####


def _measure_candidate_target(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  position_tolerance_m: float,
  tangent_tolerance_rad: float,
  pressure_tolerance_fraction: float,
) -> tuple[
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
  bool,
  bool,
  bool,
  str,
]:
  coordinate_residuals: list[float] = []
  tangent_residuals: list[float] = []
  pressure_residuals: list[float] = []
  for x_m, target_point, target_tangent, target_pressure in zip(
    request.target_x_stations_m,
    request.target_boundary_points_m,
    request.target_tangent_rad,
    request.target_static_pressure_Pa,
    strict=True,
  ):
    sample = _sample_boundary_at_x(
      closure,
      x_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sample is None:
      return (), (), (), False, False, False, (
        'target station lies outside the retained fresh global boundary; '
        'no extrapolation or endpoint hold was attempted'
      )
    ####
    boundary_y, boundary_tangent, boundary_pressure = sample
    coordinate_residuals.append(abs(boundary_y - target_point[1]))
    tangent_residuals.append(abs(boundary_tangent - target_tangent))
    pressure_residuals.append(abs(boundary_pressure - target_pressure))
  ####
  residuals = (
    *coordinate_residuals,
    *tangent_residuals,
    *pressure_residuals,
  )
  finite = bool(residuals) and all(isfinite(value) for value in residuals)
  match = bool(
    finite
    and max(coordinate_residuals, default=float('inf')) <= position_tolerance_m
    and max(tangent_residuals, default=float('inf')) <= tangent_tolerance_rad
    and all(
      pressure_residual / max(abs(target_pressure), 1.0)
      <= pressure_tolerance_fraction
      for pressure_residual, target_pressure in zip(
        pressure_residuals,
        request.target_static_pressure_Pa,
        strict=True,
      )
    )
  )
  return (
    tuple(coordinate_residuals),
    tuple(tangent_residuals),
    tuple(pressure_residuals),
    True,
    finite,
    match,
    (
      'fresh global boundary covered the exact target and met the bounded '
      'research tolerances'
      if match
      else 'fresh global boundary covered the exact target but exceeded at '
      'least one bounded research tolerance'
    ),
  )
####


def _candidate_target_score(
  candidate: MocReflectedDomainGlobalFrontierTargetResolveCandidate,
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  position_tolerance_m: float,
  tangent_tolerance_rad: float,
  pressure_tolerance_fraction: float,
) -> float:
  if not (
    candidate.target_coverage_verified
    and candidate.target_residuals_finite
  ):
    return float('inf')
  ####
  return max(
    max(candidate.target_coordinate_residuals_m, default=float('inf'))
    / position_tolerance_m,
    max(candidate.target_tangent_residuals_rad, default=float('inf'))
    / tangent_tolerance_rad,
    max(
      (
        residual / max(abs(target_pressure), 1.0)
        for residual, target_pressure in zip(
          candidate.target_pressure_residuals_Pa,
          request.target_static_pressure_Pa,
          strict=True,
        )
      ),
      default=float('inf'),
    )
    / pressure_tolerance_fraction,
  )
####


def run_reflected_domain_global_frontier_target_guided_resolve(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  candidate_compression_envelope_skews: Sequence[float] | None = None,
  shock_angle_tolerance_rad: float = 0.02,
  position_tolerance_m: float = 5.0e-3,
  tangent_tolerance_rad: float = 5.0e-3,
  pressure_tolerance_fraction: float = 0.02,
  maximum_candidate_count: int = 8,
) -> MocReflectedDomainGlobalFrontierTargetResolveResult:
  """Fresh-solve bounded global candidates against one exact target packet.

  The source band, outer/centerline source indices, and amplitude bracket come
  from the retained global solver result.  The target changes only candidate
  selection within that explicit family; it never changes the source field,
  extrapolates a state, or promotes the selected candidate.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    source_closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not request.lineage_verified:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      'frontier request lineage is not verified',
    )
  ####
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  if source_fingerprint != request.source_closure_fingerprint:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      'source closure does not match the exact frontier request fingerprint',
    )
  ####
  if not source_closure.converged or not source_closure.physical_closure_verified:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      'target-guided global re-solving requires a locally verified source closure',
    )
  ####
  try:
    resolved_position_tolerance = float(position_tolerance_m)
    resolved_tangent_tolerance = float(tangent_tolerance_rad)
    resolved_pressure_tolerance = float(pressure_tolerance_fraction)
    resolved_shock_angle_tolerance = float(shock_angle_tolerance_rad)
  except (TypeError, ValueError) as error:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      f'target-guided resolve tolerances must be numeric: {error}',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      resolved_position_tolerance,
      resolved_tangent_tolerance,
      resolved_pressure_tolerance,
      resolved_shock_angle_tolerance,
    )
  ):
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      'target-guided resolve tolerances must be finite and positive',
    )
  ####
  if (
    isinstance(maximum_candidate_count, bool)
    or not isinstance(maximum_candidate_count, int)
    or maximum_candidate_count < 1
  ):
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      'maximum_candidate_count must be a positive integer',
    )
  ####
  remesh = source_closure.global_remesh
  selected_attempt = None if remesh is None else remesh.selected_attempt
  if remesh is None or selected_attempt is None or source_closure.source_band is None:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      'source closure retained no complete remesh, selected attempt, or source band',
    )
  ####
  bracket = selected_attempt.first_cell_result.compression_amplitude_bracket
  selected_field = selected_attempt.first_cell_result.selected_physical_field
  if (
    bracket is None
    or len(bracket) != 2
    or selected_field is None
    or selected_field.field is None
  ):
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      'source closure retained no solver-owned amplitude bracket or field sample count',
    )
  ####
  sample_count = len(selected_field.field.shock_boundary_points_m)
  if sample_count < 3:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_closure,
      'source closure retained too few shock samples for a fresh global resolve',
    )
  ####
  try:
    raw_skews = (
      remesh.compression_envelope_skews
      if candidate_compression_envelope_skews is None
      else tuple(candidate_compression_envelope_skews)
    )
    skews = tuple(float(value) for value in raw_skews)
  except (TypeError, ValueError) as error:
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      f'candidate_compression_envelope_skews must be numeric: {error}',
    )
  ####
  if (
    not skews
    or len(skews) > maximum_candidate_count
    or any(not isfinite(value) or abs(value) > 1.0 for value in skews)
    or len(set(skews)) != len(skews)
  ):
    return _invalid_result(
      MocReflectedDomainGlobalFrontierTargetResolveStatus.INVALID_INPUT,
      request,
      source_closure,
      'candidate_compression_envelope_skews must be unique, bounded, and '
      f'contain at most {maximum_candidate_count} values',
    )
  ####
  candidates: list[MocReflectedDomainGlobalFrontierTargetResolveCandidate] = []
  for skew in skews:
    try:
      fresh_closure = solve_reflected_domain_global_physical_closure(
        source_closure.source_band,
        outer_source_indices=remesh.outer_source_indices,
        target_centerline_indices=remesh.target_centerline_indices,
        compression_amplitude_lower_rad=float(bracket[0]),
        compression_amplitude_upper_rad=float(bracket[1]),
        compression_envelope_skews=(skew,),
        incoming_handoff=source_closure.source_band.incoming_handoff,
        sample_count=sample_count,
        branch=ShockBranch.WEAK,
        shock_angle_tolerance_rad=resolved_shock_angle_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      candidates.append(
        MocReflectedDomainGlobalFrontierTargetResolveCandidate(
          compression_envelope_skew=skew,
          closure=None,
          fresh_global_solve_attempted=True,
          message=f'fresh global re-solve raised: {error}',
        )
      )
      continue
    ####
    if not fresh_closure.converged or not fresh_closure.physical_closure_verified:
      candidates.append(
        MocReflectedDomainGlobalFrontierTargetResolveCandidate(
          compression_envelope_skew=skew,
          closure=fresh_closure,
          fresh_global_solve_attempted=True,
          message=(
            'fresh global re-solve retained a typed non-converged closure: '
            f'{fresh_closure.message}'
          ),
        )
      )
      continue
    ####
    (
      coordinate_residuals,
      tangent_residuals,
      pressure_residuals,
      coverage_verified,
      residuals_finite,
      match_verified,
      measurement_message,
    ) = _measure_candidate_target(
      fresh_closure,
      request,
      position_tolerance_m=resolved_position_tolerance,
      tangent_tolerance_rad=resolved_tangent_tolerance,
      pressure_tolerance_fraction=resolved_pressure_tolerance,
    )
    candidates.append(
      MocReflectedDomainGlobalFrontierTargetResolveCandidate(
        compression_envelope_skew=skew,
        closure=fresh_closure,
        target_coordinate_residuals_m=coordinate_residuals,
        target_tangent_residuals_rad=tangent_residuals,
        target_pressure_residuals_Pa=pressure_residuals,
        target_coverage_verified=coverage_verified,
        target_residuals_finite=residuals_finite,
        target_match_verified=match_verified,
        fresh_global_solve_attempted=True,
        message=measurement_message,
      )
    )
  ####
  fresh_invocation_verified = bool(
    candidates and all(candidate.fresh_global_solve_attempted for candidate in candidates)
  )
  valid_indices = tuple(
    index
    for index, candidate in enumerate(candidates)
    if candidate.global_closure_verified
    and candidate.target_coverage_verified
    and candidate.target_residuals_finite
  )
  selected_index = (
    None
    if not valid_indices
    else min(
      valid_indices,
      key=lambda index: _candidate_target_score(
        candidates[index],
        request,
        position_tolerance_m=resolved_position_tolerance,
        tangent_tolerance_rad=resolved_tangent_tolerance,
        pressure_tolerance_fraction=resolved_pressure_tolerance,
      ),
    )
  )
  selected = None if selected_index is None else candidates[selected_index]
  target_coverage_verified = bool(
    selected is not None and selected.target_coverage_verified
  )
  target_match_verified = bool(
    selected is not None and selected.target_match_verified
  )
  target_consumption_verified = bool(
    request.lineage_verified
    and fresh_invocation_verified
    and selected is not None
    and target_coverage_verified
  )
  if selected is None:
    status = (
      MocReflectedDomainGlobalFrontierTargetResolveStatus.TARGET_COVERAGE_FAILURE
      if candidates
      else MocReflectedDomainGlobalFrontierTargetResolveStatus.CANDIDATE_RESOLVE_FAILURE
    )
    message = (
      'fresh global candidates did not produce a covered, locally verified '
      'boundary for the exact frontier target'
    )
  elif target_match_verified:
    status = (
      MocReflectedDomainGlobalFrontierTargetResolveStatus
      .CONVERGED_TARGET_GUIDED_RESEARCH_RESOLVE
    )
    message = (
      'fresh global closure candidates were measured against the exact '
      'frontier target and the selected candidate passed bounded research '
      'tolerances; canonical global coupling remains open'
    )
  else:
    status = MocReflectedDomainGlobalFrontierTargetResolveStatus.TARGET_MISMATCH
    message = (
      'fresh global closure candidates covered the exact frontier target, '
      'but none met all bounded target tolerances'
    )
  ####
  return MocReflectedDomainGlobalFrontierTargetResolveResult(
    status=status,
    request=request,
    source_closure=source_closure,
    candidates=tuple(candidates),
    selected_candidate_index=selected_index,
    target_lineage_verified=request.lineage_verified,
    fresh_global_solve_invocation_verified=fresh_invocation_verified,
    target_consumption_verified=target_consumption_verified,
    target_coverage_verified=target_coverage_verified,
    target_match_verified=target_match_verified,
    message=message,
  )
####
