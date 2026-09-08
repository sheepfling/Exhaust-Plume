"""Independent audit for front-aligned physical-field reconciliation.

The model-side reconciliation solver retains a conservative result on a fixed
shock/ambient/centerline mesh.  This validator rebuilds the edge topology,
thermodynamic states, conservative face fluxes, shock Rankine--Hugoniot
residuals, and material-boundary diagnostics from the retained raw result.  A
passing audit is local evidence only; the shock placement, refinement ladder,
external validation, and product claim gates remain separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, isfinite, sin, sqrt
from typing import Any

import numpy as np

from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
  MocPhysicalFieldEulerReconciliationResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState

__all__ = (
  'MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_AUDIT_OPERATOR_ID',
  'MocPhysicalFieldEulerReconciliationAuditStatus',
  'MocPhysicalFieldEulerReconciliationAudit',
  'measure_moc_physical_field_euler_reconciliation',
)


MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_AUDIT_OPERATOR_ID = (
  'op.moc.physical-field-euler-reconciliation-audit'
)
_CHANNEL_NAMES = (
  'mass',
  'streamwise_momentum',
  'transverse_momentum',
  'energy',
  'euler',
)


class MocPhysicalFieldEulerReconciliationAuditStatus(str, Enum):
  """Outcome of the independent fixed-front reconciliation audit."""

  VERIFIED = 'verified-local-physical-field-euler-reconciliation'
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'reconciliation-audit-source-failure'
  GEOMETRY_FAILURE = 'reconciliation-audit-geometry-failure'
  STATE_FAILURE = 'reconciliation-audit-state-failure'
  RESIDUAL_FAILURE = 'reconciliation-audit-residual-failure'
  SHOCK_JUMP_FAILURE = 'reconciliation-audit-shock-jump-failure'
  BOUNDARY_FAILURE = 'reconciliation-audit-boundary-failure'
  FLAG_FAILURE = 'reconciliation-audit-promotion-flag-failure'
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationAudit:
  """Recomputed evidence for one fixed-front conservative candidate."""

  status: MocPhysicalFieldEulerReconciliationAuditStatus
  candidate: MocPhysicalFieldEulerReconciliationResult | None
  operator_id: str = MOC_PHYSICAL_FIELD_EULER_RECONCILIATION_AUDIT_OPERATOR_ID
  cell_count: int = 0
  expected_cell_count: int = 0
  maximum_conservative_euler_residual: float | None = None
  maximum_shock_jump_residual: float | None = None
  maximum_ambient_pressure_residual_Pa: float | None = None
  maximum_ambient_normal_velocity_residual_m_s: float | None = None
  maximum_centerline_normal_velocity_residual_m_s: float | None = None
  ambient_pressure_target_coverage_verified: bool = False
  ambient_pressure_target_consumption_verified: bool = False
  ambient_pressure_target_residual_report_verified: bool = False
  geometry_verified: bool = False
  source_lineage_verified: bool = False
  state_samples_verified: bool = False
  residual_channels_recomputed: bool = False
  residual_report_verified: bool = False
  shock_front_verified: bool = False
  ambient_boundary_verified: bool = False
  centerline_boundary_verified: bool = False
  promotion_flags_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldEulerReconciliationAuditStatus,
    ):
      raise TypeError(
        'status must be a MocPhysicalFieldEulerReconciliationAuditStatus'
      )
    ####
    if self.candidate is not None and not isinstance(
      self.candidate,
      MocPhysicalFieldEulerReconciliationResult,
    ):
      raise TypeError(
        'candidate must be a MocPhysicalFieldEulerReconciliationResult or None'
      )
    ####
    for name in (
      'cell_count',
      'expected_cell_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    for name in (
      'maximum_conservative_euler_residual',
      'maximum_shock_jump_residual',
      'maximum_ambient_pressure_residual_Pa',
      'maximum_ambient_normal_velocity_residual_m_s',
      'maximum_centerline_normal_velocity_residual_m_s',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'geometry_verified',
      'source_lineage_verified',
      'state_samples_verified',
      'residual_channels_recomputed',
      'residual_report_verified',
      'shock_front_verified',
      'ambient_boundary_verified',
      'centerline_boundary_verified',
      'ambient_pressure_target_coverage_verified',
      'ambient_pressure_target_consumption_verified',
      'ambient_pressure_target_residual_report_verified',
      'promotion_flags_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.production_claim_allowed:
      raise ValueError('reconciliation audit cannot allow production claims')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('reconciliation audit must retain its promotion block')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocPhysicalFieldEulerReconciliationAuditStatus.VERIFIED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'cell_count': self.cell_count,
      'expected_cell_count': self.expected_cell_count,
      'maximum_conservative_euler_residual': (
        self.maximum_conservative_euler_residual
      ),
      'maximum_shock_jump_residual': self.maximum_shock_jump_residual,
      'maximum_ambient_pressure_residual_Pa': (
        self.maximum_ambient_pressure_residual_Pa
      ),
      'maximum_ambient_normal_velocity_residual_m_s': (
        self.maximum_ambient_normal_velocity_residual_m_s
      ),
      'maximum_centerline_normal_velocity_residual_m_s': (
        self.maximum_centerline_normal_velocity_residual_m_s
      ),
      'ambient_pressure_target_coverage_verified': (
        self.ambient_pressure_target_coverage_verified
      ),
      'ambient_pressure_target_consumption_verified': (
        self.ambient_pressure_target_consumption_verified
      ),
      'ambient_pressure_target_residual_report_verified': (
        self.ambient_pressure_target_residual_report_verified
      ),
      'geometry_verified': self.geometry_verified,
      'source_lineage_verified': self.source_lineage_verified,
      'state_samples_verified': self.state_samples_verified,
      'residual_channels_recomputed': self.residual_channels_recomputed,
      'residual_report_verified': self.residual_report_verified,
      'shock_front_verified': self.shock_front_verified,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'promotion_flags_verified': self.promotion_flags_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'message': self.message,
      'claim_status': (
        'independent-local-reconciliation-audit; canonical placement, '
        'refinement, external validation, and production gates remain open'
      ),
    }
  ####
####


def _failure(
  status: MocPhysicalFieldEulerReconciliationAuditStatus,
  candidate: MocPhysicalFieldEulerReconciliationResult | None,
  *,
  cell_count: int = 0,
  expected_cell_count: int = 0,
  message: str,
) -> MocPhysicalFieldEulerReconciliationAudit:
  return MocPhysicalFieldEulerReconciliationAudit(
    status=status,
    candidate=candidate,
    cell_count=cell_count,
    expected_cell_count=expected_cell_count,
    message=message,
  )
####


def _point_key(
  point: tuple[float, float],
  tolerance_m: float,
) -> tuple[int, int]:
  return round(point[0] / tolerance_m), round(point[1] / tolerance_m)
####


def _edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _point_key(first, tolerance_m)
  second_key = _point_key(second, tolerance_m)
  return (
    (first_key, second_key)
    if first_key <= second_key
    else (second_key, first_key)
  )
####


def _signed_area(vertices: tuple[tuple[float, float], ...]) -> float:
  return 0.5 * sum(
    vertices[index][0] * vertices[(index + 1) % len(vertices)][1]
    - vertices[(index + 1) % len(vertices)][0] * vertices[index][1]
    for index in range(len(vertices))
  )
####


def _normal(
  first: tuple[float, float],
  second: tuple[float, float],
  signed_area: float,
) -> tuple[float, float, float]:
  delta_x = second[0] - first[0]
  delta_y = second[1] - first[1]
  length = float(np.hypot(delta_x, delta_y))
  if not isfinite(length) or length <= 0.0:
    raise ValueError('audit found a zero-length edge')
  ####
  if signed_area > 0.0:
    return delta_y / length, -delta_x / length, length
  ####
  return -delta_y / length, delta_x / length, length
####


def _primitive(
  state: np.ndarray,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[float, float, float, float, float]:
  density = float(state[0])
  if not isfinite(density) or density <= 0.0:
    raise FloatingPointError('audit density is not positive')
  ####
  velocity_u = float(state[1]) / density
  velocity_v = float(state[2]) / density
  pressure = (gamma - 1.0) * (
    float(state[3])
    - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise FloatingPointError('audit pressure is not positive')
  ####
  sound_speed = sqrt(gamma * pressure / density)
  return density, velocity_u, velocity_v, pressure, sound_speed
####


def _conservative_from_characteristic(
  state: CharacteristicState,
  total_pressure_Pa: float,
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  gamma = state.gamma
  factor = 1.0 + 0.5 * (gamma - 1.0) * state.mach * state.mach
  pressure = total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
  temperature = total_temperature_K / factor
  density = pressure / (gas_constant_J_kgK * temperature)
  sound_speed = sqrt(gamma * gas_constant_J_kgK * temperature)
  speed = state.mach * sound_speed
  return np.array(
    (
      density,
      density * speed * cos(state.theta_rad),
      density * speed * sin(state.theta_rad),
      pressure / (gamma - 1.0) + 0.5 * density * speed * speed,
    ),
    dtype=float,
  )
####


def _flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float]:
  density, velocity_u, velocity_v, pressure, sound_speed = _primitive(
    state,
    gamma,
    gas_constant_J_kgK,
  )
  normal_velocity = velocity_u * normal_x + velocity_v * normal_y
  return (
    np.array(
      (
        density * normal_velocity,
        density * velocity_u * normal_velocity + pressure * normal_x,
        density * velocity_v * normal_velocity + pressure * normal_y,
        (state[3] + pressure) * normal_velocity,
      ),
      dtype=float,
    ),
    abs(normal_velocity) + sound_speed,
  )
####


def _rusanov(
  left: np.ndarray,
  right: np.ndarray,
  normal_x: float,
  normal_y: float,
  length_m: float,
  gamma: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  left_flux, left_wave = _flux(
    left,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  right_flux, right_wave = _flux(
    right,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  return (
    0.5 * (left_flux + right_flux)
    - 0.5 * max(left_wave, right_wave) * (right - left)
  ) * length_m
####


def _interpolate_state(
  points: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  index: int,
  point: tuple[float, float],
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float]:
  first = points[index]
  second = points[index + 1]
  delta_x = second[0] - first[0]
  delta_y = second[1] - first[1]
  denominator = delta_x * delta_x + delta_y * delta_y
  fraction = 0.0
  if denominator > 0.0:
    fraction = (
      (point[0] - first[0]) * delta_x
      + (point[1] - first[1]) * delta_y
    ) / denominator
  ####
  fraction = float(np.clip(fraction, 0.0, 1.0))
  first_state = states[index]
  second_state = states[index + 1]
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=first_state.theta_rad + fraction * (
      second_state.theta_rad - first_state.theta_rad
    ),
    mach=first_state.mach + fraction * (second_state.mach - first_state.mach),
    gamma=first_state.gamma + fraction * (second_state.gamma - first_state.gamma),
  )
  pressure = pressures[index] + fraction * (pressures[index + 1] - pressures[index])
  return (
    _conservative_from_characteristic(
      state,
      pressure,
      total_temperature_K,
      gas_constant_J_kgK,
    ),
    pressure,
  )
####


def _target_pressure_at_x(
  target: MocPhysicalFieldEulerBoundaryPressureTarget | None,
  x_m: float,
  *,
  position_tolerance_m: float,
  fallback_pressure_Pa: float,
) -> float:
  if target is None:
    return float(fallback_pressure_Pa)
  ####
  pressure = target.pressure_at_x(
    x_m,
    position_tolerance_m=position_tolerance_m,
  )
  if pressure is None:
    raise ValueError(
      'independent audit target does not cover an ambient-face midpoint'
    )
  ####
  return float(pressure)
####


def _path_map(
  condition: Any,
  tolerance_m: float,
) -> dict[tuple[tuple[int, int], tuple[int, int]], tuple[str, int]]:
  paths = {
    'shock': tuple(condition.shock_front_points_m),
    'ambient': tuple(condition.ambient_neighbor_points_m),
    'centerline': tuple(condition.centerline_neighbor_points_m),
  }
  output: dict[tuple[tuple[int, int], tuple[int, int]], tuple[str, int]] = {}
  for kind, points in paths.items():
    for index, (first, second) in enumerate(zip(points, points[1:])):
      key = _edge_key(first, second, tolerance_m)
      if key in output:
        raise ValueError('audit boundary paths share an edge')
      ####
      output[key] = (kind, index)
    ####
  ####
  return output
####


def _normalised_residuals(
  states: np.ndarray,
  raw_residual: np.ndarray,
  polygons: tuple[tuple[tuple[float, float], ...], ...],
  gamma: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  output = np.empty((len(polygons), 5), dtype=float)
  for index, polygon in enumerate(polygons):
    density, velocity_u, velocity_v, pressure, sound_speed = _primitive(
      states[index],
      gamma,
      gas_constant_J_kgK,
    )
    perimeter = sum(
      float(
        np.hypot(
          polygon[(edge_index + 1) % len(polygon)][0] - polygon[edge_index][0],
          polygon[(edge_index + 1) % len(polygon)][1] - polygon[edge_index][1],
        )
      )
      for edge_index in range(len(polygon))
    )
    mass_scale = max(density * sound_speed * perimeter, 1.0e-12)
    momentum_scale = max(
      (density * (velocity_u * velocity_u + velocity_v * velocity_v) + pressure)
      * perimeter,
      1.0e-12,
    )
    energy_scale = max(
      (states[index, 3] + pressure) * sound_speed * perimeter,
      1.0e-12,
    )
    output[index, :4] = (
      abs(raw_residual[index, 0]) / mass_scale,
      abs(raw_residual[index, 1]) / momentum_scale,
      abs(raw_residual[index, 2]) / momentum_scale,
      abs(raw_residual[index, 3]) / energy_scale,
    )
    output[index, 4] = float(np.max(output[index, :4]))
  ####
  return output
####


def measure_moc_physical_field_euler_reconciliation(
  candidate: MocPhysicalFieldEulerReconciliationResult,
  *,
  residual_tolerance: float = 1.0e-8,
) -> MocPhysicalFieldEulerReconciliationAudit:
  """Recompute fixed-front residuals and boundary evidence independently."""

  if not isinstance(
    candidate,
    MocPhysicalFieldEulerReconciliationResult,
  ):
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.INVALID_INPUT,
      None,
      message=(
        'candidate must be a MocPhysicalFieldEulerReconciliationResult'
      ),
    )
  ####
  try:
    tolerance = float(residual_tolerance)
  except (TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.INVALID_INPUT,
      candidate,
      message=f'residual_tolerance must be numeric: {error}',
    )
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.INVALID_INPUT,
      candidate,
      message='residual_tolerance must be finite and positive',
    )
  ####
  request = candidate.request
  condition = candidate.shock_front_condition
  if request is None or condition is None or condition.field is None:
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.SOURCE_FAILURE,
      candidate,
      message='candidate retained no complete request/source condition',
    )
  ####
  source_field = condition.field
  expected_cells = tuple(source_field.cells)
  polygons = candidate.cell_vertices_by_cell_m
  states = np.asarray(candidate.conservative_states_by_cell, dtype=float)
  if len(polygons) != len(expected_cells) or len(states) != len(polygons):
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.GEOMETRY_FAILURE,
      candidate,
      cell_count=len(polygons),
      expected_cell_count=len(expected_cells),
      message='candidate cell count does not match the retained source field',
    )
  ####
  source_lineage_verified = bool(
    candidate.shock_front_condition is request.shock_front_condition
    and all(
      tuple(tuple(point) for point in polygon)
      == tuple(tuple(point) for point in source_cell.vertices_xr_m)
      for polygon, source_cell in zip(polygons, expected_cells, strict=True)
    )
  )
  if not source_lineage_verified:
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.SOURCE_FAILURE,
      candidate,
      cell_count=len(polygons),
      expected_cell_count=len(expected_cells),
      message='candidate geometry or source-condition identity changed',
    )
  ####
  try:
    path_map = _path_map(condition, request.position_tolerance_m)
    edge_entries: dict[
      tuple[tuple[int, int], tuple[int, int]],
      list[tuple[int, int, tuple[float, float], tuple[float, float]]],
    ] = {}
    for cell_index, polygon in enumerate(polygons):
      if len(polygon) not in (3, 4):
        raise ValueError('candidate polygon is not triangular or quadrilateral')
      ####
      for edge_index, (first, second) in enumerate(
        zip(polygon, (*polygon[1:], polygon[0]))
      ):
        key = _edge_key(first, second, request.position_tolerance_m)
        edge_entries.setdefault(key, []).append(
          (cell_index, edge_index, first, second)
        )
      ####
    ####
    for path_key in path_map:
      if path_key not in edge_entries or len(edge_entries[path_key]) != 1:
        raise ValueError('candidate does not retain every source boundary edge')
      ####
    ####
    boundary_entries = {
      key: entries[0]
      for key, entries in edge_entries.items()
      if len(entries) == 1
    }
    terminal_entries = {
      key: entries
      for key, entries in boundary_entries.items()
      if key not in path_map
    }
    ambient_end = tuple(condition.ambient_neighbor_points_m)[-1]
    centerline_end = tuple(condition.centerline_neighbor_points_m)[-1]
    endpoint_tolerance = max(10.0 * request.position_tolerance_m, 1.0e-7)
    for _key, (_cell, _edge, first, second) in terminal_entries.items():
      if not all(
        min(
          np.hypot(point[0] - ambient_end[0], point[1] - ambient_end[1]),
          np.hypot(point[0] - centerline_end[0], point[1] - centerline_end[1]),
        )
        <= endpoint_tolerance
        for point in (first, second)
      ):
        raise ValueError('candidate retained an unknown boundary edge')
      ####
    ####
  except (ArithmeticError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.GEOMETRY_FAILURE,
      candidate,
      cell_count=len(polygons),
      expected_cell_count=len(expected_cells),
      message=f'independent boundary geometry audit failed: {error}',
    )
  ####
  try:
    gamma = float(source_field.post_shock_boundary_states[0].gamma)
    if states.shape != (len(polygons), 4):
      raise ValueError('candidate state shape does not match cell count')
    ####
    for state in states:
      _primitive(state, gamma, request.gas_constant_J_kgK)
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError, IndexError) as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.STATE_FAILURE,
      candidate,
      cell_count=len(polygons),
      expected_cell_count=len(expected_cells),
      message=f'independent thermodynamic audit failed: {error}',
    )
  ####
  raw_residual = np.zeros_like(states)
  shock_jumps: list[float] = []
  ambient_pressures: list[float] = []
  ambient_normals: list[float] = []
  centerline_normals: list[float] = []
  upstream_states = tuple(source_field.upstream_shock_boundary_states)
  upstream_pressures = tuple(source_field.upstream_shock_boundary_total_pressure_Pa)
  post_states = tuple(source_field.post_shock_boundary_states)
  post_pressures = tuple(source_field.post_shock_boundary_total_pressure_Pa)
  shock_points = tuple(condition.shock_front_points_m)
  ambient_points = tuple(condition.ambient_neighbor_points_m)
  centerline_points = tuple(condition.centerline_neighbor_points_m)
  ambient_pressure = source_field.ambient_boundary.ambient_pressure_Pa
  if (
    ambient_pressure is None
    or len(upstream_states) != len(shock_points)
    or len(post_states) != len(shock_points)
  ):
    return _failure(
      MocPhysicalFieldEulerReconciliationAuditStatus.SOURCE_FAILURE,
      candidate,
      cell_count=len(polygons),
      expected_cell_count=len(expected_cells),
      message='source boundary states do not cover the audited paths',
    )
  ####
  for key, entries in edge_entries.items():
    if len(entries) == 2:
      first_entry, second_entry = entries
      for current, neighbor in ((first_entry, second_entry), (second_entry, first_entry)):
        cell_index, _edge_index, first, second = current
        signed_area = _signed_area(polygons[cell_index])
        normal_x, normal_y, length = _normal(first, second, signed_area)
        raw_residual[cell_index] += _rusanov(
          states[cell_index],
          states[neighbor[0]],
          normal_x,
          normal_y,
          length,
          gamma,
          request.gas_constant_J_kgK,
        )
      ####
      continue
    ####
    cell_index, _edge_index, first, second = entries[0]
    signed_area = _signed_area(polygons[cell_index])
    normal_x, normal_y, length = _normal(first, second, signed_area)
    boundary = path_map.get(key)
    midpoint = (0.5 * (first[0] + second[0]), 0.5 * (first[1] + second[1]))
    if boundary is not None and boundary[0] == 'shock':
      index = boundary[1]
      upstream, _ = _interpolate_state(
        shock_points,
        upstream_states,
        upstream_pressures,
        index,
        midpoint,
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
      downstream, _ = _interpolate_state(
        shock_points,
        post_states,
        post_pressures,
        index,
        midpoint,
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
      raw_residual[cell_index] += _rusanov(
        states[cell_index],
        downstream,
        normal_x,
        normal_y,
        length,
        gamma,
        request.gas_constant_J_kgK,
      )
      upstream_flux, _ = _flux(
        upstream,
        normal_x,
        normal_y,
        gamma,
        request.gas_constant_J_kgK,
      )
      downstream_flux, _ = _flux(
        downstream,
        normal_x,
        normal_y,
        gamma,
        request.gas_constant_J_kgK,
      )
      shock_jumps.append(
        float(
          np.max(
            np.abs(upstream_flux - downstream_flux)
            / np.maximum(
              np.maximum(np.abs(upstream_flux), np.abs(downstream_flux)),
              1.0,
            )
          )
        )
      )
    elif boundary is not None and boundary[0] == 'ambient':
      _density, velocity_u, velocity_v, pressure, sound_speed = _primitive(
        states[cell_index],
        gamma,
        request.gas_constant_J_kgK,
      )
      del sound_speed
      target_pressure = _target_pressure_at_x(
        request.ambient_pressure_target,
        midpoint[0],
        position_tolerance_m=request.position_tolerance_m,
        fallback_pressure_Pa=float(ambient_pressure),
      )
      raw_residual[cell_index] += np.array(
        (0.0, target_pressure * normal_x, target_pressure * normal_y, 0.0),
        dtype=float,
      ) * length
      ambient_pressures.append(abs(pressure - target_pressure))
      ambient_normals.append(abs(velocity_u * normal_x + velocity_v * normal_y))
    elif boundary is not None and boundary[0] == 'centerline':
      _density, velocity_u, velocity_v, pressure, _sound_speed = _primitive(
        states[cell_index],
        gamma,
        request.gas_constant_J_kgK,
      )
      raw_residual[cell_index] += np.array(
        (0.0, pressure * normal_x, pressure * normal_y, 0.0),
        dtype=float,
      ) * length
      centerline_normals.append(abs(velocity_u * normal_x + velocity_v * normal_y))
    else:
      terminal_flux, _ = _flux(
        states[cell_index],
        normal_x,
        normal_y,
        gamma,
        request.gas_constant_J_kgK,
      )
      raw_residual[cell_index] += terminal_flux * length
    ####
  ####
  normalised = _normalised_residuals(
    states,
    raw_residual,
    polygons,
    gamma,
    request.gas_constant_J_kgK,
  )
  maximum_euler = float(np.max(normalised[:, 4]))
  maximum_shock = max(shock_jumps, default=0.0)
  maximum_ambient_pressure = max(ambient_pressures, default=0.0)
  maximum_ambient_normal = max(ambient_normals, default=0.0)
  target = request.ambient_pressure_target
  target_coverage_verified = bool(
    target is None
    or all(
      target.pressure_at_x(
        0.5 * (first[0] + second[0]),
        position_tolerance_m=request.position_tolerance_m,
      )
      is not None
      for boundary_key, entries in edge_entries.items()
      if len(entries) == 1
      for boundary in (path_map.get(boundary_key),)
      if boundary is not None and boundary[0] == 'ambient'
      for _cell_index, _edge_index, first, second in entries
    )
  )
  target_consumption_verified = bool(
    target is None
    or (
      target_coverage_verified
      and candidate.ambient_pressure_target_coverage_verified
      and candidate.ambient_pressure_target_consumed
      and (
        target is None
        or (
          len(candidate.ambient_pressure_target_residuals_Pa)
          == len(ambient_pressures)
          and np.allclose(
            np.asarray(candidate.ambient_pressure_target_residuals_Pa),
            np.asarray(ambient_pressures),
            rtol=1.0e-7,
            atol=1.0e-10,
          )
        )
      )
    )
  )
  target_residual_report_verified = bool(
    target is None
    or (
      len(candidate.ambient_pressure_target_residuals_Pa)
      == len(ambient_pressures)
      and np.allclose(
        np.asarray(candidate.ambient_pressure_target_residuals_Pa),
        np.asarray(ambient_pressures),
        rtol=1.0e-7,
        atol=1.0e-10,
      )
    )
  )
  pressure_reference = (
    float(ambient_pressure)
    if target is None
    else target.maximum_pressure_Pa
  )
  maximum_centerline_normal = max(centerline_normals, default=0.0)
  residual_report_verified = bool(
    len(candidate.residual_channels_by_cell) == len(normalised)
    and np.allclose(
      np.asarray(candidate.residual_channels_by_cell, dtype=float),
      normalised,
      rtol=1.0e-7,
      atol=1.0e-10,
    )
    and candidate.maximum_conservative_euler_residual is not None
    and abs(candidate.maximum_conservative_euler_residual - maximum_euler)
    <= 1.0e-7 * max(1.0, maximum_euler)
  )
  residual_channels_recomputed = bool(
    normalised.shape == (len(polygons), len(_CHANNEL_NAMES))
    and np.all(np.isfinite(normalised))
  )
  source_lineage_verified = bool(
    source_lineage_verified
    and len(candidate.cell_centers_m) == len(polygons)
    and candidate.shock_boundary_edge_count == len(shock_points) - 1
    and candidate.ambient_boundary_edge_count == len(ambient_points) - 1
    and candidate.centerline_boundary_edge_count == len(centerline_points) - 1
  )
  shock_verified = bool(
    candidate.maximum_shock_jump_residual is not None
    and abs(candidate.maximum_shock_jump_residual - maximum_shock)
    <= 1.0e-7 * max(1.0, maximum_shock)
    and maximum_shock <= request.shock_jump_tolerance
  )
  maximum_speed = 0.0
  for state in states:
    _density, velocity_u, velocity_v, _pressure, sound_speed = _primitive(
      state,
      gamma,
      request.gas_constant_J_kgK,
    )
    maximum_speed = max(
      maximum_speed,
      float(np.hypot(velocity_u, velocity_v) + sound_speed),
    )
  ####
  ambient_verified = bool(
    candidate.maximum_ambient_pressure_residual_Pa is not None
    and abs(candidate.maximum_ambient_pressure_residual_Pa - maximum_ambient_pressure)
    <= 1.0e-7 * max(1.0, maximum_ambient_pressure)
    and maximum_ambient_pressure
    <= request.ambient_pressure_tolerance_fraction * pressure_reference
    and candidate.maximum_ambient_normal_velocity_residual_m_s is not None
    and abs(
      candidate.maximum_ambient_normal_velocity_residual_m_s
      - maximum_ambient_normal
    )
    <= 1.0e-7 * max(1.0, maximum_ambient_normal)
    and maximum_ambient_normal
    <= request.boundary_normal_velocity_tolerance_fraction
    * max(maximum_speed, 1.0e-12)
  )
  centerline_verified = bool(
    candidate.maximum_centerline_normal_velocity_residual_m_s is not None
    and abs(
      candidate.maximum_centerline_normal_velocity_residual_m_s
      - maximum_centerline_normal
    )
    <= 1.0e-7 * max(1.0, maximum_centerline_normal)
    and maximum_centerline_normal
    <= request.boundary_normal_velocity_tolerance_fraction
    * max(maximum_speed, 1.0e-12)
  )
  geometry_verified = bool(
    len(boundary_entries) == len(path_map) + candidate.terminal_boundary_count
    and candidate.internal_edge_count == sum(
      len(entries) == 2 for entries in edge_entries.values()
    )
  )
  flags_verified = bool(
    candidate.chain_promotion_blocked
    and not candidate.production_claim_allowed
    and not candidate.physical_closure_verified
    and not candidate.global_coupling_verified
  )
  if not residual_channels_recomputed or not residual_report_verified:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.RESIDUAL_FAILURE
    message = 'independent conservative residual reconstruction disagrees with candidate'
  elif not shock_verified:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.SHOCK_JUMP_FAILURE
    message = 'independent shock Rankine--Hugoniot residual remains open'
  elif not ambient_verified or not centerline_verified:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.BOUNDARY_FAILURE
    message = 'independent ambient or centerline boundary residual remains open'
  elif not target_consumption_verified:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.BOUNDARY_FAILURE
    message = 'independent ambient pressure-target consumption audit failed'
  elif not geometry_verified or not source_lineage_verified:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.GEOMETRY_FAILURE
    message = 'independent source geometry or path lineage audit failed'
  elif not flags_verified:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.FLAG_FAILURE
    message = 'candidate weakened the research-only promotion boundary'
  elif not candidate.converged:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.RESIDUAL_FAILURE
    message = 'candidate did not report a locally converged reconciliation'
  else:
    status = MocPhysicalFieldEulerReconciliationAuditStatus.VERIFIED
    message = (
      'independent fixed-front conservative reconciliation audit passed; '
      'canonical placement and refinement remain open'
    )
  ####
  return MocPhysicalFieldEulerReconciliationAudit(
    status=status,
    candidate=candidate,
    cell_count=len(polygons),
    expected_cell_count=len(expected_cells),
    maximum_conservative_euler_residual=maximum_euler,
    maximum_shock_jump_residual=maximum_shock,
    maximum_ambient_pressure_residual_Pa=maximum_ambient_pressure,
    maximum_ambient_normal_velocity_residual_m_s=maximum_ambient_normal,
    maximum_centerline_normal_velocity_residual_m_s=maximum_centerline_normal,
    ambient_pressure_target_coverage_verified=target_coverage_verified,
    ambient_pressure_target_consumption_verified=target_consumption_verified,
    ambient_pressure_target_residual_report_verified=(
      target_residual_report_verified
    ),
    geometry_verified=geometry_verified,
    source_lineage_verified=source_lineage_verified,
    state_samples_verified=True,
    residual_channels_recomputed=residual_channels_recomputed,
    residual_report_verified=residual_report_verified,
    shock_front_verified=shock_verified,
    ambient_boundary_verified=ambient_verified,
    centerline_boundary_verified=centerline_verified,
    promotion_flags_verified=flags_verified,
    message=message,
  )
####
