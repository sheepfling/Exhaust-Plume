"""Bounded transonic pressure-target reference for the mixed-regime seam.

The canonical reflected field is not closed when a subsonic control section
cannot reach the requested ambient pressure isentropically.  This module
quantifies one physically explicit mechanism that can supply the missing
entropy: a supersonic transition followed by a normal shock.  It is a scalar
reference only.  It does not place the transition in the 2-D field, solve the
free boundary, or promote a shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isclose, isfinite, log, sqrt
from typing import Any

__all__ = (
  'MocTransonicTransitionAuditStatus',
  'MocTransonicTransitionStatus',
  'MocTransonicTransitionRequest',
  'MocTransonicTransitionResult',
  'MocTransonicTransitionAudit',
  'measure_moc_transonic_transition',
  'solve_moc_transonic_transition',
)


class MocTransonicTransitionStatus(str, Enum):
  """Outcome of the scalar pressure-target transition reference."""

  TARGET_ABOVE_TOTAL_PRESSURE = 'target-above-upstream-total-pressure'
  TARGET_REACHABLE_WITHOUT_SHOCK = 'target-reachable-without-shock'
  CONVERGED_NORMAL_SHOCK_REFERENCE = 'converged-normal-shock-pressure-reference'
  BRACKET_FAILURE = 'normal-shock-pressure-bracket-failure'
####


class MocTransonicTransitionAuditStatus(str, Enum):
  """Independent audit outcome for a transition reference."""

  VERIFIED = 'verified-scalar-transition-reference'
  RESULT_FAILURE = 'scalar-transition-reference-result-failure'
####


@dataclass(frozen=True, slots=True)
class MocTransonicTransitionRequest:
  """Inputs for a constant-gamma pressure-target normal-shock reference."""

  upstream_total_pressure_Pa: float
  target_downstream_static_pressure_Pa: float
  gamma: float
  gas_constant_J_kgK: float = 287.05
  pressure_tolerance_fraction: float = 1.0e-10
  mach_tolerance: float = 1.0e-10
  max_iterations: int = 128

  def __post_init__(self) -> None:
    for name, value in (
      ('upstream_total_pressure_Pa', self.upstream_total_pressure_Pa),
      ('target_downstream_static_pressure_Pa', self.target_downstream_static_pressure_Pa),
      ('gamma', self.gamma),
      ('gas_constant_J_kgK', self.gas_constant_J_kgK),
      ('pressure_tolerance_fraction', self.pressure_tolerance_fraction),
      ('mach_tolerance', self.mach_tolerance),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    ####
    if self.pressure_tolerance_fraction >= 1.0:
      raise ValueError('pressure_tolerance_fraction must be less than one')
    ####
    if isinstance(self.max_iterations, bool) or not isinstance(self.max_iterations, int) or self.max_iterations < 16:
      raise ValueError('max_iterations must be an integer greater than or equal to 16')
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'upstream_total_pressure_Pa': self.upstream_total_pressure_Pa,
      'target_downstream_static_pressure_Pa': self.target_downstream_static_pressure_Pa,
      'gamma': self.gamma,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'pressure_tolerance_fraction': self.pressure_tolerance_fraction,
      'mach_tolerance': self.mach_tolerance,
      'max_iterations': self.max_iterations,
      'model': 'research-normal-shock-after-transonic-pressure-reference-v1',
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicTransitionResult:
  """Scalar transition result with explicit non-promotion flags."""

  status: MocTransonicTransitionStatus
  request: MocTransonicTransitionRequest
  sonic_static_pressure_Pa: float
  required_upstream_mach: float | None = None
  upstream_static_pressure_Pa: float | None = None
  downstream_static_pressure_Pa: float | None = None
  downstream_mach: float | None = None
  downstream_total_pressure_Pa: float | None = None
  total_pressure_ratio: float | None = None
  entropy_increase_JpkgK: float | None = None
  pressure_residual_Pa: float | None = None
  iterations: int = 0
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocTransonicTransitionStatus):
      raise TypeError('status must be a MocTransonicTransitionStatus')
    ####
    values = (
      ('sonic_static_pressure_Pa', self.sonic_static_pressure_Pa),
      ('required_upstream_mach', self.required_upstream_mach),
      ('upstream_static_pressure_Pa', self.upstream_static_pressure_Pa),
      ('downstream_static_pressure_Pa', self.downstream_static_pressure_Pa),
      ('downstream_mach', self.downstream_mach),
      ('downstream_total_pressure_Pa', self.downstream_total_pressure_Pa),
      ('total_pressure_ratio', self.total_pressure_ratio),
      ('entropy_increase_JpkgK', self.entropy_increase_JpkgK),
      ('pressure_residual_Pa', self.pressure_residual_Pa),
    )
    for name, value in values:
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or (
        numeric < 0.0
        if name == 'pressure_residual_Pa'
        else numeric <= 0.0
      ):
        qualifier = 'nonnegative' if name == 'pressure_residual_Pa' else 'positive'
        raise ValueError(f'{name} must be finite and {qualifier} when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.total_pressure_ratio is not None and self.total_pressure_ratio >= 1.0:
      raise ValueError('total_pressure_ratio must be less than one for a resolved shock')
    ####
    if isinstance(self.iterations, bool) or not isinstance(self.iterations, int) or self.iterations < 0:
      raise ValueError('iterations must be a nonnegative integer')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def transition_required(self) -> bool:
    """Whether the target is below the isentropic sonic pressure bound."""

    return self.status in (
      MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE,
      MocTransonicTransitionStatus.BRACKET_FAILURE,
    )
  ####

  @property
  def converged(self) -> bool:
    """Whether the scalar reference or no-shock reachability test succeeded."""

    return self.status in (
      MocTransonicTransitionStatus.TARGET_REACHABLE_WITHOUT_SHOCK,
      MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE,
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Scalar pressure closure is not a surrounding 2-D physical closure."""

    return False
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    """The reference does not solve or verify a free boundary."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Keep scalar transition evidence out of continued shock-cell chains."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """The reference is never a production claim source."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'transition_required': self.transition_required,
      'sonic_static_pressure_Pa': self.sonic_static_pressure_Pa,
      'required_upstream_mach': self.required_upstream_mach,
      'upstream_static_pressure_Pa': self.upstream_static_pressure_Pa,
      'downstream_static_pressure_Pa': self.downstream_static_pressure_Pa,
      'downstream_mach': self.downstream_mach,
      'downstream_total_pressure_Pa': self.downstream_total_pressure_Pa,
      'total_pressure_ratio': self.total_pressure_ratio,
      'entropy_increase_JpkgK': self.entropy_increase_JpkgK,
      'pressure_residual_Pa': self.pressure_residual_Pa,
      'iterations': self.iterations,
      'request': self.request.as_report(),
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-scalar-transonic-normal-shock-reference; '
        '2-D placement, mixed-regime field closure, and external validation remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicTransitionAudit:
  """Independent re-derivation of scalar transition quantities."""

  status: MocTransonicTransitionAuditStatus
  result_status: MocTransonicTransitionStatus
  rederived: bool
  pressure_residual_Pa: float | None
  mach_residual: float | None
  total_pressure_residual: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocTransonicTransitionAuditStatus.VERIFIED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'result_status': self.result_status.value,
      'converged': self.converged,
      'rederived': self.rederived,
      'pressure_residual_Pa': self.pressure_residual_Pa,
      'mach_residual': self.mach_residual,
      'total_pressure_residual': self.total_pressure_residual,
      'physical_closure_verified': self.physical_closure_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
    }
  ####
