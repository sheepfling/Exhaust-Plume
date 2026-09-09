"""Cross-section coverage evidence for the open mixed-wave terminal patch.

The terminal scalar handoff identifies one subsonic normal-shock state.  It does
not supply a vertical inlet profile for a downstream subsonic field.  This
module makes that distinction explicit by sampling a caller-declared
cross-section only inside the retained reflection patch.  Missing ordinates
are retained as missing; no endpoint hold, extrapolation, or scalar-to-profile
promotion is performed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.moving_mixed_regime_interface import (
  MocMovingMixedRegimeInterfaceRequest,
  build_moc_terminal_conservative_boundary_sample,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_terminal_handoff import (
  MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit,
  MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
  measure_reflected_domain_global_transonic_mixed_wave_terminal_handoff,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_AUDIT_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAudit',
  'build_reflected_domain_global_transonic_mixed_wave_moving_interface_request_from_terminal_handoff',
  'assess_reflected_domain_global_transonic_mixed_wave_terminal_field_coverage',
  'measure_reflected_domain_global_transonic_mixed_wave_terminal_field_coverage',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-field-coverage'
)
MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_AUDIT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-terminal-field-coverage-audit'
)
DEFAULT_SAMPLE_COUNT = 17
DEFAULT_POSITION_TOLERANCE_M = 1.0e-5
DEFAULT_COVERAGE_TOLERANCE = 1.0e-10


class MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus(
  str,
  Enum,
):
  """Typed outcome of one open-patch cross-section coverage assessment."""

  CONVERGED_OPEN_PATCH_COVERAGE = (
    'converged-open-terminal-patch-cross-section-coverage'
  )
  INVALID_INPUT = 'invalid_input'
  HANDOFF_REQUIRED = 'global-transonic-mixed-wave-terminal-handoff-required'
  PATCH_REQUIRED = 'global-transonic-mixed-wave-terminal-patch-required'
  TERMINAL_OUTSIDE_SECTION = (
    'global-transonic-mixed-wave-terminal-outside-requested-section'
  )
  SUBSONIC_FIELD_REQUIRED = (
    'global-transonic-mixed-wave-subsonic-field-cross-section-required'
  )


class MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus(
  str,
  Enum,
):
  """Typed outcome of the independent coverage remeasurement."""

  VERIFIED = 'verified-open-terminal-patch-cross-section-coverage'
  INVALID_INPUT = 'invalid_input'
  CANDIDATE_REQUIRED = 'global-transonic-mixed-wave-terminal-field-coverage-required'
  HANDOFF_FAILURE = 'global-transonic-mixed-wave-terminal-field-handoff-failure'
  SAMPLE_LINEAGE_FAILURE = (
    'global-transonic-mixed-wave-terminal-field-sample-lineage-failure'
  )
  CLAIM_FLAG_FAILURE = (
    'global-transonic-mixed-wave-terminal-field-claim-flag-failure'
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest:
  """Caller-owned section on which retained terminal-patch coverage is tested."""

  handoff: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult
  cross_section_x_m: float
  lower_y_m: float
  upper_y_m: float
  sample_count: int = DEFAULT_SAMPLE_COUNT
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M
  coverage_tolerance: float = DEFAULT_COVERAGE_TOLERANCE
  source: str = 'research-terminal-patch-cross-section-coverage-v1'

  def __post_init__(self) -> None:
    if not isinstance(
      self.handoff,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
    ):
      raise TypeError(
        'handoff must be a typed global transonic terminal handoff result'
      )
    ####
    for name in (
      'cross_section_x_m',
      'lower_y_m',
      'upper_y_m',
      'position_tolerance_m',
      'coverage_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      ####
      if name in ('position_tolerance_m', 'coverage_tolerance') and value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.upper_y_m <= self.lower_y_m:
      raise ValueError('upper_y_m must be strictly greater than lower_y_m')
    ####
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer of at least three')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def sample_points(self) -> tuple[tuple[float, float], ...]:
    """Return the declared section points without any state extrapolation."""

    denominator = self.sample_count - 1
    return tuple(
      (
        self.cross_section_x_m,
        self.lower_y_m
        + (self.upper_y_m - self.lower_y_m) * index / denominator,
      )
      for index in range(self.sample_count)
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_OPERATOR_ID
      ),
      'cross_section_x_m': self.cross_section_x_m,
      'lower_y_m': self.lower_y_m,
      'upper_y_m': self.upper_y_m,
      'sample_count': self.sample_count,
      'position_tolerance_m': self.position_tolerance_m,
      'coverage_tolerance': self.coverage_tolerance,
      'sample_points_m': list(self.sample_points()),
      'source': self.source,
    }
  ####


def build_reflected_domain_global_transonic_mixed_wave_moving_interface_request_from_terminal_handoff(
  handoff: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
  *,
  upper_y_m: float,
  sample_count: int = DEFAULT_SAMPLE_COUNT,
  gas_constant_J_kgK: float | None = None,
  source: str = 'solver-owned-terminal-handoff-moving-interface-request-v1',
) -> MocMovingMixedRegimeInterfaceRequest:
  """Build the next solver request from the exact audited scalar handoff.

  Only the terminal point/state is materialized here.  The singleton
  interface geometry intentionally leaves the downstream moving trace
  unsolved, so the next solver returns a typed geometry/field requirement
  instead of extending the open reflection patch.
  """

  if not isinstance(
    handoff,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffResult,
  ):
    raise TypeError('handoff must be a typed terminal-handoff result')
  ####
  handoff_audit = measure_reflected_domain_global_transonic_mixed_wave_terminal_handoff(
    handoff
  )
  if not handoff.handoff_verified or not handoff_audit.converged:
    raise ValueError(
      'moving-interface request requires an independently verified scalar '
      'terminal handoff'
    )
  ####
  geometry = handoff.geometry
  assert geometry is not None
  terminal_sample = build_moc_terminal_conservative_boundary_sample(geometry)
  terminal_x, terminal_y = geometry.shock_point_m
  shock_state = geometry.request.shock_state
  return MocMovingMixedRegimeInterfaceRequest(
    terminal_geometry=geometry,
    interface_points_m=(geometry.shock_point_m,),
    boundary_samples=(terminal_sample,),
    cross_section_x_m=terminal_x,
    lower_y_m=terminal_y,
    upper_y_m=upper_y_m,
    sample_count=sample_count,
    gas_constant_J_kgK=(
      shock_state.gas_constant_J_kgK
      if gas_constant_J_kgK is None
      else gas_constant_J_kgK
    ),
    source=source,
  )
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample:
  """One exact section sample, with missing patch coverage preserved."""

  index: int
  point_m: tuple[float, float]
  state: CharacteristicState | None = None
  total_pressure_Pa: float | None = None
  static_pressure_Pa: float | None = None
  covered: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
      raise ValueError('index must be a nonnegative integer')
    ####
    if len(self.point_m) != 2 or not all(isfinite(float(value)) for value in self.point_m):
      raise ValueError('point_m must contain two finite coordinates')
    ####
    if self.state is not None and not isinstance(self.state, CharacteristicState):
      raise TypeError('state must be a CharacteristicState or None')
    ####
    for name in ('total_pressure_Pa', 'static_pressure_Pa'):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if not isinstance(self.covered, bool):
      raise TypeError('covered must be a bool')
    ####
    if self.covered and (
      self.state is None
      or self.total_pressure_Pa is None
      or self.static_pressure_Pa is None
    ):
      raise ValueError('a covered sample must retain state and both pressures')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'index': self.index,
      'point_m': self.point_m,
      'covered': self.covered,
      'state': (
        None
        if self.state is None
        else {
          'x_m': self.state.x_m,
          'y_m': self.state.y_m,
          'theta_rad': self.state.theta_rad,
          'mach': self.state.mach,
          'gamma': self.state.gamma,
        }
      ),
      'total_pressure_Pa': self.total_pressure_Pa,
      'static_pressure_Pa': self.static_pressure_Pa,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult:
  """Retained-patch coverage, never a downstream subsonic field."""

  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest
  handoff_audit: (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit | None
  )
  patch: MocTerminalReflectionPatchResult | None
  samples: tuple[
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample, ...
  ] = ()
  first_missing_sample_index: int | None = None
  maximum_covered_y_m: float | None = None
  terminal_point_m: tuple[float, float] | None = None
  terminal_binding_verified: bool = False
  patch_coverage_verified: bool = False
  subsonic_field_required: bool = True
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus,
    ):
      raise TypeError('status must be a terminal-field coverage status')
    ####
    if not isinstance(
      self.request,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest,
    ):
      raise TypeError('request must be a terminal-field coverage request')
    ####
    if self.handoff_audit is not None and not isinstance(
      self.handoff_audit,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit,
    ):
      raise TypeError('handoff_audit must be a typed handoff audit or None')
    ####
    if self.patch is not None and not isinstance(
      self.patch,
      MocTerminalReflectionPatchResult,
    ):
      raise TypeError('patch must be a typed reflection patch or None')
    ####
    if any(
      not isinstance(
        sample,
  MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample,
      )
      for sample in self.samples
    ):
      raise TypeError('samples must contain typed coverage samples')
    ####
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError('first_missing_sample_index must be a nonnegative integer or None')
    ####
    if self.maximum_covered_y_m is not None:
      value = float(self.maximum_covered_y_m)
      if not isfinite(value):
        raise ValueError('maximum_covered_y_m must be finite or None')
      ####
      object.__setattr__(self, 'maximum_covered_y_m', value)
    ####
    if self.terminal_point_m is not None:
      if len(self.terminal_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.terminal_point_m
      ):
        raise ValueError('terminal_point_m must contain two finite coordinates')
      ####
    ####
    for name in (
      'terminal_binding_verified',
      'patch_coverage_verified',
      'subsonic_field_required',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if not self.subsonic_field_required:
      raise ValueError('terminal coverage evidence must require a subsonic field')
    ####
    if self.physical_closure_verified or not self.chain_promotion_blocked:
      raise ValueError('terminal coverage evidence cannot close or promote a field')
    ####
    if self.production_claim_allowed:
      raise ValueError('terminal coverage evidence cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def covered_sample_count(self) -> int:
    return sum(sample.covered for sample in self.samples)
  ####

  @property
  def complete_cross_section_coverage(self) -> bool:
    return bool(
      self.patch_coverage_verified
      and len(self.samples) == self.request.sample_count
      and self.first_missing_sample_index is None
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_OPERATOR_ID
      ),
      'status': self.status.value,
      'complete_cross_section_coverage': self.complete_cross_section_coverage,
      'covered_sample_count': self.covered_sample_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'maximum_covered_y_m': self.maximum_covered_y_m,
      'terminal_point_m': self.terminal_point_m,
      'terminal_binding_verified': self.terminal_binding_verified,
      'patch_coverage_verified': self.patch_coverage_verified,
      'subsonic_field_required': self.subsonic_field_required,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': self.request.as_report(),
      'handoff_audit': (
        None if self.handoff_audit is None else self.handoff_audit.as_report()
      ),
      'patch': None if self.patch is None else self.patch.as_report(),
      'samples': [sample.as_report() for sample in self.samples],
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAudit:
  """Independent remeasurement of retained open-patch coverage."""

  status: (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
  )
  candidate: (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult | None
  )
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_TERMINAL_FIELD_COVERAGE_AUDIT_OPERATOR_ID
  )
  handoff_verified: bool = False
  terminal_binding_rederived: bool = False
  samples_rederived: bool = False
  missing_sample_lineage_verified: bool = False
  claim_flags_verified: bool = False
  maximum_state_residual: float | None = None
  maximum_total_pressure_residual_Pa: float | None = None
  maximum_static_pressure_residual_Pa: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus,
    ):
      raise TypeError('status must be a terminal-field coverage audit status')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult,
    ):
      raise TypeError('candidate must be a typed terminal-field coverage result or None')
    ####
    if not str(self.operator_id):
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    for name in (
      'handoff_verified',
      'terminal_binding_rederived',
      'samples_rederived',
      'missing_sample_lineage_verified',
      'claim_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'maximum_state_residual',
      'maximum_total_pressure_residual_Pa',
      'maximum_static_pressure_residual_Pa',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .VERIFIED
      and self.handoff_verified
      and self.terminal_binding_rederived
      and self.samples_rederived
      and self.missing_sample_lineage_verified
      and self.claim_flags_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'handoff_verified': self.handoff_verified,
      'terminal_binding_rederived': self.terminal_binding_rederived,
      'samples_rederived': self.samples_rederived,
      'missing_sample_lineage_verified': self.missing_sample_lineage_verified,
      'claim_flags_verified': self.claim_flags_verified,
      'maximum_state_residual': self.maximum_state_residual,
      'maximum_total_pressure_residual_Pa': self.maximum_total_pressure_residual_Pa,
      'maximum_static_pressure_residual_Pa': self.maximum_static_pressure_residual_Pa,
      'physical_closure_verified': self.physical_closure_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'candidate_status': (
        None if self.candidate is None else self.candidate.status.value
      ),
      'message': self.message,
    }
  ####


def _state_residual(
  first: CharacteristicState,
  second: CharacteristicState,
) -> float:
  return max(
    abs(first.x_m - second.x_m),
    abs(first.y_m - second.y_m),
    abs(first.theta_rad - second.theta_rad),
    abs(first.mach - second.mach),
    abs(first.gamma - second.gamma),
  )


def _pressure_residual(first: float, second: float) -> float:
  return abs(float(first) - float(second))


def _sample_patch(
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest,
  patch: MocTerminalReflectionPatchResult,
) -> tuple[
  tuple[MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample, ...],
  int | None,
  float | None,
]:
  samples: list[
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample
  ] = []
  first_missing: int | None = None
  maximum_covered_y: float | None = None
  for index, point in enumerate(request.sample_points()):
    state = patch.state_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    total_pressure = patch.total_pressure_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    static_pressure = patch.static_pressure_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    covered = bool(
      state is not None
      and total_pressure is not None
      and static_pressure is not None
      and isfinite(float(total_pressure))
      and float(total_pressure) > 0.0
      and isfinite(float(static_pressure))
      and float(static_pressure) > 0.0
    )
    if not covered:
      if first_missing is None:
        first_missing = index
      samples.append(
        MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample(
          index=index,
          point_m=point,
          covered=False,
          message='retained terminal patch has no state and pressure at this ordinate',
        )
      )
      continue
    ####
    assert state is not None
    assert total_pressure is not None
    assert static_pressure is not None
    maximum_covered_y = (
      float(point[1])
      if maximum_covered_y is None
      else max(maximum_covered_y, float(point[1]))
    )
    samples.append(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample(
        index=index,
        point_m=point,
        state=state,
        total_pressure_Pa=float(total_pressure),
        static_pressure_Pa=float(static_pressure),
        covered=True,
        message='sample lies inside the retained terminal reflection patch',
      )
    )
  ####
  return tuple(samples), first_missing, maximum_covered_y


def _result(
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus,
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest,
  *,
  handoff_audit: MocReflectedDomainGlobalTransonicMixedWaveTerminalHandoffAudit | None = None,
  patch: MocTerminalReflectionPatchResult | None = None,
  samples: tuple[MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageSample, ...] = (),
  first_missing_sample_index: int | None = None,
  maximum_covered_y_m: float | None = None,
  terminal_point_m: tuple[float, float] | None = None,
  terminal_binding_verified: bool = False,
  patch_coverage_verified: bool = False,
  message: str,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult(
    status=status,
    request=request,
    handoff_audit=handoff_audit,
    patch=patch,
    samples=samples,
    first_missing_sample_index=first_missing_sample_index,
    maximum_covered_y_m=maximum_covered_y_m,
    terminal_point_m=terminal_point_m,
    terminal_binding_verified=terminal_binding_verified,
    patch_coverage_verified=patch_coverage_verified,
    message=message,
  )


def assess_reflected_domain_global_transonic_mixed_wave_terminal_field_coverage(
  request: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult:
  """Assess an exact section against the retained terminal patch."""

  if not isinstance(
    request,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageRequest,
  ):
    raise TypeError('request must be a terminal-field coverage request')
  ####
  handoff = request.handoff
  handoff_audit = measure_reflected_domain_global_transonic_mixed_wave_terminal_handoff(
    handoff
  )
  if not handoff.handoff_verified or not handoff_audit.converged:
    return _result(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus
      .HANDOFF_REQUIRED,
      request,
      handoff_audit=handoff_audit,
      message=(
        'terminal-field coverage requires a currently verified scalar terminal '
        'handoff and independent handoff audit'
      ),
    )
  ####
  patch = handoff.request.probe.reflection_patch
  if patch is None or not patch.converged:
    return _result(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus
      .PATCH_REQUIRED,
      request,
      handoff_audit=handoff_audit,
      patch=patch,
      message='terminal-field coverage requires a converged retained reflection patch',
    )
  ####
  geometry = handoff.geometry
  assert geometry is not None
  terminal_point = geometry.shock_point_m
  terminal_binding_verified = bool(
    abs(float(terminal_point[0]) - request.cross_section_x_m)
    <= request.position_tolerance_m
    and request.lower_y_m - request.position_tolerance_m
    <= float(terminal_point[1])
    <= request.upper_y_m + request.position_tolerance_m
  )
  if not terminal_binding_verified:
    return _result(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus
      .TERMINAL_OUTSIDE_SECTION,
      request,
      handoff_audit=handoff_audit,
      patch=patch,
      terminal_point_m=terminal_point,
      message=(
        'requested cross-section does not contain the retained terminal point; '
        'the section was not shifted or reinterpreted'
      ),
    )
  ####
  samples, first_missing, maximum_covered_y = _sample_patch(request, patch)
  complete = first_missing is None
  status = (
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus
    .CONVERGED_OPEN_PATCH_COVERAGE
    if complete
    else MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageStatus
    .SUBSONIC_FIELD_REQUIRED
  )
  message = (
    'retained terminal patch covers the declared section samples; a separate '
    'subsonic field is still required and no production claim is enabled'
    if complete
    else (
      'retained terminal patch does not cover the declared section: first '
      f'missing sample index={first_missing}; a solver-owned subsonic field '
      'or moving interface is required, and no extrapolation was used'
    )
  )
  return _result(
    status,
    request,
    handoff_audit=handoff_audit,
    patch=patch,
    samples=samples,
    first_missing_sample_index=first_missing,
    maximum_covered_y_m=maximum_covered_y,
    terminal_point_m=terminal_point,
    terminal_binding_verified=True,
    patch_coverage_verified=complete,
    message=message,
  )


def _audit_failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus,
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult | None,
  message: str,
  **kwargs: object,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAudit:
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAudit(
    status=status,
    candidate=candidate,
    message=message,
    **kwargs,
  )


def measure_reflected_domain_global_transonic_mixed_wave_terminal_field_coverage(
  candidate: MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult,
) -> MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAudit:
  """Independently remeasure section samples and missing-coverage lineage."""

  if not isinstance(
    candidate,
    MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageResult,
  ):
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .INVALID_INPUT,
      None,
      'candidate must be a typed terminal-field coverage result',
    )
  ####
  handoff_audit = measure_reflected_domain_global_transonic_mixed_wave_terminal_handoff(
    candidate.request.handoff
  )
  if not candidate.request.handoff.handoff_verified or not handoff_audit.converged:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .HANDOFF_FAILURE,
      candidate,
      'independent terminal handoff audit did not converge',
    )
  ####
  patch = candidate.request.handoff.request.probe.reflection_patch
  if patch is None or not patch.converged or candidate.patch is not patch:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .SAMPLE_LINEAGE_FAILURE,
      candidate,
      'candidate did not retain the exact solver-owned reflection patch',
      handoff_verified=True,
    )
  ####
  expected = assess_reflected_domain_global_transonic_mixed_wave_terminal_field_coverage(
    candidate.request
  )
  if expected.status is not candidate.status:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .SAMPLE_LINEAGE_FAILURE,
      candidate,
      'independent coverage assessment changed the typed status',
      handoff_verified=True,
    )
  ####
  state_residuals: list[float] = []
  total_pressure_residuals: list[float] = []
  static_pressure_residuals: list[float] = []
  if len(expected.samples) != len(candidate.samples):
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .SAMPLE_LINEAGE_FAILURE,
      candidate,
      'candidate sample count does not match independent section sampling',
      handoff_verified=True,
    )
  ####
  for expected_sample, candidate_sample in zip(
    expected.samples,
    candidate.samples,
    strict=True,
  ):
    if (
      expected_sample.index != candidate_sample.index
      or expected_sample.point_m != candidate_sample.point_m
      or expected_sample.covered != candidate_sample.covered
    ):
      return _audit_failure(
        MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
        .SAMPLE_LINEAGE_FAILURE,
        candidate,
        'candidate sample geometry or coverage flag differs from remeasurement',
        handoff_verified=True,
      )
    ####
    if not expected_sample.covered:
      continue
    ####
    if (
      expected_sample.state is None
      or candidate_sample.state is None
      or expected_sample.total_pressure_Pa is None
      or candidate_sample.total_pressure_Pa is None
      or expected_sample.static_pressure_Pa is None
      or candidate_sample.static_pressure_Pa is None
    ):
      return _audit_failure(
        MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
        .SAMPLE_LINEAGE_FAILURE,
        candidate,
        'covered sample lost state or pressure lineage',
        handoff_verified=True,
      )
    ####
    state_residuals.append(_state_residual(expected_sample.state, candidate_sample.state))
    total_pressure_residuals.append(
      _pressure_residual(
        expected_sample.total_pressure_Pa,
        candidate_sample.total_pressure_Pa,
      )
    )
    static_pressure_residuals.append(
      _pressure_residual(
        expected_sample.static_pressure_Pa,
        candidate_sample.static_pressure_Pa,
      )
    )
    pressure_scale = max(
      1.0,
      abs(float(expected_sample.total_pressure_Pa)),
      abs(float(candidate_sample.total_pressure_Pa)),
      abs(float(expected_sample.static_pressure_Pa)),
      abs(float(candidate_sample.static_pressure_Pa)),
    )
    if (
      state_residuals[-1] > candidate.request.coverage_tolerance
      or total_pressure_residuals[-1]
      > candidate.request.coverage_tolerance * pressure_scale
      or static_pressure_residuals[-1]
      > candidate.request.coverage_tolerance * pressure_scale
    ):
      return _audit_failure(
        MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
        .SAMPLE_LINEAGE_FAILURE,
        candidate,
        'candidate covered-sample state or pressure residual exceeds the '
        'declared coverage tolerance',
        handoff_verified=True,
        terminal_binding_rederived=True,
        samples_rederived=True,
        maximum_state_residual=max(state_residuals),
        maximum_total_pressure_residual_Pa=max(total_pressure_residuals),
        maximum_static_pressure_residual_Pa=max(static_pressure_residuals),
      )
  ####
  missing_lineage_verified = bool(
    expected.first_missing_sample_index == candidate.first_missing_sample_index
    and expected.maximum_covered_y_m == candidate.maximum_covered_y_m
    and expected.terminal_point_m == candidate.terminal_point_m
    and expected.terminal_binding_verified == candidate.terminal_binding_verified
    and expected.patch_coverage_verified == candidate.patch_coverage_verified
  )
  if not missing_lineage_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .SAMPLE_LINEAGE_FAILURE,
      candidate,
      'candidate missing-coverage summary differs from remeasurement',
      handoff_verified=True,
      terminal_binding_rederived=True,
      samples_rederived=True,
      maximum_state_residual=max(state_residuals, default=0.0),
      maximum_total_pressure_residual_Pa=max(total_pressure_residuals, default=0.0),
      maximum_static_pressure_residual_Pa=max(static_pressure_residuals, default=0.0),
    )
  ####
  flags_verified = bool(
    candidate.subsonic_field_required
    and not candidate.physical_closure_verified
    and candidate.chain_promotion_blocked
    and not candidate.production_claim_allowed
  )
  if not flags_verified:
    return _audit_failure(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .CLAIM_FLAG_FAILURE,
      candidate,
      'terminal field coverage claim flags were weakened or inconsistent',
      handoff_verified=True,
      terminal_binding_rederived=True,
      samples_rederived=True,
      missing_sample_lineage_verified=True,
      maximum_state_residual=max(state_residuals, default=0.0),
      maximum_total_pressure_residual_Pa=max(total_pressure_residuals, default=0.0),
      maximum_static_pressure_residual_Pa=max(static_pressure_residuals, default=0.0),
    )
  ####
  return MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAudit(
    status=(
      MocReflectedDomainGlobalTransonicMixedWaveTerminalFieldCoverageAuditStatus
      .VERIFIED
    ),
    candidate=candidate,
    handoff_verified=True,
    terminal_binding_rederived=True,
    samples_rederived=True,
    missing_sample_lineage_verified=True,
    claim_flags_verified=True,
    maximum_state_residual=max(state_residuals, default=0.0),
    maximum_total_pressure_residual_Pa=max(total_pressure_residuals, default=0.0),
    maximum_static_pressure_residual_Pa=max(static_pressure_residuals, default=0.0),
    message=(
      'independent remeasurement reproduces the retained open-patch section '
      'coverage and preserves the subsonic-field/non-promotion boundary'
    ),
  )
