"""Independent audit for a fresh global frontier re-solve.

The model-side frontier resolver retains a compact result with solver-owned
flags.  This module deliberately does not use those summary flags as proof.
It rebuilds the exact target from the request, checks the consumed target's
lineage, and recomputes geometry, tangent, and pressure residuals from the
candidate downstream boundary.  The audit remains research-only: it cannot
open the canonical free-boundary, refinement, validation, or production
gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import atan2, cos, hypot, isfinite, sin
from typing import Any

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierFreshResolveResult,
  build_reflected_domain_global_frontier_pressure_target,
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
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_AUDIT_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierFreshResolveAuditStatus',
  'MocReflectedDomainGlobalFrontierFreshResolveAudit',
  'audit_reflected_domain_global_frontier_fresh_resolve',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-fresh-resolve-audit'
)


class MocReflectedDomainGlobalFrontierFreshResolveAuditStatus(str, Enum):
  """Outcome of independently checking one fresh frontier re-solve."""

  AUDITED_RESEARCH_RESOLVE = (
    'audited-research-global-frontier-fresh-resolve'
  )
  INVALID_INPUT = 'invalid_input'
  TARGET_PACKET_FAILURE = 'global-frontier-audit-target-packet-failure'
  SOURCE_LINEAGE_FAILURE = 'global-frontier-audit-source-lineage-failure'
  CANDIDATE_FAILURE = 'global-frontier-audit-candidate-failure'
  TARGET_CONSUMPTION_FAILURE = (
    'global-frontier-audit-target-consumption-failure'
  )
  TARGET_COVERAGE_FAILURE = 'global-frontier-audit-target-coverage-failure'
  TARGET_RESIDUAL_FAILURE = 'global-frontier-audit-target-residual-failure'
  TARGET_MATCH_FAILURE = 'global-frontier-audit-target-match-failure'
  PROMOTION_FLAG_FAILURE = 'global-frontier-audit-promotion-flag-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierFreshResolveAudit:
  """Independently recomputed evidence for one fresh global candidate."""

  status: MocReflectedDomainGlobalFrontierFreshResolveAuditStatus
  result: MocReflectedDomainGlobalFrontierFreshResolveResult
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  candidate_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  target_coordinate_residuals_m: tuple[float, ...] = ()
  target_tangent_residuals_rad: tuple[float, ...] = ()
  target_pressure_residuals_Pa: tuple[float, ...] = ()
  target_packet_verified: bool = False
  source_lineage_verified: bool = False
  candidate_identity_verified: bool = False
  candidate_closure_verified: bool = False
  target_consumption_verified: bool = False
  target_geometry_consumption_verified: bool = False
  target_coverage_verified: bool = False
  target_residuals_finite: bool = False
  target_match_verified: bool = False
  promotion_flags_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierFreshResolveAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveAuditStatus'
      )
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalFrontierFreshResolveResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveResult'
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
    lengths = set()
    for name in (
      'target_coordinate_residuals_m',
      'target_tangent_residuals_rad',
      'target_pressure_residuals_Pa',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      lengths.add(len(values))
      object.__setattr__(self, name, values)
    ####
    if len(lengths) != 1:
      raise ValueError('audit residual channels must have equal lengths')
    ####
    for name in (
      'target_packet_verified',
      'source_lineage_verified',
      'candidate_identity_verified',
      'candidate_closure_verified',
      'target_consumption_verified',
      'target_geometry_consumption_verified',
      'target_coverage_verified',
      'target_residuals_finite',
      'target_match_verified',
      'promotion_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.target_geometry_consumption_verified and not (
      self.target_consumption_verified
    ):
      raise ValueError(
        'target_geometry_consumption_verified requires target consumption'
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
  def audited_research_resolve(self) -> bool:
    """Whether every independently recomputed research gate passed."""

    return bool(
      self.status
      is MocReflectedDomainGlobalFrontierFreshResolveAuditStatus
      .AUDITED_RESEARCH_RESOLVE
      and self.target_packet_verified
      and self.source_lineage_verified
      and self.candidate_identity_verified
      and self.candidate_closure_verified
      and self.target_consumption_verified
      and self.target_geometry_consumption_verified
      and self.target_coverage_verified
      and self.target_residuals_finite
      and self.target_match_verified
      and self.promotion_flags_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """The independent audit never opens the production gate."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_AUDIT_OPERATOR_ID
      ),
      'status': self.status.value,
      'audited_research_resolve': self.audited_research_resolve,
      'target': None if self.target is None else self.target.as_report(),
      'candidate_closure': (
        None
        if self.candidate_closure is None
        else self.candidate_closure.as_report()
      ),
      'target_coordinate_residuals_m': self.target_coordinate_residuals_m,
      'target_tangent_residuals_rad': self.target_tangent_residuals_rad,
      'target_pressure_residuals_Pa': self.target_pressure_residuals_Pa,
      'target_packet_verified': self.target_packet_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'candidate_identity_verified': self.candidate_identity_verified,
      'candidate_closure_verified': self.candidate_closure_verified,
      'target_consumption_verified': self.target_consumption_verified,
      'target_geometry_consumption_verified': (
        self.target_geometry_consumption_verified
      ),
      'target_coverage_verified': self.target_coverage_verified,
      'target_residuals_finite': self.target_residuals_finite,
      'target_match_verified': self.target_match_verified,
      'promotion_flags_verified': self.promotion_flags_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'source_result_status': self.result.status.value,
      'message': self.message,
    }
  ####
