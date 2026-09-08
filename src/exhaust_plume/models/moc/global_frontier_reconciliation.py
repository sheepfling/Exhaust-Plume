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
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamUpstreamFeedbackProposal,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL',
  'MocReflectedDomainGlobalFrontierReconciliationStatus',
  'MocReflectedDomainGlobalFrontierReconciliationReceipt',
  'MocReflectedDomainGlobalFrontierReconciliationRequest',
  'MocReflectedDomainGlobalFrontierReconciliationResult',
  'moc_reflected_domain_global_frontier_proposal_fingerprint',
  'build_reflected_domain_global_frontier_reconciliation_request',
  'reconcile_reflected_domain_global_frontier',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_RECONCILIATION_MODEL = (
  'research-global-frontier-reconciliation-consumer-v1'
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
