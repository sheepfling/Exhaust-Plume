"""Research-only consumption seam for global frontier feedback.

The downstream response ladder can already produce a typed, relaxed target for
a future global re-solve.  This module defines the missing boundary around
that target: a solver-owned consumer must receive the exact proposal and
return an exact receipt.  The receipt proves target acceptance only; it is not
a new global field, a closure result, or a promotion record.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import atan2, cos, hypot, isfinite, sin
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL',
  'MocReflectedDomainGlobalFrontierReconciliationStatus',
  'MocReflectedDomainGlobalFrontierReconciliationReceipt',
  'MocReflectedDomainGlobalFrontierReconciliationRequest',
  'MocReflectedDomainGlobalFrontierReconciliationResult',
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_MODEL',
  'MocReflectedDomainGlobalFrontierFreshResolveStatus',
  'MocReflectedDomainGlobalFrontierFreshResolveRequest',
  'MocReflectedDomainGlobalFrontierFreshResolveResult',
  'moc_reflected_domain_global_frontier_proposal_fingerprint',
  'build_reflected_domain_global_frontier_reconciliation_request',
  'build_reflected_domain_global_frontier_pressure_target',
  'reconcile_reflected_domain_global_frontier',
  'solve_reflected_domain_global_frontier_fresh_resolve',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL = (
  'research-global-frontier-reconciliation-consumer-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_MODEL = (
  'research-global-frontier-fresh-global-resolve-v1'
)


class MocReflectedDomainGlobalFrontierReconciliationStatus(str, Enum):
  """Outcome of handing one exact feedback proposal to a consumer."""

  RESEARCH_TARGET_ACCEPTED = 'research-global-frontier-target-accepted'
  CONSUMER_REQUIRED = 'global-frontier-consumer-required'
  CONSUMER_REJECTED = 'global-frontier-consumer-rejected-target'
  CONSUMER_FAILURE = 'global-frontier-consumer-failure'
  RECEIPT_FAILURE = 'global-frontier-consumer-receipt-failure'
  INVALID_INPUT = 'invalid_input'
####


def _validate_digest(value: str, name: str) -> str:
  digest = str(value)
  if len(digest) != 64 or any(
    character not in '0123456789abcdef' for character in digest
  ):
    raise ValueError(f'{name} must be a 64-character lowercase SHA-256 digest')
  ####
  return digest
####


def moc_reflected_domain_global_frontier_proposal_fingerprint(
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
) -> str:
  """Return a deterministic identity for one immutable feedback proposal."""

  if not isinstance(
    proposal,
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  ):
    raise TypeError(
      'proposal must be a '
      'MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal'
    )
  ####
  serialized = json.dumps(
    proposal.as_report(),
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierReconciliationReceipt:
  """Solver-owned acknowledgement of one exact target handoff.

  A receipt is intentionally smaller than a solver result.  It proves that a
  named consumer accepted the exact target frame; it does not assert that the
  global equations were re-solved or that a new closure converged.
  """

  consumer_id: str
  source_closure_fingerprint: str
  source_proposal_fingerprint: str
  accepted_x_stations_m: tuple[float, ...]
  accepted_boundary_points_m: tuple[tuple[float, float], ...]
  accepted_tangent_rad: tuple[float, ...]
  accepted_static_pressure_Pa: tuple[float, ...]
  target_accepted: bool = True
  solver_owned_target_verified: bool = True
  global_resolve_requested: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    consumer_id = str(self.consumer_id)
    if not consumer_id:
      raise ValueError('consumer_id must be non-empty')
    ####
    closure_fingerprint = _validate_digest(
      self.source_closure_fingerprint,
      'source_closure_fingerprint',
    )
    proposal_fingerprint = _validate_digest(
      self.source_proposal_fingerprint,
      'source_proposal_fingerprint',
    )
    stations = tuple(float(value) for value in self.accepted_x_stations_m)
    if len(stations) < 2 or any(not isfinite(value) for value in stations):
      raise ValueError(
        'accepted_x_stations_m must contain at least two finite stations'
      )
    ####
    if any(second <= first for first, second in zip(stations, stations[1:])):
      raise ValueError('accepted_x_stations_m must be strictly ordered')
    ####
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in self.accepted_boundary_points_m
    )
    tangents = tuple(float(value) for value in self.accepted_tangent_rad)
    pressures = tuple(
      float(value) for value in self.accepted_static_pressure_Pa
    )
    if len(points) != len(stations) or len(tangents) != len(stations):
      raise ValueError(
        'accepted boundary points and tangents must align with stations'
      )
    ####
    if len(pressures) != len(stations):
      raise ValueError(
        'accepted_static_pressure_Pa must align with stations'
      )
    ####
    if any(
      not all(isfinite(value) for value in point) for point in points
    ):
      raise ValueError('accepted_boundary_points_m must be finite')
    ####
    if any(not isfinite(value) for value in tangents):
      raise ValueError('accepted_tangent_rad must be finite')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in pressures):
      raise ValueError(
        'accepted_static_pressure_Pa must contain finite positive values'
      )
    ####
    for name in (
      'target_accepted',
      'solver_owned_target_verified',
      'global_resolve_requested',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.global_resolve_requested:
      raise ValueError('a frontier receipt must request a global re-solve')
    ####
    if self.target_accepted and not self.solver_owned_target_verified:
      raise ValueError(
        'an accepted frontier target requires solver-owned verification'
      )
    ####
    object.__setattr__(self, 'consumer_id', consumer_id)
    object.__setattr__(self, 'source_closure_fingerprint', closure_fingerprint)
    object.__setattr__(self, 'source_proposal_fingerprint', proposal_fingerprint)
    object.__setattr__(self, 'accepted_x_stations_m', stations)
    object.__setattr__(self, 'accepted_boundary_points_m', points)
    object.__setattr__(self, 'accepted_tangent_rad', tangents)
    object.__setattr__(self, 'accepted_static_pressure_Pa', pressures)
    object.__setattr__(self, 'message', str(self.message))
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL,
      'consumer_id': self.consumer_id,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_proposal_fingerprint': self.source_proposal_fingerprint,
      'accepted_x_stations_m': self.accepted_x_stations_m,
      'accepted_boundary_points_m': self.accepted_boundary_points_m,
      'accepted_tangent_rad': self.accepted_tangent_rad,
      'accepted_static_pressure_Pa': self.accepted_static_pressure_Pa,
      'target_accepted': self.target_accepted,
      'solver_owned_target_verified': self.solver_owned_target_verified,
      'global_resolve_requested': self.global_resolve_requested,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierReconciliationRequest:
  """Exact target frame supplied to a solver-owned consumer."""

  consumer_id: str
  source_closure_fingerprint: str
  source_proposal_fingerprint: str
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal
  target_x_stations_m: tuple[float, ...]
  target_boundary_points_m: tuple[tuple[float, float], ...]
  target_tangent_rad: tuple[float, ...]
  target_static_pressure_Pa: tuple[float, ...]
  global_resolve_required: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.proposal,
      MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
    ):
      raise TypeError(
        'proposal must be a '
        'MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal'
      )
    ####
    consumer_id = str(self.consumer_id)
    if not consumer_id:
      raise ValueError('consumer_id must be non-empty')
    ####
    closure_fingerprint = _validate_digest(
      self.source_closure_fingerprint,
      'source_closure_fingerprint',
    )
    proposal_fingerprint = _validate_digest(
      self.source_proposal_fingerprint,
      'source_proposal_fingerprint',
    )
    expected_fingerprint = moc_reflected_domain_global_frontier_proposal_fingerprint(
      self.proposal
    )
    if proposal_fingerprint != expected_fingerprint:
      raise ValueError(
        'source_proposal_fingerprint does not match the retained proposal'
      )
    ####
    if closure_fingerprint != self.proposal.source_closure_fingerprint:
      raise ValueError(
        'source_closure_fingerprint does not match the retained proposal'
      )
    ####
    if not self.proposal.ready_for_global_resolve:
      raise ValueError(
        'frontier reconciliation requires a proposal ready for global resolve'
      )
    ####
    stations = tuple(float(value) for value in self.target_x_stations_m)
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in self.target_boundary_points_m
    )
    tangents = tuple(float(value) for value in self.target_tangent_rad)
    pressures = tuple(float(value) for value in self.target_static_pressure_Pa)
    expected = (
      self.proposal.matched_x_stations_m,
      self.proposal.proposed_boundary_points_m,
      self.proposal.proposed_tangent_rad,
      self.proposal.proposed_static_pressure_Pa,
    )
    actual = (stations, points, tangents, pressures)
    if actual != expected:
      raise ValueError(
        'frontier reconciliation targets must retain the proposal exactly'
      )
    ####
    if not isinstance(self.global_resolve_required, bool):
      raise TypeError('global_resolve_required must be a bool')
    ####
    if not self.global_resolve_required:
      raise ValueError('frontier reconciliation requires a global re-solve')
    ####
    object.__setattr__(self, 'consumer_id', consumer_id)
    object.__setattr__(self, 'source_closure_fingerprint', closure_fingerprint)
    object.__setattr__(self, 'source_proposal_fingerprint', proposal_fingerprint)
    object.__setattr__(self, 'target_x_stations_m', stations)
    object.__setattr__(self, 'target_boundary_points_m', points)
    object.__setattr__(self, 'target_tangent_rad', tangents)
    object.__setattr__(self, 'target_static_pressure_Pa', pressures)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def lineage_verified(self) -> bool:
    return bool(
      self.proposal.ready_for_global_resolve
      and self.source_closure_fingerprint
      == self.proposal.source_closure_fingerprint
      and self.source_proposal_fingerprint
      == moc_reflected_domain_global_frontier_proposal_fingerprint(
        self.proposal
      )
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL,
      'consumer_id': self.consumer_id,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_proposal_fingerprint': self.source_proposal_fingerprint,
      'lineage_verified': self.lineage_verified,
      'target_x_stations_m': self.target_x_stations_m,
      'target_boundary_points_m': self.target_boundary_points_m,
      'target_tangent_rad': self.target_tangent_rad,
      'target_static_pressure_Pa': self.target_static_pressure_Pa,
      'global_resolve_required': self.global_resolve_required,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-global-frontier-consumer-request; no global field or '
        'production claim is produced by this request'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierReconciliationResult:
  """Research result for one solver-owned target-consumption attempt."""

  status: MocReflectedDomainGlobalFrontierReconciliationStatus
  request: MocReflectedDomainGlobalFrontierReconciliationRequest
  receipt: MocReflectedDomainGlobalFrontierReconciliationReceipt | None = None
  consumer_called: bool = False
  source_lineage_verified: bool = False
  receipt_lineage_verified: bool = False
  solver_owned_target_accepted: bool = False
  global_resolve_requested: bool = True
  global_solver_consumed: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierReconciliationStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierReconciliationStatus'
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
    if self.receipt is not None and not isinstance(
      self.receipt,
      MocReflectedDomainGlobalFrontierReconciliationReceipt,
    ):
      raise TypeError(
        'receipt must be a '
        'MocReflectedDomainGlobalFrontierReconciliationReceipt or None'
      )
    ####
    for name in (
      'consumer_called',
      'source_lineage_verified',
      'receipt_lineage_verified',
      'solver_owned_target_accepted',
      'global_resolve_requested',
      'global_solver_consumed',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.global_resolve_requested:
      raise ValueError('a reconciliation result must retain the global resolve request')
    ####
    if self.global_solver_consumed:
      raise ValueError(
        'this research seam cannot claim consumption by a global solver'
      )
    ####
    if (
      self.global_coupling_verified
      or self.downstream_boundary_closure_verified
      or not self.chain_promotion_blocked
      or self.production_claim_allowed
    ):
      raise ValueError(
        'frontier reconciliation cannot claim global closure or promotion'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged_research_consumption(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierReconciliationStatus
      .RESEARCH_TARGET_ACCEPTED
      and self.consumer_called
      and self.source_lineage_verified
      and self.receipt_lineage_verified
      and self.solver_owned_target_accepted
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL,
      'status': self.status.value,
      'converged_research_consumption': self.converged_research_consumption,
      'consumer_called': self.consumer_called,
      'source_lineage_verified': self.source_lineage_verified,
      'receipt_lineage_verified': self.receipt_lineage_verified,
      'solver_owned_target_accepted': self.solver_owned_target_accepted,
      'global_resolve_requested': self.global_resolve_requested,
      'global_solver_consumed': self.global_solver_consumed,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': self.request.as_report(),
      'receipt': None if self.receipt is None else self.receipt.as_report(),
      'claim_status': (
        'research-only-global-frontier-target-consumption; an accepted target '
        'does not constitute a global re-solve, physical closure, chain fit, '
        'or production claim'
      ),
      'message': self.message,
    }
  ####
####


def build_reflected_domain_global_frontier_reconciliation_request(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  proposal: MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  *,
  consumer_id: str,
) -> MocReflectedDomainGlobalFrontierReconciliationRequest:
  """Build an exact, solver-owned target request from one closure/proposal."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not isinstance(
    proposal,
    MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
  ):
    raise TypeError(
      'proposal must be a '
      'MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal'
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    raise ValueError(
      'frontier reconciliation requires a locally verified global closure'
    )
  ####
  closure_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    closure
  )
  if proposal.source_closure_fingerprint != closure_fingerprint:
    raise ValueError(
      'frontier proposal fingerprint does not match the supplied closure'
    )
  ####
  return MocReflectedDomainGlobalFrontierReconciliationRequest(
    consumer_id=consumer_id,
    source_closure_fingerprint=closure_fingerprint,
    source_proposal_fingerprint=(
      moc_reflected_domain_global_frontier_proposal_fingerprint(proposal)
    ),
    proposal=proposal,
    target_x_stations_m=proposal.matched_x_stations_m,
    target_boundary_points_m=proposal.proposed_boundary_points_m,
    target_tangent_rad=proposal.proposed_tangent_rad,
    target_static_pressure_Pa=proposal.proposed_static_pressure_Pa,
    message=(
      'exact downstream response target prepared for a named solver-owned '
      'global re-solve; no re-solve has been performed'
    ),
  )
