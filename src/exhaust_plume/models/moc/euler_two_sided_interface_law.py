"""Solver-owned research response law for a two-sided moving shock.

The fixed-front two-sided field already contains the two pieces needed for a
bounded front-tracking response: an upstream state/total-pressure source band
and an interior downstream state on the retained physical mesh.  This module
uses those states in the moving Rankine--Hugoniot mass equation to derive a
dimensional normal front speed, evaluates all three flux channels in the
front-relative frame, advances only the unconstrained interior shock samples,
resamples the upstream field by identity, and refits an exact Euler-consistent
shock before rebuilding the open companion strip.

This is deliberately a research law, not canonical free-boundary closure.  It
does not invent a subsonic field, move an endpoint without a boundary law, or
promote the regenerated strip.  Missing source coverage, a missing downstream
cell, a nonphysical speed, or an invalid exact refit is a typed failure.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.euler_characteristic_field import (
  assemble_euler_consistent_companion_characteristic_strip,
  solve_euler_ambient_companion_boundary_reference,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  fit_euler_consistent_shock_boundary_from_geometry,
)
from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
  MocEulerTwoSidedMovingInterfaceRequest,
  MocEulerTwoSidedMovingInterfaceResult,
  compute_moc_euler_two_sided_interface_normal_displacements,
  solve_euler_two_sided_moving_interface,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
)
from exhaust_plume.models.moc.reflected_domain import (
  MocReflectedDomainAlternatingSourceResult,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MOC_EULER_TWO_SIDED_INTERFACE_LAW_OPERATOR_ID',
  'MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID',
  'MocEulerTwoSidedInterfaceLawStatus',
  'MocEulerTwoSidedInterfaceLawRequest',
  'MocEulerTwoSidedInterfaceLawResult',
  'build_solver_owned_euler_two_sided_interface_response',
  'make_solver_owned_euler_two_sided_interface_advance',
  'solve_euler_two_sided_moving_interface_with_solver_owned_law',
)


MOC_EULER_TWO_SIDED_INTERFACE_LAW_OPERATOR_ID = (
  'op.moc.euler-two-sided-solver-owned-interface-law'
)
MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID = (
  'solver-owned-two-sided-euler-rankine-front-response-v1'
)


class MocEulerTwoSidedInterfaceLawStatus(str, Enum):
  """Typed outcomes of one solver-owned interface response attempt."""

  RESPONSE_READY = 'solver-owned-two-sided-interface-response-ready'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FIELD_REQUIRED = 'two-sided-interface-law-source-field-required'
  SOURCE_LINEAGE_FAILURE = 'two-sided-interface-law-source-lineage-failure'
  DOWNSTREAM_FIELD_REQUIRED = 'two-sided-interface-law-downstream-field-required'
  DOWNSTREAM_PROBE_FAILURE = 'two-sided-interface-law-downstream-probe-failure'
  GEOMETRY_FAILURE = 'two-sided-interface-law-geometry-failure'
  SHOCK_FIT_FAILURE = 'two-sided-interface-law-shock-fit-failure'
  COMPANION_BOUNDARY_FAILURE = 'two-sided-interface-law-companion-boundary-failure'
  COMPANION_FIELD_FAILURE = 'two-sided-interface-law-companion-field-failure'
  NO_INTERFACE_MOTION = 'two-sided-interface-law-no-interface-motion'


def _positive_float(value: Any, name: str) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric


def _bounded_fraction(
  value: Any,
  name: str,
  *,
  allow_zero: bool = False,
) -> float:
  numeric = float(value)
  if not isfinite(numeric) or (numeric < 0.0 if allow_zero else numeric <= 0.0):
    qualifier = 'nonnegative' if allow_zero else 'positive'
    raise ValueError(f'{name} must be finite and {qualifier}')
  if numeric > 1.0:
    raise ValueError(f'{name} must be no greater than one')
  ####
  return numeric


def _primitive(
  state: Any,
  total_pressure_Pa: float,
  *,
  reference_total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> tuple[float, float, float, float, float]:
  """Return rho, u, v, p, and rho*total-specific-enthalpy.

  ``CharacteristicState`` carries Mach/angle but no dimensional temperature.
  The explicit total-temperature and gas-constant inputs make the dimensional
  scale used by the front-speed law visible instead of silently assuming one.
  """

  gamma = float(state.gamma)
  mach = float(state.mach)
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  temperature = reference_total_temperature_K / factor
  pressure = float(total_pressure_Pa) / factor ** (gamma / (gamma - 1.0))
  density = pressure / (gas_constant_J_kgK * temperature)
  sound_speed = sqrt(gamma * gas_constant_J_kgK * temperature)
  speed = mach * sound_speed
  velocity_u = speed * cos(float(state.theta_rad))
  velocity_v = speed * sin(float(state.theta_rad))
  specific_energy = pressure / (density * (gamma - 1.0)) + 0.5 * (
    velocity_u * velocity_u + velocity_v * velocity_v
  )
  total_enthalpy_density = density * specific_energy + pressure
  values = (
    density,
    velocity_u,
    velocity_v,
    pressure,
    total_enthalpy_density,
  )
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
    raise ValueError('dimensional primitive reconstruction was nonphysical')
  ####
  return values


def _point_matches(
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> bool:
  return bool(
    abs(first[0] - second[0]) <= tolerance_m
    and abs(first[1] - second[1]) <= tolerance_m
  )


def _cell_centroid(
  vertices: tuple[tuple[float, float], ...],
) -> tuple[float, float]:
  if len(vertices) < 3:
    raise ValueError('downstream shock cell must contain at least three vertices')
  ####
  count = float(len(vertices))
  return (
    sum(point[0] for point in vertices) / count,
    sum(point[1] for point in vertices) / count,
  )


@dataclass(frozen=True, slots=True)
class _DownstreamProbe:
  point_m: tuple[float, float]
  probe_point_m: tuple[float, float]
  normal_x: float
  normal_y: float
  state: Any
  total_pressure_Pa: float


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceLawRequest:
  """Explicit scales and boundary policies for the research front law."""

  source_band: MocReflectedDomainAlternatingSourceResult
  reference_total_temperature_K: float
  gas_constant_J_kgK: float = 287.05
  pseudo_time_step_s: float = 1.0e-8
  relaxation: float = 0.5
  maximum_normal_displacement_m: float = 1.0e-3
  # The interface state is the one-sided post-front limit.  A positive
  # fraction samples just inside the retained downstream cell for the
  # research response; zero selects the explicitly retained post-shock
  # boundary state and is the stationary-equilibrium/front-limit path.
  downstream_probe_fraction: float = 0.01
  companion_separation_m: float = 0.5
  companion_seed_flow_angle_rad: float = 0.0
  # Two samples per endpoint are retained so the endpoint tangent is not
  # changed by an interior-only update.  A single anchored point would still
  # change the geometry-conditioned endpoint turn.
  anchor_endpoint_samples: int = 2
  branch: ShockBranch = ShockBranch.WEAK
  position_tolerance_m: float = 1.0e-8
  source_state_tolerance: float = 1.0e-6
  source_pressure_tolerance: float = 1.0e-8
  residual_tolerance: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_band,
      MocReflectedDomainAlternatingSourceResult,
    ):
      raise TypeError(
        'source_band must be a MocReflectedDomainAlternatingSourceResult'
      )
    ####
    if not self.source_band.source_field_verified:
      raise ValueError(
        'source_band must pass its independent source-field gates before it '
        'can drive a moving-interface response'
      )
    ####
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    ####
    for name in (
      'reference_total_temperature_K',
      'gas_constant_J_kgK',
      'pseudo_time_step_s',
      'maximum_normal_displacement_m',
      'companion_separation_m',
      'position_tolerance_m',
      'source_state_tolerance',
      'source_pressure_tolerance',
      'residual_tolerance',
    ):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    object.__setattr__(self, 'relaxation', _bounded_fraction(self.relaxation, 'relaxation'))
    object.__setattr__(
      self,
      'downstream_probe_fraction',
      _bounded_fraction(
        self.downstream_probe_fraction,
        'downstream_probe_fraction',
        allow_zero=True,
      ),
    )
    ####
    seed_angle = float(self.companion_seed_flow_angle_rad)
    if not isfinite(seed_angle):
      raise ValueError('companion_seed_flow_angle_rad must be finite')
    ####
    object.__setattr__(self, 'companion_seed_flow_angle_rad', seed_angle)
    if (
      isinstance(self.anchor_endpoint_samples, bool)
      or not isinstance(self.anchor_endpoint_samples, int)
      or self.anchor_endpoint_samples < 1
    ):
      raise ValueError('anchor_endpoint_samples must be a positive integer')
    ####
    if self.source_band.ambient_pressure_Pa is None:
      raise ValueError('source_band must retain an ambient pressure')
    ####
  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_EULER_TWO_SIDED_INTERFACE_LAW_OPERATOR_ID,
      'law_id': MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID,
      'source_status': self.source_band.status.value,
      'source_field_verified': self.source_band.source_field_verified,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'pseudo_time_step_s': self.pseudo_time_step_s,
      'relaxation': self.relaxation,
      'maximum_normal_displacement_m': self.maximum_normal_displacement_m,
      'downstream_probe_fraction': self.downstream_probe_fraction,
      'companion_separation_m': self.companion_separation_m,
      'companion_seed_flow_angle_rad': self.companion_seed_flow_angle_rad,
      'anchor_endpoint_samples': self.anchor_endpoint_samples,
      'branch': self.branch.value,
      'position_tolerance_m': self.position_tolerance_m,
      'source_state_tolerance': self.source_state_tolerance,
      'source_pressure_tolerance': self.source_pressure_tolerance,
      'residual_tolerance': self.residual_tolerance,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceLawResult:
  """One independently inspectable front-response attempt."""

  status: MocEulerTwoSidedInterfaceLawStatus
  request: MocEulerTwoSidedInterfaceLawRequest | None
  current_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  response: MocEulerTwoSidedInterfaceResponse | None
  probe_points_m: tuple[tuple[float, float], ...] = ()
  probe_normals: tuple[tuple[float, float], ...] = ()
  interface_normal_speeds_m_s: tuple[float, ...] = ()
  downstream_probe_states: tuple[Any, ...] = ()
  downstream_probe_total_pressure_Pa: tuple[float, ...] = ()
  source_lineage_verified: bool = False
  downstream_probe_verified: bool = False
  candidate_geometry_verified: bool = False
  companion_field_verified: bool = False
  endpoint_constraints_applied: bool = False
  interface_motion_verified: bool = False
  stationary_equilibrium_candidate: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedInterfaceLawStatus):
      raise TypeError('status must be a MocEulerTwoSidedInterfaceLawStatus')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocEulerTwoSidedInterfaceLawRequest,
    ):
      raise TypeError(
        'request must be a MocEulerTwoSidedInterfaceLawRequest or None'
      )
    ####
    if self.current_field_iteration is not None and not isinstance(
      self.current_field_iteration,
      MocEulerTwoSidedFieldIterationResult,
    ):
      raise TypeError(
        'current_field_iteration must be a '
        'MocEulerTwoSidedFieldIterationResult or None'
      )
    ####
    if self.response is not None and not isinstance(
      self.response,
      MocEulerTwoSidedInterfaceResponse,
    ):
      raise TypeError(
        'response must be a MocEulerTwoSidedInterfaceResponse or None'
      )
    ####
    points = tuple(
      (float(point[0]), float(point[1])) for point in self.probe_points_m
    )
    normals = tuple(
      (float(normal[0]), float(normal[1])) for normal in self.probe_normals
    )
    speeds = tuple(float(value) for value in self.interface_normal_speeds_m_s)
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('probe_points_m must contain finite points')
    ####
    if any(
      not all(isfinite(value) for value in normal)
      or abs(hypot(*normal) - 1.0) > 1.0e-6
      for normal in normals
    ):
      raise ValueError('probe_normals must contain finite unit normals')
    ####
    if any(not isfinite(value) for value in speeds):
      raise ValueError('interface_normal_speeds_m_s must be finite')
    ####
    if not (
      len(points)
      == len(normals)
      == len(speeds)
      == len(self.downstream_probe_states)
      == len(self.downstream_probe_total_pressure_Pa)
    ):
      raise ValueError('interface-law probe channels must have equal lengths')
    ####
    if any(
      not isfinite(float(value)) or float(value) <= 0.0
      for value in self.downstream_probe_total_pressure_Pa
    ):
      raise ValueError(
        'downstream_probe_total_pressure_Pa must contain finite positive values'
      )
    ####
    for name in (
      'source_lineage_verified',
      'downstream_probe_verified',
      'candidate_geometry_verified',
      'companion_field_verified',
      'endpoint_constraints_applied',
      'interface_motion_verified',
      'stationary_equilibrium_candidate',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.status is MocEulerTwoSidedInterfaceLawStatus.RESPONSE_READY and (
      self.response is None
      or not self.source_lineage_verified
      or not self.downstream_probe_verified
      or not self.candidate_geometry_verified
      or not self.companion_field_verified
      or not self.endpoint_constraints_applied
      or not (
        self.interface_motion_verified
        or self.stationary_equilibrium_candidate
      )
    ):
      raise ValueError(
        'a ready interface-law response must retain every local response gate'
      )
    ####
    object.__setattr__(self, 'probe_points_m', points)
    object.__setattr__(self, 'probe_normals', normals)
    object.__setattr__(self, 'interface_normal_speeds_m_s', speeds)
    object.__setattr__(
      self,
      'downstream_probe_total_pressure_Pa',
      tuple(float(value) for value in self.downstream_probe_total_pressure_Pa),
    )
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def response_ready(self) -> bool:
    return self.status is MocEulerTwoSidedInterfaceLawStatus.RESPONSE_READY
  ####

  @property
  def maximum_interface_normal_speed_m_s(self) -> float:
    return max((abs(value) for value in self.interface_normal_speeds_m_s), default=0.0)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_EULER_TWO_SIDED_INTERFACE_LAW_OPERATOR_ID,
      'law_id': MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID,
      'status': self.status.value,
      'response_ready': self.response_ready,
      'request': None if self.request is None else self.request.as_report(),
      'source_lineage_verified': self.source_lineage_verified,
      'downstream_probe_verified': self.downstream_probe_verified,
      'candidate_geometry_verified': self.candidate_geometry_verified,
      'companion_field_verified': self.companion_field_verified,
      'endpoint_constraints_applied': self.endpoint_constraints_applied,
      'interface_motion_verified': self.interface_motion_verified,
      'stationary_equilibrium_candidate': self.stationary_equilibrium_candidate,
      'probe_points_m': self.probe_points_m,
      'probe_normals': self.probe_normals,
      'interface_normal_speeds_m_s': self.interface_normal_speeds_m_s,
      'maximum_interface_normal_speed_m_s': (
        self.maximum_interface_normal_speed_m_s
      ),
      'downstream_probe_states': tuple(
        {
          'x_m': state.x_m,
          'y_m': state.y_m,
          'theta_rad': state.theta_rad,
          'mach': state.mach,
          'gamma': state.gamma,
        }
        for state in self.downstream_probe_states
      ),
      'downstream_probe_total_pressure_Pa': (
        self.downstream_probe_total_pressure_Pa
      ),
      'response': None if self.response is None else self.response.as_report(),
      'message': self.message,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedInterfaceLawStatus,
  message: str,
  *,
  request: MocEulerTwoSidedInterfaceLawRequest | None = None,
  current_field_iteration: MocEulerTwoSidedFieldIterationResult | None = None,
  **values: Any,
) -> MocEulerTwoSidedInterfaceLawResult:
  return MocEulerTwoSidedInterfaceLawResult(
    status=status,
    request=request,
    current_field_iteration=current_field_iteration,
    response=None,
    message=message,
    **values,
  )


def _source_sample(
  source_band: MocReflectedDomainAlternatingSourceResult,
  point_m: tuple[float, float],
  *,
  tolerance_m: float,
) -> tuple[Any, float]:
  state = source_band.state_at(point_m, position_tolerance_m=tolerance_m)
  pressure = source_band.total_pressure_at(
    point_m,
    position_tolerance_m=tolerance_m,
  )
  if state is None or pressure is None:
    raise ValueError('solver-owned upstream source band does not cover the proposed shock point')
  ####
  pressure_value = float(pressure)
  if not isfinite(pressure_value) or pressure_value <= 0.0:
    raise ValueError('solver-owned upstream source band returned a nonphysical pressure')
  ####
  return state, pressure_value


def _source_static_pressure(
  source_band: MocReflectedDomainAlternatingSourceResult,
  point_m: tuple[float, float],
  *,
  tolerance_m: float,
) -> float:
  """Return static pressure for the shock-fit API's dimensional contract."""

  pressure = source_band.static_pressure_at(
    point_m,
    position_tolerance_m=tolerance_m,
  )
  if pressure is None:
    raise ValueError(
      'solver-owned upstream source band does not provide static pressure '
      'at the proposed shock point'
    )
  ####
  pressure_value = float(pressure)
  if not isfinite(pressure_value) or pressure_value <= 0.0:
    raise ValueError(
      'solver-owned upstream source band returned a nonphysical static pressure'
    )
  ####
  return pressure_value


