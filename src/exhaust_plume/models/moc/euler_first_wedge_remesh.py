"""Bounded diagnostic subdivision of the reflected Euler first wedge.

The ambient-closed Euler field currently contains one finite reflected wedge
between the terminal shock point, the terminal ``C+`` node, and the first
centerline reflection.  Increasing the shock/ambient boundary sample count
does not refine that topological cell.  This module provides the next
solver-owned seam: a local, bounded subdivision that samples state and total
pressure only from the retained field.

The subdivision is intentionally a diagnostic remesh, not a conservative
Euler solve.  It is useful for measuring whether a future terminal-wedge
solver has the right geometry and state handoff, but its interpolated states
must not be promoted to a physical shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_physical_field import (
  MocEulerAmbientPhysicalFieldResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeRemeshStatus',
  'MocEulerAmbientFirstWedgeCellSample',
  'MocEulerAmbientFirstWedgeRemeshResult',
  'remesh_euler_ambient_first_wedge',
)


def _coerce_point(point: Any, *, label: str) -> tuple[float, float]:
  try:
    if len(point) != 2:
      raise ValueError(f'{label} must be a coordinate pair')
    values = (float(point[0]), float(point[1]))
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(f'{label} must be a coordinate pair') from error
  if not all(isfinite(value) for value in values):
    raise ValueError(f'{label} must contain finite coordinates')
  return values


class MocEulerAmbientFirstWedgeRemeshStatus(str, Enum):
  """Outcome of the bounded first-wedge subdivision seam."""

  CONVERGED_DIAGNOSTIC_SUBDIVISION = (
    'converged_euler_ambient_first_wedge_diagnostic_subdivision'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_REQUIRED = 'euler_ambient_first_wedge_field_required'
  WEDGE_REQUIRED = 'euler_ambient_first_wedge_required'
  STATE_SAMPLING_FAILURE = 'euler_ambient_first_wedge_state_sampling_failure'
  GEOMETRY_FAILURE = 'euler_ambient_first_wedge_geometry_failure'
  TOPOLOGY_FAILURE = 'euler_ambient_first_wedge_topology_failure'


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCellSample:
  """State/pressure samples retained at one remeshed wedge cell."""

  vertices_xr_m: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  total_pressure_Pa: tuple[float, ...]

  def __post_init__(self) -> None:
    vertices = tuple(
      _coerce_point(point, label='remeshed cell vertices')
      for point in self.vertices_xr_m
    )
    states = tuple(self.states)
    pressures = tuple(float(value) for value in self.total_pressure_Pa)
    if len(vertices) != 3 or len(states) != 3 or len(pressures) != 3:
      raise ValueError(
        'a first-wedge remesh cell sample requires three vertices, states, '
        'and total-pressure values'
      )
    if any(not isinstance(state, CharacteristicState) for state in states):
      raise TypeError('remeshed cell states must be CharacteristicState values')
    if any(
      not isfinite(value) or value <= 0.0 for value in pressures
    ):
      raise ValueError(
        'remeshed cell total-pressure values must be finite and positive'
      )
    if any(
      hypot(state.x_m - point[0], state.y_m - point[1]) > 1.0e-10
      for point, state in zip(vertices, states, strict=True)
    ):
      raise ValueError('remeshed cell states must lie on their sample vertices')
    object.__setattr__(self, 'vertices_xr_m', vertices)
    object.__setattr__(self, 'states', states)
    object.__setattr__(self, 'total_pressure_Pa', pressures)

  def as_report(self) -> dict[str, Any]:
    return {
      'vertices_xr_m': [list(point) for point in self.vertices_xr_m],
      'mach': [state.mach for state in self.states],
      'flow_angles_rad': [state.theta_rad for state in self.states],
      'total_pressure_Pa': list(self.total_pressure_Pa),
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeRemeshResult:
  """A bounded local first-wedge remesh candidate.

  ``converged`` means only that the requested geometric subdivision was
  assembled from samples inside the accepted field.  The result deliberately
  reports ``physical_closure_verified=False`` even when its local topology is
  closed, because linear state projection is not a replacement for a
  conservative characteristic solve.
  """

  status: MocEulerAmbientFirstWedgeRemeshStatus
  source_field: MocEulerAmbientPhysicalFieldResult | None
  source_cell_index: int | None
  source_cell_kind: str | None
  original_vertices_xr_m: tuple[tuple[float, float], ...]
  subdivision_level: int
  subdivision_side_count: int
  cells: tuple[MocCharacteristicCell, ...]
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...]
  topology: MocTopologyResult
  state_projection_verified: bool
  pressure_lineage_carried: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientFirstWedgeRemeshStatus):
      raise TypeError(
        'status must be a MocEulerAmbientFirstWedgeRemeshStatus'
      )
    if self.source_field is not None and not isinstance(
      self.source_field,
      MocEulerAmbientPhysicalFieldResult,
    ):
      raise TypeError(
        'source_field must be a MocEulerAmbientPhysicalFieldResult or None'
      )
    if self.source_cell_index is not None and (
      isinstance(self.source_cell_index, bool)
      or not isinstance(self.source_cell_index, int)
      or self.source_cell_index < 0
    ):
      raise ValueError('source_cell_index must be a nonnegative integer or None')
    if self.source_cell_kind is not None:
      object.__setattr__(self, 'source_cell_kind', str(self.source_cell_kind))
    original_vertices = tuple(
      _coerce_point(point, label='original wedge vertices')
      for point in self.original_vertices_xr_m
    )
    object.__setattr__(self, 'original_vertices_xr_m', original_vertices)
    for name in ('subdivision_level', 'subdivision_side_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.subdivision_level == 0 and self.subdivision_side_count != 1:
      raise ValueError(
        'a zero-level remesh must retain one subdivision side'
      )
    if self.subdivision_level > 0 and self.subdivision_side_count < 2:
      raise ValueError(
        'a positive-level remesh must contain at least two subdivision sides'
      )
    cells = tuple(self.cells)
    samples = tuple(self.cell_samples)
    if len(cells) != len(samples):
      raise ValueError('remeshed cells and state samples must have equal lengths')
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError('cells must contain MocCharacteristicCell values')
    if any(
      not isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      for sample in samples
    ):
      raise TypeError(
        'cell_samples must contain MocEulerAmbientFirstWedgeCellSample values'
      )
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    for name in (
      'state_projection_verified',
      'pressure_lineage_carried',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'cell_samples', samples)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeRemeshStatus.CONVERGED_DIAGNOSTIC_SUBDIVISION
    )

  @property
  def cell_count(self) -> int:
    return len(self.cells)

  @property
  def state_sample_count(self) -> int:
    return len({
      point
      for sample in self.cell_samples
      for point in sample.vertices_xr_m
    })

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit non-promotion boundary for this remesh."""

    if self.status is MocEulerAmbientFirstWedgeRemeshStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    else:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'diagnostic first-wedge subdivision does not produce a continued '
        'physical shock-cell chain'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'remesh_status': self.status.value,
        'source_cell_index': self.source_cell_index,
        'source_cell_kind': self.source_cell_kind,
        'subdivision_level': self.subdivision_level,
        'subdivision_side_count': self.subdivision_side_count,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'solver-owned-terminal-wedge-characteristic-remesh-with-'
          'conservative-euler-cell-closure'
        ),
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_field_status': (
        None if self.source_field is None else self.source_field.status.value
      ),
      'source_cell_index': self.source_cell_index,
      'source_cell_kind': self.source_cell_kind,
      'original_vertices_xr_m': [
        list(point) for point in self.original_vertices_xr_m
      ],
      'subdivision_level': self.subdivision_level,
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'state_sample_count': self.state_sample_count,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_boundary_edge_count': self.topology.boundary_edge_count,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'state_projection_verified': self.state_projection_verified,
      'pressure_lineage_carried': self.pressure_lineage_carried,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'cells': [sample.as_report() for sample in self.cell_samples],
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _failure(
  status: MocEulerAmbientFirstWedgeRemeshStatus,
  source_field: MocEulerAmbientPhysicalFieldResult | None,
  *,
  source_cell_index: int | None = None,
  source_cell_kind: str | None = None,
  original_vertices: tuple[tuple[float, float], ...] = (),
  subdivision_level: int = 0,
  subdivision_side_count: int = 1,
  cells: tuple[MocCharacteristicCell, ...] = (),
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...] = (),
  topology: MocTopologyResult | None = None,
  state_projection_verified: bool = False,
  pressure_lineage_carried: bool = False,
  message: str,
) -> MocEulerAmbientFirstWedgeRemeshResult:
  return MocEulerAmbientFirstWedgeRemeshResult(
    status=status,
    source_field=source_field,
    source_cell_index=source_cell_index,
    source_cell_kind=source_cell_kind,
    original_vertices_xr_m=original_vertices,
    subdivision_level=subdivision_level,
    subdivision_side_count=subdivision_side_count,
    cells=cells,
    cell_samples=cell_samples,
    topology=_empty_topology() if topology is None else topology,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    message=message,
  )


