"""Refinement evidence for the solver-owned pressure free-boundary lane.

This operator is intentionally separate from the older target-bound refinement
ladder.  That ladder consumes pressure and geometry profiles together.  This
lane consumes a pressure target only and requires the coupled Euler solver to
own the downstream boundary ordinates.  It is local research evidence; it
does not feed a response back into the global solve or authorize production
shock-cell claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerInletBoundaryMode,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
  MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
  MocReflectedDomainGlobalCoupledDownstreamResult,
  build_reflected_domain_global_solver_owned_physical_field_handoff,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.validation.moc_coupled_euler_free_boundary import (
  measure_reflected_domain_coupled_euler_free_boundary,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_CROSS_CASE_REFINEMENT_OPERATOR_ID',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementMeasurement',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun',
  'run_reflected_domain_global_coupled_pressure_free_boundary_refinement',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseMeasurement',
  'MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseRun',
  'run_reflected_domain_global_coupled_pressure_free_boundary_cross_case_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-pressure-free-boundary-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-pressure-free-boundary-refinement-run'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_CROSS_CASE_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-pressure-free-boundary-cross-case-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-pressure-free-boundary-cross-case-refinement-run'
)
_PRESSURE_PROFILE_SOURCE_PREFIX = (
  'research-global-frontier-target-pressure-free-boundary-v1:'
)


class MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus(
  str, Enum
):
  """Typed result for one pressure-only free-boundary ladder."""

  CONVERGED_RESEARCH_LADDER = (
    'converged-research-pressure-free-boundary-ladder'
  )
  INVALID_INPUT = 'invalid_input'
  TARGET_FAILURE = 'pressure-free-boundary-target-failure'
  RESOLUTION_FAILURE = 'pressure-free-boundary-resolution-failure'
  FIDELITY_FAILURE = 'pressure-free-boundary-fidelity-failure'
  CONVERGED_RESEARCH_CROSS_CASE = (
    'converged-research-pressure-free-boundary-cross-case'
  )
  CROSS_CASE_FAILURE = 'pressure-free-boundary-cross-case-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase:
  """One fresh pressure-only coupled solve and its independent audit."""

  resolution: tuple[int, int]
  result: MocReflectedDomainGlobalCoupledDownstreamResult
  pressure_profile: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None
  response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  target_lineage_verified: bool = False
  pressure_consumption_verified: bool = False
  geometry_injection_blocked: bool = False
  geometry_solver_owned_verified: bool = False
  independent_audit_verified: bool = False

  def __post_init__(self) -> None:
    resolution = tuple(self.resolution)
    if len(resolution) != 2 or any(
      isinstance(value, bool) or not isinstance(value, int)
      for value in resolution
    ):
      raise ValueError('resolution must contain two integer counts')
    ####
    if resolution[0] < 4 or resolution[1] < 3:
      raise ValueError(
        'resolution must contain axial >= 4 and transverse >= 3'
      )
    ####
    if not isinstance(
      self.result,
      MocReflectedDomainGlobalCoupledDownstreamResult,
    ):
      raise TypeError(
        'result must be a '
        'MocReflectedDomainGlobalCoupledDownstreamResult'
      )
    ####
    if self.pressure_profile is not None and not isinstance(
      self.pressure_profile,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile,
    ):
      raise TypeError(
        'pressure_profile must be a '
        'MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile '
        'or None'
      )
    ####
    if self.response is not None and not isinstance(
      self.response,
      MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
    ):
      raise TypeError(
        'response must be a '
        'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse or None'
      )
    ####
    for name in (
      'target_lineage_verified',
      'pressure_consumption_verified',
      'geometry_injection_blocked',
      'geometry_solver_owned_verified',
      'independent_audit_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'resolution', resolution)
  ####

  @property
  def local_coupled_field_verified(self) -> bool:
    return bool(self.result.local_coupled_field_verified)
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    field = self.result.coupled_field
    return bool(
      not self.result.global_coupling_verified
      and not self.result.downstream_boundary_closure_verified
      and self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and (field is None or not field.production_claim_allowed)
    )
  ####

  @property
  def response_channels_finite(self) -> bool:
    response = self.response
    if response is None:
      return False
    ####
    return all(
      isfinite(value)
      for channel in (
        response.coordinate_residuals_m,
        response.tangent_residuals_rad,
        response.pressure_residuals_Pa,
        response.normal_velocity_residuals_m_s,
        response.coordinate_offsets_m,
        response.tangent_offsets_rad,
        response.pressure_offsets_Pa,
        response.normal_velocity_values_m_s,
      )
      for value in channel
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'resolution': self.resolution,
      'cell_count': self.resolution[0] * self.resolution[1],
      'solver_status': self.result.status.value,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'target_lineage_verified': self.target_lineage_verified,
      'pressure_consumption_verified': self.pressure_consumption_verified,
      'geometry_injection_blocked': self.geometry_injection_blocked,
      'geometry_solver_owned_verified': self.geometry_solver_owned_verified,
      'independent_audit_verified': self.independent_audit_verified,
      'response_channels_finite': self.response_channels_finite,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'pressure_profile': (
        None
        if self.pressure_profile is None
        else self.pressure_profile.as_report()
      ),
      'response': None if self.response is None else self.response.as_report(),
      'result': self.result.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementMeasurement:
  """Independent evidence over the pressure-only resolution ladder."""

  status: MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
  cases: tuple[MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  resolution_order_verified: bool = False
  target_lineage_verified: bool = False
  pressure_consumption_verified: bool = False
  geometry_injection_blocked: bool = False
  geometry_solver_owned_verified: bool = False
  independent_audits_verified: bool = False
  response_channels_finite: bool = False
  local_coupled_field_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed pressure-free-boundary cases')
    ####
    resolutions = tuple(tuple(value) for value in self.resolutions)
    if resolutions != tuple(case.resolution for case in cases):
      raise ValueError('resolutions must match cases')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'resolutions', resolutions)
    for name in (
      'resolution_order_verified',
      'target_lineage_verified',
      'pressure_consumption_verified',
      'geometry_injection_blocked',
      'geometry_solver_owned_verified',
      'independent_audits_verified',
      'response_channels_finite',
      'local_coupled_field_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'pressure-free-boundary refinement cannot claim global or downstream '
        'closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'pressure-free-boundary refinement must retain its promotion block'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'pressure-free-boundary refinement must retain external validation'
      )
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
      .CONVERGED_RESEARCH_LADDER
      and len(self.cases) >= 2
      and self.resolution_order_verified
      and self.target_lineage_verified
      and self.pressure_consumption_verified
      and self.geometry_injection_blocked
      and self.geometry_solver_owned_verified
      and self.independent_audits_verified
      and self.response_channels_finite
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'resolutions': self.resolutions,
      'checks': {
        'resolution_order_verified': self.resolution_order_verified,
        'target_lineage_verified': self.target_lineage_verified,
        'pressure_consumption_verified': self.pressure_consumption_verified,
        'geometry_injection_blocked': self.geometry_injection_blocked,
        'geometry_solver_owned_verified': self.geometry_solver_owned_verified,
        'independent_audits_verified': self.independent_audits_verified,
        'response_channels_finite': self.response_channels_finite,
        'local_coupled_field_verified': self.local_coupled_field_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'external_validation_required': self.external_validation_required,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'cases': tuple(case.as_report() for case in self.cases),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun:
  """Fresh execution record for one pressure-only mesh ladder."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  target: MocPhysicalFieldEulerBoundaryPressureTarget
  requested_resolutions: tuple[tuple[int, int], ...]
  cases: tuple[MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase, ...]
  measurement: MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
      )
    ####
    requested = tuple(tuple(value) for value in self.requested_resolutions)
    cases = tuple(self.cases)
    if requested != tuple(case.resolution for case in cases):
      raise ValueError('requested_resolutions must match cases')
    ####
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact cases')
    ####
    if len(str(self.configuration_fingerprint)) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    if self.measurement.production_claim_allowed:
      raise ValueError(
        'pressure-free-boundary refinement cannot claim production validity'
      )
    ####
    object.__setattr__(self, 'requested_resolutions', requested)
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'configuration_fingerprint', str(self.configuration_fingerprint))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_REFINEMENT_RUN_OPERATOR_ID,
      'converged': self.converged,
      'requested_resolutions': self.requested_resolutions,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(
        self.closure
      ),
      'target': self.target.as_report(),
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def _pressure_profile_for_resolution(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  *,
  resolution: tuple[int, int],
  x_start_m: float,
  downstream_length_m: float,
) -> MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile:
  axial_count = resolution[0]
  x_nodes = tuple(
    float(x_start_m + downstream_length_m * index / axial_count)
    for index in range(axial_count + 1)
  )
  x_centers = tuple(
    0.5 * (first + second) for first, second in zip(x_nodes, x_nodes[1:])
  )
  pressures: list[float] = []
  for x_value in x_centers:
    pressure = target.pressure_at_x(x_value, position_tolerance_m=1.0e-8)
    if pressure is None:
      raise ValueError(
        'pressure target does not cover a coupled cell-center station; '
        'no extrapolation was attempted'
      )
    ####
    pressures.append(float(pressure))
  ####
  target_source = f'{target.source_id}:{target.composition_mode}'
  return MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile(
    source_closure_fingerprint=(
      moc_reflected_domain_global_physical_closure_fingerprint(closure)
    ),
    x_stations_m=x_centers,
    pressure_Pa=tuple(pressures),
    source=f'{_PRESSURE_PROFILE_SOURCE_PREFIX}{target_source}',
    coverage_verified=True,
  )
