"""Research-only consumption of an upstream state equation by the live field.

The upstream state/entropy equation produces an exact target-node frame and an
entropy-closed conservative state for each free-boundary cell column.  This
operator installs those values into a fresh coupled-Euler free-boundary solve,
then independently audits the resulting field.  The target is consumed on the
same node/cell frame; no interpolation, regridding, pressure-only fallback, or
canonical/global promotion is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryFluxMode,
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
  solve_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_state_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  audit_reflected_domain_global_mixed_regime_upstream_state_equation,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryAudit,
  measure_reflected_domain_coupled_euler_free_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_FREE_BOUNDARY_CONSUMER_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerResult',
  'run_reflected_domain_global_mixed_regime_upstream_state_equation_free_boundary_consumer',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_FREE_BOUNDARY_CONSUMER_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-state-equation-free-boundary-consumer-v1'
)
_STATE_PROFILE_SOURCE = (
  'research-global-mixed-regime-upstream-state-equation-free-boundary-state-target-v1'
)
_GEOMETRY_PROFILE_SOURCE = (
  'research-global-mixed-regime-upstream-state-equation-free-boundary-geometry-target-v1'
)


class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus(
  str,
  Enum,
):
  """Typed outcomes of the exact equation-to-field consumer seam."""

  CONVERGED_LOCAL_RESEARCH_CONSUMER = (
    'converged-local-research-upstream-state-equation-free-boundary-consumer'
  )
  COMPLETED_RESEARCH_CONSUMER_WITH_OPEN_RESIDUAL = (
    'completed-research-upstream-state-equation-free-boundary-consumer-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_LINEAGE_FAILURE = (
    'upstream-state-equation-free-boundary-consumer-source-lineage-failure'
  )
  EQUATION_CONSUMPTION_FAILURE = (
    'upstream-state-equation-free-boundary-consumer-equation-consumption-failure'
  )
  TARGET_FRAME_FAILURE = (
    'upstream-state-equation-free-boundary-consumer-target-frame-failure'
  )
  REQUEST_FAILURE = (
    'upstream-state-equation-free-boundary-consumer-request-failure'
  )
  SOLVER_FAILURE = (
    'upstream-state-equation-free-boundary-consumer-solver-failure'
  )
  INDEPENDENT_AUDIT_FAILURE = (
    'upstream-state-equation-free-boundary-consumer-independent-audit-failure'
  )
####


def _coordinate_profile_matches(
  actual: tuple[float, ...],
  expected: tuple[float, ...],
) -> bool:
  if len(actual) != len(expected):
    return False
  ####
  scale = max(1.0, *(abs(value) for value in (*actual, *expected)))
  tolerance = 1.0e-9 * scale
  return bool(
    all(
      isfinite(first)
      and isfinite(second)
      and abs(first - second) <= tolerance
      for first, second in zip(actual, expected, strict=True)
    )
  )
####


def _point_frame_matches(
  actual: tuple[tuple[float, float], ...],
  expected: tuple[tuple[float, float], ...],
) -> bool:
  if len(actual) != len(expected):
    return False
  ####
  return bool(
    _coordinate_profile_matches(
      tuple(point[0] for point in actual),
      tuple(point[0] for point in expected),
    )
    and _coordinate_profile_matches(
      tuple(point[1] for point in actual),
      tuple(point[1] for point in expected),
    )
  )
####


def _state_profile_matches(
  actual: tuple[tuple[float, float, float, float], ...],
  expected: tuple[tuple[float, float, float, float], ...],
) -> bool:
  if len(actual) != len(expected):
    return False
  ####
  return bool(
    all(
      len(first) == len(second) == 4
      and all(
        isfinite(left)
        and isfinite(right)
        and abs(left - right)
        <= 1.0e-12 * max(1.0, abs(left), abs(right))
        for left, right in zip(first, second, strict=True)
      )
      for first, second in zip(actual, expected, strict=True)
    )
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerResult:
  """Evidence from one fresh exact-target free-boundary field solve."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None
  upstream_state_equation: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None
  )
  upstream_state_equation_audit: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit | None
  ) = None
  coupled_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None = None
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None
  coupled_field_audit: MocReflectedDomainCoupledEulerFreeBoundaryAudit | None = None
  source_lineage_verified: bool = False
  equation_consumption_verified: bool = False
  equation_replay_verified: bool = False
  target_frame_verified: bool = False
  request_frame_verified: bool = False
  coupled_field_consumed: bool = False
  independent_audit_verified: bool = False
  local_research_consumer_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus,
    ):
      raise TypeError('status must be a typed free-boundary consumer status')
    ####
    for name, expected in (
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('source_downstream', MocReflectedDomainGlobalCoupledDownstreamResult),
      (
        'upstream_state_equation',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
      ),
      (
        'upstream_state_equation_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
      ),
      ('coupled_request', MocReflectedDomainCoupledEulerFreeBoundaryRequest),
      ('coupled_field', MocReflectedDomainCoupledEulerFreeBoundaryResult),
      ('coupled_field_audit', MocReflectedDomainCoupledEulerFreeBoundaryAudit),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed result')
      ####
    ####
    for name in (
      'source_lineage_verified',
      'equation_consumption_verified',
      'equation_replay_verified',
      'target_frame_verified',
      'request_frame_verified',
      'coupled_field_consumed',
      'independent_audit_verified',
      'local_research_consumer_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('free-boundary consumer cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('free-boundary consumer must remain promotion-blocked')
    ####
    if self.local_research_consumer_verified and not (
      self.source_lineage_verified
      and self.equation_consumption_verified
      and self.equation_replay_verified
      and self.target_frame_verified
      and self.request_frame_verified
      and self.coupled_field_consumed
      and self.independent_audit_verified
    ):
      raise ValueError('verified consumer must pass every retained consumer gate')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.source_closure is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus
      .CONVERGED_LOCAL_RESEARCH_CONSUMER
      and self.local_research_consumer_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_STATE_EQUATION_FREE_BOUNDARY_CONSUMER_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_lineage_verified': self.source_lineage_verified,
      'equation_consumption_verified': self.equation_consumption_verified,
      'equation_replay_verified': self.equation_replay_verified,
      'target_frame_verified': self.target_frame_verified,
      'request_frame_verified': self.request_frame_verified,
      'coupled_field_consumed': self.coupled_field_consumed,
      'independent_audit_verified': self.independent_audit_verified,
      'local_research_consumer_verified': self.local_research_consumer_verified,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'upstream_state_equation': (
        None
        if self.upstream_state_equation is None
        else self.upstream_state_equation.as_report()
      ),
      'upstream_state_equation_audit': (
        None
        if self.upstream_state_equation_audit is None
        else self.upstream_state_equation_audit.as_report()
      ),
      'coupled_request': (
        None
        if self.coupled_request is None
        else self.coupled_request.as_report()
      ),
      'coupled_field': (
        None
        if self.coupled_field is None
        else self.coupled_field.as_report()
      ),
      'coupled_field_audit': (
        None
        if self.coupled_field_audit is None
        else self.coupled_field_audit.as_report()
      ),
      'claim_status': (
        'research-only exact upstream state/entropy target consumption by a '
        'local coupled free-boundary field; canonical global closure, external '
        'validation, and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus,
  message: str,
  *,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  source_downstream: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  upstream_state_equation: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult | None
  ) = None,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerResult:
  return MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerResult(
    status=status,
    source_closure=source_closure,
    source_downstream=source_downstream,
    upstream_state_equation=upstream_state_equation,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_mixed_regime_upstream_state_equation_free_boundary_consumer(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  downstream: MocReflectedDomainGlobalCoupledDownstreamResult,
  upstream_state_equation: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerResult:
  """Consume one exact upstream equation target in a fresh field solve."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationFreeBoundaryConsumerStatus
  )
  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    return _result(status_type.INVALID_INPUT, 'closure must be a typed global physical closure')
  ####
  if not isinstance(downstream, MocReflectedDomainGlobalCoupledDownstreamResult):
    return _result(
      status_type.INVALID_INPUT,
      'downstream must be a typed global coupled-downstream result',
      source_closure=closure,
    )
  ####
  if not isinstance(
    upstream_state_equation,
    MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  ):
    return _result(
      status_type.INVALID_INPUT,
      'upstream_state_equation must be a typed upstream state-equation result',
      source_closure=closure,
      source_downstream=downstream,
    )
  ####
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  source_lineage_verified = bool(
    closure.converged
    and closure.physical_closure_verified
    and downstream.closure is closure
    and downstream.closure_lineage_verified
    and downstream.source_closure_fingerprint == fingerprint
    and downstream.coupled_request is not None
    and downstream.coupled_field is not None
    and downstream.coupled_field.request is downstream.coupled_request
    and downstream.coupled_request.mixed_regime_request.closure is closure
  )
  if not source_lineage_verified:
    return _result(
      status_type.SOURCE_LINEAGE_FAILURE,
      'source downstream result did not retain the exact verified closure and '
      'coupled-field identity',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
    )
  ####
  equation_audit: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit
  try:
    equation_audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
      upstream_state_equation
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      status_type.EQUATION_CONSUMPTION_FAILURE,
      f'upstream state-equation audit raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
    )
  ####
  equation_consumption_verified = bool(
    upstream_state_equation.research_state_equation_consumed
  )
  equation_replay_verified = bool(equation_audit.converged)
  if not equation_consumption_verified or not equation_replay_verified:
    return _result(
      status_type.EQUATION_CONSUMPTION_FAILURE,
      'upstream state-equation target was not both consumed and independently '
      'replayed before the free-boundary solve',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
    )
  ####
  base_request = downstream.coupled_request
  base_field = downstream.coupled_field
  assert base_request is not None
  assert base_field is not None
  target_request = upstream_state_equation.request
  if target_request is None:
    return _result(
      status_type.EQUATION_CONSUMPTION_FAILURE,
      'upstream state-equation result did not retain its typed request',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
    )
  ####
  target_points = tuple(target_request.target_points_m)
  target_states = tuple(upstream_state_equation.entropy_closed_target_profile)
  target_profile_x = tuple(
    0.5 * (first[0] + second[0])
    for first, second in zip(target_points, target_points[1:])
  )
  target_frame_verified = bool(
    len(target_points) == base_request.axial_cell_count + 1
    and len(target_states) == base_request.axial_cell_count
    and _point_frame_matches(
      tuple(base_field.free_boundary_points_m),
      target_points,
    )
  )
  if not target_frame_verified:
    return _result(
      status_type.TARGET_FRAME_FAILURE,
      'upstream state-equation target nodes do not cover the existing coupled '
      'free-boundary frame exactly; no regridding was attempted',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
      target_frame_verified=False,
    )
  ####
  if base_request.inlet_boundary_mode is not (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ) or base_request.free_boundary_update_mode is not (
    MocReflectedDomainCoupledEulerFreeBoundaryUpdateMode.PRESSURE_SLOPE_RESEARCH
  ):
    return _result(
      status_type.REQUEST_FAILURE,
      'the exact upstream state-equation consumer currently requires the '
      'full-state inlet and pressure-slope research update modes',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
      target_frame_verified=True,
    )
  ####
  geometry_x = tuple(point[0] for point in target_points)
  geometry_y = tuple(point[1] for point in target_points)
  control_lower = float(base_request.mixed_regime_request.control_section.points_m[0][1])
  try:
    coupled_request = replace(
      base_request,
      free_boundary_pressure_profile_Pa=None,
      free_boundary_pressure_profile_x_stations_m=None,
      free_boundary_pressure_profile_source=None,
      entropy_closure_profile=None,
      free_boundary_geometry_profile_y_m=geometry_y,
      free_boundary_geometry_profile_x_stations_m=geometry_x,
      free_boundary_geometry_profile_source=_GEOMETRY_PROFILE_SOURCE,
      free_boundary_geometry_profile_lower_ordinate_m=control_lower,
      free_boundary_flux_mode=(
        MocReflectedDomainCoupledEulerFreeBoundaryFluxMode
        .CONSERVATIVE_STATE_TRACE_ENTROPY_COMPATIBLE_RUSANOV
      ),
      free_boundary_conservative_state_profile=target_states,
      free_boundary_conservative_state_profile_x_stations_m=target_profile_x,
      free_boundary_conservative_state_profile_source=_STATE_PROFILE_SOURCE,
      free_boundary_conservative_flux_profile=None,
      free_boundary_conservative_flux_profile_source=None,
      upstream_state_equation=upstream_state_equation,
      source=(
        'research-global-mixed-regime-upstream-state-equation-'
        'free-boundary-consumer-v1'
      ),
    )
  except (TypeError, ValueError) as error:
    return _result(
      status_type.REQUEST_FAILURE,
      f'fresh upstream state-equation free-boundary request failed: {error}',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
      target_frame_verified=True,
    )
  ####
  request_frame_verified = bool(
    coupled_request.mixed_regime_request is base_request.mixed_regime_request
    and _coordinate_profile_matches(
      tuple(coupled_request.free_boundary_geometry_profile_y_m or ()),
      geometry_y,
    )
    and _coordinate_profile_matches(
      tuple(coupled_request.free_boundary_geometry_profile_x_stations_m or ()),
      geometry_x,
    )
    and _state_profile_matches(
      tuple(coupled_request.free_boundary_conservative_state_profile or ()),
      target_states,
    )
    and _coordinate_profile_matches(
      tuple(
        coupled_request.free_boundary_conservative_state_profile_x_stations_m
        or ()
      ),
      target_profile_x,
    )
    and coupled_request.upstream_state_equation is upstream_state_equation
  )
  if not request_frame_verified:
    return _result(
      status_type.REQUEST_FAILURE,
      'fresh request did not retain the exact upstream target frame and '
      'state-equation identity',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      coupled_request=coupled_request,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
      target_frame_verified=True,
      request_frame_verified=False,
    )
  ####
  try:
    coupled_field = solve_reflected_domain_coupled_euler_free_boundary(
      coupled_request
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return _result(
      status_type.SOLVER_FAILURE,
      f'fresh upstream state-equation free-boundary solve raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      coupled_request=coupled_request,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
      target_frame_verified=True,
      request_frame_verified=True,
    )
  ####
  try:
    coupled_field_audit = measure_reflected_domain_coupled_euler_free_boundary(
      coupled_field
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return _result(
      status_type.INDEPENDENT_AUDIT_FAILURE,
      f'fresh upstream state-equation free-boundary audit raised: {error}',
      source_closure=closure,
      source_downstream=downstream,
      upstream_state_equation=upstream_state_equation,
      upstream_state_equation_audit=equation_audit,
      coupled_request=coupled_request,
      coupled_field=coupled_field,
      source_lineage_verified=source_lineage_verified,
      equation_consumption_verified=equation_consumption_verified,
      equation_replay_verified=equation_replay_verified,
      target_frame_verified=True,
      request_frame_verified=True,
    )
  ####
  coupled_field_consumed = bool(
    coupled_field.request is coupled_request
    and coupled_field.upstream_state_equation_consumed
    and coupled_field.upstream_state_equation_target_frame_verified
  )
  independent_audit_verified = bool(
    coupled_field_audit.candidate is coupled_field
    and coupled_field_audit.converged
    and coupled_field_audit.local_consistency_verified
  )
  local_research_consumer_verified = bool(
    source_lineage_verified
    and equation_consumption_verified
    and equation_replay_verified
    and target_frame_verified
    and request_frame_verified
    and coupled_field_consumed
    and independent_audit_verified
    and coupled_field.converged
  )
  common = dict(
    source_closure=closure,
    source_downstream=downstream,
    upstream_state_equation=upstream_state_equation,
    upstream_state_equation_audit=equation_audit,
    coupled_request=coupled_request,
    coupled_field=coupled_field,
    coupled_field_audit=coupled_field_audit,
    source_lineage_verified=source_lineage_verified,
    equation_consumption_verified=equation_consumption_verified,
    equation_replay_verified=equation_replay_verified,
    target_frame_verified=target_frame_verified,
    request_frame_verified=request_frame_verified,
    coupled_field_consumed=coupled_field_consumed,
    independent_audit_verified=independent_audit_verified,
    local_research_consumer_verified=local_research_consumer_verified,
  )
  if local_research_consumer_verified:
    return _result(
      status_type.CONVERGED_LOCAL_RESEARCH_CONSUMER,
      'the exact upstream state/entropy target was consumed by a fresh live '
      'free-boundary field on the same node/cell frame and independently '
      'audited; canonical/global and production gates remain closed',
      **common,
    )
  ####
  return _result(
    status_type.COMPLETED_RESEARCH_CONSUMER_WITH_OPEN_RESIDUAL,
    'the exact upstream state/entropy target was installed and retained by a '
    'fresh free-boundary solve, but local convergence or the independent '
    'field audit remains open; no canonical/global claim is made',
    **common,
  )
####
