"""Typed entropy/mixing closure contracts for the mixed-wave research lane.

The mixed-wave downstream field exposes a real pressure-budget deficit: its
subsonic branch cannot reach the retained ambient target without additional
total-pressure loss.  This module makes the missing physics an explicit input
contract and now provides a bounded research consumer for it.  A profile must
carry its exact upstream lineage, an ordered total-pressure loss law, and the
static-pressure targets that the coupled field consumes.

The original consumer is deliberately a fixed-velocity/fixed-temperature
relaxation source.  It remains available as a research baseline.  This module
also exposes an explicit conservative ambient-entrainment source contract:
the source state is a convex conservative mixture with a caller-supplied
ambient thermodynamic state and station-wise entrainment fraction.  That
mechanism is still research-only until the coupled free-boundary equations,
refinement ladder, and provider validation accept it.
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
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_JOINT_FIELD_OPERATOR_ID',
  'CONSERVATIVE_AMBIENT_ENTRAINMENT_MECHANISM_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile',
  'MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureResult',
  'MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration',
  'MocReflectedDomainGlobalTransonicMixedWaveJointFieldResult',
  'build_reflected_domain_global_transonic_mixed_wave_entropy_closure_profile',
  'build_reflected_domain_global_transonic_mixed_wave_ambient_entrainment_profile',
  'audit_reflected_domain_global_transonic_mixed_wave_entropy_closure',
  'solve_reflected_domain_global_transonic_mixed_wave_entropy_closure',
  'solve_reflected_domain_global_transonic_mixed_wave_joint_field',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_ENTROPY_CLOSURE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-entropy-closure'
)
MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_JOINT_FIELD_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-joint-interface-field'
)
DEFAULT_ENTROPY_CLOSURE_PROFILE_SOURCE = (
  'solver-owned-mixed-wave-entropy-loss-profile-v1'
)
CONSERVATIVE_AMBIENT_ENTRAINMENT_MECHANISM_ID = (
  'solver-owned-conservative-ambient-entrainment-v1'
)
DEFAULT_AMBIENT_ENTRAINMENT_PROFILE_SOURCE = (
  'solver-owned-conservative-ambient-entrainment-profile-v1'
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
  ambient_temperature_K: float | None = None
  ambient_velocity_m_s: tuple[float, float] | None = None
  entrainment_fraction_by_station: tuple[float, ...] = ()
  ambient_temperature_K_by_station: tuple[float, ...] | None = None
  ambient_velocity_m_s_by_station: tuple[tuple[float, float], ...] | None = None

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
    ####
    ambient_temperature = self.ambient_temperature_K
    ambient_velocity = self.ambient_velocity_m_s
    ambient_temperature_by_station = self.ambient_temperature_K_by_station
    ambient_velocity_by_station = self.ambient_velocity_m_s_by_station
    entrainment = tuple(
      float(value) for value in self.entrainment_fraction_by_station
    )
    if mechanism_id == CONSERVATIVE_AMBIENT_ENTRAINMENT_MECHANISM_ID:
      if (ambient_temperature is None) == (ambient_temperature_by_station is None):
        raise ValueError(
          'conservative ambient entrainment requires exactly one of scalar '
          'or station-resolved ambient temperatures'
        )
      if (ambient_velocity is None) == (ambient_velocity_by_station is None):
        raise ValueError(
          'conservative ambient entrainment requires exactly one of scalar '
          'or station-resolved ambient velocities'
        )
      if ambient_temperature_by_station is not None:
        ambient_temperature_by_station = tuple(
          float(value) for value in ambient_temperature_by_station
        )
        if len(ambient_temperature_by_station) != len(x_stations):
          raise ValueError(
            'ambient_temperature_K_by_station must align with x_stations_m'
          )
        if any(
          not isfinite(value) or value <= 0.0
          for value in ambient_temperature_by_station
        ):
          raise ValueError(
            'ambient_temperature_K_by_station must contain finite positive '
            'values'
          )
        object.__setattr__(
          self,
          'ambient_temperature_K_by_station',
          ambient_temperature_by_station,
        )
      else:
        ambient_temperature = float(ambient_temperature)
        if not isfinite(ambient_temperature) or ambient_temperature <= 0.0:
          raise ValueError(
            'ambient_temperature_K must be finite and strictly positive'
          )
      if ambient_velocity_by_station is not None:
        ambient_velocity_by_station = tuple(
          tuple(float(component) for component in value)
          for value in ambient_velocity_by_station
        )
        if len(ambient_velocity_by_station) != len(x_stations):
          raise ValueError(
            'ambient_velocity_m_s_by_station must align with x_stations_m'
          )
        if any(
          len(value) != 2 or any(not isfinite(component) for component in value)
          for value in ambient_velocity_by_station
        ):
          raise ValueError(
            'ambient_velocity_m_s_by_station must contain finite two-component '
            'values'
          )
        object.__setattr__(
          self,
          'ambient_velocity_m_s_by_station',
          ambient_velocity_by_station,
        )
      else:
        ambient_velocity = tuple(float(value) for value in ambient_velocity)
        if len(ambient_velocity) != 2 or any(
          not isfinite(value) for value in ambient_velocity
        ):
          raise ValueError(
            'ambient_velocity_m_s must contain two finite values'
          )
      if len(entrainment) != len(x_stations):
        raise ValueError(
          'entrainment_fraction_by_station must align with x_stations_m'
        )
      if any(
        not isfinite(value) or not 0.0 <= value <= 1.0
        for value in entrainment
      ):
        raise ValueError(
          'entrainment_fraction_by_station must contain values in [0, 1]'
        )
      if not any(value > 0.0 for value in entrainment):
        raise ValueError(
          'conservative ambient entrainment requires a nonzero entrainment '
          'fraction at at least one station'
        )
      object.__setattr__(self, 'ambient_temperature_K', ambient_temperature)
      object.__setattr__(self, 'ambient_velocity_m_s', ambient_velocity)
    else:
      if (
        ambient_temperature is not None
        or ambient_velocity is not None
        or ambient_temperature_by_station is not None
        or ambient_velocity_by_station is not None
        or entrainment
      ):
        raise ValueError(
          'ambient entrainment inputs require the conservative ambient '
          'entrainment mechanism id'
        )
      ambient_temperature = None
      ambient_velocity = None
      ambient_temperature_by_station = None
      ambient_velocity_by_station = None
      entrainment = ()
    object.__setattr__(self, 'entrainment_fraction_by_station', entrainment)
    object.__setattr__(
      self,
      'ambient_temperature_K_by_station',
      ambient_temperature_by_station,
    )
    object.__setattr__(
      self,
      'ambient_velocity_m_s_by_station',
      ambient_velocity_by_station,
    )

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
      'ambient_temperature_K': self.ambient_temperature_K,
      'ambient_velocity_m_s': self.ambient_velocity_m_s,
      'entrainment_fraction_by_station': self.entrainment_fraction_by_station,
      'ambient_temperature_K_by_station': self.ambient_temperature_K_by_station,
      'ambient_velocity_m_s_by_station': self.ambient_velocity_m_s_by_station,
      'budget_satisfied': self.budget_satisfied,
      'claim_status': (
        'research-only declared entropy/mixing source; it is not a field '
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


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveJointFieldResult:
  """Research-only result for the coupled source/interface iteration."""

  status: MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult | None
  initial_profile: (
    MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile | None
  )
  iterations: tuple[
    MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration, ...
  ] = ()
  requested_iterations: int = 0
  source_closure_fingerprint: str = ''
  profile_lineage_verified: bool = False
  interface_placement_lineage_verified: bool = False
  interface_placement_coverage_verified: bool = False
  independent_iteration_audits_verified: bool = False
  joint_field_consumed: bool = False
  local_joint_boundary_verified: bool = False
  physical_closure_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus,
    ):
      raise TypeError('status must be a typed joint-field status')
    if self.downstream is not None and not isinstance(
      self.downstream,
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
    ):
      raise TypeError('downstream must be a typed downstream result or None')
    if self.initial_profile is not None and not isinstance(
      self.initial_profile,
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
    ):
      raise TypeError('initial_profile must be a typed entropy profile or None')
    iterations = tuple(self.iterations)
    if any(
      not isinstance(
        item,
        MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration,
      )
      for item in iterations
    ):
      raise TypeError('iterations must contain typed joint-field iterations')
    if tuple(item.iteration_index for item in iterations) != tuple(
      range(len(iterations))
    ):
      raise ValueError('iterations must have contiguous zero-based indices')
    if (
      isinstance(self.requested_iterations, bool)
      or not isinstance(self.requested_iterations, int)
      or self.requested_iterations < 0
    ):
      raise ValueError('requested_iterations must be a nonnegative integer')
    if len(iterations) > self.requested_iterations:
      raise ValueError('iterations cannot exceed requested_iterations')
    object.__setattr__(self, 'iterations', iterations)
    object.__setattr__(
      self,
      'source_closure_fingerprint',
      str(self.source_closure_fingerprint),
    )
    for name in (
      'profile_lineage_verified',
      'interface_placement_lineage_verified',
      'interface_placement_coverage_verified',
      'independent_iteration_audits_verified',
      'joint_field_consumed',
      'local_joint_boundary_verified',
      'physical_closure_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_closure_verified:
      raise ValueError('joint research evidence cannot claim physical closure')
    if self.global_coupling_verified:
      raise ValueError('joint research evidence cannot claim global coupling')
    if not self.chain_promotion_blocked:
      raise ValueError('joint research evidence must block chain promotion')
    if self.production_claim_allowed:
      raise ValueError('joint research evidence cannot allow production claims')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
      .CONVERGED_RESEARCH_ITERATION
    )

  @property
  def final_profile(
    self,
  ) -> MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile | None:
    return None if not self.iterations else self.iterations[-1].profile

  @property
  def joint_field_research_verified(self) -> bool:
    """Whether every local and interface-coverage gate passed."""

    return bool(
      self.converged
      and self.joint_field_consumed
      and self.profile_lineage_verified
      and self.interface_placement_lineage_verified
      and self.interface_placement_coverage_verified
      and self.independent_iteration_audits_verified
      and self.local_joint_boundary_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_JOINT_FIELD_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'joint_field_research_verified': self.joint_field_research_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'profile_lineage_verified': self.profile_lineage_verified,
      'interface_placement_lineage_verified': (
        self.interface_placement_lineage_verified
      ),
      'interface_placement_coverage_verified': (
        self.interface_placement_coverage_verified
      ),
      'independent_iteration_audits_verified': (
        self.independent_iteration_audits_verified
      ),
      'joint_field_consumed': self.joint_field_consumed,
      'local_joint_boundary_verified': self.local_joint_boundary_verified,
      'requested_iterations': self.requested_iterations,
      'iteration_count': len(self.iterations),
      'initial_profile': (
        None
        if self.initial_profile is None
        else self.initial_profile.as_report()
      ),
      'final_profile': (
        None if self.final_profile is None else self.final_profile.as_report()
      ),
      'iterations': tuple(item.as_report() for item in self.iterations),
      'downstream': (
        None if self.downstream is None else self.downstream.as_report()
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': (
        'research-only conservative ambient source/interface/free-boundary '
        'iteration; canonical closure, external validation, shock-cell '
        'promotion, and production claims remain blocked'
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class _JointFieldMetrics:
  pressure_residual_fraction_by_station: tuple[float, ...]
  total_pressure_residual_fraction_by_station: tuple[float, ...]
  signed_update_error_by_station: tuple[float, ...]
  maximum_pressure_residual_fraction: float | None
  maximum_total_pressure_residual_fraction: float | None
  maximum_normal_velocity_residual_fraction: float | None
  maximum_centerline_normal_velocity_residual_fraction: float | None
  maximum_euler_residual: float | None
  objective: float | None


def _joint_field_metrics(
  field: MocReflectedDomainCoupledEulerFreeBoundaryResult,
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
) -> _JointFieldMetrics:
  """Measure boundary and total-pressure errors for one source update."""

  targets = tuple(float(value) for value in profile.target_static_pressure_Pa)
  actual_boundary = tuple(
    float(value) for value in field.free_boundary_adjacent_static_pressure_Pa
  )
  if len(actual_boundary) != len(targets):
    return _JointFieldMetrics((), (), (), None, None, None, None, None, None)
  ####
  boundary_signed = tuple(
    (actual - target) / max(abs(target), 1.0)
    for actual, target in zip(actual_boundary, targets, strict=True)
  )
  boundary_residual = tuple(abs(value) for value in boundary_signed)
  ####
  total_pressure = ()
  request = field.request
  if request is not None:
    expected_count = request.axial_cell_count * request.transverse_cell_count
    retained = tuple(float(value) for value in field.total_pressure_by_cell_Pa)
    if len(retained) == expected_count:
      column_means = tuple(
        sum(
          retained[index * request.transverse_cell_count + transverse]
          for transverse in range(request.transverse_cell_count)
        )
        / request.transverse_cell_count
        for index in range(request.axial_cell_count)
      )
      if len(column_means) == len(targets):
        total_signed = tuple(
          (actual - profile_total) / max(abs(profile_total), 1.0)
          for actual, profile_total in zip(
            column_means,
            profile.total_pressure_Pa,
            strict=True,
          )
        )
        total_pressure = tuple(abs(value) for value in total_signed)
      else:
        total_signed = ()
    else:
      total_signed = ()
  else:
    total_signed = ()
  ####
  if total_signed:
    signed_update = tuple(
      0.5 * (boundary + total)
      for boundary, total in zip(boundary_signed, total_signed, strict=True)
    )
  else:
    signed_update = boundary_signed
  ####
  normal = field.maximum_free_boundary_normal_velocity_residual_fraction
  centerline = field.maximum_centerline_normal_velocity_residual_fraction
  euler = field.maximum_conservative_euler_residual
  objective_values = [*boundary_residual]
  if normal is not None:
    objective_values.append(float(normal))
  if centerline is not None:
    objective_values.append(float(centerline))
  return _JointFieldMetrics(
    boundary_residual,
    total_pressure,
    signed_update,
    None if not boundary_residual else max(boundary_residual),
    None if not total_pressure else max(total_pressure),
    None if normal is None else float(normal),
    None if centerline is None else float(centerline),
    None if euler is None else float(euler),
    None if not objective_values else max(objective_values),
  )


def _joint_next_profile(
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
  signed_update_error_by_station: tuple[float, ...],
  step: float,
) -> tuple[
  MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
  bool,
]:
  """Apply one bounded residual-directed conservative-source update."""

  current = tuple(float(value) for value in profile.entrainment_fraction_by_station)
  if len(current) != len(signed_update_error_by_station):
    return profile, False
  updated = tuple(
    min(
      1.0,
      max(0.0, fraction + step * max(-1.0, min(1.0, error))),
    )
    for fraction, error in zip(
      current,
      signed_update_error_by_station,
      strict=True,
    )
  )
  if updated == current or not any(value > 0.0 for value in updated):
    return profile, False
  return replace(profile, entrainment_fraction_by_station=updated), True


def _joint_interface_lineage_verified(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
) -> bool:
  placement = downstream.transonic_interface_placement
  field = downstream.field
  request = None if field is None else field.request
  return bool(
    placement is not None
    and downstream.transonic_interface_placement_verified
    and downstream.transonic_interface_placement_consumed
    and field is not None
    and request is not None
    and request.transonic_shock_interface_field_placement is placement
    and field.transonic_shock_interface_field_placement is placement
    and field.transonic_shock_interface_field_placement_consumed
    and field.transonic_shock_interface_profile_consumed
  )


def _joint_result(
  status: MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus,
  message: str,
  *,
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult | None,
  initial_profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile | None,
  requested_iterations: int,
  iterations: tuple[
    MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration, ...
  ] = (),
  source_closure_fingerprint: str = '',
  profile_lineage_verified: bool = False,
  interface_placement_lineage_verified: bool = False,
  interface_placement_coverage_verified: bool = False,
) -> MocReflectedDomainGlobalTransonicMixedWaveJointFieldResult:
  return MocReflectedDomainGlobalTransonicMixedWaveJointFieldResult(
    status=status,
    downstream=downstream,
    initial_profile=initial_profile,
    iterations=iterations,
    requested_iterations=requested_iterations,
    source_closure_fingerprint=source_closure_fingerprint,
    profile_lineage_verified=profile_lineage_verified,
    interface_placement_lineage_verified=interface_placement_lineage_verified,
    interface_placement_coverage_verified=interface_placement_coverage_verified,
    independent_iteration_audits_verified=bool(
      iterations
      and all(item.independently_audited for item in iterations)
    ),
    joint_field_consumed=bool(
      iterations and all(item.exact_profile_consumed for item in iterations)
    ),
    local_joint_boundary_verified=(
      status
      is MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
      .CONVERGED_RESEARCH_ITERATION
    ),
    physical_closure_verified=False,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )


def solve_reflected_domain_global_transonic_mixed_wave_joint_field(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
  *,
  maximum_iterations: int = 4,
  entrainment_step: float = 0.20,
) -> MocReflectedDomainGlobalTransonicMixedWaveJointFieldResult:
  """Run a bounded, source-controlled joint research iteration.

  The existing coupled field owns the Euler/free-boundary solve.  This outer
  operator updates only the explicitly supplied conservative ambient
  entrainment fractions from signed station residuals, then independently
  audits every resulting field.  It does not infer ambient conditions,
  rewrite the total-pressure loss profile, move the transonic interface, or
  promote a locally converged field into canonical physics.
  """

  if not isinstance(
    downstream,
    MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  ):
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.INVALID_INPUT,
      'downstream must be a typed mixed-wave downstream result',
      downstream=None,
      initial_profile=(
        profile
        if isinstance(
          profile,
          MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
        )
        else None
      ),
      requested_iterations=0,
    )
  if not isinstance(
    profile,
    MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
  ):
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.INVALID_INPUT,
      'profile must be a typed entropy closure profile',
      downstream=downstream,
      initial_profile=None,
      requested_iterations=0,
    )
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.INVALID_INPUT,
      'maximum_iterations must be a positive integer',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=0,
    )
  step = float(entrainment_step)
  if not isfinite(step) or not 0.0 < step <= 1.0:
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.INVALID_INPUT,
      'entrainment_step must be finite and lie in the (0, 1] interval',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=maximum_iterations,
    )
  if profile.mechanism_id != CONSERVATIVE_AMBIENT_ENTRAINMENT_MECHANISM_ID:
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
      .CONSERVATIVE_SOURCE_REQUIRED,
      'joint interface/free-boundary iteration requires the explicit '
      'conservative ambient-entrainment mechanism',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=maximum_iterations,
    )
  ####
  try:
    preflight = audit_reflected_domain_global_transonic_mixed_wave_entropy_closure(
      downstream,
      profile,
    )
  except (ArithmeticError, TypeError, ValueError) as error:
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.LINEAGE_FAILURE,
      f'joint-field profile preflight failed: {error}',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=maximum_iterations,
    )
  if not preflight.profile_ready_for_joint_solver:
    status = (
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.LINEAGE_FAILURE
      if preflight.status
      is MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureStatus.LINEAGE_FAILURE
      else MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
      .DOWNSTREAM_SEAM_REQUIRED
    )
    return _joint_result(
      status,
      f'joint-field profile preflight did not pass: {preflight.message}',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=maximum_iterations,
      source_closure_fingerprint=preflight.source_closure_fingerprint,
      profile_lineage_verified=preflight.profile_lineage_verified,
    )
  ####
  field = downstream.field
  if field is None or not isinstance(
    field.request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
      .DOWNSTREAM_SEAM_REQUIRED,
      'downstream result retained no typed coupled-Euler request for joint '
      'consumption',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=maximum_iterations,
      source_closure_fingerprint=preflight.source_closure_fingerprint,
      profile_lineage_verified=preflight.profile_lineage_verified,
    )
  ####
  placement_lineage_verified = _joint_interface_lineage_verified(downstream)
  if not placement_lineage_verified:
    return _joint_result(
      MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.LINEAGE_FAILURE,
      'joint-field iteration requires the exact solver-owned transonic '
      'placement to remain bound through the downstream field request',
      downstream=downstream,
      initial_profile=profile,
      requested_iterations=maximum_iterations,
      source_closure_fingerprint=preflight.source_closure_fingerprint,
      profile_lineage_verified=preflight.profile_lineage_verified,
      interface_placement_coverage_verified=(
        downstream.interface_placement_coverage_verified
      ),
    )
  ####
  current_profile = profile
  current_step = step
  retained: list[MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration] = []
  for iteration_index in range(maximum_iterations):
    current_preflight = audit_reflected_domain_global_transonic_mixed_wave_entropy_closure(
      downstream,
      current_profile,
    )
    if not current_preflight.profile_ready_for_joint_solver:
      return _joint_result(
        MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.LINEAGE_FAILURE,
        f'joint-field profile update failed preflight: '
        f'{current_preflight.message}',
        downstream=downstream,
        initial_profile=profile,
        requested_iterations=maximum_iterations,
        iterations=tuple(retained),
        source_closure_fingerprint=preflight.source_closure_fingerprint,
        profile_lineage_verified=preflight.profile_lineage_verified,
        interface_placement_lineage_verified=placement_lineage_verified,
        interface_placement_coverage_verified=(
          downstream.interface_placement_coverage_verified
        ),
      )
    ####
    try:
      consumed_request = replace(
        field.request,
        entropy_closure_profile=current_profile,
        free_boundary_pressure_profile_Pa=(
          current_profile.target_static_pressure_Pa
        ),
        free_boundary_pressure_profile_x_stations_m=current_profile.x_stations_m,
        free_boundary_pressure_profile_source=(
          f'{current_profile.source}:joint-static-target'
        ),
      )
      candidate = solve_reflected_domain_coupled_euler_free_boundary(
        consumed_request
      )
      independent_audit = measure_reflected_domain_coupled_euler_free_boundary(
        candidate
      )
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      return _joint_result(
        MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.FIELD_FAILURE,
        f'joint-field iteration {iteration_index} failed: {error}',
        downstream=downstream,
        initial_profile=profile,
        requested_iterations=maximum_iterations,
        iterations=tuple(retained),
        source_closure_fingerprint=preflight.source_closure_fingerprint,
        profile_lineage_verified=preflight.profile_lineage_verified,
        interface_placement_lineage_verified=placement_lineage_verified,
        interface_placement_coverage_verified=(
          downstream.interface_placement_coverage_verified
        ),
      )
    ####
    metrics = _joint_field_metrics(candidate, current_profile)
    exact_consumption = bool(
      candidate.request is consumed_request
      and candidate.request.entropy_closure_profile is current_profile
      and candidate.transonic_shock_interface_field_placement
      is downstream.transonic_interface_placement
      and candidate.transonic_shock_interface_field_placement_consumed
    )
    next_profile = current_profile
    update_applied = False
    if (
      metrics.signed_update_error_by_station
      and iteration_index + 1 < maximum_iterations
    ):
      next_profile, update_applied = _joint_next_profile(
        current_profile,
        metrics.signed_update_error_by_station,
        current_step,
      )
    step_record = MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration(
      iteration_index=iteration_index,
      profile=current_profile,
      field=candidate,
      audit=independent_audit,
      pressure_residual_fraction_by_station=(
        metrics.pressure_residual_fraction_by_station
      ),
      total_pressure_residual_fraction_by_station=(
        metrics.total_pressure_residual_fraction_by_station
      ),
      maximum_pressure_residual_fraction=(
        metrics.maximum_pressure_residual_fraction
      ),
      maximum_total_pressure_residual_fraction=(
        metrics.maximum_total_pressure_residual_fraction
      ),
      maximum_normal_velocity_residual_fraction=(
        metrics.maximum_normal_velocity_residual_fraction
      ),
      maximum_centerline_normal_velocity_residual_fraction=(
        metrics.maximum_centerline_normal_velocity_residual_fraction
      ),
      maximum_euler_residual=metrics.maximum_euler_residual,
      objective=metrics.objective,
      source_update_applied=update_applied and exact_consumption,
      source_update_step=current_step if update_applied else 0.0,
      message=(
        'exact conservative source and transonic placement were consumed; '
        'independent field audit retained'
        if exact_consumption
        else 'field result did not retain the exact joint request lineage'
      ),
    )
    retained.append(step_record)
    local_ready = bool(
      exact_consumption
      and candidate.local_physical_closure_verified
      and independent_audit.local_consistency_verified
      and metrics.maximum_pressure_residual_fraction is not None
      and metrics.maximum_pressure_residual_fraction
      <= candidate.request.free_boundary_pressure_tolerance_fraction
      and metrics.maximum_normal_velocity_residual_fraction is not None
      and metrics.maximum_normal_velocity_residual_fraction
      <= candidate.request.free_boundary_normal_velocity_tolerance_fraction
      and metrics.maximum_centerline_normal_velocity_residual_fraction
      is not None
      and metrics.maximum_centerline_normal_velocity_residual_fraction
      <= candidate.request.centerline_normal_velocity_tolerance_fraction
    )
    if local_ready:
      if downstream.interface_placement_coverage_verified:
        return _joint_result(
          MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
          .CONVERGED_RESEARCH_ITERATION,
          'joint conservative source/interface/free-boundary research '
          'iteration passed its local residual and independent-audit gates; '
          'canonical closure and promotion remain blocked',
          downstream=downstream,
          initial_profile=profile,
          requested_iterations=maximum_iterations,
          iterations=tuple(retained),
          source_closure_fingerprint=preflight.source_closure_fingerprint,
          profile_lineage_verified=preflight.profile_lineage_verified,
          interface_placement_lineage_verified=placement_lineage_verified,
          interface_placement_coverage_verified=True,
        )
      return _joint_result(
        MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus
        .INTERFACE_COVERAGE_REQUIRED,
        'joint field locally passed, but the exact transonic placement does '
        'not span the mixed-wave interface; no boundary extension or '
        'promotion was inferred',
        downstream=downstream,
        initial_profile=profile,
        requested_iterations=maximum_iterations,
        iterations=tuple(retained),
        source_closure_fingerprint=preflight.source_closure_fingerprint,
        profile_lineage_verified=preflight.profile_lineage_verified,
        interface_placement_lineage_verified=placement_lineage_verified,
        interface_placement_coverage_verified=False,
      )
    ####
    if not update_applied:
      break
    current_profile = next_profile
    current_step *= 0.75
  ####
  return _joint_result(
    MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus.ITERATION_LIMIT,
    'joint conservative source/interface/free-boundary iteration stopped '
    'before all local residual gates passed; retained fields and audits are '
    'research evidence only',
    downstream=downstream,
    initial_profile=profile,
    requested_iterations=maximum_iterations,
    iterations=tuple(retained),
    source_closure_fingerprint=preflight.source_closure_fingerprint,
    profile_lineage_verified=preflight.profile_lineage_verified,
    interface_placement_lineage_verified=placement_lineage_verified,
    interface_placement_coverage_verified=(
      downstream.interface_placement_coverage_verified
    ),
  )


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
  ambient_temperature_K: float | None = None,
  ambient_velocity_m_s: tuple[float, float] | None = None,
  entrainment_fraction_by_station: tuple[float, ...] = (),
  ambient_temperature_K_by_station: tuple[float, ...] | None = None,
  ambient_velocity_m_s_by_station: tuple[tuple[float, float], ...] | None = None,
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
    ambient_temperature_K=ambient_temperature_K,
    ambient_velocity_m_s=ambient_velocity_m_s,
    entrainment_fraction_by_station=entrainment_fraction_by_station,
    ambient_temperature_K_by_station=ambient_temperature_K_by_station,
    ambient_velocity_m_s_by_station=ambient_velocity_m_s_by_station,
  )


def build_reflected_domain_global_transonic_mixed_wave_ambient_entrainment_profile(
  downstream: MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult,
  *,
  x_stations_m: tuple[float, ...],
  total_pressure_Pa: tuple[float, ...],
  target_static_pressure_Pa: tuple[float, ...],
  ambient_temperature_K: float | None = None,
  ambient_velocity_m_s: tuple[float, float] | None = None,
  entrainment_fraction_by_station: tuple[float, ...],
  ambient_temperature_K_by_station: tuple[float, ...] | None = None,
  ambient_velocity_m_s_by_station: tuple[tuple[float, float], ...] | None = None,
  relaxation_fraction: float = 0.25,
  source: str = DEFAULT_AMBIENT_ENTRAINMENT_PROFILE_SOURCE,
) -> MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile:
  """Bind a conservative ambient-entrainment source to the exact seam.

  ``total_pressure_Pa`` remains an explicit downstream acceptance target.  It
  is not converted into a source term.  The source itself mixes each local
  conservative state toward the explicitly supplied ambient state using the
  station-wise entrainment fraction, so the pressure-loss mechanism is not
  the former fixed-velocity/fixed-temperature target reconstruction.
  """

  return build_reflected_domain_global_transonic_mixed_wave_entropy_closure_profile(
    downstream,
    x_stations_m=x_stations_m,
    total_pressure_Pa=total_pressure_Pa,
    target_static_pressure_Pa=target_static_pressure_Pa,
    relaxation_fraction=relaxation_fraction,
    mechanism_id=CONSERVATIVE_AMBIENT_ENTRAINMENT_MECHANISM_ID,
    source=source,
    ambient_temperature_K=ambient_temperature_K,
    ambient_velocity_m_s=ambient_velocity_m_s,
    entrainment_fraction_by_station=entrainment_fraction_by_station,
    ambient_temperature_K_by_station=ambient_temperature_K_by_station,
    ambient_velocity_m_s_by_station=ambient_velocity_m_s_by_station,
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


class MocReflectedDomainGlobalTransonicMixedWaveJointFieldStatus(str, Enum):
  """Outcome of the bounded interface/source/free-boundary iteration."""

  CONVERGED_RESEARCH_ITERATION = (
    'converged-research-global-transonic-mixed-wave-joint-interface-field'
  )
  INVALID_INPUT = 'invalid_input'
  CONSERVATIVE_SOURCE_REQUIRED = (
    'mixed-wave-joint-field-conservative-ambient-source-required'
  )
  DOWNSTREAM_SEAM_REQUIRED = 'mixed-wave-joint-field-downstream-seam-required'
  LINEAGE_FAILURE = 'mixed-wave-joint-field-lineage-failure'
  FIELD_FAILURE = 'mixed-wave-joint-field-solver-failure'
  INTERFACE_COVERAGE_REQUIRED = (
    'mixed-wave-joint-field-interface-coverage-required'
  )
  ITERATION_LIMIT = 'mixed-wave-joint-field-iteration-limit'


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveJointFieldIteration:
  """One independently audited source/interface/free-boundary iteration."""

  iteration_index: int
  profile: MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile
  field: MocReflectedDomainCoupledEulerFreeBoundaryResult
  audit: MocReflectedDomainCoupledEulerFreeBoundaryAudit
  pressure_residual_fraction_by_station: tuple[float, ...] = ()
  total_pressure_residual_fraction_by_station: tuple[float, ...] = ()
  maximum_pressure_residual_fraction: float | None = None
  maximum_total_pressure_residual_fraction: float | None = None
  maximum_normal_velocity_residual_fraction: float | None = None
  maximum_centerline_normal_velocity_residual_fraction: float | None = None
  maximum_euler_residual: float | None = None
  objective: float | None = None
  source_update_applied: bool = False
  source_update_step: float = 0.0
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.iteration_index, bool)
      or not isinstance(self.iteration_index, int)
      or self.iteration_index < 0
    ):
      raise ValueError('iteration_index must be a nonnegative integer')
    if not isinstance(
      self.profile,
      MocReflectedDomainGlobalTransonicMixedWaveEntropyClosureProfile,
    ):
      raise TypeError('profile must be a typed entropy closure profile')
    if not isinstance(
      self.field,
      MocReflectedDomainCoupledEulerFreeBoundaryResult,
    ):
      raise TypeError('field must be a typed coupled-Euler result')
    if not isinstance(
      self.audit,
      MocReflectedDomainCoupledEulerFreeBoundaryAudit,
    ):
      raise TypeError('audit must be a typed coupled-Euler audit')
    for name in (
      'pressure_residual_fraction_by_station',
      'total_pressure_residual_fraction_by_station',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    if len(self.pressure_residual_fraction_by_station) not in (
      0,
      len(self.profile.x_stations_m),
    ):
      raise ValueError(
        'pressure residuals must be empty or aligned with the profile stations'
      )
    if len(self.total_pressure_residual_fraction_by_station) not in (
      0,
      len(self.profile.x_stations_m),
    ):
      raise ValueError(
        'total-pressure residuals must be empty or aligned with the profile '
        'stations'
      )
    for name in (
      'maximum_pressure_residual_fraction',
      'maximum_total_pressure_residual_fraction',
      'maximum_normal_velocity_residual_fraction',
      'maximum_centerline_normal_velocity_residual_fraction',
      'maximum_euler_residual',
      'objective',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        object.__setattr__(self, name, numeric)
    step = float(self.source_update_step)
    if not isfinite(step) or step < 0.0:
      raise ValueError('source_update_step must be finite and nonnegative')
    object.__setattr__(self, 'source_update_step', step)
    if not isinstance(self.source_update_applied, bool):
      raise TypeError('source_update_applied must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def exact_profile_consumed(self) -> bool:
    """Whether the field request retained this exact source profile."""

    request = self.field.request
    return bool(
      request is not None
      and request.entropy_closure_profile is self.profile
      and request.free_boundary_pressure_profile_Pa
      == self.profile.target_static_pressure_Pa
      and request.free_boundary_pressure_profile_x_stations_m
      == self.profile.x_stations_m
      and self.field.entropy_closure_profile_consumed
      and self.audit.candidate is self.field
    )

  @property
  def independently_audited(self) -> bool:
    """Whether the independent operator remeasured this iteration."""

    return bool(
      self.exact_profile_consumed
      and self.audit.residual_channels_recomputed
      and self.audit.residual_report_verified
      and self.audit.free_boundary_report_verified
      and self.audit.centerline_report_verified
      and self.audit.promotion_flags_verified
      and self.field.chain_promotion_blocked
      and not self.field.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'profile': self.profile.as_report(),
      'field': self.field.as_report(),
      'audit': self.audit.as_report(),
      'pressure_residual_fraction_by_station': (
        self.pressure_residual_fraction_by_station
      ),
      'total_pressure_residual_fraction_by_station': (
        self.total_pressure_residual_fraction_by_station
      ),
      'maximum_pressure_residual_fraction': (
        self.maximum_pressure_residual_fraction
      ),
      'maximum_total_pressure_residual_fraction': (
        self.maximum_total_pressure_residual_fraction
      ),
      'maximum_normal_velocity_residual_fraction': (
        self.maximum_normal_velocity_residual_fraction
      ),
      'maximum_centerline_normal_velocity_residual_fraction': (
        self.maximum_centerline_normal_velocity_residual_fraction
      ),
      'maximum_euler_residual': self.maximum_euler_residual,
      'objective': self.objective,
      'source_update_applied': self.source_update_applied,
      'source_update_step': self.source_update_step,
      'exact_profile_consumed': self.exact_profile_consumed,
      'independently_audited': self.independently_audited,
      'message': self.message,
    }
