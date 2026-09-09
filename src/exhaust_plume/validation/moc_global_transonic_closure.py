"""Bounded joint transonic-interface closure gate for the global MOC lane.

The existing solver-owned interface placement is a useful handoff, but it is
not allowed to masquerade as a mixed-regime solution.  This operator binds
one exact global physical closure to one exact frontier identity, checks the
pressure budget before starting the downstream field, and only then permits a
research coupled-Euler candidate to run.

The first vertical slice is intentionally a hard physical feasibility gate.
An attached compression shock cannot lower static pressure below the retained
upstream pressure.  When the requested target is below that floor, the
operator returns the best retained in-domain placement and a typed stop; it
does not run a lower-fidelity fallback, hold an endpoint, extrapolate a state,
or fabricate a profile.  A future expansion/mixed-regime solver can consume
this contract without changing the claim ceiling of the existing lanes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
  MocEulerAmbientFirstWedgeEntropyCarryStatus,
  solve_euler_ambient_first_wedge_entropy_carry,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_closure import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_continuation_closure,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_field,
)
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)
from exhaust_plume.models.moc.euler_terminal_wedge import (
  MocEulerAmbientFirstWedgeCharacteristicResult,
  solve_euler_ambient_first_wedge_characteristic_remesh,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamResult,
  build_reflected_domain_global_solver_owned_transonic_interface_placement,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.mixed_wave import (
  MocMixedWavePathResult,
  solve_mixed_wave_path,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementResult,
  MocTransonicShockInterfaceFieldPlacementStatus,
)
from exhaust_plume.validation.moc_global_transonic_interface import (
  MocReflectedDomainGlobalTransonicInterfaceAudit,
  measure_reflected_domain_global_transonic_interface,
)
from exhaust_plume.validation.moc_transonic_interface import (
  MocTransonicShockInterfaceProfileBuildAudit,
  measure_moc_transonic_shock_interface_profile_build,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_CLOSURE_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicClosureStatus',
  'MocReflectedDomainGlobalTransonicPressureBudget',
  'MocReflectedDomainGlobalTransonicClosureRequest',
  'MocReflectedDomainGlobalTransonicExpansionAttemptStatus',
  'MocReflectedDomainGlobalTransonicExpansionAttempt',
  'MocReflectedDomainGlobalTransonicClosureResult',
  'moc_reflected_domain_global_transonic_frontier_fingerprint',
  'run_reflected_domain_global_transonic_expansion_attempt',
  'run_reflected_domain_global_transonic_closure',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_CLOSURE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-interface-closure'
)
GLOBAL_TRANSONIC_CLOSURE_STATION_POLICY_ID = (
  'solver-owned-post-shock-cross-section-fraction-v1'
)
GLOBAL_TRANSONIC_CLOSURE_FRAME_POLICY_ID = (
  'exact-retained-global-field-cross-section-frame-v1'
)


class MocReflectedDomainGlobalTransonicClosureStatus(str, Enum):
  """Outcome of one bounded joint interface/field closure attempt."""

  CONVERGED_RESEARCH_JOINT_CLOSURE = (
    'converged-research-global-transonic-joint-closure'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-transonic-closure-source-failure'
  FRONTIER_LINEAGE_FAILURE = 'global-transonic-closure-frontier-lineage-failure'
  PLACEMENT_FAILURE = 'global-transonic-closure-placement-failure'
  INTERFACE_PROFILE_AUDIT_FAILURE = (
    'global-transonic-closure-interface-profile-audit-failure'
  )
  INTERFACE_TARGET_UNREACHABLE = (
    'global-transonic-closure-compression-target-unreachable'
  )
  COUPLED_FIELD_FAILURE = 'global-transonic-closure-coupled-field-failure'
  BOUNDARY_RESIDUAL_FAILURE = (
    'global-transonic-closure-boundary-residual-failure'
  )
  CENTERLINE_BOUNDARY_FAILURE = (
    'global-transonic-closure-centerline-boundary-failure'
  )
  INTERFACE_LINEAGE_FAILURE = (
    'global-transonic-closure-interface-lineage-failure'
  )
####


def _finite_positive(name: str, value: Any) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _finite_nonnegative(name: str, value: Any) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric < 0.0:
    raise ValueError(f'{name} must be finite and nonnegative')
  ####
  return numeric
####


def _static_pressure_from_total_pressure(
  *,
  total_pressure_Pa: float,
  mach: float,
  gamma: float,
) -> float:
  """Recover static pressure for the local mixed-wave source probe."""

  factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  pressure = total_pressure_Pa / factor**(gamma / (gamma - 1.0))
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('source total pressure did not yield a finite positive static pressure')
  ####
  return pressure
####


def moc_reflected_domain_global_transonic_frontier_fingerprint(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> str:
  """Return the stable identity of the retained global downstream frontier."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  boundary = closure.downstream_boundary
  if boundary is None:
    raise ValueError('closure retained no solver-owned downstream frontier')
  ####
  payload = {
    'source_closure_fingerprint': (
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    'source_frontier_verified': closure.source_frontier_verified,
    'downstream_boundary': boundary.as_report(),
  }
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicClosureRequest:
  """Exact source and bounded solver policy for a joint closure attempt."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  reference_total_temperature_K: float
  ambient_pressure_Pa: float
  sample_count: int = 10
  post_shock_fraction: float = 0.25
  target_pressure_tolerance_fraction: float = 0.02
  downstream_length_m: float = 0.2
  initial_outlet_height_m: float = 0.05
  control_section_x_offset_m: float = 0.02
  control_section_height_m: float = 0.05
  control_section_sample_count: int = 4
  axial_station_count: int = 7
  axial_cell_count: int = 12
  transverse_cell_count: int = 6
  max_pseudo_iterations: int = 1200
  max_shape_iterations: int = 18
  outlet_static_pressure_Pa: float | None = None
  station_policy_id: str = GLOBAL_TRANSONIC_CLOSURE_STATION_POLICY_ID
  frame_policy_id: str = GLOBAL_TRANSONIC_CLOSURE_FRAME_POLICY_ID
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    object.__setattr__(
      self,
      'reference_total_temperature_K',
      _finite_positive(
        'reference_total_temperature_K',
        self.reference_total_temperature_K,
      ),
    )
    object.__setattr__(
      self,
      'ambient_pressure_Pa',
      _finite_positive('ambient_pressure_Pa', self.ambient_pressure_Pa),
    )
    if (
      isinstance(self.sample_count, bool)
      or not isinstance(self.sample_count, int)
      or self.sample_count < 3
    ):
      raise ValueError('sample_count must be an integer greater than or equal to three')
    ####
    post_shock_fraction = _finite_nonnegative(
      'post_shock_fraction',
      self.post_shock_fraction,
    )
    if not 0.0 < post_shock_fraction < 1.0:
      raise ValueError('post_shock_fraction must be strictly between zero and one')
    ####
    target_tolerance = _finite_positive(
      'target_pressure_tolerance_fraction',
      self.target_pressure_tolerance_fraction,
    )
    object.__setattr__(self, 'post_shock_fraction', post_shock_fraction)
    object.__setattr__(self, 'target_pressure_tolerance_fraction', target_tolerance)
    for name in (
      'downstream_length_m',
      'initial_outlet_height_m',
      'control_section_x_offset_m',
      'control_section_height_m',
    ):
      object.__setattr__(
        self,
        name,
        _finite_positive(name, getattr(self, name)),
      )
    ####
    for name in (
      'control_section_sample_count',
      'axial_station_count',
      'axial_cell_count',
      'transverse_cell_count',
      'max_pseudo_iterations',
      'max_shape_iterations',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
      ####
    ####
    if self.outlet_static_pressure_Pa is not None:
      object.__setattr__(
        self,
        'outlet_static_pressure_Pa',
        _finite_positive(
          'outlet_static_pressure_Pa',
          self.outlet_static_pressure_Pa,
        ),
      )
    ####
    for name, expected in (
      ('station_policy_id', GLOBAL_TRANSONIC_CLOSURE_STATION_POLICY_ID),
      ('frame_policy_id', GLOBAL_TRANSONIC_CLOSURE_FRAME_POLICY_ID),
    ):
      value = str(getattr(self, name))
      if value != expected:
        raise ValueError(f'{name} must retain the solver-owned policy {expected}')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.inlet_boundary_mode is not (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    ):
      raise ValueError(
        'joint transonic closure requires the solver-owned interior interface '
        'boundary mode'
      )
    ####
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def source_frontier_fingerprint(self) -> str | None:
    try:
      return moc_reflected_domain_global_transonic_frontier_fingerprint(
        self.closure
      )
    except (TypeError, ValueError):
      return None
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_CLOSURE_OPERATOR_ID,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_frontier_fingerprint': self.source_frontier_fingerprint,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'sample_count': self.sample_count,
      'post_shock_fraction': self.post_shock_fraction,
      'target_pressure_tolerance_fraction': (
        self.target_pressure_tolerance_fraction
      ),
      'downstream_length_m': self.downstream_length_m,
      'initial_outlet_height_m': self.initial_outlet_height_m,
      'control_section_x_offset_m': self.control_section_x_offset_m,
      'control_section_height_m': self.control_section_height_m,
      'control_section_sample_count': self.control_section_sample_count,
      'axial_station_count': self.axial_station_count,
      'axial_cell_count': self.axial_cell_count,
      'transverse_cell_count': self.transverse_cell_count,
      'max_pseudo_iterations': self.max_pseudo_iterations,
      'max_shape_iterations': self.max_shape_iterations,
      'outlet_static_pressure_Pa': self.outlet_static_pressure_Pa,
      'station_policy_id': self.station_policy_id,
      'frame_policy_id': self.frame_policy_id,
      'inlet_boundary_mode': self.inlet_boundary_mode.value,
    }
  ####
####


class MocReflectedDomainGlobalTransonicExpansionAttemptStatus(str, Enum):
  """Outcome of the exact-source pressure-lowering continuation attempt."""

  CONVERGED_RESEARCH_MIXED_REGIME_BAND = (
    'converged-research-global-transonic-mixed-regime-band'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'global-transonic-expansion-source-failure'
  SOURCE_FIELD_FAILURE = 'global-transonic-expansion-source-field-failure'
  TERMINAL_WEDGE_FAILURE = 'global-transonic-expansion-terminal-wedge-failure'
  ENTROPY_CARRY_FAILURE = 'global-transonic-expansion-entropy-carry-failure'
  CHARACTERISTIC_FIELD_FAILURE = (
    'global-transonic-expansion-characteristic-field-failure'
  )
  CONTINUATION_FAILURE = 'global-transonic-expansion-continuation-failure'
  EXPANSION_REQUIRED = 'global-transonic-expansion-required'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicExpansionAttempt:
  """Exact-source mixed-regime continuation evidence below promotion.

  This result deliberately stops short of a global expansion/free-boundary
  solve.  It carries the retained global physical field through the existing
  solver-owned terminal wedge, entropy-carry, and characteristic-band lanes,
  then records where the compression-only continuation path fails.  No
  pressure, state, geometry, or endpoint is synthesized when that path cannot
  satisfy the target.
  """

  status: MocReflectedDomainGlobalTransonicExpansionAttemptStatus
  request: MocReflectedDomainGlobalTransonicClosureRequest | None
  source_field: MocEulerAmbientPhysicalFieldResult | None = None
  terminal_wedge: MocEulerAmbientFirstWedgeCharacteristicResult | None = None
  entropy_trial: MocEulerAmbientFirstWedgeEntropyCarryResult | None = None
  characteristic_field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None
  ) = None
  continuation_closure: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult
    | None
  ) = None
  mixed_wave_path: MocMixedWavePathResult | None = None
  mixed_wave_path_verified: bool = False
  outer_flow_angle_bracket: tuple[float, float] | None = None
  minimum_upstream_static_pressure_Pa: float | None = None
  target_pressure_Pa: float | None = None
  pressure_lowering_required: bool = False
  source_field_consumed: bool = False
  local_entropy_band_verified: bool = False
  mixed_regime_closure_verified: bool = False
  canonical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicExpansionAttemptStatus,
    ):
      raise TypeError('status must be a typed expansion-attempt status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalTransonicClosureRequest,
    ):
      raise TypeError('request must be a typed transonic closure request or None')
    ####
    if self.source_field is not None and not isinstance(
      self.source_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError('source_field must be a typed Euler physical field or None')
    ####
    if self.terminal_wedge is not None and not isinstance(
      self.terminal_wedge,
      MocEulerAmbientFirstWedgeCharacteristicResult,
    ):
      raise TypeError('terminal_wedge must be typed or None')
    ####
    if self.entropy_trial is not None and not isinstance(
      self.entropy_trial,
      MocEulerAmbientFirstWedgeEntropyCarryResult,
    ):
      raise TypeError('entropy_trial must be typed or None')
    ####
    if self.characteristic_field is not None and not isinstance(
      self.characteristic_field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError('characteristic_field must be typed or None')
    ####
    if self.continuation_closure is not None and not isinstance(
      self.continuation_closure,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult,
    ):
      raise TypeError('continuation_closure must be typed or None')
    ####
    if self.mixed_wave_path is not None and not isinstance(
      self.mixed_wave_path,
      MocMixedWavePathResult,
    ):
      raise TypeError('mixed_wave_path must be typed or None')
    ####
    if self.outer_flow_angle_bracket is not None:
      bracket = tuple(float(value) for value in self.outer_flow_angle_bracket)
      if len(bracket) != 2 or not all(isfinite(value) for value in bracket):
        raise ValueError('outer_flow_angle_bracket must contain two finite values')
      ####
      if bracket[0] >= bracket[1]:
        raise ValueError('outer_flow_angle_bracket must be ordered')
      ####
      object.__setattr__(self, 'outer_flow_angle_bracket', bracket)
    ####
    for name in (
      'minimum_upstream_static_pressure_Pa',
      'target_pressure_Pa',
    ):
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
    for name in (
      'pressure_lowering_required',
      'source_field_consumed',
      'local_entropy_band_verified',
      'mixed_wave_path_verified',
      'mixed_regime_closure_verified',
      'canonical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_closure_verified:
      raise ValueError('this expansion attempt cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('this expansion attempt must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('this expansion attempt cannot allow production claims')
    ####
    if self.mixed_wave_path_verified and (
      self.mixed_wave_path is None or not self.mixed_wave_path.converged
    ):
      raise ValueError(
        'mixed_wave_path_verified requires a converged mixed-wave path'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    return (
      None
      if self.request is None
      else self.request.source_closure_fingerprint
    )
  ####

  @property
  def source_frontier_fingerprint(self) -> str | None:
    return None if self.request is None else self.request.source_frontier_fingerprint
  ####

  @property
  def local_band_converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicExpansionAttemptStatus
      .CONVERGED_RESEARCH_MIXED_REGIME_BAND
      and self.source_field_consumed
      and self.local_entropy_band_verified
      and not self.mixed_regime_closure_verified
      and self.chain_promotion_blocked
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': 'op.moc.reflected-domain.global-transonic-expansion-attempt',
      'status': self.status.value,
      'local_band_converged': self.local_band_converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_frontier_fingerprint': self.source_frontier_fingerprint,
      'source_field_consumed': self.source_field_consumed,
      'local_entropy_band_verified': self.local_entropy_band_verified,
      'mixed_wave_path_verified': self.mixed_wave_path_verified,
      'mixed_regime_closure_verified': self.mixed_regime_closure_verified,
      'canonical_closure_verified': self.canonical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'minimum_upstream_static_pressure_Pa': (
        self.minimum_upstream_static_pressure_Pa
      ),
      'target_pressure_Pa': self.target_pressure_Pa,
      'pressure_lowering_required': self.pressure_lowering_required,
      'source_field': (
        None if self.source_field is None else self.source_field.as_report()
      ),
      'terminal_wedge': (
        None if self.terminal_wedge is None else self.terminal_wedge.as_report()
      ),
      'entropy_trial': (
        None if self.entropy_trial is None else self.entropy_trial.as_report()
      ),
      'characteristic_field': (
        None
        if self.characteristic_field is None
        else self.characteristic_field.as_report()
      ),
      'continuation_closure': (
        None
        if self.continuation_closure is None
        else self.continuation_closure.as_report()
      ),
      'mixed_wave_path': (
        None
        if self.mixed_wave_path is None
        else self.mixed_wave_path.as_report()
      ),
      'claim_status': (
        'exact-source-research-band-only; expansion/free-boundary closure, '
        'stable refinement, physical shock-cell acceptance, external '
        'validation, and production promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicPressureBudget:
  """Independent pressure feasibility evidence for the retained interface."""

  target_pressure_Pa: float
  minimum_upstream_static_pressure_Pa: float
  maximum_upstream_static_pressure_Pa: float
  minimum_derived_downstream_static_pressure_Pa: float
  maximum_derived_downstream_static_pressure_Pa: float
  minimum_static_pressure_jump_Pa: float
  target_minus_upstream_pressure_floor_Pa: float
  target_minus_compression_pressure_floor_Pa: float
  independent_profile_verified: bool
  compression_pressure_increase_verified: bool
  target_below_upstream_pressure_floor: bool
  target_below_compression_pressure_floor: bool
  message: str = ''

  def __post_init__(self) -> None:
    for name in (
      'target_pressure_Pa',
      'minimum_upstream_static_pressure_Pa',
      'maximum_upstream_static_pressure_Pa',
      'minimum_derived_downstream_static_pressure_Pa',
      'maximum_derived_downstream_static_pressure_Pa',
    ):
      object.__setattr__(self, name, _finite_positive(name, getattr(self, name)))
    ####
    for name in (
      'minimum_static_pressure_jump_Pa',
      'target_minus_upstream_pressure_floor_Pa',
      'target_minus_compression_pressure_floor_Pa',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      ####
      object.__setattr__(self, name, value)
    ####
    if not isinstance(self.independent_profile_verified, bool):
      raise TypeError('independent_profile_verified must be a bool')
    ####
    if not isinstance(self.compression_pressure_increase_verified, bool):
      raise TypeError('compression_pressure_increase_verified must be a bool')
    ####
    if not isinstance(self.target_below_upstream_pressure_floor, bool):
      raise TypeError('target_below_upstream_pressure_floor must be a bool')
    ####
    if not isinstance(self.target_below_compression_pressure_floor, bool):
      raise TypeError('target_below_compression_pressure_floor must be a bool')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def compression_floor_passes(self) -> bool:
    return bool(
      self.independent_profile_verified
      and self.compression_pressure_increase_verified
      and not self.target_below_upstream_pressure_floor
    )
  ####

  @property
  def hard_stop_required(self) -> bool:
    return self.target_below_upstream_pressure_floor
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'target_pressure_Pa': self.target_pressure_Pa,
      'minimum_upstream_static_pressure_Pa': (
        self.minimum_upstream_static_pressure_Pa
      ),
      'maximum_upstream_static_pressure_Pa': (
        self.maximum_upstream_static_pressure_Pa
      ),
      'minimum_derived_downstream_static_pressure_Pa': (
        self.minimum_derived_downstream_static_pressure_Pa
      ),
      'maximum_derived_downstream_static_pressure_Pa': (
        self.maximum_derived_downstream_static_pressure_Pa
      ),
      'minimum_static_pressure_jump_Pa': self.minimum_static_pressure_jump_Pa,
      'target_minus_upstream_pressure_floor_Pa': (
        self.target_minus_upstream_pressure_floor_Pa
      ),
      'target_minus_compression_pressure_floor_Pa': (
        self.target_minus_compression_pressure_floor_Pa
      ),
      'independent_profile_verified': self.independent_profile_verified,
      'compression_pressure_increase_verified': (
        self.compression_pressure_increase_verified
      ),
      'target_below_upstream_pressure_floor': (
        self.target_below_upstream_pressure_floor
      ),
      'target_below_compression_pressure_floor': (
        self.target_below_compression_pressure_floor
      ),
      'compression_floor_passes': self.compression_floor_passes,
      'hard_stop_required': self.hard_stop_required,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicClosureResult:
  """Research result for one exact, bounded transonic closure attempt."""

  status: MocReflectedDomainGlobalTransonicClosureStatus
  request: MocReflectedDomainGlobalTransonicClosureRequest | None
  placement: MocTransonicShockInterfaceFieldPlacementResult | None = None
  pressure_budget: MocReflectedDomainGlobalTransonicPressureBudget | None = None
  expansion_attempt: MocReflectedDomainGlobalTransonicExpansionAttempt | None = None
  interface_profile_build_audit: MocTransonicShockInterfaceProfileBuildAudit | None = None
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult | None = None
  interface_audit: MocReflectedDomainGlobalTransonicInterfaceAudit | None = None
  source_lineage_verified: bool = False
  placement_lineage_verified: bool = False
  downstream_field_attempted: bool = False
  joint_interface_consumption_verified: bool = False
  canonical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalTransonicClosureStatus):
      raise TypeError('status must be a typed global transonic closure status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalTransonicClosureRequest,
    ):
      raise TypeError('request must be a typed transonic closure request or None')
    ####
    if self.placement is not None and not isinstance(
      self.placement,
      MocTransonicShockInterfaceFieldPlacementResult,
    ):
      raise TypeError('placement must be a typed field placement or None')
    ####
    if self.pressure_budget is not None and not isinstance(
      self.pressure_budget,
      MocReflectedDomainGlobalTransonicPressureBudget,
    ):
      raise TypeError('pressure_budget must be a typed pressure budget or None')
    ####
    if self.expansion_attempt is not None and not isinstance(
      self.expansion_attempt,
      MocReflectedDomainGlobalTransonicExpansionAttempt,
    ):
      raise TypeError('expansion_attempt must be typed or None')
    ####
    if self.interface_profile_build_audit is not None and not isinstance(
      self.interface_profile_build_audit,
      MocTransonicShockInterfaceProfileBuildAudit,
    ):
      raise TypeError('interface_profile_build_audit must be typed or None')
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError('candidate must be a coupled downstream result or None')
    ####
    if self.interface_audit is not None and not isinstance(
      self.interface_audit,
      MocReflectedDomainGlobalTransonicInterfaceAudit,
    ):
      raise TypeError('interface_audit must be a typed interface audit or None')
    ####
    for name in (
      'source_lineage_verified',
      'placement_lineage_verified',
      'downstream_field_attempted',
      'joint_interface_consumption_verified',
      'canonical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_closure_verified:
      raise ValueError('this research operator cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('this research operator must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('this research operator cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def source_closure_fingerprint(self) -> str | None:
    return (
      None
      if self.request is None
      else self.request.source_closure_fingerprint
    )
  ####

  @property
  def source_frontier_fingerprint(self) -> str | None:
    return (
      None if self.request is None else self.request.source_frontier_fingerprint
    )
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicClosureStatus
      .CONVERGED_RESEARCH_JOINT_CLOSURE
      and self.source_lineage_verified
      and self.placement_lineage_verified
      and self.placement is not None
      and self.placement.converged
      and self.pressure_budget is not None
      and self.pressure_budget.compression_floor_passes
      and self.candidate is not None
      and self.candidate.converged
      and self.interface_profile_build_audit is not None
      and self.interface_profile_build_audit.converged
      and self.interface_audit is not None
      and self.interface_audit.converged
      and self.interface_audit.joint_boundary_residuals_verified
      and self.downstream_field_attempted
      and self.joint_interface_consumption_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def global_coupling_verified(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_CLOSURE_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_frontier_fingerprint': self.source_frontier_fingerprint,
      'source_lineage_verified': self.source_lineage_verified,
      'placement_lineage_verified': self.placement_lineage_verified,
      'downstream_field_attempted': self.downstream_field_attempted,
      'joint_interface_consumption_verified': (
        self.joint_interface_consumption_verified
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'canonical_closure_verified': self.canonical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': None if self.request is None else self.request.as_report(),
      'placement': (
        None if self.placement is None else self.placement.as_report()
      ),
      'pressure_budget': (
        None
        if self.pressure_budget is None
        else self.pressure_budget.as_report()
      ),
      'expansion_attempt': (
        None
        if self.expansion_attempt is None
        else self.expansion_attempt.as_report()
      ),
      'interface_profile_build_audit': (
        None
        if self.interface_profile_build_audit is None
        else self.interface_profile_build_audit.as_report()
      ),
      'candidate': (
        None if self.candidate is None else self.candidate.as_report()
      ),
      'interface_audit': (
        None
        if self.interface_audit is None
        else self.interface_audit.as_report()
      ),
      'claim_status': (
        'research-only-joint-transonic-interface-gate; canonical mixed-regime '
        'closure, stable refinement, physical shock-cell acceptance, external '
        'validation, Signature/FPA claims, and release promotion remain open'
      ),
      'message': self.message,
    }
  ####
####


def _result(
  status: MocReflectedDomainGlobalTransonicClosureStatus,
  request: MocReflectedDomainGlobalTransonicClosureRequest | None,
  *,
  placement: MocTransonicShockInterfaceFieldPlacementResult | None = None,
  pressure_budget: MocReflectedDomainGlobalTransonicPressureBudget | None = None,
  expansion_attempt: MocReflectedDomainGlobalTransonicExpansionAttempt | None = None,
  interface_profile_build_audit: MocTransonicShockInterfaceProfileBuildAudit | None = None,
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult | None = None,
  interface_audit: MocReflectedDomainGlobalTransonicInterfaceAudit | None = None,
  source_lineage_verified: bool = False,
  placement_lineage_verified: bool = False,
  downstream_field_attempted: bool = False,
  joint_interface_consumption_verified: bool = False,
  message: str,
) -> MocReflectedDomainGlobalTransonicClosureResult:
  return MocReflectedDomainGlobalTransonicClosureResult(
    status=status,
    request=request,
    placement=placement,
    pressure_budget=pressure_budget,
    expansion_attempt=expansion_attempt,
    interface_profile_build_audit=interface_profile_build_audit,
    candidate=candidate,
    interface_audit=interface_audit,
    source_lineage_verified=source_lineage_verified,
    placement_lineage_verified=placement_lineage_verified,
    downstream_field_attempted=downstream_field_attempted,
    joint_interface_consumption_verified=joint_interface_consumption_verified,
    message=message,
  )
####


def _build_pressure_budget(
  placement: MocTransonicShockInterfaceFieldPlacementResult,
  target_pressure_Pa: float,
  profile_audit: MocTransonicShockInterfaceProfileBuildAudit,
) -> MocReflectedDomainGlobalTransonicPressureBudget | None:
  profile = placement.profile
  if profile is None:
    return None
  ####
  upstream = tuple(sample.static_pressure_Pa for sample in profile.upstream_samples)
  downstream = tuple(
    sample.static_pressure_Pa for sample in profile.downstream_samples
  )
  if not upstream or len(upstream) != len(downstream):
    return None
  ####
  minimum_upstream = min(upstream)
  maximum_upstream = max(upstream)
  minimum_downstream = min(downstream)
  maximum_downstream = max(downstream)
  jumps = tuple(
    downstream_value - upstream_value
    for upstream_value, downstream_value in zip(upstream, downstream, strict=True)
  )
  minimum_jump = min(jumps)
  tolerance = max(1.0e-9, 1.0e-12 * max(target_pressure_Pa, minimum_upstream))
  target_below_upstream = target_pressure_Pa < minimum_upstream - tolerance
  target_below_compression = target_pressure_Pa < minimum_downstream - tolerance
  compression_increase = bool(minimum_jump > tolerance)
  return MocReflectedDomainGlobalTransonicPressureBudget(
    target_pressure_Pa=target_pressure_Pa,
    minimum_upstream_static_pressure_Pa=minimum_upstream,
    maximum_upstream_static_pressure_Pa=maximum_upstream,
    minimum_derived_downstream_static_pressure_Pa=minimum_downstream,
    maximum_derived_downstream_static_pressure_Pa=maximum_downstream,
    minimum_static_pressure_jump_Pa=minimum_jump,
    target_minus_upstream_pressure_floor_Pa=target_pressure_Pa - minimum_upstream,
    target_minus_compression_pressure_floor_Pa=(
      target_pressure_Pa - minimum_downstream
    ),
    independent_profile_verified=profile_audit.converged,
    compression_pressure_increase_verified=compression_increase,
    target_below_upstream_pressure_floor=target_below_upstream,
    target_below_compression_pressure_floor=target_below_compression,
    message=(
      'attached compression pressure budget is feasible at the retained '
      'profile'
      if not target_below_compression
      else (
        'requested target is below the currently retained normal-shock '
        'profile pressure; a future joint solver may need a different '
        'compression/expansion law'
      )
    ),
  )
####


def _joint_interface_consumption_verified(
  request: MocReflectedDomainGlobalTransonicClosureRequest,
  placement: MocTransonicShockInterfaceFieldPlacementResult,
  candidate: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> bool:
  exact_field = None
  if request.closure.global_euler is not None:
    physical = request.closure.global_euler.physical_field
    if physical is not None:
      exact_field = physical.field
    ####
  ####
  coupled_request = candidate.coupled_request
  coupled_field = candidate.coupled_field
  return bool(
    exact_field is not None
    and placement.request.field is exact_field
    and placement.field is exact_field
    and coupled_request is not None
    and coupled_field is not None
    and coupled_request.source_closure_fingerprint
    == request.source_closure_fingerprint
    and coupled_request.transonic_shock_interface_field_placement is placement
    and coupled_field.request is coupled_request
    and coupled_field.transonic_shock_interface_field_placement is placement
    and coupled_field.transonic_shock_interface_field_placement_consumed
    and coupled_field.transonic_shock_interface_profile_consumed
  )
####


def run_reflected_domain_global_transonic_expansion_attempt(
  request: MocReflectedDomainGlobalTransonicClosureRequest,
  *,
  pressure_floor_Pa: float | None = None,
) -> MocReflectedDomainGlobalTransonicExpansionAttempt:
  """Carry the exact global field into the bounded mixed-regime research lane.

  The existing entropy-characteristic continuation is the highest-fidelity
  pressure-lowering path currently available to this gate.  It is consumed
  only from the exact retained global Euler field.  If the continuation still
  asks the compression-only boundary marcher to handle a negative turn, the
  result is a typed ``EXPANSION_REQUIRED`` stop; no endpoint or pressure is
  invented and the global closure remains open.
  """

  status_type = MocReflectedDomainGlobalTransonicExpansionAttemptStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalTransonicClosureRequest,
  ):
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.INVALID_INPUT,
      request=None,
      message=(
        'request must be a MocReflectedDomainGlobalTransonicClosureRequest'
      ),
    )
  ####
  closure = request.closure
  source_lineage_verified = bool(
    request.source_frontier_fingerprint is not None
    and closure.converged
    and closure.physical_closure_verified
    and closure.source_frontier_verified
  )
  if not source_lineage_verified:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.SOURCE_CLOSURE_FAILURE,
      request=request,
      message=(
        'exact-source expansion attempt requires a locally verified global '
        'physical closure and frontier fingerprint'
      ),
    )
  ####
  global_euler = closure.global_euler
  physical = None if global_euler is None else global_euler.physical_field
  source_field = None if physical is None else physical
  exact_field = None if physical is None else physical.field
  if (
    physical is None
    or exact_field is None
    or not physical.converged
    or not physical.physical_closure_verified
    or not physical.state_sampling_available
  ):
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.SOURCE_FIELD_FAILURE,
      request=request,
      source_field=source_field,
      message=(
        'exact-source expansion attempt requires the retained global Euler '
        'physical field with a bounded state sampler'
      ),
    )
  ####
  curve = None if global_euler is None else global_euler.shock_boundary
  upstream_static = () if curve is None else tuple(curve.upstream_static_pressure_Pa)
  if pressure_floor_Pa is not None:
    try:
      supplied_floor = float(pressure_floor_Pa)
    except (TypeError, ValueError):
      supplied_floor = float('nan')
    ####
    if not isfinite(supplied_floor) or supplied_floor <= 0.0:
      return MocReflectedDomainGlobalTransonicExpansionAttempt(
        status=status_type.INVALID_INPUT,
        request=request,
        source_field=source_field,
        source_field_consumed=physical is closure.global_euler.physical_field,
        message='pressure_floor_Pa must be finite and positive when supplied',
      )
    ####
  elif not upstream_static or any(
    not isfinite(float(value)) or float(value) <= 0.0
    for value in upstream_static
  ):
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.SOURCE_FIELD_FAILURE,
      request=request,
      source_field=source_field,
      source_field_consumed=physical is closure.global_euler.physical_field,
      message=(
        'exact-source expansion attempt requires finite upstream static '
        'pressure samples on the retained shock curve'
      ),
    )
  ####
  minimum_upstream = (
    float(pressure_floor_Pa)
    if pressure_floor_Pa is not None
    else min(float(value) for value in upstream_static)
  )
  pressure_tolerance = max(
    1.0e-9,
    1.0e-12 * max(minimum_upstream, request.ambient_pressure_Pa),
  )
  pressure_lowering_required = bool(
    request.ambient_pressure_Pa < minimum_upstream - pressure_tolerance
  )
  common = {
    'request': request,
    'source_field': source_field,
    'minimum_upstream_static_pressure_Pa': minimum_upstream,
    'target_pressure_Pa': request.ambient_pressure_Pa,
    'pressure_lowering_required': pressure_lowering_required,
    'source_field_consumed': physical is closure.global_euler.physical_field,
  }
  try:
    terminal_wedge = solve_euler_ambient_first_wedge_characteristic_remesh(
      physical,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.TERMINAL_WEDGE_FAILURE,
      message=f'exact-source terminal wedge solve raised: {error}',
      **common,
    )
  ####
  if not (
    terminal_wedge.converged
    and terminal_wedge.characteristic_geometry_verified
    and terminal_wedge.variable_entropy_compatibility_verified
  ):
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.TERMINAL_WEDGE_FAILURE,
      terminal_wedge=terminal_wedge,
      message=(
        'exact-source terminal wedge did not pass its local characteristic '
        f'gates: {terminal_wedge.message}'
      ),
      **common,
    )
  ####
  try:
    entropy_trial = solve_euler_ambient_first_wedge_entropy_carry(
      terminal_wedge,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.ENTROPY_CARRY_FAILURE,
      terminal_wedge=terminal_wedge,
      message=f'exact-source entropy carry solve raised: {error}',
      **common,
    )
  ####
  if not (
    entropy_trial.status
    is MocEulerAmbientFirstWedgeEntropyCarryStatus.CONVERGED_LOCAL_ENTROPY_CARRY
    and entropy_trial.pressure_lineage_verified
    and entropy_trial.variable_entropy_compatibility_verified
    and entropy_trial.cell_euler_residual_verified
  ):
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.ENTROPY_CARRY_FAILURE,
      terminal_wedge=terminal_wedge,
      entropy_trial=entropy_trial,
      message=(
        'exact-source entropy carry did not pass its independent pressure, '
        f'characteristic, and local Euler gates: {entropy_trial.message}'
      ),
      **common,
    )
  ####
  try:
    characteristic_field = (
      solve_euler_ambient_first_wedge_entropy_characteristic_field(
        entropy_trial,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.CHARACTERISTIC_FIELD_FAILURE,
      terminal_wedge=terminal_wedge,
      entropy_trial=entropy_trial,
      message=f'exact-source characteristic field solve raised: {error}',
      **common,
    )
  ####
  local_entropy_band_verified = bool(
    characteristic_field.converged
    and characteristic_field.local_consistency_verified
    and characteristic_field.state_sampling_available
    and characteristic_field.continuation_boundary_verified
    and characteristic_field.pressure_lineage_verified
    and characteristic_field.cell_euler_residuals_verified
  )
  if not local_entropy_band_verified:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.CHARACTERISTIC_FIELD_FAILURE,
      terminal_wedge=terminal_wedge,
      entropy_trial=entropy_trial,
      characteristic_field=characteristic_field,
      message=(
        'exact-source entropy-characteristic band did not pass its bounded '
        f'local gates: {characteristic_field.message}'
      ),
      **common,
    )
  ####
  boundary_states = tuple(
    sample.state for sample in characteristic_field.continuation_boundary
  )
  if not boundary_states:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.CHARACTERISTIC_FIELD_FAILURE,
      terminal_wedge=terminal_wedge,
      entropy_trial=entropy_trial,
      characteristic_field=characteristic_field,
      message='exact-source entropy-characteristic band retained no frontier states',
      **common,
    )
  ####
  mixed_wave_path: MocMixedWavePathResult | None = None
  mixed_wave_path_verified = False
  try:
    boundary_pressures = tuple(
      _static_pressure_from_total_pressure(
        total_pressure_Pa=sample.total_pressure_Pa,
        mach=sample.state.mach,
        gamma=sample.state.gamma,
      )
      for sample in characteristic_field.continuation_boundary
    )
    mixed_wave_path = solve_mixed_wave_path(
      boundary_states,
      boundary_pressures,
      tuple(0.0 for _ in boundary_states),
    )
    mixed_wave_path_verified = mixed_wave_path.converged
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    mixed_wave_path = None
    mixed_wave_path_verified = False
  ####
  angle_bracket = (
    min(state.theta_rad for state in boundary_states) - 0.2,
    max(state.theta_rad for state in boundary_states) + 0.2,
  )
  try:
    continuation_closure = (
      solve_euler_ambient_first_wedge_entropy_characteristic_continuation_closure(
        characteristic_field,
        characteristic_field.continuation_boundary,
        request.ambient_pressure_Pa,
        angle_bracket[0],
        angle_bracket[1],
        cycle_count=4,
        subdivision_side_count=32,
        target_centerline_y_m=0.0,
        target_centerline_flow_angle_rad=0.0,
        sample_count=request.sample_count,
        allow_zero_strength_attachment=True,
        allow_zero_strength_endpoints=True,
        use_outgoing_frontier_bridge=True,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=(
        status_type.EXPANSION_REQUIRED
        if pressure_lowering_required
        else status_type.CONTINUATION_FAILURE
      ),
      terminal_wedge=terminal_wedge,
      entropy_trial=entropy_trial,
      characteristic_field=characteristic_field,
      mixed_wave_path=mixed_wave_path,
      mixed_wave_path_verified=mixed_wave_path_verified,
      outer_flow_angle_bracket=angle_bracket,
      message=f'exact-source mixed-regime continuation raised: {error}',
      **common,
    )
  ####
  if continuation_closure.local_closure_verified:
    return MocReflectedDomainGlobalTransonicExpansionAttempt(
      status=status_type.CONVERGED_RESEARCH_MIXED_REGIME_BAND,
      terminal_wedge=terminal_wedge,
      entropy_trial=entropy_trial,
      characteristic_field=characteristic_field,
      continuation_closure=continuation_closure,
      mixed_wave_path=mixed_wave_path,
      mixed_wave_path_verified=mixed_wave_path_verified,
      outer_flow_angle_bracket=angle_bracket,
      local_entropy_band_verified=True,
      mixed_regime_closure_verified=False,
      message=(
        'exact-source mixed-regime continuation formed a bounded local band; '
        'global expansion/free-boundary closure and production promotion '
        'remain blocked'
      ),
      **common,
    )
  ####
  return MocReflectedDomainGlobalTransonicExpansionAttempt(
    status=(
      status_type.EXPANSION_REQUIRED
      if pressure_lowering_required
      else status_type.CONTINUATION_FAILURE
    ),
    terminal_wedge=terminal_wedge,
    entropy_trial=entropy_trial,
    characteristic_field=characteristic_field,
    continuation_closure=continuation_closure,
    mixed_wave_path=mixed_wave_path,
    mixed_wave_path_verified=mixed_wave_path_verified,
    outer_flow_angle_bracket=angle_bracket,
    local_entropy_band_verified=True,
    message=(
      'the exact-source entropy-characteristic band is locally verified, but '
      'the retained continuation/free-boundary path did not close: '
      f'{continuation_closure.message}'
    ),
    **common,
  )
####


def run_reflected_domain_global_transonic_closure(
  request: MocReflectedDomainGlobalTransonicClosureRequest,
) -> MocReflectedDomainGlobalTransonicClosureResult:
  """Run the bounded joint interface/field closure gate.

  The current operator intentionally stops before the coupled solve when the
  attached-compression pressure budget is impossible.  If that gate passes,
  the existing coupled-Euler lane is invoked with the exact solver-owned
  placement and the result is independently audited.  The returned evidence
  remains research-only until the missing centerline/free-boundary/global
  feedback and refinement gates are closed.
  """

  if not isinstance(
    request,
    MocReflectedDomainGlobalTransonicClosureRequest,
  ):
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.INVALID_INPUT,
      None,
      message=(
        'request must be a MocReflectedDomainGlobalTransonicClosureRequest'
      ),
    )
  ####
  source_lineage_verified = bool(
    request.source_frontier_fingerprint is not None
    and request.closure.converged
    and request.closure.physical_closure_verified
    and request.closure.source_frontier_verified
  )
  if request.source_frontier_fingerprint is None:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.FRONTIER_LINEAGE_FAILURE,
      request,
      message=(
        'joint transonic closure requires one retained solver-owned frontier '
        'with an exact frontier fingerprint'
      ),
    )
  ####
  if not source_lineage_verified:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.SOURCE_CLOSURE_FAILURE,
      request,
      source_lineage_verified=False,
      message=(
        'joint transonic closure requires one locally verified global physical '
        'closure with a retained solver-owned frontier'
      ),
    )
  ####
  try:
    placement = build_reflected_domain_global_solver_owned_transonic_interface_placement(
      request.closure,
      sample_count=request.sample_count,
      post_shock_fraction=request.post_shock_fraction,
      target_downstream_static_pressure_Pa=request.ambient_pressure_Pa,
      target_pressure_tolerance_fraction=(
        request.target_pressure_tolerance_fraction
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.PLACEMENT_FAILURE,
      request,
      source_lineage_verified=True,
      message=f'solver-owned interface placement raised: {error}',
    )
  ####
  placement_lineage_verified = bool(
    request.closure.global_euler is not None
    and request.closure.global_euler.physical_field is not None
    and request.closure.global_euler.physical_field.field is not None
    and placement.request.field is request.closure.global_euler.physical_field.field
    and placement.field is request.closure.global_euler.physical_field.field
  )
  profile_build = (
    None
    if placement.profile_result is None
    else placement.profile_result.profile_build
  )
  if profile_build is None:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.INTERFACE_PROFILE_AUDIT_FAILURE,
      request,
      placement=placement,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      message=(
        'solver-owned placement retained no profile build for independent '
        'Rankine--Hugoniot pressure-budget rederivation'
      ),
    )
  ####
  try:
    profile_audit = measure_moc_transonic_shock_interface_profile_build(
      profile_build
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.INTERFACE_PROFILE_AUDIT_FAILURE,
      request,
      placement=placement,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      message=f'interface profile audit raised: {error}',
    )
  ####
  pressure_budget = _build_pressure_budget(
    placement,
    request.ambient_pressure_Pa,
    profile_audit,
  )
  if pressure_budget is None or not profile_audit.converged:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.INTERFACE_PROFILE_AUDIT_FAILURE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      message=(
        'retained interface profile did not pass independent pressure and '
        'Rankine--Hugoniot evidence'
      ),
    )
  ####
  if (
    placement.status is (
      MocTransonicShockInterfaceFieldPlacementStatus
      .TARGET_PRESSURE_UNREACHABLE
    )
    or pressure_budget.hard_stop_required
  ):
    expansion_attempt = run_reflected_domain_global_transonic_expansion_attempt(
      request,
      pressure_floor_Pa=pressure_budget.minimum_upstream_static_pressure_Pa,
    )
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.INTERFACE_TARGET_UNREACHABLE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      expansion_attempt=expansion_attempt,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      message=(
        'solver-owned compression interface target is unreachable at the '
        f'retained field: target={request.ambient_pressure_Pa:.6g} Pa, '
      f'upstream pressure floor='
        f'{pressure_budget.minimum_upstream_static_pressure_Pa:.6g} Pa, '
        f'derived normal-shock pressure='
        f'{pressure_budget.minimum_derived_downstream_static_pressure_Pa:.6g} '
        'Pa; no downstream field was attempted, and an expansion/mixed-regime '
        'joint solve is required'
      ),
    )
  ####
  if not placement.converged or not placement_lineage_verified:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.PLACEMENT_FAILURE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      message=(
        'solver-owned interface placement did not pass its complete lineage '
        f'gate: {placement.message}'
      ),
    )
  ####
  try:
    candidate = solve_reflected_domain_global_coupled_downstream(
      request.closure,
      reference_total_temperature_K=request.reference_total_temperature_K,
      ambient_pressure_Pa=request.ambient_pressure_Pa,
      downstream_length_m=request.downstream_length_m,
      initial_outlet_height_m=request.initial_outlet_height_m,
      control_section_x_offset_m=request.control_section_x_offset_m,
      control_section_height_m=request.control_section_height_m,
      control_section_sample_count=request.control_section_sample_count,
      axial_station_count=request.axial_station_count,
      axial_cell_count=request.axial_cell_count,
      transverse_cell_count=request.transverse_cell_count,
      max_pseudo_iterations=request.max_pseudo_iterations,
      max_shape_iterations=request.max_shape_iterations,
      inlet_boundary_mode=request.inlet_boundary_mode,
      outlet_static_pressure_Pa=request.outlet_static_pressure_Pa,
      transonic_shock_interface_field_placement=placement,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.COUPLED_FIELD_FAILURE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      downstream_field_attempted=True,
      message=f'joint downstream field solver raised: {error}',
    )
  ####
  joint_consumption_verified = _joint_interface_consumption_verified(
    request,
    placement,
    candidate,
  )
  if candidate.coupled_field is None:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.COUPLED_FIELD_FAILURE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      candidate=candidate,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      downstream_field_attempted=True,
      joint_interface_consumption_verified=joint_consumption_verified,
      message=(
        'joint downstream field attempt retained no coupled-Euler field: '
        f'{candidate.message}'
      ),
    )
  ####
  try:
    interface_audit = measure_reflected_domain_global_transonic_interface(
      candidate
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.BOUNDARY_RESIDUAL_FAILURE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      candidate=candidate,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      downstream_field_attempted=True,
      joint_interface_consumption_verified=joint_consumption_verified,
      message=f'joint interface boundary audit raised: {error}',
    )
  ####
  if not joint_consumption_verified:
    return _result(
      MocReflectedDomainGlobalTransonicClosureStatus.INTERFACE_LINEAGE_FAILURE,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      candidate=candidate,
      interface_audit=interface_audit,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      downstream_field_attempted=True,
      joint_interface_consumption_verified=False,
      message=(
        'coupled field did not consume the exact solver-owned interface '
        'placement and profile'
      ),
    )
  ####
  if (
    not interface_audit.converged
    or not interface_audit.joint_boundary_residuals_verified
    or not candidate.converged
  ):
    status = (
      MocReflectedDomainGlobalTransonicClosureStatus
      .CENTERLINE_BOUNDARY_FAILURE
      if interface_audit.interface_jump_verified
      and interface_audit.ambient_boundary_verified
      and not interface_audit.centerline_boundary_verified
      else MocReflectedDomainGlobalTransonicClosureStatus.BOUNDARY_RESIDUAL_FAILURE
    )
    return _result(
      status,
      request,
      placement=placement,
      pressure_budget=pressure_budget,
      interface_profile_build_audit=profile_audit,
      candidate=candidate,
      interface_audit=interface_audit,
      source_lineage_verified=True,
      placement_lineage_verified=placement_lineage_verified,
      downstream_field_attempted=True,
      joint_interface_consumption_verified=True,
      message=(
        'joint downstream field did not close all independently audited '
        f'boundaries: {interface_audit.message}'
      ),
    )
  ####
  return _result(
    MocReflectedDomainGlobalTransonicClosureStatus
    .CONVERGED_RESEARCH_JOINT_CLOSURE,
    request,
    placement=placement,
    pressure_budget=pressure_budget,
    interface_profile_build_audit=profile_audit,
    candidate=candidate,
    interface_audit=interface_audit,
    source_lineage_verified=True,
    placement_lineage_verified=placement_lineage_verified,
    downstream_field_attempted=True,
    joint_interface_consumption_verified=True,
    message=(
      'solver-owned interface, downstream field, ambient boundary, centerline '
      'boundary, and independent residual gates passed locally; canonical '
      'global closure and production promotion remain blocked'
    ),
  )
####
