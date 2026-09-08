"""Front-aligned conservative reconciliation of a retained physical field.

The existing characteristic field carries a fitted shock front, an ambient
pressure path, and a reflected centerline path.  This module consumes those
exact paths as a fixed, solver-owned finite-volume geometry and re-solves the
conservative Euler residual on the retained cells.  It is a reconciliation
solver, not a shock-placement optimizer: the geometry remains research input
until a separate placement/refinement ladder proves that it is stable.

The result deliberately has no production or chain-promotion path.  Its
purpose is to replace a profile-only handoff with a conservative field
consumer that can expose the actual shock jump, ambient tangency, centerline,
and residual channels needed by the next P2.2 closure slice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import cos, isfinite, sin, sqrt
from types import MappingProxyType
from typing import Any

import numpy as np

from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState

__all__ = (
  'MocPhysicalFieldEulerReconciliationStatus',
  'MocPhysicalFieldEulerBoundaryPressureTarget',
  'compose_moc_physical_field_euler_boundary_pressure_target',
  'MocPhysicalFieldEulerReconciliationRequest',
  'MocPhysicalFieldEulerReconciliationResult',
  'solve_moc_physical_field_euler_reconciliation',
)


PHYSICAL_FIELD_EULER_RECONCILIATION_MODEL = (
  'research-front-aligned-physical-field-euler-reconciliation-v1'
)
PHYSICAL_FIELD_EULER_RECONCILIATION_TERMINAL_BOUNDARY = (
  'solver-owned-terminal-outflow-edge-v1'
)
_CHANNEL_NAMES = (
  'mass',
  'streamwise_momentum',
  'transverse_momentum',
  'energy',
  'euler',
)


PHYSICAL_FIELD_EULER_BOUNDARY_PRESSURE_TARGET_MODEL = (
  'research-solver-owned-frontier-pressure-target-v1'
)
PHYSICAL_FIELD_EULER_BOUNDARY_PRESSURE_TARGET_COMPOSITE_MODEL = (
  'research-solver-owned-frontier-pressure-target-explicit-overlay-v1'
)


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerBoundaryPressureTarget:
  """A bounded pressure target consumed on the retained ambient path.

  The target is deliberately narrower than a free-boundary condition.  Its
  stations define a pressure profile only; the fixed reconciliation mesh still
  owns the boundary geometry and tangent checks.  Interpolation is allowed
  only between declared stations, and a target that does not cover every
  ambient-face midpoint is rejected before the conservative solve starts.
  """

  x_stations_m: tuple[float, ...]
  static_pressure_Pa: tuple[float, ...]
  source_id: str
  boundary_points_m: tuple[tuple[float, float], ...] = ()
  tangent_rad: tuple[float, ...] = ()
  model: str = PHYSICAL_FIELD_EULER_BOUNDARY_PRESSURE_TARGET_MODEL
  source_closure_fingerprint: str | None = None
  source_proposal_fingerprint: str | None = None
  composition_mode: str = 'direct'
  composition_base_source_id: str | None = None
  composition_overlay_source_id: str | None = None
  composition_seam_pressure_jump_fraction: float | None = None

  def __post_init__(self) -> None:
    stations = tuple(float(value) for value in self.x_stations_m)
    pressures = tuple(float(value) for value in self.static_pressure_Pa)
    if len(stations) < 2:
      raise ValueError('x_stations_m must contain at least two stations')
    ####
    if len(stations) != len(pressures):
      raise ValueError(
        'x_stations_m and static_pressure_Pa must have equal lengths'
      )
    ####
    if any(not isfinite(value) for value in stations):
      raise ValueError('x_stations_m must contain finite values')
    ####
    if any(
      second <= first
      for first, second in zip(stations, stations[1:])
    ):
      raise ValueError('x_stations_m must be strictly increasing')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in pressures):
      raise ValueError(
        'static_pressure_Pa must contain finite positive values'
      )
    ####
    points = tuple(
      (float(point[0]), float(point[1])) for point in self.boundary_points_m
    )
    if points and len(points) != len(stations):
      raise ValueError(
        'boundary_points_m must match the target station count when supplied'
      )
    ####
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('boundary_points_m must contain finite points')
    ####
    tangents = tuple(float(value) for value in self.tangent_rad)
    if tangents and len(tangents) != len(stations):
      raise ValueError(
        'tangent_rad must match the target station count when supplied'
      )
    ####
    if any(not isfinite(value) for value in tangents):
      raise ValueError('tangent_rad must contain finite values')
    ####
    source_id = str(self.source_id)
    if not source_id:
      raise ValueError('source_id must be non-empty')
    ####
    model = str(self.model)
    if not model:
      raise ValueError('model must be non-empty')
    ####
    composition_mode = str(self.composition_mode)
    if composition_mode not in ('direct', 'explicit-overlay'):
      raise ValueError(
        "composition_mode must be 'direct' or 'explicit-overlay'"
      )
    ####
    base_source_id = self.composition_base_source_id
    overlay_source_id = self.composition_overlay_source_id
    seam_jump = self.composition_seam_pressure_jump_fraction
    if composition_mode == 'direct' and (
      base_source_id is not None
      or overlay_source_id is not None
      or seam_jump is not None
    ):
      raise ValueError(
        'direct pressure targets cannot carry overlay composition metadata'
      )
    ####
    if composition_mode == 'explicit-overlay':
      if not str(base_source_id or '') or not str(overlay_source_id or ''):
        raise ValueError(
          'explicit-overlay pressure targets require base and overlay source IDs'
        )
      ####
      if seam_jump is None:
        raise ValueError(
          'explicit-overlay pressure targets require a seam pressure diagnostic'
        )
      ####
    ####
    if seam_jump is not None:
      seam_jump = float(seam_jump)
      if not isfinite(seam_jump) or seam_jump < 0.0:
        raise ValueError(
          'composition_seam_pressure_jump_fraction must be finite and nonnegative'
        )
      ####
    ####
    closure_fingerprint = self.source_closure_fingerprint
    proposal_fingerprint = self.source_proposal_fingerprint
    if (closure_fingerprint is None) != (proposal_fingerprint is None):
      raise ValueError(
        'source_closure_fingerprint and source_proposal_fingerprint must '
        'be supplied together'
      )
    ####
    if closure_fingerprint is not None and (
      len(str(closure_fingerprint)) != 64
      or any(
        character not in '0123456789abcdef'
        for character in str(closure_fingerprint)
      )
      or len(str(proposal_fingerprint)) != 64
      or any(
        character not in '0123456789abcdef'
        for character in str(proposal_fingerprint)
      )
    ):
      raise ValueError(
        'source target fingerprints must be lowercase SHA-256 digests'
      )
    ####
    object.__setattr__(self, 'x_stations_m', stations)
    object.__setattr__(self, 'static_pressure_Pa', pressures)
    object.__setattr__(self, 'boundary_points_m', points)
    object.__setattr__(self, 'tangent_rad', tangents)
    object.__setattr__(self, 'source_id', source_id)
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'composition_mode', composition_mode)
    if composition_mode == 'explicit-overlay':
      object.__setattr__(self, 'composition_base_source_id', str(base_source_id))
      object.__setattr__(self, 'composition_overlay_source_id', str(overlay_source_id))
      object.__setattr__(self, 'composition_seam_pressure_jump_fraction', seam_jump)
    ####
    if closure_fingerprint is not None:
      object.__setattr__(
        self,
        'source_closure_fingerprint',
        str(closure_fingerprint),
      )
      object.__setattr__(
        self,
        'source_proposal_fingerprint',
        str(proposal_fingerprint),
      )
    ####
  ####

  @property
  def sample_count(self) -> int:
    return len(self.x_stations_m)
  ####

  @property
  def minimum_pressure_Pa(self) -> float:
    return min(self.static_pressure_Pa)
  ####

  @property
  def maximum_pressure_Pa(self) -> float:
    return max(self.static_pressure_Pa)
  ####

  def pressure_at_x(
    self,
    x_m: float,
    *,
    position_tolerance_m: float,
  ) -> float | None:
    """Interpolate a target pressure without endpoint extrapolation."""

    x_value = float(x_m)
    tolerance = float(position_tolerance_m)
    if not isfinite(x_value) or not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('x_m and position_tolerance_m must be finite and valid')
    ####
    if (
      x_value < self.x_stations_m[0] - tolerance
      or x_value > self.x_stations_m[-1] + tolerance
    ):
      return None
    ####
    for index, (first, second) in enumerate(
      zip(self.x_stations_m, self.x_stations_m[1:])
    ):
      if abs(x_value - first) <= tolerance:
        return self.static_pressure_Pa[index]
      ####
      if x_value <= second + tolerance:
        span = second - first
        fraction = min(max((x_value - first) / span, 0.0), 1.0)
        return self.static_pressure_Pa[index] + fraction * (
          self.static_pressure_Pa[index + 1]
          - self.static_pressure_Pa[index]
        )
      ####
    ####
    return self.static_pressure_Pa[-1]
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': self.model,
      'source_id': self.source_id,
      'x_stations_m': self.x_stations_m,
      'static_pressure_Pa': self.static_pressure_Pa,
      'boundary_points_m': self.boundary_points_m,
      'tangent_rad': self.tangent_rad,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_proposal_fingerprint': self.source_proposal_fingerprint,
      'composition_mode': self.composition_mode,
      'composition_base_source_id': self.composition_base_source_id,
      'composition_overlay_source_id': self.composition_overlay_source_id,
      'composition_seam_pressure_jump_fraction': (
        self.composition_seam_pressure_jump_fraction
      ),
      'sample_count': self.sample_count,
      'minimum_pressure_Pa': self.minimum_pressure_Pa,
      'maximum_pressure_Pa': self.maximum_pressure_Pa,
    }
  ####
####


def _interpolate_target_values(
  x_stations_m: tuple[float, ...],
  values: tuple[float, ...],
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, ...]:
  """Interpolate one target-aligned value tuple without extrapolation."""

  x_value = float(x_m)
  tolerance = float(position_tolerance_m)
  if (
    x_value < x_stations_m[0] - tolerance
    or x_value > x_stations_m[-1] + tolerance
  ):
    raise ValueError('target interpolation requested outside its station frame')
  ####
  for index, (first, second) in enumerate(zip(x_stations_m, x_stations_m[1:])):
    if abs(x_value - first) <= tolerance:
      return (values[index],)
    ####
    if x_value <= second + tolerance:
      span = second - first
      fraction = min(max((x_value - first) / span, 0.0), 1.0)
      return (
        values[index] + fraction * (values[index + 1] - values[index]),
      )
    ####
  ####
  return (values[-1],)
####


def _interpolate_target_points(
  target: MocPhysicalFieldEulerBoundaryPressureTarget,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, float]:
  """Interpolate optional target geometry in the target station frame."""

  if not target.boundary_points_m:
    raise ValueError('target has no boundary-point metadata')
  ####
  x_value = float(x_m)
  tolerance = float(position_tolerance_m)
  if (
    x_value < target.x_stations_m[0] - tolerance
    or x_value > target.x_stations_m[-1] + tolerance
  ):
    raise ValueError('target point requested outside its station frame')
  ####
  for index, (first, second) in enumerate(
    zip(target.x_stations_m, target.x_stations_m[1:])
  ):
    if abs(x_value - first) <= tolerance:
      return target.boundary_points_m[index]
    ####
    if x_value <= second + tolerance:
      span = second - first
      fraction = min(max((x_value - first) / span, 0.0), 1.0)
      first_point = target.boundary_points_m[index]
      second_point = target.boundary_points_m[index + 1]
      return (
        first_point[0] + fraction * (second_point[0] - first_point[0]),
        first_point[1] + fraction * (second_point[1] - first_point[1]),
      )
    ####
  ####
  return target.boundary_points_m[-1]
####


def _interpolate_target_scalar(
  x_stations_m: tuple[float, ...],
  values: tuple[float, ...],
  x_m: float,
  *,
  position_tolerance_m: float,
) -> float:
  return _interpolate_target_values(
    x_stations_m,
    values,
    x_m,
    position_tolerance_m=position_tolerance_m,
  )[0]
####


def compose_moc_physical_field_euler_boundary_pressure_target(
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget,
  overlay_target: MocPhysicalFieldEulerBoundaryPressureTarget,
  *,
  source_id: str,
  position_tolerance_m: float = 1.0e-8,
  seam_pressure_tolerance_fraction: float = 0.25,
) -> MocPhysicalFieldEulerBoundaryPressureTarget:
  """Compose an explicit bounded pressure-target overlay.

  ``base_target`` owns the complete retained boundary station frame.  The
  ``overlay_target`` is consumed only on its declared interval; outside that
  interval the base profile is sampled.  The overlay must be contained by the
  base frame, so this helper never extrapolates or invents an endpoint hold.
  The resulting target is explicitly marked as an overlay and retains both
  source IDs.  It remains a fixed-front research input; it is not a global
  geometry update or a free-boundary solve.
  """

  if not isinstance(base_target, MocPhysicalFieldEulerBoundaryPressureTarget):
    raise TypeError(
      'base_target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
    )
  ####
  if not isinstance(overlay_target, MocPhysicalFieldEulerBoundaryPressureTarget):
    raise TypeError(
      'overlay_target must be a MocPhysicalFieldEulerBoundaryPressureTarget'
    )
  ####
  try:
    tolerance = float(position_tolerance_m)
    seam_tolerance = float(seam_pressure_tolerance_fraction)
  except (TypeError, ValueError) as error:
    raise ValueError(
      'position and seam tolerances must be numeric'
    ) from error
  ####
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  if not isfinite(seam_tolerance) or seam_tolerance < 0.0:
    raise ValueError(
      'seam_pressure_tolerance_fraction must be finite and nonnegative'
    )
  ####
  if not str(source_id):
    raise ValueError('source_id must be non-empty')
  ####
  base_min = base_target.x_stations_m[0]
  base_max = base_target.x_stations_m[-1]
  overlay_min = overlay_target.x_stations_m[0]
  overlay_max = overlay_target.x_stations_m[-1]
  if (
    overlay_min < base_min - tolerance
    or overlay_max > base_max + tolerance
  ):
    raise ValueError(
      'overlay target must be contained by the base target station frame; '
      'no extrapolation is allowed'
    )
  ####
  seam_jumps: list[float] = []
  for seam_x in (overlay_min, overlay_max):
    is_interior = (
      seam_x > base_min + tolerance
      and seam_x < base_max - tolerance
    )
    if not is_interior:
      continue
    ####
    base_pressure = base_target.pressure_at_x(
      seam_x,
      position_tolerance_m=tolerance,
    )
    overlay_pressure = overlay_target.pressure_at_x(
      seam_x,
      position_tolerance_m=tolerance,
    )
    if base_pressure is None or overlay_pressure is None:
      raise ValueError('target composition seam is outside a declared profile')
    ####
    seam_jumps.append(
      abs(float(overlay_pressure) - float(base_pressure))
      / max(float(overlay_pressure), float(base_pressure))
    )
  ####
  maximum_seam_jump = max(seam_jumps, default=0.0)
  if maximum_seam_jump > seam_tolerance:
    raise ValueError(
      'overlay target has a pressure discontinuity at its declared seam: '
      f'{maximum_seam_jump} > {seam_tolerance}'
    )
  ####
  stations: list[float] = []
  for value in sorted((*base_target.x_stations_m, *overlay_target.x_stations_m)):
    if not stations or abs(value - stations[-1]) > tolerance:
      stations.append(float(value))
    ####
  ####
  pressures: list[float] = []
  for station in stations:
    in_overlay = (
      overlay_min - tolerance <= station <= overlay_max + tolerance
    )
    active = overlay_target if in_overlay else base_target
    pressure = active.pressure_at_x(
      station,
      position_tolerance_m=tolerance,
    )
    if pressure is None:
      raise ValueError('composed target sampling left the declared station frame')
    ####
    pressures.append(float(pressure))
  ####
  boundary_points: tuple[tuple[float, float], ...] = ()
  tangent: tuple[float, ...] = ()
  if base_target.boundary_points_m and overlay_target.boundary_points_m:
    composed_points: list[tuple[float, float]] = []
    for station in stations:
      active = (
        overlay_target
        if overlay_min - tolerance <= station <= overlay_max + tolerance
        else base_target
      )
      composed_points.append(
        _interpolate_target_points(
          active,
          station,
          position_tolerance_m=tolerance,
        )
      )
    ####
    boundary_points = tuple(composed_points)
  ####
  if base_target.tangent_rad and overlay_target.tangent_rad:
    tangent = tuple(
      _interpolate_target_scalar(
        (
          overlay_target.x_stations_m
          if overlay_min - tolerance <= station <= overlay_max + tolerance
          else base_target.x_stations_m
        ),
        (
          overlay_target.tangent_rad
          if overlay_min - tolerance <= station <= overlay_max + tolerance
          else base_target.tangent_rad
        ),
        station,
        position_tolerance_m=tolerance,
      )
      for station in stations
    )
  ####
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=tuple(stations),
    static_pressure_Pa=tuple(pressures),
    source_id=str(source_id),
    boundary_points_m=boundary_points,
    tangent_rad=tangent,
    model=PHYSICAL_FIELD_EULER_BOUNDARY_PRESSURE_TARGET_COMPOSITE_MODEL,
    source_closure_fingerprint=overlay_target.source_closure_fingerprint,
    source_proposal_fingerprint=overlay_target.source_proposal_fingerprint,
    composition_mode='explicit-overlay',
    composition_base_source_id=base_target.source_id,
    composition_overlay_source_id=overlay_target.source_id,
    composition_seam_pressure_jump_fraction=maximum_seam_jump,
  )
####


class MocPhysicalFieldEulerReconciliationStatus(str, Enum):
  """Typed outcome for one front-aligned conservative re-solve."""

  CONVERGED_LOCAL_RECONCILIATION = (
    'converged-local-physical-field-euler-reconciliation'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = 'source-physical-field-closure-failure'
  GEOMETRY_FAILURE = 'front-aligned-geometry-failure'
  STATE_SAMPLE_FAILURE = 'front-aligned-state-sample-failure'
  POSITIVITY_FAILURE = 'front-aligned-positivity-failure'
  RESIDUAL_FAILURE = 'front-aligned-conservative-residual-failure'
  BOUNDARY_FAILURE = 'front-aligned-boundary-residual-failure'
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationRequest:
  """Inputs for a conservative solve on one retained physical-field mesh."""

  shock_front_condition: MocPhysicalFieldShockFrontConditionResult
  reference_total_temperature_K: float
  gas_constant_J_kgK: float = 287.05
  cfl_number: float = 0.55
  max_pseudo_iterations: int = 600
  euler_residual_tolerance: float = 5.0e-4
  shock_jump_tolerance: float = 5.0e-3
  ambient_pressure_tolerance_fraction: float = 0.10
  boundary_normal_velocity_tolerance_fraction: float = 0.05
  relaxation: float = 0.75
  position_tolerance_m: float = 1.0e-8
  source: str = PHYSICAL_FIELD_EULER_RECONCILIATION_MODEL
  ambient_pressure_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.shock_front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'shock_front_condition must be a '
        'MocPhysicalFieldShockFrontConditionResult'
      )
    ####
    for name in (
      'reference_total_temperature_K',
      'gas_constant_J_kgK',
      'cfl_number',
      'euler_residual_tolerance',
      'shock_jump_tolerance',
      'ambient_pressure_tolerance_fraction',
      'boundary_normal_velocity_tolerance_fraction',
      'relaxation',
      'position_tolerance_m',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.cfl_number >= 1.0:
      raise ValueError('cfl_number must be less than one')
    ####
    if self.ambient_pressure_tolerance_fraction >= 1.0:
      raise ValueError(
        'ambient_pressure_tolerance_fraction must be less than one'
      )
    ####
    if self.boundary_normal_velocity_tolerance_fraction >= 1.0:
      raise ValueError(
        'boundary_normal_velocity_tolerance_fraction must be less than one'
      )
    ####
    if self.relaxation > 1.0:
      raise ValueError('relaxation must be no greater than one')
    ####
    if (
      isinstance(self.max_pseudo_iterations, bool)
      or not isinstance(self.max_pseudo_iterations, int)
      or self.max_pseudo_iterations < 1
    ):
      raise ValueError('max_pseudo_iterations must be a positive integer')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    if self.ambient_pressure_target is not None and not isinstance(
      self.ambient_pressure_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'ambient_pressure_target must be a '
        'MocPhysicalFieldEulerBoundaryPressureTarget or None'
      )
    ####
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': PHYSICAL_FIELD_EULER_RECONCILIATION_MODEL,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'cfl_number': self.cfl_number,
      'max_pseudo_iterations': self.max_pseudo_iterations,
      'euler_residual_tolerance': self.euler_residual_tolerance,
      'shock_jump_tolerance': self.shock_jump_tolerance,
      'ambient_pressure_tolerance_fraction': (
        self.ambient_pressure_tolerance_fraction
      ),
      'boundary_normal_velocity_tolerance_fraction': (
        self.boundary_normal_velocity_tolerance_fraction
      ),
      'relaxation': self.relaxation,
      'position_tolerance_m': self.position_tolerance_m,
      'source': self.source,
      'ambient_pressure_target': (
        None
        if self.ambient_pressure_target is None
        else self.ambient_pressure_target.as_report()
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocPhysicalFieldEulerReconciliationResult:
  """Research result retaining the complete conservative reconciliation."""

  status: MocPhysicalFieldEulerReconciliationStatus
  request: MocPhysicalFieldEulerReconciliationRequest | None
  shock_front_condition: MocPhysicalFieldShockFrontConditionResult | None
  cell_vertices_by_cell_m: tuple[tuple[tuple[float, float], ...], ...] = ()
  cell_centers_m: tuple[tuple[float, float], ...] = ()
  conservative_states_by_cell: tuple[tuple[float, float, float, float], ...] = ()
  residual_channels_by_cell: tuple[tuple[float, float, float, float, float], ...] = ()
  residual_history: tuple[float, ...] = ()
  shock_jump_residuals: tuple[float, ...] = ()
  ambient_pressure_residuals_Pa: tuple[float, ...] = ()
  ambient_normal_velocity_residuals_m_s: tuple[float, ...] = ()
  centerline_normal_velocity_residuals_m_s: tuple[float, ...] = ()
  ambient_pressure_target_residuals_Pa: tuple[float, ...] = ()
  terminal_boundary_count: int = 0
  shock_boundary_edge_count: int = 0
  ambient_boundary_edge_count: int = 0
  centerline_boundary_edge_count: int = 0
  internal_edge_count: int = 0
  pseudo_iteration_count: int = 0
  maximum_conservative_euler_residual: float | None = None
  maximum_shock_jump_residual: float | None = None
  maximum_ambient_pressure_residual_Pa: float | None = None
  maximum_ambient_normal_velocity_residual_m_s: float | None = None
  maximum_centerline_normal_velocity_residual_m_s: float | None = None
  coupled_euler_field_verified: bool = False
  shock_jump_verified: bool = False
  ambient_boundary_verified: bool = False
  centerline_boundary_verified: bool = False
  mesh_verified: bool = False
  conservative_euler_residuals_measured: bool = False
  conservative_euler_residuals_verified: bool = False
  residual_channel_coverage: MappingProxyType = field(
    default_factory=lambda: MappingProxyType({})
  )
  residual_channel_validity: MappingProxyType = field(
    default_factory=lambda: MappingProxyType({})
  )
  ambient_pressure_target_coverage_verified: bool = False
  ambient_pressure_target_consumed: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocPhysicalFieldEulerReconciliationStatus,
    ):
      raise TypeError(
        'status must be a MocPhysicalFieldEulerReconciliationStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocPhysicalFieldEulerReconciliationRequest,
    ):
      raise TypeError(
        'request must be a MocPhysicalFieldEulerReconciliationRequest or None'
      )
    ####
    if self.shock_front_condition is not None and not isinstance(
      self.shock_front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'shock_front_condition must be a '
        'MocPhysicalFieldShockFrontConditionResult or None'
      )
    ####
    centers = tuple(
      (float(point[0]), float(point[1])) for point in self.cell_centers_m
    )
    if any(not all(isfinite(value) for value in point) for point in centers):
      raise ValueError('cell_centers_m must contain finite points')
    ####
    if len(centers) != len(self.cell_vertices_by_cell_m):
      raise ValueError('cell_centers_m must match cell vertex count')
    ####
    object.__setattr__(self, 'cell_centers_m', centers)
    for name in (
      'residual_history',
      'shock_jump_residuals',
      'ambient_pressure_residuals_Pa',
      'ambient_normal_velocity_residuals_m_s',
      'centerline_normal_velocity_residuals_m_s',
      'ambient_pressure_target_residuals_Pa',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    vertices = tuple(
      tuple((float(point[0]), float(point[1])) for point in polygon)
      for polygon in self.cell_vertices_by_cell_m
    )
    if any(
      len(polygon) not in (3, 4)
      or any(not all(isfinite(value) for value in point) for point in polygon)
      for polygon in vertices
    ):
      raise ValueError('cell_vertices_by_cell_m must contain finite triangles or quadrilaterals')
    ####
    object.__setattr__(self, 'cell_vertices_by_cell_m', vertices)
    if len(vertices) != len(self.conservative_states_by_cell):
      raise ValueError(
        'cell_vertices_by_cell_m must match conservative state count'
      )
    ####
    states = tuple(
      tuple(float(value) for value in state)
      for state in self.conservative_states_by_cell
    )
    if any(len(state) != 4 for state in states):
      raise ValueError('conservative_states_by_cell must contain four values')
    ####
    if any(not all(isfinite(value) for value in state) for state in states):
      raise ValueError('conservative_states_by_cell must be finite')
    ####
    object.__setattr__(self, 'conservative_states_by_cell', states)
    residuals = tuple(
      tuple(float(value) for value in residual)
      for residual in self.residual_channels_by_cell
    )
    if any(len(residual) != 5 for residual in residuals):
      raise ValueError('residual_channels_by_cell must contain five values')
    ####
    if any(not all(isfinite(value) for value in residual) for residual in residuals):
      raise ValueError('residual_channels_by_cell must be finite')
    ####
    if len(residuals) != len(states):
      raise ValueError(
        'residual_channels_by_cell must match conservative state count'
      )
    ####
    object.__setattr__(self, 'residual_channels_by_cell', residuals)
    for name in (
      'terminal_boundary_count',
      'shock_boundary_edge_count',
      'ambient_boundary_edge_count',
      'centerline_boundary_edge_count',
      'internal_edge_count',
      'pseudo_iteration_count',
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
    coverage = dict(self.residual_channel_coverage)
    validity = dict(self.residual_channel_validity)
    if any(
      not isinstance(key, str) or not isinstance(value, bool)
      for key, value in (*coverage.items(), *validity.items())
    ):
      raise TypeError('residual channel maps must map strings to bool values')
    ####
    object.__setattr__(self, 'residual_channel_coverage', MappingProxyType(coverage))
    object.__setattr__(self, 'residual_channel_validity', MappingProxyType(validity))
    for name in (
      'coupled_euler_field_verified',
      'shock_jump_verified',
      'ambient_boundary_verified',
      'centerline_boundary_verified',
      'mesh_verified',
      'conservative_euler_residuals_measured',
      'conservative_euler_residuals_verified',
      'ambient_pressure_target_coverage_verified',
      'ambient_pressure_target_consumed',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'physical-field Euler reconciliation cannot allow production claims'
      )
    ####
    if not self.chain_promotion_blocked:
      raise ValueError(
        'physical-field Euler reconciliation must retain its promotion block'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the local conservative and boundary gates all passed."""

    return bool(
      self.status
      is MocPhysicalFieldEulerReconciliationStatus
      .CONVERGED_LOCAL_RECONCILIATION
      and self.mesh_verified
      and self.coupled_euler_field_verified
      and self.shock_jump_verified
      and self.ambient_boundary_verified
      and self.centerline_boundary_verified
      and self.conservative_euler_residuals_measured
      and self.conservative_euler_residuals_verified
      and (
        self.request is None
        or self.request.ambient_pressure_target is None
        or (
          self.ambient_pressure_target_coverage_verified
          and self.ambient_pressure_target_consumed
        )
      )
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Keep the canonical physical-cell gate closed for this fixed mesh."""

    return False
  ####

  @property
  def global_coupling_verified(self) -> bool:
    """A fixed-front reconciliation is not a global placement solve."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'model': PHYSICAL_FIELD_EULER_RECONCILIATION_MODEL,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'cell_vertices_by_cell_m': self.cell_vertices_by_cell_m,
      'cell_centers_m': self.cell_centers_m,
      'conservative_states_by_cell': self.conservative_states_by_cell,
      'residual_channels_by_cell': self.residual_channels_by_cell,
      'residual_history': self.residual_history,
      'shock_jump_residuals': self.shock_jump_residuals,
      'ambient_pressure_residuals_Pa': self.ambient_pressure_residuals_Pa,
      'ambient_normal_velocity_residuals_m_s': (
        self.ambient_normal_velocity_residuals_m_s
      ),
      'centerline_normal_velocity_residuals_m_s': (
        self.centerline_normal_velocity_residuals_m_s
      ),
      'ambient_pressure_target_residuals_Pa': (
        self.ambient_pressure_target_residuals_Pa
      ),
      'terminal_boundary_count': self.terminal_boundary_count,
      'shock_boundary_edge_count': self.shock_boundary_edge_count,
      'ambient_boundary_edge_count': self.ambient_boundary_edge_count,
      'centerline_boundary_edge_count': self.centerline_boundary_edge_count,
      'internal_edge_count': self.internal_edge_count,
      'pseudo_iteration_count': self.pseudo_iteration_count,
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
      'coupled_euler_field_verified': self.coupled_euler_field_verified,
      'shock_jump_verified': self.shock_jump_verified,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'mesh_verified': self.mesh_verified,
      'conservative_euler_residuals_measured': (
        self.conservative_euler_residuals_measured
      ),
      'conservative_euler_residuals_verified': (
        self.conservative_euler_residuals_verified
      ),
      'residual_channel_coverage': dict(self.residual_channel_coverage),
      'residual_channel_validity': dict(self.residual_channel_validity),
      'ambient_pressure_target_coverage_verified': (
        self.ambient_pressure_target_coverage_verified
      ),
      'ambient_pressure_target_consumed': self.ambient_pressure_target_consumed,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': None if self.request is None else self.request.as_report(),
      'message': self.message,
      'claim_status': (
        'research-only-fixed-front-conservative-reconciliation; '
        'front placement, refinement, external validation, and production '
        'gates remain open'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class _BoundaryFace:
  cell_index: int
  edge_index: int
  kind: str
  path_index: int
  first: tuple[float, float]
  second: tuple[float, float]
  normal_x: float
  normal_y: float
  length_m: float
####


@dataclass(frozen=True, slots=True)
class _EdgeLink:
  """One oriented cell edge, either internal or a named boundary face."""

  neighbor_index: int | None
  boundary: _BoundaryFace | None
  first: tuple[float, float]
  second: tuple[float, float]
  normal_x: float
  normal_y: float
  length_m: float
####


@dataclass(frozen=True, slots=True)
class _Mesh:
  vertices: tuple[tuple[tuple[float, float], ...], ...]
  centers: tuple[tuple[float, float], ...]
  areas_m2: tuple[float, ...]
  edges: tuple[tuple[_EdgeLink, ...], ...]
  boundary_faces: tuple[_BoundaryFace, ...]
  internal_edge_count: int
####


def _failure(
  status: MocPhysicalFieldEulerReconciliationStatus,
  request: MocPhysicalFieldEulerReconciliationRequest | None,
  *,
  condition: MocPhysicalFieldShockFrontConditionResult | None = None,
  message: str,
) -> MocPhysicalFieldEulerReconciliationResult:
  return MocPhysicalFieldEulerReconciliationResult(
    status=status,
    request=request,
    shock_front_condition=condition,
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


def _face_normal(
  first: tuple[float, float],
  second: tuple[float, float],
  signed_area: float,
) -> tuple[float, float, float]:
  delta_x = second[0] - first[0]
  delta_y = second[1] - first[1]
  length = float(np.hypot(delta_x, delta_y))
  if not isfinite(length) or length <= 0.0:
    raise ValueError('front-aligned mesh contains a zero-length edge')
  ####
  if signed_area > 0.0:
    return delta_y / length, -delta_x / length, length
  ####
  return -delta_y / length, delta_x / length, length
####


def _build_mesh(
  condition: MocPhysicalFieldShockFrontConditionResult,
  tolerance_m: float,
) -> _Mesh:
  field_result = condition.field
  if field_result is None or not field_result.physical_closure_verified:
    raise RuntimeError(
      'front-aligned reconciliation requires a physically closed source field'
    )
  ####
  cells = tuple(field_result.cells)
  if not cells:
    raise ValueError('source field retained no conservative cells')
  ####
  vertices = tuple(tuple(tuple(point) for point in cell.vertices_xr_m) for cell in cells)
  centers = tuple(
    tuple(float(value) for value in np.mean(np.asarray(polygon), axis=0))
    for polygon in vertices
  )
  areas = tuple(abs(_signed_area(polygon)) for polygon in vertices)
  if any(not isfinite(area) or area <= 0.0 for area in areas):
    raise ValueError('source field contains a nonpositive cell area')
  ####
  all_edges: dict[
    tuple[tuple[int, int], tuple[int, int]],
    list[tuple[int, int, tuple[float, float], tuple[float, float], float]],
  ] = {}
  for cell_index, polygon in enumerate(vertices):
    signed_area = _signed_area(polygon)
    for edge_index, (first, second) in enumerate(
      zip(polygon, (*polygon[1:], polygon[0]))
    ):
      normal_x, normal_y, length = _face_normal(first, second, signed_area)
      key = _edge_key(first, second, tolerance_m)
      all_edges.setdefault(key, []).append(
        (cell_index, edge_index, first, second, length)
      )
    ####
  ####
  paths = {
    'shock': tuple(condition.shock_front_points_m),
    'ambient': tuple(condition.ambient_neighbor_points_m),
    'centerline': tuple(condition.centerline_neighbor_points_m),
  }
  path_edges: dict[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[str, int],
  ] = {}
  for kind, points in paths.items():
    if len(points) < 2:
      raise ValueError(f'{kind} boundary path requires at least two points')
    ####
    for path_index, (first, second) in enumerate(zip(points, points[1:])):
      key = _edge_key(first, second, tolerance_m)
      if key in path_edges:
        raise ValueError('source boundary paths share an edge')
      ####
      if key not in all_edges or len(all_edges[key]) != 1:
        raise ValueError(
          f'{kind} boundary segment {path_index} is not a source boundary edge'
        )
      ####
      path_edges[key] = (kind, path_index)
    ####
  ####
  edges_by_cell: list[list[_EdgeLink]] = [
    [] for _ in cells
  ]
  boundary_faces: list[_BoundaryFace] = []
  internal_edge_count = 0
  for key, entries in all_edges.items():
    if len(entries) == 2:
      first_entry, second_entry = entries
      for entry, neighbor_entry in (
        (first_entry, second_entry),
        (second_entry, first_entry),
      ):
        cell_index, edge_index, first, second, length = entry
        signed_area = _signed_area(vertices[cell_index])
        normal_x, normal_y, _ = _face_normal(first, second, signed_area)
        edges_by_cell[cell_index].append(
          _EdgeLink(
            neighbor_index=neighbor_entry[0],
            boundary=None,
            first=first,
            second=second,
            normal_x=normal_x,
            normal_y=normal_y,
            length_m=length,
          )
        )
      ####
      internal_edge_count += 1
      continue
    ####
    if len(entries) != 1:
      raise ValueError('source field contains a non-manifold edge')
    ####
    cell_index, edge_index, first, second, length = entries[0]
    path = path_edges.get(key)
    if path is None:
      ambient_end = paths['ambient'][-1]
      centerline_end = paths['centerline'][-1]
      endpoint_tolerance = max(10.0 * tolerance_m, 1.0e-7)
      terminal = all(
        min(
          np.hypot(point[0] - ambient_end[0], point[1] - ambient_end[1]),
          np.hypot(point[0] - centerline_end[0], point[1] - centerline_end[1]),
        )
        <= endpoint_tolerance
        for point in (first, second)
      )
      if not terminal:
        raise ValueError(
          'source field contains an unbound boundary edge outside the '
          'shock, ambient, centerline, or terminal paths'
        )
      ####
      kind, path_index = 'terminal', -1
    else:
      kind, path_index = path
    ####
    signed_area = _signed_area(vertices[cell_index])
    normal_x, normal_y, _ = _face_normal(first, second, signed_area)
    face = _BoundaryFace(
      cell_index=cell_index,
      edge_index=edge_index,
      kind=kind,
      path_index=path_index,
      first=first,
      second=second,
      normal_x=normal_x,
      normal_y=normal_y,
      length_m=length,
    )
    edges_by_cell[cell_index].append(
      _EdgeLink(
        neighbor_index=None,
        boundary=face,
        first=first,
        second=second,
        normal_x=normal_x,
        normal_y=normal_y,
        length_m=length,
      )
    )
    boundary_faces.append(face)
  ####
  if any(len(edges) != len(polygon) for edges, polygon in zip(edges_by_cell, vertices, strict=True)):
    raise ValueError('source field edge adjacency does not match cell polygons')
  ####
  return _Mesh(
    vertices=vertices,
    centers=centers,
    areas_m2=areas,
    edges=tuple(tuple(edges) for edges in edges_by_cell),
    boundary_faces=tuple(boundary_faces),
    internal_edge_count=internal_edge_count,
  )
####


def _conservative_from_characteristic(
  state: CharacteristicState,
  total_pressure_Pa: float,
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  gamma = float(state.gamma)
  mach = float(state.mach)
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_pressure = total_pressure_Pa / factor ** (gamma / (gamma - 1.0))
  static_temperature = total_temperature_K / factor
  density = static_pressure / (gas_constant_J_kgK * static_temperature)
  sound_speed = sqrt(gamma * gas_constant_J_kgK * static_temperature)
  speed = mach * sound_speed
  return np.array(
    (
      density,
      density * speed * cos(state.theta_rad),
      density * speed * sin(state.theta_rad),
      static_pressure / (gamma - 1.0) + 0.5 * density * speed * speed,
    ),
    dtype=float,
  )
####


def _primitive(
  state: np.ndarray,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[float, float, float, float, float]:
  density = float(state[0])
  if not isfinite(density) or density <= 0.0:
    raise FloatingPointError('reconciled density is not positive')
  ####
  velocity_u = float(state[1]) / density
  velocity_v = float(state[2]) / density
  pressure = (gamma - 1.0) * (
    float(state[3]) - 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v)
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise FloatingPointError('reconciled pressure is not positive')
  ####
  sound_speed = sqrt(gamma * pressure / density)
  return density, velocity_u, velocity_v, pressure, sound_speed
####


def _euler_flux(
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


def _rusanov_flux(
  left: np.ndarray,
  right: np.ndarray,
  normal_x: float,
  normal_y: float,
  face_length: float,
  gamma: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float]:
  left_flux, left_wave = _euler_flux(
    left,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  right_flux, right_wave = _euler_flux(
    right,
    normal_x,
    normal_y,
    gamma,
    gas_constant_J_kgK,
  )
  wave = max(left_wave, right_wave)
  return (
    0.5 * (left_flux + right_flux) - 0.5 * wave * (right - left)
  ) * face_length, wave
####


def _wall_flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  face_length: float,
  gamma: float,
  gas_constant_J_kgK: float,
  pressure_override: float | None = None,
) -> tuple[np.ndarray, float, float, float]:
  _density, velocity_u, velocity_v, pressure, sound_speed = _primitive(
    state,
    gamma,
    gas_constant_J_kgK,
  )
  boundary_pressure = pressure if pressure_override is None else pressure_override
  normal_velocity = velocity_u * normal_x + velocity_v * normal_y
  return (
    np.array(
      (0.0, boundary_pressure * normal_x, boundary_pressure * normal_y, 0.0),
      dtype=float,
    )
    * face_length,
    sound_speed,
    pressure,
    normal_velocity,
  )
####


def _interpolate_boundary_state(
  path_points: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  total_pressures: tuple[float, ...],
  path_index: int,
  point: tuple[float, float],
  total_temperature_K: float,
  gas_constant_J_kgK: float,
) -> tuple[np.ndarray, float]:
  first = path_points[path_index]
  second = path_points[path_index + 1]
  delta_x = second[0] - first[0]
  delta_y = second[1] - first[1]
  denominator = delta_x * delta_x + delta_y * delta_y
  fraction = (
    0.0
    if denominator <= 0.0
    else ((point[0] - first[0]) * delta_x + (point[1] - first[1]) * delta_y)
    / denominator
  )
  fraction = float(np.clip(fraction, 0.0, 1.0))
  first_state = states[path_index]
  second_state = states[path_index + 1]
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=first_state.theta_rad + fraction * (
      second_state.theta_rad - first_state.theta_rad
    ),
    mach=first_state.mach + fraction * (second_state.mach - first_state.mach),
    gamma=first_state.gamma + fraction * (second_state.gamma - first_state.gamma),
  )
  total_pressure = total_pressures[path_index] + fraction * (
    total_pressures[path_index + 1] - total_pressures[path_index]
  )
  return (
    _conservative_from_characteristic(
      state,
      total_pressure,
      total_temperature_K,
      gas_constant_J_kgK,
    ),
    total_pressure,
  )
####


def _ambient_pressure_at_x(
  request: MocPhysicalFieldEulerReconciliationRequest,
  x_m: float,
  *,
  position_tolerance_m: float,
  ambient_pressure_Pa: float,
) -> float:
  target = request.ambient_pressure_target
  if target is None:
    return float(ambient_pressure_Pa)
  ####
  pressure = target.pressure_at_x(
    x_m,
    position_tolerance_m=position_tolerance_m,
  )
  if pressure is None:
    raise ValueError(
      'ambient pressure target does not cover every retained boundary face'
    )
  ####
  return float(pressure)
####


def _ambient_pressure_target_covers_mesh(
  request: MocPhysicalFieldEulerReconciliationRequest,
  mesh: _Mesh,
) -> bool:
  target = request.ambient_pressure_target
  if target is None:
    return True
  ####
  return all(
    target.pressure_at_x(
      0.5 * (face.first[0] + face.second[0]),
      position_tolerance_m=request.position_tolerance_m,
    )
    is not None
    for face in mesh.boundary_faces
    if face.kind == 'ambient'
  )
####


def _source_cell_states(
  condition: MocPhysicalFieldShockFrontConditionResult,
  mesh: _Mesh,
  request: MocPhysicalFieldEulerReconciliationRequest,
) -> np.ndarray:
  field_result = condition.field
  if field_result is None:
    raise RuntimeError('source field is unavailable')
  ####
  states = np.empty((len(mesh.centers), 4), dtype=float)
  for index, point in enumerate(mesh.centers):
    characteristic = field_result.state_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    total_pressure = field_result.total_pressure_at(
      point,
      position_tolerance_m=request.position_tolerance_m,
    )
    if characteristic is None or total_pressure is None:
      raise ValueError(
        f'source physical field cannot sample reconciled cell center {point!r}'
      )
    ####
    if abs(characteristic.gamma - field_result.post_shock_boundary_states[0].gamma) > 1.0e-8:
      raise ValueError('source cell gamma does not match the shock-front field')
    ####
    states[index] = _conservative_from_characteristic(
      characteristic,
      total_pressure,
      request.reference_total_temperature_K,
      request.gas_constant_J_kgK,
    )
  ####
  return states
####


def _normalise_residuals(
  states: np.ndarray,
  residual: np.ndarray,
  mesh: _Mesh,
  gamma: float,
  gas_constant_J_kgK: float,
) -> np.ndarray:
  output = np.empty((len(mesh.vertices), 5), dtype=float)
  for index, polygon in enumerate(mesh.vertices):
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
    energy_scale = max((states[index, 3] + pressure) * sound_speed * perimeter, 1.0e-12)
    output[index, :4] = (
      abs(residual[index, 0]) / mass_scale,
      abs(residual[index, 1]) / momentum_scale,
      abs(residual[index, 2]) / momentum_scale,
      abs(residual[index, 3]) / energy_scale,
    )
    output[index, 4] = float(np.max(output[index, :4]))
  ####
  return output
####


def _residuals(
  states: np.ndarray,
  mesh: _Mesh,
  condition: MocPhysicalFieldShockFrontConditionResult,
  request: MocPhysicalFieldEulerReconciliationRequest,
  gamma: float,
) -> tuple[
  np.ndarray,
  np.ndarray,
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
]:
  residual = np.zeros_like(states)
  wave_sums = np.zeros(len(mesh.vertices), dtype=float)
  shock_jumps: list[float] = []
  ambient_pressures: list[float] = []
  ambient_normals: list[float] = []
  centerline_normals: list[float] = []
  field_result = condition.field
  if field_result is None:
    raise RuntimeError('source physical field is unavailable')
  ####
  shock_points = tuple(condition.shock_front_points_m)
  upstream_states = tuple(field_result.upstream_shock_boundary_states)
  upstream_pressures = tuple(field_result.upstream_shock_boundary_total_pressure_Pa)
  post_shock_states = tuple(field_result.post_shock_boundary_states)
  post_shock_pressures = tuple(field_result.post_shock_boundary_total_pressure_Pa)
  if len(upstream_states) != len(shock_points) or len(post_shock_states) != len(shock_points):
    raise ValueError('source shock-front state arrays do not cover the shock path')
  ####
  ambient_pressure = field_result.ambient_boundary.ambient_pressure_Pa
  if ambient_pressure is None:
    raise ValueError('source physical field has no ambient pressure')
  ####
  for cell_index, edge_links in enumerate(mesh.edges):
    state = states[cell_index]
    for link in edge_links:
      face = link.boundary
      if face is None:
        if link.neighbor_index is None:
          raise ValueError('internal edge has no neighboring cell')
        ####
        flux, wave = _rusanov_flux(
          state,
          states[link.neighbor_index],
          link.normal_x,
          link.normal_y,
          link.length_m,
          gamma,
          request.gas_constant_J_kgK,
        )
        residual[cell_index] += flux
        wave_sums[cell_index] += wave * link.length_m
        continue
      ####
      midpoint = (
        0.5 * (face.first[0] + face.second[0]),
        0.5 * (face.first[1] + face.second[1]),
      )
      if face.kind == 'shock':
        boundary_state, _boundary_pressure = _interpolate_boundary_state(
          shock_points,
          post_shock_states,
          post_shock_pressures,
          face.path_index,
          midpoint,
          request.reference_total_temperature_K,
          request.gas_constant_J_kgK,
        )
        flux, wave = _rusanov_flux(
          state,
          boundary_state,
          face.normal_x,
          face.normal_y,
          face.length_m,
          gamma,
          request.gas_constant_J_kgK,
        )
        upstream, _ = _interpolate_boundary_state(
          shock_points,
          upstream_states,
          upstream_pressures,
          face.path_index,
          midpoint,
          request.reference_total_temperature_K,
          request.gas_constant_J_kgK,
        )
        downstream, _ = _interpolate_boundary_state(
          shock_points,
          post_shock_states,
          post_shock_pressures,
          face.path_index,
          midpoint,
          request.reference_total_temperature_K,
          request.gas_constant_J_kgK,
        )
        upstream_flux, _ = _euler_flux(
          upstream,
          face.normal_x,
          face.normal_y,
          gamma,
          request.gas_constant_J_kgK,
        )
        downstream_flux, _ = _euler_flux(
          downstream,
          face.normal_x,
          face.normal_y,
          gamma,
          request.gas_constant_J_kgK,
        )
        shock_jumps.append(
          float(
            np.max(
              np.abs(upstream_flux - downstream_flux)
              / np.maximum(np.maximum(np.abs(upstream_flux), np.abs(downstream_flux)), 1.0)
            )
          )
        )
      elif face.kind == 'ambient':
        target_pressure = _ambient_pressure_at_x(
          request,
          midpoint[0],
          position_tolerance_m=request.position_tolerance_m,
          ambient_pressure_Pa=float(ambient_pressure),
        )
        flux, wave, pressure, normal_velocity = _wall_flux(
          state,
          face.normal_x,
          face.normal_y,
          face.length_m,
          gamma,
          request.gas_constant_J_kgK,
          target_pressure,
        )
        ambient_pressures.append(abs(pressure - target_pressure))
        ambient_normals.append(abs(normal_velocity))
      elif face.kind == 'centerline':
        flux, wave, _pressure, normal_velocity = _wall_flux(
          state,
          face.normal_x,
          face.normal_y,
          face.length_m,
          gamma,
          request.gas_constant_J_kgK,
        )
        centerline_normals.append(abs(normal_velocity))
      elif face.kind == 'terminal':
        flux_density, wave = _euler_flux(
          state,
          face.normal_x,
          face.normal_y,
          gamma,
          request.gas_constant_J_kgK,
        )
        flux = flux_density * face.length_m
      else:
        raise ValueError(f'unknown boundary face kind {face.kind!r}')
      ####
      residual[cell_index] += flux
      wave_sums[cell_index] += wave * face.length_m
    ####
  ####
  return (
    residual,
    wave_sums,
    tuple(shock_jumps),
    tuple(ambient_pressures),
    tuple(ambient_normals),
    tuple(centerline_normals),
  )
####


def solve_moc_physical_field_euler_reconciliation(
  request: MocPhysicalFieldEulerReconciliationRequest,
) -> MocPhysicalFieldEulerReconciliationResult:
  """Run a conservative fixed-front reconciliation on the retained field."""

  if not isinstance(
    request,
    MocPhysicalFieldEulerReconciliationRequest,
  ):
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.INVALID_INPUT,
      None,
      message=(
        'request must be a MocPhysicalFieldEulerReconciliationRequest'
      ),
    )
  ####
  condition = request.shock_front_condition
  if not condition.converged or condition.field is None:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.SOURCE_CLOSURE_FAILURE,
      request,
      condition=condition,
      message=(
        'front-aligned reconciliation requires a converged, exact source '
        'shock-front condition'
      ),
    )
  ####
  try:
    mesh = _build_mesh(condition, request.position_tolerance_m)
  except RuntimeError as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.SOURCE_CLOSURE_FAILURE,
      request,
      condition=condition,
      message=str(error),
    )
  except (ArithmeticError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.GEOMETRY_FAILURE,
      request,
      condition=condition,
      message=f'front-aligned source mesh failed: {error}',
    )
  ####
  target_coverage_verified = _ambient_pressure_target_covers_mesh(
    request,
    mesh,
  )
  if not target_coverage_verified:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.BOUNDARY_FAILURE,
      request,
      condition=condition,
      message=(
        'solver-owned ambient pressure target does not cover every retained '
        'ambient-face midpoint; no extrapolation was attempted'
      ),
    )
  ####
  try:
    gamma = float(condition.field.post_shock_boundary_states[0].gamma)
    states = _source_cell_states(condition, mesh, request)
    for state in states:
      _primitive(state, gamma, request.gas_constant_J_kgK)
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError, IndexError) as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.STATE_SAMPLE_FAILURE,
      request,
      condition=condition,
      message=f'front-aligned source state sampling failed: {error}',
    )
  ####
  residual_history: list[float] = []
  positivity_failure = False
  pseudo_iteration_count = 0
  final_residual: np.ndarray | None = None
  diagnostics: tuple[tuple[float, ...], ...] = ()
  for _iteration in range(request.max_pseudo_iterations):
    try:
      (
        residual,
        wave_sums,
        shock_jumps,
        ambient_pressures,
        ambient_normals,
        centerline_normals,
      ) = _residuals(states, mesh, condition, request, gamma)
      normalised = _normalise_residuals(
        states,
        residual,
        mesh,
        gamma,
        request.gas_constant_J_kgK,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError, RuntimeError) as error:
      return _failure(
        MocPhysicalFieldEulerReconciliationStatus.GEOMETRY_FAILURE,
        request,
        condition=condition,
        message=f'front-aligned conservative residual assembly failed: {error}',
      )
    ####
    maximum_residual = float(np.max(normalised[:, 4]))
    if not isfinite(maximum_residual):
      positivity_failure = True
      break
    ####
    residual_history.append(maximum_residual)
    final_residual = residual
    diagnostics = (
      shock_jumps,
      ambient_pressures,
      ambient_normals,
      centerline_normals,
    )
    pseudo_iteration_count = _iteration + 1
    if maximum_residual <= request.euler_residual_tolerance:
      break
    ####
    candidate = states.copy()
    for index, area in enumerate(mesh.areas_m2):
      timestep = request.cfl_number * area / max(wave_sums[index], 1.0e-12)
      delta = -timestep / area * residual[index]
      relaxation = request.relaxation
      accepted = False
      while relaxation >= 1.0e-4:
        trial = states[index] + relaxation * delta
        try:
          _primitive(trial, gamma, request.gas_constant_J_kgK)
        except (FloatingPointError, ValueError):
          relaxation *= 0.5
          continue
        ####
        candidate[index] = trial
        accepted = True
        break
      ####
      if not accepted:
        positivity_failure = True
        break
      ####
    ####
    if positivity_failure:
      break
    ####
    states = candidate
  ####
  if final_residual is None or not diagnostics:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.RESIDUAL_FAILURE,
      request,
      condition=condition,
      message='front-aligned reconciliation produced no residual sample',
    )
  ####
  try:
    normalised = _normalise_residuals(
      states,
      final_residual,
      mesh,
      gamma,
      request.gas_constant_J_kgK,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocPhysicalFieldEulerReconciliationStatus.POSITIVITY_FAILURE,
      request,
      condition=condition,
      message=f'front-aligned final state is nonphysical: {error}',
    )
  ####
  shock_jumps, ambient_pressures, ambient_normals, centerline_normals = diagnostics
  maximum_euler = float(np.max(normalised[:, 4]))
  maximum_shock = max(shock_jumps, default=0.0)
  maximum_ambient_pressure = max(
    (abs(value) for value in ambient_pressures),
    default=0.0,
  )
  maximum_ambient_normal = max((abs(value) for value in ambient_normals), default=0.0)
  maximum_centerline_normal = max(
    (abs(value) for value in centerline_normals),
    default=0.0,
  )
  ambient_pressure = float(condition.field.ambient_boundary.ambient_pressure_Pa)
  pressure_reference = (
    ambient_pressure
    if request.ambient_pressure_target is None
    else request.ambient_pressure_target.maximum_pressure_Pa
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
  mesh_verified = bool(
    mesh.internal_edge_count > 0
    and mesh.boundary_faces
    and any(face.kind == 'shock' for face in mesh.boundary_faces)
    and any(face.kind == 'ambient' for face in mesh.boundary_faces)
    and any(face.kind == 'centerline' for face in mesh.boundary_faces)
  )
  shock_verified = maximum_shock <= request.shock_jump_tolerance
  ambient_verified = bool(
    maximum_ambient_pressure
    <= request.ambient_pressure_tolerance_fraction * pressure_reference
    and maximum_ambient_normal
    <= request.boundary_normal_velocity_tolerance_fraction
    * max(maximum_speed, 1.0e-12)
  )
  centerline_verified = bool(
    maximum_centerline_normal
    <= request.boundary_normal_velocity_tolerance_fraction
    * max(maximum_speed, 1.0e-12)
  )
  residual_verified = maximum_euler <= request.euler_residual_tolerance
  coupled_verified = bool(mesh_verified and residual_verified)
  if positivity_failure:
    status = MocPhysicalFieldEulerReconciliationStatus.POSITIVITY_FAILURE
    message = 'front-aligned pseudo-time update could not retain positivity'
  elif not residual_verified:
    status = MocPhysicalFieldEulerReconciliationStatus.RESIDUAL_FAILURE
    message = 'front-aligned conservative residual tolerance was not reached'
  elif not (shock_verified and ambient_verified and centerline_verified):
    status = MocPhysicalFieldEulerReconciliationStatus.BOUNDARY_FAILURE
    message = (
      'front-aligned conservative field reached its Euler residual gate, but '
      'shock-jump, ambient, or centerline boundary residuals remain open'
    )
  else:
    status = MocPhysicalFieldEulerReconciliationStatus.CONVERGED_LOCAL_RECONCILIATION
    message = (
      'front-aligned conservative reconciliation passed local residual and '
      'boundary checks; shock placement, refinement, and external validation '
      'remain open'
    )
  ####
  coverage = MappingProxyType({name: True for name in _CHANNEL_NAMES})
  validity = MappingProxyType({
    'mass': bool(np.all(np.isfinite(normalised[:, 0]))),
    'streamwise_momentum': bool(np.all(np.isfinite(normalised[:, 1]))),
    'transverse_momentum': bool(np.all(np.isfinite(normalised[:, 2]))),
    'energy': bool(np.all(np.isfinite(normalised[:, 3]))),
    'euler': bool(np.all(np.isfinite(normalised[:, 4]))),
  })
  edge_counts = {
    kind: sum(face.kind == kind for face in mesh.boundary_faces)
    for kind in ('shock', 'ambient', 'centerline', 'terminal')
  }
  return MocPhysicalFieldEulerReconciliationResult(
    status=status,
    request=request,
    shock_front_condition=condition,
    cell_vertices_by_cell_m=mesh.vertices,
    cell_centers_m=mesh.centers,
    conservative_states_by_cell=tuple(
      tuple(float(value) for value in state) for state in states
    ),
    residual_channels_by_cell=tuple(
      tuple(float(value) for value in row) for row in normalised
    ),
    residual_history=tuple(residual_history),
    shock_jump_residuals=shock_jumps,
    ambient_pressure_residuals_Pa=ambient_pressures,
    ambient_normal_velocity_residuals_m_s=ambient_normals,
    centerline_normal_velocity_residuals_m_s=centerline_normals,
    ambient_pressure_target_residuals_Pa=(
      ambient_pressures if request.ambient_pressure_target is not None else ()
    ),
    terminal_boundary_count=edge_counts['terminal'],
    shock_boundary_edge_count=edge_counts['shock'],
    ambient_boundary_edge_count=edge_counts['ambient'],
    centerline_boundary_edge_count=edge_counts['centerline'],
    internal_edge_count=mesh.internal_edge_count,
    pseudo_iteration_count=pseudo_iteration_count,
    maximum_conservative_euler_residual=maximum_euler,
    maximum_shock_jump_residual=maximum_shock,
    maximum_ambient_pressure_residual_Pa=maximum_ambient_pressure,
    maximum_ambient_normal_velocity_residual_m_s=maximum_ambient_normal,
    maximum_centerline_normal_velocity_residual_m_s=maximum_centerline_normal,
    coupled_euler_field_verified=coupled_verified,
    shock_jump_verified=shock_verified,
    ambient_boundary_verified=ambient_verified,
    centerline_boundary_verified=centerline_verified,
    mesh_verified=mesh_verified,
    conservative_euler_residuals_measured=True,
    conservative_euler_residuals_verified=residual_verified,
    residual_channel_coverage=coverage,
    residual_channel_validity=validity,
    ambient_pressure_target_coverage_verified=target_coverage_verified,
    ambient_pressure_target_consumed=(
      request.ambient_pressure_target is not None and bool(ambient_pressures)
    ),
    message=message,
  )
####