####


def _receipt_matches_request(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  receipt: MocReflectedDomainGlobalFrontierReconciliationReceipt,
) -> bool:
  return bool(
    receipt.consumer_id == request.consumer_id
    and receipt.source_closure_fingerprint
    == request.source_closure_fingerprint
    and receipt.source_proposal_fingerprint
    == request.source_proposal_fingerprint
    and receipt.accepted_x_stations_m == request.target_x_stations_m
    and receipt.accepted_boundary_points_m == request.target_boundary_points_m
    and receipt.accepted_tangent_rad == request.target_tangent_rad
    and receipt.accepted_static_pressure_Pa
    == request.target_static_pressure_Pa
    and receipt.global_resolve_requested
  )
####


def reconcile_reflected_domain_global_frontier(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  *,
  consumer: Callable[
    [MocReflectedDomainGlobalFrontierReconciliationRequest],
    MocReflectedDomainGlobalFrontierReconciliationReceipt,
  ] | None = None,
) -> MocReflectedDomainGlobalFrontierReconciliationResult:
  """Offer one exact target to a solver-owned consumer.

  With no consumer the result is a typed stop.  A consumer may acknowledge
  the target, but the result never claims that a global solver consumed the
  original proposal or that the resulting field closed.
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
  source_lineage_verified = request.lineage_verified
  if consumer is None:
    return MocReflectedDomainGlobalFrontierReconciliationResult(
      status=(
        MocReflectedDomainGlobalFrontierReconciliationStatus.CONSUMER_REQUIRED
      ),
      request=request,
      source_lineage_verified=source_lineage_verified,
      message=(
        'no solver-owned global consumer was supplied; target remains an '
        'unconsumed research handoff'
      ),
    )
  ####
  try:
    receipt = consumer(request)
  except Exception as error:  # noqa: BLE001 - typed research boundary
    return MocReflectedDomainGlobalFrontierReconciliationResult(
      status=(
        MocReflectedDomainGlobalFrontierReconciliationStatus.CONSUMER_FAILURE
      ),
      request=request,
      consumer_called=True,
      source_lineage_verified=source_lineage_verified,
      message=f'solver-owned global consumer raised: {error}',
    )
  ####
  if not isinstance(
    receipt,
    MocReflectedDomainGlobalFrontierReconciliationReceipt,
  ):
    return MocReflectedDomainGlobalFrontierReconciliationResult(
      status=(
        MocReflectedDomainGlobalFrontierReconciliationStatus.RECEIPT_FAILURE
      ),
      request=request,
      consumer_called=True,
      source_lineage_verified=source_lineage_verified,
      message=(
        'solver-owned global consumer did not return a typed reconciliation '
        'receipt'
      ),
    )
  ####
  receipt_lineage_verified = _receipt_matches_request(request, receipt)
  if not receipt_lineage_verified:
    return MocReflectedDomainGlobalFrontierReconciliationResult(
      status=(
        MocReflectedDomainGlobalFrontierReconciliationStatus.RECEIPT_FAILURE
      ),
      request=request,
      receipt=receipt,
      consumer_called=True,
      source_lineage_verified=source_lineage_verified,
      receipt_lineage_verified=False,
      message=(
        'solver-owned global consumer receipt changed the exact target frame '
        'or proposal lineage'
      ),
    )
  ####
  if not receipt.target_accepted:
    return MocReflectedDomainGlobalFrontierReconciliationResult(
      status=(
        MocReflectedDomainGlobalFrontierReconciliationStatus.CONSUMER_REJECTED
      ),
      request=request,
      receipt=receipt,
      consumer_called=True,
      source_lineage_verified=source_lineage_verified,
      receipt_lineage_verified=True,
      message=(
        'solver-owned global consumer rejected the target; no re-solve or '
        'promotion was recorded'
      ),
    )
  ####
  return MocReflectedDomainGlobalFrontierReconciliationResult(
    status=(
      MocReflectedDomainGlobalFrontierReconciliationStatus
      .RESEARCH_TARGET_ACCEPTED
    ),
    request=request,
    receipt=receipt,
    consumer_called=True,
    source_lineage_verified=source_lineage_verified,
    receipt_lineage_verified=True,
    solver_owned_target_accepted=True,
    message=(
      'solver-owned consumer accepted the exact frontier target; a global '
      're-solve and physical closure audit are still required'
    ),
  )
####


class MocReflectedDomainGlobalFrontierFreshResolveStatus(str, Enum):
  """Outcome of one model-owned fresh global target re-solve."""

  CONVERGED_RESEARCH_RESOLVE = 'converged-research-global-frontier-resolve'
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_REQUIRED = 'global-frontier-source-closure-required'
  SOURCE_CONFIGURATION_FAILURE = 'global-frontier-source-configuration-failure'
  GLOBAL_RESOLVE_FAILURE = 'global-frontier-fresh-global-resolve-failure'
  TARGET_CONSUMPTION_FAILURE = 'global-frontier-target-consumption-failure'
  TARGET_COVERAGE_FAILURE = 'global-frontier-target-coverage-failure'
  TARGET_MATCH_FAILURE = 'global-frontier-target-match-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierFreshResolveRequest:
  """Inputs for a solver-owned global re-solve from one exact target packet.

  The request retains both the source closure and the immutable frontier
  proposal request.  This is intentionally different from the receipt-only
  reconciliation seam: the solver is required to create a fresh closure and
  consume the target's pressure, geometry, and tangent channels.  The result
  remains research-only until the canonical mixed-regime and refinement gates
  are independently satisfied.
  """

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest
  compression_envelope_skew: float | None = None
  branch: ShockBranch = ShockBranch.WEAK
  shock_angle_tolerance_rad: float = 2.0e-2
  target_position_tolerance_m: float = 5.0e-3
  target_tangent_tolerance_rad: float = 5.0e-3
  target_pressure_tolerance_fraction: float = 2.0e-2
  maximum_boundary_iterations: int = 16
  source: str = MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_MODEL

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.frontier_request,
      MocReflectedDomainGlobalFrontierReconciliationRequest,
    ):
      raise TypeError(
        'frontier_request must be a '
        'MocReflectedDomainGlobalFrontierReconciliationRequest'
      )
    ####
    closure_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
    if closure_fingerprint != self.frontier_request.source_closure_fingerprint:
      raise ValueError(
        'frontier_request must retain the exact source closure fingerprint'
      )
    ####
    if not self.frontier_request.lineage_verified:
      raise ValueError('frontier_request lineage must be verified')
    ####
    if not self.closure.converged or not self.closure.physical_closure_verified:
      raise ValueError(
        'fresh global frontier resolving requires a locally verified source '
        'closure'
      )
    ####
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    ####
    for name in (
      'shock_angle_tolerance_rad',
      'target_position_tolerance_m',
      'target_tangent_tolerance_rad',
      'target_pressure_tolerance_fraction',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.target_pressure_tolerance_fraction >= 1.0:
      raise ValueError('target_pressure_tolerance_fraction must be less than one')
    ####
    if (
      isinstance(self.maximum_boundary_iterations, bool)
      or not isinstance(self.maximum_boundary_iterations, int)
      or self.maximum_boundary_iterations < 1
    ):
      raise ValueError('maximum_boundary_iterations must be a positive integer')
    ####
    if self.compression_envelope_skew is not None:
      skew = float(self.compression_envelope_skew)
      if not isfinite(skew) or abs(skew) > 1.0:
        raise ValueError('compression_envelope_skew must lie in [-1, 1]')
      ####
      object.__setattr__(self, 'compression_envelope_skew', skew)
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_MODEL,
      'closure_fingerprint': (
        moc_reflected_domain_global_physical_closure_fingerprint(self.closure)
      ),
      'frontier_request': self.frontier_request.as_report(),
      'compression_envelope_skew': self.compression_envelope_skew,
      'branch': self.branch.value,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'target_position_tolerance_m': self.target_position_tolerance_m,
      'target_tangent_tolerance_rad': self.target_tangent_tolerance_rad,
      'target_pressure_tolerance_fraction': (
        self.target_pressure_tolerance_fraction
      ),
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'source': self.source,
      'claim_status': (
        'research-only-global-frontier-fresh-resolve-request; canonical '
        'free-boundary, refinement, external validation, and production '
        'promotion remain open'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierFreshResolveResult:
  """Retained evidence from one exact target-consuming global re-solve."""

  status: MocReflectedDomainGlobalFrontierFreshResolveStatus
  request: MocReflectedDomainGlobalFrontierFreshResolveRequest
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  candidate_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  target_coordinate_residuals_m: tuple[float, ...] = ()
  target_tangent_residuals_rad: tuple[float, ...] = ()
  target_pressure_residuals_Pa: tuple[float, ...] = ()
  source_lineage_verified: bool = False
  fresh_global_solve_attempted: bool = False
  candidate_is_fresh: bool = False
  target_consumption_verified: bool = False
  target_geometry_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_residuals_finite: bool = False
  target_match_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierFreshResolveStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalFrontierFreshResolveStatus'
      )
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalFrontierFreshResolveRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveRequest'
      )
    ####
    if self.target is not None and not isinstance(
      self.target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'target must be a MocPhysicalFieldEulerBoundaryPressureTarget or None'
      )
    ####
    if self.candidate_closure is not None and not isinstance(
      self.candidate_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'candidate_closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    residual_lengths: set[int] = set()
    for name in (
      'target_coordinate_residuals_m',
      'target_tangent_residuals_rad',
      'target_pressure_residuals_Pa',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      residual_lengths.add(len(values))
      object.__setattr__(self, name, values)
    ####
    if len(residual_lengths) != 1:
      raise ValueError('target residual channels must have equal lengths')
    ####
    for name in (
      'source_lineage_verified',
      'fresh_global_solve_attempted',
      'candidate_is_fresh',
      'target_consumption_verified',
      'target_geometry_consumption_verified',
      'target_coverage_verified',
      'target_residuals_finite',
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
        'fresh frontier research results cannot claim canonical global '
        'coupling or downstream boundary closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'fresh frontier research results must remain promotion-blocked'
      )
    ####
    if self.target_match_verified and not (
      self.target_coverage_verified and self.target_residuals_finite
    ):
      raise ValueError(
        'target_match_verified requires covered finite target residuals'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return self.request.frontier_request.source_closure_fingerprint
  ####

  @property
  def candidate_closure_fingerprint(self) -> str | None:
    return (
      None
      if self.candidate_closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        self.candidate_closure
      )
    )
  ####

  @property
  def converged_research_resolve(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierFreshResolveStatus
      .CONVERGED_RESEARCH_RESOLVE
      and self.source_lineage_verified
      and self.fresh_global_solve_attempted
      and self.candidate_is_fresh
      and self.target_consumption_verified
      and self.target_geometry_consumption_verified
      and self.target_coverage_verified
      and self.target_residuals_finite
      and self.target_match_verified
      and self.candidate_closure is not None
      and self.candidate_closure.converged
      and self.candidate_closure.physical_closure_verified
    )
  ####

  @property
  def production_claim_allowed_by_result(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_MODEL,
      'status': self.status.value,
      'converged_research_resolve': self.converged_research_resolve,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'candidate_closure_fingerprint': self.candidate_closure_fingerprint,
      'request': self.request.as_report(),
      'target': None if self.target is None else self.target.as_report(),
      'candidate_closure': (
        None
        if self.candidate_closure is None
        else self.candidate_closure.as_report()
      ),
      'target_coordinate_residuals_m': self.target_coordinate_residuals_m,
      'target_tangent_residuals_rad': self.target_tangent_residuals_rad,
      'target_pressure_residuals_Pa': self.target_pressure_residuals_Pa,
      'source_lineage_verified': self.source_lineage_verified,
      'fresh_global_solve_attempted': self.fresh_global_solve_attempted,
      'candidate_is_fresh': self.candidate_is_fresh,
      'target_consumption_verified': self.target_consumption_verified,
      'target_geometry_consumption_verified': (
        self.target_geometry_consumption_verified
      ),
      'target_coverage_verified': self.target_coverage_verified,
      'target_residuals_finite': self.target_residuals_finite,
      'target_match_verified': self.target_match_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'production_claim_allowed_by_result': (
        self.production_claim_allowed_by_result
      ),
      'claim_status': (
        'research-only-global-frontier-fresh-resolve; exact target consumption '
        'and a fresh global field are retained, but canonical mixed-regime '
        'coupling, refinement, external validation, and production claims '
        'remain open'
      ),
      'message': self.message,
    }
  ####
####


def build_reflected_domain_global_frontier_pressure_target(
  request: MocReflectedDomainGlobalFrontierReconciliationRequest,
) -> MocPhysicalFieldEulerBoundaryPressureTarget:
  """Build the exact pressure/geometry target consumed by the fresh solver."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not request.lineage_verified:
    raise ValueError('frontier reconciliation request lineage must be verified')
  ####
  proposal_fingerprint = moc_reflected_domain_global_frontier_proposal_fingerprint(
    request.proposal
  )
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=request.target_x_stations_m,
    static_pressure_Pa=request.target_static_pressure_Pa,
    boundary_points_m=request.target_boundary_points_m,
    tangent_rad=request.target_tangent_rad,
    source_id=f'global-frontier-fresh-resolve-target:{proposal_fingerprint}',
    model=MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_MODEL,
    source_closure_fingerprint=request.source_closure_fingerprint,
    source_proposal_fingerprint=proposal_fingerprint,
  )
