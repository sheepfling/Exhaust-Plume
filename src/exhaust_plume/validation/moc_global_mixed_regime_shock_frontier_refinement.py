"""Disjoint source/resolution coverage for the physical shock frontier.

The coupled downstream trace can be entirely subsonic, while the verified
global Euler closure still retains a supersonic shock frontier. This runner
keeps those contracts separate: it binds the exact global frontier to the
research state equation, characteristic frame, incoming-family compatibility,
and local normal closure. It never turns that local handoff into a canonical
global fixed point or a production claim.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.global_mixed_regime_normal_closure import (
  MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState,
  MocReflectedDomainGlobalMixedRegimeNormalClosureAudit,
  MocReflectedDomainGlobalMixedRegimeNormalClosureRequest,
  MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
  audit_reflected_domain_global_mixed_regime_normal_closure,
  solve_reflected_domain_global_mixed_regime_normal_closure,
)
from exhaust_plume.models.moc.global_mixed_regime_characteristic_free_boundary import (
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit,
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureSample,
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest,
  MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult,
  audit_reflected_domain_global_mixed_regime_characteristic_free_boundary,
  solve_reflected_domain_global_mixed_regime_characteristic_free_boundary,
)
from exhaust_plume.models.moc.global_mixed_regime_transonic_interface import (
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest,
  MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
  audit_reflected_domain_global_mixed_regime_transonic_interface,
  solve_reflected_domain_global_mixed_regime_transonic_interface,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_compatibility import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
  audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility,
  consume_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
  admit_reflected_domain_global_mixed_regime_upstream_characteristic_equation,
  audit_reflected_domain_global_mixed_regime_upstream_characteristic_equation,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_characteristic_frame import (
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
  audit_reflected_domain_global_mixed_regime_upstream_characteristic_frame,
  build_reflected_domain_global_mixed_regime_upstream_characteristic_frame,
)
from exhaust_plume.models.moc.global_mixed_regime_upstream_state_equation import (
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
  MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
  build_reflected_domain_global_mixed_regime_upstream_state_equation_request_from_global_shock_frontier,
  audit_reflected_domain_global_mixed_regime_upstream_state_equation,
  solve_reflected_domain_global_mixed_regime_upstream_state_equation,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_SHOCK_FRONTIER_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus',
  'MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase',
  'MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep',
  'MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementMeasurement',
  'run_reflected_domain_global_mixed_regime_shock_frontier_step',
  'measure_reflected_domain_global_mixed_regime_shock_frontier_refinement',
  'run_reflected_domain_global_mixed_regime_shock_frontier_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_SHOCK_FRONTIER_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-shock-frontier-refinement-v1'
)


class MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus(
  str,
  Enum,
):
  """Typed outcomes of the shock-frontier coverage gate."""

  CONVERGED_LOCAL_RESEARCH_COVERAGE = (
    'converged-local-research-shock-frontier-coverage'
  )
  CONVERGED_CROSS_CASE_RESEARCH_COVERAGE = (
    'converged-cross-case-research-shock-frontier-coverage'
  )
  COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE = (
    'completed-research-shock-frontier-coverage-with-open-gate'
  )
  INVALID_INPUT = 'invalid_input'
  FRONTIER_FAILURE = 'shock-frontier-refinement-frontier-failure'
####


def _positive(name: str, value: object) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _frontier_sample_count(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> int:
  if closure.global_euler is None or closure.global_euler.shock_boundary is None:
    return 0
  ####
  return len(closure.global_euler.shock_boundary.shock_points_m)
####


def _increasing(values: Sequence[int]) -> bool:
  return bool(
    len(values) >= 2
    and all(right > left for left, right in zip(values, values[1:]))
  )
####


def _interface_normals(
  points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
  if len(points) < 2:
    raise ValueError('shock-frontier interface requires at least two points')
  ####
  normals: list[tuple[float, float]] = []
  for index, _point in enumerate(points):
    if index == 0:
      first, second = points[0], points[1]
    elif index == len(points) - 1:
      first, second = points[-2], points[-1]
    else:
      first, second = points[index - 1], points[index + 1]
    ####
    tangent_x = second[0] - first[0]
    tangent_y = second[1] - first[1]
    length = sqrt(tangent_x * tangent_x + tangent_y * tangent_y)
    if not isfinite(length) or length <= 0.0:
      raise ValueError('shock-frontier tangent must have positive length')
    ####
    normals.append((-tangent_y / length, tangent_x / length))
  ####
  return tuple(normals)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase:
  """One physical closure and its exact shock-frontier sampling resolution."""

  case_id: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  reference_total_temperature_K: float
  sample_start_index: int = 1
  normal_offset_m: float = 1.0e-3
  offset_side: float = 1.0
  invariant_tolerance: float = 5.0e-4
  geometry_tolerance: float = 1.0e-2
  component_tolerance: float = 1.0e-5
  target_entropy_consistency_tolerance: float = 1.0e-4
  boundary_family: CharacteristicFamily = CharacteristicFamily.PLUS

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if (
      isinstance(self.sample_start_index, bool)
      or not isinstance(self.sample_start_index, int)
      or self.sample_start_index < 0
    ):
      raise ValueError('sample_start_index must be a nonnegative integer')
    ####
    offset_side = float(self.offset_side)
    if not isfinite(offset_side) or abs(abs(offset_side) - 1.0) > 1.0e-12:
      raise ValueError('offset_side must be either -1 or +1')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(
      self,
      'reference_total_temperature_K',
      _positive('reference_total_temperature_K', self.reference_total_temperature_K),
    )
    for name in (
      'normal_offset_m',
      'invariant_tolerance',
      'geometry_tolerance',
      'component_tolerance',
      'target_entropy_consistency_tolerance',
    ):
      object.__setattr__(self, name, _positive(name, getattr(self, name)))
    ####
    object.__setattr__(self, 'offset_side', offset_side)
    if not isinstance(self.boundary_family, CharacteristicFamily):
      raise TypeError('boundary_family must be a CharacteristicFamily')
    ####
  ####

  @property
  def frontier_sample_count(self) -> int:
    return _frontier_sample_count(self.closure)
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'frontier_sample_count': self.frontier_sample_count,
      'sample_start_index': self.sample_start_index,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'normal_offset_m': self.normal_offset_m,
      'offset_side': self.offset_side,
      'invariant_tolerance': self.invariant_tolerance,
      'geometry_tolerance': self.geometry_tolerance,
      'component_tolerance': self.component_tolerance,
      'target_entropy_consistency_tolerance': (
        self.target_entropy_consistency_tolerance
      ),
      'boundary_family': self.boundary_family.value,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'closure_status': self.closure.status.value,
      'closure_converged': self.closure.converged,
      'physical_closure_verified': self.closure.physical_closure_verified,
    }
  ####
####


def _ambient_profile(
  case: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
  request: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
) -> tuple[MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState, ...]:
  closure = case.closure
  if closure.global_euler is None or closure.global_euler.shock_boundary is None:
    raise ValueError('global closure retains no exact Euler shock frontier')
  ####
  shock = closure.global_euler.shock_boundary
  states = tuple(shock.downstream_states[case.sample_start_index:])
  total_pressure = tuple(
    float(value)
    for value in shock.downstream_total_pressure_Pa[case.sample_start_index:]
  )
  points = request.target_points_m
  if len(states) != len(total_pressure) or len(states) != len(points):
    raise ValueError(
      'downstream shock states and total pressures must align with the '
      'retained shock-frontier target points'
    )
  ####
  profile: list[MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState] = []
  gamma = request.target_gamma
  gas_constant = request.gas_constant_J_kgK
  for index, (state, pressure_total, point) in enumerate(
    zip(states, total_pressure, points, strict=True)
  ):
    factor = 1.0 + 0.5 * (gamma - 1.0) * state.mach * state.mach
    static_pressure = pressure_total / factor ** (gamma / (gamma - 1.0))
    static_temperature = request.reference_total_temperature_K / factor
    density = static_pressure / (gas_constant * static_temperature)
    sound_speed = sqrt(gamma * gas_constant * static_temperature)
    speed = state.mach * sound_speed
    profile.append(
      MocReflectedDomainGlobalMixedRegimeNormalClosureAmbientState(
        sample_index=index,
        point_m=point,
        density_kg_m3=density,
        velocity_u_m_s=speed * cos(state.theta_rad),
        velocity_v_m_s=speed * sin(state.theta_rad),
        static_pressure_Pa=static_pressure,
        static_temperature_K=static_temperature,
        gamma=gamma,
        specific_gas_constant_J_kg_K=gas_constant,
      )
    )
  ####
  return tuple(profile)
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep:
  """One exact frontier handoff and its independent replay chain."""

  case_id: str
  sample_start_index: int
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  state_equation_request: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest
  state_equation: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult
  state_equation_audit: MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit
  characteristic_frame: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult
  characteristic_frame_audit: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit
  transonic_interface: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult
  transonic_interface_audit: MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit
  characteristic_handoff: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult
  characteristic_handoff_audit: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit
  compatibility_request: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest
  compatibility: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult
  compatibility_audit: MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit
  free_boundary_request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest
  free_boundary: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult
  free_boundary_audit: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit
  normal_closure_request: MocReflectedDomainGlobalMixedRegimeNormalClosureRequest
  normal_closure: MocReflectedDomainGlobalMixedRegimeNormalClosureResult
  normal_closure_audit: MocReflectedDomainGlobalMixedRegimeNormalClosureAudit

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('closure must be a typed global physical closure')
    ####
    if (
      isinstance(self.sample_start_index, bool)
      or not isinstance(self.sample_start_index, int)
      or self.sample_start_index < 0
    ):
      raise ValueError('sample_start_index must be a nonnegative integer')
    ####
    typed = (
      (
        'state_equation_request',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationRequest,
      ),
      (
        'state_equation',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationResult,
      ),
      (
        'state_equation_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamStateEquationAudit,
      ),
      (
        'characteristic_frame',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameResult,
      ),
      (
        'characteristic_frame_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameAudit,
      ),
      (
        'transonic_interface',
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceResult,
      ),
      (
        'transonic_interface_audit',
        MocReflectedDomainGlobalMixedRegimeTransonicInterfaceAudit,
      ),
      (
        'characteristic_handoff',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationResult,
      ),
      (
        'characteristic_handoff_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationAudit,
      ),
      (
        'compatibility_request',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest,
      ),
      (
        'compatibility',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityResult,
      ),
      (
        'compatibility_audit',
        MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityAudit,
      ),
      (
        'free_boundary_request',
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest,
      ),
      (
        'free_boundary',
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryResult,
      ),
      (
        'free_boundary_audit',
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryAudit,
      ),
      (
        'normal_closure_request',
        MocReflectedDomainGlobalMixedRegimeNormalClosureRequest,
      ),
      (
        'normal_closure',
        MocReflectedDomainGlobalMixedRegimeNormalClosureResult,
      ),
      (
        'normal_closure_audit',
        MocReflectedDomainGlobalMixedRegimeNormalClosureAudit,
      ),
    )
    for name, expected in typed:
      if not isinstance(getattr(self, name), expected):
        raise TypeError(f'{name} must retain its typed solver result')
      ####
    ####
    object.__setattr__(self, 'case_id', case_id)
  ####

  @property
  def frontier_sample_count(self) -> int:
    return (
      len(self.state_equation_request.target_points_m)
      + self.sample_start_index
    )
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def source_lineage_verified(self) -> bool:
    equation_request = self.state_equation.request
    frame_request = self.characteristic_frame.request
    interface_request = self.transonic_interface.request
    handoff_request = self.characteristic_handoff.request
    normal_request = self.normal_closure.request
    free_boundary_request = self.free_boundary.request
    return bool(
      self.state_equation_request.closure is self.closure
      and equation_request is self.state_equation_request
      and frame_request is not None
      and frame_request.upstream_state_equation is self.state_equation
      and interface_request is not None
      and interface_request.characteristic_frame is self.characteristic_frame
      and handoff_request is not None
      and handoff_request.transonic_interface is self.transonic_interface
      and self.compatibility.request is self.compatibility_request
      and self.compatibility_request.upstream_equation_handoff
      is self.characteristic_handoff
      and free_boundary_request is self.free_boundary_request
      and free_boundary_request.characteristic_compatibility
      is self.compatibility
      and free_boundary_request.characteristic_compatibility_audit
      is self.compatibility_audit
      and normal_request is self.normal_closure_request
      and normal_request.transonic_interface is self.transonic_interface
      and normal_request.characteristic_compatibility is self.compatibility
      and self.state_equation.source_closure is self.closure
      and self.characteristic_frame.source_closure is self.closure
    )
  ####

  @property
  def independent_audits_verified(self) -> bool:
    return bool(
      self.state_equation_audit.converged
      and self.state_equation_audit.result is self.state_equation
      and self.characteristic_frame_audit.converged
      and self.characteristic_frame_audit.result is self.characteristic_frame
      and self.transonic_interface_audit.converged
      and self.transonic_interface_audit.candidate is self.transonic_interface
      and self.characteristic_handoff_audit.converged
      and self.characteristic_handoff_audit.candidate
      is self.characteristic_handoff
      and self.compatibility_audit.converged
      and self.compatibility_audit.candidate is self.compatibility
      and self.free_boundary_audit.converged
      and self.free_boundary_audit.candidate is self.free_boundary
      and self.normal_closure_audit.converged
      and self.normal_closure_audit.candidate is self.normal_closure
    )
  ####

  @property
  def frontier_regime_verified(self) -> bool:
    return bool(
      self.characteristic_frame.converged
      and self.characteristic_frame.supersonic_sample_count
      == len(self.characteristic_frame.samples)
      and self.characteristic_frame.subsonic_or_sonic_sample_count == 0
      and self.transonic_interface.converged
      and self.transonic_interface.supersonic_sample_count
      == len(self.characteristic_frame.samples)
      and self.characteristic_handoff.interface_handoff_verified
      and self.characteristic_handoff.incoming_characteristic_count > 0
      and self.compatibility.converged
      and self.compatibility.compatibility_gate_verified
      and self.free_boundary.converged
      and self.free_boundary.equation_consumption_verified
      and self.normal_closure.converged
      and self.normal_closure.normal_closure_verified
    )
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      self.characteristic_handoff.chain_promotion_blocked
      and self.compatibility.chain_promotion_blocked
      and self.free_boundary.chain_promotion_blocked
      and self.normal_closure.chain_promotion_blocked
      and not self.characteristic_handoff.upstream_characteristic_equation_consumed
      and not self.compatibility.upstream_characteristic_equation_consumed
      and not self.normal_closure.canonical_free_boundary_verified
      and not self.normal_closure.global_coupling_verified
      and not self.characteristic_handoff.production_claim_allowed
      and not self.compatibility.production_claim_allowed
      and not self.free_boundary.canonical_free_boundary_verified
      and not self.free_boundary.global_coupling_verified
      and not self.free_boundary.production_claim_allowed
      and not self.normal_closure.production_claim_allowed
    )
  ####

  @property
  def locally_verified(self) -> bool:
    return bool(
      self.source_lineage_verified
      and self.independent_audits_verified
      and self.frontier_regime_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'sample_start_index': self.sample_start_index,
      'frontier_sample_count': self.frontier_sample_count,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_lineage_verified': self.source_lineage_verified,
      'independent_audits_verified': self.independent_audits_verified,
      'frontier_regime_verified': self.frontier_regime_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'locally_verified': self.locally_verified,
      'metrics': {
        'maximum_mach': max(
          (sample.mach for sample in self.characteristic_frame.samples),
          default=None,
        ),
        'supersonic_sample_count': (
          self.characteristic_frame.supersonic_sample_count
        ),
        'incoming_characteristic_count': (
          self.characteristic_handoff.incoming_characteristic_count
        ),
        'maximum_invariant_residual': (
          self.compatibility.maximum_invariant_residual
        ),
        'maximum_geometry_residual': (
          self.compatibility.maximum_geometry_residual
        ),
        'maximum_free_boundary_pressure_residual': (
          self.free_boundary.maximum_absolute_pressure_residual
        ),
        'maximum_free_boundary_tangent_residual': (
          self.free_boundary.maximum_absolute_tangent_residual
        ),
        'maximum_free_boundary_geometry_residual': (
          self.free_boundary.maximum_geometry_residual
        ),
        'maximum_component_residual': (
          self.normal_closure.maximum_component_residual
        ),
      },
      'state_equation': self.state_equation.as_report(),
      'state_equation_audit': self.state_equation_audit.as_report(),
      'characteristic_frame': self.characteristic_frame.as_report(),
      'characteristic_frame_audit': self.characteristic_frame_audit.as_report(),
      'transonic_interface': self.transonic_interface.as_report(),
      'transonic_interface_audit': self.transonic_interface_audit.as_report(),
      'characteristic_handoff': self.characteristic_handoff.as_report(),
      'characteristic_handoff_audit': self.characteristic_handoff_audit.as_report(),
      'compatibility': self.compatibility.as_report(),
      'compatibility_audit': self.compatibility_audit.as_report(),
      'free_boundary_request': self.free_boundary_request.as_report(),
      'free_boundary': self.free_boundary.as_report(),
      'free_boundary_audit': self.free_boundary_audit.as_report(),
      'normal_closure': self.normal_closure.as_report(),
      'normal_closure_audit': self.normal_closure_audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementMeasurement:
  """Coverage evidence below canonical/global/production claim ceilings."""

  status: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus
  steps: tuple[MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep, ...] = ()
  case_ids: tuple[str, ...] = ()
  frontier_sample_counts: tuple[int, ...] = ()
  source_closure_fingerprints: tuple[str, ...] = ()
  local_case_resolution_ladders_verified: bool = False
  distinct_source_closures_verified: bool = False
  source_lineage_verified: bool = False
  frontier_regimes_verified: bool = False
  independent_audits_verified: bool = False
  fidelity_isolation_verified: bool = False
  local_coverage_verified: bool = False
  cross_case_coverage_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_SHOCK_FRONTIER_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus,
    ):
      raise TypeError('status must be a typed shock-frontier refinement status')
    ####
    steps = tuple(self.steps)
    if any(
      not isinstance(
        step,
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
      )
      for step in steps
    ):
      raise TypeError('steps must contain typed shock-frontier refinement steps')
    ####
    case_ids = tuple(str(value) for value in self.case_ids)
    counts = tuple(int(value) for value in self.frontier_sample_counts)
    fingerprints = tuple(str(value) for value in self.source_closure_fingerprints)
    if not (len(case_ids) == len(counts) == len(fingerprints) == len(steps)):
      raise ValueError('measurement summaries must match the step count')
    ####
    for name in (
      'local_case_resolution_ladders_verified',
      'distinct_source_closures_verified',
      'source_lineage_verified',
      'frontier_regimes_verified',
      'independent_audits_verified',
      'fidelity_isolation_verified',
      'local_coverage_verified',
      'cross_case_coverage_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('shock-frontier coverage cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('shock-frontier coverage must remain promotion-blocked')
    ####
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'frontier_sample_counts', counts)
    object.__setattr__(self, 'source_closure_fingerprints', fingerprints)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in {
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus
        .CONVERGED_LOCAL_RESEARCH_COVERAGE,
        MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus
        .CONVERGED_CROSS_CASE_RESEARCH_COVERAGE,
      }
      and self.local_coverage_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'frontier_sample_counts': self.frontier_sample_counts,
      'source_closure_fingerprints': self.source_closure_fingerprints,
      'checks': {
        'local_case_resolution_ladders_verified': (
          self.local_case_resolution_ladders_verified
        ),
        'distinct_source_closures_verified': (
          self.distinct_source_closures_verified
        ),
        'source_lineage_verified': self.source_lineage_verified,
        'frontier_regimes_verified': self.frontier_regimes_verified,
        'independent_audits_verified': self.independent_audits_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'local_coverage_verified': self.local_coverage_verified,
        'cross_case_coverage_verified': self.cross_case_coverage_verified,
        'canonical_free_boundary_verified': False,
        'global_coupling_verified': False,
        'external_validation_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'steps': tuple(step.as_report() for step in self.steps),
      'message': self.message,
      'claim_status': (
        'research-only physical global shock-frontier handoff coverage; the '
        'subsonic coupled downstream seam, canonical fixed point, external '
        'validation, and production promotion remain separate gates'
      ),
    }
  ####
####


def _measurement(
  status: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus,
  message: str,
  *,
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep] = (),
  **flags: bool,
) -> MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementMeasurement:
  retained = tuple(steps)
  return MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementMeasurement(
    status=status,
    steps=retained,
    case_ids=tuple(step.case_id for step in retained),
    frontier_sample_counts=tuple(
      step.frontier_sample_count for step in retained
    ),
    source_closure_fingerprints=tuple(
      step.source_closure_fingerprint for step in retained
    ),
    **flags,
    message=message,
  )
####


def measure_reflected_domain_global_mixed_regime_shock_frontier_refinement(
  steps: Sequence[MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementMeasurement:
  """Audit exact frontier handoffs by source case and sample resolution."""

  status_type = MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus
  try:
    retained = tuple(steps)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'steps must be iterable')
  ####
  if len(retained) < 2:
    return _measurement(
      status_type.INVALID_INPUT,
      'shock-frontier refinement requires at least two steps',
    )
  ####
  if any(
    not isinstance(
      step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    )
    for step in retained
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'steps must contain typed shock-frontier refinement steps',
    )
  ####
  grouped: dict[str, list[MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep]] = defaultdict(list)
  for step in retained:
    grouped[step.case_id].append(step)
  ####
  actual_case_ids = tuple(grouped)
  expected = (
    None
    if expected_case_ids is None
    else tuple(str(value) for value in expected_case_ids)
  )
  case_ids_verified = bool(
    actual_case_ids
    and all(actual_case_ids)
    and (expected is None or actual_case_ids == expected)
  )
  ladders = bool(
    grouped
    and all(
      _increasing(tuple(step.frontier_sample_count for step in case_steps))
      for case_steps in grouped.values()
    )
  )
  fingerprints = tuple(step.source_closure_fingerprint for step in retained)
  distinct_sources = bool(
    len(grouped) >= 2
    and len(set(fingerprints)) >= len(grouped)
  )
  source_lineage = all(step.source_lineage_verified for step in retained)
  frontier_regimes = all(step.frontier_regime_verified for step in retained)
  independent_audits = all(step.independent_audits_verified for step in retained)
  fidelity_isolation = all(step.fidelity_isolation_verified for step in retained)
  local_coverage = bool(
    case_ids_verified
    and ladders
    and source_lineage
    and frontier_regimes
    and independent_audits
    and fidelity_isolation
  )
  cross_case = bool(local_coverage and distinct_sources)
  status = (
    status_type.CONVERGED_CROSS_CASE_RESEARCH_COVERAGE
    if cross_case
    else status_type.CONVERGED_LOCAL_RESEARCH_COVERAGE
    if local_coverage
    else status_type.COMPLETED_RESEARCH_COVERAGE_WITH_OPEN_GATE
  )
  message = (
    'physical shock-frontier handoff passed independent replay across '
    'distinct source closures and strictly increasing frontier resolutions; '
    'canonical/global promotion remains open'
    if cross_case
    else 'physical shock-frontier handoff passed independent replay across a '
    'strictly increasing frontier-resolution ladder for the supplied source '
    'case; a disjoint source-closure gate remains open'
    if local_coverage
    else 'shock-frontier evidence was retained, but case, resolution, lineage, '
    'regime, audit, or fidelity-isolation gates remain open'
  )
  return _measurement(
    status,
    message,
    steps=retained,
    local_case_resolution_ladders_verified=ladders,
    distinct_source_closures_verified=distinct_sources,
    source_lineage_verified=source_lineage,
    frontier_regimes_verified=frontier_regimes,
    independent_audits_verified=independent_audits,
    fidelity_isolation_verified=fidelity_isolation,
    local_coverage_verified=local_coverage,
    cross_case_coverage_verified=cross_case,
    canonical_free_boundary_verified=False,
    global_coupling_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
  )
####


def _run_case(
  case: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
) -> MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep:
  if not case.closure.converged or not case.closure.physical_closure_verified:
    raise ValueError(
      'case closure must be a locally verified global physical closure'
    )
  ####
  if case.frontier_sample_count <= case.sample_start_index + 1:
    raise ValueError(
      'case closure does not retain enough shock-frontier samples after the '
      'attachment index'
    )
  ####
  state_request = (
    build_reflected_domain_global_mixed_regime_upstream_state_equation_request_from_global_shock_frontier(
      case.closure,
      reference_total_temperature_K=case.reference_total_temperature_K,
      sample_start_index=case.sample_start_index,
      normal_offset_m=case.normal_offset_m,
      offset_side=case.offset_side,
      max_pseudo_iterations=400,
      target_entropy_consistency_tolerance=(
        case.target_entropy_consistency_tolerance
      ),
    )
  )
  state_equation = solve_reflected_domain_global_mixed_regime_upstream_state_equation(
    state_request
  )
  if not state_equation.converged:
    raise ValueError(f'state equation did not converge: {state_equation.message}')
  ####
  state_equation_audit = audit_reflected_domain_global_mixed_regime_upstream_state_equation(
    state_equation
  )
  if not state_equation_audit.converged:
    raise ValueError(
      f'state equation audit did not converge: {state_equation_audit.message}'
    )
  ####
  frame = build_reflected_domain_global_mixed_regime_upstream_characteristic_frame(
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicFrameRequest(
      upstream_state_equation=state_equation,
    )
  )
  if not frame.converged:
    raise ValueError(f'characteristic frame did not converge: {frame.message}')
  ####
  frame_audit = audit_reflected_domain_global_mixed_regime_upstream_characteristic_frame(
    frame
  )
  if not frame_audit.converged:
    raise ValueError(
      f'characteristic frame audit did not converge: {frame_audit.message}'
    )
  ####
  source_band = case.closure.source_band
  if source_band is None or source_band.ambient_pressure_Pa is None:
    raise ValueError('physical closure retains no ambient pressure for interface')
  ####
  interface = solve_reflected_domain_global_mixed_regime_transonic_interface(
    MocReflectedDomainGlobalMixedRegimeTransonicInterfaceRequest(
      characteristic_frame=frame,
      interface_normals_m=_interface_normals(
        tuple(sample.point_m for sample in frame.samples)
      ),
      ambient_pressure_Pa=source_band.ambient_pressure_Pa,
      component_tolerance=case.component_tolerance,
      require_supersonic_characteristic_data=True,
    )
  )
  if not interface.converged:
    raise ValueError(f'transonic interface did not converge: {interface.message}')
  ####
  interface_audit = audit_reflected_domain_global_mixed_regime_transonic_interface(
    interface
  )
  if not interface_audit.converged:
    raise ValueError(
      f'transonic interface audit did not converge: {interface_audit.message}'
    )
  ####
  handoff = admit_reflected_domain_global_mixed_regime_upstream_characteristic_equation(
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicEquationRequest(
      transonic_interface=interface,
      transonic_interface_audit=interface_audit,
      incoming_family=CharacteristicFamily.MINUS,
    )
  )
  if not handoff.interface_handoff_verified:
    raise ValueError(f'characteristic handoff failed: {handoff.message}')
  ####
  handoff_audit = audit_reflected_domain_global_mixed_regime_upstream_characteristic_equation(
    handoff
  )
  if not handoff_audit.converged:
    raise ValueError(
      f'characteristic handoff audit did not converge: {handoff_audit.message}'
    )
  ####
  compatibility_request = (
    MocReflectedDomainGlobalMixedRegimeUpstreamCharacteristicCompatibilityRequest(
      upstream_equation_handoff=handoff,
      invariant_tolerance=case.invariant_tolerance,
      geometry_tolerance=case.geometry_tolerance,
    )
  )
  compatibility = (
    consume_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
      compatibility_request
    )
  )
  if not compatibility.converged or not compatibility.compatibility_gate_verified:
    raise ValueError(
      f'characteristic compatibility did not pass its gate: {compatibility.message}'
    )
  ####
  compatibility_audit = (
    audit_reflected_domain_global_mixed_regime_upstream_characteristic_compatibility(
      compatibility
    )
  )
  if not compatibility_audit.converged:
    raise ValueError(
      'characteristic compatibility audit did not converge: '
      f'{compatibility_audit.message}'
    )
  ####
  ambient_profile = _ambient_profile(case, state_request)
  ambient_by_index = {
    sample.sample_index: sample for sample in ambient_profile
  }
  incoming_ambient_profile = tuple(
    ambient_by_index[sample.sample_index]
    for sample in compatibility.samples
  )
  free_boundary_request = (
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryRequest(
      characteristic_compatibility=compatibility,
      characteristic_compatibility_audit=compatibility_audit,
      ambient_pressure_profile=tuple(
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureSample(
          sample_index=sample.sample_index,
          point_m=(sample.state.x_m, sample.state.y_m),
          ambient_pressure_Pa=ambient.static_pressure_Pa,
        )
        for sample, ambient in zip(
          compatibility.samples,
          incoming_ambient_profile,
          strict=True,
        )
      ),
      seed_boundary_state=compatibility.samples[0].state,
      boundary_family=case.boundary_family,
      geometry_tolerance=case.geometry_tolerance,
    )
  )
  free_boundary = (
    solve_reflected_domain_global_mixed_regime_characteristic_free_boundary(
      free_boundary_request
    )
  )
  if not free_boundary.converged:
    raise ValueError(
      f'characteristic free-boundary march did not converge: '
      f'{free_boundary.message}'
    )
  ####
  free_boundary_audit = (
    audit_reflected_domain_global_mixed_regime_characteristic_free_boundary(
      free_boundary
    )
  )
  if not free_boundary_audit.converged:
    raise ValueError(
      'characteristic free-boundary audit did not converge: '
      f'{free_boundary_audit.message}'
    )
  ####
  normal_request = MocReflectedDomainGlobalMixedRegimeNormalClosureRequest(
    transonic_interface=interface,
    transonic_interface_audit=interface_audit,
    characteristic_compatibility=compatibility,
    characteristic_compatibility_audit=compatibility_audit,
    ambient_state_profile=ambient_profile,
    component_tolerance=case.component_tolerance,
  )
  normal_closure = solve_reflected_domain_global_mixed_regime_normal_closure(
    normal_request
  )
  if not normal_closure.converged:
    raise ValueError(f'normal closure did not converge: {normal_closure.message}')
  ####
  normal_closure_audit = audit_reflected_domain_global_mixed_regime_normal_closure(
    normal_closure
  )
  if not normal_closure_audit.converged:
    raise ValueError(
      f'normal closure audit did not converge: {normal_closure_audit.message}'
    )
  ####
  return MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep(
    case_id=case.case_id,
    sample_start_index=case.sample_start_index,
    closure=case.closure,
    state_equation_request=state_request,
    state_equation=state_equation,
    state_equation_audit=state_equation_audit,
    characteristic_frame=frame,
    characteristic_frame_audit=frame_audit,
    transonic_interface=interface,
    transonic_interface_audit=interface_audit,
    characteristic_handoff=handoff,
    characteristic_handoff_audit=handoff_audit,
    compatibility_request=compatibility_request,
    compatibility=compatibility,
    compatibility_audit=compatibility_audit,
    free_boundary_request=free_boundary_request,
    free_boundary=free_boundary,
    free_boundary_audit=free_boundary_audit,
    normal_closure_request=normal_request,
    normal_closure=normal_closure,
    normal_closure_audit=normal_closure_audit,
  )
####


def run_reflected_domain_global_mixed_regime_shock_frontier_refinement(
  cases: Sequence[MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase],
  *,
  expected_case_ids: Sequence[str] | None = None,
) -> MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementMeasurement:
  """Run and independently audit each declared physical frontier case."""

  status_type = MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStatus
  try:
    retained_cases = tuple(cases)
  except TypeError:
    return _measurement(status_type.INVALID_INPUT, 'cases must be iterable')
  ####
  if len(retained_cases) < 2:
    return _measurement(
      status_type.INVALID_INPUT,
      'shock-frontier refinement requires at least two cases/resolutions',
    )
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
    )
    for case in retained_cases
  ):
    return _measurement(
      status_type.INVALID_INPUT,
      'cases must contain typed shock-frontier refinement cases',
    )
  ####
  steps: list[MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep] = []
  for case in retained_cases:
    try:
      steps.append(_run_case(case))
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _measurement(
        status_type.FRONTIER_FAILURE,
        f'shock-frontier refinement execution failed: {error}',
        steps=steps,
      )
    ####
  ####
  return measure_reflected_domain_global_mixed_regime_shock_frontier_refinement(
    steps,
    expected_case_ids=expected_case_ids,
  )
####


def run_reflected_domain_global_mixed_regime_shock_frontier_step(
  case: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
) -> MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep:
  """Execute one exact physical shock-frontier research step.

  Coverage callers should use the refinement runner above.  This single-step
  entry point exists for a joint feedback consumer that must replay the same
  frontier contract at each fresh global closure; it deliberately returns the
  typed step only on success and leaves failures to the enclosing typed
  consumer.
  """

  if not isinstance(
    case,
    MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
  ):
    raise TypeError(
      'case must be a typed shock-frontier refinement case'
    )
  ####
  return _run_case(case)
####