####


def _normal_shock_values(
    upstream_total_pressure_Pa: float,
    upstream_mach: float,
    gamma: float,
) -> tuple[float, float, float, float, float]:
  """Return pre-shock static p, post-shock static p, M2, p02, and p02/p01."""

  isentropic_factor = 1.0 + 0.5 * (gamma - 1.0) * upstream_mach**2
  upstream_static_pressure = upstream_total_pressure_Pa / isentropic_factor ** (
    gamma / (gamma - 1.0)
  )
  static_pressure_ratio = 1.0 + 2.0 * gamma / (gamma + 1.0) * (
    upstream_mach**2 - 1.0
  )
  downstream_static_pressure = upstream_static_pressure * static_pressure_ratio
  downstream_mach_squared = (
    1.0 + 0.5 * (gamma - 1.0) * upstream_mach**2
  ) / (
    gamma * upstream_mach**2 - 0.5 * (gamma - 1.0)
  )
  downstream_mach = sqrt(downstream_mach_squared)
  downstream_isentropic_factor = 1.0 + 0.5 * (gamma - 1.0) * downstream_mach**2
  downstream_total_pressure = downstream_static_pressure * downstream_isentropic_factor ** (
    gamma / (gamma - 1.0)
  )
  return (
    upstream_static_pressure,
    downstream_static_pressure,
    downstream_mach,
    downstream_total_pressure,
    downstream_total_pressure / upstream_total_pressure_Pa,
  )
####