####


def _fresh_resolve_boundary_sample(
  candidate: MocReflectedDomainGlobalPhysicalClosureResult,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[tuple[float, float], float, float] | None:
  boundary = candidate.downstream_boundary
  if boundary is None:
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
        (float(first[0]), float(first[1])),
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
        (
          float(first[0] + fraction * (second[0] - first[0])),
          float(first[1] + fraction * (second[1] - first[1])),
        ),
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
      (float(points[-1][0]), float(points[-1][1])),
      float(states[-1].theta_rad),
      float(pressures[-1]),
    )
  ####
  return None
####


def _fresh_resolve_target_measurement(
  request: MocReflectedDomainGlobalFrontierFreshResolveRequest,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult,
) -> tuple[
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
  bool,
  bool,
  bool,
]:
  coordinate_residuals: list[float] = []
  tangent_residuals: list[float] = []
  pressure_residuals: list[float] = []
  coverage_verified = True
  for station, target_point, target_tangent, target_pressure in zip(
    target.x_stations_m,
    target.boundary_points_m,
    target.tangent_rad,
    target.static_pressure_Pa,
    strict=True,
  ):
    sample = _fresh_resolve_boundary_sample(
      candidate,
      station,
      position_tolerance_m=request.target_position_tolerance_m,
    )
    if sample is None:
      coverage_verified = False
      continue
    ####
    point, tangent, pressure = sample
    coordinate_residuals.append(hypot(point[0] - target_point[0], point[1] - target_point[1]))
    tangent_residuals.append(
      abs(
        atan2(
          sin(tangent - target_tangent),
          cos(tangent - target_tangent),
        )
      )
    )
    pressure_residuals.append(abs(pressure - target_pressure))
  ####
  residuals = (
    *coordinate_residuals,
    *tangent_residuals,
    *pressure_residuals,
  )
  residuals_finite = bool(residuals) and all(isfinite(value) for value in residuals)
  target_match_verified = bool(
    coverage_verified
    and residuals_finite
    and len(coordinate_residuals) == len(target.x_stations_m)
    and max(coordinate_residuals, default=float('inf'))
    <= request.target_position_tolerance_m
    and max(tangent_residuals, default=float('inf'))
    <= request.target_tangent_tolerance_rad
    and all(
      residual / max(abs(target_pressure), 1.0)
      <= request.target_pressure_tolerance_fraction
      for residual, target_pressure in zip(
        pressure_residuals,
        target.static_pressure_Pa,
        strict=True,
      )
    )
  )
  return (
    tuple(coordinate_residuals),
    tuple(tangent_residuals),
    tuple(pressure_residuals),
    coverage_verified,
    residuals_finite,
    target_match_verified,
  )