def _source_lineage(
  source_band: MocReflectedDomainAlternatingSourceResult,
  shock: MocEulerShockBoundaryCurveResult,
  request: MocEulerTwoSidedInterfaceLawRequest,
) -> bool:
  for point, state, pressure in zip(
    shock.shock_points_m,
    shock.upstream_states,
    shock.upstream_total_pressure_Pa,
    strict=True,
  ):
    try:
      sampled_state, sampled_pressure = _source_sample(
        source_band,
        point,
        tolerance_m=request.position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      return False
    ####
    if max(
      abs(sampled_state.x_m - state.x_m),
      abs(sampled_state.y_m - state.y_m),
      abs(sampled_state.theta_rad - state.theta_rad),
      abs(sampled_state.mach - state.mach),
      abs(sampled_state.gamma - state.gamma),
    ) > request.source_state_tolerance:
      return False
    ####
    if abs(sampled_pressure - pressure) > request.source_pressure_tolerance * max(
      1.0,
      abs(sampled_pressure),
      abs(pressure),
    ):
      return False
    ####
  ####
  return True


def _front_limit_state_compatible(
  upstream_state: Any,
  upstream_pressure: float,
  downstream_state: Any,
  downstream_pressure: float,
  request: MocEulerTwoSidedInterfaceLawRequest,
) -> bool:
  return bool(
    max(
      abs(float(upstream_state.theta_rad) - float(downstream_state.theta_rad)),
      abs(float(upstream_state.mach) - float(downstream_state.mach)),
      abs(float(upstream_state.gamma) - float(downstream_state.gamma)),
    )
    <= request.source_state_tolerance
    and abs(upstream_pressure - downstream_pressure)
    <= request.source_pressure_tolerance
    * max(1.0, abs(upstream_pressure), abs(downstream_pressure))
  )


def _probe_downstream_field(
  field: MocPhysicalPostShockFieldResult,
  point_m: tuple[float, float],
  index: int,
  shock_points: tuple[tuple[float, float], ...],
  request: MocEulerTwoSidedInterfaceLawRequest,
) -> _DownstreamProbe:
  if index == len(shock_points) - 1:
    edge_start, edge_end = shock_points[index - 1], shock_points[index]
    normal_start, normal_end = edge_start, edge_end
  elif index == 0:
    edge_start, edge_end = shock_points[index], shock_points[index + 1]
    normal_start, normal_end = edge_start, edge_end
  else:
    edge_start, edge_end = shock_points[index], shock_points[index + 1]
    # The exact shock solver uses a centered tangent for interior samples.
    # Keep the forward edge for cell ownership, but use the same centered
    # front normal for the conservative response channels.
    normal_start, normal_end = shock_points[index - 1], shock_points[index + 1]
  ####
  edge_midpoint = (
    0.5 * (edge_start[0] + edge_end[0]),
    0.5 * (edge_start[1] + edge_end[1]),
  )
  tangent_x = normal_end[0] - normal_start[0]
  tangent_y = normal_end[1] - normal_start[1]
  tangent_length = hypot(tangent_x, tangent_y)
  if tangent_length <= request.position_tolerance_m:
    raise ValueError('shock probe edge has no positive length')
  ####
  normal_x = -tangent_y / tangent_length
  normal_y = tangent_x / tangent_length
  cell_candidates: list[tuple[tuple[float, float], ...]] = []
  for vertices, _states, _pressures in field.cell_state_samples(
    position_tolerance_m=request.position_tolerance_m,
  ):
    if (
      any(_point_matches(vertex, edge_start, request.position_tolerance_m) for vertex in vertices)
      and any(_point_matches(vertex, edge_end, request.position_tolerance_m) for vertex in vertices)
    ):
      cell_candidates.append(vertices)
  ####
  if len(cell_candidates) != 1:
    raise ValueError(
      'shock probe requires exactly one retained downstream cell at each '
      f'shock edge; found {len(cell_candidates)} at sample {index}'
    )
  ####
  centroid = _cell_centroid(cell_candidates[0])
  toward_downstream = (
    centroid[0] - edge_midpoint[0],
    centroid[1] - edge_midpoint[1],
  )
  if toward_downstream[0] * normal_x + toward_downstream[1] * normal_y < 0.0:
    normal_x = -normal_x
    normal_y = -normal_y
  ####
  probe_fraction = request.downstream_probe_fraction
  if probe_fraction == 0.0:
    if (
      len(field.post_shock_boundary_states) != len(shock_points)
      or len(field.post_shock_boundary_total_pressure_Pa) != len(shock_points)
    ):
      raise ValueError(
        'exact front-limit response requires retained post-shock boundary '
        'state and pressure samples'
      )
    probe_point = point_m
    state = field.post_shock_boundary_states[index]
    pressure = field.post_shock_boundary_total_pressure_Pa[index]
  else:
    probe_point = (
      point_m[0] + probe_fraction * (centroid[0] - point_m[0]),
      point_m[1] + probe_fraction * (centroid[1] - point_m[1]),
    )
    state = field.state_at(
      probe_point,
      position_tolerance_m=max(1.0e-10, request.position_tolerance_m * 0.1),
    )
    pressure = field.total_pressure_at(
      probe_point,
      position_tolerance_m=max(1.0e-10, request.position_tolerance_m * 0.1),
    )
  if state is None or pressure is None:
    raise ValueError(
      f'downstream physical field does not sample the shock probe at {index}'
    )
  ####
  pressure_value = float(pressure)
  if not isfinite(pressure_value) or pressure_value <= 0.0:
    raise ValueError('downstream shock probe returned a nonphysical pressure')
  ####
  return _DownstreamProbe(
    point_m=point_m,
    probe_point_m=probe_point,
    normal_x=normal_x,
    normal_y=normal_y,
    state=state,
    total_pressure_Pa=pressure_value,
  )


def build_solver_owned_euler_two_sided_interface_response(
  current_field_iteration: MocEulerTwoSidedFieldIterationResult,
  request: MocEulerTwoSidedInterfaceLawRequest,
  *,
  iteration_index: int = 0,
) -> MocEulerTwoSidedInterfaceLawResult:
  """Build one conservative moving-front response from a retained field.

  The response uses the exact source band for the proposed geometry and the
  current downstream cell field for the normal-speed equation.  It does not
  call a pressure controller or infer a field where a probe is unavailable.
  """

  if not isinstance(
    current_field_iteration,
    MocEulerTwoSidedFieldIterationResult,
  ):
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.INVALID_INPUT,
      'current_field_iteration must be a MocEulerTwoSidedFieldIterationResult',
      request=request if isinstance(request, MocEulerTwoSidedInterfaceLawRequest) else None,
    )
  ####
  if not isinstance(request, MocEulerTwoSidedInterfaceLawRequest):
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.INVALID_INPUT,
      'request must be a MocEulerTwoSidedInterfaceLawRequest',
      current_field_iteration=current_field_iteration,
    )
  ####
  if (
    isinstance(iteration_index, bool)
    or not isinstance(iteration_index, int)
    or iteration_index < 0
  ):
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.INVALID_INPUT,
      'iteration_index must be a nonnegative integer',
      request=request,
      current_field_iteration=current_field_iteration,
    )
  ####
  shock = current_field_iteration.shock_boundary
  physical = current_field_iteration.final_physical_field
  field = None if physical is None else physical.field
  if (
    not current_field_iteration.field_iteration_verified
    or shock is None
    or physical is None
    or not physical.physical_field_verified
    or field is None
  ):
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.DOWNSTREAM_FIELD_REQUIRED,
      'moving-interface response requires a verified exact two-sided field and '
      'a bounded downstream physical mesh; no geometry update was attempted',
      request=request,
      current_field_iteration=current_field_iteration,
    )
  ####
  if not request.source_band.source_field_verified:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.SOURCE_FIELD_REQUIRED,
      'moving-interface response requires a verified upstream source band',
      request=request,
      current_field_iteration=current_field_iteration,
    )
  ####
  source_lineage_verified = _source_lineage(
    request.source_band,
    shock,
    request,
  )
  if not source_lineage_verified:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.SOURCE_LINEAGE_FAILURE,
      'upstream source band does not reproduce the exact current shock state '
      'and total-pressure lineage; no front update was attempted',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=False,
    )
  ####
  probes: list[_DownstreamProbe] = []
  try:
    for index, point in enumerate(shock.shock_points_m):
      probes.append(
        _probe_downstream_field(
          field,
          point,
          index,
          tuple(shock.shock_points_m),
          request,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.DOWNSTREAM_PROBE_FAILURE,
      f'downstream field probe failed: {error}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
    )
  ####
  next_points: list[tuple[float, float]] = []
  speeds: list[float] = []
  mass_residuals: list[float] = []
  momentum_residuals: list[float] = []
  energy_residuals: list[float] = []
  try:
    for index, (point, probe) in enumerate(zip(shock.shock_points_m, probes, strict=True)):
      upstream_state, upstream_pressure = _source_sample(
        request.source_band,
        point,
        tolerance_m=request.position_tolerance_m,
      )
      upstream = _primitive(
        upstream_state,
        upstream_pressure,
        reference_total_temperature_K=request.reference_total_temperature_K,
        gas_constant_J_kgK=request.gas_constant_J_kgK,
      )
      downstream = _primitive(
        probe.state,
        probe.total_pressure_Pa,
        reference_total_temperature_K=request.reference_total_temperature_K,
        gas_constant_J_kgK=request.gas_constant_J_kgK,
      )
      upstream_density, upstream_u, upstream_v, upstream_pressure_static, upstream_h = upstream
      downstream_density, downstream_u, downstream_v, downstream_pressure_static, downstream_h = downstream
      upstream_normal_velocity = (
        upstream_u * probe.normal_x + upstream_v * probe.normal_y
      )
      downstream_normal_velocity = (
        downstream_u * probe.normal_x + downstream_v * probe.normal_y
      )
      density_jump = downstream_density - upstream_density
      if abs(density_jump) <= 1.0e-12 * max(upstream_density, downstream_density, 1.0):
        if (
          request.downstream_probe_fraction != 0.0
          or not _front_limit_state_compatible(
            upstream_state,
            upstream_pressure,
            probe.state,
            probe.total_pressure_Pa,
            request,
          )
        ):
          raise ValueError(f'shock density jump is too small at sample {index}')
        speed = 0.0
      else:
        speed = (
          downstream_density * downstream_normal_velocity
          - upstream_density * upstream_normal_velocity
        ) / density_jump
      if not isfinite(speed):
        raise ValueError(f'interface normal speed is non-finite at sample {index}')
      ####
      upstream_relative_velocity = upstream_normal_velocity - speed
      downstream_relative_velocity = downstream_normal_velocity - speed
      mass_residuals.append(
        abs(
          downstream_density * downstream_relative_velocity
          - upstream_density * upstream_relative_velocity
        )
      )
      momentum_residuals.append(
        abs(
          downstream_density * downstream_relative_velocity**2
          + downstream_pressure_static
          - upstream_density * upstream_relative_velocity**2
          - upstream_pressure_static
        )
      )
      energy_residuals.append(
        abs(
          downstream_h * downstream_relative_velocity
          - upstream_h * upstream_relative_velocity
        )
      )
      ####
      speeds.append(speed)
      if index < request.anchor_endpoint_samples or index >= len(probes) - request.anchor_endpoint_samples:
        displacement = 0.0
      else:
        displacement = request.relaxation * speed * request.pseudo_time_step_s
        displacement = max(
          -request.maximum_normal_displacement_m,
          min(request.maximum_normal_displacement_m, displacement),
        )
      next_points.append(
        (
          point[0] + displacement * probe.normal_x,
          point[1] + displacement * probe.normal_y,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.DOWNSTREAM_PROBE_FAILURE,
      f'Rankine--Hugoniot front-speed response failed: {error}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
    )
  ####
  points = tuple(next_points)
  geometry_valid = bool(
    len(points) >= 3
    and all(
      second[0] > first[0] + request.position_tolerance_m
      and second[1] <= first[1] + request.position_tolerance_m
      for first, second in zip(points, points[1:])
    )
    and points[-1][1] >= (
      current_field_iteration.request.target_centerline_y_m
      if current_field_iteration.request is not None
      else 0.0
    ) - request.position_tolerance_m
  )
  if not geometry_valid:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.GEOMETRY_FAILURE,
      'Rankine--Hugoniot response produced a non-monotone or centerline-crossing '
      'shock geometry; no extrapolation or endpoint correction was attempted',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  try:
    next_upstream_states = []
    next_upstream_pressures = []
    for point in points:
      state, _total_pressure = _source_sample(
        request.source_band,
        point,
        tolerance_m=request.position_tolerance_m,
      )
      next_upstream_states.append(state)
      next_upstream_pressures.append(
        _source_static_pressure(
          request.source_band,
          point,
          tolerance_m=request.position_tolerance_m,
        )
      )
    ####
    next_shock = fit_euler_consistent_shock_boundary_from_geometry(
      tuple(next_upstream_states),
      tuple(next_upstream_pressures),
      points,
      branch=request.branch,
      position_tolerance_m=request.position_tolerance_m,
      residual_tolerance=request.residual_tolerance,
      allow_zero_strength_endpoints=shock.zero_strength_endpoints_allowed,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.SHOCK_FIT_FAILURE,
      f'next exact shock refit raised: {error}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  if not next_shock.converged or not next_shock.local_euler_verified:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.SHOCK_FIT_FAILURE,
      'next geometry did not produce a locally Euler-verified exact shock '
      f'boundary: {next_shock.message}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      candidate_geometry_verified=False,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  ambient_pressure = request.source_band.ambient_pressure_Pa
  assert ambient_pressure is not None
  try:
    companion_boundary = solve_euler_ambient_companion_boundary_reference(
      next_shock,
      ambient_pressure,
      separation_m=request.companion_separation_m,
      seed_flow_angle_rad=request.companion_seed_flow_angle_rad,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.source_pressure_tolerance,
      pressure_tolerance=request.source_pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.COMPANION_BOUNDARY_FAILURE,
      f'next companion boundary reference raised: {error}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      candidate_geometry_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  if not companion_boundary.converged:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.COMPANION_BOUNDARY_FAILURE,
      'next solver-owned companion boundary did not converge: '
      f'{companion_boundary.message}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      candidate_geometry_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  try:
    next_companion = assemble_euler_consistent_companion_characteristic_strip(
      next_shock,
      companion_boundary.samples,
      position_tolerance_m=request.position_tolerance_m,
      invariant_tolerance=request.source_pressure_tolerance,
      pressure_tolerance=request.source_pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.COMPANION_FIELD_FAILURE,
      f'next companion characteristic strip raised: {error}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      candidate_geometry_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  if not next_companion.converged or not next_companion.state_sampling_available:
    return _failure(
      MocEulerTwoSidedInterfaceLawStatus.COMPANION_FIELD_FAILURE,
      'next solver-owned companion strip did not provide a verified state '
      f'handoff: {next_companion.message}',
      request=request,
      current_field_iteration=current_field_iteration,
      source_lineage_verified=True,
      downstream_probe_verified=True,
      candidate_geometry_verified=True,
      probe_points_m=tuple(probe.probe_point_m for probe in probes),
      probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
      interface_normal_speeds_m_s=tuple(speeds),
      downstream_probe_states=tuple(probe.state for probe in probes),
      downstream_probe_total_pressure_Pa=tuple(
        probe.total_pressure_Pa for probe in probes
      ),
      endpoint_constraints_applied=True,
    )
  ####
  displacement = compute_moc_euler_two_sided_interface_normal_displacements(
    shock,
    next_shock,
  )
  motion_verified = any(
    abs(value) > request.position_tolerance_m for value in displacement
  )
  stationary_equilibrium_candidate = bool(
    request.downstream_probe_fraction == 0.0 and not motion_verified
  )
  response = MocEulerTwoSidedInterfaceResponse(
    prior_shock_boundary=shock,
    next_shock_boundary=next_shock,
    next_companion_field=next_companion,
    normal_displacements_m=displacement,
    mass_flux_residuals_kg_m2_s=tuple(mass_residuals),
    normal_momentum_residuals_Pa=tuple(momentum_residuals),
    energy_flux_residuals_W_m2=tuple(energy_residuals),
    response_source=MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID,
    law_id=MOC_EULER_TWO_SIDED_INTERFACE_LAW_ID,
    stationary_equilibrium_candidate=stationary_equilibrium_candidate,
  )
  result_status = (
    MocEulerTwoSidedInterfaceLawStatus.RESPONSE_READY
    if motion_verified or stationary_equilibrium_candidate
    else MocEulerTwoSidedInterfaceLawStatus.NO_INTERFACE_MOTION
  )
  return MocEulerTwoSidedInterfaceLawResult(
    status=result_status,
    request=request,
    current_field_iteration=current_field_iteration,
    response=response,
    probe_points_m=tuple(probe.probe_point_m for probe in probes),
    probe_normals=tuple((probe.normal_x, probe.normal_y) for probe in probes),
    interface_normal_speeds_m_s=tuple(speeds),
    downstream_probe_states=tuple(probe.state for probe in probes),
    downstream_probe_total_pressure_Pa=tuple(
      probe.total_pressure_Pa for probe in probes
    ),
    source_lineage_verified=True,
    downstream_probe_verified=True,
    candidate_geometry_verified=True,
    companion_field_verified=True,
    endpoint_constraints_applied=True,
    interface_motion_verified=motion_verified,
    stationary_equilibrium_candidate=stationary_equilibrium_candidate,
    message=(
      'solver-owned Rankine--Hugoniot front response built from the retained '
      'upstream source band and downstream physical cell probes; the regenerated '
      'companion field remains research-only and must be consumed by an exact '
      'field re-solve'
    ),
  )


def make_solver_owned_euler_two_sided_interface_advance(
  request: MocEulerTwoSidedInterfaceLawRequest,
) -> Callable[[MocEulerTwoSidedFieldIterationResult, int], MocEulerTwoSidedInterfaceResponse]:
  """Return the concrete advance callback consumed by the moving driver."""

  if not isinstance(request, MocEulerTwoSidedInterfaceLawRequest):
    raise TypeError('request must be a MocEulerTwoSidedInterfaceLawRequest')
  ####

  def advance(
    current: MocEulerTwoSidedFieldIterationResult,
    iteration_index: int,
  ) -> MocEulerTwoSidedInterfaceResponse:
    result = build_solver_owned_euler_two_sided_interface_response(
      current,
      request,
      iteration_index=iteration_index,
    )
    if result.response is None:
      raise ValueError(f'{result.status.value}: {result.message}')
    ####
    return result.response
  ####

  return advance


def solve_euler_two_sided_moving_interface_with_solver_owned_law(
  moving_request: MocEulerTwoSidedMovingInterfaceRequest,
  law_request: MocEulerTwoSidedInterfaceLawRequest,
) -> MocEulerTwoSidedMovingInterfaceResult:
  """Run the bounded moving-interface driver with the concrete front law."""

  if not isinstance(
    moving_request,
    MocEulerTwoSidedMovingInterfaceRequest,
  ):
    raise TypeError(
      'moving_request must be a MocEulerTwoSidedMovingInterfaceRequest'
    )
  ####
  advance = make_solver_owned_euler_two_sided_interface_advance(law_request)
  return solve_euler_two_sided_moving_interface(
    moving_request,
    advance_interface=advance,
  )