def _downstream_static_pressure_from_upstream_mach(
    request: MocTransonicTransitionRequest,
    upstream_mach: float,
) -> float:
  return _normal_shock_values(
    request.upstream_total_pressure_Pa,
    upstream_mach,
    request.gamma,
  )[1]
####


def solve_moc_transonic_transition(
    request: MocTransonicTransitionRequest,
) -> MocTransonicTransitionResult:
  """Solve the scalar shock pressure target while retaining research gates."""

  if not isinstance(request, MocTransonicTransitionRequest):
    raise TypeError('request must be a MocTransonicTransitionRequest')
  ####
  gamma = request.gamma
  sonic_factor = (1.0 + 0.5 * (gamma - 1.0)) ** (gamma / (gamma - 1.0))
  sonic_pressure = request.upstream_total_pressure_Pa / sonic_factor
  target = request.target_downstream_static_pressure_Pa
  pressure_tolerance = request.pressure_tolerance_fraction * max(
    target,
    sonic_pressure,
    request.upstream_total_pressure_Pa,
    1.0,
  )
  if target > request.upstream_total_pressure_Pa + pressure_tolerance:
    return MocTransonicTransitionResult(
      status=MocTransonicTransitionStatus.TARGET_ABOVE_TOTAL_PRESSURE,
      request=request,
      sonic_static_pressure_Pa=sonic_pressure,
      message='target static pressure exceeds the upstream total-pressure bound',
    )
  ####
  if target >= sonic_pressure - pressure_tolerance:
    return MocTransonicTransitionResult(
      status=MocTransonicTransitionStatus.TARGET_REACHABLE_WITHOUT_SHOCK,
      request=request,
      sonic_static_pressure_Pa=sonic_pressure,
      message='target lies within the isentropic subsonic pressure interval',
    )
  ####
  lower_mach = 1.0
  upper_mach = 2.0
  while _downstream_static_pressure_from_upstream_mach(request, upper_mach) > target:
    upper_mach *= 2.0
    if not isfinite(upper_mach) or upper_mach > 1.0e6:
      return MocTransonicTransitionResult(
        status=MocTransonicTransitionStatus.BRACKET_FAILURE,
        request=request,
        sonic_static_pressure_Pa=sonic_pressure,
        message='normal-shock pressure target could not be bracketed below Mach 1e6',
      )
    ####
  ####
  iterations = 0
  for iterations in range(1, request.max_iterations + 1):
    midpoint = 0.5 * (lower_mach + upper_mach)
    pressure = _downstream_static_pressure_from_upstream_mach(request, midpoint)
    if pressure > target:
      lower_mach = midpoint
    else:
      upper_mach = midpoint
    ####
    if upper_mach - lower_mach <= request.mach_tolerance * max(1.0, midpoint):
      break
    ####
  ####
  required_mach = 0.5 * (lower_mach + upper_mach)
  upstream_static, downstream_static, downstream_mach, downstream_total, ratio = (
    _normal_shock_values(request.upstream_total_pressure_Pa, required_mach, gamma)
  )
  residual = abs(downstream_static - target)
  valid = (
    required_mach > 1.0
    and downstream_mach < 1.0
    and 0.0 < ratio < 1.0
    and residual <= pressure_tolerance
  )
  if not valid:
    return MocTransonicTransitionResult(
      status=MocTransonicTransitionStatus.BRACKET_FAILURE,
      request=request,
      sonic_static_pressure_Pa=sonic_pressure,
      required_upstream_mach=required_mach,
      upstream_static_pressure_Pa=upstream_static,
      downstream_static_pressure_Pa=downstream_static,
      downstream_mach=downstream_mach,
      downstream_total_pressure_Pa=downstream_total,
      total_pressure_ratio=ratio,
      entropy_increase_JpkgK=request.gas_constant_J_kgK * log(1.0 / ratio),
      pressure_residual_Pa=residual,
      iterations=iterations,
      message='normal-shock pressure target did not satisfy scalar invariants',
    )
  ####
  return MocTransonicTransitionResult(
    status=MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE,
    request=request,
    sonic_static_pressure_Pa=sonic_pressure,
    required_upstream_mach=required_mach,
    upstream_static_pressure_Pa=upstream_static,
    downstream_static_pressure_Pa=downstream_static,
    downstream_mach=downstream_mach,
    downstream_total_pressure_Pa=downstream_total,
    total_pressure_ratio=ratio,
    entropy_increase_JpkgK=request.gas_constant_J_kgK * log(1.0 / ratio),
    pressure_residual_Pa=residual,
    iterations=iterations,
    message=(
      'scalar normal-shock pressure target is closed; 2-D transition placement '
      'and mixed-regime field closure remain open'
    ),
  )
