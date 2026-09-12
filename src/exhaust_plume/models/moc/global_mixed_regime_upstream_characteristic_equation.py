"""Typed handoff gate for the upstream characteristic/free-boundary equation.

The transonic-interface admission exposes two different kinds of data: a
primitive subsonic condition and optional genuinely supersonic characteristic
samples.  This module makes the next equation boundary explicit.  It consumes
the audited interface, retains both subsets without conversion, and stops
when the incoming characteristic or normal/free-boundary closure is absent.

It is intentionally an admission contract, not a fabricated characteristic
solve.  In particular, an all-subsonic trace produces a typed
``MISSING_INCOMING_CHARACTERISTIC`` result and never changes any canonical or
production flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_transonic_interface import (
  MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_MODEL',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit',
  'admit_reflected_domain_global_mixed_regime_upstream_characteristic_equation',
  'audit_reflected_domain_global_mixed_regime_upstream_characteristic_equation',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-upstream-characteristic-equation-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_MODEL = (
  'research-global-mixed-regime-upstream-characteristic-equation-handoff-v1'
)


class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus(
  str,
  Enum,
):
  """Typed outcomes of the canonical-equation admission boundary."""

  ADMITTED_LOCAL_RESEARCH_HANDOFF = (
    'admitted-local-research-upstream-characteristic-equation-handoff'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_REQUIRED = (
    'upstream-characteristic-equation-transonic-interface-required'
  )
  INTERFACE_AUDIT_REQUIRED = (
    'upstream-characteristic-equation-interface-audit-required'
  )
  INTERFACE_LINEAGE_FAILURE = (
    'upstream-characteristic-equation-interface-lineage-failure'
  )
  MISSING_INCOMING_CHARACTERISTIC = (
    'upstream-characteristic-equation-missing-incoming-characteristic'
  )
  NORMAL_CLOSURE_REQUIRED = (
    'upstream-characteristic-equation-normal-closure-required'
  )
####


class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the handoff replay."""

  VERIFIED_LOCAL_RESEARCH_HANDOFF = (
    'verified-local-research-upstream-characteristic-equation-handoff'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'upstream-characteristic-equation-audit-replay-failure'
  LINEAGE_FAILURE = 'upstream-characteristic-equation-audit-lineage-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest:
  """Exact interface/audit handoff requested by the future equation."""

  transonic_interface: (
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult
  )
  transonic_interface_audit: (
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit
  )
  require_incoming_characteristic: bool = True
  require_normal_closure: bool = True
  incoming_family: CharacteristicFamily = CharacteristicFamily.PLUS
  incoming_normal_sign: float = 1.0
  characteristic_alignment_tolerance: float = 1.0e-8
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_MODEL
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.transonic_interface,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
    ):
      raise TypeError('transonic_interface must be a typed interface result')
    ####
    if not isinstance(
      self.transonic_interface_audit,
      MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit,
    ):
      raise TypeError('transonic_interface_audit must be a typed interface audit')
    ####
    for name in ('require_incoming_characteristic', 'require_normal_closure'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not isinstance(self.incoming_family, CharacteristicFamily):
      raise TypeError('incoming_family must be a CharacteristicFamily')
    ####
    normal_sign = float(self.incoming_normal_sign)
    if not isfinite(normal_sign) or abs(abs(normal_sign) - 1.0) > 1.0e-12:
      raise ValueError('incoming_normal_sign must be either -1 or +1')
    ####
    alignment_tolerance = float(self.characteristic_alignment_tolerance)
    if not isfinite(alignment_tolerance) or alignment_tolerance <= 0.0:
      raise ValueError(
        'characteristic_alignment_tolerance must be finite and positive'
      )
    ####
    object.__setattr__(self, 'incoming_normal_sign', normal_sign)
    object.__setattr__(
      self,
      'characteristic_alignment_tolerance',
      alignment_tolerance,
    )
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_MODEL,
      'interface_operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_TRANSONIC_INTERFACE_OPERATOR_ID
      ),
      'interface_status': self.transonic_interface.status.value,
      'interface_audit_status': self.transonic_interface_audit.status.value,
      'require_incoming_characteristic': self.require_incoming_characteristic,
      'require_normal_closure': self.require_normal_closure,
      'incoming_family': self.incoming_family.value,
      'incoming_normal_sign': self.incoming_normal_sign,
      'characteristic_alignment_tolerance': (
        self.characteristic_alignment_tolerance
      ),
      'source': self.source,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult:
  """Audited local handoff with canonical equation claims still closed."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest | None
  subsonic_sample_indices: tuple[int, ...] = ()
  supersonic_sample_indices: tuple[int, ...] = ()
  incoming_characteristic_indices: tuple[int, ...] = ()
  outgoing_characteristic_indices: tuple[int, ...] = ()
  interface_lineage_verified: bool = False
  subsonic_boundary_condition_consumed: bool = False
  supersonic_characteristic_data_consumed: bool = False
  incoming_characteristic_count: int = 0
  normal_closure_verified: bool = False
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
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus,
    ):
      raise TypeError('status must be a typed upstream-equation status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest,
    ):
      raise TypeError('request must be a typed upstream-equation request')
    ####
    subsonic = tuple(int(index) for index in self.subsonic_sample_indices)
    supersonic = tuple(int(index) for index in self.supersonic_sample_indices)
    incoming = tuple(int(index) for index in self.incoming_characteristic_indices)
    outgoing = tuple(int(index) for index in self.outgoing_characteristic_indices)
    if any(index < 0 for index in (*subsonic, *supersonic)):
      raise ValueError('sample indices must be nonnegative')
    ####
    if set(subsonic).intersection(supersonic):
      raise ValueError('subsonic and supersonic sample indices must be disjoint')
    ####
    if set(incoming).intersection(outgoing):
      raise ValueError('incoming and outgoing characteristic indices must be disjoint')
    ####
    if not set(incoming).union(outgoing).issubset(set(supersonic)):
      raise ValueError(
        'incoming and outgoing characteristic indices must be supersonic samples'
      )
    ####
    if set(incoming).union(outgoing) != set(supersonic):
      raise ValueError(
        'incoming and outgoing characteristic indices must partition supersonic samples'
      )
    ####
    if (
      isinstance(self.incoming_characteristic_count, bool)
      or not isinstance(self.incoming_characteristic_count, int)
      or self.incoming_characteristic_count < 0
    ):
      raise ValueError('incoming_characteristic_count must be nonnegative')
    ####
    if self.incoming_characteristic_count != len(incoming):
      raise ValueError(
        'incoming_characteristic_count must match the retained incoming sample count'
      )
    ####
    object.__setattr__(self, 'subsonic_sample_indices', subsonic)
    object.__setattr__(self, 'supersonic_sample_indices', supersonic)
    object.__setattr__(self, 'incoming_characteristic_indices', incoming)
    object.__setattr__(self, 'outgoing_characteristic_indices', outgoing)
    for name in (
      'interface_lineage_verified',
      'subsonic_boundary_condition_consumed',
      'supersonic_characteristic_data_consumed',
      'normal_closure_verified',
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
      raise ValueError('upstream-equation handoff cannot claim equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('upstream-equation handoff must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def interface_handoff_verified(self) -> bool:
    return bool(
      self.interface_lineage_verified
      and (
        self.subsonic_boundary_condition_consumed
        or not self.subsonic_sample_indices
      )
      and (
        self.supersonic_characteristic_data_consumed
        or not self.supersonic_sample_indices
      )
    )
  ####

  @property
  def equation_ready(self) -> bool:
    return bool(
      self.interface_handoff_verified
      and self.incoming_characteristic_count > 0
      and self.normal_closure_verified
      and self.upstream_characteristic_equation_consumed
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus
      .ADMITTED_LOCAL_RESEARCH_HANDOFF
      and self.interface_handoff_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID
      ),
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_MODEL,
      'status': self.status.value,
      'converged': self.converged,
      'equation_ready': self.equation_ready,
      'subsonic_sample_indices': self.subsonic_sample_indices,
      'supersonic_sample_indices': self.supersonic_sample_indices,
      'incoming_characteristic_indices': self.incoming_characteristic_indices,
      'outgoing_characteristic_indices': self.outgoing_characteristic_indices,
      'incoming_characteristic_count': self.incoming_characteristic_count,
      'interface_lineage_verified': self.interface_lineage_verified,
      'subsonic_boundary_condition_consumed': (
        self.subsonic_boundary_condition_consumed
      ),
      'supersonic_characteristic_data_consumed': (
        self.supersonic_characteristic_data_consumed
      ),
      'normal_closure_verified': self.normal_closure_verified,
      'upstream_characteristic_equation_consumed': False,
      'free_boundary_equation_consumed': False,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only upstream characteristic-equation handoff; exact '
        'subsonic boundary data are retained, but incoming characteristics and '
        'normal/free-boundary closure must be supplied before equation closure'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit:
  """Independent replay of the typed upstream-equation handoff gate."""

  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult | None
  replay: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult | None
  interface_lineage_replayed: bool = False
  regime_partition_replayed: bool = False
  independent_handoff_verified: bool = False
  upstream_characteristic_equation_consumed: bool = False
  free_boundary_equation_consumed: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAuditStatus,
    ):
      raise TypeError('status must be a typed upstream-equation audit status')
    ####
    for name in ('candidate', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
      ):
        raise TypeError(f'{name} must be a typed upstream-equation result')
      ####
    ####
    for name in (
      'interface_lineage_replayed',
      'regime_partition_replayed',
      'independent_handoff_verified',
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
      raise ValueError('upstream-equation audit cannot claim equation closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('upstream-equation audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAuditStatus
      .VERIFIED_LOCAL_RESEARCH_HANDOFF
      and self.independent_handoff_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_UPSTREAM_CHARACTERISTIC_EQUATION_OPERATOR_ID
      ),
      'audit_status': self.status.value,
      'converged': self.converged,
      'interface_lineage_replayed': self.interface_lineage_replayed,
      'regime_partition_replayed': self.regime_partition_replayed,
      'independent_handoff_verified': self.independent_handoff_verified,
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
  status: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult:
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult(
    status=status,
    request=request,
    message=message,
    **values,
  )
####


def admit_reflected_domain_global_mixed_regime_upstream_characteristic_equation(
  request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult:
  """Admit the interface handoff or return its exact missing-closure stop."""

  status_type = (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationStatus
  )
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed upstream characteristic-equation request',
    )
  ####
  interface = request.transonic_interface
  audit = request.transonic_interface_audit
  if not interface.converged:
    return _failure(
      status_type.INTERFACE_REQUIRED,
      'upstream characteristic-equation admission requires a converged '
      'transonic interface result',
      request=request,
    )
  ####
  if (
    audit.status
    is not MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAuditStatus
    .VERIFIED_LOCAL_RESEARCH_INTERFACE
    or not audit.converged
    or audit.candidate is not interface
  ):
    return _failure(
      status_type.INTERFACE_AUDIT_REQUIRED,
      'upstream characteristic-equation admission requires an independent '
      'audit of the exact transonic interface result',
      request=request,
      interface_lineage_verified=False,
    )
  ####
  subsonic_indices = tuple(
    sample.sample_index
    for sample in interface.flux_samples
    if not sample.characteristic_data_admitted
  )
  supersonic_indices = tuple(
    sample.sample_index
    for sample in interface.flux_samples
    if sample.characteristic_data_admitted
  )
  incoming_indices: list[int] = []
  outgoing_indices: list[int] = []
  for sample in interface.flux_samples:
    characteristic = sample.frame_sample.characteristic_state
    if characteristic is None:
      continue
    ####
    direction = characteristic.direction(request.incoming_family)
    signed_normal_projection = request.incoming_normal_sign * (
      direction[0] * sample.normal_m[0]
      + direction[1] * sample.normal_m[1]
    )
    if (
      isfinite(signed_normal_projection)
      and signed_normal_projection
      > request.characteristic_alignment_tolerance
    ):
      incoming_indices.append(sample.sample_index)
    else:
      outgoing_indices.append(sample.sample_index)
    ####
  ####
  incoming = tuple(incoming_indices)
  outgoing = tuple(outgoing_indices)
  lineage = bool(
    interface.frame_lineage_verified
    and interface.regime_separation_verified
    and interface.component_fluxes_measured
    and interface.entropy_channel_measured
    and audit.independent_interface_verified
  )
  if not lineage:
    return _failure(
      status_type.INTERFACE_LINEAGE_FAILURE,
      'transonic interface did not retain the exact audited regime/flux lineage',
      request=request,
      subsonic_sample_indices=subsonic_indices,
      supersonic_sample_indices=supersonic_indices,
      incoming_characteristic_indices=incoming,
      outgoing_characteristic_indices=outgoing,
      interface_lineage_verified=False,
      subsonic_boundary_condition_consumed=bool(subsonic_indices),
      supersonic_characteristic_data_consumed=bool(supersonic_indices),
      incoming_characteristic_count=len(incoming),
    )
  ####
  if request.require_incoming_characteristic and not incoming:
    return _failure(
      status_type.MISSING_INCOMING_CHARACTERISTIC,
      'the exact interface supplies no incoming genuinely supersonic '
      'characteristic for the upstream equation; the frame contains '
      f'{len(supersonic_indices)} supersonic and {len(outgoing)} outgoing '
      'characteristic samples',
      request=request,
      subsonic_sample_indices=subsonic_indices,
      supersonic_sample_indices=supersonic_indices,
      incoming_characteristic_indices=incoming,
      outgoing_characteristic_indices=outgoing,
      interface_lineage_verified=True,
      subsonic_boundary_condition_consumed=bool(subsonic_indices),
      supersonic_characteristic_data_consumed=bool(supersonic_indices),
      incoming_characteristic_count=0,
    )
  ####
  if request.require_normal_closure:
    return _failure(
      status_type.NORMAL_CLOSURE_REQUIRED,
      'the interface provides primitive subsonic and optional supersonic '
      'data, but no solver-owned normal/free-boundary closure has been '
      'consumed by the upstream equation',
      request=request,
      subsonic_sample_indices=subsonic_indices,
      supersonic_sample_indices=supersonic_indices,
      incoming_characteristic_indices=incoming,
      outgoing_characteristic_indices=outgoing,
      interface_lineage_verified=True,
      subsonic_boundary_condition_consumed=bool(subsonic_indices),
      supersonic_characteristic_data_consumed=bool(supersonic_indices),
      incoming_characteristic_count=len(incoming),
    )
  ####
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult(
    status=status_type.ADMITTED_LOCAL_RESEARCH_HANDOFF,
    request=request,
    subsonic_sample_indices=subsonic_indices,
    supersonic_sample_indices=supersonic_indices,
    incoming_characteristic_indices=incoming,
    outgoing_characteristic_indices=outgoing,
    interface_lineage_verified=True,
    subsonic_boundary_condition_consumed=bool(subsonic_indices),
    supersonic_characteristic_data_consumed=bool(supersonic_indices),
    incoming_characteristic_count=len(incoming),
    normal_closure_verified=False,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'audited interface handoff is retained for the next equation; canonical '
      'normal/free-boundary closure remains an explicit later gate'
    ),
  )
####


def audit_reflected_domain_global_mixed_regime_upstream_characteristic_equation(
  result: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
) -> MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit:
  """Replay the exact interface audit and regime partition."""

  audit_status = (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAuditStatus
  )
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      replay=None,
      message='result must be a typed upstream characteristic-equation result',
    )
  ####
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message='upstream characteristic-equation replay requires the request frame',
    )
  ####
  try:
    replay = admit_reflected_domain_global_mixed_regime_upstream_characteristic_equation(
      result.request
    )
  except (ArithmeticError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=f'independent upstream characteristic-equation replay raised: {error}',
    )
  ####
  lineage = bool(
    replay.request is result.request
    and replay.interface_lineage_verified == result.interface_lineage_verified
  )
  partition = bool(
    replay.subsonic_sample_indices == result.subsonic_sample_indices
    and replay.supersonic_sample_indices == result.supersonic_sample_indices
    and replay.incoming_characteristic_indices
    == result.incoming_characteristic_indices
    and replay.outgoing_characteristic_indices
    == result.outgoing_characteristic_indices
    and replay.incoming_characteristic_count
    == result.incoming_characteristic_count
  )
  independent = bool(
    lineage
    and partition
    and replay.status is result.status
    and replay.subsonic_boundary_condition_consumed
    == result.subsonic_boundary_condition_consumed
    and replay.supersonic_characteristic_data_consumed
    == result.supersonic_characteristic_data_consumed
  )
  return MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit(
    status=(
      audit_status.VERIFIED_LOCAL_RESEARCH_HANDOFF
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    replay=replay,
    interface_lineage_replayed=lineage,
    regime_partition_replayed=partition,
    independent_handoff_verified=independent,
    upstream_characteristic_equation_consumed=False,
    free_boundary_equation_consumed=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact audited interface handoff and '
      'subsonic/supersonic partition'
      if independent
      else 'independent replay did not reproduce the exact interface handoff'
    ),
  )
####
