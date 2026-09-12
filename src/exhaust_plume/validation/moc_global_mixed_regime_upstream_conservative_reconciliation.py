"""Research-only conservative reconciliation of the global reflected field.

The reflected global MOC solver carries a characteristic state on a fixed
shock/ambient/centerline mesh.  The downstream mixed-regime lane carries a
dimensional conservative target frame.  This operator runs the existing
front-aligned finite-volume reconciler on the exact global field and samples
the resulting conservative field at the exact target points.

This is the first explicit upstream conservative-equation consumer, but it is
still a fixed-front research lane.  The downstream target is retained and
measured; it is not imposed as an interior source or silently projected onto
an ambient boundary.  Consequently the operator cannot claim a moving
free-boundary fixed point, global mixed-regime coupling, or production
validity.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite, log
from typing import Any

from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfileRequest,
  build_moc_physical_field_continuation_profile,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerReconciliationRequest,
  MocPhysicalFieldEulerReconciliationResult,
  solve_moc_physical_field_euler_reconciliation,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionRequest,
  MocPhysicalFieldShockFrontConditionResult,
  build_moc_physical_field_shock_front_condition,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementRequest,
  build_moc_transonic_shock_interface_profile_from_field_placement,
)
from exhaust_plume.validation.moc_global_mixed_regime_state_equation_contract import (
  MocReflectedDomainGlobalMixedRegimeStateEquationContract,
)
from exhaust_plume.validation.moc_global_mixed_regime_upstream_state_target import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult,
  measure_reflected_domain_global_mixed_regime_upstream_state_target,
)
from exhaust_plume.validation.moc_physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerReconciliationAudit,
  measure_moc_physical_field_euler_reconciliation,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CONSERVATIVE_RECONCILIATION_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationResult',
  'run_reflected_domain_global_mixed_regime_upstream_conservative_reconciliation',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CONSERVATIVE_RECONCILIATION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-conservative-reconciliation-v1'
)

_STATE_COMPONENT_NAMES = (
  'density',
  'streamwise_momentum',
  'transverse_momentum',
  'total_energy',
)


class MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus(
  str,
  Enum,
):
  """Typed outcomes of one fixed-front upstream equation attempt."""

  CONVERGED_LOCAL_UPSTREAM_CONSERVATIVE_RECONCILIATION = (
    'converged-local-global-mixed-regime-upstream-conservative-reconciliation'
  )
  INVALID_INPUT = 'invalid_input'
  CONTRACT_NOT_READY = (
    'global-mixed-regime-upstream-conservative-contract-not-ready'
  )
  FRONT_CONDITION_FAILURE = (
    'global-mixed-regime-upstream-conservative-front-condition-failure'
  )
  SOLVER_FAILURE = (
    'global-mixed-regime-upstream-conservative-solver-failure'
  )
  AUDIT_FAILURE = (
    'global-mixed-regime-upstream-conservative-audit-failure'
  )
  TARGET_SAMPLE_FAILURE = (
    'global-mixed-regime-upstream-conservative-target-sample-failure'
  )
####


def _options(
  value: Mapping[str, Any] | None,
) -> dict[str, Any]:
  if value is None:
    return {}
  ####
  if not isinstance(value, Mapping):
    raise TypeError('reconciliation_options must be a mapping when supplied')
  ####
  options = dict(value)
  reserved = (
    'shock_front_condition',
    'reference_total_temperature_K',
    'gas_constant_J_kgK',
    'ambient_pressure_target',
  )
  collisions = tuple(name for name in reserved if name in options)
  if collisions:
    raise ValueError(
      'reconciliation_options cannot override solver-owned controls: '
      f'{", ".join(collisions)}'
    )
  ####
  return options
####


def _state_profile(
  values: Any,
  name: str,
) -> tuple[tuple[float, float, float, float], ...]:
  profile = tuple(
    tuple(float(component) for component in state)
    for state in values
  )
  if any(
    len(state) != 4 or any(not isfinite(value) for value in state)
    for state in profile
  ):
    raise ValueError(f'{name} must contain finite four-component states')
  ####
  return profile
####


def _points(
  values: Any,
  name: str,
) -> tuple[tuple[float, float], ...]:
  points = tuple(
    tuple(float(coordinate) for coordinate in point)
    for point in values
  )
  if any(
    len(point) != 2 or any(not isfinite(value) for value in point)
    for point in points
  ):
    raise ValueError(f'{name} must contain finite 2-D points')
  ####
  return points
####


def _build_front_condition(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> MocPhysicalFieldShockFrontConditionResult:
  global_euler = closure.global_euler
  physical = None if global_euler is None else global_euler.physical_field
  field = None if physical is None else physical.field
  if field is None or not field.physical_closure_verified:
    raise ValueError(
      'source closure retained no verified global physical field for '
      'conservative reconciliation'
    )
  ####
  placement = build_moc_transonic_shock_interface_profile_from_field_placement(
    MocTransonicShockInterfaceFieldPlacementRequest(
      field=field,
      boundary_margin_fraction=0.0,
    )
  )
  if not placement.converged:
    raise ValueError(
      f'global physical-field placement did not converge: {placement.message}'
    )
  ####
  continuation = build_moc_physical_field_continuation_profile(
    MocPhysicalFieldContinuationProfileRequest(
      field=field,
      sample_points_m=placement.sample_points_m,
    )
  )
  if not continuation.converged:
    raise ValueError(
      'global physical-field continuation did not converge: '
      f'{continuation.message}'
    )
  ####
  condition = build_moc_physical_field_shock_front_condition(
    MocPhysicalFieldShockFrontConditionRequest(
      continuation_profile=continuation,
      condition_id='solver-owned-global-mixed-regime-upstream-conservative-v1',
    )
  )
  if not condition.converged:
    raise ValueError(
      'global physical-field shock-front condition did not converge: '
      f'{condition.message}'
    )
  ####
  return condition
####


def _contains(
  point: tuple[float, float],
  polygon: tuple[tuple[float, float], ...],
  tolerance_m: float,
) -> bool:
  crosses = tuple(
    (second[0] - first[0]) * (point[1] - first[1])
    - (second[1] - first[1]) * (point[0] - first[0])
    for first, second in zip(polygon, (*polygon[1:], polygon[0]))
  )
  return bool(
    crosses
    and (
      min(crosses) >= -tolerance_m
      or max(crosses) <= tolerance_m
    )
  )
####


def _sample_reconciled_field(
  reconciliation: MocPhysicalFieldEulerReconciliationResult,
  points: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[tuple[int, ...], tuple[tuple[float, float, float, float], ...]]:
  polygons = tuple(
    tuple(tuple(float(value) for value in point) for point in polygon)
    for polygon in reconciliation.cell_vertices_by_cell_m
  )
  states = _state_profile(
    reconciliation.conservative_states_by_cell,
    'reconciliation.conservative_states_by_cell',
  )
  if len(polygons) != len(states) or not polygons:
    raise ValueError(
      'reconciliation retained no aligned conservative cell states and mesh'
    )
  ####
  indices: list[int] = []
  sampled: list[tuple[float, float, float, float]] = []
  for point in points:
    matches = tuple(
      index
      for index, polygon in enumerate(polygons)
      if _contains(point, polygon, tolerance_m)
    )
    if not matches:
      raise ValueError(
        f'reconciled global field does not cover target point {point!r}'
      )
    ####
    index = matches[0]
    indices.append(index)
    sampled.append(states[index])
  ####
  return tuple(indices), tuple(sampled)
####


def _entropy_proxy(
  state: tuple[float, float, float, float],
  gamma: float,
) -> float:
  density, momentum_x, momentum_y, total_energy = state
  if density <= 0.0:
    raise ValueError('reconciled state density must be positive')
  ####
  pressure = (gamma - 1.0) * (
    total_energy
    - 0.5 * (momentum_x * momentum_x + momentum_y * momentum_y) / density
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('reconciled state pressure must be positive')
  ####
  proxy = pressure / density**gamma
  if not isfinite(proxy) or proxy <= 0.0:
    raise ValueError('reconciled state entropy proxy must be positive')
  ####
  return proxy
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationResult:
  """Evidence from one fixed-front conservative global-field re-solve."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
  contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract | None
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  front_condition: MocPhysicalFieldShockFrontConditionResult | None = None
  reconciliation: MocPhysicalFieldEulerReconciliationResult | None = None
  audit: MocPhysicalFieldEulerReconciliationAudit | None = None
  initial_target_measurement: (
    MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult | None
  ) = None
  target_profile: tuple[tuple[float, float, float, float], ...] = ()
  target_points_m: tuple[tuple[float, float], ...] = ()
  target_entropy_proxy_profile: tuple[float, ...] = ()
  reconciled_target_cell_indices: tuple[int, ...] = ()
  reconciled_target_profile: tuple[tuple[float, float, float, float], ...] = ()
  reconciled_target_entropy_proxy_profile: tuple[float, ...] = ()
  signed_target_state_residuals: tuple[tuple[float, float, float, float], ...] = ()
  relative_target_state_residuals: tuple[tuple[float, float, float, float], ...] = ()
  signed_target_entropy_log_residuals: tuple[float, ...] = ()
  maximum_relative_target_state_residual_norm: float | None = None
  maximum_absolute_target_entropy_log_residual: float | None = None
  source_field_lineage_verified: bool = False
  target_frame_verified: bool = False
  fixed_front_solver_invoked: bool = False
  fixed_front_conservative_equation_consumed: bool = False
  independent_audit_verified: bool = False
  post_resolve_target_sampling_verified: bool = False
  upstream_state_target_consumed: bool = False
  entropy_channel_consumed: bool = False
  upstream_equation_consumed: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus,
    ):
      raise TypeError('status must be a typed upstream conservative status')
    ####
    if self.contract is not None and not isinstance(
      self.contract,
      MocReflectedDomainGlobalMixedRegimeStateEquationContract,
    ):
      raise TypeError('contract must be a typed state-equation contract or None')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
    ):
      raise TypeError('request must be a typed upstream target request or None')
    ####
    if self.source_closure is not None and not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('source_closure must be a typed global closure or None')
    ####
    if self.front_condition is not None and not isinstance(
      self.front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError('front_condition must be typed or None')
    ####
    if self.reconciliation is not None and not isinstance(
      self.reconciliation,
      MocPhysicalFieldEulerReconciliationResult,
    ):
      raise TypeError('reconciliation must be typed or None')
    ####
    if self.audit is not None and not isinstance(
      self.audit,
      MocPhysicalFieldEulerReconciliationAudit,
    ):
      raise TypeError('audit must be typed or None')
    ####
    if self.initial_target_measurement is not None and not isinstance(
      self.initial_target_measurement,
      MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetResult,
    ):
      raise TypeError('initial_target_measurement must be typed or None')
    ####
    target_profile = _state_profile(self.target_profile, 'target_profile')
    target_points = _points(self.target_points_m, 'target_points_m')
    target_entropy = tuple(float(value) for value in self.target_entropy_proxy_profile)
    if any(not isfinite(value) or value <= 0.0 for value in target_entropy):
      raise ValueError('target_entropy_proxy_profile must be finite and positive')
    ####
    reconciled_profile = _state_profile(
      self.reconciled_target_profile,
      'reconciled_target_profile',
    )
    reconciled_entropy = tuple(
      float(value) for value in self.reconciled_target_entropy_proxy_profile
    )
    if any(not isfinite(value) or value <= 0.0 for value in reconciled_entropy):
      raise ValueError(
        'reconciled_target_entropy_proxy_profile must be finite and positive'
      )
    ####
    indices = tuple(int(value) for value in self.reconciled_target_cell_indices)
    if any(value < 0 for value in indices):
      raise ValueError('reconciled_target_cell_indices must be nonnegative')
    ####
    if not (
      len(target_profile)
      == len(target_points)
      == len(target_entropy)
    ):
      raise ValueError('target state, point, and entropy profiles must align')
    ####
    if len(reconciled_profile) not in (0, len(target_profile)):
      raise ValueError('reconciled target profile must align with target profile')
    ####
    if len(reconciled_entropy) not in (0, len(target_profile)):
      raise ValueError('reconciled target entropy must align with target profile')
    ####
    if len(indices) not in (0, len(target_profile)):
      raise ValueError('reconciled target cell indices must align with target profile')
    ####
    for name in (
      'signed_target_state_residuals',
      'relative_target_state_residuals',
    ):
      residuals = tuple(
        tuple(float(value) for value in residual)
        for residual in getattr(self, name)
      )
      if any(
        len(residual) != 4 or any(not isfinite(value) for value in residual)
        for residual in residuals
      ):
        raise ValueError(f'{name} must contain finite four-component residuals')
      ####
      object.__setattr__(self, name, residuals)
    ####
    entropy_logs = tuple(float(value) for value in self.signed_target_entropy_log_residuals)
    if any(not isfinite(value) for value in entropy_logs):
      raise ValueError('signed_target_entropy_log_residuals must be finite')
    ####
    if len(entropy_logs) not in (0, len(target_profile)):
      raise ValueError('signed_target_entropy_log_residuals must align with target')
    ####
    object.__setattr__(self, 'signed_target_entropy_log_residuals', entropy_logs)
    for name in (
      'maximum_relative_target_state_residual_norm',
      'maximum_absolute_target_entropy_log_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'source_field_lineage_verified',
      'target_frame_verified',
      'fixed_front_solver_invoked',
      'fixed_front_conservative_equation_consumed',
      'independent_audit_verified',
      'post_resolve_target_sampling_verified',
      'upstream_state_target_consumed',
      'entropy_channel_consumed',
      'upstream_equation_consumed',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if (
      self.upstream_state_target_consumed
      or self.entropy_channel_consumed
      or self.upstream_equation_consumed
      or self.global_coupling_verified
      or self.canonical_free_boundary_verified
    ):
      raise ValueError(
        'fixed-front upstream reconciliation cannot claim downstream target, '
        'entropy, upstream equation, or global coupling consumption'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('fixed-front upstream reconciliation must remain blocked')
    ####
    object.__setattr__(self, 'target_profile', target_profile)
    object.__setattr__(self, 'target_points_m', target_points)
    object.__setattr__(self, 'target_entropy_proxy_profile', target_entropy)
    object.__setattr__(self, 'reconciled_target_cell_indices', indices)
    object.__setattr__(self, 'reconciled_target_profile', reconciled_profile)
    object.__setattr__(
      self,
      'reconciled_target_entropy_proxy_profile',
      reconciled_entropy,
    )
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def component_names(self) -> tuple[str, ...]:
    return _STATE_COMPONENT_NAMES
  ####

  @property
  def local_fixed_front_reconciliation_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .CONVERGED_LOCAL_UPSTREAM_CONSERVATIVE_RECONCILIATION
      and self.source_field_lineage_verified
      and self.target_frame_verified
      and self.fixed_front_solver_invoked
      and self.fixed_front_conservative_equation_consumed
      and self.independent_audit_verified
      and self.post_resolve_target_sampling_verified
      and self.reconciliation is not None
      and self.reconciliation.converged
      and self.audit is not None
      and self.audit.converged
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CONSERVATIVE_RECONCILIATION_OPERATOR_ID
      ),
      'status': self.status.value,
      'local_fixed_front_reconciliation_verified': (
        self.local_fixed_front_reconciliation_verified
      ),
      'component_names': self.component_names,
      'source_closure_fingerprint': (
        None
        if self.source_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'target_profile': self.target_profile,
      'target_points_m': self.target_points_m,
      'target_entropy_proxy_profile': self.target_entropy_proxy_profile,
      'reconciled_target_cell_indices': self.reconciled_target_cell_indices,
      'reconciled_target_profile': self.reconciled_target_profile,
      'reconciled_target_entropy_proxy_profile': (
        self.reconciled_target_entropy_proxy_profile
      ),
      'signed_target_state_residuals': self.signed_target_state_residuals,
      'relative_target_state_residuals': self.relative_target_state_residuals,
      'signed_target_entropy_log_residuals': (
        self.signed_target_entropy_log_residuals
      ),
      'maximum_relative_target_state_residual_norm': (
        self.maximum_relative_target_state_residual_norm
      ),
      'maximum_absolute_target_entropy_log_residual': (
        self.maximum_absolute_target_entropy_log_residual
      ),
      'source_field_lineage_verified': self.source_field_lineage_verified,
      'target_frame_verified': self.target_frame_verified,
      'fixed_front_solver_invoked': self.fixed_front_solver_invoked,
      'fixed_front_conservative_equation_consumed': (
        self.fixed_front_conservative_equation_consumed
      ),
      'independent_audit_verified': self.independent_audit_verified,
      'post_resolve_target_sampling_verified': (
        self.post_resolve_target_sampling_verified
      ),
      'upstream_state_target_consumed': False,
      'entropy_channel_consumed': False,
      'upstream_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'initial_target_measurement': (
        None
        if self.initial_target_measurement is None
        else self.initial_target_measurement.as_report()
      ),
      'front_condition': (
        None if self.front_condition is None else self.front_condition.as_report()
      ),
      'reconciliation': (
        None
        if self.reconciliation is None
        else self.reconciliation.as_report()
      ),
      'audit': None if self.audit is None else self.audit.as_report(),
      'claim_status': (
        'research-only-fixed-front-global-conservative-equation-consumer; '
        'the exact downstream target was measured but not imposed, moving '
        'free-boundary/global coupling and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus,
  message: str,
  *,
  contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract | None = None,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest | None = None,
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  **kwargs: Any,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationResult:
  return MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationResult(
    status=status,
    contract=contract,
    request=request,
    source_closure=source_closure,
    message=message,
    **kwargs,
  )
####


def run_reflected_domain_global_mixed_regime_upstream_conservative_reconciliation(
  contract: MocReflectedDomainGlobalMixedRegimeStateEquationContract,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
  *,
  reconciliation_options: Mapping[str, Any] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationResult:
  """Run and audit a fixed-front conservative re-solve of the global field.

  ``contract`` supplies the exact downstream target frame and its closure
  lineage.  The target remains an observation in this first upstream slice;
  only the closure-owned shock/ambient/centerline geometry and characteristic
  field seed enter the fixed-front finite-volume equations.
  """

  if not isinstance(
    contract,
    MocReflectedDomainGlobalMixedRegimeStateEquationContract,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .INVALID_INPUT,
      'contract must be a typed mixed-regime state-equation contract',
    )
  ####
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeUpstreamStateTargetRequest,
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .INVALID_INPUT,
      'request must be a typed upstream state-target request',
      contract=contract,
    )
  ####
  if not contract.state_target_ready:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .CONTRACT_NOT_READY,
      'fixed-front upstream reconciliation requires a ready exact target frame',
      contract=contract,
      request=request,
      source_closure=contract.closure,
    )
  ####
  closure = contract.closure
  if closure is None or not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .CONTRACT_NOT_READY,
      'fixed-front upstream reconciliation requires a locally verified source closure',
      contract=contract,
      request=request,
      source_closure=closure,
    )
  ####
  if contract.source_closure_fingerprint != (
    moc_reflected_domain_global_physical_closure_fingerprint(closure)
  ):
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .CONTRACT_NOT_READY,
      'state-equation contract does not retain the exact source closure fingerprint',
      contract=contract,
      request=request,
      source_closure=closure,
    )
  ####
  try:
    options = _options(reconciliation_options)
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .INVALID_INPUT,
      f'reconciliation options are invalid: {error}',
      contract=contract,
      request=request,
      source_closure=closure,
    )
  ####
  try:
    initial_measurement = (
      measure_reflected_domain_global_mixed_regime_upstream_state_target(
        contract,
        request,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .TARGET_SAMPLE_FAILURE,
      f'initial exact target measurement raised: {error}',
      contract=contract,
      request=request,
      source_closure=closure,
    )
  ####
  target_profile = _state_profile(
    contract.conservative_state_profile,
    'contract.conservative_state_profile',
  )
  target_points = _points(
    contract.conservative_state_profile_points_m,
    'contract.conservative_state_profile_points_m',
  )
  target_entropy = tuple(float(value) for value in contract.entropy_proxy_profile)
  target_frame_verified = bool(
    initial_measurement.local_research_residuals_verified
    and initial_measurement.target_frame_verified
    and initial_measurement.target_profile == target_profile
    and initial_measurement.target_points_m == target_points
    and initial_measurement.target_entropy_proxy_profile == target_entropy
  )
  if not target_frame_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .TARGET_SAMPLE_FAILURE,
      'initial exact target measurement did not pass its frame and sampling gates',
      contract=contract,
      request=request,
      source_closure=closure,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      target_frame_verified=False,
    )
  ####
  try:
    front_condition = _build_front_condition(closure)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .FRONT_CONDITION_FAILURE,
      f'exact global front condition construction failed: {error}',
      contract=contract,
      request=request,
      source_closure=closure,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=False,
      target_frame_verified=True,
    )
  ####
  source_field_lineage_verified = bool(
    front_condition.field is not None
    and closure.global_euler is not None
    and closure.global_euler.physical_field is not None
    and front_condition.field is closure.global_euler.physical_field.field
    and front_condition.converged
  )
  if not source_field_lineage_verified:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .FRONT_CONDITION_FAILURE,
      'front condition did not retain the exact closure-owned global field',
      contract=contract,
      request=request,
      source_closure=closure,
      front_condition=front_condition,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=False,
      target_frame_verified=True,
    )
  ####
  try:
    reconciliation = solve_moc_physical_field_euler_reconciliation(
      MocPhysicalFieldEulerReconciliationRequest(
        shock_front_condition=front_condition,
        reference_total_temperature_K=request.reference_total_temperature_K,
        gas_constant_J_kgK=request.gas_constant_J_kgK,
        **options,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .SOLVER_FAILURE,
      f'fixed-front conservative global solve raised: {error}',
      contract=contract,
      request=request,
      source_closure=closure,
      front_condition=front_condition,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=True,
      target_frame_verified=True,
      fixed_front_solver_invoked=True,
    )
  ####
  if not reconciliation.converged:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .SOLVER_FAILURE,
      'fixed-front conservative global solve did not converge: '
      f'{reconciliation.message}',
      contract=contract,
      request=request,
      source_closure=closure,
      front_condition=front_condition,
      reconciliation=reconciliation,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=True,
      target_frame_verified=True,
      fixed_front_solver_invoked=True,
    )
  ####
  try:
    audit = measure_moc_physical_field_euler_reconciliation(reconciliation)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .AUDIT_FAILURE,
      f'fixed-front conservative global audit raised: {error}',
      contract=contract,
      request=request,
      source_closure=closure,
      front_condition=front_condition,
      reconciliation=reconciliation,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=True,
      target_frame_verified=True,
      fixed_front_solver_invoked=True,
    )
  ####
  independent_audit_verified = bool(audit.converged)
  fixed_front_consumed = bool(
    reconciliation.converged
    and independent_audit_verified
    and audit.source_lineage_verified
    and audit.state_samples_verified
    and audit.residual_channels_recomputed
    and audit.residual_report_verified
  )
  if not fixed_front_consumed:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .AUDIT_FAILURE,
      'fixed-front conservative global solve converged, but its independent '
      f'audit did not pass: {audit.message}',
      contract=contract,
      request=request,
      source_closure=closure,
      front_condition=front_condition,
      reconciliation=reconciliation,
      audit=audit,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=True,
      target_frame_verified=True,
      fixed_front_solver_invoked=True,
      fixed_front_conservative_equation_consumed=False,
      independent_audit_verified=False,
    )
  ####
  try:
    cell_indices, reconciled_profile = _sample_reconciled_field(
      reconciliation,
      target_points,
      tolerance_m=max(request.position_tolerance_m, 1.0e-8),
    )
    reconciled_entropy = tuple(
      _entropy_proxy(state, request.target_gamma)
      for state in reconciled_profile
    )
    signed = tuple(
      tuple(actual - target for actual, target in zip(produced, target, strict=True))
      for produced, target in zip(reconciled_profile, target_profile, strict=True)
    )
    relative = tuple(
      tuple(
        residual / max(abs(target), request.residual_floor)
        for residual, target in zip(residual_row, target, strict=True)
      )
      for residual_row, target in zip(signed, target_profile, strict=True)
    )
    entropy_logs = tuple(
      log(actual / target)
      for actual, target in zip(reconciled_entropy, target_entropy, strict=True)
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .TARGET_SAMPLE_FAILURE,
      f'reconciled global field target sampling failed: {error}',
      contract=contract,
      request=request,
      source_closure=closure,
      front_condition=front_condition,
      reconciliation=reconciliation,
      audit=audit,
      initial_target_measurement=initial_measurement,
      target_profile=target_profile,
      target_points_m=target_points,
      target_entropy_proxy_profile=target_entropy,
      source_field_lineage_verified=True,
      target_frame_verified=True,
      fixed_front_solver_invoked=True,
      fixed_front_conservative_equation_consumed=True,
      independent_audit_verified=True,
    )
  ####
  maximum_relative_norm = max(
    (
      sum(value * value for value in residual) / len(_STATE_COMPONENT_NAMES)
      for residual in relative
    ),
    default=0.0,
  ) ** 0.5
  maximum_entropy = max((abs(value) for value in entropy_logs), default=0.0)
  return MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationResult(
    status=(
      MocReflectedDomainGlobalMixedRegimeUpstreamConservativeReconciliationStatus
      .CONVERGED_LOCAL_UPSTREAM_CONSERVATIVE_RECONCILIATION
    ),
    contract=contract,
    request=request,
    source_closure=closure,
    front_condition=front_condition,
    reconciliation=reconciliation,
    audit=audit,
    initial_target_measurement=initial_measurement,
    target_profile=target_profile,
    target_points_m=target_points,
    target_entropy_proxy_profile=target_entropy,
    reconciled_target_cell_indices=cell_indices,
    reconciled_target_profile=reconciled_profile,
    reconciled_target_entropy_proxy_profile=reconciled_entropy,
    signed_target_state_residuals=signed,
    relative_target_state_residuals=relative,
    signed_target_entropy_log_residuals=entropy_logs,
    maximum_relative_target_state_residual_norm=maximum_relative_norm,
    maximum_absolute_target_entropy_log_residual=maximum_entropy,
    source_field_lineage_verified=True,
    target_frame_verified=True,
    fixed_front_solver_invoked=True,
    fixed_front_conservative_equation_consumed=True,
    independent_audit_verified=True,
    post_resolve_target_sampling_verified=True,
    message=(
      'closure-owned global field was re-solved with the fixed-front '
      'conservative Euler equations and independently audited at the exact '
      'downstream target frame; the target remains an observation rather than '
      'an imposed interior or free-boundary condition, so global coupling and '
      'production promotion remain open'
    ),
  )
####
