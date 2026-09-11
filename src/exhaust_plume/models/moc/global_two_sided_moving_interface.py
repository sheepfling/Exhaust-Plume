"""Global-closure adapter for the exact two-sided moving-interface ladder.

The global reflected closure owns the source band and the locally verified
Euler shock curve.  This module binds those exact objects to the existing
two-sided field, solver-owned Rankine--Hugoniot response, and exact field
re-solve operators.  It is a research lane: a locally converged response is
useful evidence, but it does not close the canonical downstream free boundary
or authorize shock-cell-chain or production promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerCompanionFieldResult,
  MocEulerAmbientCompanionBoundaryResult,
  assemble_euler_consistent_companion_characteristic_strip,
  solve_euler_ambient_companion_boundary_reference,
)
from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationRequest,
)
from exhaust_plume.models.moc.euler_two_sided_interface_law import (
  MocEulerTwoSidedInterfaceLawRequest,
  solve_euler_two_sided_moving_interface_with_solver_owned_law,
)
from exhaust_plume.models.moc.euler_two_sided_conservative_residual_solve import (
  MocEulerTwoSidedConservativeResidualSolveRequest,
  MocEulerTwoSidedConservativeResidualSolveResult,
  solve_euler_two_sided_conservative_residual,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedMovingInterfaceRequest,
  MocEulerTwoSidedMovingInterfaceResult,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID',
  'MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus',
  'MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest',
  'MocReflectedDomainGlobalTwoSidedMovingInterfaceResult',
  'solve_reflected_domain_global_two_sided_moving_interface',
  'solve_reflected_domain_global_two_sided_stationary_interface',
)


MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID = (
  'op.moc.global-two-sided-moving-interface-adapter-v1'
)
DEFAULT_GAS_CONSTANT_J_KGK = 287.05


class MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus(str, Enum):
  """Outcome of binding a global closure to the moving-interface ladder."""

  CONVERGED_RESEARCH_INTERFACE = (
    'converged-global-two-sided-research-moving-interface'
  )
  INVALID_INPUT = 'invalid_input'
  GLOBAL_CLOSURE_REQUIRED = 'global-two-sided-global-closure-required'
  SHOCK_BOUNDARY_REQUIRED = 'global-two-sided-shock-boundary-required'
  COMPANION_BOUNDARY_FAILURE = 'global-two-sided-companion-boundary-failure'
  COMPANION_FIELD_FAILURE = 'global-two-sided-companion-field-failure'
  MOVING_INTERFACE_FAILURE = 'global-two-sided-moving-interface-failure'
  INDEPENDENT_AUDIT_FAILURE = 'global-two-sided-independent-audit-failure'


def _positive_float(value: object, name: str) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _bounded_fraction(value: object, name: str, *, allow_zero: bool = False) -> float:
  numeric = float(value)
  lower = 0.0 if allow_zero else 1.0e-15
  if not isfinite(numeric) or numeric < lower or numeric > 1.0:
    lower_text = 'nonnegative' if allow_zero else 'positive'
    raise ValueError(f'{name} must be finite, {lower_text}, and no greater than one')
  ####
  return numeric
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest:
  """Configuration for one exact global-to-moving-interface handoff."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  reference_total_temperature_K: float
  gas_constant_J_kgK: float = DEFAULT_GAS_CONSTANT_J_KGK
  companion_separation_m: float = 0.5
  companion_seed_flow_angle_rad: float = 0.0
  target_centerline_y_m: float | None = None
  position_tolerance_m: float = 1.0e-8
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance: float = 1.0e-8
  handoff_position_tolerance_m: float = 1.0e-8
  handoff_state_tolerance: float = 1.0e-8
  handoff_pressure_tolerance_Pa: float = 1.0e-8
  source_trace_position_tolerance_m: float = 1.0e-3
  source_trace_forward_tolerance_m: float = 1.0e-3
  maximum_field_iterations: int = 3
  maximum_boundary_iterations: int = 16
  maximum_interface_iterations: int = 3
  pseudo_time_step_s: float = 1.0e-8
  relaxation: float = 0.5
  maximum_normal_displacement_m: float = 1.0e-3
  downstream_probe_fraction: float = 0.01
  anchor_endpoint_samples: int = 2
  branch: ShockBranch = ShockBranch.WEAK
  mass_flux_tolerance_kg_m2_s: float = 1.0e-3
  # Interior downstream probes are intentionally research-only.  The
  # conservative consumer must opt in and provide a tighter accepted budget.
  normal_momentum_tolerance_Pa: float = 100.0
  energy_flux_tolerance_W_m2: float = 1.0e-1
  require_interface_motion: bool = True
  allow_stationary_equilibrium: bool = False
  require_conservative_flux_closure: bool = False
  require_terminal_fixed_point: bool = False
  use_conservative_residual_line_search: bool = False
  maximum_residual_backtracks: int = 5
  residual_backtrack_factor: float = 0.5
  minimum_residual_step_fraction: float = 1.0e-2
  minimum_residual_descent_fraction: float = 1.0e-6
  require_strict_residual_descent: bool = True
  use_conservative_residual_directional_correction: bool = True
  residual_jacobian_probe_fraction: float = 0.5
  maximum_residual_directional_step_fraction: float = 1.0
  source: str = 'solver-owned-global-two-sided-moving-interface-request-v1'

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    ####
    for name in (
      'reference_total_temperature_K',
      'gas_constant_J_kgK',
      'companion_separation_m',
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
      'handoff_position_tolerance_m',
      'handoff_state_tolerance',
      'handoff_pressure_tolerance_Pa',
      'source_trace_position_tolerance_m',
      'source_trace_forward_tolerance_m',
      'pseudo_time_step_s',
      'maximum_normal_displacement_m',
      'mass_flux_tolerance_kg_m2_s',
      'normal_momentum_tolerance_Pa',
      'energy_flux_tolerance_W_m2',
    ):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    if (
      isinstance(self.maximum_residual_backtracks, bool)
      or not isinstance(self.maximum_residual_backtracks, int)
      or self.maximum_residual_backtracks < 1
    ):
      raise ValueError('maximum_residual_backtracks must be a positive integer')
    ####
    for name in (
      'residual_backtrack_factor',
      'minimum_residual_step_fraction',
      'minimum_residual_descent_fraction',
      'residual_jacobian_probe_fraction',
      'maximum_residual_directional_step_fraction',
    ):
      value = _bounded_fraction(getattr(self, name), name)
      if name == 'residual_backtrack_factor' and value >= 1.0:
        raise ValueError('residual_backtrack_factor must be less than one')
      ####
      object.__setattr__(self, name, value)
    ####
    seed_angle = float(self.companion_seed_flow_angle_rad)
    if not isfinite(seed_angle):
      raise ValueError('companion_seed_flow_angle_rad must be finite')
    ####
    object.__setattr__(self, 'companion_seed_flow_angle_rad', seed_angle)
    target_y = self.target_centerline_y_m
    if target_y is not None:
      target_y = float(target_y)
      if not isfinite(target_y):
        raise ValueError('target_centerline_y_m must be finite when supplied')
      ####
      object.__setattr__(self, 'target_centerline_y_m', target_y)
    ####
    object.__setattr__(
      self,
      'relaxation',
      _bounded_fraction(self.relaxation, 'relaxation'),
    )
    object.__setattr__(
      self,
      'downstream_probe_fraction',
      _bounded_fraction(
        self.downstream_probe_fraction,
        'downstream_probe_fraction',
        allow_zero=True,
      ),
    )
    ####
    for name, minimum in (
      ('maximum_field_iterations', 1),
      ('maximum_boundary_iterations', 1),
      ('maximum_interface_iterations', 1),
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'{name} must be an integer greater than or equal to {minimum}')
    ####
    if (
      isinstance(self.anchor_endpoint_samples, bool)
      or not isinstance(self.anchor_endpoint_samples, int)
      or self.anchor_endpoint_samples < 1
    ):
      raise ValueError('anchor_endpoint_samples must be a positive integer')
    ####
    for name in (
      'require_interface_motion',
      'allow_stationary_equilibrium',
      'require_conservative_flux_closure',
      'require_terminal_fixed_point',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if not isinstance(self.use_conservative_residual_line_search, bool):
      raise TypeError('use_conservative_residual_line_search must be a bool')
    if not isinstance(self.require_strict_residual_descent, bool):
      raise TypeError('require_strict_residual_descent must be a bool')
    if not isinstance(
      self.use_conservative_residual_directional_correction,
      bool,
    ):
      raise TypeError(
        'use_conservative_residual_directional_correction must be a bool'
      )
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID,
      'closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.closure
      ),
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'companion_separation_m': self.companion_separation_m,
      'companion_seed_flow_angle_rad': self.companion_seed_flow_angle_rad,
      'target_centerline_y_m': self.target_centerline_y_m,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'handoff_position_tolerance_m': self.handoff_position_tolerance_m,
      'handoff_state_tolerance': self.handoff_state_tolerance,
      'handoff_pressure_tolerance_Pa': self.handoff_pressure_tolerance_Pa,
      'source_trace_position_tolerance_m': self.source_trace_position_tolerance_m,
      'source_trace_forward_tolerance_m': self.source_trace_forward_tolerance_m,
      'maximum_field_iterations': self.maximum_field_iterations,
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'maximum_interface_iterations': self.maximum_interface_iterations,
      'pseudo_time_step_s': self.pseudo_time_step_s,
      'relaxation': self.relaxation,
      'maximum_normal_displacement_m': self.maximum_normal_displacement_m,
      'downstream_probe_fraction': self.downstream_probe_fraction,
      'anchor_endpoint_samples': self.anchor_endpoint_samples,
      'branch': self.branch.value,
      'mass_flux_tolerance_kg_m2_s': self.mass_flux_tolerance_kg_m2_s,
      'normal_momentum_tolerance_Pa': self.normal_momentum_tolerance_Pa,
      'energy_flux_tolerance_W_m2': self.energy_flux_tolerance_W_m2,
      'require_interface_motion': self.require_interface_motion,
      'allow_stationary_equilibrium': self.allow_stationary_equilibrium,
      'require_conservative_flux_closure': self.require_conservative_flux_closure,
      'require_terminal_fixed_point': self.require_terminal_fixed_point,
      'use_conservative_residual_line_search': (
        self.use_conservative_residual_line_search
      ),
      'maximum_residual_backtracks': self.maximum_residual_backtracks,
      'residual_backtrack_factor': self.residual_backtrack_factor,
      'minimum_residual_step_fraction': self.minimum_residual_step_fraction,
      'minimum_residual_descent_fraction': (
        self.minimum_residual_descent_fraction
      ),
      'require_strict_residual_descent': self.require_strict_residual_descent,
      'use_conservative_residual_directional_correction': (
        self.use_conservative_residual_directional_correction
      ),
      'residual_jacobian_probe_fraction': self.residual_jacobian_probe_fraction,
      'maximum_residual_directional_step_fraction': (
        self.maximum_residual_directional_step_fraction
      ),
      'source': self.source,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTwoSidedMovingInterfaceResult:
  """Audited global-to-moving-interface research result."""

  status: MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None
  companion_boundary: MocEulerAmbientCompanionBoundaryResult | None = None
  companion_field: MocEulerCompanionFieldResult | None = None
  moving_result: MocEulerTwoSidedMovingInterfaceResult | None = None
  conservative_residual_result: (
    MocEulerTwoSidedConservativeResidualSolveResult | None
  ) = None
  conservative_residual_audit: Any | None = None
  moving_audit: Any | None = None
  joint_audit: Any | None = None
  moving_fixed_point_audit: Any | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus,
    ):
      raise TypeError('status must be a global two-sided moving-interface status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
    ):
      raise TypeError('request must be a typed global two-sided request or None')
    ####
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError('shock_boundary must be a typed Euler shock boundary or None')
    ####
    if self.companion_boundary is not None and not isinstance(
      self.companion_boundary,
      MocEulerAmbientCompanionBoundaryResult,
    ):
      raise TypeError(
        'companion_boundary must be a typed Euler companion boundary or None'
      )
    ####
    if self.companion_field is not None and not isinstance(
      self.companion_field,
      MocEulerCompanionFieldResult,
    ):
      raise TypeError('companion_field must be a typed Euler companion field or None')
    ####
    if self.moving_result is not None and not isinstance(
      self.moving_result,
      MocEulerTwoSidedMovingInterfaceResult,
    ):
      raise TypeError('moving_result must be a typed moving-interface result or None')
    ####
    if self.conservative_residual_result is not None and not isinstance(
      self.conservative_residual_result,
      MocEulerTwoSidedConservativeResidualSolveResult,
    ):
      raise TypeError(
        'conservative_residual_result must be a typed residual-solve result '
        'or None'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.request is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.request.closure
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus
      .CONVERGED_RESEARCH_INTERFACE
      and (
        (
          self.moving_result is not None
          and self.moving_result.converged
          and self.moving_audit is not None
          and bool(getattr(self.moving_audit, 'converged', False))
          and self.joint_audit is not None
          and bool(getattr(self.joint_audit, 'converged', False))
        )
        or (
          self.conservative_residual_result is not None
          and self.conservative_residual_result.converged
          and self.conservative_residual_audit is not None
          and bool(getattr(self.conservative_residual_audit, 'converged', False))
        )
      )
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_GLOBAL_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'shock_boundary': (
        None if self.shock_boundary is None else self.shock_boundary.as_report()
      ),
      'companion_boundary': (
        None
        if self.companion_boundary is None
        else self.companion_boundary.as_report()
      ),
      'companion_field': (
        None
        if self.companion_field is None
        else self.companion_field.as_report()
      ),
      'moving_result': (
        None if self.moving_result is None else self.moving_result.as_report()
      ),
      'conservative_residual_result': (
        None
        if self.conservative_residual_result is None
        else self.conservative_residual_result.as_report()
      ),
      'conservative_residual_audit': (
        None
        if (
          self.conservative_residual_audit is None
          or not hasattr(self.conservative_residual_audit, 'as_report')
        )
        else self.conservative_residual_audit.as_report()
      ),
      'moving_audit': (
        None
        if self.moving_audit is None or not hasattr(self.moving_audit, 'as_report')
        else self.moving_audit.as_report()
      ),
      'joint_audit': (
        None
        if self.joint_audit is None or not hasattr(self.joint_audit, 'as_report')
        else self.joint_audit.as_report()
      ),
      'moving_fixed_point_audit': (
        None
        if (
          self.moving_fixed_point_audit is None
          or not hasattr(self.moving_fixed_point_audit, 'as_report')
        )
        else self.moving_fixed_point_audit.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only global-to-two-sided moving-interface evidence; canonical '
        'free-boundary closure, refinement, physical shock-cell acceptance, and '
        'external validation remain open'
      ),
      'message': self.message,
    }
  ####