####


def _fresh_resolve_target_consumption(
  request: MocReflectedDomainGlobalFrontierFreshResolveRequest,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult,
) -> tuple[bool, bool]:
  source_band = candidate.source_band
  consumed_target = None if source_band is None else source_band.ambient_pressure_target
  if consumed_target is None:
    return False, False
  ####
  target_consumed = bool(
    candidate.source_pressure_target_consumed
    and consumed_target.source_closure_fingerprint
    == request.frontier_request.source_closure_fingerprint
    and consumed_target.source_proposal_fingerprint
    == request.frontier_request.source_proposal_fingerprint
    and consumed_target.composition_overlay_source_id == target.source_id
  )
  geometry_consumed = bool(
    target_consumed
    and candidate.source_pressure_target_geometry_consumed
    and source_band.ambient_pressure_target_geometry_consumed
  )
  return target_consumed, geometry_consumed
####


def _fresh_resolve_failure(
  request: MocReflectedDomainGlobalFrontierFreshResolveRequest,
  status: MocReflectedDomainGlobalFrontierFreshResolveStatus,
  message: str,
  *,
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  fresh_global_solve_attempted: bool = False,
  source_lineage_verified: bool = False,
) -> MocReflectedDomainGlobalFrontierFreshResolveResult:
  return MocReflectedDomainGlobalFrontierFreshResolveResult(
    status=status,
    request=request,
    target=target,
    candidate_closure=candidate,
    source_lineage_verified=source_lineage_verified,
    fresh_global_solve_attempted=fresh_global_solve_attempted,
    candidate_is_fresh=bool(candidate is not None and candidate is not request.closure),
    message=message,
  )
