"""Conservative residual admission for a fresh global frontier resolve.

This adapter is deliberately downstream of the model-owned fresh frontier
solve.  It requires the independently audited fresh candidate, binds that
exact candidate into the existing two-sided conservative residual solver, and
retains a second independent residual audit.  It is a research seam: a
successful signed mass/momentum/energy descent does not open canonical
free-boundary, shock-cell, product, or release gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.global_frontier_reconciliation import (
  MocReflectedDomainGlobalFrontierFreshResolveResult,
)
from exhaust_plume.models.moc.global_two_sided_moving_interface import (
  MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
  solve_reflected_domain_global_two_sided_moving_interface,
)
from exhaust_plume.validation.moc_euler_two_sided_conservative_residual import (
  MocEulerTwoSidedConservativeResidualAudit,
  measure_moc_euler_two_sided_conservative_residual,
)
from exhaust_plume.validation.moc_global_frontier_fresh_resolve import (
  MocReflectedDomainGlobalFrontierFreshResolveAudit,
  audit_reflected_domain_global_frontier_fresh_resolve,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_RESIDUAL_OPERATOR_ID',
  'MocReflectedDomainGlobalFrontierFreshResolveResidualStatus',
  'MocReflectedDomainGlobalFrontierFreshResolveResidualResult',
  'run_reflected_domain_global_frontier_fresh_resolve_conservative_residual',
)


MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_RESIDUAL_OPERATOR_ID = (
  'op.moc.reflected-domain.global-frontier-fresh-resolve-conservative-residual-v1'
)


class MocReflectedDomainGlobalFrontierFreshResolveResidualStatus(str, Enum):
  """Typed outcomes of the fresh-frontier residual admission seam."""

  CONVERGED_RESEARCH_RESIDUAL = (
    'converged-research-global-frontier-fresh-resolve-residual'
  )
  CONVERGED_RESEARCH_STATIONARY_RESIDUAL = (
    'converged-research-global-frontier-fresh-resolve-stationary-residual'
  )
  INVALID_INPUT = 'invalid_input'
  FRESH_RESOLVE_REQUIRED = (
    'global-frontier-fresh-resolve-residual-fresh-resolve-required'
  )
  FRESH_AUDIT_FAILURE = (
    'global-frontier-fresh-resolve-residual-fresh-audit-failure'
  )
  LINEAGE_FAILURE = (
    'global-frontier-fresh-resolve-residual-lineage-failure'
  )
  RESIDUAL_FAILURE = (
    'global-frontier-fresh-resolve-residual-solver-failure'
  )
  RESIDUAL_AUDIT_FAILURE = (
    'global-frontier-fresh-resolve-residual-audit-failure'
  )
  PROMOTION_FAILURE = (
    'global-frontier-fresh-resolve-residual-promotion-failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalFrontierFreshResolveResidualResult:
  """Audited signed-residual evidence bound to one fresh global candidate."""

  status: MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
  fresh_resolve: MocReflectedDomainGlobalFrontierFreshResolveResult
  fresh_audit: MocReflectedDomainGlobalFrontierFreshResolveAudit | None = None
  two_sided_result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult | None = None
  conservative_residual_audit: MocEulerTwoSidedConservativeResidualAudit | None = None
  initial_residual_norm: float | None = None
  final_residual_norm: float | None = None
  maximum_mass_flux_residual_kg_m2_s: float | None = None
  maximum_normal_momentum_residual_Pa: float | None = None
  maximum_energy_flux_residual_W_m2: float | None = None
  fresh_resolve_verified: bool = False
  fresh_audit_verified: bool = False
  residual_solver_invoked: bool = False
  residual_vector_verified: bool = False
  strict_residual_descent_verified: bool = False
  independent_residual_audit_verified: bool = False
  fidelity_isolation_verified: bool = False
  stationary_residual_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveResidualStatus'
      )
    ####
    if not isinstance(
      self.fresh_resolve,
      MocReflectedDomainGlobalFrontierFreshResolveResult,
    ):
      raise TypeError(
        'fresh_resolve must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveResult'
      )
    ####
    if self.fresh_audit is not None and not isinstance(
      self.fresh_audit,
      MocReflectedDomainGlobalFrontierFreshResolveAudit,
    ):
      raise TypeError(
        'fresh_audit must be a '
        'MocReflectedDomainGlobalFrontierFreshResolveAudit or None'
      )
    ####
    if self.two_sided_result is not None and not isinstance(
      self.two_sided_result,
      MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
    ):
      raise TypeError(
        'two_sided_result must be a '
        'MocReflectedDomainGlobalTwoSidedMovingInterfaceResult or None'
      )
    ####
    if self.conservative_residual_audit is not None and not isinstance(
      self.conservative_residual_audit,
      MocEulerTwoSidedConservativeResidualAudit,
    ):
      raise TypeError(
        'conservative_residual_audit must be a '
        'MocEulerTwoSidedConservativeResidualAudit or None'
      )
    ####
    for name in (
      'initial_residual_norm',
      'final_residual_norm',
      'maximum_mass_flux_residual_kg_m2_s',
      'maximum_normal_momentum_residual_Pa',
      'maximum_energy_flux_residual_W_m2',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'fresh_resolve_verified',
      'fresh_audit_verified',
      'residual_solver_invoked',
      'residual_vector_verified',
      'strict_residual_descent_verified',
      'independent_residual_audit_verified',
      'fidelity_isolation_verified',
      'stationary_residual_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'fresh-frontier residual evidence must remain promotion-blocked'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged_research_residual(self) -> bool:
    """Whether every fresh and conservative research gate passed."""

    return bool(
      self.status
      in (
        MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
        .CONVERGED_RESEARCH_RESIDUAL,
        MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
        .CONVERGED_RESEARCH_STATIONARY_RESIDUAL,
      )
      and self.fresh_resolve_verified
      and self.fresh_audit_verified
      and self.residual_solver_invoked
      and self.residual_vector_verified
      and (
        self.strict_residual_descent_verified
        or self.stationary_residual_closure_verified
      )
      and self.independent_residual_audit_verified
      and self.fidelity_isolation_verified
      and self.two_sided_result is not None
      and self.two_sided_result.converged
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_FRONTIER_FRESH_RESOLVE_RESIDUAL_OPERATOR_ID
      ),
      'status': self.status.value,
      'converged_research_residual': self.converged_research_residual,
      'fresh_resolve_verified': self.fresh_resolve_verified,
      'fresh_audit_verified': self.fresh_audit_verified,
      'residual_solver_invoked': self.residual_solver_invoked,
      'residual_vector_verified': self.residual_vector_verified,
      'strict_residual_descent_verified': self.strict_residual_descent_verified,
      'independent_residual_audit_verified': (
        self.independent_residual_audit_verified
      ),
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'stationary_residual_closure_verified': (
        self.stationary_residual_closure_verified
      ),
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'initial_residual_norm': self.initial_residual_norm,
      'final_residual_norm': self.final_residual_norm,
      'maximum_mass_flux_residual_kg_m2_s': (
        self.maximum_mass_flux_residual_kg_m2_s
      ),
      'maximum_normal_momentum_residual_Pa': (
        self.maximum_normal_momentum_residual_Pa
      ),
      'maximum_energy_flux_residual_W_m2': (
        self.maximum_energy_flux_residual_W_m2
      ),
      'fresh_resolve': self.fresh_resolve.as_report(),
      'fresh_audit': (
        None if self.fresh_audit is None else self.fresh_audit.as_report()
      ),
      'two_sided_result': (
        None
        if self.two_sided_result is None
        else self.two_sided_result.as_report()
      ),
      'conservative_residual_audit': (
        None
        if self.conservative_residual_audit is None
        else self.conservative_residual_audit.as_report()
      ),
      'claim_status': (
        'research-only fresh-global-frontier conservative residual evidence; '
        'canonical free-boundary, refinement, shock-cell, product, external '
        'validation, and release gates remain open'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalFrontierFreshResolveResidualStatus,
  fresh_resolve: MocReflectedDomainGlobalFrontierFreshResolveResult,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainGlobalFrontierFreshResolveResidualResult:
  return MocReflectedDomainGlobalFrontierFreshResolveResidualResult(
    status=status,
    fresh_resolve=fresh_resolve,
    message=message,
    **kwargs,
  )
####


def _response_metrics(
  result: MocReflectedDomainGlobalTwoSidedMovingInterfaceResult,
) -> tuple[float, float, float] | None:
  residual = result.conservative_residual_result
  if residual is None or residual.final_response is None:
    return None
  response = residual.final_response
  return (
    response.maximum_mass_flux_residual_kg_m2_s,
    response.maximum_normal_momentum_residual_Pa,
    response.maximum_energy_flux_residual_W_m2,
  )
####


def run_reflected_domain_global_frontier_fresh_resolve_conservative_residual(
  fresh_resolve: MocReflectedDomainGlobalFrontierFreshResolveResult,
  two_sided_request: MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
) -> MocReflectedDomainGlobalFrontierFreshResolveResidualResult:
  """Consume one fresh frontier field through strict residual evidence."""

  if not isinstance(
    fresh_resolve,
    MocReflectedDomainGlobalFrontierFreshResolveResult,
  ):
    raise TypeError(
      'fresh_resolve must be a '
      'MocReflectedDomainGlobalFrontierFreshResolveResult'
    )
  ####
  if not isinstance(
    two_sided_request,
    MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest,
  ):
    raise TypeError(
      'two_sided_request must be a '
      'MocReflectedDomainGlobalTwoSidedMovingInterfaceRequest'
    )
  ####
  candidate = fresh_resolve.candidate_closure
  if candidate is None:
    return _result(
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
      .FRESH_RESOLVE_REQUIRED,
      fresh_resolve,
      'fresh frontier result retained no candidate closure',
    )
  ####
  if not (
    two_sided_request.closure is candidate
    and two_sided_request.use_conservative_residual_line_search
    and two_sided_request.require_conservative_flux_closure
    and two_sided_request.require_strict_residual_descent
  ):
    return _result(
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus.LINEAGE_FAILURE,
      fresh_resolve,
      'two-sided residual request must consume the exact fresh candidate and '
      'request conservative strict-descent mode',
    )
  ####
  fresh_audit = audit_reflected_domain_global_frontier_fresh_resolve(
    fresh_resolve
  )
  if not fresh_audit.audited_research_resolve:
    return _result(
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
      .FRESH_AUDIT_FAILURE,
      fresh_resolve,
      f'fresh frontier independent audit did not pass: {fresh_audit.message}',
      fresh_audit=fresh_audit,
      fresh_resolve_verified=fresh_resolve.converged_research_resolve,
      fresh_audit_verified=False,
    )
  ####
  try:
    two_sided_result = solve_reflected_domain_global_two_sided_moving_interface(
      two_sided_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus.RESIDUAL_FAILURE,
      fresh_resolve,
      f'fresh frontier conservative residual solve raised: {error}',
      fresh_audit=fresh_audit,
      fresh_resolve_verified=fresh_resolve.converged_research_resolve,
      fresh_audit_verified=True,
      residual_solver_invoked=True,
    )
  ####
  residual_result = two_sided_result.conservative_residual_result
  if residual_result is None:
    return _result(
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus.RESIDUAL_FAILURE,
      fresh_resolve,
      'two-sided result retained no conservative residual solver result',
      fresh_audit=fresh_audit,
      two_sided_result=two_sided_result,
      fresh_resolve_verified=fresh_resolve.converged_research_resolve,
      fresh_audit_verified=True,
      residual_solver_invoked=True,
    )
  ####
  try:
    residual_audit = measure_moc_euler_two_sided_conservative_residual(
      residual_result
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
      .RESIDUAL_AUDIT_FAILURE,
      fresh_resolve,
      f'independent conservative residual audit raised: {error}',
      fresh_audit=fresh_audit,
      two_sided_result=two_sided_result,
      fresh_resolve_verified=fresh_resolve.converged_research_resolve,
      fresh_audit_verified=True,
      residual_solver_invoked=True,
    )
  ####
  metrics = _response_metrics(two_sided_result)
  initial_norm = residual_result.initial_residual_norm
  final_norm = residual_result.final_residual_norm
  vector_verified = bool(
    residual_result.residual_vector_verified
    and residual_audit.residual_vector_verified
  )
  strict_descent = bool(
    len(residual_result.records) > 0
    and initial_norm is not None
    and final_norm is not None
    and final_norm < initial_norm
    and residual_audit.descent_verified
  )
  independent_verified = residual_audit.local_consistency_verified
  stationary_closure = bool(
    not strict_descent
    and not residual_result.records
    and residual_result.converged
    and residual_result.conservative_flux_closure_verified
    and residual_result.field_re_solve_verified
    and residual_result.terminal_fixed_point_verified
    and residual_audit.local_consistency_verified
    and two_sided_result.request is not None
    and two_sided_result.request.downstream_probe_fraction == 0.0
    and not two_sided_result.request.require_interface_motion
    and two_sided_result.request.allow_stationary_equilibrium
    and residual_result.final_response is not None
    and residual_result.final_response.stationary_equilibrium_candidate
  )
  fidelity_verified = bool(
    two_sided_result.chain_promotion_blocked
    and not two_sided_result.production_claim_allowed
    and not fresh_resolve.global_coupling_verified
    and not fresh_resolve.downstream_boundary_closure_verified
    and fresh_resolve.chain_promotion_blocked
    and not fresh_resolve.production_claim_allowed
  )
  common: dict[str, object] = {
    'fresh_audit': fresh_audit,
    'two_sided_result': two_sided_result,
    'conservative_residual_audit': residual_audit,
    'initial_residual_norm': initial_norm,
    'final_residual_norm': final_norm,
    'fresh_resolve_verified': fresh_resolve.converged_research_resolve,
    'fresh_audit_verified': True,
    'residual_solver_invoked': True,
    'residual_vector_verified': vector_verified,
    'strict_residual_descent_verified': strict_descent,
    'independent_residual_audit_verified': independent_verified,
    'fidelity_isolation_verified': fidelity_verified,
    'stationary_residual_closure_verified': stationary_closure,
  }
  if metrics is not None:
    common.update(
      maximum_mass_flux_residual_kg_m2_s=metrics[0],
      maximum_normal_momentum_residual_Pa=metrics[1],
      maximum_energy_flux_residual_W_m2=metrics[2],
    )
  ####
  if not independent_verified:
    status = (
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
      .RESIDUAL_AUDIT_FAILURE
    )
    message = f'independent conservative residual audit did not pass: {residual_audit.message}'
  elif not fidelity_verified:
    status = (
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
      .PROMOTION_FAILURE
    )
    message = 'fresh frontier residual handoff weakened a promotion blocker'
  elif not strict_descent:
    if stationary_closure:
      status = (
        MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
        .CONVERGED_RESEARCH_STATIONARY_RESIDUAL
      )
      message = (
        'fresh frontier exact front-limit reached independently audited '
        'stationary mass/momentum/energy closure; moving-front descent and '
        'canonical free-boundary coupling remain open'
      )
    else:
      status = (
        MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
        .RESIDUAL_FAILURE
      )
      message = (
        'fresh frontier residual solve did not retain strict signed-vector '
        'descent through an exact field re-solve'
      )
  elif not two_sided_result.converged:
    status = (
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus.RESIDUAL_FAILURE
    )
    message = (
      'fresh frontier residual solver retained strict descent but did not '
      f'close its declared research residuals: {two_sided_result.message}'
    )
  else:
    status = (
      MocReflectedDomainGlobalFrontierFreshResolveResidualStatus
      .CONVERGED_RESEARCH_RESIDUAL
    )
    message = (
      'fresh frontier closure retained independently audited signed '
      'mass/momentum/energy descent; canonical coupling remains open'
    )
  return _result(status, fresh_resolve, message, **common)
####
