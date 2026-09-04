"""Independent audit for the bounded Euler MOC entropy-carrying trial.

The entropy-carrying solver is deliberately a local research seam.  This
module remeasures its returned vertices, states, pressures, characteristic
geometry, generalized source compatibility, pressure lineage, and Euler
residual without trusting the solver's cached gates.  A successful local
audit still cannot promote the result to a physical shock-cell chain: the
internal characteristic subcell field and reflected free boundary remain
open requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
  MocEulerAmbientFirstWedgeEntropyCarryStatus,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.topology import validate_moc_mesh
from exhaust_plume.validation.moc_euler import _cell_flux_residual

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCarryAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit',
  'MocEulerAmbientFirstWedgeEntropyCarryAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_carry',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-carry-audit'
)


class MocEulerAmbientFirstWedgeEntropyCarryAuditStatus(str, Enum):
  """Outcome of the independent entropy-carrying trial audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_carry_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'euler_ambient_first_wedge_entropy_source_failure'
  TOPOLOGY_FAILURE = 'euler_ambient_first_wedge_entropy_topology_failure'
  STATE_FAILURE = 'euler_ambient_first_wedge_entropy_state_failure'
  PRESSURE_LINEAGE_FAILURE = (
    'euler_ambient_first_wedge_entropy_pressure_lineage_failure'
  )
  GEOMETRY_FAILURE = 'euler_ambient_first_wedge_entropy_geometry_failure'
  ENTROPY_FAILURE = 'euler_ambient_first_wedge_entropy_compatibility_failure'
  EULER_RESIDUAL_FAILURE = 'euler_ambient_first_wedge_entropy_euler_residual_failure'
  FLAG_FAILURE = 'euler_ambient_first_wedge_entropy_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit:
  """Independent generalized-compatibility evidence for one edge."""

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
      if len(point) != 2 or not all(isfinite(float(value)) for value in point):
        raise ValueError(f'{name} must contain a finite coordinate pair')
      ####
      object.__setattr__(
        self,
        name,
        (float(point[0]), float(point[1])),
      )
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
class MocEulerAmbientFirstWedgeEntropyCarryAudit:
  """Independent gates for one entropy-carrying terminal trial."""

  status: MocEulerAmbientFirstWedgeEntropyCarryAuditStatus
  solver_status: str | None
  vertex_count: int
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit, ...]
  incoming_characteristic_alignment_residual: float | None
  incoming_forward_margin_m: float | None
  incoming_k_minus_residual: float | None
  maximum_edge_alignment_residual: float | None
  minimum_forward_margin_m: float | None
  maximum_k_residual: float | None
  maximum_entropy_compatibility_residual: float | None
  axis_streamline_pressure_residual_log: float | None
  cell_euler_residual: float | None
  topology_verified: bool
  state_samples_finite: bool
  pressure_lineage_verified: bool
  incoming_characteristic_geometry_verified: bool
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  axis_streamline_entropy_verified: bool
  cell_euler_residual_finite: bool
  cell_euler_residual_verified: bool
  solver_status_consistent: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  pressure_lineage_tolerance: float = 1.0e-8
  message: str = ''
  operator_id: str = (
    MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus,
    ):
      raise TypeError(
        'status must be a MocEulerAmbientFirstWedgeEntropyCarryAuditStatus'
      )
    ####
    if self.solver_status is not None:
      object.__setattr__(self, 'solver_status', str(self.solver_status))
    ####
    if (
      isinstance(self.vertex_count, bool)
      or not isinstance(self.vertex_count, int)
      or self.vertex_count < 0
    ):
      raise ValueError('vertex_count must be a nonnegative integer')
    ####
    edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(edge, MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit)
      for edge in edges
    ):
      raise TypeError(
        'characteristic_edges must contain entropy-carrying edge audits'
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
      'axis_streamline_pressure_residual_log',
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
      'pressure_lineage_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'topology_verified',
      'state_samples_finite',
      'pressure_lineage_verified',
      'incoming_characteristic_geometry_verified',
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'axis_streamline_entropy_verified',
      'cell_euler_residual_finite',
      'cell_euler_residual_verified',
      'solver_status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
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
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.topology_verified
      and self.state_samples_finite
      and self.pressure_lineage_verified
      and self.incoming_characteristic_geometry_verified
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.axis_streamline_entropy_verified
      and self.cell_euler_residual_finite
      and self.cell_euler_residual_verified
      and self.solver_status_consistent
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'vertex_count': self.vertex_count,
      'characteristic_edge_count': len(self.characteristic_edges),
      'incoming_characteristic_alignment_residual': (
        self.incoming_characteristic_alignment_residual
      ),
      'incoming_forward_margin_m': self.incoming_forward_margin_m,
      'incoming_k_minus_residual': self.incoming_k_minus_residual,
      'maximum_edge_alignment_residual': self.maximum_edge_alignment_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_k_residual': self.maximum_k_residual,
      'maximum_entropy_compatibility_residual': (
        self.maximum_entropy_compatibility_residual
      ),
      'axis_streamline_pressure_residual_log': (
        self.axis_streamline_pressure_residual_log
      ),
      'cell_euler_residual': self.cell_euler_residual,
      'checks': {
        'topology_verified': self.topology_verified,
        'state_samples_finite': self.state_samples_finite,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'incoming_characteristic_geometry_verified': (
          self.incoming_characteristic_geometry_verified
        ),
        'characteristic_geometry_verified': self.characteristic_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'axis_streamline_entropy_verified': self.axis_streamline_entropy_verified,
        'cell_euler_residual_finite': self.cell_euler_residual_finite,
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'solver_status_consistent': self.solver_status_consistent,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'characteristic_edges': [edge.as_report() for edge in self.characteristic_edges],
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-solver-owned-entropy-carrying-terminal-audit; internal '
        'characteristic refinement, reflected closure, and external validation '
        'remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCarryAuditStatus,
  message: str,
  *,
  solver_status: str | None = None,
  vertex_count: int = 0,
  characteristic_edges: Sequence[MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit] = (),
  incoming_characteristic_alignment_residual: float | None = None,
  incoming_forward_margin_m: float | None = None,
  incoming_k_minus_residual: float | None = None,
  maximum_edge_alignment_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  maximum_k_residual: float | None = None,
  maximum_entropy_compatibility_residual: float | None = None,
  axis_streamline_pressure_residual_log: float | None = None,
  cell_euler_residual: float | None = None,
  topology_verified: bool = False,
  state_samples_finite: bool = False,
  pressure_lineage_verified: bool = False,
  incoming_characteristic_geometry_verified: bool = False,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  axis_streamline_entropy_verified: bool = False,
  cell_euler_residual_finite: bool = False,
  cell_euler_residual_verified: bool = False,
  solver_status_consistent: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCarryAudit:
  return MocEulerAmbientFirstWedgeEntropyCarryAudit(
    status=status,
    solver_status=solver_status,
    vertex_count=vertex_count,
    characteristic_edges=tuple(characteristic_edges),
    incoming_characteristic_alignment_residual=(
      incoming_characteristic_alignment_residual
    ),
    incoming_forward_margin_m=incoming_forward_margin_m,
    incoming_k_minus_residual=incoming_k_minus_residual,
    maximum_edge_alignment_residual=maximum_edge_alignment_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    maximum_k_residual=maximum_k_residual,
    maximum_entropy_compatibility_residual=(
      maximum_entropy_compatibility_residual
    ),
    axis_streamline_pressure_residual_log=axis_streamline_pressure_residual_log,
    cell_euler_residual=cell_euler_residual,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    pressure_lineage_verified=pressure_lineage_verified,
    incoming_characteristic_geometry_verified=(
      incoming_characteristic_geometry_verified
    ),
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=(
      variable_entropy_compatibility_verified
    ),
    axis_streamline_entropy_verified=axis_streamline_entropy_verified,
    cell_euler_residual_finite=cell_euler_residual_finite,
    cell_euler_residual_verified=cell_euler_residual_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    message=message,
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


def _log_pressure_gradient(
  vertices: tuple[tuple[float, float], ...],
  pressures: tuple[float, ...],
) -> tuple[float, float] | None:
  if len(vertices) != 3 or len(pressures) != 3:
    return None
  ####
  (x1, y1), (x2, y2), (x3, y3) = vertices
  denominator = (
    x1 * (y2 - y3)
    + x2 * (y3 - y1)
    + x3 * (y1 - y2)
  )
  if not isfinite(denominator) or abs(denominator) <= 1.0e-24:
    return None
  ####
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return None
  ####
  values = tuple(log(value) for value in pressures)
  return (
    (
      values[0] * (y2 - y3)
      + values[1] * (y3 - y1)
      + values[2] * (y1 - y2)
    ) / denominator,
    (
      values[0] * (x3 - x2)
      + values[1] * (x1 - x3)
      + values[2] * (x2 - x1)
    ) / denominator,
  )
####


def _edge_evidence(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  start_index: int,
  end_index: int,
  family: CharacteristicFamily,
  edge_index: int,
) -> MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit | None:
  direction = _average_direction(states[start_index], states[end_index], family)
  gradient = _log_pressure_gradient(vertices, pressures)
  if direction is None or gradient is None:
    return None
  ####
  displacement = (
    vertices[end_index][0] - vertices[start_index][0],
    vertices[end_index][1] - vertices[start_index][1],
  )
  length = hypot(*displacement)
  if not isfinite(length) or length <= 0.0:
    return None
  ####
  alignment = abs(
    displacement[0] * direction[1] - displacement[1] * direction[0]
  ) / length
  forward = displacement[0] * direction[0] + displacement[1] * direction[1]
  average_theta = 0.5 * (
    states[start_index].theta_rad + states[end_index].theta_rad
  )
  normal = (-sin(average_theta), cos(average_theta))
  normal_gradient = gradient[0] * normal[0] + gradient[1] * normal[1]
  average_mach = 0.5 * (states[start_index].mach + states[end_index].mach)
  gamma = 0.5 * (states[start_index].gamma + states[end_index].gamma)
  source = -sqrt(max(average_mach * average_mach - 1.0, 0.0)) / (
    gamma * average_mach ** 3
  ) * normal_gradient * length
  actual = (
    states[end_index].k_plus - states[start_index].k_plus
    if family is CharacteristicFamily.PLUS
    else states[end_index].k_minus - states[start_index].k_minus
  )
  return MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit(
    edge_index=edge_index,
    family=family,
    start_vertex=vertices[start_index],
    end_vertex=vertices[end_index],
    edge_length_m=length,
    forward_margin_m=forward,
    alignment_residual=alignment,
    k_residual=abs(actual),
    entropy_source_prediction=abs(source),
    compatibility_residual=abs(actual - source),
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_carry(
  result: MocEulerAmbientFirstWedgeEntropyCarryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCarryAudit:
  """Recompute entropy-carrying gates from raw solver evidence."""

  if not isinstance(result, MocEulerAmbientFirstWedgeEntropyCarryResult):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.INVALID_INPUT,
      'result must be a MocEulerAmbientFirstWedgeEntropyCarryResult',
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
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.INVALID_INPUT,
      'entropy-carrying audit tolerances must be numeric',
      solver_status=result.status.value,
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
  common = {
    'solver_status': result.status.value,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'pressure_lineage_tolerance': lineage_tolerance,
    'physical_closure_verified': result.physical_closure_verified,
    'chain_promotion_blocked': result.chain_promotion_blocked,
    'production_claim_allowed': result.production_claim_allowed,
  }
  candidate = result.source_candidate
  source_field = result.source_field
  if candidate is None or source_field is None or source_field.field is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.SOURCE_FAILURE,
      'entropy-carrying result does not retain its source candidate and field',
      **common,
    )
  ####
  cell = result.cell
  sample = result.cell_sample
  vertices = tuple(
    (float(point[0]), float(point[1])) for point in result.vertices_xr_m
  )
  states = tuple(result.states)
  pressures = tuple(float(value) for value in result.total_pressure_Pa)
  topology = validate_moc_mesh(()) if cell is None else validate_moc_mesh((cell,))
  topology_verified = bool(
    cell is not None
    and topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  cell_vertices = (
    ()
    if cell is None
    else tuple(
      (float(point[0]), float(point[1])) for point in cell.vertices_xr_m
    )
  )
  sample_vertices = (
    ()
    if sample is None
    else tuple(
      (float(point[0]), float(point[1])) for point in sample.vertices_xr_m
    )
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.TOPOLOGY_FAILURE,
      f'independent entropy-carrying topology audit failed: {topology.message}',
      vertex_count=len(vertices),
      topology_verified=False,
      **common,
    )
  ####
  state_samples_finite = bool(
    len(vertices) == len(states) == len(pressures) == 3
    and len(cell_vertices) == len(sample_vertices) == 3
    and all(
      hypot(first[0] - second[0], first[1] - second[1])
      <= position_tolerance
      for first, second in zip(cell_vertices, vertices, strict=True)
    )
    and all(
      hypot(first[0] - second[0], first[1] - second[1])
      <= position_tolerance
      for first, second in zip(sample_vertices, vertices, strict=True)
    )
    and all(
      isinstance(state, CharacteristicState)
      and all(
        isfinite(value)
        for value in (
          state.x_m,
          state.y_m,
          state.theta_rad,
          state.mach,
          state.gamma,
        )
      )
      and state.mach > 1.0
      and state.gamma > 1.0
      for state in states
    )
    and all(isfinite(value) and value > 0.0 for value in pressures)
    and all(
      isinstance(state, CharacteristicState)
      and all(
        isfinite(value)
        for value in (
          state.x_m,
          state.y_m,
          state.theta_rad,
          state.mach,
          state.gamma,
        )
      )
      for state in sample.states
    )
    and all(
      abs(first - second)
      <= position_tolerance * max(1.0, abs(first), abs(second))
      for first, second in zip(pressures, sample.total_pressure_Pa, strict=True)
    )
    and all(
      hypot(first.x_m - second.x_m, first.y_m - second.y_m)
      <= position_tolerance
      and abs(first.theta_rad - second.theta_rad) <= residual_tolerance
      and abs(first.mach - second.mach) <= residual_tolerance
      and abs(first.gamma - second.gamma) <= residual_tolerance
      for first, second in zip(states, sample.states, strict=True)
    )
    and all(
      hypot(state.x_m - point[0], state.y_m - point[1]) <= position_tolerance
      for point, state in zip(vertices, states, strict=True)
    )
    if sample is not None
    else False
  )
  if not state_samples_finite:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.STATE_FAILURE,
      'entropy-carrying raw vertices, states, or sample values are inconsistent',
      vertex_count=len(vertices),
      topology_verified=True,
      state_samples_finite=False,
      **common,
    )
  ####
  try:
    ambient_points = source_field.field.ambient_boundary.points_m
    ambient_states = source_field.field.ambient_boundary.states
    ambient_pressures = source_field.field.ambient_boundary.total_pressure_Pa
    ambient_point = (
      float(ambient_points[0][0]),
      float(ambient_points[0][1]),
    )
    ambient_state = ambient_states[0]
    ambient_pressure = float(ambient_pressures[0])
  except (IndexError, TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.SOURCE_FAILURE,
      'independent entropy-carrying audit could not recover the ambient source',
      vertex_count=len(vertices),
      topology_verified=True,
      state_samples_finite=True,
      **common,
    )
  ####
  pressure_lineage_verified = bool(
    abs(pressures[1] - ambient_pressure)
    <= lineage_tolerance * max(1.0, abs(pressures[1]), abs(ambient_pressure))
    and abs(pressures[2] - pressures[0])
    <= lineage_tolerance * max(1.0, abs(pressures[2]), abs(pressures[0]))
  )
  incoming_direction = _average_direction(
    ambient_state,
    states[1],
    CharacteristicFamily.MINUS,
  )
  incoming_alignment: float | None = None
  incoming_forward: float | None = None
  incoming_k_minus: float | None = None
  if incoming_direction is not None:
    incoming_displacement = (
      vertices[1][0] - ambient_point[0],
      vertices[1][1] - ambient_point[1],
    )
    incoming_length = hypot(*incoming_displacement)
    if isfinite(incoming_length) and incoming_length > 0.0:
      incoming_alignment = abs(
        incoming_displacement[0] * incoming_direction[1]
        - incoming_displacement[1] * incoming_direction[0]
      ) / incoming_length
      incoming_forward = (
        incoming_displacement[0] * incoming_direction[0]
        + incoming_displacement[1] * incoming_direction[1]
      )
      incoming_k_minus = abs(states[1].k_minus - ambient_state.k_minus)
    ####
  ####
  incoming_geometry_verified = bool(
    incoming_alignment is not None
    and incoming_forward is not None
    and incoming_k_minus is not None
    and incoming_alignment <= alignment_tolerance
    and incoming_forward > position_tolerance
    and incoming_k_minus <= residual_tolerance
  )
  edges: list[MocEulerAmbientFirstWedgeEntropyCarryEdgeAudit] = []
  for edge_index, (start, end, family) in enumerate(
    (
      (0, 1, CharacteristicFamily.PLUS),
      (1, 2, CharacteristicFamily.MINUS),
    )
  ):
    evidence = _edge_evidence(
      vertices,
      states,
      pressures,
      start,
      end,
      family,
      edge_index,
    )
    if evidence is not None:
      edges.append(evidence)
    ####
  ####
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
    incoming_geometry_verified
    and len(edges) == 2
    and maximum_alignment is not None
    and maximum_alignment <= alignment_tolerance
    and minimum_forward is not None
    and minimum_forward > position_tolerance
    and abs(vertices[0][1]) <= position_tolerance
    and abs(vertices[2][1]) <= position_tolerance
    and abs(states[0].theta_rad) <= residual_tolerance
    and abs(states[2].theta_rad) <= residual_tolerance
  )
  variable_entropy_verified = bool(
    characteristic_geometry_verified
    and maximum_entropy is not None
    and maximum_entropy <= residual_tolerance
  )
  axis_residual = abs(log(pressures[2] / pressures[0]))
  axis_entropy_verified = bool(axis_residual <= lineage_tolerance)
  try:
    cell_residual = _cell_flux_residual(vertices, states, pressures)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    cell_residual = None
  ####
  cell_residual_finite = bool(
    cell_residual is not None and isfinite(cell_residual)
  )
  cell_residual_verified = bool(
    cell_residual_finite and cell_residual <= cell_tolerance
  )
  if not pressure_lineage_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.PRESSURE_LINEAGE_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.PRESSURE_LINEAGE_FAILURE
    message = 'independent entropy-carrying pressure lineage audit failed'
  elif not characteristic_geometry_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CHARACTERISTIC_GEOMETRY_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.GEOMETRY_FAILURE
    message = 'independent entropy-carrying characteristic geometry audit failed'
  elif not variable_entropy_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.ENTROPY_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.ENTROPY_FAILURE
    message = 'independent entropy-carrying source compatibility audit failed'
  elif not axis_entropy_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.PRESSURE_LINEAGE_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.PRESSURE_LINEAGE_FAILURE
    message = 'independent centerline streamline entropy audit failed'
  elif not cell_residual_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.EULER_RESIDUAL_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.EULER_RESIDUAL_FAILURE
    message = 'independent entropy-carrying coarse-cell Euler residual audit failed'
  elif (
    result.physical_closure_verified
    or not result.chain_promotion_blocked
    or result.production_claim_allowed
  ):
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CONVERGED_LOCAL_ENTROPY_CARRY.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.FLAG_FAILURE
    message = 'entropy-carrying result returned weakened fidelity flags'
  else:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCarryStatus.CONVERGED_LOCAL_ENTROPY_CARRY.value
    )
    status = MocEulerAmbientFirstWedgeEntropyCarryAuditStatus.CONVERGED_LOCAL_AUDIT
    message = 'independent entropy-carrying local audit passed; physical closure remains blocked'
  ####
  solver_status_consistent = result.status.value == expected_status
  if not solver_status_consistent:
    message += (
      f'; solver status {result.status.value!r} does not match the independent '
      f'expected status {expected_status!r}'
    )
  ####
  return MocEulerAmbientFirstWedgeEntropyCarryAudit(
    status=status,
    solver_status=result.status.value,
    vertex_count=len(vertices),
    characteristic_edges=tuple(edges),
    incoming_characteristic_alignment_residual=incoming_alignment,
    incoming_forward_margin_m=incoming_forward,
    incoming_k_minus_residual=incoming_k_minus,
    maximum_edge_alignment_residual=maximum_alignment,
    minimum_forward_margin_m=minimum_forward,
    maximum_k_residual=maximum_k,
    maximum_entropy_compatibility_residual=maximum_entropy,
    axis_streamline_pressure_residual_log=axis_residual,
    cell_euler_residual=cell_residual,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    pressure_lineage_verified=pressure_lineage_verified,
    incoming_characteristic_geometry_verified=incoming_geometry_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_verified,
    axis_streamline_entropy_verified=axis_entropy_verified,
    cell_euler_residual_finite=cell_residual_finite,
    cell_euler_residual_verified=cell_residual_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=result.physical_closure_verified,
    chain_promotion_blocked=result.chain_promotion_blocked,
    production_claim_allowed=result.production_claim_allowed,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    cell_residual_tolerance=cell_tolerance,
    pressure_lineage_tolerance=lineage_tolerance,
    message=message,
  )
####
