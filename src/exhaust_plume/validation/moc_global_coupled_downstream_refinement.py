"""Resolution evidence for the global/coupled downstream response seam.

The coupled-Euler refinement ladder already measures local conservative-field
residuals.  This operator adds the missing upstream/downstream evidence: every
declared mesh is solved from the same exact global closure, the retained
boundary response is independently remeasured, and the overlap channels are
reported without turning a local mesh result into global feedback or a
production shock-cell claim.
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
  MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
  MocReflectedDomainGlobalCoupledDownstreamResult,
  MocReflectedDomainGlobalCoupledDownstreamStatus,
  measure_reflected_domain_global_coupled_downstream_boundary_response,
  solve_reflected_domain_global_coupled_downstream,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementStatus',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementCase',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement',
  'measure_reflected_domain_global_coupled_downstream_refinement',
  'MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_RUN_OPERATOR_ID',
  'MocReflectedDomainGlobalCoupledDownstreamRefinementRun',
  'run_reflected_domain_global_coupled_downstream_refinement',
)


MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-refinement'
)
MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_RUN_OPERATOR_ID = (
  'op.moc.reflected-domain.global-coupled-downstream-refinement-run'
)


class MocReflectedDomainGlobalCoupledDownstreamRefinementStatus(str, Enum):
  """Outcome of an independently measured global/coupled response ladder."""

  CONVERGED_RESEARCH_LADDER = (
    'converged-research-global-coupled-downstream-ladder'
  )
  INVALID_INPUT = 'invalid_input'
  RESOLUTION_FAILURE = 'global-coupled-downstream-refinement-resolution-failure'
  CASE_FAILURE = 'global-coupled-downstream-refinement-case-failure'
  RESPONSE_FAILURE = 'global-coupled-downstream-refinement-response-failure'
  FIDELITY_FAILURE = 'global-coupled-downstream-refinement-fidelity-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamRefinementCase:
  """One fresh coupled solve and an independent boundary-response measure."""

  resolution: tuple[int, int]
  result: MocReflectedDomainGlobalCoupledDownstreamResult
  solver_response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  response: MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse | None
  response_lineage_verified: bool = False

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
        'axial resolution must be at least four and transverse resolution '
        'must be at least three'
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
    for name in ('solver_response', 'response'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse,
      ):
        raise TypeError(
          f'{name} must be a '
          'MocReflectedDomainGlobalCoupledDownstreamBoundaryResponse or None'
        )
      ####
    ####
    if not isinstance(self.response_lineage_verified, bool):
      raise TypeError('response_lineage_verified must be a bool')
    ####
    object.__setattr__(self, 'resolution', resolution)
  ####

  @property
  def local_coupled_field_verified(self) -> bool:
    return bool(self.result.local_coupled_field_verified)
  ####

  @property
  def response_coverage_verified(self) -> bool:
    return bool(
      self.response is not None and self.response.overlap_coverage_verified
    )
  ####

  @property
  def response_residuals_verified(self) -> bool:
    return bool(self.response is not None and self.response.residuals_verified)
  ####

  @property
  def fidelity_isolation_verified(self) -> bool:
    return bool(
      not self.result.global_coupling_verified
      and not self.result.downstream_boundary_closure_verified
      and self.result.chain_promotion_blocked
      and not self.result.production_claim_allowed
      and (self.response is None or not self.response.production_claim_allowed)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'resolution': self.resolution,
      'cell_count': self.resolution[0] * self.resolution[1],
      'solver_status': self.result.status.value,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'response_coverage_verified': self.response_coverage_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'solver_response': (
        None if self.solver_response is None else self.solver_response.as_report()
      ),
      'response': None if self.response is None else self.response.as_report(),
      'result': self.result.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement:
  """Independent response-ladder evidence below the physical gate."""

  status: MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
  cases: tuple[MocReflectedDomainGlobalCoupledDownstreamRefinementCase, ...] = ()
  resolutions: tuple[tuple[int, int], ...] = ()
  cell_counts: tuple[int, ...] = ()
  maximum_coordinate_residuals_m: tuple[float, ...] = ()
  maximum_tangent_residuals_rad: tuple[float, ...] = ()
  maximum_pressure_residuals_Pa: tuple[float, ...] = ()
  maximum_normal_velocity_residuals_m_s: tuple[float, ...] = ()
  resolution_order_verified: bool = False
  mesh_growth_verified: bool = False
  case_audits_verified: bool = False
  response_lineage_verified: bool = False
  response_channels_finite: bool = False
  overlap_coverage_verified: bool = False
  overlap_residuals_verified: bool = False
  local_coupled_field_verified: bool = False
  fidelity_isolation_verified: bool = False
  global_coupling_verified: bool = False
  downstream_boundary_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  operator_id: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_OPERATOR_ID
  )
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalCoupledDownstreamRefinementStatus'
      )
    ####
    cases = tuple(self.cases)
    if any(
      not isinstance(
        case,
        MocReflectedDomainGlobalCoupledDownstreamRefinementCase,
      )
      for case in cases
    ):
      raise TypeError(
        'cases must contain typed global/coupled downstream refinement cases'
      )
    ####
    object.__setattr__(self, 'cases', cases)
    resolutions = tuple(tuple(value) for value in self.resolutions)
    if len(resolutions) != len(cases):
      raise ValueError('resolutions must match cases')
    ####
    object.__setattr__(self, 'resolutions', resolutions)
    cell_counts = tuple(int(value) for value in self.cell_counts)
    if len(cell_counts) != len(cases):
      raise ValueError('cell_counts must match cases')
    ####
    object.__setattr__(self, 'cell_counts', cell_counts)
    for name in (
      'maximum_coordinate_residuals_m',
      'maximum_tangent_residuals_rad',
      'maximum_pressure_residuals_Pa',
      'maximum_normal_velocity_residuals_m_s',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(cases) or any(
        not isfinite(value) or value < 0.0 for value in values
      ):
        raise ValueError(f'{name} must contain one finite nonnegative value per case')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'resolution_order_verified',
      'mesh_growth_verified',
      'case_audits_verified',
      'response_lineage_verified',
      'response_channels_finite',
      'overlap_coverage_verified',
      'overlap_residuals_verified',
      'local_coupled_field_verified',
      'fidelity_isolation_verified',
      'global_coupling_verified',
      'downstream_boundary_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or self.downstream_boundary_closure_verified:
      raise ValueError(
        'research response refinement cannot claim global or downstream closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'research response refinement must retain its promotion block'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
      .CONVERGED_RESEARCH_LADDER
      and self.resolution_order_verified
      and self.mesh_growth_verified
      and self.case_audits_verified
      and self.response_lineage_verified
      and self.response_channels_finite
      and self.overlap_coverage_verified
      and self.overlap_residuals_verified
      and self.local_coupled_field_verified
      and self.fidelity_isolation_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'resolutions': self.resolutions,
      'cell_counts': self.cell_counts,
      'maximum_coordinate_residuals_m': self.maximum_coordinate_residuals_m,
      'maximum_tangent_residuals_rad': self.maximum_tangent_residuals_rad,
      'maximum_pressure_residuals_Pa': self.maximum_pressure_residuals_Pa,
      'maximum_normal_velocity_residuals_m_s': (
        self.maximum_normal_velocity_residuals_m_s
      ),
      'resolution_order_verified': self.resolution_order_verified,
      'mesh_growth_verified': self.mesh_growth_verified,
      'case_audits_verified': self.case_audits_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'response_channels_finite': self.response_channels_finite,
      'overlap_coverage_verified': self.overlap_coverage_verified,
      'overlap_residuals_verified': self.overlap_residuals_verified,
      'local_coupled_field_verified': self.local_coupled_field_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'cases': tuple(case.as_report() for case in self.cases),
      'message': self.message,
    }
  ####
####


def _measurement_status(
  *,
  resolution_order_verified: bool,
  mesh_growth_verified: bool,
  case_audits_verified: bool,
  response_lineage_verified: bool,
  response_channels_finite: bool,
  overlap_coverage_verified: bool,
  overlap_residuals_verified: bool,
  fidelity_isolation_verified: bool,
) -> tuple[
  MocReflectedDomainGlobalCoupledDownstreamRefinementStatus,
  str,
]:
  if not resolution_order_verified or not mesh_growth_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.RESOLUTION_FAILURE,
      'declared coupled-Euler resolutions are not strictly ordered with mesh growth',
    )
  ####
  if not fidelity_isolation_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.FIDELITY_FAILURE,
      'a response-ladder case changed the global or production claim ceiling',
    )
  ####
  if not case_audits_verified:
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.CASE_FAILURE,
      'at least one fresh coupled-Euler case did not pass its local audit',
    )
  ####
  if not (
    response_lineage_verified
    and response_channels_finite
    and overlap_coverage_verified
    and overlap_residuals_verified
  ):
    return (
      MocReflectedDomainGlobalCoupledDownstreamRefinementStatus.RESPONSE_FAILURE,
      'the coupled-Euler ladder is locally measured, but global-boundary '
      'overlap evidence is incomplete or exceeds its declared tolerances',
    )
  ####
  return (
    MocReflectedDomainGlobalCoupledDownstreamRefinementStatus
    .CONVERGED_RESEARCH_LADDER,
    'fresh global/coupled downstream response ladder passed its local '
    'overlap checks; global feedback and production promotion remain blocked',
  )
####


def measure_reflected_domain_global_coupled_downstream_refinement(
  cases: Sequence[MocReflectedDomainGlobalCoupledDownstreamRefinementCase],
) -> MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement:
  """Independently measure response evidence across fresh mesh cases."""

  retained_cases = tuple(cases)
  if not retained_cases:
    raise ValueError('cases must not be empty')
  ####
  resolutions = tuple(case.resolution for case in retained_cases)
  cell_counts = tuple(
    resolution[0] * resolution[1] for resolution in resolutions
  )
  resolution_order_verified = all(
    second[0] > first[0] and second[1] > first[1]
    for first, second in zip(resolutions, resolutions[1:])
  )
  mesh_growth_verified = all(
    second > first for first, second in zip(cell_counts, cell_counts[1:])
  )
  responses = tuple(case.response for case in retained_cases)
  response_channels_finite = bool(
    responses
    and all(
      response is not None
      and all(
        isfinite(value)
        for channel in (
          response.coordinate_residuals_m,
          response.tangent_residuals_rad,
          response.pressure_residuals_Pa,
          response.normal_velocity_residuals_m_s,
        )
        for value in channel
      )
      for response in responses
    )
  )
  maximum_coordinate = tuple(
    0.0 if response is None else response.maximum_coordinate_residual_m
    for response in responses
  )
  maximum_tangent = tuple(
    0.0 if response is None else response.maximum_tangent_residual_rad
    for response in responses
  )
  maximum_pressure = tuple(
    0.0 if response is None else response.maximum_pressure_residual_Pa
    for response in responses
  )
  maximum_normal_velocity = tuple(
    0.0 if response is None else response.maximum_normal_velocity_residual_m_s
    for response in responses
  )
  case_audits_verified = all(
    case.local_coupled_field_verified and case.response is not None
    for case in retained_cases
  )
  response_lineage_verified = all(
    case.response_lineage_verified for case in retained_cases
  )
  overlap_coverage_verified = all(
    case.response_coverage_verified for case in retained_cases
  )
  overlap_residuals_verified = all(
    case.response_residuals_verified for case in retained_cases
  )
  fidelity_isolation_verified = all(
    case.fidelity_isolation_verified for case in retained_cases
  )
  status, message = _measurement_status(
    resolution_order_verified=resolution_order_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    overlap_coverage_verified=overlap_coverage_verified,
    overlap_residuals_verified=overlap_residuals_verified,
    fidelity_isolation_verified=fidelity_isolation_verified,
  )
  return MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement(
    status=status,
    cases=retained_cases,
    resolutions=resolutions,
    cell_counts=cell_counts,
    maximum_coordinate_residuals_m=maximum_coordinate,
    maximum_tangent_residuals_rad=maximum_tangent,
    maximum_pressure_residuals_Pa=maximum_pressure,
    maximum_normal_velocity_residuals_m_s=maximum_normal_velocity,
    resolution_order_verified=resolution_order_verified,
    mesh_growth_verified=mesh_growth_verified,
    case_audits_verified=case_audits_verified,
    response_lineage_verified=response_lineage_verified,
    response_channels_finite=response_channels_finite,
    overlap_coverage_verified=overlap_coverage_verified,
    overlap_residuals_verified=overlap_residuals_verified,
    local_coupled_field_verified=all(
      case.local_coupled_field_verified for case in retained_cases
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalCoupledDownstreamRefinementRun:
  """Fresh execution record for one exact global closure and mesh ladder."""

  closure: MocReflectedDomainGlobalPhysicalClosureResult
  requested_resolutions: tuple[tuple[int, int], ...]
  cases: tuple[MocReflectedDomainGlobalCoupledDownstreamRefinementCase, ...]
  measurement: MocReflectedDomainGlobalCoupledDownstreamRefinementMeasurement
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
    requested = tuple(tuple(value) for value in self.requested_resolutions)
    cases = tuple(self.cases)
    if requested != tuple(case.resolution for case in cases):
      raise ValueError('requested_resolutions must match case resolutions')
    ####
    if self.measurement.cases != cases:
      raise ValueError('measurement must retain the exact cases')
    ####
    if len(self.configuration_fingerprint) != 64:
      raise ValueError('configuration_fingerprint must be a SHA-256 digest')
    ####
    if not isinstance(self.fresh_solver_invocation_verified, bool):
      raise TypeError('fresh_solver_invocation_verified must be a bool')
    ####
    if not isinstance(self.fidelity_isolation_verified, bool):
      raise TypeError('fidelity_isolation_verified must be a bool')
    ####
    if self.measurement.production_claim_allowed:
      raise ValueError('response refinement cannot claim production validity')
    ####
    object.__setattr__(self, 'requested_resolutions', requested)
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'configuration', dict(self.configuration))
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
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_COUPLED_DOWNSTREAM_REFINEMENT_RUN_OPERATOR_ID,
      'converged': self.converged,
      'requested_resolutions': self.requested_resolutions,
      'fresh_solver_invocation_verified': self.fresh_solver_invocation_verified,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'production_claim_allowed': self.production_claim_allowed,
      'configuration': self.configuration,
      'configuration_fingerprint': self.configuration_fingerprint,
      'cases': tuple(case.as_report() for case in self.cases),
      'measurement': self.measurement.as_report(),
      'message': self.message,
    }
  ####
####


def _failed_result(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  message: str,
) -> MocReflectedDomainGlobalCoupledDownstreamResult:
  return MocReflectedDomainGlobalCoupledDownstreamResult(
    status=MocReflectedDomainGlobalCoupledDownstreamStatus.COUPLED_SOLVER_FAILURE,
    closure=closure,
    mixed_regime_request=None,
    coupled_request=None,
    coupled_field=None,
    coupled_field_audit=None,
    message=message,
  )
####


def run_reflected_domain_global_coupled_downstream_refinement(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
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
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  outlet_static_pressure_Pa: float | None = None,
  physical_field_continuation_profile: Any | None = None,
  physical_field_shock_front_condition: Any | None = None,
) -> MocReflectedDomainGlobalCoupledDownstreamRefinementRun:
  """Freshly solve and independently measure each declared mesh resolution."""

  if not isinstance(closure, MocReflectedDomainGlobalPhysicalClosureResult):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  requested_resolutions = tuple(tuple(value) for value in resolutions)
  if not requested_resolutions:
    raise ValueError('resolutions must not be empty')
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
    second[0] <= first[0] or second[1] <= first[1]
    for first, second in zip(requested_resolutions, requested_resolutions[1:])
  ):
    raise ValueError('resolutions must strictly increase in both dimensions')
  ####
  configuration = {
    'closure_fingerprint': closure.as_report()['closure_fingerprint'],
    'reference_total_temperature_K': float(reference_total_temperature_K),
    'ambient_pressure_Pa': ambient_pressure_Pa,
    'downstream_length_m': float(downstream_length_m),
    'initial_outlet_height_m': float(initial_outlet_height_m),
    'control_section_x_offset_m': float(control_section_x_offset_m),
    'control_section_height_m': float(control_section_height_m),
    'control_section_sample_count': int(control_section_sample_count),
    'max_pseudo_iterations': int(max_pseudo_iterations),
    'max_shape_iterations': int(max_shape_iterations),
    'inlet_boundary_mode': inlet_boundary_mode.value,
    'outlet_static_pressure_Pa': outlet_static_pressure_Pa,
    'resolutions': requested_resolutions,
  }
  configuration_fingerprint = sha256(
    json.dumps(
      configuration,
      sort_keys=True,
      separators=(',', ':'),
      default=str,
    ).encode('utf-8')
  ).hexdigest()
  cases: list[MocReflectedDomainGlobalCoupledDownstreamRefinementCase] = []
  for resolution in requested_resolutions:
    try:
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
        inlet_boundary_mode=inlet_boundary_mode,
        outlet_static_pressure_Pa=outlet_static_pressure_Pa,
        physical_field_continuation_profile=physical_field_continuation_profile,
        physical_field_shock_front_condition=physical_field_shock_front_condition,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      result = _failed_result(
        closure,
        f'fresh global/coupled downstream solve raised: {error}',
      )
    ####
    solver_response = result.downstream_boundary_response
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
    response_lineage_verified = bool(
      solver_response is not None
      and response is not None
      and solver_response.as_report() == response.as_report()
    )
    cases.append(
      MocReflectedDomainGlobalCoupledDownstreamRefinementCase(
        resolution=resolution,
        result=result,
        solver_response=solver_response,
        response=response,
        response_lineage_verified=response_lineage_verified,
      )
    )
  ####
  retained_cases = tuple(cases)
  measurement = measure_reflected_domain_global_coupled_downstream_refinement(
    retained_cases
  )
  fidelity_isolation_verified = all(
    case.fidelity_isolation_verified for case in retained_cases
  )
  return MocReflectedDomainGlobalCoupledDownstreamRefinementRun(
    closure=closure,
    requested_resolutions=requested_resolutions,
    cases=retained_cases,
    measurement=measurement,
    configuration=configuration,
    configuration_fingerprint=configuration_fingerprint,
    fresh_solver_invocation_verified=(
      len(retained_cases) == len(requested_resolutions)
    ),
    fidelity_isolation_verified=fidelity_isolation_verified,
    message=(
      'fresh global/coupled downstream response refinement completed; '
      'global feedback, canonical boundary closure, physical chain promotion, '
      'and external validation remain separate gates'
    ),
  )
####