####


def solve_reflected_domain_global_frontier_fresh_resolve(
  request: MocReflectedDomainGlobalFrontierFreshResolveRequest,
) -> MocReflectedDomainGlobalFrontierFreshResolveResult:
  """Consume an exact frontier target through a fresh global closure solve.

  The source closure is used only to recover its solver-owned remesh family,
  first-cell bracket, and incoming handoff.  The target is then passed into a
  new alternating source/global Euler solve with pressure, boundary geometry,
  and tangent consumption enabled.  No current downstream field is relabeled
  as canonical global coupling; the result is a research evidence packet until
  a downstream recheck, multi-case refinement, and independent promotion audit
  all pass.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalFrontierFreshResolveRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalFrontierFreshResolveRequest'
    )
  ####
  target = build_reflected_domain_global_frontier_pressure_target(
    request.frontier_request
  )
  ####
  remesh = request.closure.global_remesh
  selected_attempt = None if remesh is None else remesh.selected_attempt
  source_band = request.closure.source_band
  if remesh is None or selected_attempt is None or source_band is None:
    return _fresh_resolve_failure(
      request,
      MocReflectedDomainGlobalFrontierFreshResolveStatus
      .SOURCE_CONFIGURATION_FAILURE,
      'source closure retained no selected global remesh attempt or source band',
      target=target,
      source_lineage_verified=True,
    )
  ####
  first_cell = selected_attempt.first_cell_result
  bracket = first_cell.compression_amplitude_bracket
  selected_field = first_cell.selected_physical_field
  selected_physical_field = (
    None if selected_field is None else selected_field.field
  )
  if (
    bracket is None
    or len(bracket) != 2
    or selected_physical_field is None
    or len(selected_physical_field.shock_boundary_points_m) < 3
  ):
    return _fresh_resolve_failure(
      request,
      MocReflectedDomainGlobalFrontierFreshResolveStatus
      .SOURCE_CONFIGURATION_FAILURE,
      'source closure retained no solver-owned amplitude bracket or complete '
      'selected physical field for a fresh global re-solve',
      target=target,
      source_lineage_verified=True,
    )
  ####
  skew = (
    selected_attempt.compression_envelope_skew
    if request.compression_envelope_skew is None
    else request.compression_envelope_skew
  )
  try:
    candidate = solve_reflected_domain_global_physical_closure(
      source_band,
      outer_source_indices=remesh.outer_source_indices,
      target_centerline_indices=remesh.target_centerline_indices,
      compression_amplitude_lower_rad=float(bracket[0]),
      compression_amplitude_upper_rad=float(bracket[1]),
      compression_envelope_skews=(float(skew),),
      use_trace_referenced_profile=remesh.use_trace_referenced_profile,
      incoming_handoff=source_band.incoming_handoff,
      ambient_pressure_target=target,
      sample_count=len(selected_physical_field.shock_boundary_points_m),
      branch=request.branch,
      shock_angle_tolerance_rad=request.shock_angle_tolerance_rad,
      maximum_boundary_iterations=request.maximum_boundary_iterations,
      consume_ambient_pressure_target_geometry=True,
      ambient_pressure_target_geometry_tolerance_rad=(
        request.target_tangent_tolerance_rad
      ),
      use_composed_source_pressure_target_for_global_euler=True,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _fresh_resolve_failure(
      request,
      MocReflectedDomainGlobalFrontierFreshResolveStatus.GLOBAL_RESOLVE_FAILURE,
      f'fresh global frontier re-solve raised: {error}',
      target=target,
      fresh_global_solve_attempted=True,
      source_lineage_verified=True,
    )
  ####
  target_consumed, target_geometry_consumed = _fresh_resolve_target_consumption(
    request,
    target,
    candidate,
  )
  if not candidate.converged or not candidate.physical_closure_verified:
    return _fresh_resolve_failure(
      request,
      MocReflectedDomainGlobalFrontierFreshResolveStatus.GLOBAL_RESOLVE_FAILURE,
      'fresh global frontier re-solve retained a typed non-converged closure: '
      f'{candidate.message}',
      target=target,
      candidate=candidate,
      fresh_global_solve_attempted=True,
      source_lineage_verified=True,
    )
  ####
  coordinate_residuals, tangent_residuals, pressure_residuals, coverage, finite, match = (
    _fresh_resolve_target_measurement(request, target, candidate)
  )
  base_kwargs = {
    'target': target,
    'candidate_closure': candidate,
    'target_coordinate_residuals_m': coordinate_residuals,
    'target_tangent_residuals_rad': tangent_residuals,
    'target_pressure_residuals_Pa': pressure_residuals,
    'source_lineage_verified': True,
    'fresh_global_solve_attempted': True,
    'candidate_is_fresh': candidate is not request.closure,
    'target_consumption_verified': target_consumed,
    'target_geometry_consumption_verified': target_geometry_consumed,
    'target_coverage_verified': coverage,
    'target_residuals_finite': finite,
    'target_match_verified': match,
  }
  if not target_consumed or not target_geometry_consumed:
    return MocReflectedDomainGlobalFrontierFreshResolveResult(
      status=(
        MocReflectedDomainGlobalFrontierFreshResolveStatus
        .TARGET_CONSUMPTION_FAILURE
      ),
      request=request,
      message=(
        'fresh global closure converged but did not retain exact solver-owned '
        'pressure and geometry/tangent target consumption'
      ),
      **base_kwargs,
    )
  ####
  if not coverage or not finite:
    return MocReflectedDomainGlobalFrontierFreshResolveResult(
      status=(
        MocReflectedDomainGlobalFrontierFreshResolveStatus
        .TARGET_COVERAGE_FAILURE
      ),
      request=request,
      message=(
        'fresh global closure consumed the target but did not retain complete '
        'finite target-station coverage'
      ),
      **base_kwargs,
    )
  ####
  if not match:
    return MocReflectedDomainGlobalFrontierFreshResolveResult(
      status=(
        MocReflectedDomainGlobalFrontierFreshResolveStatus.TARGET_MATCH_FAILURE
      ),
      request=request,
      message=(
        'fresh global closure consumed the target but exceeded one or more '
        'bounded geometry, tangent, or pressure target tolerances'
      ),
      **base_kwargs,
    )
  ####
  return MocReflectedDomainGlobalFrontierFreshResolveResult(
    status=(
      MocReflectedDomainGlobalFrontierFreshResolveStatus
      .CONVERGED_RESEARCH_RESOLVE
    ),
    request=request,
    message=(
      'fresh global closure consumed the exact frontier target and matched '
      'its retained station frame; canonical downstream coupling, refinement, '
      'external validation, and production promotion remain open'
    ),
    **base_kwargs,
  )
####
