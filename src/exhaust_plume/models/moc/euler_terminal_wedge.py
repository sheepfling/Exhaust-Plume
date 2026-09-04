"""Solver-owned characteristic reconstruction for the reflected terminal wedge.

The ambient-closed physical field retains one small triangle where its
terminal shock point, terminal shock-sourced ``C+`` node, and first axis
sample meet.  That triangle is topologically closed, but its axis vertex was
constructed from the earlier ambient source rather than from the terminal
``C-`` characteristic.  This module builds a separate, solver-owned local
candidate by reflecting the terminal ``C-`` node to the symmetry line.

The candidate is intentionally narrow.  It does not overwrite the physical
field, solve the global reflected free boundary, or create a chain cell.  It
does, however, make the terminal characteristic geometry and carried entropy
source measurable before a future multi-cell terminal remesher is attempted.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import cos, hypot, isfinite, log, sin, sqrt
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
  MocPhysicalPostShockFieldStatus,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicPointResult,
  CharacteristicState,
  centerline_characteristic_point,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeCharacteristicStatus',
  'MocEulerAmbientFirstWedgeCharacteristicEdge',
  'MocEulerAmbientFirstWedgeCharacteristicResult',
  'solve_euler_ambient_first_wedge_characteristic_remesh',
  'MocEulerAmbientFirstWedgeCharacteristicFieldStatus',
  'MocEulerAmbientFirstWedgeCharacteristicFieldResult',
  'remesh_euler_ambient_first_wedge_characteristic_field',
)


class MocEulerAmbientFirstWedgeCharacteristicStatus(str, Enum):
  """Outcome of the solver-owned terminal-wedge reconstruction."""

  CONVERGED_CHARACTERISTIC_WEDGE = (
    'converged_euler_ambient_first_wedge_characteristic_remesh'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_REQUIRED = 'euler_ambient_first_wedge_field_required'
  WEDGE_REQUIRED = 'euler_ambient_first_wedge_required'
  REFLECTION_FAILURE = 'euler_ambient_first_wedge_reflection_failure'
  CHARACTERISTIC_GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_geometry_failure'
  )
  ENTROPY_FAILURE = 'euler_ambient_first_wedge_entropy_failure'
  EULER_RESIDUAL_FAILURE = 'euler_ambient_first_wedge_euler_residual_failure'
  TOPOLOGY_FAILURE = 'euler_ambient_first_wedge_topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicEdge:
  """One measured characteristic edge in the terminal-wedge candidate."""

  edge_index: int
  family: CharacteristicFamily
  start_vertex: tuple[float, float]
  end_vertex: tuple[float, float]
  edge_length_m: float
  forward_margin_m: float
  alignment_residual: float
  k_residual: float
  entropy_source_prediction: float
  compatibility_residual: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.edge_index, bool)
      or not isinstance(self.edge_index, int)
      or self.edge_index < 0
    ):
      raise ValueError('edge_index must be a nonnegative integer')
    ####
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    ####
    for name in ('start_vertex', 'end_vertex'):
      point = getattr(self, name)
      try:
        values = (float(point[0]), float(point[1]))
      except (IndexError, TypeError, ValueError) as error:
        raise ValueError(f'{name} must contain two numeric coordinates') from error
      ####
      if not all(isfinite(value) for value in values):
        raise ValueError(f'{name} must contain finite coordinates')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'edge_length_m',
      'forward_margin_m',
      'alignment_residual',
      'k_residual',
      'entropy_source_prediction',
      'compatibility_residual',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'edge_index': self.edge_index,
      'family': self.family.value,
      'start_vertex': list(self.start_vertex),
      'end_vertex': list(self.end_vertex),
      'edge_length_m': self.edge_length_m,
      'forward_margin_m': self.forward_margin_m,
      'alignment_residual': self.alignment_residual,
      'k_residual': self.k_residual,
      'entropy_source_prediction': self.entropy_source_prediction,
      'compatibility_residual': self.compatibility_residual,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicResult:
  """A local entropy-aware terminal-wedge candidate.

  ``converged`` means the two characteristic edges, carried entropy source,
  and local finite-volume residual all passed.  It is still below physical
  first-cell closure: the candidate is a replacement for one terminal
  triangle only and is never eligible for direct chain promotion.
  """

  status: MocEulerAmbientFirstWedgeCharacteristicStatus
  source_field: MocEulerAmbientPhysicalFieldResult | None
  source_cell_index: int | None
  source_cell_kind: str | None
  original_vertices_xr_m: tuple[tuple[float, float], ...]
  vertices_xr_m: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  total_pressure_Pa: tuple[float, ...]
  cell: MocCharacteristicCell | None
  cell_sample: MocEulerAmbientFirstWedgeCellSample | None
  topology: MocTopologyResult
  reflection_result: CharacteristicPointResult | None
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdge, ...]
  maximum_edge_alignment_residual: float | None
  minimum_forward_margin_m: float | None
  maximum_k_residual: float | None
  maximum_entropy_compatibility_residual: float | None
  cell_euler_residual: float | None
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  cell_euler_residual_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeCharacteristicStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeCharacteristicStatus'
      )
    ####
    if self.source_field is not None and not isinstance(
      self.source_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'source_field must be a MocEulerAmbientPhysicalFieldResult or None'
      )
    ####
    if self.source_cell_index is not None and (
      isinstance(self.source_cell_index, bool)
      or not isinstance(self.source_cell_index, int)
      or self.source_cell_index < 0
    ):
      raise ValueError('source_cell_index must be a nonnegative integer or None')
    ####
    if self.source_cell_kind is not None:
      object.__setattr__(self, 'source_cell_kind', str(self.source_cell_kind))
    ####
    for name in ('original_vertices_xr_m', 'vertices_xr_m'):
      points = tuple(_finite_point(point, name) for point in getattr(self, name))
      object.__setattr__(self, name, points)
    ####
    states = tuple(self.states)
    pressures = tuple(float(value) for value in self.total_pressure_Pa)
    if len(states) != len(self.vertices_xr_m):
      raise ValueError('states must match vertices_xr_m')
    ####
    if len(pressures) != len(self.vertices_xr_m):
      raise ValueError('total_pressure_Pa must match vertices_xr_m')
    ####
    if any(not isinstance(state, CharacteristicState) for state in states):
      raise TypeError('states must contain CharacteristicState values')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in pressures):
      raise ValueError('total_pressure_Pa must contain finite positive values')
    ####
    if any(
      hypot(state.x_m - point[0], state.y_m - point[1]) > 1.0e-10
      for point, state in zip(self.vertices_xr_m, states, strict=True)
    ):
      raise ValueError('states must lie on vertices_xr_m')
    ####
    object.__setattr__(self, 'states', states)
    object.__setattr__(self, 'total_pressure_Pa', pressures)
    if self.cell is not None and not isinstance(self.cell, MocCharacteristicCell):
      raise TypeError('cell must be a MocCharacteristicCell or None')
    ####
    if self.cell_sample is not None and not isinstance(
      self.cell_sample,
      MocEulerAmbientFirstWedgeCellSample,
    ):
      raise TypeError(
        'cell_sample must be a MocEulerAmbientFirstWedgeCellSample or None'
      )
    ####
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    if self.reflection_result is not None and not isinstance(
      self.reflection_result,
      CharacteristicPointResult,
    ):
      raise TypeError(
        'reflection_result must be a CharacteristicPointResult or None'
      )
    ####
    edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(edge, MocEulerAmbientFirstWedgeCharacteristicEdge)
      for edge in edges
    ):
      raise TypeError(
        'characteristic_edges must contain typed characteristic edge values'
      )
    ####
    object.__setattr__(self, 'characteristic_edges', edges)
    for name in (
      'maximum_edge_alignment_residual',
      'minimum_forward_margin_m',
      'maximum_k_residual',
      'maximum_entropy_compatibility_residual',
      'cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'cell_euler_residual_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .CONVERGED_CHARACTERISTIC_WEDGE
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.cell_euler_residual_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the hard stop between this candidate and a continued chain."""

    if self.status is MocEulerAmbientFirstWedgeCharacteristicStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    else:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'solver-owned terminal-wedge candidate remains below physical chain '
        'promotion; reflected free-boundary, complete entropy transport, and '
        'external validation are still required'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'terminal_wedge_status': self.status.value,
        'source_cell_index': self.source_cell_index,
        'characteristic_geometry_verified': (
          self.characteristic_geometry_verified
        ),
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'globally-coupled-entropy-carrying-terminal-wedge-remesh-and-'
          'reflected-free-boundary-closure'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_field_status': (
        None if self.source_field is None else self.source_field.status.value
      ),
      'source_cell_index': self.source_cell_index,
      'source_cell_kind': self.source_cell_kind,
      'original_vertices_xr_m': [
        list(point) for point in self.original_vertices_xr_m
      ],
      'vertices_xr_m': [list(point) for point in self.vertices_xr_m],
      'mach': [state.mach for state in self.states],
      'flow_angles_rad': [state.theta_rad for state in self.states],
      'total_pressure_Pa': list(self.total_pressure_Pa),
      'cell_count': 0 if self.cell is None else 1,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'reflection_result': (
        None
        if self.reflection_result is None
        else {
          'status': self.reflection_result.status.value,
          'point_m': self.reflection_result.point_m,
          'invariant_residual_minus': (
            self.reflection_result.invariant_residual_minus
          ),
          'geometry_residual': self.reflection_result.geometry_residual,
          'message': self.reflection_result.message,
        }
      ),
      'characteristic_edges': [
        edge.as_report() for edge in self.characteristic_edges
      ],
      'maximum_edge_alignment_residual': (
        self.maximum_edge_alignment_residual
      ),
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_k_residual': self.maximum_k_residual,
      'maximum_entropy_compatibility_residual': (
        self.maximum_entropy_compatibility_residual
      ),
      'cell_euler_residual': self.cell_euler_residual,
      'checks': {
        'characteristic_geometry_verified': (
          self.characteristic_geometry_verified
        ),
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'characteristic_residual_tolerance': (
        self.characteristic_residual_tolerance
      ),
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'claim_status': (
        'solver-owned-local-terminal-characteristic-candidate; global '
        'entropy/free-boundary closure and external validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _finite_point(value: Any, label: str) -> tuple[float, float]:
  try:
    point = (float(value[0]), float(value[1]))
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(f'{label} must contain two numeric coordinates') from error
  ####
  if not all(isfinite(component) for component in point):
    raise ValueError(f'{label} must contain finite coordinates')
  ####
  return point
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _failure(
  status: MocEulerAmbientFirstWedgeCharacteristicStatus,
  source_field: MocEulerAmbientPhysicalFieldResult | None,
  *,
  source_cell_index: int | None = None,
  source_cell_kind: str | None = None,
  original_vertices: tuple[tuple[float, float], ...] = (),
  vertices: tuple[tuple[float, float], ...] = (),
  states: tuple[CharacteristicState, ...] = (),
  pressures: tuple[float, ...] = (),
  cell: MocCharacteristicCell | None = None,
  cell_sample: MocEulerAmbientFirstWedgeCellSample | None = None,
  topology: MocTopologyResult | None = None,
  reflection_result: CharacteristicPointResult | None = None,
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdge, ...] = (),
  maximum_edge_alignment_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  maximum_k_residual: float | None = None,
  maximum_entropy_compatibility_residual: float | None = None,
  cell_euler_residual: float | None = None,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  cell_euler_residual_verified: bool = False,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  message: str,
) -> MocEulerAmbientFirstWedgeCharacteristicResult:
  return MocEulerAmbientFirstWedgeCharacteristicResult(
    status=status,
    source_field=source_field,
    source_cell_index=source_cell_index,
    source_cell_kind=source_cell_kind,
    original_vertices_xr_m=original_vertices,
    vertices_xr_m=vertices,
    states=states,
    total_pressure_Pa=pressures,
    cell=cell,
    cell_sample=cell_sample,
    topology=_empty_topology() if topology is None else topology,
    reflection_result=reflection_result,
    characteristic_edges=characteristic_edges,
    maximum_edge_alignment_residual=maximum_edge_alignment_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    maximum_k_residual=maximum_k_residual,
    maximum_entropy_compatibility_residual=(
      maximum_entropy_compatibility_residual
    ),
    cell_euler_residual=cell_euler_residual,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=(
      variable_entropy_compatibility_verified
    ),
    cell_euler_residual_verified=cell_euler_residual_verified,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def _log_pressure_gradient(
  vertices: tuple[tuple[float, float], ...],
  pressures: tuple[float, ...],
) -> tuple[float, float] | None:
  if len(vertices) != 3 or len(pressures) != 3:
    return None
  ####
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return None
  ####
  (x1, y1), (x2, y2), (x3, y3) = vertices
  twice_area = (
    x1 * (y2 - y3)
    + x2 * (y3 - y1)
    + x3 * (y1 - y2)
  )
  if not isfinite(twice_area) or abs(twice_area) <= 1.0e-24:
    return None
  ####
  values = tuple(log(value) for value in pressures)
  return (
    (
      values[0] * (y2 - y3)
      + values[1] * (y3 - y1)
      + values[2] * (y1 - y2)
    ) / twice_area,
    (
      values[0] * (x3 - x2)
      + values[1] * (x1 - x3)
      + values[2] * (x2 - x1)
    ) / twice_area,
  )
####


def _primitive(
  state: CharacteristicState,
  total_pressure_Pa: float,
) -> tuple[float, float, float, float, float]:
  temperature_ratio = 1.0 / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  )
  pressure = total_pressure_Pa * temperature_ratio ** (
    state.gamma / (state.gamma - 1.0)
  )
  density = pressure / temperature_ratio
  sound_speed = sqrt(state.gamma * temperature_ratio)
  speed = state.mach * sound_speed
  velocity_x = speed * cos(state.theta_rad)
  velocity_y = speed * sin(state.theta_rad)
  total_energy = pressure / (state.gamma - 1.0) + 0.5 * density * speed * speed
  values = (density, pressure, velocity_x, velocity_y, total_energy)
  if not all(isfinite(value) for value in values):
    raise ValueError('terminal-wedge Euler primitive contains a non-finite value')
  ####
  return values
####


def _flux_dot_normal(
  primitive: tuple[float, float, float, float, float],
  normal_x: float,
  normal_y: float,
) -> tuple[float, float, float, float]:
  density, pressure, velocity_x, velocity_y, total_energy = primitive
  normal_speed = velocity_x * normal_x + velocity_y * normal_y
  return (
    density * normal_speed,
    density * velocity_x * normal_speed + pressure * normal_x,
    density * velocity_y * normal_speed + pressure * normal_y,
    (total_energy + pressure) * normal_speed,
  )
####


def _cell_euler_residual(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
) -> float:
  if len(vertices) != len(states) or len(vertices) != len(pressures):
    raise ValueError('terminal-wedge vertices, states, and pressures must align')
  ####
  if len(vertices) < 3:
    raise ValueError('terminal-wedge Euler residual requires a polygon')
  ####
  signed_area = 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(vertices, (*vertices[1:], vertices[0]))
  )
  if not isfinite(signed_area) or abs(signed_area) <= 1.0e-24:
    raise ValueError('terminal-wedge Euler residual requires a non-degenerate cell')
  ####
  orientation = 1.0 if signed_area > 0.0 else -1.0
  primitives = tuple(
    _primitive(state, pressure)
    for state, pressure in zip(states, pressures, strict=True)
  )
  residual = [0.0, 0.0, 0.0, 0.0]
  scale = 0.0
  for index, (first, second) in enumerate(
    zip(vertices, (*vertices[1:], vertices[0]))
  ):
    dx = second[0] - first[0]
    dy = second[1] - first[1]
    length = hypot(dx, dy)
    if not isfinite(length) or length <= 0.0:
      raise ValueError(f'terminal-wedge Euler edge {index} has zero length')
    ####
    normal_x = orientation * dy / length
    normal_y = -orientation * dx / length
    first_flux = _flux_dot_normal(primitives[index], normal_x, normal_y)
    second_flux = _flux_dot_normal(
      primitives[(index + 1) % len(primitives)],
      normal_x,
      normal_y,
    )
    for component in range(4):
      residual[component] += 0.5 * length * (
        first_flux[component] + second_flux[component]
      )
    ####
    scale += length * max(
      1.0,
      max(abs(value) for value in first_flux),
      max(abs(value) for value in second_flux),
    )
  ####
  return sqrt(sum(value * value for value in residual)) / max(1.0, scale)
