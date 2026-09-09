"""Typed entropy/mixing closure contract for the mixed-wave research lane.

The mixed-wave downstream field exposes a real pressure-budget deficit: its
subsonic branch cannot reach the retained ambient target without additional
total-pressure loss.  This module makes the missing physics an explicit input
contract and now provides a bounded research consumer for it.  A profile must
carry its exact upstream lineage, an ordered total-pressure loss law, and the
static-pressure targets that the coupled field consumes.

The consumer is deliberately a fixed-velocity/fixed-temperature relaxation
source.  It is useful for exercising the joint field, residual, and audit
seams, but it is not a physical mixing closure and cannot promote a downstream
field or a shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  solve_reflected_domain_coupled_euler_free_boundary,
)

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_downstream import (
  MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryAudit,
  measure_reflected_domain_coupled_euler_free_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_ENTROPY_CLOSURE_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile',
  'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult',
  'build_reflected_domain_global_transonic_mixed_wave_entropy_closure_profile',
  'audit_reflected_domain_global_transonic_mixed_wave_entropy_closure',
  'solve_reflected_domain_global_transonic_mixed_wave_entropy_closure',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_ENTROPY_CLOSURE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-entropy-closure'
)
DEFAULT_ENTROPY_CLOSURE_PROFILE_SOURCE = (
  'solver-owned-mixed-wave-entropy-loss-profile-v1'
)


class MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus(
  str,
  Enum,
):
  """Outcome of the explicit entropy/mixing closure contract audit."""

  PROFILE_READY_FOR_JOINT_SOLVER = (
    'mixed-wave-entropy-profile-ready-for-joint-interface-field-solver'
  )
  INVALID_INPUT = 'invalid_input'
  DOWNSTREAM_SEAM_REQUIRED = (
    'mixed-wave-entropy-closure-downstream-seam-required'
  )
  LINEAGE_FAILURE = 'mixed-wave-entropy-closure-lineage-failure'
  TARGET_PROFILE_FAILURE = 'mixed-wave-entropy-closure-target-profile-failure'
  LOSS_BUDGET_FAILURE = 'mixed-wave-entropy-closure-loss-budget-failure'
  JOINT_FIELD_CONSUMER_REQUIRED = (
    'mixed-wave-entropy-closure-joint-field-consumer-required'
  )
  JOINT_FIELD_RESEARCH_RESULT = (
    'mixed-wave-entropy-closure-joint-field-research-result'
  )
  JOINT_FIELD_FAILURE = 'mixed-wave-entropy-closure-joint-field-failure'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile:
  """An explicit, solver-owned total-pressure loss profile.

  The profile is a proposed physical mechanism, not a result.  Its total
  pressure is required to be ordered and non-increasing; its static-pressure
  targets are retained separately because the free boundary and entropy law
  are different equations.  No default distribution, endpoint hold, or
  interpolation is inferred here.
  """

  source_closure_fingerprint: str
  source_perimeter_contract_source: str
  x_stations_m: tuple[float, ...]
  total_pressure_Pa: tuple[float, ...]
  target_static_pressure_Pa: tuple[float, ...]
  reference_total_pressure_Pa: float
  additional_total_pressure_loss_fraction: float
  minimum_required_total_pressure_loss_fraction: float
  relaxation_fraction: float = 0.25
  mechanism_id: str = DEFAULT_ENTROPY_CLOSURE_PROFILE_SOURCE
  source: str = DEFAULT_ENTROPY_CLOSURE_PROFILE_SOURCE

  def __post_init__(self) -> None:
    closure_fingerprint = str(self.source_closure_fingerprint)
    if not closure_fingerprint:
      raise ValueError('source_closure_fingerprint must be non-empty')
    object.__setattr__(self, 'source_closure_fingerprint', closure_fingerprint)

    contract_source = str(self.source_perimeter_contract_source)
    if not contract_source:
      raise ValueError('source_perimeter_contract_source must be non-empty')
    object.__setattr__(self, 'source_perimeter_contract_source', contract_source)

    x_stations = tuple(float(value) for value in self.x_stations_m)
    total_pressures = tuple(float(value) for value in self.total_pressure_Pa)
    static_targets = tuple(
      float(value) for value in self.target_static_pressure_Pa
    )
    if len(x_stations) < 2:
      raise ValueError('entropy closure profile requires at least two stations')
    if not (len(x_stations) == len(total_pressures) == len(static_targets)):
      raise ValueError(
        'entropy closure coordinates, total pressures, and static targets '
        'must have equal lengths'
      )
    if any(not isfinite(value) for value in x_stations):
      raise ValueError('x_stations_m must contain finite values')
    if any(
      second <= first
      for first, second in zip(x_stations, x_stations[1:])
    ):
      raise ValueError('x_stations_m must be strictly downstream ordered')
    if any(
      not isfinite(value) or value <= 0.0
      for value in (*total_pressures, *static_targets)
    ):
      raise ValueError(
        'entropy closure pressures must be finite and strictly positive'
      )
    if any(
      second > first * (1.0 + 1.0e-10)
      for first, second in zip(total_pressures, total_pressures[1:])
    ):
      raise ValueError(
        'total_pressure_Pa must be non-increasing; entropy closure cannot '
        'invent a total-pressure gain'
      )
    object.__setattr__(self, 'x_stations_m', x_stations)
    object.__setattr__(self, 'total_pressure_Pa', total_pressures)
    object.__setattr__(self, 'target_static_pressure_Pa', static_targets)

    reference_pressure = float(self.reference_total_pressure_Pa)
    if not isfinite(reference_pressure) or reference_pressure <= 0.0:
      raise ValueError(
        'reference_total_pressure_Pa must be finite and strictly positive'
      )
    if abs(reference_pressure - total_pressures[0]) > 1.0e-10 * max(
      reference_pressure,
      total_pressures[0],
      1.0,
    ):
      raise ValueError(
        'reference_total_pressure_Pa must match the first profile sample'
      )
    object.__setattr__(self, 'reference_total_pressure_Pa', reference_pressure)

    loss_fraction = float(self.additional_total_pressure_loss_fraction)
    minimum_loss = float(self.minimum_required_total_pressure_loss_fraction)
    for name, value in (
      ('additional_total_pressure_loss_fraction', loss_fraction),
      ('minimum_required_total_pressure_loss_fraction', minimum_loss),
    ):
      if not isfinite(value) or not 0.0 <= value < 1.0:
        raise ValueError(f'{name} must be finite and in the [0, 1) interval')
    ####
    measured_loss = 1.0 - total_pressures[-1] / total_pressures[0]
    if abs(measured_loss - loss_fraction) > 1.0e-9:
      raise ValueError(
        'additional_total_pressure_loss_fraction must match the retained '
        'profile endpoints'
      )
    ####
    object.__setattr__(
      self,
      'additional_total_pressure_loss_fraction',
      loss_fraction,
    )
    object.__setattr__(
      self,
      'minimum_required_total_pressure_loss_fraction',
      minimum_loss,
    )

    relaxation_fraction = float(self.relaxation_fraction)
    if not isfinite(relaxation_fraction) or not 0.0 < relaxation_fraction <= 1.0:
      raise ValueError(
        'relaxation_fraction must be finite and in the (0, 1] interval'
      )
    object.__setattr__(self, 'relaxation_fraction', relaxation_fraction)

    mechanism_id = str(self.mechanism_id)
    source = str(self.source)
    if not mechanism_id or not source:
      raise ValueError('mechanism_id and source must be non-empty')
    object.__setattr__(self, 'mechanism_id', mechanism_id)
    object.__setattr__(self, 'source', source)

  @property
  def budget_satisfied(self) -> bool:
    """Whether the declared profile supplies at least the measured budget."""

    return bool(
      self.additional_total_pressure_loss_fraction
      + 1.0e-10
      >= self.minimum_required_total_pressure_loss_fraction
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'mechanism_id': self.mechanism_id,
      'source': self.source,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_perimeter_contract_source': self.source_perimeter_contract_source,
      'x_stations_m': self.x_stations_m,
      'total_pressure_Pa': self.total_pressure_Pa,
      'target_static_pressure_Pa': self.target_static_pressure_Pa,
      'reference_total_pressure_Pa': self.reference_total_pressure_Pa,
      'additional_total_pressure_loss_fraction': (
        self.additional_total_pressure_loss_fraction
      ),
      'minimum_required_total_pressure_loss_fraction': (
        self.minimum_required_total_pressure_loss_fraction
      ),
      'relaxation_fraction': self.relaxation_fraction,
      'budget_satisfied': self.budget_satisfied,
      'claim_status': (
        'research-only-declared-entropy-loss-profile; it is not a field '
        'solution, validation result, or production closure'
      ),
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult:
  """Audit result that keeps the joint-field promotion gate explicit."""

  status: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult | None
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile | None
  source_closure_fingerprint: str = ''
  profile_lineage_verified: bool = False
  coordinate_profile_verified: bool = False
  target_profile_verified: bool = False
  pressure_budget_verified: bool = False
  joint_field_consumer_available: bool = False
  joint_field_consumed: bool = False
  joint_field_result: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None
  joint_field_audit: MocReflectedDomainCoupledEulerFreeBoundaryAudit | None = None
  local_closure_verified: bool = False
  centerline_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus,
    ):
      raise TypeError('status must be a typed entropy-closure status')
    if self.downstream is not None and not isinstance(
      self.downstream,
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
    ):
      raise TypeError(
        'downstream must be a '
        'MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult or None'
      )
    if self.profile is not None and not isinstance(
      self.profile,
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
    ):
      raise TypeError(
        'profile must be a '
        'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile or None'
      )
    if self.joint_field_result is not None and not isinstance(
      self.joint_field_result,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError(
        'joint_field_result must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryResult or None'
      )
    if self.joint_field_audit is not None and not isinstance(
      self.joint_field_audit,
      MocReflectedDomainCoupledEulerFreeBoundaryAudit,
    ):
      raise TypeError(
        'joint_field_audit must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryAudit or None'
      )
    ####
    fingerprint = str(self.source_closure_fingerprint)
    if self.downstream is not None and self.profile is not None and not fingerprint:
      raise ValueError(
        'source_closure_fingerprint must be retained when an entropy profile '
        'is audited'
      )
    object.__setattr__(self, 'source_closure_fingerprint', fingerprint)
    for name in (
      'profile_lineage_verified',
      'coordinate_profile_verified',
      'target_profile_verified',
      'pressure_budget_verified',
      'joint_field_consumer_available',
      'joint_field_consumed',
      'local_closure_verified',
      'centerline_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('entropy-closure research evidence must block promotion')
    if self.production_claim_allowed:
      raise ValueError('entropy-closure research evidence cannot allow production')
    if self.joint_field_consumed and self.joint_field_result is None:
      raise ValueError(
        'joint_field_consumed requires a retained coupled-field result'
      )
    if self.local_closure_verified and not self.joint_field_consumed:
      raise ValueError(
        'local_closure_verified requires a consumed joint field'
      )
    object.__setattr__(self, 'message', str(self.message))

  @property
  def profile_ready_for_joint_solver(self) -> bool:
    """Whether the declared mechanism passed its pre-consumer audit."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .PROFILE_READY_FOR_JOINT_SOLVER
      and self.profile is not None
      and self.profile_lineage_verified
      and self.coordinate_profile_verified
      and self.target_profile_verified
      and self.pressure_budget_verified
      and not self.joint_field_consumer_available
      and not self.joint_field_consumed
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  @property
  def physical_closure_verified(self) -> bool:
    """The research consumer is never a canonical physical closure."""

    return False

  @property
  def joint_field_research_verified(self) -> bool:
    """Whether the consumed field passed its local independent audit."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .JOINT_FIELD_RESEARCH_RESULT
      and self.joint_field_consumer_available
      and self.joint_field_consumed
      and self.joint_field_result is not None
      and self.joint_field_audit is not None
      and self.joint_field_audit.local_consistency_verified
      and self.local_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_ENTROPY_CLOSURE_OPERATOR_ID,
      'status': self.status.value,
      'profile_ready_for_joint_solver': self.profile_ready_for_joint_solver,
      'physical_closure_verified': self.physical_closure_verified,
      'joint_field_research_verified': self.joint_field_research_verified,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'profile_lineage_verified': self.profile_lineage_verified,
      'coordinate_profile_verified': self.coordinate_profile_verified,
      'target_profile_verified': self.target_profile_verified,
      'pressure_budget_verified': self.pressure_budget_verified,
      'joint_field_consumer_available': self.joint_field_consumer_available,
      'joint_field_consumed': self.joint_field_consumed,
      'joint_field_result': (
        None
        if self.joint_field_result is None
        else self.joint_field_result.as_report()
      ),
      'joint_field_audit': (
        None
        if self.joint_field_audit is None
        else self.joint_field_audit.as_report()
      ),
      'local_closure_verified': self.local_closure_verified,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'downstream': (
        None if self.downstream is None else self.downstream.as_report()
      ),
      'profile': None if self.profile is None else self.profile.as_report(),
      'claim_status': (
        'research-only-entropy-profile-and-relaxation-consumer; the '
        'relaxation is not a physical mixing closure, and canonical '
        'promotion, refinement, and external validation remain required'
      ),
      'message': self.message,
    }


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus,
  message: str,
  *,
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult | None = None,
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile | None = None,
  source_closure_fingerprint: str = '',
  profile_lineage_verified: bool = False,
  coordinate_profile_verified: bool = False,
  target_profile_verified: bool = False,
  pressure_budget_verified: bool = False,
) -> MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult:
  return MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult(
    status=status,
    downstream=downstream,
    profile=profile,
    source_closure_fingerprint=source_closure_fingerprint,
    profile_lineage_verified=profile_lineage_verified,
    coordinate_profile_verified=coordinate_profile_verified,
    target_profile_verified=target_profile_verified,
    pressure_budget_verified=pressure_budget_verified,
    message=message,
  )


def _downstream_context(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
) -> tuple[
  MocReflectedDomainGlobalPhysicalClosureResult,
  str,
  float,
  float,
]:
  if downstream.closure is None or downstream.interface is None:
    raise ValueError('downstream result retained no closure/interface context')
  if downstream.request is None or downstream.field is None:
    raise ValueError(
      'downstream result retained no coupled-field request/result for the '
      'joint entropy profile'
    )
  if downstream.subsonic_pressure_budget is None:
    raise ValueError('downstream result retained no subsonic pressure budget')
  contract_source = downstream.request.perimeter_contract_source
  if contract_source is None:
    raise ValueError('downstream request retained no perimeter contract source')
  return (
    downstream.closure,
    str(contract_source),
    float(downstream.subsonic_pressure_budget.reference_total_pressure_Pa),
    float(
      downstream.subsonic_pressure_budget.minimum_additional_total_pressure_loss_fraction
    ),
  )


def solve_reflected_domain_global_transonic_mixed_wave_entropy_closure(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
) -> MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult:
  """Consume one audited loss profile in the bounded coupled field.

  The solver receives the exact downstream request retained by ``downstream``
  with two explicit, aligned inputs: the ambient static-pressure profile for
  the free boundary and the entropy-profile relaxation source.  The returned
  result retains both the candidate field and a separate validator result.
  Even when both local checks pass, this function remains research-only because
  the relaxation law is not an independently validated physical mixing model.
  """

  preflight = audit_reflected_domain_global_transonic_mixed_wave_entropy_closure(
    downstream,
    profile,
  )
  if not preflight.profile_ready_for_joint_solver:
    return replace(
      preflight,
      joint_field_consumer_available=True,
      message=(
        f'{preflight.message}; joint-field consumer was not run because the '
        'explicit entropy profile did not pass its preflight contract'
      ),
    )
  ####
  field = downstream.field
  if field is None or field.request is None:
    return replace(
      preflight,
      status=(
        MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
        .JOINT_FIELD_FAILURE
      ),
      joint_field_consumer_available=True,
      message=(
        'the audited downstream seam retained no coupled-field request for '
        'the entropy-profile consumer'
      ),
    )
  ####
  coupled_request = field.request
  if not isinstance(
    coupled_request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    return replace(
      preflight,
      status=(
        MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
        .JOINT_FIELD_FAILURE
      ),
      joint_field_consumer_available=True,
      message='retained downstream field request is not a typed coupled-Euler request',
    )
  ####
  try:
    consumed_request = replace(
      coupled_request,
      entropy_closure_profile=profile,
      free_boundary_pressure_profile_Pa=profile.target_static_pressure_Pa,
      free_boundary_pressure_profile_x_stations_m=profile.x_stations_m,
      free_boundary_pressure_profile_source=(
        f'{profile.source}:static-target'
      ),
    )
  except (ArithmeticError, TypeError, ValueError) as error:
    return replace(
      preflight,
      status=(
        MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
        .JOINT_FIELD_FAILURE
      ),
      joint_field_consumer_available=True,
      message=f'entropy-profile coupled request construction failed: {error}',
    )
  ####
  try:
    candidate = solve_reflected_domain_coupled_euler_free_boundary(
      consumed_request
    )
    independent_audit = measure_reflected_domain_coupled_euler_free_boundary(
      candidate
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return replace(
      preflight,
      status=(
        MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
        .JOINT_FIELD_FAILURE
      ),
      joint_field_consumer_available=True,
      message=f'entropy-profile coupled field or audit failed: {error}',
    )
  ####
  consumed = bool(
    candidate.request is consumed_request
    and candidate.entropy_closure_profile_consumed
    and candidate.request.entropy_closure_profile is profile
  )
  local_verified = bool(
    consumed
    and candidate.local_physical_closure_verified
    and candidate.entropy_closure_profile_verified
    and independent_audit.local_consistency_verified
  )
  status = (
    MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
    .JOINT_FIELD_RESEARCH_RESULT
    if local_verified
    else MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
    .JOINT_FIELD_FAILURE
  )
  message = (
    'the coupled field consumed the exact entropy profile and its independent '
    'local audit passed; the relaxation law remains research-only and all '
    'canonical, chain, and production gates remain blocked'
    if local_verified
    else (
      'the coupled field consumed the exact entropy profile, but its local '
      'solver or independent audit did not pass every required check; '
      f'solver={candidate.status.value}, audit={independent_audit.status.value}'
    )
  )
  return replace(
    preflight,
    status=status,
    joint_field_consumer_available=True,
    joint_field_consumed=consumed,
    joint_field_result=candidate,
    joint_field_audit=independent_audit,
    local_closure_verified=local_verified,
    centerline_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )


def build_reflected_domain_global_transonic_mixed_wave_entropy_closure_profile(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  *,
  x_stations_m: tuple[float, ...],
  total_pressure_Pa: tuple[float, ...],
  target_static_pressure_Pa: tuple[float, ...],
  relaxation_fraction: float = 0.25,
  mechanism_id: str = DEFAULT_ENTROPY_CLOSURE_PROFILE_SOURCE,
  source: str = DEFAULT_ENTROPY_CLOSURE_PROFILE_SOURCE,
) -> MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile:
  """Bind an explicit loss law to the exact mixed-wave downstream seam.

  All stations, loss values, and static targets are caller-supplied.  This
  builder intentionally does not construct a profile from the budget because
  choosing a spatial entropy distribution is part of the missing physics.
  """

  if not isinstance(
    downstream,
    MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  ):
    raise TypeError(
      'downstream must be a '
      'MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult'
    )
  try:
    closure, contract_source, reference_pressure, minimum_loss = (
      _downstream_context(downstream)
    )
  except (TypeError, ValueError) as error:
    raise ValueError(str(error)) from error
  ####
  if downstream.status is not (
    MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
    .ADDITIONAL_ENTROPY_REQUIRED
  ):
    raise ValueError(
      'an explicit entropy profile may only bind to the typed '
      'additional-entropy-required downstream seam'
    )
  ####
  total_pressures = tuple(float(value) for value in total_pressure_Pa)
  if len(total_pressures) < 2 or not total_pressures[0] > 0.0:
    raise ValueError('total_pressure_Pa must contain at least two positive values')
  loss_fraction = 1.0 - total_pressures[-1] / total_pressures[0]
  return MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile(
    source_closure_fingerprint=(
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    source_perimeter_contract_source=contract_source,
    x_stations_m=tuple(x_stations_m),
    total_pressure_Pa=total_pressures,
    target_static_pressure_Pa=tuple(target_static_pressure_Pa),
    reference_total_pressure_Pa=reference_pressure,
    additional_total_pressure_loss_fraction=loss_fraction,
    minimum_required_total_pressure_loss_fraction=minimum_loss,
    relaxation_fraction=relaxation_fraction,
    mechanism_id=mechanism_id,
    source=source,
  )


def audit_reflected_domain_global_transonic_mixed_wave_entropy_closure(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
) -> MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult:
  """Audit one explicit loss profile without pretending to solve the field."""

  if not isinstance(
    downstream,
    MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus.INVALID_INPUT,
      'downstream must be a typed mixed-wave downstream result',
    )
  if not isinstance(
    profile,
    MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus.INVALID_INPUT,
      'profile must be a typed mixed-wave entropy closure profile',
      downstream=downstream,
    )
  ####
  try:
    closure, contract_source, reference_pressure, minimum_loss = (
      _downstream_context(downstream)
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .DOWNSTREAM_SEAM_REQUIRED,
      str(error),
      downstream=downstream,
      profile=profile,
    )
  ####
  fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(closure)
  if downstream.status is not (
    MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
    .ADDITIONAL_ENTROPY_REQUIRED
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .DOWNSTREAM_SEAM_REQUIRED,
      'the typed additional-entropy-required downstream seam is not open',
      downstream=downstream,
      profile=profile,
      source_closure_fingerprint=fingerprint,
    )
  ####
  lineage_verified = bool(
    profile.source_closure_fingerprint == fingerprint
    and profile.source_perimeter_contract_source == contract_source
  )
  if not lineage_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .LINEAGE_FAILURE,
      'entropy profile does not retain the exact global-closure and '
      'perimeter-contract lineage',
      downstream=downstream,
      profile=profile,
      source_closure_fingerprint=fingerprint,
    )
  ####
  budget_verified = bool(
    abs(profile.reference_total_pressure_Pa - reference_pressure)
    <= 1.0e-10 * max(reference_pressure, 1.0)
    and profile.minimum_required_total_pressure_loss_fraction
    >= minimum_loss - 1.0e-10
    and profile.budget_satisfied
  )
  if not budget_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .LOSS_BUDGET_FAILURE,
      'entropy profile does not supply the retained minimum additional '
      f'total-pressure loss budget ({minimum_loss:.6g})',
      downstream=downstream,
      profile=profile,
      source_closure_fingerprint=fingerprint,
      profile_lineage_verified=True,
    )
  ####
  target_pressure = downstream.interface.ambient_pressure_Pa
  if target_pressure is None:
    target_pressure = downstream.request.ambient_pressure_Pa
  target_profile_verified = bool(
    all(
      abs(value - float(target_pressure))
      <= 1.0e-8 * max(abs(float(target_pressure)), 1.0)
      for value in profile.target_static_pressure_Pa
    )
  )
  if not target_profile_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .TARGET_PROFILE_FAILURE,
      'entropy profile static-pressure targets must retain the exact ambient '
      'target at every declared station',
      downstream=downstream,
      profile=profile,
      source_closure_fingerprint=fingerprint,
      profile_lineage_verified=True,
      pressure_budget_verified=True,
    )
  ####
  field = downstream.field
  expected_x = tuple(
    0.5 * (first + second)
    for first, second in zip(field.x_stations_m, field.x_stations_m[1:])
  )
  coordinate_verified = bool(
    len(expected_x) == len(profile.x_stations_m)
    and all(
      abs(actual - expected) <= 1.0e-9 * max(abs(expected), 1.0)
      for actual, expected in zip(profile.x_stations_m, expected_x)
    )
  )
  if not coordinate_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .TARGET_PROFILE_FAILURE,
      'entropy profile stations must match the exact coupled-field cell '
      'centers; no regridding or endpoint extrapolation is accepted',
      downstream=downstream,
      profile=profile,
      source_closure_fingerprint=fingerprint,
      profile_lineage_verified=True,
      target_profile_verified=True,
      pressure_budget_verified=True,
    )
  ####
  return MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult(
    status=(
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus
      .PROFILE_READY_FOR_JOINT_SOLVER
    ),
    downstream=downstream,
    profile=profile,
    source_closure_fingerprint=fingerprint,
    profile_lineage_verified=True,
    coordinate_profile_verified=True,
    target_profile_verified=True,
    pressure_budget_verified=True,
    # The current coupled-Euler request has no total-pressure/entropy profile
    # slot.  Keeping these false is the central safety property of this seam.
    joint_field_consumer_available=False,
    joint_field_consumed=False,
    local_closure_verified=False,
    centerline_boundary_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'the explicit total-pressure loss profile passes exact lineage, station, '
      'ambient-target, and pressure-budget audits; the current coupled-Euler '
      'solver has no equation-level entropy/mixing consumer, so no field solve '
      'was attempted and no closure or promotion claim is made'
    ),
  )