def _failure(
  status: MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus,
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest | None,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainGlobalTwoSidedMovingInterfaceResult:
  return MocReflectedDomainGlobalTwoSidedMovingInterfaceResult(
    status=status,
    request=request,
    message=message,
    **kwargs,
  )
####


def solve_reflected_domain_global_two_sided_moving_interface(
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
) -> MocReflectedDomainGlobalTwoSidedMovingInterfaceResult:
  """Run the exact two-sided ladder from one verified global closure.

  The source band, shock curve, companion strip, and downstream physical field
  remain exact object-identity handoffs.  A failure in any required stage is
  returned as a typed failure; no scalar normal-shock, compression-envelope,
  interpolation, or endpoint-hold fallback is attempted.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  ):
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      None,
      'request must be a typed global two-sided moving-interface request',
    )
  ####
  closure = request.closure
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.GLOBAL_CLOSURE_REQUIRED,
      request,
      'global two-sided moving-interface solving requires a locally verified '
      'global physical closure; no lower-fidelity fallback was attempted',
    )
  ####
  source_band = closure.source_band
  global_euler = closure.global_euler
  if source_band is None or not source_band.source_field_verified:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.GLOBAL_CLOSURE_REQUIRED,
      request,
      'global closure did not retain an independently verified source band',
    )
  ####
  shock_boundary = None if global_euler is None else global_euler.shock_boundary
  if shock_boundary is None or not (
    shock_boundary.converged and shock_boundary.local_euler_verified
  ):
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.SHOCK_BOUNDARY_REQUIRED,
      request,
      'global closure did not retain a locally Euler-verified shock boundary',
    )
  ####
  ambient_pressure = source_band.ambient_pressure_Pa
  if ambient_pressure is None:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.GLOBAL_CLOSURE_REQUIRED,
      request,
      'global source band did not retain ambient pressure for the companion '
      'boundary; no pressure target was inferred',
      shock_boundary=shock_boundary,
    )
  ####
  try:
    companion_boundary = solve_euler_ambient_companion_boundary_reference(
      shock_boundary,
      ambient_pressure,
      separation_m=request.companion_separation_m,
      seed_flow_angle_rad=request.companion_seed_flow_angle_rad,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
      pressure_tolerance=request.pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.COMPANION_BOUNDARY_FAILURE,
      request,
      f'global two-sided companion boundary solve raised: {error}',
      shock_boundary=shock_boundary,
    )
  ####
  if not companion_boundary.converged:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.COMPANION_BOUNDARY_FAILURE,
      request,
      'global two-sided companion boundary did not converge: '
      f'{companion_boundary.message}',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
    )
  ####
  try:
    companion_field = assemble_euler_consistent_companion_characteristic_strip(
      shock_boundary,
      companion_boundary.samples,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
      pressure_tolerance=request.pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.COMPANION_FIELD_FAILURE,
      request,
      f'global two-sided companion field assembly raised: {error}',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
    )
  ####
  if not companion_field.converged or not companion_field.state_sampling_available:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.COMPANION_FIELD_FAILURE,
      request,
      'global two-sided companion field did not retain a verified state '
      f'handoff: {companion_field.message}',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
      companion_field=companion_field,
    )
  ####
  target_centerline_y = (
    source_band.target_centerline_y_m
    if request.target_centerline_y_m is None
    else request.target_centerline_y_m
  )
  try:
    field_request = MocEulerTwoSidedFieldIterationRequest(
      shock_boundary=shock_boundary,
      companion_field=companion_field,
      ambient_pressure_Pa=ambient_pressure,
      target_centerline_y_m=target_centerline_y,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.invariant_tolerance,
      pressure_tolerance=request.pressure_tolerance,
      tangent_tolerance=request.tangent_tolerance,
      handoff_position_tolerance_m=request.handoff_position_tolerance_m,
      handoff_state_tolerance=request.handoff_state_tolerance,
      handoff_pressure_tolerance_Pa=request.handoff_pressure_tolerance_Pa,
      source_trace_position_tolerance_m=request.source_trace_position_tolerance_m,
      source_trace_forward_tolerance_m=request.source_trace_forward_tolerance_m,
      maximum_field_iterations=request.maximum_field_iterations,
      maximum_boundary_iterations=request.maximum_boundary_iterations,
    )
    law_request = MocEulerTwoSidedInterfaceLawRequest(
      source_band=source_band,
      reference_total_temperature_K=request.reference_total_temperature_K,
      gas_constant_J_kgK=request.gas_constant_J_kgK,
      pseudo_time_step_s=request.pseudo_time_step_s,
      relaxation=request.relaxation,
      maximum_normal_displacement_m=request.maximum_normal_displacement_m,
      downstream_probe_fraction=request.downstream_probe_fraction,
      companion_separation_m=request.companion_separation_m,
      companion_seed_flow_angle_rad=request.companion_seed_flow_angle_rad,
      anchor_endpoint_samples=request.anchor_endpoint_samples,
      branch=request.branch,
      position_tolerance_m=request.position_tolerance_m,
      source_state_tolerance=request.handoff_state_tolerance,
      source_pressure_tolerance=request.handoff_pressure_tolerance_Pa,
      residual_tolerance=request.pressure_tolerance,
      require_conservative_flux_closure=request.require_conservative_flux_closure,
      mass_flux_tolerance_kg_m2_s=request.mass_flux_tolerance_kg_m2_s,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
      energy_flux_tolerance_W_m2=request.energy_flux_tolerance_W_m2,
    )
    moving_request = MocEulerTwoSidedMovingInterfaceRequest(
      field_request=field_request,
      maximum_interface_iterations=request.maximum_interface_iterations,
      position_tolerance_m=request.position_tolerance_m,
      mass_flux_tolerance_kg_m2_s=request.mass_flux_tolerance_kg_m2_s,
      normal_momentum_tolerance_Pa=request.normal_momentum_tolerance_Pa,
      energy_flux_tolerance_W_m2=request.energy_flux_tolerance_W_m2,
      require_interface_motion=request.require_interface_motion,
      allow_stationary_equilibrium=request.allow_stationary_equilibrium,
      require_conservative_flux_closure=request.require_conservative_flux_closure,
      require_terminal_fixed_point=request.require_terminal_fixed_point,
    )
    moving_result: MocEulerTwoSidedMovingInterfaceResult | None = None
    conservative_residual_result: (
      MocEulerTwoSidedConservativeResidualSolveResult | None
    ) = None
    if request.use_conservative_residual_line_search:
      conservative_residual_result = solve_euler_two_sided_conservative_residual(
        MocEulerTwoSidedConservativeResidualSolveRequest(
          moving_request=moving_request,
          law_request=law_request,
          maximum_iterations=request.maximum_interface_iterations,
          maximum_backtracks=request.maximum_residual_backtracks,
          backtrack_factor=request.residual_backtrack_factor,
          minimum_step_fraction=request.minimum_residual_step_fraction,
          minimum_descent_fraction=request.minimum_residual_descent_fraction,
          require_strict_descent=request.require_strict_residual_descent,
          use_directional_residual_correction=(
            request.use_conservative_residual_directional_correction
          ),
          jacobian_probe_fraction=request.residual_jacobian_probe_fraction,
          maximum_directional_step_fraction=(
            request.maximum_residual_directional_step_fraction
          ),
        )
      )
    else:
      moving_result = solve_euler_two_sided_moving_interface_with_solver_owned_law(
        moving_request,
        law_request,
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.MOVING_INTERFACE_FAILURE,
      request,
      f'global two-sided moving-interface solve raised: {error}',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
      companion_field=companion_field,
    )
  ####
  if request.use_conservative_residual_line_search:
    assert conservative_residual_result is not None
    try:
      from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
        measure_moc_euler_two_sided_conservative_residual,
      )

      conservative_residual_audit = (
        measure_moc_euler_two_sided_conservative_residual(
          conservative_residual_result
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
        request,
        f'global conservative residual independent audit raised: {error}',
        shock_boundary=shock_boundary,
        companion_boundary=companion_boundary,
        companion_field=companion_field,
        conservative_residual_result=conservative_residual_result,
      )
    ####
    if not conservative_residual_result.converged:
      return _failure(
        MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.MOVING_INTERFACE_FAILURE,
        request,
        'global two-sided conservative residual line-search retained a typed '
        f'non-converged result: {conservative_residual_result.message}',
        shock_boundary=shock_boundary,
        companion_boundary=companion_boundary,
        companion_field=companion_field,
        conservative_residual_result=conservative_residual_result,
        conservative_residual_audit=conservative_residual_audit,
      )
    ####
    if not conservative_residual_audit.converged:
      return _failure(
        MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
        request,
        'global conservative residual solver converged locally but its '
        'independent residual audit did not converge: '
        f'{conservative_residual_audit.message}',
        shock_boundary=shock_boundary,
        companion_boundary=companion_boundary,
        companion_field=companion_field,
        conservative_residual_result=conservative_residual_result,
        conservative_residual_audit=conservative_residual_audit,
      )
    ####
    return MocReflectedDomainGlobalTwoSidedMovingInterfaceResult(
      status=(
        MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus
        .CONVERGED_RESEARCH_INTERFACE
      ),
      request=request,
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
      companion_field=companion_field,
      conservative_residual_result=conservative_residual_result,
      conservative_residual_audit=conservative_residual_audit,
      message=(
        'global closure fed the solver-owned signed conservative residual '
        'line-search and exact field re-solves; the result is research-only '
        'and independent canonical mixed-regime/free-boundary audits remain '
        'required'
      ),
    )
  ####
  assert moving_result is not None
  try:
    from exhaust_plume.validation.moc_euler_two_sided_interface_field_joint_closure import (
      measure_moc_euler_two_sided_interface_field_joint_closure,
    )
    from exhaust_plume.validation.moc_euler_two_sided_moving_interface import (
      measure_moc_euler_two_sided_moving_interface,
    )
    from exhaust_plume.validation.moc_euler_two_sided_moving_interface_fixed_point import (
      measure_moc_euler_two_sided_moving_interface_fixed_point,
    )

    moving_audit = measure_moc_euler_two_sided_moving_interface(moving_result)
    joint_audit = measure_moc_euler_two_sided_interface_field_joint_closure(
      moving_result
    )
    moving_fixed_point_audit = (
      measure_moc_euler_two_sided_moving_interface_fixed_point(moving_result)
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      f'global two-sided independent audit raised: {error}',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
      companion_field=companion_field,
      moving_result=moving_result,
    )
  ####
  if not moving_result.converged:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.MOVING_INTERFACE_FAILURE,
      request,
      'global two-sided moving-interface ladder retained a typed non-converged '
      f'result: {moving_result.message}',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
      companion_field=companion_field,
      moving_result=moving_result,
      moving_audit=moving_audit,
      joint_audit=joint_audit,
      moving_fixed_point_audit=moving_fixed_point_audit,
    )
  ####
  if not (
    moving_audit.converged
    and joint_audit.converged
  ):
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      'global two-sided moving-interface result converged locally but its '
      'independent moving and joint audits did not converge',
      shock_boundary=shock_boundary,
      companion_boundary=companion_boundary,
      companion_field=companion_field,
      moving_result=moving_result,
      moving_audit=moving_audit,
      joint_audit=joint_audit,
      moving_fixed_point_audit=moving_fixed_point_audit,
    )
  ####
  return MocReflectedDomainGlobalTwoSidedMovingInterfaceResult(
    status=(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus
      .CONVERGED_RESEARCH_INTERFACE
    ),
    request=request,
    shock_boundary=shock_boundary,
    companion_boundary=companion_boundary,
    companion_field=companion_field,
    moving_result=moving_result,
    moving_audit=moving_audit,
    joint_audit=joint_audit,
    moving_fixed_point_audit=moving_fixed_point_audit,
    message=(
      'verified global source-band and shock-boundary lineage fed the exact '
      'two-sided companion/physical-field response ladder; result remains '
      'research-only and cannot promote a canonical free boundary or chain'
    ),
  )


def solve_reflected_domain_global_two_sided_stationary_interface(
  request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
) -> MocReflectedDomainGlobalTwoSidedMovingInterfaceResult:
  """Run the explicit zero-speed front-limit research lane.

  A stationary front-limit response is a different solver mode from the
  interior-probe moving response.  This helper makes that distinction
  executable: it accepts only the exact post-shock boundary probe and forces
  the conservative-flux and terminal-fixed-point gates on.  It never turns a
  stationary result into moving-interface evidence or changes the result's
  research-only claim ceiling.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  ):
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      None,
      'request must be a typed global two-sided moving-interface request',
    )
  ####
  if request.downstream_probe_fraction != 0.0:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      request,
      'stationary interface mode requires downstream_probe_fraction=0; '
      'interior probes belong to the moving research lane',
    )
  ####
  if request.require_interface_motion:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      request,
      'stationary interface mode requires require_interface_motion=false',
    )
  ####
  if not request.allow_stationary_equilibrium:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      request,
      'stationary interface mode requires allow_stationary_equilibrium=true',
    )
  ####
  if not request.require_conservative_flux_closure:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      request,
      'stationary interface mode requires strict conservative-flux closure',
    )
  ####
  if not request.require_terminal_fixed_point:
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      request,
      'stationary interface mode requires a terminal fixed-point audit',
    )
  ####
  result = solve_reflected_domain_global_two_sided_moving_interface(request)
  if result.converged and (
    result.moving_result is None
    or not result.moving_result.stationary_equilibrium_verified
    or not result.moving_result.conservative_flux_closure_verified
    or not result.moving_result.terminal_fixed_point_verified
  ):
    return _failure(
      MocReflectedDomainGlobalTwoSidedMovingInterfaceStatus.INDEPENDENT_AUDIT_FAILURE,
      request,
      'stationary interface mode returned without independently verified '
      'stationary, conservative, and terminal fixed-point evidence',
      shock_boundary=result.shock_boundary,
      companion_boundary=result.companion_boundary,
      companion_field=result.companion_field,
      moving_result=result.moving_result,
      moving_audit=result.moving_audit,
      joint_audit=result.joint_audit,
    )
  ####
  return result
