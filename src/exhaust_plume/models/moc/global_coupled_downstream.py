"""Bounded global-to-coupled downstream continuation for the MOC lane.

The global reflected closure and the constant-gamma coupled Euler field are
separate solver lanes.  This module binds them for one explicit research
candidate and retains the independent coupled-field audit.  The candidate is
not a canonical global closure: the downstream field does not feed its
pressure and characteristic response back into the upstream shock solve, so
``global_coupling_verified`` remains false by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
  build_reflected_domain_coupled_euler_free_boundary_request,
  solve_reflected_domain_coupled_euler_free_boundary,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfileResult,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionResult,
)
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  MocReflectedDomainMixedRegimeBoundaryRequest,
  build_reflected_domain_mixed_regime_boundary_request,
)

__all__ = (
  'MocReflectedDomainGlobalCoupledDownstreamStatus',
  'MocReflectedDomainGlobalCoupledDownstreamResult',
  'solve_reflected_domain_global_coupled_downstream',
)


GLOBAL_COUPLED_DOWNSTREAM_MODEL = (
  'research-global-coupled-euler-downstream-candidate'
)


class MocReflectedDomainGlobalCoupledDownstreamStatus(str, Enum):
  """Outcome of one bound global-to-coupled downstream candidate."""

  CONVERGED_LOCAL_COUPLED_FIELD = (
    'converged-local-global-coupled-downstream-field'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_CLOSURE_FAILURE = 'global-coupled-downstream-upstream-failure'
  MIXED_REGIME_REQUEST_FAILURE = (
    'global-coupled-downstream-mixed-regime-request-failure'
  )
  COUPLED_SOLVER_FAILURE = 'global-coupled-downstream-solver-failure'
  INDEPENDENT_AUDIT_FAILURE = (
    'global-coupled-downstream-independent-audit-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamResult:
  """A research candidate with explicit upstream and downstream lineage."""

  status: MocReflectedDomainGlobalCoupledDownstreamStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest | None
  coupled_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  coupled_field_audit: Any | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainGlobalCoupledDownstreamStatus'
      )
    ####
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a '
        'MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    if self.mixed_regime_request is not None and not isinstance(
      self.mixed_regime_request,
      MocReflectedDomainMixedRegimeBoundaryRequest,
    ):
      raise TypeError(
        'mixed_regime_request must be a '
        'MocReflectedDomainMixedRegimeBoundaryRequest or None'
      )
    ####
    if self.coupled_request is not None and not isinstance(
      self.coupled_request,
      MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    ):
      raise TypeError(
        'coupled_request must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryRequest or None'
      )
    ####
    if self.coupled_field is not None and not isinstance(
      self.coupled_field,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'coupled_field must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult or None'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    if self.closure is None:
      return None
    ####
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def closure_lineage_verified(self) -> bool:
    """Whether the candidate retains one exact closure identity end to end."""

    fingerprint = self.source_closure_fingerprint
    return bool(
      fingerprint is not None
      and self.mixed_regime_request is not None
      and self.mixed_regime_request.closure_fingerprint == fingerprint
      and self.coupled_request is not None
      and self.coupled_request.source_closure_fingerprint == fingerprint
      and (
        self.coupled_field is None
        or (
          self.coupled_field.request is self.coupled_request
          and self.coupled_field.request.source_closure_fingerprint == fingerprint
        )
      )
      and (
        self.coupled_field_audit is None
        or getattr(self.coupled_field_audit, 'candidate', None)
        is self.coupled_field
      )
    )
  ####

  @property
  def local_coupled_field_verified(self) -> bool:
    """Whether the downstream candidate and its independent audit both pass."""

    return bool(
      self.coupled_field is not None
      and self.coupled_field_audit is not None
      and self.coupled_field.status
      is MocReflectedDomainCoupledEulerFreeBoundaryStatus
      .CONVERGED_LOCAL_PHYSICAL_CLOSURE
      and self.coupled_field.converged
      and getattr(self.coupled_field_audit, 'converged', False)
      and getattr(self.coupled_field_audit, 'local_consistency_verified', False)
      and self.closure_lineage_verified
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamStatus
      .CONVERGED_LOCAL_COUPLED_FIELD
      and self.local_coupled_field_verified
    )
  ####

  @property
  def global_coupling_verified(self) -> bool:
    """Whether downstream response was iterated back into the global solve."""

    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """The candidate never satisfies the canonical downstream gate."""

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

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.local_coupled_field_verified
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'termination_model': GLOBAL_COUPLED_DOWNSTREAM_MODEL,
        'status': self.status.value,
        'source_closure_fingerprint': self.source_closure_fingerprint,
        'closure_lineage_verified': self.closure_lineage_verified,
        'local_coupled_field_verified': self.local_coupled_field_verified,
        'global_coupling_verified': self.global_coupling_verified,
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': GLOBAL_COUPLED_DOWNSTREAM_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'closure_lineage_verified': self.closure_lineage_verified,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'mixed_regime_request': (
        None
        if self.mixed_regime_request is None
        else self.mixed_regime_request.as_report()
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
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalCoupledDownstreamStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest | None = None,
  coupled_request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None = None,
  coupled_field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None,
  coupled_field_audit: Any | None = None,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=status,
    closure=closure,
    mixed_regime_request=mixed_regime_request,
    coupled_request=coupled_request,
    coupled_field=coupled_field,
    coupled_field_audit=coupled_field_audit,
    message=message,
  )
####


def solve_reflected_domain_global_coupled_downstream(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  reference_total_temperature_K: float,
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  axial_station_count: int = 7,
  axial_cell_count: int = 12,
  transverse_cell_count: int = 6,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None,
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  """Run one explicitly bound downstream coupled-Euler research candidate."""

  if not isinstance(
    closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus.UPSTREAM_CLOSURE_FAILURE,
      'global coupled downstream solving requires a locally verified global '
      'physical closure',
      closure=closure,
    )
  ####
  try:
    mixed_regime_request = build_reflected_domain_mixed_regime_boundary_request(
      closure,
      ambient_pressure_Pa=ambient_pressure_Pa,
      downstream_length_m=downstream_length_m,
      initial_outlet_height_m=initial_outlet_height_m,
      control_section_x_offset_m=control_section_x_offset_m,
      control_section_height_m=control_section_height_m,
      control_section_sample_count=control_section_sample_count,
      axial_station_count=axial_station_count,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus
      .MIXED_REGIME_REQUEST_FAILURE,
      f'global coupled downstream mixed-regime request failed: {error}',
      closure=closure,
    )
  ####
  try:
    coupled_request = build_reflected_domain_coupled_euler_free_boundary_request(
      mixed_regime_request,
      reference_total_temperature_K=reference_total_temperature_K,
      axial_cell_count=axial_cell_count,
      transverse_cell_count=transverse_cell_count,
      max_pseudo_iterations=max_pseudo_iterations,
      max_shape_iterations=max_shape_iterations,
      inlet_boundary_mode=inlet_boundary_mode,
      outlet_static_pressure_Pa=outlet_static_pressure_Pa,
      physical_field_continuation_profile=physical_field_continuation_profile,
      physical_field_shock_front_condition=physical_field_shock_front_condition,
    )
    coupled_field = solve_reflected_domain_coupled_euler_free_boundary(
      coupled_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE,
      f'global coupled downstream solver raised: {error}',
      closure=closure,
      mixed_regime_request=mixed_regime_request,
    )
  ####
  try:
    from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
      measure_reflected_domain_coupled_euler_free_boundary,
    )

    coupled_field_audit = measure_reflected_domain_coupled_euler_free_boundary(
      coupled_field
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalCoupledDownstreamStatus
      .INDEPENDENT_AUDIT_FAILURE,
      f'global coupled downstream independent audit raised: {error}',
      closure=closure,
      mixed_regime_request=mixed_regime_request,
      coupled_request=coupled_request,
      coupled_field=coupled_field,
    )
  ####
  if coupled_field.status is (
    MocReflectedDomainCoupledEulerFreeBoundaryStatus
    .CONVERGED_LOCAL_PHYSICAL_CLOSURE
  ) and coupled_field_audit.converged:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamStatus
      .CONVERGED_LOCAL_COUPLED_FIELD
    )
    message = (
      'global closure and downstream coupled-Euler field passed their local '
      'audits; global feedback, canonical boundary closure, refinement, and '
      'external validation remain open'
    )
  else:
    status = (
      MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE
    )
    message = (
      'downstream coupled-Euler candidate retained its typed solver/audit '
      f'failure ({coupled_field.status.value}); no global feedback or '
      'lower-fidelity fallback was attempted'
    )
  ####
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=status,
    closure=closure,
    mixed_regime_request=mixed_regime_request,
    coupled_request=coupled_request,
    coupled_field=coupled_field,
    coupled_field_audit=coupled_field_audit,
    message=message,
  )
####
