"""Bounded negotiation of a solver-owned global boundary station frame.

The pressure-conditioned global consumer can fail after the downstream
response has moved the ambient boundary to a station outside the retained
pressure frame.  This module makes that stop explicit.  It measures the
stations actually produced by the fresh solver attempt, verifies the source
and proposal lineage, and returns the exact extension that a future
mixed-regime/free-boundary law must generate.

The operator never extrapolates a pressure profile, holds an endpoint,
injects downstream geometry, or fabricates a new station.  A negotiated
extension is a typed request for the next solver-owned physics slice, not a
successful physical closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierReconciliationRequest,
  moc_reflected_domain_global_frontier_proposal_fingerprint,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_FRAME_NEGOTIATION_OPERATOR_ID',
  'MocReflectedDomainGlobalBoundaryFrameNegotiationStatus',
  'MocReflectedDomainGlobalBoundaryFrameNegotiationRequest',
  'MocReflectedDomainGlobalBoundaryFrameNegotiationResult',
  'solver_owned_global_boundary_station_xs',
  'build_reflected_domain_global_boundary_frame_negotiation_request',
  'negotiate_reflected_domain_global_boundary_frame',
)


MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_FRAME_NEGOTIATION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-boundary-frame-negotiation'
)


def _is_digest(value: object) -> bool:
  text = str(value)
  return bool(
    len(text) == 64
    and all(character in '0123456789abcdef' for character in text)
  )
####


def _configuration_fingerprint(configuration: dict[str, Any]) -> str:
  serialized = json.dumps(
    configuration,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


class MocReflectedDomainGlobalBoundaryFrameNegotiationStatus(str, Enum):
  """Outcome of one bounded station-frame negotiation."""

  COVERED_SOLVER_FRAME = 'covered_solver_owned_global_boundary_frame'
  FRAME_EXTENSION_REQUIRED = 'solver_owned_global_boundary_frame_extension_required'
  EXTENSION_BUDGET_FAILURE = 'global_boundary_frame_extension_budget_failure'
  NON_PHYSICAL_FRAME = 'non_physical_global_boundary_frame_request'
  LINEAGE_FAILURE = 'global_boundary_frame_lineage_failure'
  INVALID_INPUT = 'invalid_input'
####


def solver_owned_global_boundary_station_xs(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  position_tolerance_m: float = 1.0e-9,
) -> tuple[float, ...]:
  """Return the ordered ambient stations retained by a solver attempt.

  A failed ambient march may retain a final failed point result even though
  no physical field was assembled.  That point is evidence of the station the
  solver attempted to produce and is therefore included.  No point is
  interpolated or extrapolated here.
  """

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  global_euler = closure.global_euler
  if global_euler is None or global_euler.physical_field is None:
    return ()
  ####
  physical_field = global_euler.physical_field
  march = physical_field.ambient_march
  points: list[tuple[float, float]] = []
  if march is not None:
    points.extend(sample.point_m for sample in march.boundary_samples)
    if march.failed_point_result is not None and march.failed_point_result.point_m is not None:
      points.append(march.failed_point_result.point_m)
    ####
    for point_result in march.point_results:
      if point_result.point_m is not None:
        point = point_result.point_m
        if not points or point[0] > points[-1][0] + tolerance:
          points.append(point)
        # ``point_results`` repeats the accepted boundary prefix.  A repeated
        # or earlier prefix point is not a new requested station; retaining it
        # would make the typed frame request appear non-monotone.
        elif abs(point[0] - points[-1][0]) <= tolerance:
          continue
        ####
      ####
    ####
  ####
  if not points and global_euler.shock_boundary is not None:
    points.extend(global_euler.shock_boundary.shock_points_m)
  ####
  stations: list[float] = []
  for point in points:
    x_value = float(point[0])
    if not isfinite(x_value):
      continue
    ####
    if not stations or abs(x_value - stations[-1]) > tolerance:
      stations.append(x_value)
    ####
  ####
  return tuple(stations)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryFrameNegotiationRequest:
  """Lineage-bound request for a solver-owned boundary-frame extension."""

  source_closure_fingerprint: str
  source_proposal_fingerprint: str
  available_target: MocPhysicalFieldEulerBoundaryPressureTarget
  requested_x_stations_m: tuple[float, ...]
  maximum_extension_m: float
  consumer_id: str
  position_tolerance_m: float = 1.0e-9

  def __post_init__(self) -> None:
    if not _is_digest(self.source_closure_fingerprint):
      raise ValueError('source_closure_fingerprint must be a lowercase SHA-256 digest')
    ####
    if not _is_digest(self.source_proposal_fingerprint):
      raise ValueError('source_proposal_fingerprint must be a lowercase SHA-256 digest')
    ####
    if not isinstance(
      self.available_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'available_target must be a '
        'MocPhysicalFieldEulerBoundaryPressureTarget'
      )
    ####
    stations = tuple(float(value) for value in self.requested_x_stations_m)
    if len(stations) < 2:
      raise ValueError('requested_x_stations_m must contain at least two stations')
    ####
    if any(not isfinite(value) for value in stations):
      raise ValueError('requested_x_stations_m must contain finite values')
    ####
    if any(second <= first for first, second in zip(stations, stations[1:])):
      raise ValueError('requested_x_stations_m must be strictly increasing')
    ####
    maximum_extension = float(self.maximum_extension_m)
    if not isfinite(maximum_extension) or maximum_extension < 0.0:
      raise ValueError('maximum_extension_m must be finite and nonnegative')
    ####
    tolerance = float(self.position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    consumer_id = str(self.consumer_id)
    if not consumer_id:
      raise ValueError('consumer_id must be non-empty')
    ####
    object.__setattr__(self, 'requested_x_stations_m', stations)
    object.__setattr__(self, 'maximum_extension_m', maximum_extension)
    object.__setattr__(self, 'position_tolerance_m', tolerance)
    object.__setattr__(self, 'consumer_id', consumer_id)
  ####

  @property
  def available_x_interval_m(self) -> tuple[float, float]:
    return (
      self.available_target.x_stations_m[0],
      self.available_target.x_stations_m[-1],
    )
  ####

  @property
  def requested_x_interval_m(self) -> tuple[float, float]:
    return (
      self.requested_x_stations_m[0],
      self.requested_x_stations_m[-1],
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_proposal_fingerprint': self.source_proposal_fingerprint,
      'available_target': self.available_target.as_report(),
      'requested_x_stations_m': self.requested_x_stations_m,
      'available_x_interval_m': self.available_x_interval_m,
      'requested_x_interval_m': self.requested_x_interval_m,
      'maximum_extension_m': self.maximum_extension_m,
      'consumer_id': self.consumer_id,
      'position_tolerance_m': self.position_tolerance_m,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalBoundaryFrameNegotiationResult:
  """Typed frame coverage/extension evidence; never a physical closure."""

  status: MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
  request: MocReflectedDomainGlobalBoundaryFrameNegotiationRequest
  source_closure_fingerprint: str
  source_proposal_fingerprint: str
  available_x_interval_m: tuple[float, float] | None = None
  requested_x_interval_m: tuple[float, float] | None = None
  extension_lower_m: float = 0.0
  extension_upper_m: float = 0.0
  maximum_required_extension_m: float = 0.0
  lineage_verified: bool = False
  frame_request_verified: bool = False
  frame_coverage_verified: bool = False
  extension_budget_verified: bool = False
  solver_owned_extension_required: bool = False
  extrapolation_blocked: bool = True
  endpoint_hold_blocked: bool = True
  geometry_injection_blocked: bool = True
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  configuration: dict[str, Any] | None = None
  configuration_fingerprint: str = ''
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
    ):
      raise TypeError('status must be a typed frame-negotiation status')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalBoundaryFrameNegotiationRequest,
    ):
      raise TypeError('request must be a typed frame-negotiation request')
    ####
    if (
      self.source_closure_fingerprint
      != self.request.source_closure_fingerprint
      or self.source_proposal_fingerprint
      != self.request.source_proposal_fingerprint
    ):
      raise ValueError(
        'result fingerprints must match the bound request fingerprints'
      )
    ####
    for name in (
      'source_closure_fingerprint',
      'source_proposal_fingerprint',
    ):
      if not _is_digest(getattr(self, name)):
        raise ValueError(f'{name} must be a lowercase SHA-256 digest')
      ####
    ####
    for name in ('available_x_interval_m', 'requested_x_interval_m'):
      interval = getattr(self, name)
      if interval is None:
        continue
      ####
      values = tuple(float(value) for value in interval)
      if len(values) != 2 or any(not isfinite(value) for value in values):
        raise ValueError(f'{name} must contain two finite values')
      ####
      if values[1] <= values[0]:
        raise ValueError(f'{name} must be strictly increasing')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'extension_lower_m',
      'extension_upper_m',
      'maximum_required_extension_m',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'lineage_verified',
      'frame_request_verified',
      'frame_coverage_verified',
      'extension_budget_verified',
      'solver_owned_extension_required',
      'extrapolation_blocked',
      'endpoint_hold_blocked',
      'geometry_injection_blocked',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified or self.production_claim_allowed:
      raise ValueError('frame negotiation cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('frame negotiation must block chain promotion')
    ####
    object.__setattr__(self, 'configuration', dict(self.configuration or {}))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def frame_covered(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .COVERED_SOLVER_FRAME
      and self.lineage_verified
      and self.frame_request_verified
      and self.frame_coverage_verified
      and self.extension_budget_verified
      and not self.solver_owned_extension_required
    )
  ####

  @property
  def extension_required(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalBoundaryFrameNegotiationStatus
      .FRAME_EXTENSION_REQUIRED
      and self.lineage_verified
      and self.frame_request_verified
      and self.solver_owned_extension_required
    )
  ####

  @property
  def converged(self) -> bool:
    """Whether the existing frame is covered, not whether physics is closed."""

    return self.frame_covered
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_BOUNDARY_FRAME_NEGOTIATION_OPERATOR_ID,
      'status': self.status.value,
      'frame_covered': self.frame_covered,
      'extension_required': self.extension_required,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_proposal_fingerprint': self.source_proposal_fingerprint,
      'available_x_interval_m': self.available_x_interval_m,
      'requested_x_interval_m': self.requested_x_interval_m,
      'extension_lower_m': self.extension_lower_m,
      'extension_upper_m': self.extension_upper_m,
      'maximum_required_extension_m': self.maximum_required_extension_m,
      'lineage_verified': self.lineage_verified,
      'frame_request_verified': self.frame_request_verified,
      'frame_coverage_verified': self.frame_coverage_verified,
      'extension_budget_verified': self.extension_budget_verified,
      'solver_owned_extension_required': self.solver_owned_extension_required,
      'extrapolation_blocked': self.extrapolation_blocked,
      'endpoint_hold_blocked': self.endpoint_hold_blocked,
      'geometry_injection_blocked': self.geometry_injection_blocked,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': self.request.as_report(),
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'claim_status': (
        'research-only-solver-owned-frame-negotiation; no station extension '
        'was generated and mixed-regime/free-boundary closure remains open'
      ),
      'message': self.message,
    }
  ####
####


def build_reflected_domain_global_boundary_frame_negotiation_request(
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  frontier_request: MocReflectedDomainGlobalFrontierReconciliationRequest,
  available_target: MocPhysicalFieldEulerBoundaryPressureTarget,
  requested_x_stations_m: tuple[float, ...],
  *,
  maximum_extension_m: float = 0.5,
  consumer_id: str = 'moc-global-boundary-frame-negotiation-v1',
  position_tolerance_m: float = 1.0e-9,
) -> MocReflectedDomainGlobalBoundaryFrameNegotiationRequest:
  """Bind a frame request to one exact closure and frontier proposal."""

  if not isinstance(source_closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not isinstance(
    frontier_request,
    MocReflectedDomainGlobalFrontierReconciliationRequest,
  ):
    raise TypeError(
      'frontier_request must be a '
      'MocReflectedDomainGlobalFrontierReconciliationRequest'
    )
  ####
  if not isinstance(
    available_target,
    MocPhysicalFieldEulerBoundaryPressureTarget,
  ):
    raise TypeError(
      'available_target must be a '
      'MocPhysicalFieldEulerBoundaryPressureTarget'
    )
  ####
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    source_closure
  )
  proposal_fingerprint = moc_reflected_domain_global_frontier_proposal_fingerprint(
    frontier_request.proposal
  )
  return MocReflectedDomainGlobalBoundaryFrameNegotiationRequest(
    source_closure_fingerprint=source_fingerprint,
    source_proposal_fingerprint=proposal_fingerprint,
    available_target=available_target,
    requested_x_stations_m=requested_x_stations_m,
    maximum_extension_m=maximum_extension_m,
    consumer_id=consumer_id,
    position_tolerance_m=position_tolerance_m,
  )
####


def _invalid_result(
  request: MocReflectedDomainGlobalBoundaryFrameNegotiationRequest,
  status: MocReflectedDomainGlobalBoundaryFrameNegotiationStatus,
  message: str,
  *,
  lineage_verified: bool = False,
  frame_request_verified: bool = False,
  available_interval: tuple[float, float] | None = None,
  requested_interval: tuple[float, float] | None = None,
) -> MocReflectedDomainGlobalBoundaryFrameNegotiationResult:
  configuration = {
    'consumer_id': request.consumer_id,
    'maximum_extension_m': request.maximum_extension_m,
    'position_tolerance_m': request.position_tolerance_m,
    'operator_policy': (
      'solver-owned-station-frame-no-extrapolation-no-endpoint-hold-v1'
    ),
  }
  return MocReflectedDomainGlobalBoundaryFrameNegotiationResult(
    status=status,
    request=request,
    source_closure_fingerprint=request.source_closure_fingerprint,
    source_proposal_fingerprint=request.source_proposal_fingerprint,
    available_x_interval_m=available_interval,
    requested_x_interval_m=requested_interval,
    lineage_verified=lineage_verified,
    frame_request_verified=frame_request_verified,
    extension_budget_verified=False,
    solver_owned_extension_required=False,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    message=message,
  )
####


def negotiate_reflected_domain_global_boundary_frame(
  request: MocReflectedDomainGlobalBoundaryFrameNegotiationRequest,
) -> MocReflectedDomainGlobalBoundaryFrameNegotiationResult:
  """Classify coverage and the exact bounded extension request.

  This function only negotiates the frame.  It does not create pressure
  samples or alter boundary geometry.  A future mixed-regime solver must
  consume ``requested_x_interval_m`` and produce the extension through its
  own boundary equations before the outer feedback operator can continue.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalBoundaryFrameNegotiationRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainGlobalBoundaryFrameNegotiationRequest'
    )
  ####
  available_interval = request.available_x_interval_m
  requested_interval = request.requested_x_interval_m
  target_lineage = bool(
    request.available_target.source_closure_fingerprint
    == request.source_closure_fingerprint
    and request.available_target.source_proposal_fingerprint
    == request.source_proposal_fingerprint
  )
  configuration = {
    'consumer_id': request.consumer_id,
    'maximum_extension_m': request.maximum_extension_m,
    'position_tolerance_m': request.position_tolerance_m,
    'operator_policy': (
      'solver-owned-station-frame-no-extrapolation-no-endpoint-hold-v1'
    ),
  }
  if not target_lineage:
    return _invalid_result(
      request,
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.LINEAGE_FAILURE,
      'available pressure frame does not carry the exact source/proposal lineage',
      lineage_verified=False,
      frame_request_verified=True,
      available_interval=available_interval,
      requested_interval=requested_interval,
    )
  ####
  tolerance = request.position_tolerance_m
  available_min, available_max = available_interval
  requested_min, requested_max = requested_interval
  extension_lower = max(available_min - requested_min, 0.0)
  extension_upper = max(requested_max - available_max, 0.0)
  maximum_required = max(extension_lower, extension_upper)
  if not isfinite(maximum_required):
    return _invalid_result(
      request,
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.NON_PHYSICAL_FRAME,
      'required solver-owned frame extension is not finite',
      lineage_verified=True,
      frame_request_verified=True,
      available_interval=available_interval,
      requested_interval=requested_interval,
    )
  ####
  coverage = bool(maximum_required <= tolerance)
  budget = bool(maximum_required <= request.maximum_extension_m + tolerance)
  status = (
    MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.COVERED_SOLVER_FRAME
    if coverage
    else (
      MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.FRAME_EXTENSION_REQUIRED
      if budget
      else MocReflectedDomainGlobalBoundaryFrameNegotiationStatus.EXTENSION_BUDGET_FAILURE
    )
  )
  return MocReflectedDomainGlobalBoundaryFrameNegotiationResult(
    status=status,
    request=request,
    source_closure_fingerprint=request.source_closure_fingerprint,
    source_proposal_fingerprint=request.source_proposal_fingerprint,
    available_x_interval_m=available_interval,
    requested_x_interval_m=requested_interval,
    extension_lower_m=extension_lower,
    extension_upper_m=extension_upper,
    maximum_required_extension_m=maximum_required,
    lineage_verified=True,
    frame_request_verified=True,
    frame_coverage_verified=coverage,
    extension_budget_verified=budget,
    solver_owned_extension_required=not coverage,
    configuration=configuration,
    configuration_fingerprint=_configuration_fingerprint(configuration),
    message=(
      'solver-produced boundary lies inside the retained pressure frame'
      if coverage
      else (
        'solver-owned boundary frame extension is required; no pressure '
        'extrapolation, endpoint hold, or geometry injection was attempted'
        if budget
        else 'required solver-owned boundary-frame extension exceeds the bounded budget'
      )
    ),
  )
####