def _point(
  first: tuple[float, float],
  second: tuple[float, float],
  third: tuple[float, float],
  side_count: int,
  first_index: int,
  second_index: int,
) -> tuple[float, float]:
  """Return one barycentric lattice point in the source triangle."""

  first_weight = first_index / side_count
  second_weight = second_index / side_count
  return (
    first[0]
    + first_weight * (second[0] - first[0])
    + second_weight * (third[0] - first[0]),
    first[1]
    + first_weight * (second[1] - first[1])
    + second_weight * (third[1] - first[1]),
  )


def remesh_euler_ambient_first_wedge(
  source_field: MocEulerAmbientPhysicalFieldResult,
  *,
  subdivision_level: int = 1,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerAmbientFirstWedgeRemeshResult:
  """Subdivide the retained reflected first wedge using bounded samples.

  ``subdivision_level=1`` creates four triangles and level two creates
  sixteen.  The sampled state and total pressure at every new vertex come
  from ``source_field.field.state_at`` and ``total_pressure_at``; no value is
  extrapolated outside the accepted source cell.
  """

  if not isinstance(source_field, MocEulerAmbientPhysicalFieldResult):
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.INVALID_INPUT,
      None,
      message='source_field must be a MocEulerAmbientPhysicalFieldResult',
    )
  if (
    isinstance(subdivision_level, bool)
    or not isinstance(subdivision_level, int)
    or subdivision_level < 1
    or subdivision_level > 8
  ):
    raise ValueError('subdivision_level must be an integer from one through eight')
  try:
    tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.INVALID_INPUT,
      source_field,
      subdivision_level=subdivision_level,
      subdivision_side_count=2 ** subdivision_level,
      message='position_tolerance_m must be numeric',
    )
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not (
    source_field.converged
    and source_field.field is not None
    and source_field.physical_closure_verified
    and source_field.state_sampling_available
  ):
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.FIELD_REQUIRED,
      source_field,
      subdivision_level=subdivision_level,
      subdivision_side_count=2 ** subdivision_level,
      message=(
        'first-wedge remesh requires a converged ambient-closed field with '
        'a bounded state sampler'
      ),
    )
  field = source_field.field
  wedge_indices = tuple(
    index
    for index, cell in enumerate(field.cells)
    if cell.cell_kind == 'post-shock-ambient-centerline-triangle'
  )
  if len(wedge_indices) != 1:
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.WEDGE_REQUIRED,
      source_field,
      subdivision_level=subdivision_level,
      subdivision_side_count=2 ** subdivision_level,
      message=(
        'first-wedge remesh requires exactly one '
        'post-shock-ambient-centerline-triangle cell'
      ),
    )
  source_cell_index = wedge_indices[0]
  source_cell = field.cells[source_cell_index]
  if len(source_cell.vertices_xr_m) != 3:
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.GEOMETRY_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      subdivision_level=subdivision_level,
      subdivision_side_count=2 ** subdivision_level,
      message='the reflected first wedge must be triangular',
    )
  original_vertices = tuple(source_cell.vertices_xr_m)
  side_count = 2 ** subdivision_level
  first, second, third = original_vertices
  lattice: dict[tuple[int, int], tuple[float, float]] = {}
  state_samples: dict[tuple[int, int], tuple[CharacteristicState, float]] = {}
  for first_index in range(side_count + 1):
    for second_index in range(side_count + 1 - first_index):
      point = _point(
        first,
        second,
        third,
        side_count,
        first_index,
        second_index,
      )
      state = field.state_at(point, position_tolerance_m=tolerance)
      pressure = field.total_pressure_at(point, position_tolerance_m=tolerance)
      if state is None or pressure is None:
        return _failure(
          MocEulerAmbientFirstWedgeRemeshStatus.STATE_SAMPLING_FAILURE,
          source_field,
          source_cell_index=source_cell_index,
          source_cell_kind=source_cell.cell_kind,
          original_vertices=original_vertices,
          subdivision_level=subdivision_level,
          subdivision_side_count=side_count,
          message=(
            'bounded first-wedge state sampling failed at lattice point '
            f'({first_index}, {second_index})'
          ),
        )
      lattice[(first_index, second_index)] = point
      state_samples[(first_index, second_index)] = (state, float(pressure))

  cells: list[MocCharacteristicCell] = []
  samples: list[MocEulerAmbientFirstWedgeCellSample] = []

  def append_cell(keys: tuple[tuple[int, int], ...]) -> None:
    vertices = tuple(lattice[key] for key in keys)
    resolved = tuple(state_samples[key] for key in keys)
    states = tuple(item[0] for item in resolved)
    pressures = tuple(item[1] for item in resolved)
    cells.append(
      MocCharacteristicCell(
        cell_index=len(cells),
        cell_kind='post-shock-ambient-centerline-wedge-remesh',
        vertices_xr_m=vertices,
        centerline_indices=(),
        boundary_indices=(),
      )
    )
    samples.append(
      MocEulerAmbientFirstWedgeCellSample(
        vertices_xr_m=vertices,
        states=states,
        total_pressure_Pa=pressures,
      )
    )

  try:
    for first_index in range(side_count):
      for second_index in range(side_count - first_index):
        append_cell(
          (
            (first_index, second_index),
            (first_index + 1, second_index),
            (first_index, second_index + 1),
          )
        )
        if first_index + second_index <= side_count - 2:
          append_cell(
            (
              (first_index + 1, second_index),
              (first_index + 1, second_index + 1),
              (first_index, second_index + 1),
            )
          )
  except (KeyError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.GEOMETRY_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      subdivision_level=subdivision_level,
      subdivision_side_count=side_count,
      cells=tuple(cells),
      cell_samples=tuple(samples),
      message=f'first-wedge diagnostic subdivision failed: {error}',
    )
  topology = validate_moc_mesh(tuple(cells))
  if (
    not topology.connected
    or not topology.forms_closed_zone
    or topology.nonmanifold_edge_count
  ):
    return _failure(
      MocEulerAmbientFirstWedgeRemeshStatus.TOPOLOGY_FAILURE,
      source_field,
      source_cell_index=source_cell_index,
      source_cell_kind=source_cell.cell_kind,
      original_vertices=original_vertices,
      subdivision_level=subdivision_level,
      subdivision_side_count=side_count,
      cells=tuple(cells),
      cell_samples=tuple(samples),
      topology=topology,
      state_projection_verified=True,
      pressure_lineage_carried=True,
      message=f'first-wedge diagnostic subdivision topology failed: {topology.message}',
    )
  return MocEulerAmbientFirstWedgeRemeshResult(
    status=MocEulerAmbientFirstWedgeRemeshStatus.CONVERGED_DIAGNOSTIC_SUBDIVISION,
    source_field=source_field,
    source_cell_index=source_cell_index,
    source_cell_kind=source_cell.cell_kind,
    original_vertices_xr_m=original_vertices,
    subdivision_level=subdivision_level,
    subdivision_side_count=side_count,
    cells=tuple(cells),
    cell_samples=tuple(samples),
    topology=topology,
    state_projection_verified=True,
    pressure_lineage_carried=True,
    message=(
      'first reflected wedge was geometrically subdivided from bounded field '
      'samples; conservative Euler remesh closure and chain promotion remain '
      'blocked'
    ),
  )