####


def _relative_residual(reported: float | None, measured: float | None) -> float | None:
  if reported is None or measured is None:
    return None
  ####
  return abs(reported - measured) / max(abs(measured), 1.0)
####


def measure_moc_transonic_transition(
    result: MocTransonicTransitionResult,
) -> MocTransonicTransitionAudit:
  """Recompute the scalar pressure and shock invariants independently."""

  if not isinstance(result, MocTransonicTransitionResult):
    raise TypeError('result must be a MocTransonicTransitionResult')
  ####
  request = result.request
  gamma = request.gamma
  sonic_factor = (1.0 + 0.5 * (gamma - 1.0)) ** (gamma / (gamma - 1.0))
  sonic_pressure = request.upstream_total_pressure_Pa / sonic_factor
  pressure_scale = max(
    request.target_downstream_static_pressure_Pa,
    sonic_pressure,
    request.upstream_total_pressure_Pa,
    1.0,
  )
  tolerance = max(request.pressure_tolerance_fraction * pressure_scale, 1.0e-8)
  if result.status is MocTransonicTransitionStatus.TARGET_REACHABLE_WITHOUT_SHOCK:
    valid = request.target_downstream_static_pressure_Pa >= sonic_pressure - tolerance
    return MocTransonicTransitionAudit(
      status=(
        MocTransonicTransitionAuditStatus.VERIFIED
        if valid
        else MocTransonicTransitionAuditStatus.RESULT_FAILURE
      ),
      result_status=result.status,
      rederived=True,
      pressure_residual_Pa=abs(result.sonic_static_pressure_Pa - sonic_pressure),
      mach_residual=None,
      total_pressure_residual=None,
      message='isentropic subsonic reachability classification independently rederived',
    )
  ####
  if result.status is not MocTransonicTransitionStatus.CONVERGED_NORMAL_SHOCK_REFERENCE:
    return MocTransonicTransitionAudit(
      status=MocTransonicTransitionAuditStatus.RESULT_FAILURE,
      result_status=result.status,
      rederived=True,
      pressure_residual_Pa=None,
      mach_residual=None,
      total_pressure_residual=None,
      message='the scalar transition result did not report a verified reference to audit',
    )
  ####
  if result.required_upstream_mach is None:
    return MocTransonicTransitionAudit(
      status=MocTransonicTransitionAuditStatus.RESULT_FAILURE,
      result_status=result.status,
      rederived=False,
      pressure_residual_Pa=None,
      mach_residual=None,
      total_pressure_residual=None,
      message='resolved transition result omitted required_upstream_mach',
    )
  ####
  upstream_static, downstream_static, downstream_mach, downstream_total, ratio = (
    _normal_shock_values(
      request.upstream_total_pressure_Pa,
      result.required_upstream_mach,
      gamma,
    )
  )
  pressure_residual = abs(downstream_static - request.target_downstream_static_pressure_Pa)
  reported_pressure_residual = _relative_residual(
    result.downstream_static_pressure_Pa,
    downstream_static,
  )
  reported_mach_residual = _relative_residual(result.downstream_mach, downstream_mach)
  reported_total_pressure_residual = _relative_residual(
    result.downstream_total_pressure_Pa,
    downstream_total,
  )
  valid = (
    isclose(
      result.sonic_static_pressure_Pa,
      sonic_pressure,
      rel_tol=1.0e-8,
      abs_tol=tolerance,
    )
    and result.required_upstream_mach > 1.0
    and downstream_mach < 1.0
    and 0.0 < ratio < 1.0
    and pressure_residual <= tolerance
    and reported_pressure_residual is not None
    and reported_pressure_residual <= 1.0e-8
    and reported_mach_residual is not None
    and reported_mach_residual <= 1.0e-8
    and reported_total_pressure_residual is not None
    and reported_total_pressure_residual <= 1.0e-8
  )
  return MocTransonicTransitionAudit(
    status=(
      MocTransonicTransitionAuditStatus.VERIFIED
      if valid
      else MocTransonicTransitionAuditStatus.RESULT_FAILURE
    ),
    result_status=result.status,
    rederived=True,
    pressure_residual_Pa=pressure_residual,
    mach_residual=reported_mach_residual,
    total_pressure_residual=reported_total_pressure_residual,
    message=(
      'normal-shock pressure, subsonic downstream Mach, and total-pressure '
      'loss were independently rederived'
      if valid
      else 'reported scalar transition quantities do not match independent re-derivation'
    ),
  )
####