####


def _edge(
  edge_index: int,
  family: CharacteristicFamily,
  start: tuple[float, float],
  end: tuple[float, float],
  start_state: CharacteristicState,
  end_state: CharacteristicState,
  gradient: tuple[float, float],
) -> MocEulerAmbientFirstWedgeCharacteristicEdge | None:
  start_direction = start_state.direction(family)
  end_direction = end_state.direction(family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  direction_length = hypot(*average_direction)
  displacement = (end[0] - start[0], end[1] - start[1])
  edge_length = hypot(*displacement)
  if direction_length <= 0.0 or edge_length <= 0.0:
    return None
  ####
  unit_direction = (
    average_direction[0] / direction_length,
    average_direction[1] / direction_length,
  )
  forward_margin = (
    displacement[0] * unit_direction[0]
    + displacement[1] * unit_direction[1]
  )
  if forward_margin <= 0.0:
    return None
  ####
  alignment = abs(
    displacement[0] * unit_direction[1]
    - displacement[1] * unit_direction[0]
  ) / edge_length
  average_theta = 0.5 * (start_state.theta_rad + end_state.theta_rad)
  normal = (-sin(average_theta), cos(average_theta))
  normal_gradient = gradient[0] * normal[0] + gradient[1] * normal[1]
  average_mach = 0.5 * (start_state.mach + end_state.mach)
  gamma = 0.5 * (start_state.gamma + end_state.gamma)
  coefficient = -sqrt(max(average_mach * average_mach - 1.0, 0.0)) / (
    gamma * average_mach ** 3
  )
  signed_source = coefficient * normal_gradient * edge_length
  actual = (
    end_state.k_plus - start_state.k_plus
    if family is CharacteristicFamily.PLUS
    else end_state.k_minus - start_state.k_minus
  )
  return MocEulerAmbientFirstWedgeCharacteristicEdge(
    edge_index=edge_index,
    family=family,
    start_vertex=start,
    end_vertex=end,
    edge_length_m=edge_length,
    forward_margin_m=forward_margin,
    alignment_residual=alignment,
    k_residual=abs(actual),
    entropy_source_prediction=abs(signed_source),
    compatibility_residual=abs(actual - signed_source),
  )
####


def solve_euler_ambient_first_wedge_characteristic_remesh(
  source_field: MocEulerAmbientPhysicalFieldResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeCharacteristicResult:
  """Build one solver-owned characteristic terminal-wedge candidate.

  The terminal node is reflected to the centerline with its ``C-``
  characteristic.  The resulting triangle uses the existing shock-to-node
  ``C+`` edge, the newly solved node-to-axis ``C-`` edge, and the axis as its
  closing boundary.  Total pressure on the reflected edge is carried from
  the terminal node; it is never reset to the upstream shock value.
  """

  if not isinstance(source_field, MocEulerAmbientPhysicalFieldResult):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.INVALID_INPUT,
      None,
      message='source_field must be a MocEulerAmbientPhysicalFieldResult',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.INVALID_INPUT,
      source_field,
      message='terminal-wedge tolerances must be numeric',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  common = {
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
  }
  if not (
    source_field.converged
    and source_field.field is not None
    and source_field.physical_closure_verified
    and source_field.state_sampling_available
  ):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.FIELD_REQUIRED,
      source_field,
      message=(
        'terminal-wedge characteristic remesh requires a converged '
        'ambient-closed field with a bounded state sampler'
      ),
      **common,
    )
  ####
  field = source_field.field
  wedge_indices = tuple(
    index
    for index, cell in enumerate(field.cells)
    if cell.cell_kind == 'post-shock-ambient-centerline-triangle'
  )
  if len(wedge_indices) != 1:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.WEDGE_REQUIRED,
      source_field,
      message=(
        'terminal-wedge characteristic remesh requires exactly one '
        'post-shock-ambient-centerline-triangle source cell'
      ),
      **common,
    )
  ####
  source_cell_index = wedge_indices[0]
  source_cell = field.cells[source_cell_index]
  try:
    original_vertices = tuple(
      _finite_point(point, 'source first-wedge vertices')
      for point in source_cell.vertices_xr_m
    )
  except ValueError as error:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.WEDGE_REQUIRED,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      message=str(error),
      **common,
    )
  ####
  if len(original_vertices) != 3:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.WEDGE_REQUIRED,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      message='terminal-wedge source cell must be triangular',
      **common,
    )
  ####
  axis_vertices = tuple(
    point for point in original_vertices
    if abs(point[1]) <= position_tolerance
  )
  off_axis_vertices = tuple(
    point for point in original_vertices
    if abs(point[1]) > position_tolerance
  )
  if len(axis_vertices) != 2 or len(off_axis_vertices) != 1:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.WEDGE_REQUIRED,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      message=(
        'terminal-wedge source cell must have two axis vertices and one '
        'off-axis characteristic vertex'
      ),
      **common,
  )
  ####
  shock_endpoint = min(axis_vertices, key=lambda point: point[0])
  terminal_node_point = off_axis_vertices[0]
  shock_states = field.post_shock_boundary_states
  shock_pressures = field.post_shock_boundary_total_pressure_Pa
  if not shock_states or len(shock_states) != len(shock_pressures):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.FIELD_REQUIRED,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      message='terminal-wedge source field is missing shock state/pressure data',
      **common,
    )
  ####
  shock_state = shock_states[-1]
  shock_pressure = float(shock_pressures[-1])
  if hypot(
    shock_state.x_m - shock_endpoint[0],
    shock_state.y_m - shock_endpoint[1],
  ) > position_tolerance:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.FIELD_REQUIRED,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      message='terminal shock state does not match the source wedge endpoint',
      **common,
    )
  ####
  terminal_state = field.state_at(
    terminal_node_point,
    position_tolerance_m=position_tolerance,
  )
  terminal_pressure = field.total_pressure_at(
    terminal_node_point,
    position_tolerance_m=position_tolerance,
  )
  if terminal_state is None or terminal_pressure is None:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.FIELD_REQUIRED,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      message='terminal wedge node has no bounded state/pressure sample',
      **common,
    )
  ####
  terminal_pressure = float(terminal_pressure)
  try:
    reflection = centerline_characteristic_point(
      terminal_state,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=residual_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.REFLECTION_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      message=f'terminal C- reflection raised: {error}',
      **common,
    )
  ####
  if not reflection.converged or reflection.point_m is None or reflection.state is None:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.REFLECTION_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      reflection_result=reflection,
      message=f'terminal C- reflection failed: {reflection.message}',
      **common,
    )
  ####
  reflected_axis_point = _finite_point(
    reflection.point_m,
    'reflected terminal axis point',
  )
  reflected_axis_state = reflection.state
  if (
    reflected_axis_point[0] <= shock_endpoint[0] + position_tolerance
    or reflected_axis_point[0] <= terminal_node_point[0] + position_tolerance
    or abs(reflected_axis_point[1]) > position_tolerance
    or abs(reflected_axis_state.theta_rad) > residual_tolerance
  ):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.REFLECTION_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      reflection_result=reflection,
      message=(
        'terminal C- reflection did not produce a downstream centerline '
        'endpoint'
      ),
      **common,
    )
  ####
  vertices = (shock_endpoint, terminal_node_point, reflected_axis_point)
  states = (shock_state, terminal_state, reflected_axis_state)
  pressures = (shock_pressure, terminal_pressure, terminal_pressure)
  gradient = _log_pressure_gradient(vertices, pressures)
  if gradient is None:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      vertices=vertices,
      states=states,
      pressures=pressures,
      reflection_result=reflection,
      message='terminal-wedge pressure gradient is not finite and non-degenerate',
      **common,
    )
  ####
  edges = tuple(
    edge
    for edge in (
      _edge(
        0,
        CharacteristicFamily.PLUS,
        vertices[0],
        vertices[1],
        states[0],
        states[1],
        gradient,
      ),
      _edge(
        1,
        CharacteristicFamily.MINUS,
        vertices[1],
        vertices[2],
        states[1],
        states[2],
        gradient,
      ),
    )
    if edge is not None
  )
  maximum_alignment = max(
    (edge.alignment_residual for edge in edges),
    default=None,
  )
  minimum_forward = min(
    (edge.forward_margin_m for edge in edges),
    default=None,
  )
  maximum_k = max((edge.k_residual for edge in edges), default=None)
  maximum_entropy = max(
    (edge.compatibility_residual for edge in edges),
    default=None,
  )
  characteristic_geometry_verified = bool(
    len(edges) == 2
    and maximum_alignment is not None
    and maximum_alignment <= alignment_tolerance
    and minimum_forward is not None
    and minimum_forward > position_tolerance
    and abs(shock_endpoint[1]) <= position_tolerance
    and abs(reflected_axis_point[1]) <= position_tolerance
    and abs(shock_state.theta_rad) <= residual_tolerance
    and abs(reflected_axis_state.theta_rad) <= residual_tolerance
  )
  variable_entropy_verified = bool(
    characteristic_geometry_verified
    and maximum_entropy is not None
    and maximum_entropy <= residual_tolerance
  )
  try:
    cell = MocCharacteristicCell(
      cell_index=0,
      cell_kind='post-shock-ambient-terminal-characteristic-wedge',
      vertices_xr_m=vertices,
      centerline_indices=(),
      boundary_indices=(),
    )
    cell_sample = MocEulerAmbientFirstWedgeCellSample(
      vertices_xr_m=vertices,
      states=states,
      total_pressure_Pa=pressures,
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      vertices=vertices,
      states=states,
      pressures=pressures,
      reflection_result=reflection,
      characteristic_edges=edges,
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_entropy,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      message=f'terminal-wedge cell geometry failed: {error}',
      **common,
    )
  ####
  topology = validate_moc_mesh((cell,))
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.TOPOLOGY_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      vertices=vertices,
      states=states,
      pressures=pressures,
      cell=cell,
      cell_sample=cell_sample,
      topology=topology,
      reflection_result=reflection,
      characteristic_edges=edges,
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_entropy,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      message=f'terminal-wedge topology failed: {topology.message}',
      **common,
    )
  ####
  try:
    cell_residual = _cell_euler_residual(vertices, states, pressures)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicStatus.EULER_RESIDUAL_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      vertices=vertices,
      states=states,
      pressures=pressures,
      cell=cell,
      cell_sample=cell_sample,
      topology=topology,
      reflection_result=reflection,
      characteristic_edges=edges,
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_entropy,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      message=f'terminal-wedge Euler residual reconstruction failed: {error}',
      **common,
    )
  ####
  cell_residual_verified = bool(cell_residual <= cell_tolerance)
  if not characteristic_geometry_verified:
    status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .CHARACTERISTIC_GEOMETRY_FAILURE
    )
    message = (
      'solver-owned terminal wedge did not retain two forward aligned '
      'characteristic edges'
    )
  elif not variable_entropy_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicStatus.ENTROPY_FAILURE
    message = (
      'terminal characteristic geometry is locally aligned, but the carried '
      'total-pressure gradient is not satisfied by the isentropic K+/K- '
      'transport; an entropy-carrying remesh is still required'
    )
  elif not cell_residual_verified:
    status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus.EULER_RESIDUAL_FAILURE
    )
    message = (
      'terminal characteristic wedge Euler residual exceeds the local '
      'acceptance tolerance'
    )
  else:
    status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .CONVERGED_CHARACTERISTIC_WEDGE
    )
    message = (
      'solver-owned terminal characteristic wedge passed local geometry, '
      'entropy, and Euler residual gates; global physical closure remains '
      'blocked'
    )
  ####
  if not cell_residual_verified:
    message += f' (cell Euler residual={cell_residual})'
  ####
  return MocEulerAmbientFirstWedgeCharacteristicResult(
    status=status,
    source_field=source_field,
    source_cell_index=source_cell_index,
    source_cell_kind=source_cell.cell_kind,
    original_vertices_xr_m=original_vertices,
    vertices_xr_m=vertices,
    states=states,
    total_pressure_Pa=pressures,
    cell=cell,
    cell_sample=cell_sample,
    topology=topology,
    reflection_result=reflection,
    characteristic_edges=edges,
    maximum_edge_alignment_residual=maximum_alignment,
    minimum_forward_margin_m=minimum_forward,
    maximum_k_residual=maximum_k,
    maximum_entropy_compatibility_residual=maximum_entropy,
    cell_euler_residual=cell_residual,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_verified,
    cell_euler_residual_verified=cell_residual_verified,
    **common,
    message=message,
  )