####


def _target_lineage_verified(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  profile: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None,
) -> bool:
  if profile is None:
    return False
  ####
  closure_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    closure
  )
  target_source = f'{target.source_id}:{target.composition_mode}'
  return bool(
    target.source_closure_fingerprint == closure_fingerprint
    and profile.source_closure_fingerprint == closure_fingerprint
    and profile.source == f'{_PRESSURE_PROFILE_SOURCE_PREFIX}{target_source}'
    and all(
      target.pressure_at_x(x_value, position_tolerance_m=1.0e-8)
      == pressure
      for x_value, pressure in zip(
        profile.x_stations_m,
        profile.pressure_Pa,
      )
    )
  )
####


def _pressure_consumption_verified(
  result: MocReflectedDomainGlobalCoupledDownstreamResult,
  profile: MocReflectedDomainGlobalCoupledDownstreamBoundaryPressureProfile | None,
) -> bool:
  field = result.coupled_field
  request = result.coupled_request
  audit = result.coupled_field_audit
  return bool(
    profile is not None
    and field is not None
    and request is not None
    and audit is not None
    and request.inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_PRESSURE_FREE_BOUNDARY
    and request.free_boundary_pressure_profile_Pa == profile.pressure_Pa
    and request.free_boundary_pressure_profile_x_stations_m
    == profile.x_stations_m
    and request.free_boundary_pressure_profile_source == profile.source
    and request.free_boundary_geometry_profile_y_m is None
    and field.free_boundary_pressure_profile_consumed
    and not field.free_boundary_geometry_profile_consumed
    and getattr(audit, 'pressure_profile_compatibility_verified', False)
    and getattr(audit, 'free_boundary_geometry_profile_verified', False)
  )
