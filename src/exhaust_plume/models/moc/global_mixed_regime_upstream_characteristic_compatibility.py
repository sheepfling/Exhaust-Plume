"""Bounded compatibility consumption for an admitted supersonic interface.

P3.41 identifies which exact interface samples are primitive subsonic data and
which are genuinely supersonic characteristics.  This module consumes only
the latter subset with the existing planar MOC invariants and characteristic
directions.  It checks one declared incoming family along a contiguous
sampled span; it does not interpolate across a subsonic gap, invent the other
characteristic family, or solve a normal/free-boundary closure.

The output is therefore equation-consumption evidence for the next canonical
solver, not a global field or production shock-cell result.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_equation import (
  MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  characteristic_invariants,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_MODEL',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySegment',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit',
  'consume_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility',
  'audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-characteristic-compatibility-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_MODEL = (
  'research-global-mixed-regime-upstream-characteristic-compatibility-v1'
)


class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus(
  str,
  Enum,
):
  """Typed outcomes of one bounded compatibility consumption."""

  CONVERGED_LOCAL_RESEARCH_COMPATIBILITY = (
    'converged-local-research-upstream-characteristic-compatibility'
  )
  COMPLETED_RESEARCH_COMPATIBILITY_WITH_OPEN_RESIDUAL = (
    'completed-research-upstream-characteristic-compatibility-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  HANDOFF_REQUIRED = (
    'upstream-characteristic-compatibility-equation-handoff-required'
  )
  CHARACTERISTIC_DATA_REQUIRED = (
    'upstream-characteristic-compatibility-characteristic-data-required'
  )
  CHARACTERISTIC_COVERAGE_FAILURE = (
    'upstream-characteristic-compatibility-noncontiguous-coverage'
  )
  COMPATIBILITY_FAILURE = (
    'upstream-characteristic-compatibility-residual-failure'
  )
####


class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of an independent compatibility replay."""

  VERIFIED_LOCAL_RESEARCH_COMPATIBILITY = (
    'verified-local-research-upstream-characteristic-compatibility'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = (
    'upstream-characteristic-compatibility-audit-replay-failure'
  )
  LINEAGE_FAILURE = (
    'upstream-characteristic-compatibility-audit-lineage-failure'
  )
####


def _finite_positive(name: str, value: object) -> float:
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


def _finite_nonnegative(name: str, value: object) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric < 0.0:
    raise ValueError(f'{name} must be finite and nonnegative')
  ####
  return numeric
####


def _relative_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(abs(actual), abs(expected), 1.0e-12)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest:
  """Controls for a declared incoming-family compatibility probe."""

  upstream_equation_handoff: (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult
  )
  invariant_tolerance: float = 1.0e-8
  geometry_tolerance: float = 1.0e-2
  forward_margin_tolerance_m: float = 1.0e-10
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_MODEL
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.upstream_equation_handoff,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
    ):
      raise TypeError(
        'upstream_equation_handoff must be a typed upstream-equation result'
      )
    ####
    for name in (
      'invariant_tolerance',
      'geometry_tolerance',
      'forward_margin_tolerance_m',
    ):
      object.__setattr__(self, name, _finite_positive(name, getattr(self, name)))
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  @property
  def equation_request(
    self,
  ) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest | None:
    return self.upstream_equation_handoff.request
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_MODEL,
      'equation_operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID
      ),
      'equation_handoff_status': self.upstream_equation_handoff.status.value,
      'incoming_family': (
        None
        if self.equation_request is None
        else self.equation_request.incoming_family.value
      ),
      'invariant_tolerance': self.invariant_tolerance,
      'geometry_tolerance': self.geometry_tolerance,
      'forward_margin_tolerance_m': self.forward_margin_tolerance_m,
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample:
  """One exact incoming characteristic state and its selected invariant."""

  sample_index: int
  state: CharacteristicState
  family: CharacteristicFamily
  selected_invariant: float
  k_plus: float
  k_minus: float
  normal_projection: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.sample_index, bool)
      or not isinstance(self.sample_index, int)
      or self.sample_index < 0
    ):
      raise ValueError('sample_index must be a nonnegative integer')
    ####
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('state must be a CharacteristicState')
    ####
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    ####
    k_plus, k_minus = characteristic_invariants(self.state)
    for name, value in (
      ('selected_invariant', self.selected_invariant),
      ('k_plus', k_plus),
      ('k_minus', k_minus),
      ('normal_projection', self.normal_projection),
    ):
      numeric = float(value)
      if not isfinite(numeric):
        raise ValueError(f'{name} must be finite')
      ####
      if name == 'selected_invariant':
        object.__setattr__(self, name, numeric)
      ####
    ####
    if abs(float(self.k_plus) - k_plus) > 1.0e-12:
      raise ValueError('k_plus must match the exact characteristic state')
    ####
    if abs(float(self.k_minus) - k_minus) > 1.0e-12:
      raise ValueError('k_minus must match the exact characteristic state')
    ####
    expected = k_plus if self.family is CharacteristicFamily.PLUS else k_minus
    if abs(float(self.selected_invariant) - expected) > 1.0e-12:
      raise ValueError('selected_invariant must match the declared family')
    ####
    object.__setattr__(self, 'k_plus', k_plus)
    object.__setattr__(self, 'k_minus', k_minus)
    object.__setattr__(self, 'normal_projection', float(self.normal_projection))
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'sample_index': self.sample_index,
      'point_m': [self.state.x_m, self.state.y_m],
      'family': self.family.value,
      'mach': self.state.mach,
      'theta_rad': self.state.theta_rad,
      'gamma': self.state.gamma,
      'selected_invariant': self.selected_invariant,
      'k_plus': self.k_plus,
      'k_minus': self.k_minus,
      'normal_projection': self.normal_projection,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySegment:
  """Geometry and invariant residuals for one contiguous segment."""

  segment_index: int
  start_sample_index: int
  end_sample_index: int
  invariant_residual: float
  geometry_residual: float
  forward_margin_m: float
  path_length_m: float

  def __post_init__(self) -> None:
    for name in ('segment_index', 'start_sample_index', 'end_sample_index'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.end_sample_index != self.start_sample_index + 1:
      raise ValueError('compatibility segment sample indices must be consecutive')
    ####
    for name in ('invariant_residual', 'geometry_residual'):
      value = _finite_nonnegative(name, getattr(self, name))
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(
      self,
      'path_length_m',
      _finite_positive('path_length_m', self.path_length_m),
    )
    object.__setattr__(
      self,
      'forward_margin_m',
      float(self.forward_margin_m),
    )
    if not isfinite(self.forward_margin_m):
      raise ValueError('forward_margin_m must be finite')
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'segment_index': self.segment_index,
      'start_sample_index': self.start_sample_index,
      'end_sample_index': self.end_sample_index,
      'invariant_residual': self.invariant_residual,
      'geometry_residual': self.geometry_residual,
      'forward_margin_m': self.forward_margin_m,
      'path_length_m': self.path_length_m,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult:
  """Research compatibility evidence below canonical global closure."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest | None
  samples: tuple[
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample,
    ...
  ] = ()
  segments: tuple[
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySegment,
    ...
  ] = ()
  family: CharacteristicFamily | None = None
  subsonic_sample_indices: tuple[int, ...] = ()
  incoming_sample_indices: tuple[int, ...] = ()
  interface_handoff_verified: bool = False
  characteristic_compatibility_consumed: bool = False
  compatibility_gate_verified: bool = False
  normal_closure_required: bool = True
  upstream_characteristic_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus,
    ):
      raise TypeError('status must be a typed compatibility status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest,
    ):
      raise TypeError('request must be a typed compatibility request')
    ####
    samples = tuple(self.samples)
    segments = tuple(self.segments)
    if any(
      not isinstance(
        sample,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample,
      )
      for sample in samples
    ):
      raise TypeError('samples must contain typed compatibility samples')
    ####
    if any(
      not isinstance(
        segment,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySegment,
      )
      for segment in segments
    ):
      raise TypeError('segments must contain typed compatibility segments')
    ####
    if segments and len(segments) != len(samples) - 1:
      raise ValueError('compatibility segments must cover adjacent samples')
    ####
    if self.family is not None and not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily or None')
    ####
    subsonic = tuple(int(index) for index in self.subsonic_sample_indices)
    incoming = tuple(int(index) for index in self.incoming_sample_indices)
    if any(index < 0 for index in (*subsonic, *incoming)):
      raise ValueError('sample indices must be nonnegative')
    ####
    object.__setattr__(self, 'samples', samples)
    object.__setattr__(self, 'segments', segments)
    object.__setattr__(self, 'subsonic_sample_indices', subsonic)
    object.__setattr__(self, 'incoming_sample_indices', incoming)
    for name in (
      'interface_handoff_verified',
      'characteristic_compatibility_consumed',
      'compatibility_gate_verified',
      'normal_closure_required',
      'upstream_characteristic_equation_consumed',
      'free_boundary_equation_consumed',
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
      self.upstream_characteristic_equation_consumed
      or self.free_boundary_equation_consumed
      or self.global_coupling_verified
      or self.canonical_free_boundary_verified
    ):
      raise ValueError('compatibility evidence cannot claim global equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('compatibility evidence must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus
        .CONVERGED_LOCAL_RESEARCH_COMPATIBILITY,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus
        .COMPLETED_RESEARCH_COMPATIBILITY_WITH_OPEN_RESIDUAL,
      }
      and self.interface_handoff_verified
      and self.characteristic_compatibility_consumed
      and self.samples
      and len(self.segments) == len(self.samples) - 1
    )
  ####

  @property
  def maximum_invariant_residual(self) -> float | None:
    if not self.segments:
      return None
    ####
    return max(segment.invariant_residual for segment in self.segments)
  ####

  @property
  def maximum_geometry_residual(self) -> float | None:
    if not self.segments:
      return None
    ####
    return max(segment.geometry_residual for segment in self.segments)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'family': None if self.family is None else self.family.value,
      'samples': [sample.as_report() for sample in self.samples],
      'segments': [segment.as_report() for segment in self.segments],
      'subsonic_sample_indices': self.subsonic_sample_indices,
      'incoming_sample_indices': self.incoming_sample_indices,
      'maximum_invariant_residual': self.maximum_invariant_residual,
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'interface_handoff_verified': self.interface_handoff_verified,
      'characteristic_compatibility_consumed': (
        self.characteristic_compatibility_consumed
      ),
      'compatibility_gate_verified': self.compatibility_gate_verified,
      'normal_closure_required': self.normal_closure_required,
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only incoming-family compatibility evidence; no subsonic '
        'interpolation, second-family closure, moving free-boundary solve, '
        'global fixed point, or production claim is implied'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit:
  """Independent replay of exact characteristic compatibility evidence."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult | None
  replay: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult | None
  handoff_lineage_replayed: bool = False
  sample_replay_verified: bool = False
  segment_replay_verified: bool = False
  independent_compatibility_verified: bool = False
  upstream_characteristic_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAuditStatus,
    ):
      raise TypeError('status must be a typed compatibility audit status')
    ####
    for name in ('candidate', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
      ):
        raise TypeError(f'{name} must be a typed compatibility result')
      ####
    ####
    for name in (
      'handoff_lineage_replayed',
      'sample_replay_verified',
      'segment_replay_verified',
      'independent_compatibility_verified',
      'upstream_characteristic_equation_consumed',
      'free_boundary_equation_consumed',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if (
      self.upstream_characteristic_equation_consumed
      or self.free_boundary_equation_consumed
      or self.global_coupling_verified
    ):
      raise ValueError('compatibility audit cannot claim global equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('compatibility audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAuditStatus
      .VERIFIED_LOCAL_RESEARCH_COMPATIBILITY
      and self.independent_compatibility_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_COMPATIBILITY_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'handoff_lineage_replayed': self.handoff_lineage_replayed,
      'sample_replay_verified': self.sample_replay_verified,
      'segment_replay_verified': self.segment_replay_verified,
      'independent_compatibility_verified': self.independent_compatibility_verified,
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': None if self.candidate is None else self.candidate.as_report(),
      'replay': None if self.replay is None else self.replay.as_report(),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult:
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def _compatibility_segment(
  index: int,
  start: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample,
  end: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySegment:
  displacement = (
    end.state.x_m - start.state.x_m,
    end.state.y_m - start.state.y_m,
  )
  path_length = hypot(*displacement)
  if path_length <= 0.0:
    raise ValueError('incoming characteristic samples must be spatially distinct')
  ####
  start_direction = start.state.direction(start.family)
  end_direction = end.state.direction(end.family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  average_length = hypot(*average_direction)
  if average_length <= 0.0:
    raise ValueError('incoming characteristic direction is degenerate')
  ####
  geometry_residual = abs(
    displacement[0] * average_direction[1]
    - displacement[1] * average_direction[0]
  ) / (path_length * average_length)
  forward_margin = (
    displacement[0] * average_direction[0]
    + displacement[1] * average_direction[1]
  ) / average_length
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySegment(
    segment_index=index,
    start_sample_index=start.sample_index,
    end_sample_index=end.sample_index,
    invariant_residual=_relative_residual(
      end.selected_invariant,
      start.selected_invariant,
    ),
    geometry_residual=geometry_residual,
    forward_margin_m=forward_margin,
    path_length_m=path_length,
  )
####


def consume_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult:
  """Consume one contiguous incoming characteristic-family span."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityStatus
  )
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed characteristic-compatibility request',
    )
  ####
  handoff = request.upstream_equation_handoff
  equation_request = request.equation_request
  if equation_request is None:
    return _failure(
      status_type.HANDOFF_REQUIRED,
      'characteristic compatibility requires the exact upstream-equation '
      'request and interface lineage',
      request=request,
    )
  ####
  interface = equation_request.transonic_interface
  subsonic_indices = tuple(handoff.subsonic_sample_indices)
  incoming_indices = tuple(handoff.incoming_characteristic_indices)
  family = equation_request.incoming_family
  if not handoff.interface_handoff_verified:
    return _failure(
      status_type.HANDOFF_REQUIRED,
      'characteristic compatibility requires a verified interface handoff',
      request=request,
      family=family,
      subsonic_sample_indices=subsonic_indices,
      incoming_sample_indices=incoming_indices,
      interface_handoff_verified=False,
    )
  ####
  if not incoming_indices:
    return _failure(
      status_type.CHARACTERISTIC_DATA_REQUIRED,
      'the exact interface handoff retains no incoming genuinely supersonic '
      'characteristic samples; primitive subsonic data are not coerced',
      request=request,
      family=family,
      subsonic_sample_indices=subsonic_indices,
      incoming_sample_indices=(),
      interface_handoff_verified=True,
    )
  ####
  if incoming_indices != tuple(
    range(incoming_indices[0], incoming_indices[-1] + 1)
  ):
    return _failure(
      status_type.CHARACTERISTIC_COVERAGE_FAILURE,
      'incoming characteristic samples are not contiguous; no compatibility '
      'segment is allowed to cross a subsonic or missing sample',
      request=request,
      family=family,
      subsonic_sample_indices=subsonic_indices,
      incoming_sample_indices=incoming_indices,
      interface_handoff_verified=True,
    )
  ####
  sample_by_index = {
    sample.sample_index: sample for sample in interface.flux_samples
  }
  samples: list[
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample
  ] = []
  try:
    for sample_index in incoming_indices:
      interface_sample = sample_by_index[sample_index]
      state = interface_sample.frame_sample.characteristic_state
      if state is None:
        raise ValueError(
          f'incoming sample {sample_index} has no exact CharacteristicState'
        )
      ####
      direction = state.direction(family)
      normal_projection = direction[0] * interface_sample.normal_m[0] + (
        direction[1] * interface_sample.normal_m[1]
      )
      k_plus, k_minus = characteristic_invariants(state)
      samples.append(
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilitySample(
          sample_index=sample_index,
          state=state,
          family=family,
          selected_invariant=(k_plus if family is CharacteristicFamily.PLUS else k_minus),
          k_plus=k_plus,
          k_minus=k_minus,
          normal_projection=normal_projection,
        )
      )
    ####
    segments = tuple(
      _compatibility_segment(index, start, end)
      for index, (start, end) in enumerate(zip(samples, samples[1:]))
    )
  except (ArithmeticError, FloatingPointError, KeyError, TypeError, ValueError) as error:
    return _failure(
      status_type.COMPATIBILITY_FAILURE,
      f'characteristic compatibility consumption failed: {error}',
      request=request,
      family=family,
      subsonic_sample_indices=subsonic_indices,
      incoming_sample_indices=incoming_indices,
      interface_handoff_verified=True,
    )
  ####
  if not segments:
    return _failure(
      status_type.CHARACTERISTIC_COVERAGE_FAILURE,
      'at least two contiguous incoming characteristic samples are required '
      'to measure compatibility',
      request=request,
      family=family,
      samples=tuple(samples),
      subsonic_sample_indices=subsonic_indices,
      incoming_sample_indices=incoming_indices,
      interface_handoff_verified=True,
    )
  ####
  gate_verified = bool(
    all(
      segment.invariant_residual <= request.invariant_tolerance
      and segment.geometry_residual <= request.geometry_tolerance
      and segment.forward_margin_m > request.forward_margin_tolerance_m
      for segment in segments
    )
  )
  status = (
    status_type.CONVERGED_LOCAL_RESEARCH_COMPATIBILITY
    if gate_verified
    else status_type.COMPLETED_RESEARCH_COMPATIBILITY_WITH_OPEN_RESIDUAL
  )
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult(
    status=status,
    request=request,
    samples=tuple(samples),
    segments=segments,
    family=family,
    subsonic_sample_indices=subsonic_indices,
    incoming_sample_indices=incoming_indices,
    interface_handoff_verified=True,
    characteristic_compatibility_consumed=True,
    compatibility_gate_verified=gate_verified,
    normal_closure_required=True,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'the declared incoming characteristic family was consumed with exact '
      'invariants and forward geometry; normal/free-boundary closure remains '
      'open'
      if gate_verified
      else 'the declared incoming characteristic family was consumed, but one '
      'or more invariant/geometry/forward residuals remain open; no global '
      'closure claim is made'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
  result: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit:
  """Replay exact handoff, samples, and segments."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      replay=None,
      message='result must be a typed characteristic-compatibility result',
    )
  ####
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message='compatibility replay requires the exact request frame',
    )
  ####
  try:
    replay = consume_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
      result.request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=f'independent compatibility replay raised: {error}',
    )
  ####
  handoff_replayed = bool(
    replay.request is result.request
    and replay.interface_handoff_verified == result.interface_handoff_verified
  )
  samples_replayed = bool(
    replay.samples == result.samples
    and replay.family is result.family
    and replay.incoming_sample_indices == result.incoming_sample_indices
  )
  segments_replayed = bool(replay.segments == result.segments)
  independent = bool(
    handoff_replayed
    and samples_replayed
    and segments_replayed
    and replay.status is result.status
    and replay.characteristic_compatibility_consumed
    == result.characteristic_compatibility_consumed
    and replay.compatibility_gate_verified
    == result.compatibility_gate_verified
  )
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit(
    status=(
      audit_status.VERIFIED_LOCAL_RESEARCH_COMPATIBILITY
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    replay=replay,
    handoff_lineage_replayed=handoff_replayed,
    sample_replay_verified=samples_replayed,
    segment_replay_verified=segments_replayed,
    independent_compatibility_verified=independent,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced exact incoming-family compatibility '
      'samples, invariants, geometry, and residual status'
      if independent
      else 'independent replay did not reproduce exact compatibility evidence'
    ),
  )
####