####


class MocEulerAmbientFirstWedgeCharacteristicFieldStatus(str, Enum):
  """Outcome of the first-wedge and adjacent centerline-strip retile."""

  CONVERGED_LOCAL_RETILE = (
    'converged_euler_ambient_first_wedge_characteristic_field_retile'
  )
  INVALID_INPUT = 'invalid_input'
  TERMINAL_WEDGE_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_terminal_wedge_failure'
  )
  ADJACENT_CELL_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_adjacent_cell_failure'
  )
  CHARACTERISTIC_GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_geometry_failure'
  )
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_topology_failure'
  )
  ENTROPY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_entropy_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_euler_residual_failure'
  )
####


def _field_point_key(
  point: tuple[float, float],
  tolerance_m: float,
) -> tuple[int, int]:
  return round(point[0] / tolerance_m), round(point[1] / tolerance_m)
####


def _field_edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _field_point_key(first, tolerance_m)
  second_key = _field_point_key(second, tolerance_m)
  return (
    (first_key, second_key)
    if first_key <= second_key
    else (second_key, first_key)
  )
####


def _field_boundary_paths_verified(
  cells: tuple[MocCharacteristicCell, ...],
  paths: tuple[tuple[tuple[float, float], ...], ...],
  tolerance_m: float,
) -> bool:
  edge_counts: dict[
    tuple[tuple[int, int], tuple[int, int]],
    int,
  ] = {}
  for cell in cells:
    vertices = tuple(cell.vertices_xr_m)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      edge = _field_edge_key(first, second, tolerance_m)
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
    ####
  ####
  return all(
    all(
      edge_counts.get(_field_edge_key(first, second, tolerance_m), 0) == 1
      for first, second in zip(path, path[1:])
    )
    for path in paths
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicFieldResult:
  """A solver-owned local field retile below physical chain promotion.

  The returned ``retiled_field`` retains the candidate geometry and all
  untouched source cells for inspection.  Its status is intentionally set to
  ``INVARIANT_FAILURE`` even when the local retile is topologically sound;
  this prevents the ordinary field sampler and chain adapters from treating
  an entropy-incomplete local patch as an accepted upstream domain.
  """

  status: MocEulerAmbientFirstWedgeCharacteristicFieldStatus
  source_field: MocEulerAmbientPhysicalFieldResult | None
  terminal_wedge: MocEulerAmbientFirstWedgeCharacteristicResult | None
  retiled_field: MocPhysicalPostShockFieldResult | None
  replaced_cell_indices: tuple[int, ...]
  replaced_centerline_index: int | None
  original_centerline_point: tuple[float, float] | None
  retiled_centerline_point: tuple[float, float] | None
  topology: MocTopologyResult
  retiled_field_topology_verified: bool
  boundary_paths_verified: bool
  terminal_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  cell_euler_residual_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  position_tolerance_m: float = 1.0e-10
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeCharacteristicFieldStatus'
      )
    ####
    if self.source_field is not None and not isinstance(
      self.source_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'source_field must be a MocEulerAmbientPhysicalFieldResult or None'
      )
    ####
    if self.terminal_wedge is not None and not isinstance(
      self.terminal_wedge,
      MocEulerAmbientFirstWedgeCharacteristicResult,
    ):
      raise TypeError(
        'terminal_wedge must be a '
        'MocEulerAmbientFirstWedgeCharacteristicResult or None'
      )
    ####
    if self.retiled_field is not None and not isinstance(
      self.retiled_field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError(
        'retiled_field must be a MocPhysicalPostShockFieldResult or None'
      )
    ####
    replaced_indices = tuple(self.replaced_cell_indices)
    if any(
      isinstance(index, bool) or not isinstance(index, int) or index < 0
      for index in replaced_indices
    ):
      raise ValueError('replaced_cell_indices must contain nonnegative integers')
    ####
    if len(set(replaced_indices)) != len(replaced_indices):
      raise ValueError('replaced_cell_indices must not contain duplicates')
    ####
    object.__setattr__(self, 'replaced_cell_indices', replaced_indices)
    if self.replaced_centerline_index is not None and (
      isinstance(self.replaced_centerline_index, bool)
      or not isinstance(self.replaced_centerline_index, int)
      or self.replaced_centerline_index < 0
    ):
      raise ValueError(
        'replaced_centerline_index must be a nonnegative integer or None'
      )
    ####
    for name in ('original_centerline_point', 'retiled_centerline_point'):
      point = getattr(self, name)
      if point is None:
        continue
      ####
      object.__setattr__(self, name, _finite_point(point, name))
    ####
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    for name in (
      'retiled_field_topology_verified',
      'boundary_paths_verified',
      'terminal_geometry_verified',
      'variable_entropy_compatibility_verified',
      'cell_euler_residual_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError(
        'a local characteristic field retile cannot claim physical closure'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'a local characteristic field retile cannot claim production validity'
      )
    ####
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the local retile passed every local solver gate."""

    return self.status is (
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus
      .CONVERGED_LOCAL_RETILE
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.retiled_field is not None
      and self.retiled_field.status is MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
      and self.retiled_field_topology_verified
      and self.boundary_paths_verified
      and self.terminal_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.cell_euler_residual_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def physical_chain_cell_count(self) -> int:
    """Number of physical chain cells contributed by this retile."""

    return 0
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the hard stop between the retiled field and a chain."""

    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocEulerAmbientFirstWedgeCharacteristicFieldStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'solver-owned first-wedge field retile remains below physical chain '
        'promotion; entropy-carrying reflected continuation, conservative '
        'field closure, and external validation are still required'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'characteristic_field_retile_status': self.status.value,
        'replaced_cell_indices': self.replaced_cell_indices,
        'replaced_centerline_index': self.replaced_centerline_index,
        'retiled_field_topology_verified': self.retiled_field_topology_verified,
        'boundary_paths_verified': self.boundary_paths_verified,
        'terminal_geometry_verified': self.terminal_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'multi-cell-entropy-carrying-reflected-field-continuation-and-'
          'independent-conservative-audit'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_field_status': (
        None if self.source_field is None else self.source_field.status.value
      ),
      'terminal_wedge_status': (
        None if self.terminal_wedge is None else self.terminal_wedge.status.value
      ),
      'retiled_field_status': (
        None if self.retiled_field is None else self.retiled_field.status.value
      ),
      'replaced_cell_indices': self.replaced_cell_indices,
      'replaced_centerline_index': self.replaced_centerline_index,
      'original_centerline_point': self.original_centerline_point,
      'retiled_centerline_point': self.retiled_centerline_point,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'checks': {
        'retiled_field_topology_verified': self.retiled_field_topology_verified,
        'boundary_paths_verified': self.boundary_paths_verified,
        'terminal_geometry_verified': self.terminal_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'retiled_field': (
        None if self.retiled_field is None else self.retiled_field.as_report()
      ),
      'terminal_wedge': (
        None
        if self.terminal_wedge is None
        else self.terminal_wedge.as_report()
      ),
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': (
        self.characteristic_residual_tolerance
      ),
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'claim_status': (
        'solver-owned-local-first-wedge-field-retile; complete entropy '
        'transport, reflected free-boundary continuation, and external '
        'validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _field_failure(
  status: MocEulerAmbientFirstWedgeCharacteristicFieldStatus,
  source_field: MocEulerAmbientPhysicalFieldResult | None,
  *,
  terminal_wedge: MocEulerAmbientFirstWedgeCharacteristicResult | None = None,
  retiled_field: MocPhysicalPostShockFieldResult | None = None,
  replaced_cell_indices: tuple[int, ...] = (),
  replaced_centerline_index: int | None = None,
  original_centerline_point: tuple[float, float] | None = None,
  retiled_centerline_point: tuple[float, float] | None = None,
  topology: MocTopologyResult | None = None,
  retiled_field_topology_verified: bool = False,
  boundary_paths_verified: bool = False,
  terminal_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  cell_euler_residual_verified: bool = False,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  message: str,
) -> MocEulerAmbientFirstWedgeCharacteristicFieldResult:
  return MocEulerAmbientFirstWedgeCharacteristicFieldResult(
    status=status,
    source_field=source_field,
    terminal_wedge=terminal_wedge,
    retiled_field=retiled_field,
    replaced_cell_indices=replaced_cell_indices,
    replaced_centerline_index=replaced_centerline_index,
    original_centerline_point=original_centerline_point,
    retiled_centerline_point=retiled_centerline_point,
    topology=_empty_topology() if topology is None else topology,
    retiled_field_topology_verified=retiled_field_topology_verified,
    boundary_paths_verified=boundary_paths_verified,
    terminal_geometry_verified=terminal_geometry_verified,
    variable_entropy_compatibility_verified=(
      variable_entropy_compatibility_verified
    ),
    cell_euler_residual_verified=cell_euler_residual_verified,
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def remesh_euler_ambient_first_wedge_characteristic_field(
  source_field: MocEulerAmbientPhysicalFieldResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeCharacteristicFieldResult:
  """Retile one corrected terminal wedge and its adjacent strip.

  The source field is never mutated.  The returned field is a diagnostic
  snapshot with a non-converged physical-field status, so its mesh can be
  audited without exposing it to the normal continuation sampler.
  """

  if not isinstance(source_field, MocEulerAmbientPhysicalFieldResult):
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.INVALID_INPUT,
      None,
      message='source_field must be a MocEulerAmbientPhysicalFieldResult',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.INVALID_INPUT,
      source_field,
      message='characteristic field retile tolerances must be numeric',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  common = {
    'position_tolerance_m': position_tolerance,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
  }
  terminal_wedge = solve_euler_ambient_first_wedge_characteristic_remesh(
    source_field,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    cell_residual_tolerance=cell_tolerance,
  )
  if terminal_wedge.cell is None or len(terminal_wedge.vertices_xr_m) != 3:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TERMINAL_WEDGE_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      message=(
        'characteristic field retile requires a terminal-wedge candidate '
        'with one reconstructed triangular cell'
      ),
      **common,
    )
  ####
  field = source_field.field
  if field is None or terminal_wedge.source_cell_index is None:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TERMINAL_WEDGE_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      message='terminal-wedge candidate did not retain its source field cell',
      **common,
    )
  ####
  source_cell_index = terminal_wedge.source_cell_index
  if not 0 <= source_cell_index < len(field.cells):
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TERMINAL_WEDGE_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      message='terminal-wedge source cell index is outside the physical field',
      **common,
    )
  ####
  source_cell = field.cells[source_cell_index]
  original_vertices = tuple(
    _finite_point(point, 'terminal-wedge source cell vertex')
    for point in source_cell.vertices_xr_m
  )
  axis_vertices = tuple(
    point for point in original_vertices if abs(point[1]) <= position_tolerance
  )
  off_axis_vertices = tuple(
    point for point in original_vertices if abs(point[1]) > position_tolerance
  )
  reflection = terminal_wedge.reflection_result
  if len(axis_vertices) != 2 or len(off_axis_vertices) != 1 or reflection is None:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TERMINAL_WEDGE_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      message=(
        'terminal-wedge source cell must expose two axis vertices, one '
        'off-axis vertex, and a reflected C- result'
      ),
      **common,
    )
  ####
  original_centerline_point = max(axis_vertices, key=lambda point: point[0])
  off_axis_point = off_axis_vertices[0]
  retiled_centerline_point = _finite_point(
    reflection.point_m,
    'reflected terminal centerline point',
  )
  reflected_vertex_indices = tuple(
    index
    for index, point in enumerate(terminal_wedge.vertices_xr_m)
    if hypot(
      point[0] - retiled_centerline_point[0],
      point[1] - retiled_centerline_point[1],
    ) <= position_tolerance
  )
  off_axis_matches = tuple(
    index
    for index, point in enumerate(terminal_wedge.vertices_xr_m)
    if hypot(point[0] - off_axis_point[0], point[1] - off_axis_point[1])
    <= position_tolerance
  )
  terminal_geometry_verified = bool(
    reflection.converged
    and len(reflected_vertex_indices) == 1
    and len(off_axis_matches) == 1
    and abs(retiled_centerline_point[1]) <= position_tolerance
  )
  if not terminal_geometry_verified:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      original_centerline_point=original_centerline_point,
      retiled_centerline_point=retiled_centerline_point,
      terminal_geometry_verified=False,
      message='reflected terminal characteristic is not a usable axis vertex',
      **common,
    )
  ####
  adjacent_indices = tuple(
    index
    for index, cell in enumerate(field.cells)
    if (
      index != source_cell_index
      and cell.cell_kind == 'post-shock-ambient-centerline-strip'
      and any(
        hypot(point[0] - original_centerline_point[0], point[1] - original_centerline_point[1])
        <= position_tolerance
        for point in cell.vertices_xr_m
      )
      and any(
        hypot(point[0] - off_axis_point[0], point[1] - off_axis_point[1])
        <= position_tolerance
        for point in cell.vertices_xr_m
      )
    )
  )
  if len(adjacent_indices) != 1:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.ADJACENT_CELL_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      original_centerline_point=original_centerline_point,
      retiled_centerline_point=retiled_centerline_point,
      terminal_geometry_verified=True,
      message=(
        'characteristic field retile requires exactly one adjacent '
        'post-shock centerline strip containing the original terminal axis '
        'point and terminal off-axis node'
      ),
      **common,
    )
  ####
  adjacent_index = adjacent_indices[0]
  adjacent_cell = field.cells[adjacent_index]
  adjacent_axis_matches = tuple(
    index
    for index, point in enumerate(adjacent_cell.vertices_xr_m)
    if hypot(
      point[0] - original_centerline_point[0],
      point[1] - original_centerline_point[1],
    ) <= position_tolerance
  )
  if len(adjacent_axis_matches) != 1:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.ADJACENT_CELL_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      replaced_cell_indices=(source_cell_index, adjacent_index),
      original_centerline_point=original_centerline_point,
      retiled_centerline_point=retiled_centerline_point,
      terminal_geometry_verified=True,
      message='adjacent centerline strip has an ambiguous original axis vertex',
      **common,
    )
  ####
  retiled_adjacent_vertices = tuple(
    retiled_centerline_point
    if index == adjacent_axis_matches[0]
    else point
    for index, point in enumerate(adjacent_cell.vertices_xr_m)
  )
  retiled_terminal_cell = replace(
    terminal_wedge.cell,
    cell_index=source_cell.cell_index,
  )
  retiled_adjacent_cell = replace(
    adjacent_cell,
    vertices_xr_m=retiled_adjacent_vertices,
    cell_kind=f'{adjacent_cell.cell_kind}-retiled',
  )
  retiled_cells = tuple(
    retiled_terminal_cell
    if index == source_cell_index
    else retiled_adjacent_cell
    if index == adjacent_index
    else cell
    for index, cell in enumerate(field.cells)
  )
  topology = validate_moc_mesh(retiled_cells)
  retiled_field_topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  centerline_matches = tuple(
    index
    for index, point in enumerate(field.centerline_boundary_points_m)
    if hypot(
      point[0] - original_centerline_point[0],
      point[1] - original_centerline_point[1],
    ) <= position_tolerance
  )
  if len(centerline_matches) != 1:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.ADJACENT_CELL_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      replaced_cell_indices=(source_cell_index, adjacent_index),
      original_centerline_point=original_centerline_point,
      retiled_centerline_point=retiled_centerline_point,
      topology=topology,
      retiled_field_topology_verified=retiled_field_topology_verified,
      terminal_geometry_verified=True,
      message=(
        'characteristic field retile requires exactly one matching source '
        'centerline boundary sample'
      ),
      **common,
    )
  ####
  centerline_index = centerline_matches[0]
  retiled_centerline_points = tuple(
    retiled_centerline_point
    if index == centerline_index
    else point
    for index, point in enumerate(field.centerline_boundary_points_m)
  )
  reflected_index = reflected_vertex_indices[0]
  retiled_centerline_states = tuple(
    terminal_wedge.states[reflected_index]
    if index == centerline_index
    else state
    for index, state in enumerate(field.centerline_boundary_states)
  )
  retiled_centerline_pressures = tuple(
    terminal_wedge.total_pressure_Pa[reflected_index]
    if index == centerline_index
    else pressure
    for index, pressure in enumerate(field.centerline_boundary_total_pressure_Pa)
  )
  centerline_order_verified = bool(
    all(
      abs(point[1]) <= position_tolerance
      and state.x_m == point[0]
      and state.y_m == point[1]
      for point, state in zip(
        retiled_centerline_points,
        retiled_centerline_states,
        strict=True,
      )
    )
    and all(
      second[0] > first[0] + position_tolerance
      for first, second in zip(
        retiled_centerline_points,
        retiled_centerline_points[1:],
      )
    )
  )
  if not centerline_order_verified:
    return _field_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TOPOLOGY_FAILURE,
      source_field,
      terminal_wedge=terminal_wedge,
      replaced_cell_indices=(source_cell_index, adjacent_index),
      replaced_centerline_index=centerline_index,
      original_centerline_point=original_centerline_point,
      retiled_centerline_point=retiled_centerline_point,
      topology=topology,
      retiled_field_topology_verified=retiled_field_topology_verified,
      terminal_geometry_verified=True,
      message='retiled centerline boundary is not an ordered axis trace',
      **common,
    )
  ####
  boundary_paths_verified = _field_boundary_paths_verified(
    retiled_cells,
    (
      tuple(field.shock_boundary_points_m),
      tuple(field.ambient_boundary_points_m),
      retiled_centerline_points,
    ),
    position_tolerance,
  )
  retiled_field = replace(
    field,
    status=MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE,
    cells=retiled_cells,
    topology=topology,
    centerline_boundary_points_m=retiled_centerline_points,
    centerline_boundary_states=retiled_centerline_states,
    centerline_boundary_total_pressure_Pa=retiled_centerline_pressures,
    message=(
      'solver-owned terminal characteristic retile retained for audit; '
      'physical field status intentionally remains invariant_failure until '
      'entropy-carrying continuation and conservative closure pass'
    ),
  )
  if not retiled_field_topology_verified or not boundary_paths_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TOPOLOGY_FAILURE
    message = (
      'terminal characteristic geometry was retiled, but the complete raw '
      'field topology or physical boundary paths failed validation'
    )
  elif not terminal_wedge.characteristic_geometry_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.CHARACTERISTIC_GEOMETRY_FAILURE
    message = 'retiled field retained a terminal wedge with failed characteristic geometry'
  elif not terminal_wedge.variable_entropy_compatibility_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.ENTROPY_FAILURE
    message = (
      'retiled field has the corrected local topology, but variable entropy '
      'compatibility still fails on the reflected terminal wedge'
    )
  elif not terminal_wedge.cell_euler_residual_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.EULER_RESIDUAL_FAILURE
    message = (
      'retiled field has characteristic entropy compatibility, but the '
      'terminal wedge conservative residual remains above tolerance'
    )
  else:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.CONVERGED_LOCAL_RETILE
    message = (
      'retiled first wedge and adjacent strip passed local geometry, entropy, '
      'Euler, topology, and boundary-path gates; physical chain promotion '
      'remains blocked'
    )
  ####
  return _field_failure(
    status,
    source_field,
    terminal_wedge=terminal_wedge,
    retiled_field=retiled_field,
    replaced_cell_indices=(source_cell_index, adjacent_index),
    replaced_centerline_index=centerline_index,
    original_centerline_point=original_centerline_point,
    retiled_centerline_point=retiled_centerline_point,
    topology=topology,
    retiled_field_topology_verified=retiled_field_topology_verified,
    boundary_paths_verified=boundary_paths_verified,
    terminal_geometry_verified=terminal_geometry_verified,
    variable_entropy_compatibility_verified=(
      terminal_wedge.variable_entropy_compatibility_verified
    ),
    cell_euler_residual_verified=terminal_wedge.cell_euler_residual_verified,
    message=message,
    **common,
  )
####
