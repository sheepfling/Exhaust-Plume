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
  'MocTransonicShockState',
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
  upstream_total_temperature_K: float | None = None
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
    if self.upstream_total_temperature_K is not None:
      total_temperature = float(self.upstream_total_temperature_K)
      if not isfinite(total_temperature) or total_temperature <= 0.0:
        raise ValueError(
          'upstream_total_temperature_K must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'upstream_total_temperature_K', total_temperature)
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
      'upstream_total_temperature_K': self.upstream_total_temperature_K,
      'pressure_tolerance_fraction': self.pressure_tolerance_fraction,
      'mach_tolerance': self.mach_tolerance,
      'max_iterations': self.max_iterations,
      'model': 'research-normal-shock-after-transonic-pressure-reference-v1',
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocTransonicShockState:
  """Scalar normal-shock state handoff for a future placed transition.

  The state is useful for initializing or checking a future solver-owned
  transonic interface.  It is intentionally not a geometric shock segment:
  no location, orientation, neighboring characteristic field, or free
  boundary is inferred here.
  """

  upstream_total_pressure_Pa: float
  upstream_total_temperature_K: float
  downstream_total_pressure_Pa: float
  total_pressure_ratio: float
  gamma: float
  gas_constant_J_kgK: float
  upstream_mach: float
  downstream_mach: float
  upstream_static_pressure_Pa: float
  downstream_static_pressure_Pa: float
  upstream_static_temperature_K: float
  downstream_static_temperature_K: float
  upstream_density_kg_m3: float
  downstream_density_kg_m3: float
  upstream_sound_speed_m_s: float
  downstream_sound_speed_m_s: float
  upstream_speed_m_s: float
  downstream_speed_m_s: float
  entropy_increase_JpkgK: float
  source: str = 'research-scalar-normal-shock-branch-state-v1'

  def __post_init__(self) -> None:
    for name in (
      'upstream_total_pressure_Pa',
      'upstream_total_temperature_K',
      'downstream_total_pressure_Pa',
      'total_pressure_ratio',
      'gamma',
      'gas_constant_J_kgK',
      'upstream_mach',
      'downstream_mach',
      'upstream_static_pressure_Pa',
      'downstream_static_pressure_Pa',
      'upstream_static_temperature_K',
      'downstream_static_temperature_K',
      'upstream_density_kg_m3',
      'downstream_density_kg_m3',
      'upstream_sound_speed_m_s',
      'downstream_sound_speed_m_s',
      'upstream_speed_m_s',
      'downstream_speed_m_s',
      'entropy_increase_JpkgK',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    ####
    if not self.upstream_mach > 1.0:
      raise ValueError('upstream_mach must be supersonic')
    ####
    if not self.downstream_mach < 1.0:
      raise ValueError('downstream_mach must be subsonic')
    ####
    if not 0.0 < self.total_pressure_ratio < 1.0:
      raise ValueError('total_pressure_ratio must be strictly between zero and one')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'source', source)
  ####

  @property
  def upstream_supersonic(self) -> bool:
    return self.upstream_mach > 1.0
  ####

  @property
  def downstream_subsonic(self) -> bool:
    return self.downstream_mach < 1.0
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A state seam is not a placed two-dimensional shock."""

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
      'source': self.source,
      'upstream_total_pressure_Pa': self.upstream_total_pressure_Pa,
      'upstream_total_temperature_K': self.upstream_total_temperature_K,
      'downstream_total_pressure_Pa': self.downstream_total_pressure_Pa,
      'total_pressure_ratio': self.total_pressure_ratio,
      'gamma': self.gamma,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'upstream_mach': self.upstream_mach,
      'downstream_mach': self.downstream_mach,
      'upstream_static_pressure_Pa': self.upstream_static_pressure_Pa,
      'downstream_static_pressure_Pa': self.downstream_static_pressure_Pa,
      'upstream_static_temperature_K': self.upstream_static_temperature_K,
      'downstream_static_temperature_K': self.downstream_static_temperature_K,
      'upstream_density_kg_m3': self.upstream_density_kg_m3,
      'downstream_density_kg_m3': self.downstream_density_kg_m3,
      'upstream_sound_speed_m_s': self.upstream_sound_speed_m_s,
      'downstream_sound_speed_m_s': self.downstream_sound_speed_m_s,
      'upstream_speed_m_s': self.upstream_speed_m_s,
      'downstream_speed_m_s': self.downstream_speed_m_s,
      'entropy_increase_JpkgK': self.entropy_increase_JpkgK,
      'upstream_supersonic': self.upstream_supersonic,
      'downstream_subsonic': self.downstream_subsonic,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only-scalar-normal-shock-state-handoff; geometric-placement, '
        'neighboring-field, and external-validation gates remain open'
      ),
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
  shock_state: MocTransonicShockState | None = None
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
    if self.shock_state is not None and not isinstance(
      self.shock_state,
      MocTransonicShockState,
    ):
      raise TypeError('shock_state must be a MocTransonicShockState or None')
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
      'shock_state': (
        None if self.shock_state is None else self.shock_state.as_report()
      ),
      'shock_state_available': self.shock_state is not None,
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
  shock_state_verified: bool = False
  shock_state_mass_flux_residual: float | None = None
  shock_state_momentum_flux_residual: float | None = None
  shock_state_energy_flux_residual: float | None = None
  shock_state_conservation_verified: bool = False
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
      'shock_state_verified': self.shock_state_verified,
      'shock_state_mass_flux_residual': self.shock_state_mass_flux_residual,
      'shock_state_momentum_flux_residual': self.shock_state_momentum_flux_residual,
      'shock_state_energy_flux_residual': self.shock_state_energy_flux_residual,
      'shock_state_conservation_verified': self.shock_state_conservation_verified,
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


def _normal_shock_state(
  request: MocTransonicTransitionRequest,
  upstream_mach: float,
) -> MocTransonicShockState | None:
  """Reconstruct the scalar thermodynamic state when total temperature exists."""

  if request.upstream_total_temperature_K is None:
    return None
  ####
  (
    upstream_static_pressure,
    downstream_static_pressure,
    downstream_mach,
    downstream_total_pressure,
    total_pressure_ratio,
  ) = _normal_shock_values(
    request.upstream_total_pressure_Pa,
    upstream_mach,
    request.gamma,
  )
  beta = 0.5 * (request.gamma - 1.0)
  upstream_factor = 1.0 + beta * upstream_mach * upstream_mach
  downstream_factor = 1.0 + beta * downstream_mach * downstream_mach
  upstream_static_temperature = request.upstream_total_temperature_K / upstream_factor
  downstream_static_temperature = request.upstream_total_temperature_K / downstream_factor
  upstream_density = upstream_static_pressure / (
    request.gas_constant_J_kgK * upstream_static_temperature
  )
  downstream_density = downstream_static_pressure / (
    request.gas_constant_J_kgK * downstream_static_temperature
  )
  upstream_sound_speed = sqrt(
    request.gamma
    * request.gas_constant_J_kgK
    * upstream_static_temperature
  )
  downstream_sound_speed = sqrt(
    request.gamma
    * request.gas_constant_J_kgK
    * downstream_static_temperature
  )
  return MocTransonicShockState(
    upstream_total_pressure_Pa=request.upstream_total_pressure_Pa,
    upstream_total_temperature_K=request.upstream_total_temperature_K,
    downstream_total_pressure_Pa=downstream_total_pressure,
    total_pressure_ratio=total_pressure_ratio,
    gamma=request.gamma,
    gas_constant_J_kgK=request.gas_constant_J_kgK,
    upstream_mach=upstream_mach,
    downstream_mach=downstream_mach,
    upstream_static_pressure_Pa=upstream_static_pressure,
    downstream_static_pressure_Pa=downstream_static_pressure,
    upstream_static_temperature_K=upstream_static_temperature,
    downstream_static_temperature_K=downstream_static_temperature,
    upstream_density_kg_m3=upstream_density,
    downstream_density_kg_m3=downstream_density,
    upstream_sound_speed_m_s=upstream_sound_speed,
    downstream_sound_speed_m_s=downstream_sound_speed,
    upstream_speed_m_s=upstream_mach * upstream_sound_speed,
    downstream_speed_m_s=downstream_mach * downstream_sound_speed,
    entropy_increase_JpkgK=request.gas_constant_J_kgK * log(
      1.0 / total_pressure_ratio
    ),
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
    shock_state = _normal_shock_state(request, required_mach)
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
      shock_state=shock_state,
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
    shock_state=_normal_shock_state(request, required_mach),
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


def _shock_state_matches(
  reported: MocTransonicShockState | None,
  expected: MocTransonicShockState | None,
) -> bool:
  """Compare every scalar in a reconstructed branch-state handoff."""

  if reported is None or expected is None:
    return reported is None and expected is None
  ####
  for name in (
    'upstream_total_pressure_Pa',
    'upstream_total_temperature_K',
    'downstream_total_pressure_Pa',
    'total_pressure_ratio',
    'gamma',
    'gas_constant_J_kgK',
    'upstream_mach',
    'downstream_mach',
    'upstream_static_pressure_Pa',
    'downstream_static_pressure_Pa',
    'upstream_static_temperature_K',
    'downstream_static_temperature_K',
    'upstream_density_kg_m3',
    'downstream_density_kg_m3',
    'upstream_sound_speed_m_s',
    'downstream_sound_speed_m_s',
    'upstream_speed_m_s',
    'downstream_speed_m_s',
    'entropy_increase_JpkgK',
  ):
    if not isclose(
      float(getattr(reported, name)),
      float(getattr(expected, name)),
      rel_tol=1.0e-8,
      abs_tol=1.0e-10,
    ):
      return False
    ####
  ####
  return reported.source == expected.source
####


def _shock_state_flux_residuals(
  state: MocTransonicShockState,
) -> tuple[float, float, float]:
  """Return normalized 1-D mass, momentum, and energy jump residuals."""

  upstream_mass_flux = (
    state.upstream_density_kg_m3 * state.upstream_speed_m_s
  )
  downstream_mass_flux = (
    state.downstream_density_kg_m3 * state.downstream_speed_m_s
  )
  upstream_momentum_flux = (
    upstream_mass_flux * state.upstream_speed_m_s
    + state.upstream_static_pressure_Pa
  )
  downstream_momentum_flux = (
    downstream_mass_flux * state.downstream_speed_m_s
    + state.downstream_static_pressure_Pa
  )
  upstream_energy_density = state.upstream_static_pressure_Pa / (
    state.gamma - 1.0
  ) + 0.5 * state.upstream_density_kg_m3 * state.upstream_speed_m_s**2
  downstream_energy_density = state.downstream_static_pressure_Pa / (
    state.gamma - 1.0
  ) + 0.5 * state.downstream_density_kg_m3 * state.downstream_speed_m_s**2
  upstream_energy_flux = (
    upstream_energy_density + state.upstream_static_pressure_Pa
  ) * state.upstream_speed_m_s
  downstream_energy_flux = (
    downstream_energy_density + state.downstream_static_pressure_Pa
  ) * state.downstream_speed_m_s
  return (
    abs(upstream_mass_flux - downstream_mass_flux)
    / max(1.0, abs(upstream_mass_flux), abs(downstream_mass_flux)),
    abs(upstream_momentum_flux - downstream_momentum_flux)
    / max(1.0, abs(upstream_momentum_flux), abs(downstream_momentum_flux)),
    abs(upstream_energy_flux - downstream_energy_flux)
    / max(1.0, abs(upstream_energy_flux), abs(downstream_energy_flux)),
  )
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
      shock_state_verified=result.shock_state is None,
      shock_state_conservation_verified=result.shock_state is None,
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
      shock_state_verified=result.shock_state is None,
      shock_state_conservation_verified=result.shock_state is None,
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
      shock_state_verified=False,
      shock_state_conservation_verified=False,
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
  expected_shock_state = _normal_shock_state(request, result.required_upstream_mach)
  shock_state_verified = _shock_state_matches(
    result.shock_state,
    expected_shock_state,
  )
  if expected_shock_state is None:
    conservation_residuals = (None, None, None)
    shock_state_conservation_verified = result.shock_state is None
  else:
    measured_conservation_residuals = _shock_state_flux_residuals(
      expected_shock_state
    )
    conservation_residuals = tuple(
      float(value) for value in measured_conservation_residuals
    )
    shock_state_conservation_verified = bool(
      max(measured_conservation_residuals) <= 1.0e-8
      and shock_state_verified
    )
  ####
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
    and shock_state_verified
    and shock_state_conservation_verified
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
    shock_state_verified=shock_state_verified,
    shock_state_mass_flux_residual=conservation_residuals[0],
    shock_state_momentum_flux_residual=conservation_residuals[1],
    shock_state_energy_flux_residual=conservation_residuals[2],
    shock_state_conservation_verified=shock_state_conservation_verified,
    message=(
      'normal-shock pressure, subsonic downstream Mach, and total-pressure '
      'loss were independently rederived'
      if valid
      else 'reported scalar transition quantities do not match independent re-derivation'
    ),
  )
####