####


def _geometry_solver_owned_verified(
  result: MocReflectedDomainGlobalCoupledDownstreamResult,
) -> bool:
  field = result.coupled_field
  request = result.coupled_request
  if field is None or request is None:
    return False
  ####
  ordinates = tuple(point[1] for point in field.free_boundary_points_m)
  return bool(
    request.free_boundary_geometry_profile_y_m is None
    and not field.free_boundary_geometry_profile_consumed
    and len(ordinates) >= 2
    and any(
      abs(second - first) > 1.0e-10
      for first, second in zip(ordinates, ordinates[1:])
    )
  )
####


def _measurement(
  cases: tuple[
    MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase, ...
  ],
) -> MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementMeasurement:
  resolutions = tuple(case.resolution for case in cases)
  resolution_order_verified = bool(
    len(resolutions) >= 2
    and all(
      right[0] > left[0] and right[1] > left[1]
      for left, right in zip(resolutions, resolutions[1:])
    )
  )
  target_lineage_verified = bool(
    cases and all(case.target_lineage_verified for case in cases)
  )
  pressure_consumption_verified = bool(
    cases and all(case.pressure_consumption_verified for case in cases)
  )
  geometry_injection_blocked = bool(
    cases and all(case.geometry_injection_blocked for case in cases)
  )
  geometry_solver_owned_verified = bool(
    cases and all(case.geometry_solver_owned_verified for case in cases)
  )
  independent_audits_verified = bool(
    cases and all(case.independent_audit_verified for case in cases)
  )
  response_channels_finite = bool(
    cases and all(case.response_channels_finite for case in cases)
  )
  local_coupled_field_verified = bool(
    cases and all(case.local_coupled_field_verified for case in cases)
  )
  fidelity_isolation_verified = bool(
    cases and all(case.fidelity_isolation_verified for case in cases)
  )
  all_local = bool(
    resolution_order_verified
    and target_lineage_verified
    and pressure_consumption_verified
    and geometry_injection_blocked
    and geometry_solver_owned_verified
    and independent_audits_verified
    and response_channels_finite
    and local_coupled_field_verified
    and fidelity_isolation_verified
  )
  status = (
    MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
    .CONVERGED_RESEARCH_LADDER
    if all_local
    else MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
    .RESOLUTION_FAILURE
  )
  return MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementMeasurement(
    status=status,
    cases=cases,
    resolutions=resolutions,
    resolution_order_verified=resolution_order_verified,
    target_lineage_verified=target_lineage_verified,
    pressure_consumption_verified=pressure_consumption_verified,
    geometry_injection_blocked=geometry_injection_blocked,
    geometry_solver_owned_verified=geometry_solver_owned_verified,
    independent_audits_verified=independent_audits_verified,
    response_channels_finite=response_channels_finite,
    local_coupled_field_verified=local_coupled_field_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'pressure-only solver-owned free-boundary refinement passed local '
      'mesh and provenance checks; global feedback and promotion remain '
      'blocked'
      if all_local
      else 'pressure-only free-boundary refinement did not pass every local '
      'mesh, audit, or provenance check'
    ),
  )