####


def _sample_boundary(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[tuple[float, float], float, float] | None:
  """Interpolate one candidate boundary sample without extrapolation."""

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


def _measure_target(
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult,
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
]:
  coordinate_residuals: list[float] = []
  tangent_residuals: list[float] = []
  pressure_residuals: list[float] = []
  coverage = True
  for station, point, tangent, pressure in zip(
    target.x_stations_m,
    target.boundary_points_m,
    target.tangent_rad,
    target.static_pressure_Pa,
    strict=True,
  ):
    sample = _sample_boundary(
      candidate,
      station,
      position_tolerance_m=position_tolerance_m,
    )
    if sample is None:
      coverage = False
      continue
    ####
    candidate_point, candidate_tangent, candidate_pressure = sample
    coordinate_residuals.append(hypot(
      candidate_point[0] - point[0],
      candidate_point[1] - point[1],
    ))
    tangent_residuals.append(abs(atan2(
      sin(candidate_tangent - tangent),
      cos(candidate_tangent - tangent),
    )))
    pressure_residuals.append(abs(candidate_pressure - pressure))
  ####
  residuals = (
    *coordinate_residuals,
    *tangent_residuals,
    *pressure_residuals,
  )
  finite = bool(residuals) and all(isfinite(value) for value in residuals)
  complete = len(coordinate_residuals) == len(target.x_stations_m)
  match = bool(
    coverage
    and complete
    and finite
    and max(coordinate_residuals, default=float('inf'))
    <= position_tolerance_m
    and max(tangent_residuals, default=float('inf'))
    <= tangent_tolerance_rad
    and all(
      residual / max(abs(pressure), 1.0) <= pressure_tolerance_fraction
      for residual, pressure in zip(
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
    coverage and complete,
    finite,
    match,
  )
####


def _check_target_consumption(
  result: MocReflectedDomainGlobalFrontierFreshResolveResult,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
) -> tuple[bool, bool]:
  candidate = result.candidate_closure
  if candidate is None or candidate.source_band is None:
    return False, False
  ####
  consumed = candidate.source_band.ambient_pressure_target
  if consumed is None:
    return False, False
  ####
  proposal_fingerprint = (
    result.request.frontier_request.source_proposal_fingerprint
  )
  target_consumed = bool(
    candidate.source_pressure_target_consumed
    and candidate.source_pressure_target_source == consumed.source_id
    and consumed.source_closure_fingerprint
    == result.request.frontier_request.source_closure_fingerprint
    and consumed.source_proposal_fingerprint == proposal_fingerprint
    and consumed.composition_mode == 'explicit-overlay'
    and consumed.composition_overlay_source_id == target.source_id
  )
  global_euler = candidate.global_euler
  physical_field = None if global_euler is None else global_euler.physical_field
  ambient_march = (
    None if physical_field is None else physical_field.ambient_march
  )
  geometry_consumed = bool(
    target_consumed
    and ambient_march is not None
    and ambient_march.ambient_pressure_target_consumed
    and ambient_march.ambient_pressure_target_source == consumed.source_id
    and ambient_march.ambient_pressure_target_geometry_consumed
  )
  return target_consumed, geometry_consumed
####


def audit_reflected_domain_global_frontier_fresh_resolve(
  result: MocReflectedDomainGlobalFrontierFreshResolveResult,
) -> MocReflectedDomainGlobalFrontierFreshResolveAudit:
  """Recompute target lineage, consumption, and residuals independently."""

  if not isinstance(
    result,
    MocReflectedDomainGlobalFrontierFreshResolveResult,
  ):
    raise TypeError(
      'result must be a '
      'MocReflectedDomainGlobalFrontierFreshResolveResult'
    )
  ####
  request = result.request
  try:
    target = build_reflected_domain_global_frontier_pressure_target(
      request.frontier_request
    )
  except (TypeError, ValueError) as error:
    return MocReflectedDomainGlobalFrontierFreshResolveAudit(
      status=MocReflectedDomainGlobalFrontierFreshResolveAuditStatus
      .TARGET_PACKET_FAILURE,
      result=result,
      message=f'could not rebuild exact frontier target: {error}',
    )
  ####
  target_packet_verified = result.target == target
  source_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    request.closure
  )
  proposal_fingerprint = moc_reflected_domain_global_frontier_proposal_fingerprint(
    request.frontier_request.proposal
  )
  source_lineage_verified = bool(
    request.frontier_request.lineage_verified
    and source_fingerprint
    == request.frontier_request.source_closure_fingerprint
    and proposal_fingerprint == request.frontier_request.source_proposal_fingerprint
    and target.source_closure_fingerprint == source_fingerprint
    and target.source_proposal_fingerprint == proposal_fingerprint
  )
  candidate = result.candidate_closure
  candidate_fingerprint = (
    None
    if candidate is None
    else moc_reflected_domain_global_physical_closure_fingerprint(candidate)
  )
  candidate_identity_verified = bool(
    candidate is not None
    and candidate is not request.closure
    and candidate_fingerprint != source_fingerprint
  )
  candidate_closure_verified = bool(
    candidate is not None
    and candidate.converged
    and candidate.physical_closure_verified
    and candidate.downstream_boundary is not None
    and candidate.downstream_boundary.samples_available
  )
  target_consumed, geometry_consumed = _check_target_consumption(
    result,
    target,
  )
  if candidate is None:
    coordinate_residuals = ()
    tangent_residuals = ()
    pressure_residuals = ()
    coverage = False
    finite = False
    match = False
  else:
    (
      coordinate_residuals,
      tangent_residuals,
      pressure_residuals,
      coverage,
      finite,
      match,
    ) = _measure_target(
      target,
      candidate,
      position_tolerance_m=request.target_position_tolerance_m,
      tangent_tolerance_rad=request.target_tangent_tolerance_rad,
      pressure_tolerance_fraction=request.target_pressure_tolerance_fraction,
    )
  ####
  promotion_flags_verified = bool(
    not result.global_coupling_verified
    and not result.downstream_boundary_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and (
      candidate is None
      or (
        not candidate.downstream_boundary_closure_verified
        and candidate.chain_promotion_blocked
        and not candidate.production_claim_allowed
      )
    )
  )
  ####
  if not target_packet_verified:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.TARGET_PACKET_FAILURE
    message = 'result target does not match the independently rebuilt target'
  elif not source_lineage_verified:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.SOURCE_LINEAGE_FAILURE
    message = 'source closure or frontier proposal lineage failed independently'
  elif not candidate_identity_verified or not candidate_closure_verified:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.CANDIDATE_FAILURE
    message = 'candidate was not an independently identifiable verified fresh closure'
  elif not target_consumed:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.TARGET_CONSUMPTION_FAILURE
    message = 'candidate did not retain exact solver-owned target consumption'
  elif not geometry_consumed:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.TARGET_CONSUMPTION_FAILURE
    message = 'candidate did not retain exact geometry/tangent target consumption'
  elif not coverage:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.TARGET_COVERAGE_FAILURE
    message = 'candidate boundary did not cover every declared target station'
  elif not finite:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.TARGET_RESIDUAL_FAILURE
    message = 'candidate target residuals were not complete and finite'
  elif not match:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.TARGET_MATCH_FAILURE
    message = 'candidate exceeded one or more independently measured tolerances'
  elif not promotion_flags_verified:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.PROMOTION_FLAG_FAILURE
    message = 'candidate or result opened a forbidden promotion flag'
  else:
    status = MocReflectedDomainGlobalFrontierFreshResolveAuditStatus.AUDITED_RESEARCH_RESOLVE
    message = (
      'independent audit reproduced exact target lineage, solver-owned '
      'pressure/geometry consumption, finite station residuals, and research '
      'promotion blockers; canonical coupling and production remain open'
    )
  ####
  return MocReflectedDomainGlobalFrontierFreshResolveAudit(
    status=status,
    result=result,
    target=target,
    candidate_closure=candidate,
    target_coordinate_residuals_m=coordinate_residuals,
    target_tangent_residuals_rad=tangent_residuals,
    target_pressure_residuals_Pa=pressure_residuals,
    target_packet_verified=target_packet_verified,
    source_lineage_verified=source_lineage_verified,
    candidate_identity_verified=candidate_identity_verified,
    candidate_closure_verified=candidate_closure_verified,
    target_consumption_verified=target_consumed,
    target_geometry_consumption_verified=geometry_consumed,
    target_coverage_verified=coverage,
    target_residuals_finite=finite,
    target_match_verified=match,
    promotion_flags_verified=promotion_flags_verified,
    message=message,
  )
####
