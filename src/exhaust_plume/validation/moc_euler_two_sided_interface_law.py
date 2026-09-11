"""Independent audit for the solver-owned two-sided interface law.

The research law derives a dimensional normal response from an upstream source
band and retained downstream cells.  This validator repeats the source
lineage, downstream interpolation, normal construction, Rankine--Hugoniot
speed, geometry, and response-packet checks without importing the law's
private helpers.  A passing audit is local research evidence only; canonical
free-boundary closure, refinement, external validation, and production
promotion remain blocked.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.euler_two_sided_interface_law import (
  MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID,
  MocEulerTwoSidedInterfaceLawResult,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  compute_moc_euler_two_sided_interface_normal_displacements,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_INTERFACE_LAW_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedInterfaceLawAuditStatus',
  'MocEulerTwoSidedInterfaceLawAudit',
  'measure_moc_euler_two_sided_interface_law',
)


MOC_EULER_TWO_SIDED_INTERFACE_LAW_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-solver-owned-interface-law-audit'
)


class MocEulerTwoSidedInterfaceLawAuditStatus(str, Enum):
  """Typed outcomes of the independent local response audit."""

  CONVERGED_LOCAL_AUDIT = 'converged_two-sided-interface-law-audit'
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'two-sided-interface-law-audit-request-failure'
  CURRENT_FIELD_FAILURE = 'two-sided-interface-law-audit-current-field-failure'
  SOURCE_LINEAGE_FAILURE = 'two-sided-interface-law-audit-source-lineage-failure'
  DOWNSTREAM_PROBE_FAILURE = 'two-sided-interface-law-audit-downstream-probe-failure'
  RESPONSE_FAILURE = 'two-sided-interface-law-audit-response-failure'
  GEOMETRY_FAILURE = 'two-sided-interface-law-audit-geometry-failure'
  COMPANION_FIELD_FAILURE = 'two-sided-interface-law-audit-companion-field-failure'
  FLAG_FAILURE = 'two-sided-interface-law-audit-flag-failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceLawAudit:
  """Recomputed evidence for one solver-owned interface response."""

  status: MocEulerTwoSidedInterfaceLawAuditStatus
  result_status: str | None
  request_verified: bool
  current_field_verified: bool
  source_lineage_verified: bool
  downstream_probe_verified: bool
  response_lineage_verified: bool
  candidate_geometry_verified: bool
  companion_field_verified: bool
  endpoint_constraints_verified: bool
  interface_motion_verified: bool
  result_flags_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  maximum_interface_normal_speed_m_s: float = 0.0
  maximum_normal_displacement_m: float = 0.0
  maximum_mass_flux_residual_kg_m2_s: float = 0.0
  maximum_normal_momentum_residual_Pa: float = 0.0
  maximum_energy_flux_residual_W_m2: float = 0.0
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_INTERFACE_LAW_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedInterfaceLawAuditStatus,
    ):
      raise TypeError('status must be an interface-law audit status')
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    for name in (
      'request_verified',
      'current_field_verified',
      'source_lineage_verified',
      'downstream_probe_verified',
      'response_lineage_verified',
      'candidate_geometry_verified',
      'companion_field_verified',
      'endpoint_constraints_verified',
      'interface_motion_verified',
      'result_flags_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'maximum_interface_normal_speed_m_s',
      'maximum_normal_displacement_m',
      'maximum_mass_flux_residual_kg_m2_s',
      'maximum_normal_momentum_residual_Pa',
      'maximum_energy_flux_residual_W_m2',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedInterfaceLawAuditStatus.CONVERGED_LOCAL_AUDIT
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether all local solver-law evidence agrees independently."""

    return bool(
      self.converged
      and self.request_verified
      and self.current_field_verified
      and self.source_lineage_verified
      and self.downstream_probe_verified
      and self.response_lineage_verified
      and self.candidate_geometry_verified
      and self.companion_field_verified
      and self.endpoint_constraints_verified
      and self.interface_motion_verified
      and self.result_flags_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'result_status': self.result_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'request_verified': self.request_verified,
      'current_field_verified': self.current_field_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'downstream_probe_verified': self.downstream_probe_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'candidate_geometry_verified': self.candidate_geometry_verified,
      'companion_field_verified': self.companion_field_verified,
      'endpoint_constraints_verified': self.endpoint_constraints_verified,
      'interface_motion_verified': self.interface_motion_verified,
      'result_flags_verified': self.result_flags_verified,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'maximum_interface_normal_speed_m_s': (
        self.maximum_interface_normal_speed_m_s
      ),
      'maximum_normal_displacement_m': self.maximum_normal_displacement_m,
      'maximum_mass_flux_residual_kg_m2_s': (
        self.maximum_mass_flux_residual_kg_m2_s
      ),
      'maximum_normal_momentum_residual_Pa': (
        self.maximum_normal_momentum_residual_Pa
      ),
      'maximum_energy_flux_residual_W_m2': (
        self.maximum_energy_flux_residual_W_m2
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedInterfaceLawAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  request_verified: bool = False,
  current_field_verified: bool = False,
  source_lineage_verified: bool = False,
  downstream_probe_verified: bool = False,
  response_lineage_verified: bool = False,
  candidate_geometry_verified: bool = False,
  companion_field_verified: bool = False,
  endpoint_constraints_verified: bool = False,
  interface_motion_verified: bool = False,
  result_flags_verified: bool = False,
  maximum_interface_normal_speed_m_s: float = 0.0,
  maximum_normal_displacement_m: float = 0.0,
  maximum_mass_flux_residual_kg_m2_s: float = 0.0,
  maximum_normal_momentum_residual_Pa: float = 0.0,
  maximum_energy_flux_residual_W_m2: float = 0.0,
) -> MocEulerTwoSidedInterfaceLawAudit:
  return MocEulerTwoSidedInterfaceLawAudit(
    status=status,
    result_status=result_status,
    request_verified=request_verified,
    current_field_verified=current_field_verified,
    source_lineage_verified=source_lineage_verified,
    downstream_probe_verified=downstream_probe_verified,
    response_lineage_verified=response_lineage_verified,
    candidate_geometry_verified=candidate_geometry_verified,
    companion_field_verified=companion_field_verified,
    endpoint_constraints_verified=endpoint_constraints_verified,
    interface_motion_verified=interface_motion_verified,
    result_flags_verified=result_flags_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    maximum_interface_normal_speed_m_s=maximum_interface_normal_speed_m_s,
    maximum_normal_displacement_m=maximum_normal_displacement_m,
    maximum_mass_flux_residual_kg_m2_s=maximum_mass_flux_residual_kg_m2_s,
    maximum_normal_momentum_residual_Pa=maximum_normal_momentum_residual_Pa,
    maximum_energy_flux_residual_W_m2=maximum_energy_flux_residual_W_m2,
    message=message,
  )


def _close(first: float, second: float, tolerance: float) -> bool:
  return abs(first - second) <= tolerance * max(1.0, abs(first), abs(second))


def _state_close(first: Any, second: Any, tolerance: float) -> bool:
  return all(
    _close(float(getattr(first, name)), float(getattr(second, name)), tolerance)
    for name in ('x_m', 'y_m', 'theta_rad', 'mach', 'gamma')
  )


def _point_matches(
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> bool:
  return bool(
    abs(first[0] - second[0]) <= tolerance_m
    and abs(first[1] - second[1]) <= tolerance_m
  )


def _normal_for_cell(
  field: Any,
  shock_points: tuple[tuple[float, float], ...],
  index: int,
  tolerance_m: float,
) -> tuple[float, float]:
  if index == len(shock_points) - 1:
    edge_start, edge_end = shock_points[index - 1], shock_points[index]
  else:
    edge_start, edge_end = shock_points[index], shock_points[index + 1]
  ####
  tangent_x = edge_end[0] - edge_start[0]
  tangent_y = edge_end[1] - edge_start[1]
  tangent_length = hypot(tangent_x, tangent_y)
  if tangent_length <= tolerance_m:
    raise ValueError('shock probe edge has no positive length')
  ####
  normal_x = -tangent_y / tangent_length
  normal_y = tangent_x / tangent_length
  candidates = []
  for vertices, _states, _pressures in field.cell_state_samples(
    position_tolerance_m=tolerance_m,
  ):
    if (
      any(_point_matches(vertex, edge_start, tolerance_m) for vertex in vertices)
      and any(_point_matches(vertex, edge_end, tolerance_m) for vertex in vertices)
    ):
      candidates.append(vertices)
  ####
  if len(candidates) != 1:
    raise ValueError(
      'independent interface-law audit expected exactly one downstream cell '
      f'at shock sample {index}, found {len(candidates)}'
    )
  ####
  centroid = (
    sum(vertex[0] for vertex in candidates[0]) / len(candidates[0]),
    sum(vertex[1] for vertex in candidates[0]) / len(candidates[0]),
  )
  midpoint = (
    0.5 * (edge_start[0] + edge_end[0]),
    0.5 * (edge_start[1] + edge_end[1]),
  )
  if (
    (centroid[0] - midpoint[0]) * normal_x
    + (centroid[1] - midpoint[1]) * normal_y
  ) < 0.0:
    normal_x = -normal_x
    normal_y = -normal_y
  ####
  return normal_x, normal_y


def _primitive(
  state: Any,
  total_pressure_Pa: float,
  *,
  reference_total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> tuple[float, float, float, float, float]:
  gamma = float(state.gamma)
  mach = float(state.mach)
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  temperature = reference_total_temperature_K / factor
  pressure = total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
  density = pressure / (gas_constant_J_kgK * temperature)
  sound_speed = sqrt(gamma * gas_constant_J_kgK * temperature)
  speed = mach * sound_speed
  velocity_u = speed * cos(float(state.theta_rad))
  velocity_v = speed * sin(float(state.theta_rad))
  specific_energy = pressure / (density * (gamma - 1.0)) + 0.5 * (
    velocity_u * velocity_u + velocity_v * velocity_v
  )
  total_enthalpy_density = density * specific_energy + pressure
  if not (
    isfinite(density)
    and density > 0.0
    and isfinite(velocity_u)
    and isfinite(velocity_v)
    and isfinite(pressure)
    and pressure > 0.0
    and isfinite(total_enthalpy_density)
    and total_enthalpy_density > 0.0
  ):
    raise ValueError('independent dimensional primitive is nonphysical')
  ####
  return (
    density,
    velocity_u,
    velocity_v,
    pressure,
    total_enthalpy_density,
  )


def _geometry_valid(result: MocEulerTwoSidedInterfaceLawResult) -> bool:
  request = result.request
  response = result.response
  current = result.current_field_iteration
  if request is None or response is None or current is None:
    return False
  ####
  points = response.next_shock_boundary.shock_points_m
  target_y = 0.0 if current.request is None else current.request.target_centerline_y_m
  return bool(
    len(points) >= 3
    and all(
      second[0] > first[0] + request.position_tolerance_m
      and second[1] <= first[1] + request.position_tolerance_m
      for first, second in zip(points, points[1:])
    )
    and points[-1][1] >= target_y - request.position_tolerance_m
  )


def measure_moc_euler_two_sided_interface_law(
  result: MocEulerTwoSidedInterfaceLawResult,
) -> MocEulerTwoSidedInterfaceLawAudit:
  """Independently remeasure one solver-owned interface response."""

  if not isinstance(result, MocEulerTwoSidedInterfaceLawResult):
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.INVALID_INPUT,
      'result must be a MocEulerTwoSidedInterfaceLawResult',
    )
  ####
  request = result.request
  current = result.current_field_iteration
  request_verified = bool(request is not None and current is not None)
  if not request_verified or request is None or current is None:
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.REQUEST_FAILURE,
      'interface-law result did not retain its typed request and current field',
      result_status=result.status.value,
      request_verified=request_verified,
    )
  ####
  physical = current.final_physical_field
  field = None if physical is None else physical.field
  current_field_verified = bool(
    current.field_iteration_verified
    and current.shock_boundary is not None
    and physical is not None
    and physical.physical_field_verified
    and field is not None
  )
  if not current_field_verified or current.shock_boundary is None or field is None:
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.CURRENT_FIELD_FAILURE,
      'independent audit requires a verified exact two-sided field and retained physical mesh',
      result_status=result.status.value,
      request_verified=True,
      current_field_verified=False,
    )
  ####
  source_lineage_verified = True
  try:
    for point, expected_state, expected_pressure in zip(
      current.shock_boundary.shock_points_m,
      current.shock_boundary.upstream_states,
      current.shock_boundary.upstream_total_pressure_Pa,
      strict=True,
    ):
      state = request.source_band.state_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      pressure = request.source_band.total_pressure_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      if state is None or pressure is None:
        source_lineage_verified = False
        break
      if not _state_close(state, expected_state, request.source_state_tolerance):
        source_lineage_verified = False
        break
      if not _close(
        float(pressure),
        float(expected_pressure),
        request.source_pressure_tolerance,
      ):
        source_lineage_verified = False
        break
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    source_lineage_verified = False
  ####
  if not source_lineage_verified:
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.SOURCE_LINEAGE_FAILURE,
      'independent source-band sampling did not reproduce the current shock lineage',
      result_status=result.status.value,
      request_verified=True,
      current_field_verified=True,
    )
  ####
  response = result.response
  if response is None:
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.RESPONSE_FAILURE,
      'interface-law result retained no response packet',
      result_status=result.status.value,
      request_verified=True,
      current_field_verified=True,
      source_lineage_verified=True,
    )
  ####
  sample_count = len(current.shock_boundary.shock_points_m)
  downstream_probe_verified = bool(
    len(result.probe_points_m)
    == len(result.probe_normals)
    == len(result.interface_normal_speeds_m_s)
    == len(result.downstream_probe_states)
    == len(result.downstream_probe_total_pressure_Pa)
    == sample_count
  )
  expected_speeds: list[float] = []
  expected_mass: list[float] = []
  expected_momentum: list[float] = []
  expected_energy: list[float] = []
  if downstream_probe_verified:
    try:
      for index, point in enumerate(current.shock_boundary.shock_points_m):
        probe_point = result.probe_points_m[index]
        state = field.state_at(
          probe_point,
          position_tolerance_m=max(1.0e-10, request.position_tolerance_m * 0.1),
        )
        pressure = field.total_pressure_at(
          probe_point,
          position_tolerance_m=max(1.0e-10, request.position_tolerance_m * 0.1),
        )
        declared_state = result.downstream_probe_states[index]
        declared_pressure = float(result.downstream_probe_total_pressure_Pa[index])
        if state is None or pressure is None:
          raise ValueError(f'field does not independently sample downstream probe {index}')
        if not _state_close(state, declared_state, request.source_state_tolerance):
          raise ValueError(f'downstream state mismatch at probe {index}')
        if not _close(
          float(pressure),
          declared_pressure,
          request.source_pressure_tolerance,
        ):
          raise ValueError(f'downstream pressure mismatch at probe {index}')
        normal_x, normal_y = _normal_for_cell(
          field,
          current.shock_boundary.shock_points_m,
          index,
          request.position_tolerance_m,
        )
        declared_normal = result.probe_normals[index]
        if not _close(normal_x, declared_normal[0], 1.0e-7) or not _close(
          normal_y,
          declared_normal[1],
          1.0e-7,
        ):
          raise ValueError(f'downstream normal mismatch at probe {index}')
        upstream_state = request.source_band.state_at(
          point,
          position_tolerance_m=request.position_tolerance_m,
        )
        upstream_pressure = request.source_band.total_pressure_at(
          point,
          position_tolerance_m=request.position_tolerance_m,
        )
        if upstream_state is None or upstream_pressure is None:
          raise ValueError(f'upstream source disappeared at probe {index}')
        upstream = _primitive(
          upstream_state,
          float(upstream_pressure),
          reference_total_temperature_K=request.reference_total_temperature_K,
          gas_constant_J_kgK=request.gas_constant_J_kgK,
        )
        downstream = _primitive(
          declared_state,
          declared_pressure,
          reference_total_temperature_K=request.reference_total_temperature_K,
          gas_constant_J_kgK=request.gas_constant_J_kgK,
        )
        upstream_density, upstream_u, upstream_v, upstream_static, upstream_h = upstream
        downstream_density, downstream_u, downstream_v, downstream_static, downstream_h = downstream
        upstream_normal = upstream_u * normal_x + upstream_v * normal_y
        downstream_normal = downstream_u * normal_x + downstream_v * normal_y
        density_jump = downstream_density - upstream_density
        if abs(density_jump) <= 1.0e-12 * max(upstream_density, downstream_density, 1.0):
          raise ValueError(f'density jump is too small at probe {index}')
        expected_speeds.append(
          (downstream_density * downstream_normal - upstream_density * upstream_normal)
          / density_jump
        )
        speed = expected_speeds[-1]
        upstream_relative = upstream_normal - speed
        downstream_relative = downstream_normal - speed
        expected_mass.append(
          abs(
            downstream_density * downstream_relative
            - upstream_density * upstream_relative
          )
        )
        expected_momentum.append(
          abs(
            downstream_density * downstream_relative**2 + downstream_static
            - upstream_density * upstream_relative**2 - upstream_static
          )
        )
        expected_energy.append(
          abs(
            downstream_h * downstream_relative
            - upstream_h * upstream_relative
          )
        )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      downstream_probe_verified = False
  ####
  downstream_probe_verified = bool(
    downstream_probe_verified
    and all(
      _close(actual, expected, max(1.0e-8, request.source_state_tolerance))
      for actual, expected in zip(
        result.interface_normal_speeds_m_s,
        expected_speeds,
        strict=True,
      )
    )
    and all(
      _close(actual, expected, max(1.0e-8, request.residual_tolerance))
      for actual, expected in zip(response.mass_flux_residuals_kg_m2_s, expected_mass, strict=True)
    )
    and all(
      _close(actual, expected, max(1.0e-8, request.residual_tolerance))
      for actual, expected in zip(response.normal_momentum_residuals_Pa, expected_momentum, strict=True)
    )
    and all(
      _close(actual, expected, max(1.0e-8, request.residual_tolerance))
      for actual, expected in zip(response.energy_flux_residuals_W_m2, expected_energy, strict=True)
    )
  )
  if not downstream_probe_verified:
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.DOWNSTREAM_PROBE_FAILURE,
      'independent downstream state, normal, speed, or residual remeasurement failed',
      result_status=result.status.value,
      request_verified=True,
      current_field_verified=True,
      source_lineage_verified=True,
    )
  ####
  try:
    displacements = compute_moc_euler_two_sided_interface_normal_displacements(
      response.prior_shock_boundary,
      response.next_shock_boundary,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceLawAuditStatus.RESPONSE_FAILURE,
      f'independent displacement remeasurement failed: {error}',
      result_status=result.status.value,
      request_verified=True,
      current_field_verified=True,
      source_lineage_verified=True,
      downstream_probe_verified=True,
    )
  ####
  response_lineage_verified = bool(
    response.prior_shock_boundary is current.shock_boundary
    and response.next_companion_field.shock_boundary is response.next_shock_boundary
    and response.response_source == MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID
    and response.law_id == MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID
    and len(displacements) == len(response.normal_displacements_m)
    and all(
      _close(actual, declared, request.position_tolerance_m)
      for actual, declared in zip(
        displacements,
        response.normal_displacements_m,
        strict=True,
      )
    )
  )
  maximum_displacement = max((abs(value) for value in displacements), default=0.0)
  interface_motion_verified = any(
    abs(value) > request.position_tolerance_m for value in displacements
  )
  candidate_geometry_verified = _geometry_valid(result)
  endpoint_constraints_verified = bool(
    all(
      abs(value) <= request.position_tolerance_m
      for value in response.normal_displacements_m[: request.anchor_endpoint_samples]
    )
    and all(
      abs(value) <= request.position_tolerance_m
      for value in response.normal_displacements_m[-request.anchor_endpoint_samples :]
    )
    and all(
      _point_matches(
        prior,
        next_point,
        request.position_tolerance_m,
      )
      for prior, next_point in (
        *zip(
          response.prior_shock_boundary.shock_points_m[: request.anchor_endpoint_samples],
          response.next_shock_boundary.shock_points_m[: request.anchor_endpoint_samples],
          strict=True,
        ),
        *zip(
          response.prior_shock_boundary.shock_points_m[-request.anchor_endpoint_samples :],
          response.next_shock_boundary.shock_points_m[-request.anchor_endpoint_samples :],
          strict=True,
        ),
      )
    )
  )
  companion_field_verified = bool(
    response.next_companion_field.converged
    and response.next_companion_field.state_sampling_available
    and response.next_companion_field.shock_boundary_local_euler_verified
    and response.next_companion_field.companion_boundary_contract_verified
    and response.next_companion_field.pressure_lineage_verified
    and not response.next_companion_field.physical_closure_verified
    and response.next_companion_field.chain_promotion_blocked
    and not response.next_companion_field.production_claim_allowed
  )
  result_flags_verified = bool(
    result.source_lineage_verified == source_lineage_verified
    and result.downstream_probe_verified == downstream_probe_verified
    and result.candidate_geometry_verified == candidate_geometry_verified
    and result.companion_field_verified == companion_field_verified
    and result.endpoint_constraints_applied == endpoint_constraints_verified
    and result.interface_motion_verified == interface_motion_verified
    and result.response_ready == bool(
      response_lineage_verified
      and candidate_geometry_verified
      and companion_field_verified
      and endpoint_constraints_verified
      and interface_motion_verified
    )
    and result.as_report()['chain_promotion_blocked'] is True
    and result.as_report()['production_claim_allowed'] is False
  )
  expected_ready = bool(
    response_lineage_verified
    and candidate_geometry_verified
    and companion_field_verified
    and endpoint_constraints_verified
    and interface_motion_verified
  )
  status = (
    MocEulerTwoSidedInterfaceLawAuditStatus.CONVERGED_LOCAL_AUDIT
    if expected_ready and result_flags_verified
    else MocEulerTwoSidedInterfaceLawAuditStatus.FLAG_FAILURE
  )
  return _failure(
    status,
    (
      'independent audit passed source lineage, downstream primitive/normal '
      'remeasurement, exact response lineage, endpoint constraints, and open '
      'companion-field gates; canonical closure and production promotion remain blocked'
      if status is MocEulerTwoSidedInterfaceLawAuditStatus.CONVERGED_LOCAL_AUDIT
      else 'interface-law result flags did not match independently remeasured evidence'
    ),
    result_status=result.status.value,
    request_verified=True,
    current_field_verified=True,
    source_lineage_verified=source_lineage_verified,
    downstream_probe_verified=downstream_probe_verified,
    response_lineage_verified=response_lineage_verified,
    candidate_geometry_verified=candidate_geometry_verified,
    companion_field_verified=companion_field_verified,
    endpoint_constraints_verified=endpoint_constraints_verified,
    interface_motion_verified=interface_motion_verified,
    result_flags_verified=result_flags_verified,
    maximum_interface_normal_speed_m_s=max(
      (abs(value) for value in expected_speeds),
      default=0.0,
    ),
    maximum_normal_displacement_m=maximum_displacement,
    maximum_mass_flux_residual_kg_m2_s=max(expected_mass, default=0.0),
    maximum_normal_momentum_residual_Pa=max(expected_momentum, default=0.0),
    maximum_energy_flux_residual_W_m2=max(expected_energy, default=0.0),
  )