####


def run_reflected_domain_global_coupled_pressure_free_boundary_refinement(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  reference_total_temperature_K: float,
  resolutions: Sequence[tuple[int, int]],
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: Any | None = None,
  physical_field_shock_front_condition: Any | None = None,
) -> MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun:
  """Freshly solve a pressure-only free-boundary mesh ladder."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    raise ValueError(
      'pressure-free-boundary refinement requires a locally verified global '
      'physical closure'
    )
  ####
  if not isinstance(target, MocPhysicalFieldEulerBoundaryPressureTarget):
    raise TypeError(
      'target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
    )
  ####
  closure_fingerprint = moc_reflected_domain_global_physical_closure_fingerprint(
    closure
  )
  if target.source_closure_fingerprint != closure_fingerprint:
    raise ValueError(
      'pressure-free-boundary target must retain the exact source closure '
      'fingerprint; cross-case target reuse is not allowed'
    )
  ####
  requested_resolutions = tuple(tuple(value) for value in resolutions)
  if len(requested_resolutions) < 2:
    raise ValueError('resolutions must contain at least two mesh cases')
  ####
  if any(
    len(resolution) != 2
    or any(
      isinstance(value, bool) or not isinstance(value, int)
      for value in resolution
    )
    or resolution[0] < 4
    or resolution[1] < 3
    for resolution in requested_resolutions
  ):
    raise ValueError(
      'resolutions must contain (axial, transverse) integer pairs with '
      'axial >= 4 and transverse >= 3'
    )
  ####
  if any(
    right[0] <= left[0] or right[1] <= left[1]
    for left, right in zip(requested_resolutions, requested_resolutions[1:])
  ):
    raise ValueError('resolutions must strictly increase in both dimensions')
  ####
  if physical_field_continuation_profile is None and physical_field_shock_front_condition is None:
    handoff = build_reflected_domain_global_solver_owned_physical_field_handoff(
      closure
    )
    physical_field_continuation_profile = handoff.continuation_profile
    physical_field_shock_front_condition = handoff.shock_front_condition
  elif physical_field_continuation_profile is None or physical_field_shock_front_condition is None:
    raise ValueError(
      'pressure-free-boundary refinement requires both physical-field '
      'continuation and shock-front condition when supplied explicitly'
    )
  ####
  coupled_inlet_profile = getattr(
    physical_field_shock_front_condition,
    'coupled_inlet_profile',
    None,
  )
  if coupled_inlet_profile is None:
    raise ValueError(
      'pressure-free-boundary refinement retained no coupled inlet profile'
    )
  ####
  x_start_m = float(coupled_inlet_profile.cross_section_x_m)
  configuration = {
    'closure_fingerprint': closure_fingerprint,
    'target_source_id': target.source_id,
    'target_source_closure_fingerprint': target.source_closure_fingerprint,
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'inlet_boundary_mode': (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_PRESSURE_FREE_BOUNDARY.value
    ),
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'resolutions': requested_resolutions,
    'profile_policy': 'pressure-centers-only-no-geometry-profile-v1',
    'x_start_m': x_start_m,
  }
  configuration_fingerprint = sha256(
    json.dumps(
      configuration,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  cases: list[
    MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase
  ] = []
  fresh_solver_invocations: list[bool] = []
  for resolution in requested_resolutions:
    profile = _pressure_profile_for_resolution(
      closure,
      target,
      resolution=resolution,
      x_start_m=x_start_m,
      downstream_length_m=downstream_length_m,
    )
    result = solve_reflected_domain_global_coupled_downstream(
      closure,
      reference_total_temperature_K=reference_total_temperature_K,
      ambient_pressure_Pa=ambient_pressure_Pa,
      downstream_length_m=downstream_length_m,
      initial_outlet_height_m=initial_outlet_height_m,
      control_section_x_offset_m=control_section_x_offset_m,
      control_section_height_m=control_section_height_m,
      control_section_sample_count=control_section_sample_count,
      axial_station_count=resolution[0],
      axial_cell_count=resolution[0],
      transverse_cell_count=resolution[1],
      max_pseudo_iterations=max_pseudo_iterations,
      max_shape_iterations=max_shape_iterations,
      inlet_boundary_mode=(
        MocReflectedDomainCoupledEulerInletBoundaryMode
        .SOLVER_OWNED_PHYSICAL_FIELD_PRESSURE_FREE_BOUNDARY
      ),
      outlet_static_pressure_Pa=outlet_static_pressure_Pa,
      physical_field_continuation_profile=physical_field_continuation_profile,
      physical_field_shock_front_condition=physical_field_shock_front_condition,
      boundary_pressure_profile=profile,
      boundary_geometry_profile=None,
    )
    fresh_solver_invocations.append(result.coupled_field is not None)
    response = None
    if result.coupled_field is not None:
      try:
        response = measure_reflected_domain_global_coupled_downstream_boundary_response(
          closure,
          result.coupled_field,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        response = None
      ####
    ####
    independent_audit_verified = False
    if result.coupled_field is not None:
      try:
        audit = measure_reflected_domain_coupled_euler_free_boundary(
          result.coupled_field
        )
        independent_audit_verified = bool(
          audit.converged
          and audit.local_consistency_verified
          and audit.candidate is result.coupled_field
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        independent_audit_verified = False
      ####
    ####
    cases.append(
      MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementCase(
        resolution=resolution,
        result=result,
        pressure_profile=profile,
        response=response,
        target_lineage_verified=_target_lineage_verified(
          closure,
          target,
          profile,
        ),
        pressure_consumption_verified=_pressure_consumption_verified(
          result,
          profile,
        ),
        geometry_injection_blocked=bool(
          result.coupled_request is not None
          and result.coupled_request.free_boundary_geometry_profile_y_m is None
          and result.boundary_geometry_profile is None
        ),
        geometry_solver_owned_verified=_geometry_solver_owned_verified(result),
        independent_audit_verified=independent_audit_verified,
      )
    )
  ####
  retained_cases = tuple(cases)
  measurement = _measurement(retained_cases)
  fidelity_isolation_verified = bool(
    retained_cases and all(case.fidelity_isolation_verified for case in retained_cases)
  )
  return MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun(
    closure=closure,
    target=target,
    requested_resolutions=requested_resolutions,
    cases=retained_cases,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(
      len(retained_cases) == len(requested_resolutions)
      and all(fresh_solver_invocations)
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh pressure-only solver-owned free-boundary refinement completed; '
      'global feedback, canonical closure, accepted cell length, and external '
      'validation remain separate gates'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase:
  """One named closure and its pressure-only refinement ladder."""

  case_id: str
  regime: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  target: MocPhysicalFieldEulerBoundaryPressureTarget
  resolutions: tuple[tuple[int, int], ...]

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    regime = str(self.regime)
    if not case_id or not regime:
      raise ValueError('case_id and regime must be non-empty')
    ####
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
      )
    ####
    resolutions = tuple(tuple(value) for value in self.resolutions)
    if len(resolutions) < 2:
      raise ValueError('resolutions must contain at least two mesh cases')
    ####
    if any(
      len(resolution) != 2
      or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in resolution
      )
      or resolution[0] < 4
      or resolution[1] < 3
      for resolution in resolutions
    ):
      raise ValueError(
        'resolutions must contain (axial, transverse) integer pairs with '
        'axial >= 4 and transverse >= 3'
      )
    ####
    if any(
      right[0] <= left[0] or right[1] <= left[1]
      for left, right in zip(resolutions, resolutions[1:])
    ):
      raise ValueError('resolutions must strictly increase in both dimensions')
    ####
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'regime', regime)
    object.__setattr__(self, 'resolutions', resolutions)
  ####

  @property
  def closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    )
  ####

  @property
  def resolution_ladder_verified(self) -> bool:
    return bool(
      len(self.resolutions) >= 2
      and all(
        right[0] > left[0] and right[1] > left[1]
        for left, right in zip(self.resolutions, self.resolutions[1:])
      )
    )
  ####

  @property
  def target_binding_verified(self) -> bool:
    return bool(
      self.target.source_closure_fingerprint == self.closure_fingerprint
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'regime': self.regime,
      'closure_fingerprint': self.closure_fingerprint,
      'resolutions': self.resolutions,
      'resolution_ladder_verified': self.resolution_ladder_verified,
      'target_binding_verified': self.target_binding_verified,
      'target': self.target.as_report(),
      'closure_converged': self.closure.converged,
      'physical_closure_verified': self.closure.physical_closure_verified,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseMeasurement:
  """Independent aggregate evidence for disjoint pressure-only cases."""

  status: MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
  cases: tuple[MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase, ...] = ()
  runs: tuple[MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun, ...] = ()
  case_ids: tuple[str, ...] = ()
  closure_fingerprints: tuple[str, ...] = ()
  case_ids_verified: bool = False
  closure_bindings_verified: bool = False
  distinct_closure_fingerprints_verified: bool = False
  resolution_ladders_verified: bool = False
  target_bindings_verified: bool = False
  case_runs_verified: bool = False
  local_coupled_field_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_CROSS_CASE_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    runs = tuple(self.runs)
    if len(cases) != len(runs):
      raise ValueError('cases and runs must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed cross-case inputs')
    ####
    if any(
      not isinstance(
        run,
        MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun,
      )
      for run in runs
    ):
      raise TypeError('runs must contain typed pressure-free-boundary runs')
    ####
    derived_case_ids = tuple(case.case_id for case in cases)
    derived_fingerprints = tuple(case.closure_fingerprint for case in cases)
    if self.case_ids and tuple(self.case_ids) != derived_case_ids:
      raise ValueError('case_ids must match cases')
    ####
    if (
      self.closure_fingerprints
      and tuple(self.closure_fingerprints) != derived_fingerprints
    ):
      raise ValueError('closure_fingerprints must match cases')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'runs', runs)
    object.__setattr__(self, 'case_ids', derived_case_ids)
    object.__setattr__(self, 'closure_fingerprints', derived_fingerprints)
    for name in (
      'case_ids_verified',
      'closure_bindings_verified',
      'distinct_closure_fingerprints_verified',
      'resolution_ladders_verified',
      'target_bindings_verified',
      'case_runs_verified',
      'local_coupled_field_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'cross-case pressure-free-boundary refinement cannot claim closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'cross-case pressure-free-boundary refinement must retain its '
        'promotion block'
      )
    ####
    if not self.external_validation_required:
      raise ValueError(
        'cross-case pressure-free-boundary refinement must retain external '
        'validation'
      )
    ####
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      and len(self.cases) >= 2
      and self.case_ids_verified
      and self.closure_bindings_verified
      and self.distinct_closure_fingerprints_verified
      and self.resolution_ladders_verified
      and self.target_bindings_verified
      and self.case_runs_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'case_ids': self.case_ids,
      'closure_fingerprints': self.closure_fingerprints,
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'closure_bindings_verified': self.closure_bindings_verified,
        'distinct_closure_fingerprints_verified': (
          self.distinct_closure_fingerprints_verified
        ),
        'resolution_ladders_verified': self.resolution_ladders_verified,
        'target_bindings_verified': self.target_bindings_verified,
        'case_runs_verified': self.case_runs_verified,
        'local_coupled_field_verified': self.local_coupled_field_verified,
        'fidelity_isolation_verified': self.fidelity_isolation_verified,
        'external_validation_required': self.external_validation_required,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'external_validation_verified': False,
      'external_validation_required': self.external_validation_required,
      'cases': tuple(case.as_report() for case in self.cases),
      'runs': tuple(run.as_report() for run in self.runs),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseRun:
  """Fresh aggregate execution record for disjoint closure ladders."""

  cases: tuple[MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase, ...]
  runs: tuple[MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementRun, ...]
  measurement: MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseMeasurement
  configuration: dict[str, Any]
  configuration_fingerprint: str
  fresh_solver_invocation_verified: bool = False
  fidelity_isolation_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    cases = tuple(self.cases)
    runs = tuple(self.runs)
    if len(cases) != len(runs):
      raise ValueError('cases and runs must have equal lengths')
    ####
    if self.measurement.cases != cases or self.measurement.runs != runs:
      raise ValueError('measurement must retain the exact cross-case values')
    ####
    if len(str(self.configuration_fingerprint)) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'runs', runs)
    object.__setattr__(self, 'configuration', dict(self.configuration))
    object.__setattr__(self, 'configuration_fingerprint', str(self.configuration_fingerprint))
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.measurement.converged
      and self.fresh_solver_invocation_verified
      and self.fidelity_isolation_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': (
        MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_PRESSURE_FREE_BOUNDARY_CROSS_CASE_REFINEMENT_RUN_OPERATOR_ID
      ),
      'converged': self.converged,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'runs': tuple(run.as_report() for run in self.runs),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def run_reflected_domain_global_coupled_pressure_free_boundary_cross_case_refinement(
  cases: Sequence[MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase],
  *,
  reference_total_temperature_K: float,
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float = 0.05,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  outlet_static_pressure_Pa: float | None = None,
) -> MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseRun:
  """Freshly execute pressure-only refinement on disjoint closures."""

  retained_cases = tuple(cases)
  if len(retained_cases) < 2:
    raise ValueError('cases must contain at least two named closures')
  ####
  if any(
    not isinstance(
      case,
      MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCase,
    )
    for case in retained_cases
  ):
    raise TypeError('cases must contain typed pressure-free-boundary cases')
  ####
  case_ids = tuple(case.case_id for case in retained_cases)
  closure_fingerprints = tuple(
    case.closure_fingerprint for case in retained_cases
  )
  if len(set(case_ids)) != len(case_ids):
    raise ValueError('case_id values must be unique')
  ####
  if len(set(closure_fingerprints)) != len(closure_fingerprints):
    raise ValueError(
      'cross-case refinement requires distinct source closure fingerprints'
    )
  ####
  if any(not case.target_binding_verified for case in retained_cases):
    raise ValueError(
      'every pressure-free-boundary target must retain its case closure '
      'fingerprint'
    )
  ####
  run_values = tuple(
    run_reflected_domain_global_coupled_pressure_free_boundary_refinement(
      case.closure,
      target=case.target,
      reference_total_temperature_K=reference_total_temperature_K,
      resolutions=case.resolutions,
      ambient_pressure_Pa=ambient_pressure_Pa,
      downstream_length_m=downstream_length_m,
      initial_outlet_height_m=initial_outlet_height_m,
      control_section_x_offset_m=control_section_x_offset_m,
      control_section_height_m=control_section_height_m,
      control_section_sample_count=control_section_sample_count,
      max_pseudo_iterations=max_pseudo_iterations,
      max_shape_iterations=max_shape_iterations,
      outlet_static_pressure_Pa=outlet_static_pressure_Pa,
    )
    for case in retained_cases
  )
  case_ids_verified = len(set(case_ids)) == len(case_ids)
  closure_bindings_verified = all(
    run.closure is case.closure
    and moc_reflected_domain_global_physical_closure_fingerprint(run.closure)
    == case.closure_fingerprint
    for case, run in zip(retained_cases, run_values)
  )
  distinct_closure_fingerprints_verified = (
    len(set(closure_fingerprints)) == len(closure_fingerprints)
  )
  resolution_ladders_verified = all(
    case.resolution_ladder_verified for case in retained_cases
  )
  target_bindings_verified = all(
    case.target_binding_verified and run.measurement.target_lineage_verified
    for case, run in zip(retained_cases, run_values)
  )
  case_runs_verified = all(run.converged for run in run_values)
  local_coupled_field_verified = all(
    run.measurement.local_coupled_field_verified for run in run_values
  )
  fidelity_isolation_verified = all(
    run.measurement.fidelity_isolation_verified for run in run_values
  )
  all_local = bool(
    case_ids_verified
    and closure_bindings_verified
    and distinct_closure_fingerprints_verified
    and resolution_ladders_verified
    and target_bindings_verified
    and case_runs_verified
    and local_coupled_field_verified
    and fidelity_isolation_verified
  )
  measurement = MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseMeasurement(
    status=(
      MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
      .CONVERGED_RESEARCH_CROSS_CASE
      if all_local
      else MocReflectedDomainGlobalCoupledPressureFreeBoundaryRefinementStatus
      .CROSS_CASE_FAILURE
    ),
    cases=retained_cases,
    runs=run_values,
    case_ids_verified=case_ids_verified,
    closure_bindings_verified=closure_bindings_verified,
    distinct_closure_fingerprints_verified=(
      distinct_closure_fingerprints_verified
    ),
    resolution_ladders_verified=resolution_ladders_verified,
    target_bindings_verified=target_bindings_verified,
    case_runs_verified=case_runs_verified,
    local_coupled_field_verified=local_coupled_field_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'disjoint pressure-only closure ladders passed local refinement and '
      'lineage checks; upstream global feedback and promotion remain blocked'
      if all_local
      else 'disjoint pressure-only refinement did not pass every case or '
      'lineage check'
    ),
  )
  configuration = {
    'case_ids': case_ids,
    'closure_fingerprints': closure_fingerprints,
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'inlet_boundary_mode': (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_PRESSURE_FREE_BOUNDARY.value
    ),
  }
  configuration_fingerprint = sha256(
    json.dumps(
      configuration,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  return MocReflectedDomainGlobalCoupledPressureFreeBoundaryCrossCaseRun(
    cases=retained_cases,
    runs=run_values,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=all(
      run.fresh_solver_invocation_verified for run in run_values
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=measurement.message,
  )
####
