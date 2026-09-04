"""Bounded entropy-carrying terminal-wedge trial for the Euler MOC lane.

The ordinary terminal-wedge reconstruction keeps the incoming shock and
ambient characteristic states but copies the off-axis total pressure onto the
reflected axis point.  That is useful as a topology probe, but it is not a
valid entropy transport rule: the axis point belongs to the centerline
streamline and must retain the shock-endpoint total pressure.

This module solves the smallest coupled local trial that keeps those two
lineages distinct.  The off-axis state remains connected to the ambient
``C-`` source, the axis state carries the shock-endpoint total pressure, and
the reflected ``C-`` state is adjusted until the two terminal characteristic
edges satisfy the generalized variable-entropy compatibility source.  The
trial deliberately stops before physical promotion when its coarse cell
Euler residual is still too large or when the surrounding reflected field is
not solved.  It is therefore a solver-owned evidence seam, not a replacement
for the accepted fast/basic provider or a production shock-cell solver.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import cos, hypot, isfinite, log, sin, sqrt
from typing import Any

import numpy as np

from exhaust_plume.geometry.contracts import Ray2D
from exhaust_plume.geometry.intersections import intersect_rays
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
from exhaust_plume.models.moc.euler_terminal_wedge import (
  MocEulerAmbientFirstWedgeCharacteristicEdge,
  MocEulerAmbientFirstWedgeCharacteristicResult,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCarryStatus',
  'MocEulerAmbientFirstWedgeEntropyCarryResult',
  'solve_euler_ambient_first_wedge_entropy_carry',
)


class MocEulerAmbientFirstWedgeEntropyCarryStatus(str, Enum):
  """Outcome of the bounded entropy-carrying terminal-wedge trial."""

  CONVERGED_LOCAL_ENTROPY_CARRY = (
    'converged_euler_ambient_first_wedge_local_entropy_carry'
  )
  INVALID_INPUT = 'invalid_input'
  CANDIDATE_REQUIRED = 'euler_ambient_first_wedge_entropy_candidate_required'
  AMBIENT_SOURCE_REQUIRED = (
    'euler_ambient_first_wedge_entropy_ambient_source_required'
  )
  SOLVER_FAILURE = 'euler_ambient_first_wedge_entropy_solver_failure'
  CHARACTERISTIC_GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_geometry_failure'
  )
  PRESSURE_LINEAGE_FAILURE = (
    'euler_ambient_first_wedge_entropy_pressure_lineage_failure'
  )
  ENTROPY_FAILURE = 'euler_ambient_first_wedge_entropy_compatibility_failure'
  EULER_RESIDUAL_FAILURE = 'euler_ambient_first_wedge_entropy_euler_residual_failure'
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


def _average_direction(
  first: CharacteristicState,
  second: CharacteristicState,
  family: CharacteristicFamily,
) -> tuple[float, float] | None:
  first_direction = first.direction(family)
  second_direction = second.direction(family)
  direction = (
    first_direction[0] + second_direction[0],
    first_direction[1] + second_direction[1],
  )
  length = hypot(*direction)
  if not isfinite(length) or length <= 0.0:
    return None
  ####
  return direction[0] / length, direction[1] / length
####


def _edge_metrics(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  start_index: int,
  end_index: int,
  family: CharacteristicFamily,
) -> tuple[float, float, float, float, float] | None:
  direction = _average_direction(
    states[start_index],
    states[end_index],
    family,
  )
  if direction is None:
    return None
  ####
  displacement = (
    vertices[end_index][0] - vertices[start_index][0],
    vertices[end_index][1] - vertices[start_index][1],
  )
  edge_length = hypot(*displacement)
  if not isfinite(edge_length) or edge_length <= 0.0:
    return None
  ####
  forward_margin = displacement[0] * direction[0] + displacement[1] * direction[1]
  alignment = abs(
    displacement[0] * direction[1] - displacement[1] * direction[0]
  ) / edge_length
  gradient = _log_pressure_gradient(vertices, pressures)
  if gradient is None:
    return None
  ####
  average_theta = 0.5 * (
    states[start_index].theta_rad + states[end_index].theta_rad
  )
  normal = (-sin(average_theta), cos(average_theta))
  normal_gradient = gradient[0] * normal[0] + gradient[1] * normal[1]
  average_mach = 0.5 * (
    states[start_index].mach + states[end_index].mach
  )
  gamma = 0.5 * (
    states[start_index].gamma + states[end_index].gamma
  )
  coefficient = -sqrt(max(average_mach * average_mach - 1.0, 0.0)) / (
    gamma * average_mach ** 3
  )
  signed_source = coefficient * normal_gradient * edge_length
  actual = (
    states[end_index].k_plus - states[start_index].k_plus
    if family is CharacteristicFamily.PLUS
    else states[end_index].k_minus - states[start_index].k_minus
  )
  return alignment, forward_margin, edge_length, actual, signed_source
####


def _cell_euler_residual(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
) -> float:
  """Return the normalized coarse-cell Euler flux residual."""

  if len(vertices) != len(states) or len(vertices) != len(pressures):
    raise ValueError('entropy-carrying cell samples must align')
  ####
  signed_area = 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(vertices, (*vertices[1:], vertices[0]))
  )
  if not isfinite(signed_area) or abs(signed_area) <= 1.0e-24:
    raise ValueError('entropy-carrying cell must have nonzero area')
  ####
  orientation = 1.0 if signed_area > 0.0 else -1.0

  def primitive(
    state: CharacteristicState,
    total_pressure: float,
  ) -> tuple[float, float, float, float, float]:
    temperature_ratio = 1.0 / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    )
    pressure = total_pressure * temperature_ratio ** (
      state.gamma / (state.gamma - 1.0)
    )
    density = pressure / temperature_ratio
    sound_speed = sqrt(state.gamma * temperature_ratio)
    speed = state.mach * sound_speed
    velocity_x = speed * cos(state.theta_rad)
    velocity_y = speed * sin(state.theta_rad)
    energy = pressure / (state.gamma - 1.0) + 0.5 * density * speed * speed
    values = (density, pressure, velocity_x, velocity_y, energy)
    if not all(isfinite(value) for value in values):
      raise ValueError('entropy-carrying primitive contains a non-finite value')
    ####
    return values
  ####

  def flux(
    values: tuple[float, float, float, float, float],
    normal_x: float,
    normal_y: float,
  ) -> tuple[float, float, float, float]:
    density, pressure, velocity_x, velocity_y, energy = values
    normal_speed = velocity_x * normal_x + velocity_y * normal_y
    return (
      density * normal_speed,
      density * velocity_x * normal_speed + pressure * normal_x,
      density * velocity_y * normal_speed + pressure * normal_y,
      (energy + pressure) * normal_speed,
    )
  ####

  primitives = tuple(
    primitive(state, pressure)
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
      raise ValueError('entropy-carrying cell has a zero-length edge')
    ####
    normal_x = orientation * dy / length
    normal_y = -orientation * dx / length
    first_flux = flux(primitives[index], normal_x, normal_y)
    second_flux = flux(
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


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryResult:
  """Auditable local entropy-carrying terminal-wedge trial."""

  status: MocEulerAmbientFirstWedgeEntropyCarryStatus
  source_candidate: MocEulerAmbientFirstWedgeCharacteristicResult | None
  source_field: MocEulerAmbientPhysicalFieldResult | None
  ambient_source_point: tuple[float, float] | None
  vertices_xr_m: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  total_pressure_Pa: tuple[float, ...]
  cell: MocCharacteristicCell | None
  cell_sample: MocEulerAmbientFirstWedgeCellSample | None
  topology: MocTopologyResult
  incoming_characteristic_alignment_residual: float | None
  incoming_forward_margin_m: float | None
  incoming_k_minus_residual: float | None
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdge, ...]
  maximum_edge_alignment_residual: float | None
  minimum_forward_margin_m: float | None
  maximum_k_residual: float | None
  maximum_entropy_compatibility_residual: float | None
  axis_total_pressure_Pa: float | None
  input_axis_total_pressure_Pa: float | None
  axis_streamline_pressure_residual_log: float | None
  cell_euler_residual: float | None
  solver_iterations: int
  incoming_characteristic_geometry_verified: bool
  pressure_lineage_verified: bool
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  axis_streamline_entropy_verified: bool
  cell_euler_residual_finite: bool
  cell_euler_residual_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  position_tolerance_m: float = 1.0e-10
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  pressure_lineage_tolerance: float = 1.0e-8
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientFirstWedgeEntropyCarryStatus):
      raise TypeError(
        'status must be a MocEulerAmbientFirstWedgeEntropyCarryStatus'
      )
    ####
    if self.source_candidate is not None and not isinstance(
      self.source_candidate,
      MocEulerAmbientFirstWedgeCharacteristicResult,
    ):
      raise TypeError(
        'source_candidate must be a '
        'MocEulerAmbientFirstWedgeCharacteristicResult or None'
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
    if self.ambient_source_point is not None:
      object.__setattr__(
        self,
        'ambient_source_point',
        _finite_point(self.ambient_source_point, 'ambient_source_point'),
      )
    ####
    vertices = tuple(
      _finite_point(point, 'vertices_xr_m') for point in self.vertices_xr_m
    )
    states = tuple(self.states)
    pressures = tuple(float(value) for value in self.total_pressure_Pa)
    if len(vertices) != len(states) or len(vertices) != len(pressures):
      raise ValueError('vertices, states, and total_pressure_Pa must align')
    ####
    if any(not isinstance(state, CharacteristicState) for state in states):
      raise TypeError('states must contain CharacteristicState values')
    ####
    if any(not isfinite(value) or value <= 0.0 for value in pressures):
      raise ValueError('total_pressure_Pa must contain finite positive values')
    ####
    if any(
      hypot(state.x_m - point[0], state.y_m - point[1]) > 1.0e-10
      for point, state in zip(vertices, states, strict=True)
    ):
      raise ValueError('states must lie on vertices')
    ####
    object.__setattr__(self, 'vertices_xr_m', vertices)
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
      'incoming_characteristic_alignment_residual',
      'incoming_forward_margin_m',
      'incoming_k_minus_residual',
      'maximum_edge_alignment_residual',
      'minimum_forward_margin_m',
      'maximum_k_residual',
      'maximum_entropy_compatibility_residual',
      'axis_total_pressure_Pa',
      'input_axis_total_pressure_Pa',
      'axis_streamline_pressure_residual_log',
      'cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or (
        numeric < 0.0 and name != 'axis_streamline_pressure_residual_log'
      ):
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.axis_streamline_pressure_residual_log is not None:
      object.__setattr__(
        self,
        'axis_streamline_pressure_residual_log',
        abs(self.axis_streamline_pressure_residual_log),
      )
    ####
    if (
      isinstance(self.solver_iterations, bool)
      or not isinstance(self.solver_iterations, int)
      or self.solver_iterations < 0
    ):
      raise ValueError('solver_iterations must be a nonnegative integer')
    ####
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
      'cell_residual_tolerance',
      'pressure_lineage_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'incoming_characteristic_geometry_verified',
      'pressure_lineage_verified',
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'axis_streamline_entropy_verified',
      'cell_euler_residual_finite',
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
      raise ValueError('a local entropy trial cannot claim physical closure')
    ####
    if self.production_claim_allowed:
      raise ValueError('a local entropy trial cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCarryStatus
      .CONVERGED_LOCAL_ENTROPY_CARRY
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.incoming_characteristic_geometry_verified
      and self.pressure_lineage_verified
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.axis_streamline_entropy_verified
      and self.cell_euler_residual_finite
      and self.cell_euler_residual_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocEulerAmbientFirstWedgeEntropyCarryStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'entropy-carrying terminal wedge remains below physical chain '
        'promotion; internal characteristic refinement, reflected free-boundary '
        'closure, and external validation are still required'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'entropy_carry_status': self.status.value,
        'incoming_characteristic_geometry_verified': (
          self.incoming_characteristic_geometry_verified
        ),
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'characteristic_geometry_verified': self.characteristic_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'axis_streamline_entropy_verified': self.axis_streamline_entropy_verified,
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'characteristic-subcell-refinement-with-internal-family-closure-'
          'and-reflected-free-boundary-coupling'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_candidate_status': (
        None
        if self.source_candidate is None
        else self.source_candidate.status.value
      ),
      'source_field_status': (
        None if self.source_field is None else self.source_field.status.value
      ),
      'ambient_source_point': self.ambient_source_point,
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
      'incoming_characteristic_alignment_residual': (
        self.incoming_characteristic_alignment_residual
      ),
      'incoming_forward_margin_m': self.incoming_forward_margin_m,
      'incoming_k_minus_residual': self.incoming_k_minus_residual,
      'characteristic_edges': [edge.as_report() for edge in self.characteristic_edges],
      'maximum_edge_alignment_residual': self.maximum_edge_alignment_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_k_residual': self.maximum_k_residual,
      'maximum_entropy_compatibility_residual': (
        self.maximum_entropy_compatibility_residual
      ),
      'axis_total_pressure_Pa': self.axis_total_pressure_Pa,
      'input_axis_total_pressure_Pa': self.input_axis_total_pressure_Pa,
      'axis_streamline_pressure_residual_log': (
        self.axis_streamline_pressure_residual_log
      ),
      'cell_euler_residual': self.cell_euler_residual,
      'solver_iterations': self.solver_iterations,
      'checks': {
        'incoming_characteristic_geometry_verified': (
          self.incoming_characteristic_geometry_verified
        ),
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'characteristic_geometry_verified': self.characteristic_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'axis_streamline_entropy_verified': self.axis_streamline_entropy_verified,
        'cell_euler_residual_finite': self.cell_euler_residual_finite,
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'claim_status': (
        'solver-owned-local-entropy-carrying-terminal-wedge-trial; internal '
        'characteristic refinement, reflected free-boundary closure, and '
        'external validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCarryStatus,
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult | None,
  source_field: MocEulerAmbientPhysicalFieldResult | None,
  *,
  ambient_source_point: tuple[float, float] | None = None,
  vertices: tuple[tuple[float, float], ...] = (),
  states: tuple[CharacteristicState, ...] = (),
  pressures: tuple[float, ...] = (),
  cell: MocCharacteristicCell | None = None,
  cell_sample: MocEulerAmbientFirstWedgeCellSample | None = None,
  topology: MocTopologyResult | None = None,
  incoming_characteristic_alignment_residual: float | None = None,
  incoming_forward_margin_m: float | None = None,
  incoming_k_minus_residual: float | None = None,
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdge, ...] = (),
  maximum_edge_alignment_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  maximum_k_residual: float | None = None,
  maximum_entropy_compatibility_residual: float | None = None,
  axis_total_pressure_Pa: float | None = None,
  input_axis_total_pressure_Pa: float | None = None,
  axis_streamline_pressure_residual_log: float | None = None,
  cell_euler_residual: float | None = None,
  solver_iterations: int = 0,
  incoming_characteristic_geometry_verified: bool = False,
  pressure_lineage_verified: bool = False,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  axis_streamline_entropy_verified: bool = False,
  cell_euler_residual_finite: bool = False,
  cell_euler_residual_verified: bool = False,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCarryResult:
  return MocEulerAmbientFirstWedgeEntropyCarryResult(
    status=status,
    source_candidate=candidate,
    source_field=source_field,
    ambient_source_point=ambient_source_point,
    vertices_xr_m=vertices,
    states=states,
    total_pressure_Pa=pressures,
    cell=cell,
    cell_sample=cell_sample,
    topology=_empty_topology() if topology is None else topology,
    incoming_characteristic_alignment_residual=(
      incoming_characteristic_alignment_residual
    ),
    incoming_forward_margin_m=incoming_forward_margin_m,
    incoming_k_minus_residual=incoming_k_minus_residual,
    characteristic_edges=characteristic_edges,
    maximum_edge_alignment_residual=maximum_edge_alignment_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    maximum_k_residual=maximum_k_residual,
    maximum_entropy_compatibility_residual=(
      maximum_entropy_compatibility_residual
    ),
    axis_total_pressure_Pa=axis_total_pressure_Pa,
    input_axis_total_pressure_Pa=input_axis_total_pressure_Pa,
    axis_streamline_pressure_residual_log=axis_streamline_pressure_residual_log,
    cell_euler_residual=cell_euler_residual,
    solver_iterations=solver_iterations,
    incoming_characteristic_geometry_verified=(
      incoming_characteristic_geometry_verified
    ),
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=(
      variable_entropy_compatibility_verified
    ),
    axis_streamline_entropy_verified=axis_streamline_entropy_verified,
    cell_euler_residual_finite=cell_euler_residual_finite,
    cell_euler_residual_verified=cell_euler_residual_verified,
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    message=message,
  )
####


@dataclass(frozen=True, slots=True)
class _EntropyTrialGeometry:
  vertices: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  pressures: tuple[float, ...]
  incoming_alignment: float
  incoming_forward_margin: float
  incoming_k_minus_residual: float
  incoming_edge_length: float
  outer_metrics: tuple[tuple[float, float, float, float, float], ...]
####


def _trial_geometry(
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult,
  ambient_point: tuple[float, float],
  ambient_state: CharacteristicState,
  *,
  theta_b: float,
  mach_d: float,
  position_tolerance_m: float,
  pressure_lineage_tolerance: float,
) -> _EntropyTrialGeometry | None:
  if len(candidate.vertices_xr_m) != 3 or len(candidate.states) != 3:
    return None
  ####
  if len(candidate.total_pressure_Pa) != 3:
    return None
  ####
  shock_state = candidate.states[0]
  shock_point = _finite_point(candidate.vertices_xr_m[0], 'shock point')
  shock_pressure = float(candidate.total_pressure_Pa[0])
  off_axis_pressure = float(candidate.total_pressure_Pa[1])
  if any(
    not isfinite(value) or value <= 0.0
    for value in (shock_pressure, off_axis_pressure)
  ):
    return None
  ####
  if abs(shock_state.gamma - ambient_state.gamma) > pressure_lineage_tolerance:
    return None
  ####
  nu_b = ambient_state.k_minus - float(theta_b)
  if not isfinite(nu_b) or nu_b <= 0.0:
    return None
  ####
  inversion = inverse_prandtl_meyer_angle_rad(nu_b, shock_state.gamma)
  if not inversion.converged or inversion.value is None:
    return None
  ####
  try:
    provisional_b = CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=float(theta_b),
      mach=float(inversion.value),
      gamma=shock_state.gamma,
    )
    provisional_d = CharacteristicState(
      x_m=0.0,
      y_m=0.0,
      theta_rad=0.0,
      mach=float(mach_d),
      gamma=shock_state.gamma,
    )
  except (TypeError, ValueError):
    return None
  ####
  plus_direction = _average_direction(
    shock_state,
    provisional_b,
    CharacteristicFamily.PLUS,
  )
  minus_incoming_direction = _average_direction(
    ambient_state,
    provisional_b,
    CharacteristicFamily.MINUS,
  )
  if plus_direction is None or minus_incoming_direction is None:
    return None
  ####
  try:
    intersection = intersect_rays(
      Ray2D(
        origin=np.asarray(shock_point, dtype=float),
        direction=np.asarray(plus_direction, dtype=float),
      ),
      Ray2D(
        origin=np.asarray(ambient_point, dtype=float),
        direction=np.asarray(minus_incoming_direction, dtype=float),
      ),
      condition_limit=1.0e10,
      parameter_tolerance=position_tolerance_m,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    return None
  ####
  if not intersection.is_success or intersection.point is None:
    return None
  ####
  b_point = _finite_point(intersection.point, 'entropy-carrying off-axis point')
  b_state = replace(provisional_b, x_m=b_point[0], y_m=b_point[1])
  minus_reflection_direction = _average_direction(
    b_state,
    provisional_d,
    CharacteristicFamily.MINUS,
  )
  if minus_reflection_direction is None or minus_reflection_direction[1] >= 0.0:
    return None
  ####
  reflection_parameter = -b_point[1] / minus_reflection_direction[1]
  if not isfinite(reflection_parameter) or reflection_parameter <= 0.0:
    return None
  ####
  d_point = (
    b_point[0] + reflection_parameter * minus_reflection_direction[0],
    0.0,
  )
  d_state = replace(provisional_d, x_m=d_point[0], y_m=d_point[1])
  vertices = (shock_point, b_point, d_point)
  states = (shock_state, b_state, d_state)
  pressures = (shock_pressure, off_axis_pressure, shock_pressure)
  incoming_displacement = (
    b_point[0] - ambient_point[0],
    b_point[1] - ambient_point[1],
  )
  incoming_edge_length = hypot(*incoming_displacement)
  if not isfinite(incoming_edge_length) or incoming_edge_length <= 0.0:
    return None
  ####
  incoming_alignment = abs(
    incoming_displacement[0] * minus_incoming_direction[1]
    - incoming_displacement[1] * minus_incoming_direction[0]
  ) / incoming_edge_length
  incoming_forward_margin = (
    incoming_displacement[0] * minus_incoming_direction[0]
    + incoming_displacement[1] * minus_incoming_direction[1]
  )
  outer_metrics = tuple(
    metric
    for metric in (
      _edge_metrics(
        vertices,
        states,
        pressures,
        0,
        1,
        CharacteristicFamily.PLUS,
      ),
      _edge_metrics(
        vertices,
        states,
        pressures,
        1,
        2,
        CharacteristicFamily.MINUS,
      ),
    )
    if metric is not None
  )
  return _EntropyTrialGeometry(
    vertices=vertices,
    states=states,
    pressures=pressures,
    incoming_alignment=incoming_alignment,
    incoming_forward_margin=incoming_forward_margin,
    incoming_k_minus_residual=abs(b_state.k_minus - ambient_state.k_minus),
    incoming_edge_length=incoming_edge_length,
    outer_metrics=outer_metrics,
  )
####


def _solve_two_variable_entropy_root(
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult,
  ambient_point: tuple[float, float],
  ambient_state: CharacteristicState,
  *,
  position_tolerance_m: float,
  characteristic_residual_tolerance: float,
  maximum_iterations: int,
  pressure_lineage_tolerance: float,
) -> tuple[_EntropyTrialGeometry | None, int, str]:
  if len(candidate.states) < 3:
    return None, 0, 'terminal candidate does not contain an initial reflected state'
  ####
  theta = float(candidate.states[1].theta_rad)
  mach_d = float(candidate.states[2].mach)

  def evaluate(values: tuple[float, float]) -> tuple[_EntropyTrialGeometry | None, tuple[float, float] | None]:
    geometry = _trial_geometry(
      candidate,
      ambient_point,
      ambient_state,
      theta_b=values[0],
      mach_d=values[1],
      position_tolerance_m=position_tolerance_m,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
    )
    if geometry is None or len(geometry.outer_metrics) != 2:
      return geometry, None
    ####
    return geometry, (
      geometry.outer_metrics[0][3] - geometry.outer_metrics[0][4],
      geometry.outer_metrics[1][3] - geometry.outer_metrics[1][4],
    )
  ####

  last_geometry: _EntropyTrialGeometry | None = None
  for iteration in range(1, maximum_iterations + 1):
    geometry, residual = evaluate((theta, mach_d))
    last_geometry = geometry
    if residual is None:
      return None, iteration, 'entropy root trial left the valid characteristic domain'
    ####
    norm = max(abs(residual[0]), abs(residual[1]))
    if norm <= characteristic_residual_tolerance:
      return geometry, iteration, ''
    ####
    theta_step = max(1.0e-6, abs(theta) * 1.0e-5)
    mach_step = max(1.0e-5, abs(mach_d) * 1.0e-5)
    theta_geometry, theta_residual = evaluate((theta + theta_step, mach_d))
    mach_geometry, mach_residual = evaluate((theta, mach_d + mach_step))
    if (
      theta_geometry is None
      or theta_residual is None
      or mach_geometry is None
      or mach_residual is None
    ):
      return None, iteration, 'entropy root finite-difference stencil failed'
    ####
    jacobian = (
      (
        (theta_residual[0] - residual[0]) / theta_step,
        (mach_residual[0] - residual[0]) / mach_step,
      ),
      (
        (theta_residual[1] - residual[1]) / theta_step,
        (mach_residual[1] - residual[1]) / mach_step,
      ),
    )
    determinant = (
      jacobian[0][0] * jacobian[1][1]
      - jacobian[0][1] * jacobian[1][0]
    )
    if not isfinite(determinant) or abs(determinant) <= 1.0e-18:
      return None, iteration, 'entropy root Jacobian is singular'
    ####
    delta_theta = (
      -residual[0] * jacobian[1][1]
      + jacobian[0][1] * residual[1]
    ) / determinant
    delta_mach = (
      jacobian[0][0] * -residual[1]
      - (-residual[0]) * jacobian[1][0]
    ) / determinant
    if not all(isfinite(value) for value in (delta_theta, delta_mach)):
      return None, iteration, 'entropy root Newton step is not finite'
    ####
    accepted = False
    for fraction in (1.0, 0.5, 0.25, 0.125, 0.0625, 0.03125):
      trial_theta = theta + fraction * delta_theta
      trial_mach = mach_d + fraction * delta_mach
      trial_geometry, trial_residual = evaluate((trial_theta, trial_mach))
      if trial_geometry is None or trial_residual is None:
        continue
      ####
      if max(abs(value) for value in trial_residual) < norm:
        theta = trial_theta
        mach_d = trial_mach
        accepted = True
        break
      ####
    ####
    if not accepted:
      return None, iteration, 'entropy root line search could not reduce residual'
    ####
  ####
  return last_geometry, maximum_iterations, 'entropy root did not converge'
####


def solve_euler_ambient_first_wedge_entropy_carry(
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
  maximum_iterations: int = 24,
) -> MocEulerAmbientFirstWedgeEntropyCarryResult:
  """Solve a bounded entropy-carrying terminal-wedge trial.

  The trial retains the terminal shock pressure at both axis vertices and
  retains the ambient-source pressure at the off-axis vertex.  It adjusts the
  off-axis flow angle and reflected-axis Mach number so the two terminal
  characteristic edges satisfy the generalized entropy source.  This is a
  local coupling experiment only; it does not mutate ``candidate`` or its
  source field, and it never creates a physical ``MocChainCell``.
  """

  if not isinstance(candidate, MocEulerAmbientFirstWedgeCharacteristicResult):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.INVALID_INPUT,
      None,
      None,
      message='candidate must be a MocEulerAmbientFirstWedgeCharacteristicResult',
    )
  ####
  source_field = candidate.source_field
  if source_field is None or source_field.field is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CANDIDATE_REQUIRED,
      candidate,
      source_field,
      message='entropy carry requires a terminal candidate with its source field',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    lineage_tolerance = float(pressure_lineage_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.INVALID_INPUT,
      candidate,
      source_field,
      message='entropy carry tolerances must be numeric',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
    ('pressure_lineage_tolerance', lineage_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  ####
  common = {
    'position_tolerance_m': position_tolerance,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'pressure_lineage_tolerance': lineage_tolerance,
  }
  if len(candidate.vertices_xr_m) != 3 or len(candidate.states) != 3:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CANDIDATE_REQUIRED,
      candidate,
      source_field,
      message='entropy carry requires exactly three terminal-wedge vertices and states',
      **common,
    )
  ####
  try:
    ambient_source_point = _finite_point(
      source_field.field.ambient_boundary.points_m[0],
      'ambient source point',
    )
    ambient_source_state = source_field.field.ambient_boundary.states[0]
    if not isinstance(ambient_source_state, CharacteristicState):
      raise ValueError('ambient source state is not a CharacteristicState')
    ####
    if len(source_field.field.ambient_boundary.total_pressure_Pa) == 0:
      raise ValueError('ambient source pressure is missing')
    ####
    ambient_source_pressure = float(
      source_field.field.ambient_boundary.total_pressure_Pa[0]
    )
    if not isfinite(ambient_source_pressure) or ambient_source_pressure <= 0.0:
      raise ValueError('ambient source pressure is not finite and positive')
    ####
  except (IndexError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.AMBIENT_SOURCE_REQUIRED,
      candidate,
      source_field,
      message=f'ambient source for entropy carry is unavailable: {error}',
      **common,
    )
  ####
  shock_pressure = float(candidate.total_pressure_Pa[0])
  off_axis_pressure = float(candidate.total_pressure_Pa[1])
  pressure_lineage_verified = bool(
    isfinite(shock_pressure)
    and shock_pressure > 0.0
    and isfinite(off_axis_pressure)
    and off_axis_pressure > 0.0
    and abs(off_axis_pressure - ambient_source_pressure)
    <= lineage_tolerance * max(
      1.0,
      abs(off_axis_pressure),
      abs(ambient_source_pressure),
    )
  )
  if not pressure_lineage_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.PRESSURE_LINEAGE_FAILURE,
      candidate,
      source_field,
      ambient_source_point=ambient_source_point,
      input_axis_total_pressure_Pa=(
        float(candidate.total_pressure_Pa[2])
        if len(candidate.total_pressure_Pa) > 2
        else None
      ),
      pressure_lineage_verified=False,
      message=(
        'terminal off-axis pressure does not retain the first ambient source '
        'total-pressure lineage'
      ),
      **common,
    )
  ####
  geometry, iterations, solver_message = _solve_two_variable_entropy_root(
    candidate,
    ambient_source_point,
    ambient_source_state,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=residual_tolerance,
    maximum_iterations=maximum_iterations,
    pressure_lineage_tolerance=lineage_tolerance,
  )
  if geometry is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.SOLVER_FAILURE,
      candidate,
      source_field,
      ambient_source_point=ambient_source_point,
      input_axis_total_pressure_Pa=float(candidate.total_pressure_Pa[2]),
      pressure_lineage_verified=True,
      solver_iterations=iterations,
      message=f'entropy-carrying local solve failed: {solver_message}',
      **common,
    )
  ####
  incoming_geometry_verified = bool(
    geometry.incoming_alignment <= alignment_tolerance
    and geometry.incoming_forward_margin > position_tolerance
    and geometry.incoming_k_minus_residual <= residual_tolerance
  )
  edges = tuple(
    MocEulerAmbientFirstWedgeCharacteristicEdge(
      edge_index=index,
      family=family,
      start_vertex=geometry.vertices[start_index],
      end_vertex=geometry.vertices[end_index],
      edge_length_m=metric[2],
      forward_margin_m=metric[1],
      alignment_residual=metric[0],
      k_residual=abs(metric[3]),
      entropy_source_prediction=abs(metric[4]),
      compatibility_residual=abs(metric[3] - metric[4]),
    )
    for index, start_index, end_index, family, metric in (
      (0, 0, 1, CharacteristicFamily.PLUS, geometry.outer_metrics[0]),
      (1, 1, 2, CharacteristicFamily.MINUS, geometry.outer_metrics[1]),
    )
  )
  maximum_alignment = max(edge.alignment_residual for edge in edges)
  minimum_forward = min(edge.forward_margin_m for edge in edges)
  maximum_k = max(edge.k_residual for edge in edges)
  maximum_entropy = max(edge.compatibility_residual for edge in edges)
  characteristic_geometry_verified = bool(
    incoming_geometry_verified
    and maximum_alignment <= alignment_tolerance
    and minimum_forward > position_tolerance
    and abs(geometry.vertices[0][1]) <= position_tolerance
    and abs(geometry.vertices[2][1]) <= position_tolerance
    and abs(geometry.states[0].theta_rad) <= residual_tolerance
    and abs(geometry.states[2].theta_rad) <= residual_tolerance
  )
  variable_entropy_verified = bool(
    characteristic_geometry_verified
    and maximum_entropy <= residual_tolerance
  )
  axis_pressure = geometry.pressures[2]
  input_axis_pressure = float(candidate.total_pressure_Pa[2])
  axis_pressure_residual = abs(log(axis_pressure / shock_pressure))
  axis_streamline_verified = bool(
    axis_pressure_residual <= lineage_tolerance
  )
  cell: MocCharacteristicCell | None = None
  cell_sample: MocEulerAmbientFirstWedgeCellSample | None = None
  topology = _empty_topology()
  try:
    cell = MocCharacteristicCell(
      cell_index=0,
      cell_kind='post-shock-ambient-terminal-entropy-carrying-wedge',
      vertices_xr_m=geometry.vertices,
      centerline_indices=(),
      boundary_indices=(),
    )
    cell_sample = MocEulerAmbientFirstWedgeCellSample(
      vertices_xr_m=geometry.vertices,
      states=geometry.states,
      total_pressure_Pa=geometry.pressures,
    )
    topology = validate_moc_mesh((cell,))
  except (TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      candidate,
      source_field,
      ambient_source_point=ambient_source_point,
      vertices=geometry.vertices,
      states=geometry.states,
      pressures=geometry.pressures,
      topology=topology,
      incoming_characteristic_alignment_residual=geometry.incoming_alignment,
      incoming_forward_margin_m=geometry.incoming_forward_margin,
      incoming_k_minus_residual=geometry.incoming_k_minus_residual,
      characteristic_edges=edges,
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_entropy,
      axis_total_pressure_Pa=axis_pressure,
      input_axis_total_pressure_Pa=input_axis_pressure,
      axis_streamline_pressure_residual_log=axis_pressure_residual,
      solver_iterations=iterations,
      incoming_characteristic_geometry_verified=incoming_geometry_verified,
      pressure_lineage_verified=pressure_lineage_verified,
      characteristic_geometry_verified=False,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      axis_streamline_entropy_verified=axis_streamline_verified,
      message=f'entropy-carrying terminal cell assembly failed: {error}',
      **common,
    )
  ####
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      candidate,
      source_field,
      ambient_source_point=ambient_source_point,
      vertices=geometry.vertices,
      states=geometry.states,
      pressures=geometry.pressures,
      cell=cell,
      cell_sample=cell_sample,
      topology=topology,
      incoming_characteristic_alignment_residual=geometry.incoming_alignment,
      incoming_forward_margin_m=geometry.incoming_forward_margin,
      incoming_k_minus_residual=geometry.incoming_k_minus_residual,
      characteristic_edges=edges,
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_entropy,
      axis_total_pressure_Pa=axis_pressure,
      input_axis_total_pressure_Pa=input_axis_pressure,
      axis_streamline_pressure_residual_log=axis_pressure_residual,
      solver_iterations=iterations,
      incoming_characteristic_geometry_verified=incoming_geometry_verified,
      pressure_lineage_verified=pressure_lineage_verified,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      axis_streamline_entropy_verified=axis_streamline_verified,
      message=f'entropy-carrying terminal topology failed: {topology.message}',
      **common,
    )
  ####
  try:
    cell_residual = _cell_euler_residual(
      geometry.vertices,
      geometry.states,
      geometry.pressures,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryStatus.EULER_RESIDUAL_FAILURE,
      candidate,
      source_field,
      ambient_source_point=ambient_source_point,
      vertices=geometry.vertices,
      states=geometry.states,
      pressures=geometry.pressures,
      cell=cell,
      cell_sample=cell_sample,
      topology=topology,
      incoming_characteristic_alignment_residual=geometry.incoming_alignment,
      incoming_forward_margin_m=geometry.incoming_forward_margin,
      incoming_k_minus_residual=geometry.incoming_k_minus_residual,
      characteristic_edges=edges,
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_entropy,
      axis_total_pressure_Pa=axis_pressure,
      input_axis_total_pressure_Pa=input_axis_pressure,
      axis_streamline_pressure_residual_log=axis_pressure_residual,
      solver_iterations=iterations,
      incoming_characteristic_geometry_verified=incoming_geometry_verified,
      pressure_lineage_verified=pressure_lineage_verified,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      axis_streamline_entropy_verified=axis_streamline_verified,
      message=f'entropy-carrying Euler residual failed: {error}',
      **common,
    )
  ####
  cell_residual_finite = isfinite(cell_residual)
  cell_residual_verified = bool(
    cell_residual_finite and cell_residual <= cell_tolerance
  )
  if not characteristic_geometry_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryStatus.CHARACTERISTIC_GEOMETRY_FAILURE
    message = 'entropy-carrying trial did not retain its incoming and terminal characteristic geometry'
  elif not variable_entropy_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryStatus.ENTROPY_FAILURE
    message = 'entropy-carrying trial did not satisfy both generalized characteristic source equations'
  elif not axis_streamline_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryStatus.PRESSURE_LINEAGE_FAILURE
    message = 'entropy-carrying trial changed the centerline streamline total-pressure lineage'
  elif not cell_residual_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryStatus.EULER_RESIDUAL_FAILURE
    message = 'entropy-carrying terminal wedge still requires characteristic subcell refinement'
  else:
    status = MocEulerAmbientFirstWedgeEntropyCarryStatus.CONVERGED_LOCAL_ENTROPY_CARRY
    message = 'entropy-carrying terminal wedge passed local gates; reflected field closure remains blocked'
  ####
  if not cell_residual_verified:
    message += f' (cell Euler residual={cell_residual})'
  ####
  return MocEulerAmbientFirstWedgeEntropyCarryResult(
    status=status,
    source_candidate=candidate,
    source_field=source_field,
    ambient_source_point=ambient_source_point,
    vertices_xr_m=geometry.vertices,
    states=geometry.states,
    total_pressure_Pa=geometry.pressures,
    cell=cell,
    cell_sample=cell_sample,
    topology=topology,
    incoming_characteristic_alignment_residual=geometry.incoming_alignment,
    incoming_forward_margin_m=geometry.incoming_forward_margin,
    incoming_k_minus_residual=geometry.incoming_k_minus_residual,
    characteristic_edges=edges,
    maximum_edge_alignment_residual=maximum_alignment,
    minimum_forward_margin_m=minimum_forward,
    maximum_k_residual=maximum_k,
    maximum_entropy_compatibility_residual=maximum_entropy,
    axis_total_pressure_Pa=axis_pressure,
    input_axis_total_pressure_Pa=input_axis_pressure,
    axis_streamline_pressure_residual_log=axis_pressure_residual,
    cell_euler_residual=cell_residual,
    solver_iterations=iterations,
    incoming_characteristic_geometry_verified=incoming_geometry_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_verified,
    axis_streamline_entropy_verified=axis_streamline_verified,
    cell_euler_residual_finite=cell_residual_finite,
    cell_euler_residual_verified=cell_residual_verified,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    cell_residual_tolerance=cell_tolerance,
    pressure_lineage_tolerance=lineage_tolerance,
    message=message,
  )
####
