"""Reusable source-boundary characteristic strips for the planar MOC lane.

The reflected fan is one instance of a triangular source strip: compatible
``C+`` states are supplied on an axis boundary, compatible ``C-`` states are
supplied on an outer boundary, and the diagonal intersections must reproduce
that outer boundary.  This module keeps that numerical construction separate
from the fan/reflected-boundary orchestration so a later continued-cell solver
can reuse the same field contract without importing a reduced-order cell.

The returned strip is an open upstream field.  It is not a shock closure and
does not infer a downstream boundary or physical termination.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import ceil, floor, isfinite, sqrt
from collections.abc import Mapping, Sequence
from types import MappingProxyType

from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  centerline_characteristic_point,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.boundary import solve_ambient_pressure_free_boundary_point
from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocSourceStripStatus',
  'MocSourceStripFrontierStatus',
  'MocSourceStripFrontierResult',
  'MocSourceStripCausticStatus',
  'MocSourceStripCausticEventResult',
  'MocSourceStripCausticEdgeStatus',
  'MocSourceStripCausticEdgeStateResult',
  'MocSourceStripCausticSeedStatus',
  'MocSourceStripCausticShockSeedResult',
  'MocSourceStripRemeshStatus',
  'MocSourceStripRemeshResult',
  'MocSourceStripContinuationStatus',
  'MocSourceCharacteristicStripResult',
  'MocSourceStripContinuationResult',
  'assemble_source_characteristic_strip',
  'assemble_source_characteristic_strip_window',
  'probe_source_strip_frontier',
  'remesh_source_strip_frontier',
  'build_caustic_shock_seed',
  'extend_source_characteristic_strip_constant_k_plus',
  'extend_source_characteristic_strip_centerline_reflection',
)


class MocSourceStripStatus(str, Enum):
  """Structured outcome for a source-boundary characteristic strip."""

  CONVERGED_OPEN = 'converged_open_source_strip'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


class MocSourceStripFrontierStatus(str, Enum):
  """Outcome for a local forward-intersection frontier probe."""

  CONVERGED = 'converged_source_frontier_probe'
  INVALID_INPUT = 'invalid_input'
  NO_FORWARD_SEGMENTS = 'no_forward_frontier_segments'
####


@dataclass(frozen=True, slots=True)
class MocSourceStripFrontierResult:
  """Forward intervals available for a new axis/source row.

  This is deliberately not a source strip.  Disjoint intervals identify a
  characteristic caustic or remeshing seam; they cannot be stitched into a
  single triangular field without a new local solve.
  """

  status: MocSourceStripFrontierStatus
  source_index: int
  boundary_sample_count: int
  valid_boundary_indices: tuple[int, ...]
  valid_index_ranges: tuple[tuple[int, int], ...]
  first_invalid_index: int | None
  maximum_geometry_residual_m: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripFrontierStatus.CONVERGED
  ####

  @property
  def has_disjoint_ranges(self) -> bool:
    return len(self.valid_index_ranges) > 1
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_index': self.source_index,
      'boundary_sample_count': self.boundary_sample_count,
      'valid_boundary_indices': list(self.valid_boundary_indices),
      'valid_index_ranges': [list(value) for value in self.valid_index_ranges],
      'has_disjoint_ranges': self.has_disjoint_ranges,
      'first_invalid_index': self.first_invalid_index,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'message': self.message,
    }
####


class MocSourceStripCausticStatus(str, Enum):
  """Outcome for a local source-row caustic-event extraction."""

  DETECTED = 'caustic_detected'
  NOT_DETECTED = 'no_local_caustic_detected'
  INVALID_INPUT = 'invalid_input'
####


class MocSourceStripCausticEdgeStatus(str, Enum):
  """Outcome for one-sided state reconstruction on a crossing edge."""

  CONVERGED = 'converged_one_sided_caustic_edge'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'caustic_edge_geometry_failure'
  INVARIANT_FAILURE = 'caustic_edge_invariant_failure'
####


class MocSourceStripCausticSeedStatus(str, Enum):
  """Outcome for the bounded pre-shock caustic handoff."""

  CONVERGED_ONE_SIDED_SEED = 'converged_one_sided_caustic_seed'
  INVALID_INPUT = 'invalid_input'
  EVENT_FAILURE = 'caustic_event_failure'
  EDGE_FAILURE = 'caustic_edge_state_failure'
  INVARIANT_FAILURE = 'caustic_seed_invariant_failure'
####


@dataclass(frozen=True, slots=True)
class MocSourceStripCausticEventResult:
  """A geometric caustic event that must hand off to a new family or shock.

  The event intentionally carries no fabricated post-shock state.  It records
  the first local remesh polygon whose characteristic edges cross and the
  crossing point that a future shock/new-family solver must consume.
  """

  status: MocSourceStripCausticStatus
  source_index: int
  boundary_interval: int | None = None
  cell_kind: str | None = None
  cell_vertices_m: tuple[tuple[float, float], ...] = ()
  crossing_edge_indices: tuple[tuple[int, int], ...] = ()
  crossing_segments_m: tuple[
    tuple[tuple[float, float], tuple[float, float]],
    ...
  ] = ()
  crossing_edge_states: tuple[
    tuple[CharacteristicState, CharacteristicState],
    ...
  ] = ()
  caustic_point_m: tuple[float, float] | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if any(
      len(edge) != 2
      or any(not isinstance(state, CharacteristicState) for state in edge)
      for edge in self.crossing_edge_states
    ):
      raise TypeError(
        'caustic crossing edge states must contain pairs of '
        'CharacteristicState values'
      )
  ####

  @property
  def detected(self) -> bool:
    return self.status is MocSourceStripCausticStatus.DETECTED
  ####

  @property
  def requires_new_characteristic_family(self) -> bool:
    return self.detected
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'detected': self.detected,
      'requires_new_characteristic_family': self.requires_new_characteristic_family,
      'source_index': self.source_index,
      'boundary_interval': self.boundary_interval,
      'cell_kind': self.cell_kind,
      'cell_vertices_m': [list(point) for point in self.cell_vertices_m],
      'crossing_edge_indices': [list(pair) for pair in self.crossing_edge_indices],
      'crossing_segments_m': [
        [list(segment[0]), list(segment[1])]
        for segment in self.crossing_segments_m
      ],
      'crossing_edge_states': [
        [
          {
            'x_m': state.x_m,
            'y_m': state.y_m,
            'theta_rad': state.theta_rad,
            'mach': state.mach,
            'gamma': state.gamma,
          }
          for state in edge
        ]
        for edge in self.crossing_edge_states
      ],
      'caustic_point_m': self.caustic_point_m,
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class MocSourceStripCausticEdgeStateResult:
  """One-sided state evidence reconstructed at a caustic crossing.

  The state is an interpolation along one already-solved characteristic edge.
  It is intentionally labeled one-sided and cannot be used as a downstream
  shock state or as a chain-cell boundary without a separate shock solve.
  """

  status: MocSourceStripCausticEdgeStatus
  edge_index: int | None
  fraction: float | None
  point_m: tuple[float, float] | None
  state: CharacteristicState | None
  static_pressure_Pa: float | None
  family: CharacteristicFamily | None
  maximum_absolute_invariant_residual: float | None
  geometry_residual_m: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripCausticEdgeStatus.CONVERGED
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'edge_index': self.edge_index,
      'fraction': self.fraction,
      'point_m': self.point_m,
      'state': (
        None
        if self.state is None
        else {
          'x_m': self.state.x_m,
          'y_m': self.state.y_m,
          'theta_rad': self.state.theta_rad,
          'mach': self.state.mach,
          'gamma': self.state.gamma,
        }
      ),
      'static_pressure_Pa': self.static_pressure_Pa,
      'family': None if self.family is None else self.family.value,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'geometry_residual_m': self.geometry_residual_m,
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class MocSourceStripCausticShockSeedResult:
  """Bounded one-sided evidence for a future caustic shock/new-family solve.

  This result deliberately stops before Rankine--Hugoniot fitting.  The two
  edge states are pre-shock, one-sided reconstructions at the crossing; no
  downstream state, shock curve, entropy jump, or chain-cell promotion is
  implied by ``CONVERGED_ONE_SIDED_SEED``.
  """

  status: MocSourceStripCausticSeedStatus
  event: MocSourceStripCausticEventResult | None
  edge_states: tuple[MocSourceStripCausticEdgeStateResult, ...]
  total_pressure_Pa: float | None
  flow_angle_jump_rad: float | None
  static_pressure_jump_Pa: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripCausticSeedStatus.CONVERGED_ONE_SIDED_SEED
  ####

  @property
  def shock_state_solved(self) -> bool:
    return False
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'shock_state_solved': self.shock_state_solved,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'total_pressure_Pa': self.total_pressure_Pa,
      'flow_angle_jump_rad': self.flow_angle_jump_rad,
      'static_pressure_jump_Pa': self.static_pressure_jump_Pa,
      'event': None if self.event is None else self.event.as_report(),
      'edge_states': [edge.as_report() for edge in self.edge_states],
      'message': self.message,
    }
####


class MocSourceStripRemeshStatus(str, Enum):
  """Outcome of a local source-row remesh attempt."""

  CONVERGED_OPEN_PATCH = 'converged_open_remesh_patch'
  CAUSTIC_REQUIRES_NEW_FAMILY = 'caustic_requires_new_characteristic_family'
  TOPOLOGY_FAILURE = 'remesh_topology_failure'
  INVALID_INPUT = 'invalid_input'
####


@dataclass(frozen=True, slots=True)
class MocSourceStripRemeshResult:
  """A bounded local remesh candidate, never an implicit full-strip repair."""

  status: MocSourceStripRemeshStatus
  source_index: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult | None
  frontier: MocSourceStripFrontierResult | None
  failed_boundary_index: int | None
  message: str = ''
  caustic_event: MocSourceStripCausticEventResult | None = None
  failed_boundary_indices: tuple[int, ...] = ()

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripRemeshStatus.CONVERGED_OPEN_PATCH
  ####

  @property
  def patch_cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def connected_with_base(self) -> bool:
    return self.topology is not None and self.topology.connected
  ####

  @property
  def chain_termination_available(self) -> bool:
    """Whether the remesh can return an explicit unresolved-chain stop."""

    return (
      self.status is MocSourceStripRemeshStatus.CAUSTIC_REQUIRES_NEW_FAMILY
      and self.caustic_event is not None
      and self.caustic_event.detected
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return a typed non-physical stop at the unresolved caustic seam.

    A caustic is a boundary of the current characteristic-family solve, not
    evidence of pressure equilibration.  The decision is therefore useful to
    a continued-cell callback only as an explicit handoff to a new-family or
    shock solver; it can never mark the chain physically terminated.
    """

    if not self.chain_termination_available:
      raise ValueError(
        'a chain caustic stop requires a detected caustic event in a '
        'new-family remesh result'
      )
    assert self.caustic_event is not None
    assert self.frontier is not None
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.CHARACTERISTIC_CAUSTIC,
      message=(
        'source-strip continuation reached a characteristic caustic; a new '
        'characteristic family or shock boundary is required before another '
        'resolved MOC cell can be solved'
      ),
      diagnostics={
        'termination_model': 'unresolved-characteristic-caustic',
        'source_index': self.source_index,
        'boundary_interval': self.caustic_event.boundary_interval,
        'caustic_point_m': self.caustic_event.caustic_point_m,
        'failed_boundary_indices': self.failed_boundary_indices,
        'valid_index_ranges': self.frontier.valid_index_ranges,
        'retained_patch_cell_count': self.patch_cell_count,
        'connected_with_base': self.connected_with_base,
      },
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_index': self.source_index,
      'node_count': len(self.nodes),
      'patch_cell_count': self.patch_cell_count,
      'connected_with_base': self.connected_with_base,
      'topology': None if self.topology is None else {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_component_count': self.topology.boundary_component_count,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'frontier': None if self.frontier is None else self.frontier.as_report(),
      'failed_boundary_index': self.failed_boundary_index,
      'caustic_event': (
        None if self.caustic_event is None else self.caustic_event.as_report()
      ),
      'failed_boundary_indices': list(self.failed_boundary_indices),
      'chain_termination_available': self.chain_termination_available,
      'chain_termination_decision': (
        None
        if not self.chain_termination_available
        else self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }
####


class MocSourceStripContinuationStatus(str, Enum):
  """Outcome for a simple-wave source-strip continuation."""

  CONVERGED_EXTENDED = 'converged_constant_k_plus_extension'
  CONVERGED_CENTERLINE_REFLECTION = 'converged_centerline_reflection_extension'
  CONVERGED_TERMINAL_WINDOW = 'converged_terminal_source_window'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FAILURE = 'boundary_continuation_failure'
  STRIP_FAILURE = 'strip_assembly_failure'
####


@dataclass(frozen=True, slots=True)
class MocSourceCharacteristicStripResult:
  """A domain-bounded triangular source-boundary MOC field."""

  status: MocSourceStripStatus
  plus_source_states: tuple[CharacteristicState, ...]
  minus_source_states: tuple[CharacteristicState, ...]
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  total_pressure_Pa: float
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  message: str = ''
  source_window_start_index: int = 0
  source_window_total_count: int | None = None
  _node_by_key: MappingProxyType = field(init=False, repr=False)
  _cell_bounds_m: tuple[tuple[float, float, float, float], ...] = field(
    init=False,
    repr=False,
  )
  _cell_bins: MappingProxyType = field(init=False, repr=False)
  _spatial_origin_m: tuple[float, float] = field(init=False, repr=False)
  _spatial_bin_size_m: float = field(init=False, repr=False)
  _spatial_bins_per_axis: int = field(init=False, repr=False)

  def __post_init__(self) -> None:
    if not isfinite(float(self.total_pressure_Pa)) or self.total_pressure_Pa <= 0.0:
      raise ValueError('total_pressure_Pa must be finite and positive')
    if (
      isinstance(self.source_window_start_index, bool)
      or not isinstance(self.source_window_start_index, int)
      or self.source_window_start_index < 0
    ):
      raise ValueError('source_window_start_index must be a non-negative integer')
    total_count = self.source_window_total_count
    if total_count is None:
      total_count = self.source_window_start_index + len(self.plus_source_states)
      object.__setattr__(self, 'source_window_total_count', total_count)
    if (
      isinstance(total_count, bool)
      or not isinstance(total_count, int)
      or total_count < self.source_window_start_index + len(self.plus_source_states)
    ):
      raise ValueError(
        'source_window_total_count must cover the supplied source window'
      )
    object.__setattr__(
      self,
      '_node_by_key',
      MappingProxyType({
        (node.centerline_index, node.boundary_index): node
        for node in self.nodes
      }),
    )
    cell_bounds = tuple(
      (
        min(vertex[0] for vertex in cell.vertices_xr_m),
        max(vertex[0] for vertex in cell.vertices_xr_m),
        min(vertex[1] for vertex in cell.vertices_xr_m),
        max(vertex[1] for vertex in cell.vertices_xr_m),
      )
      for cell in self.cells
    )
    object.__setattr__(self, '_cell_bounds_m', cell_bounds)
    if cell_bounds:
      origin = (
        min(bounds[0] for bounds in cell_bounds),
        min(bounds[2] for bounds in cell_bounds),
      )
      maximum = (
        max(bounds[1] for bounds in cell_bounds),
        max(bounds[3] for bounds in cell_bounds),
      )
      span = max(maximum[0] - origin[0], maximum[1] - origin[1])
      bins_per_axis = max(1, min(64, ceil(sqrt(len(cell_bounds)))))
      bin_size = span / bins_per_axis if span > 0.0 else 1.0
    else:
      origin = (0.0, 0.0)
      bins_per_axis = 1
      bin_size = 1.0
    bins: dict[tuple[int, int], list[int]] = {}
    for index, bounds in enumerate(cell_bounds):
      lower_x = max(
        0,
        min(
          bins_per_axis - 1,
          floor((bounds[0] - origin[0]) / bin_size),
        ),
      )
      upper_x = max(
        0,
        min(
          bins_per_axis - 1,
          floor((bounds[1] - origin[0]) / bin_size),
        ),
      )
      lower_y = max(
        0,
        min(
          bins_per_axis - 1,
          floor((bounds[2] - origin[1]) / bin_size),
        ),
      )
      upper_y = max(
        0,
        min(
          bins_per_axis - 1,
          floor((bounds[3] - origin[1]) / bin_size),
        ),
      )
      for bin_x in range(lower_x, upper_x + 1):
        for bin_y in range(lower_y, upper_y + 1):
          bins.setdefault((bin_x, bin_y), []).append(index)
    object.__setattr__(
      self,
      '_cell_bins',
      MappingProxyType({key: tuple(value) for key, value in bins.items()}),
    )
    object.__setattr__(self, '_spatial_origin_m', origin)
    object.__setattr__(self, '_spatial_bin_size_m', bin_size)
    object.__setattr__(self, '_spatial_bins_per_axis', bins_per_axis)
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocSourceStripStatus.CONVERGED_OPEN
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def source_window_count(self) -> int:
    return len(self.plus_source_states)
  ####

  @property
  def is_terminal_source_window(self) -> bool:
    return self.source_window_start_index > 0
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Interpolate a state inside the strip, returning ``None`` outside it."""

    point = _finite_point(point_m, 'point_m')
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    for state in (*self.plus_source_states, *self.minus_source_states):
      if _distance(point, (state.x_m, state.y_m)) <= position_tolerance_m:
        return CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=state.theta_rad,
          mach=state.mach,
          gamma=state.gamma,
        )
    if not self._cell_bounds_m:
      return None
    bin_x = floor(
      (point[0] - self._spatial_origin_m[0]) / self._spatial_bin_size_m
    )
    bin_y = floor(
      (point[1] - self._spatial_origin_m[1]) / self._spatial_bin_size_m
    )
    candidate_indices: set[int] = set()
    for candidate_x in range(bin_x - 1, bin_x + 2):
      for candidate_y in range(bin_y - 1, bin_y + 2):
        candidate_indices.update(self._cell_bins.get((candidate_x, candidate_y), ()))
    for index in sorted(candidate_indices):
      bounds = self._cell_bounds_m[index]
      if (
        point[0] < bounds[0] - position_tolerance_m
        or point[0] > bounds[1] + position_tolerance_m
        or point[1] < bounds[2] - position_tolerance_m
        or point[1] > bounds[3] + position_tolerance_m
      ):
        continue
      cell = self.cells[index]
      samples = _cell_samples(self, cell, self._node_by_key)
      if samples is None:
        continue
      vertices, states = samples
      weights = _polygon_interpolation_weights(
        point,
        vertices,
        tolerance_m=position_tolerance_m,
      )
      if weights is None:
        continue
      theta = sum(
        weight * state.theta_rad
        for weight, state in zip(weights, states, strict=True)
      )
      nu = sum(
        weight * state.nu_rad
        for weight, state in zip(weights, states, strict=True)
      )
      inverse = inverse_prandtl_meyer_angle_rad(nu, states[0].gamma)
      if not inverse.converged or inverse.value is None:
        return None
      return CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=theta,
        mach=inverse.value,
        gamma=states[0].gamma,
      )
    return None
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the isentropic static pressure for a sampled strip state."""

    state = self.state_at(point_m, position_tolerance_m=position_tolerance_m)
    if state is None:
      return None
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    return self.total_pressure_Pa / pressure_ratio
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'plus_source_count': len(self.plus_source_states),
      'minus_source_count': len(self.minus_source_states),
      'source_window_start_index': self.source_window_start_index,
      'source_window_count': self.source_window_count,
      'source_window_total_count': self.source_window_total_count,
      'source_window_kind': (
        'terminal-source-window'
        if self.is_terminal_source_window
        else 'full-source-strip'
      ),
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'total_pressure_Pa': self.total_pressure_Pa,
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class MocSourceStripContinuationResult:
  """An open source strip extended with an explicit boundary law."""

  status: MocSourceStripContinuationStatus
  strip: MocSourceCharacteristicStripResult | None
  plus_source_states: tuple[CharacteristicState, ...]
  minus_source_states: tuple[CharacteristicState, ...]
  added_sample_count: int
  axis_step_m: float | None
  continuation_k_plus: float | None
  message: str = ''
  full_strip: MocSourceCharacteristicStripResult | None = None
  source_window_start_index: int = 0
  source_window_total_count: int | None = None
  continuation_law: str = 'constant-k-plus-simple-wave'
  frontier: MocSourceStripFrontierResult | None = None
  remesh: MocSourceStripRemeshResult | None = None
  last_converged_strip: MocSourceCharacteristicStripResult | None = None

  @property
  def converged(self) -> bool:
    return self.status in (
      MocSourceStripContinuationStatus.CONVERGED_EXTENDED,
      MocSourceStripContinuationStatus.CONVERGED_CENTERLINE_REFLECTION,
      MocSourceStripContinuationStatus.CONVERGED_TERMINAL_WINDOW,
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'added_sample_count': self.added_sample_count,
      'axis_step_m': self.axis_step_m,
      'continuation_k_plus': self.continuation_k_plus,
      'continuation_law': self.continuation_law,
      'source_window_start_index': self.source_window_start_index,
      'source_window_count': len(self.plus_source_states),
      'source_window_total_count': self.source_window_total_count,
      'strip': None if self.strip is None else self.strip.as_report(),
      'full_strip': None if self.full_strip is None else self.full_strip.as_report(),
      'frontier': None if self.frontier is None else self.frontier.as_report(),
      'remesh': None if self.remesh is None else self.remesh.as_report(),
      'last_converged_strip': (
        None
        if self.last_converged_strip is None
        else self.last_converged_strip.as_report()
      ),
      'message': self.message,
    }
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _finite_point(point_m: tuple[float, float], name: str) -> tuple[float, float]:
  if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
    raise ValueError(f'{name} must contain two finite coordinates')
  return float(point_m[0]), float(point_m[1])


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
  return ((first[0] - second[0]) ** 2 + (first[1] - second[1]) ** 2) ** 0.5


def _cross_2d(
  first: tuple[float, float],
  second: tuple[float, float],
) -> float:
  return first[0] * second[1] - first[1] * second[0]


def _segment_intersection_point(
  first_start: tuple[float, float],
  first_end: tuple[float, float],
  second_start: tuple[float, float],
  second_end: tuple[float, float],
  *,
  tolerance_m: float,
) -> tuple[float, float] | None:
  """Return a bounded segment intersection without extrapolating a bridge."""

  first_direction = (
    first_end[0] - first_start[0],
    first_end[1] - first_start[1],
  )
  second_direction = (
    second_end[0] - second_start[0],
    second_end[1] - second_start[1],
  )
  denominator = _cross_2d(first_direction, second_direction)
  scale = max(
    1.0,
    abs(first_direction[0]),
    abs(first_direction[1]),
    abs(second_direction[0]),
    abs(second_direction[1]),
  )
  if abs(denominator) <= tolerance_m * scale:
    return None
  offset = (
    second_start[0] - first_start[0],
    second_start[1] - first_start[1],
  )
  first_parameter = _cross_2d(offset, second_direction) / denominator
  second_parameter = _cross_2d(offset, first_direction) / denominator
  parameter_tolerance = tolerance_m / scale
  if not (
    -parameter_tolerance <= first_parameter <= 1.0 + parameter_tolerance
    and -parameter_tolerance <= second_parameter <= 1.0 + parameter_tolerance
  ):
    return None
  bounded_parameter = max(0.0, min(1.0, first_parameter))
  return (
    first_start[0] + bounded_parameter * first_direction[0],
    first_start[1] + bounded_parameter * first_direction[1],
  )


def _caustic_event_for_cell(
  vertices: Sequence[tuple[float, float]],
  *,
  source_index: int,
  boundary_interval: int | None,
  cell_kind: str,
  tolerance_m: float,
  vertex_states: Sequence[CharacteristicState] = (),
) -> MocSourceStripCausticEventResult:
  """Extract the crossing that makes a local remesh polygon non-simple."""

  cell_vertices = tuple(
    (float(point[0]), float(point[1]))
    for point in vertices
  )
  states = tuple(vertex_states)
  valid_states = len(states) == len(cell_vertices) and all(
    isinstance(state, CharacteristicState) for state in states
  )
  if len(cell_vertices) != 4:
    return MocSourceStripCausticEventResult(
      status=MocSourceStripCausticStatus.NOT_DETECTED,
      source_index=source_index,
      boundary_interval=boundary_interval,
      cell_kind=cell_kind,
      cell_vertices_m=cell_vertices,
      message='local remesh failure was not a four-sided characteristic crossing',
    )
  edges = tuple(
    (
      cell_vertices[index],
      cell_vertices[(index + 1) % len(cell_vertices)],
    )
    for index in range(len(cell_vertices))
  )
  for first_edge, second_edge in ((0, 2), (1, 3)):
    crossing = _segment_intersection_point(
      *edges[first_edge],
      *edges[second_edge],
      tolerance_m=tolerance_m,
    )
    if crossing is not None:
      return MocSourceStripCausticEventResult(
        status=MocSourceStripCausticStatus.DETECTED,
        source_index=source_index,
        boundary_interval=boundary_interval,
        cell_kind=cell_kind,
        cell_vertices_m=cell_vertices,
        crossing_edge_indices=((first_edge, second_edge),),
        crossing_segments_m=(edges[first_edge], edges[second_edge]),
        crossing_edge_states=(
          (
            states[first_edge],
            states[(first_edge + 1) % len(states)],
          ),
          (
            states[second_edge],
            states[(second_edge + 1) % len(states)],
          ),
        ) if valid_states else (),
        caustic_point_m=crossing,
        message=(
          'local characteristic remesh edges cross at a caustic; the crossing '
          'is retained as a handoff point and no shock state is fabricated'
        ),
      )
  return MocSourceStripCausticEventResult(
    status=MocSourceStripCausticStatus.NOT_DETECTED,
    source_index=source_index,
    boundary_interval=boundary_interval,
    cell_kind=cell_kind,
    cell_vertices_m=cell_vertices,
    message=(
      'local remesh cell was rejected, but no bounded four-edge crossing '
      'could be isolated'
    ),
  )


def _caustic_edge_failure(
  status: MocSourceStripCausticEdgeStatus,
  *,
  edge_index: int | None,
  message: str,
  fraction: float | None = None,
  point_m: tuple[float, float] | None = None,
  family: CharacteristicFamily | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  geometry_residual_m: float | None = None,
) -> MocSourceStripCausticEdgeStateResult:
  return MocSourceStripCausticEdgeStateResult(
    status=status,
    edge_index=edge_index,
    fraction=fraction,
    point_m=point_m,
    state=None,
    static_pressure_Pa=None,
    family=family,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    geometry_residual_m=geometry_residual_m,
    message=message,
  )
####


def _reconstruct_caustic_edge_state(
  edge_index: int,
  segment: tuple[tuple[float, float], tuple[float, float]],
  endpoint_states: tuple[CharacteristicState, CharacteristicState],
  crossing_point: tuple[float, float],
  total_pressure_Pa: float,
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> MocSourceStripCausticEdgeStateResult:
  """Reconstruct one state at a crossing without extrapolating the edge."""

  first_point, second_point = segment
  first_state, second_state = endpoint_states
  if not all(
    isinstance(state, CharacteristicState)
    for state in endpoint_states
  ):
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVALID_INPUT,
      edge_index=edge_index,
      message='caustic edge endpoints must be CharacteristicState values',
    )
  if (
    abs(first_state.x_m - first_point[0]) > position_tolerance_m
    or abs(first_state.y_m - first_point[1]) > position_tolerance_m
    or abs(second_state.x_m - second_point[0]) > position_tolerance_m
    or abs(second_state.y_m - second_point[1]) > position_tolerance_m
  ):
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVALID_INPUT,
      edge_index=edge_index,
      point_m=crossing_point,
      message='caustic edge endpoint states must lie on their edge segment',
    )
  if abs(first_state.gamma - second_state.gamma) > invariant_tolerance:
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVALID_INPUT,
      edge_index=edge_index,
      point_m=crossing_point,
      message='caustic edge endpoint states use different gamma values',
    )
  if not isfinite(float(total_pressure_Pa)) or total_pressure_Pa <= 0.0:
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVALID_INPUT,
      edge_index=edge_index,
      point_m=crossing_point,
      message='total_pressure_Pa must be finite and positive',
    )
  direction = (
    second_point[0] - first_point[0],
    second_point[1] - first_point[1],
  )
  length_squared = direction[0] ** 2 + direction[1] ** 2
  length = sqrt(length_squared)
  if length <= position_tolerance_m:
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.GEOMETRY_FAILURE,
      edge_index=edge_index,
      point_m=crossing_point,
      message='caustic crossing edge has zero or unresolved length',
    )
  offset = (
    crossing_point[0] - first_point[0],
    crossing_point[1] - first_point[1],
  )
  fraction = (offset[0] * direction[0] + offset[1] * direction[1]) / length_squared
  geometry_residual = abs(
    offset[0] * direction[1] - offset[1] * direction[0]
  ) / length
  fraction_tolerance = position_tolerance_m / max(length, 1.0)
  if (
    fraction < -fraction_tolerance
    or fraction > 1.0 + fraction_tolerance
    or geometry_residual > position_tolerance_m
  ):
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.GEOMETRY_FAILURE,
      edge_index=edge_index,
      fraction=fraction,
      point_m=crossing_point,
      geometry_residual_m=geometry_residual,
      message='caustic point does not lie on the bounded crossing edge',
    )
  fraction = max(0.0, min(1.0, fraction))
  k_plus_residual = abs(first_state.k_plus - second_state.k_plus)
  k_minus_residual = abs(first_state.k_minus - second_state.k_minus)
  family = (
    CharacteristicFamily.PLUS
    if k_plus_residual <= k_minus_residual
    else CharacteristicFamily.MINUS
  )
  endpoint_invariant_residual = min(k_plus_residual, k_minus_residual)
  if endpoint_invariant_residual > invariant_tolerance:
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVARIANT_FAILURE,
      edge_index=edge_index,
      fraction=fraction,
      point_m=crossing_point,
      family=family,
      maximum_absolute_invariant_residual=endpoint_invariant_residual,
      geometry_residual_m=geometry_residual,
      message=(
        'crossing edge does not preserve either characteristic invariant '
        f'(K+ residual={k_plus_residual}, K- residual={k_minus_residual})'
      ),
    )
  theta = first_state.theta_rad + fraction * (
    second_state.theta_rad - first_state.theta_rad
  )
  nu = first_state.nu_rad + fraction * (second_state.nu_rad - first_state.nu_rad)
  inverse = inverse_prandtl_meyer_angle_rad(nu, first_state.gamma)
  if not inverse.converged or inverse.value is None:
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVARIANT_FAILURE,
      edge_index=edge_index,
      fraction=fraction,
      point_m=crossing_point,
      family=family,
      maximum_absolute_invariant_residual=endpoint_invariant_residual,
      geometry_residual_m=geometry_residual,
      message=f'caustic edge Prandtl-Meyer reconstruction failed: {inverse.message}',
    )
  state = CharacteristicState(
    x_m=float(crossing_point[0]),
    y_m=float(crossing_point[1]),
    theta_rad=theta,
    mach=inverse.value,
    gamma=first_state.gamma,
  )
  interpolated_invariant = (
    state.k_plus
    if family is CharacteristicFamily.PLUS
    else state.k_minus
  )
  reference_invariant = (
    first_state.k_plus
    if family is CharacteristicFamily.PLUS
    else first_state.k_minus
  )
  interpolated_invariant_residual = abs(
    interpolated_invariant - reference_invariant
  )
  if interpolated_invariant_residual > invariant_tolerance:
    return _caustic_edge_failure(
      MocSourceStripCausticEdgeStatus.INVARIANT_FAILURE,
      edge_index=edge_index,
      fraction=fraction,
      point_m=crossing_point,
      family=family,
      maximum_absolute_invariant_residual=max(
        endpoint_invariant_residual,
        interpolated_invariant_residual,
      ),
      geometry_residual_m=geometry_residual,
      message=(
        'interpolated caustic edge state does not preserve its inferred '
        f'{family.value} invariant'
      ),
    )
  static_pressure = float(total_pressure_Pa) / (
    1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
  ) ** (state.gamma / (state.gamma - 1.0))
  return MocSourceStripCausticEdgeStateResult(
    status=MocSourceStripCausticEdgeStatus.CONVERGED,
    edge_index=edge_index,
    fraction=fraction,
    point_m=(float(crossing_point[0]), float(crossing_point[1])),
    state=state,
    static_pressure_Pa=static_pressure,
    family=family,
    maximum_absolute_invariant_residual=max(
      endpoint_invariant_residual,
      interpolated_invariant_residual,
    ),
    geometry_residual_m=geometry_residual,
    message=(
      f'one-sided pre-shock state reconstructed along a bounded '
      f'{family.value} edge; '
      'Rankine-Hugoniot/shock fitting remains pending'
    ),
  )
####


def build_caustic_shock_seed(
  event: MocSourceStripCausticEventResult,
  total_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocSourceStripCausticShockSeedResult:
  """Build bounded one-sided pre-shock evidence at a caustic crossing.

  The event must already have been detected by a source-row remesh.  The
  crossing states are reconstructed independently on the two measured edges;
  no state is extrapolated from the old strip and no downstream shock state is
  synthesized.  A converged result is therefore a handoff for a future
  entropy/new-family solve, never a physical cell or a chain seed.
  """

  if not isinstance(event, MocSourceStripCausticEventResult):
    return MocSourceStripCausticShockSeedResult(
      status=MocSourceStripCausticSeedStatus.INVALID_INPUT,
      event=None,
      edge_states=(),
      total_pressure_Pa=None,
      flow_angle_jump_rad=None,
      static_pressure_jump_Pa=None,
      message='event must be a MocSourceStripCausticEventResult',
    )
  try:
    total_pressure = float(total_pressure_Pa)
  except (TypeError, ValueError):
    total_pressure = float('nan')
  if not isfinite(total_pressure) or total_pressure <= 0.0:
    return MocSourceStripCausticShockSeedResult(
      status=MocSourceStripCausticSeedStatus.INVALID_INPUT,
      event=event,
      edge_states=(),
      total_pressure_Pa=None,
      flow_angle_jump_rad=None,
      static_pressure_jump_Pa=None,
      message='total_pressure_Pa must be finite and positive',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not event.detected:
    return MocSourceStripCausticShockSeedResult(
      status=MocSourceStripCausticSeedStatus.EVENT_FAILURE,
      event=event,
      edge_states=(),
      total_pressure_Pa=total_pressure,
      flow_angle_jump_rad=None,
      static_pressure_jump_Pa=None,
      message='caustic shock seed requires a detected caustic event',
    )
  if event.caustic_point_m is None:
    return MocSourceStripCausticShockSeedResult(
      status=MocSourceStripCausticSeedStatus.EVENT_FAILURE,
      event=event,
      edge_states=(),
      total_pressure_Pa=total_pressure,
      flow_angle_jump_rad=None,
      static_pressure_jump_Pa=None,
      message='detected caustic event has no bounded crossing point',
    )
  if (
    len(event.crossing_edge_indices) != 1
    or len(event.crossing_segments_m) != 2
    or len(event.crossing_edge_states) != 2
  ):
    return MocSourceStripCausticShockSeedResult(
      status=MocSourceStripCausticSeedStatus.EVENT_FAILURE,
      event=event,
      edge_states=(),
      total_pressure_Pa=total_pressure,
      flow_angle_jump_rad=None,
      static_pressure_jump_Pa=None,
      message=(
        'detected caustic event must carry one crossing edge pair with two '
        'bounded segments and two endpoint-state pairs'
      ),
    )
  edge_indices = event.crossing_edge_indices[0]
  edges = tuple(
    _reconstruct_caustic_edge_state(
      edge_index=edge_index,
      segment=segment,
      endpoint_states=endpoint_states,
      crossing_point=event.caustic_point_m,
      total_pressure_Pa=total_pressure,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    for edge_index, segment, endpoint_states in zip(
      edge_indices,
      event.crossing_segments_m,
      event.crossing_edge_states,
      strict=True,
    )
  )
  if any(edge.status is MocSourceStripCausticEdgeStatus.INVARIANT_FAILURE for edge in edges):
    status = MocSourceStripCausticSeedStatus.INVARIANT_FAILURE
  elif any(not edge.converged for edge in edges):
    status = MocSourceStripCausticSeedStatus.EDGE_FAILURE
  else:
    status = MocSourceStripCausticSeedStatus.CONVERGED_ONE_SIDED_SEED
  if (
    len(edges) == 2
    and isinstance(edges[0].state, CharacteristicState)
    and isinstance(edges[1].state, CharacteristicState)
  ):
    resolved_states = (edges[0].state, edges[1].state)
    flow_angle_jump = abs(
      resolved_states[0].theta_rad - resolved_states[1].theta_rad
    )
  else:
    flow_angle_jump = None
  pressures = tuple(
    edge.static_pressure_Pa
    for edge in edges
    if edge.static_pressure_Pa is not None
  )
  pressure_jump = abs(pressures[0] - pressures[1]) if len(pressures) == 2 else None
  return MocSourceStripCausticShockSeedResult(
    status=status,
    event=event,
    edge_states=edges,
    total_pressure_Pa=total_pressure,
    flow_angle_jump_rad=flow_angle_jump,
    static_pressure_jump_Pa=pressure_jump,
    message=(
      'bounded one-sided caustic seed converged; downstream shock state, '
      'entropy jump, and characteristic-family remesh remain pending'
      if status is MocSourceStripCausticSeedStatus.CONVERGED_ONE_SIDED_SEED
      else 'caustic one-sided seed could not reconstruct both crossing edges'
    ),
  )
####


def probe_source_strip_frontier(
  plus_source: CharacteristicState,
  minus_source_states: Sequence[CharacteristicState],
  *,
  source_index: int,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocSourceStripFrontierResult:
  """Probe which boundary rays remain forward for one new source state.

  The probe never repairs, reorders, or interpolates a characteristic row. It
  exists to expose the local remeshing intervals when a full triangular strip
  reaches a caustic.
  """

  if not isinstance(plus_source, CharacteristicState):
    return MocSourceStripFrontierResult(
      status=MocSourceStripFrontierStatus.INVALID_INPUT,
      source_index=source_index,
      boundary_sample_count=0,
      valid_boundary_indices=(),
      valid_index_ranges=(),
      first_invalid_index=None,
      maximum_geometry_residual_m=None,
      message='plus_source must be a CharacteristicState',
    )
  if (
    isinstance(source_index, bool)
    or not isinstance(source_index, int)
    or source_index < 0
  ):
    raise ValueError('source_index must be a non-negative integer')
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  try:
    minus = tuple(minus_source_states)
  except TypeError:
    return MocSourceStripFrontierResult(
      status=MocSourceStripFrontierStatus.INVALID_INPUT,
      source_index=source_index,
      boundary_sample_count=0,
      valid_boundary_indices=(),
      valid_index_ranges=(),
      first_invalid_index=None,
      maximum_geometry_residual_m=None,
      message='minus_source_states must be an iterable of CharacteristicState values',
    )
  if not minus or any(not isinstance(state, CharacteristicState) for state in minus):
    return MocSourceStripFrontierResult(
      status=MocSourceStripFrontierStatus.INVALID_INPUT,
      source_index=source_index,
      boundary_sample_count=len(minus),
      valid_boundary_indices=(),
      valid_index_ranges=(),
      first_invalid_index=None,
      maximum_geometry_residual_m=None,
      message='minus_source_states must contain CharacteristicState values',
    )
  if any(abs(state.gamma - plus_source.gamma) > invariant_tolerance for state in minus):
    return MocSourceStripFrontierResult(
      status=MocSourceStripFrontierStatus.INVALID_INPUT,
      source_index=source_index,
      boundary_sample_count=len(minus),
      valid_boundary_indices=(),
      valid_index_ranges=(),
      first_invalid_index=None,
      maximum_geometry_residual_m=None,
      message='source states must use one common gamma',
    )
  valid_indices: list[int] = []
  first_invalid_index: int | None = None
  geometry_residuals: list[float] = []
  for index, boundary_state in enumerate(minus):
    point_result = interior_characteristic_point(
      plus_source,
      boundary_state,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if (
      point_result.converged
      and point_result.point_m is not None
      and point_result.state is not None
      and point_result.point_m[1] >= -position_tolerance_m
    ):
      valid_indices.append(index)
      if point_result.geometry_residual is not None:
        geometry_residuals.append(abs(point_result.geometry_residual))
    elif first_invalid_index is None:
      first_invalid_index = index
  ranges: list[tuple[int, int]] = []
  for index in valid_indices:
    if not ranges or index != ranges[-1][1] + 1:
      ranges.append((index, index))
    else:
      ranges[-1] = (ranges[-1][0], index)
  if not valid_indices:
    status = MocSourceStripFrontierStatus.NO_FORWARD_SEGMENTS
    message = 'the candidate source row has no forward characteristic intersections'
  elif len(ranges) > 1:
    status = MocSourceStripFrontierStatus.CONVERGED
    message = (
      'candidate source row has disjoint forward intervals; a connected '
      'triangular strip requires an explicit remesh across the caustic'
    )
  else:
    status = MocSourceStripFrontierStatus.CONVERGED
    message = 'candidate source row has one connected forward interval'
  return MocSourceStripFrontierResult(
    status=status,
    source_index=source_index,
    boundary_sample_count=len(minus),
    valid_boundary_indices=tuple(valid_indices),
    valid_index_ranges=tuple(ranges),
    first_invalid_index=first_invalid_index,
    maximum_geometry_residual_m=max(geometry_residuals, default=None),
    message=message,
  )


def remesh_source_strip_frontier(
  base_strip: MocSourceCharacteristicStripResult,
  plus_source: CharacteristicState,
  minus_source_states: Sequence[CharacteristicState],
  frontier: MocSourceStripFrontierResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocSourceStripRemeshResult:
  """Attempt a local source-row remesh without inventing a caustic bridge.

  The existing strip remains authoritative.  Only cells whose adjacent
  characteristic intersections and polygons validate are added to the local
  candidate.  A disjoint frontier or a self-intersecting candidate returns a
  structured non-promotable result rather than forcing a connected mesh.
  """

  if not isinstance(frontier, MocSourceStripFrontierResult):
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.INVALID_INPUT,
      source_index=0,
      nodes=(),
      cells=(),
      topology=None,
      frontier=None,
      failed_boundary_index=None,
      message='frontier must be a MocSourceStripFrontierResult',
    )
  source_index = frontier.source_index
  if not isinstance(base_strip, MocSourceCharacteristicStripResult):
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.INVALID_INPUT,
      source_index=source_index,
      nodes=(),
      cells=(),
      topology=None,
      frontier=frontier,
      failed_boundary_index=None,
      message='base_strip must be a MocSourceCharacteristicStripResult',
    )
  if not base_strip.converged:
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.INVALID_INPUT,
      source_index=source_index,
      nodes=(),
      cells=(),
      topology=None,
      frontier=frontier,
      failed_boundary_index=None,
      message='base_strip must be a converged open source strip',
    )
  if not isinstance(plus_source, CharacteristicState):
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.INVALID_INPUT,
      source_index=source_index,
      nodes=(),
      cells=(),
      topology=None,
      frontier=frontier,
      failed_boundary_index=None,
      message='plus_source must be a CharacteristicState',
    )
  try:
    minus = tuple(minus_source_states)
  except TypeError:
    minus = ()
  if (
    source_index != len(base_strip.plus_source_states)
    or len(minus) != source_index + 1
    or any(not isinstance(state, CharacteristicState) for state in minus)
  ):
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.INVALID_INPUT,
      source_index=source_index,
      nodes=(),
      cells=(),
      topology=None,
      frontier=frontier,
      failed_boundary_index=None,
      message=(
        'remesh requires one new plus source and one new minus source beyond '
        'the converged base strip'
      ),
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  valid_indices = set(frontier.valid_boundary_indices)
  if any(index < 0 or index >= len(minus) for index in valid_indices):
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.INVALID_INPUT,
      source_index=source_index,
      nodes=(),
      cells=(),
      topology=None,
      frontier=frontier,
      failed_boundary_index=None,
      message='frontier contains an out-of-range boundary index',
    )
  base_nodes = {
    (node.centerline_index, node.boundary_index): node
    for node in base_strip.nodes
  }
  new_nodes: dict[int, MocCharacteristicNode] = {}
  for boundary_index in sorted(valid_indices):
    point_result = interior_characteristic_point(
      plus_source,
      minus[boundary_index],
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if (
      not point_result.converged
      or point_result.point_m is None
      or point_result.state is None
      or point_result.point_m[1] < -position_tolerance_m
    ):
      return MocSourceStripRemeshResult(
        status=MocSourceStripRemeshStatus.CAUSTIC_REQUIRES_NEW_FAMILY,
        source_index=source_index,
        nodes=tuple(new_nodes.values()),
        cells=(),
        topology=None,
        frontier=frontier,
        failed_boundary_index=boundary_index,
        failed_boundary_indices=(boundary_index,),
        message=(
          f'frontier boundary {boundary_index} cannot be remeshed as a '
          f'forward characteristic: {point_result.message}'
        ),
      )
    new_nodes[boundary_index] = MocCharacteristicNode(
      centerline_index=source_index,
      boundary_index=boundary_index,
      point_m=point_result.point_m,
      state=point_result.state,
      point_result=point_result,
      total_pressure_Pa=base_strip.total_pressure_Pa,
    )
  old_index = source_index - 1
  patch_cells: list[MocCharacteristicCell] = []
  failed_boundary_indices: list[int] = []
  caustic_event: MocSourceStripCausticEventResult | None = None

  def _failure(
    status: MocSourceStripRemeshStatus,
    message: str,
    failed_boundary_index: int | None = None,
    caustic_event: MocSourceStripCausticEventResult | None = None,
  ) -> MocSourceStripRemeshResult:
    combined = (*base_strip.cells, *patch_cells)
    topology = validate_moc_mesh(combined) if combined else None
    return MocSourceStripRemeshResult(
      status=status,
      source_index=source_index,
      nodes=tuple(new_nodes.values()),
      cells=tuple(patch_cells),
      topology=topology,
      frontier=frontier,
      failed_boundary_index=failed_boundary_index,
      message=message,
      caustic_event=caustic_event,
      failed_boundary_indices=tuple(failed_boundary_indices),
    )

  axis_vertices = (
    (base_strip.plus_source_states[-1].x_m, base_strip.plus_source_states[-1].y_m),
    (plus_source.x_m, plus_source.y_m),
    new_nodes[0].point_m,
    base_nodes[(old_index, 0)].point_m,
  ) if 0 in new_nodes and (old_index, 0) in base_nodes else ()
  axis_states = (
    base_strip.plus_source_states[-1],
    plus_source,
    new_nodes[0].state,
    base_nodes[(old_index, 0)].state,
  ) if 0 in new_nodes and (old_index, 0) in base_nodes else ()
  try:
    if not axis_vertices:
      raise KeyError('axis remesh vertices are not available')
    patch_cells.append(
      MocCharacteristicCell(
        cell_index=len(patch_cells),
        cell_kind='source-axis-remesh',
        vertices_xr_m=axis_vertices,
        centerline_indices=(old_index, source_index),
        boundary_indices=(0,),
      )
    )
  except (KeyError, ValueError) as error:
    caustic_event = (
      _caustic_event_for_cell(
        axis_vertices,
        source_index=source_index,
        boundary_interval=0,
        cell_kind='source-axis-remesh',
        tolerance_m=position_tolerance_m,
        vertex_states=axis_states,
      )
      if axis_vertices
      else None
    )
    return _failure(
      MocSourceStripRemeshStatus.CAUSTIC_REQUIRES_NEW_FAMILY,
      f'axis remesh cell could not be assembled: {error}',
      0,
      caustic_event,
    )

  for start, end in frontier.valid_index_ranges:
    for boundary_index in range(start, end):
      cell_kind = 'source-remesh-unknown'
      cell_vertices: tuple[tuple[float, float], ...] = ()
      cell_states: tuple[CharacteristicState, ...] = ()
      try:
        if boundary_index == old_index:
          if boundary_index not in new_nodes or source_index not in new_nodes:
            raise KeyError('outer remesh diagonal is not available')
          cell_kind = 'source-boundary-remesh'
          cell_vertices = (
            base_nodes[(old_index, old_index)].point_m,
            new_nodes[boundary_index].point_m,
            new_nodes[source_index].point_m,
          )
          cell_states = (
            base_nodes[(old_index, old_index)].state,
            new_nodes[boundary_index].state,
            new_nodes[source_index].state,
          )
        elif boundary_index < old_index:
          cell_kind = 'source-interior-remesh'
          cell_vertices = (
            base_nodes[(old_index, boundary_index)].point_m,
            base_nodes[(old_index, boundary_index + 1)].point_m,
            new_nodes[boundary_index + 1].point_m,
            new_nodes[boundary_index].point_m,
          )
          cell_states = (
            base_nodes[(old_index, boundary_index)].state,
            base_nodes[(old_index, boundary_index + 1)].state,
            new_nodes[boundary_index + 1].state,
            new_nodes[boundary_index].state,
          )
        else:
          continue
        patch_cells.append(
          MocCharacteristicCell(
            cell_index=len(patch_cells),
            cell_kind=cell_kind,
            vertices_xr_m=cell_vertices,
            centerline_indices=(
              (source_index,)
              if boundary_index == old_index
              else (old_index, source_index)
            ),
            boundary_indices=(
              (boundary_index, source_index)
              if boundary_index == old_index
              else (boundary_index, boundary_index + 1)
            ),
          )
        )
      except (KeyError, ValueError):
        failed_boundary_indices.append(boundary_index)
        caustic_event = _caustic_event_for_cell(
          cell_vertices,
          source_index=source_index,
          boundary_interval=boundary_index,
          cell_kind=cell_kind,
          tolerance_m=position_tolerance_m,
          vertex_states=cell_states,
        ) if caustic_event is None else caustic_event
        continue
  combined_topology = validate_moc_mesh((*base_strip.cells, *patch_cells))
  if failed_boundary_indices or frontier.has_disjoint_ranges:
    first_failed_boundary_index = (
      failed_boundary_indices[0]
      if failed_boundary_indices
      else frontier.first_invalid_index
    )
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.CAUSTIC_REQUIRES_NEW_FAMILY,
      source_index=source_index,
      nodes=tuple(new_nodes.values()),
      cells=tuple(patch_cells),
      topology=combined_topology,
      frontier=frontier,
      failed_boundary_index=first_failed_boundary_index,
      caustic_event=caustic_event,
      failed_boundary_indices=tuple(failed_boundary_indices),
      message=(
        'local remesh retained valid candidate cells but the frontier still '
        'contains a caustic/new-family seam; no disconnected bridge was invented'
      ),
    )
  if not combined_topology.connected or combined_topology.nonmanifold_edge_count:
    return MocSourceStripRemeshResult(
      status=MocSourceStripRemeshStatus.TOPOLOGY_FAILURE,
      source_index=source_index,
      nodes=tuple(new_nodes.values()),
      cells=tuple(patch_cells),
      topology=combined_topology,
      frontier=frontier,
      failed_boundary_index=None,
      caustic_event=None,
      failed_boundary_indices=(),
      message=f'remeshed source patch topology failed: {combined_topology.message}',
    )
  return MocSourceStripRemeshResult(
    status=MocSourceStripRemeshStatus.CONVERGED_OPEN_PATCH,
    source_index=source_index,
    nodes=tuple(new_nodes.values()),
    cells=tuple(patch_cells),
    topology=combined_topology,
    frontier=frontier,
    failed_boundary_index=None,
    caustic_event=None,
    failed_boundary_indices=(),
    message=(
      'local source-row remesh produced a connected open patch; full '
      'upstream and physical-boundary closure remain separate gates'
    ),
  )


def _latest_converged_source_strip(
  initial_strip: MocSourceCharacteristicStripResult,
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> MocSourceCharacteristicStripResult:
  """Retain the longest valid prefix before a source-row failure.

  A source-row geometry failure is persistent for every larger triangular
  prefix because the already assembled characteristic cells are retained;
  adding later rows cannot repair the failed cell.  The bounded binary search
  therefore finds the last complete prefix without repeatedly assembling every
  intermediate row.  The returned strip is still open and is never presented
  as a full continuation.
  """

  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  lower = len(initial_strip.plus_source_states)
  upper = min(len(plus), len(minus))
  if upper <= lower:
    return initial_strip
  candidate = assemble_source_characteristic_strip(
    plus[:upper],
    minus[:upper],
    initial_strip.total_pressure_Pa,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if candidate.converged:
    return candidate
  last = initial_strip
  failing_count = upper
  while failing_count - lower > 1:
    midpoint = (lower + failing_count) // 2
    candidate = assemble_source_characteristic_strip(
      plus[:midpoint],
      minus[:midpoint],
      initial_strip.total_pressure_Pa,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if candidate.converged:
      last = candidate
      lower = midpoint
    else:
      failing_count = midpoint
  return last
####


def _source_strip_continuation_frontier(
  last_converged_strip: MocSourceCharacteristicStripResult,
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> tuple[MocSourceStripFrontierResult | None, MocSourceStripRemeshResult | None]:
  """Probe the first source row after a retained converged prefix."""

  source_index = len(last_converged_strip.plus_source_states)
  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  if source_index >= len(plus) or source_index >= len(minus):
    return None, None
  frontier = probe_source_strip_frontier(
    plus[source_index],
    minus[:source_index + 1],
    source_index=source_index,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  remesh = remesh_source_strip_frontier(
    last_converged_strip,
    plus[source_index],
    minus[:source_index + 1],
    frontier,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  return frontier, remesh


def _failure(
  status: MocSourceStripStatus,
  plus_sources: tuple[CharacteristicState, ...],
  minus_sources: tuple[CharacteristicState, ...],
  *,
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  total_pressure_Pa: float,
  message: str,
) -> MocSourceCharacteristicStripResult:
  return MocSourceCharacteristicStripResult(
    status=status,
    plus_source_states=plus_sources,
    minus_source_states=minus_sources,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=_empty_topology() if topology is None else topology,
    total_pressure_Pa=total_pressure_Pa,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    message=message,
  )


def assemble_source_characteristic_strip(
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  total_pressure_Pa: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  source_window_start_index: int = 0,
  source_window_total_count: int | None = None,
) -> MocSourceCharacteristicStripResult:
  """Assemble a triangular strip from axis and outer source states.

  The source arrays must have the same length and at least three states.  The
  plus sources are required to lie on the symmetry line.  For each diagonal
  pair ``(i, i)``, the compatible C+/C- intersection must reproduce the
  corresponding minus-source point; this is the seam that prevents a source
  line from being silently replaced by a merely topological diagonal.
  """

  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  try:
    pressure = float(total_pressure_Pa)
  except (TypeError, ValueError):
    pressure = float('nan')
  if not isfinite(pressure) or pressure <= 0.0:
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=1.0,
      message='total_pressure_Pa must be finite and positive',
    )
  if len(plus) != len(minus) or len(plus) < 3:
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source strips require equal arrays with at least three states',
    )
  if (
    isinstance(source_window_start_index, bool)
    or not isinstance(source_window_start_index, int)
    or source_window_start_index < 0
  ):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source_window_start_index must be a non-negative integer',
    )
  if source_window_total_count is None:
    source_total_count = source_window_start_index + len(plus)
  elif (
    isinstance(source_window_total_count, bool)
    or not isinstance(source_window_total_count, int)
    or source_window_total_count < source_window_start_index + len(plus)
  ):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message=(
        'source_window_total_count must cover the supplied source window'
      ),
    )
  else:
    source_total_count = source_window_total_count
  if any(not isinstance(state, CharacteristicState) for state in (*plus, *minus)):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source arrays must contain CharacteristicState values',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(float(invariant_tolerance)) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  gamma = plus[0].gamma
  if any(abs(state.gamma - gamma) > invariant_tolerance for state in (*plus, *minus)):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='source arrays must use one common gamma',
    )
  if any(abs(state.y_m) > position_tolerance_m for state in plus):
    return _failure(
      MocSourceStripStatus.INVALID_INPUT,
      plus,
      minus,
      total_pressure_Pa=pressure,
      message='plus source states must lie on the symmetry line',
    )
  ####

  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for centerline_index in range(len(plus)):
    for boundary_index in range(centerline_index + 1):
      point_result = interior_characteristic_point(
        plus[centerline_index],
        minus[boundary_index],
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
      )
      if not point_result.converged or point_result.state is None or point_result.point_m is None:
        return _failure(
          MocSourceStripStatus.GEOMETRY_FAILURE,
          plus,
          minus,
          nodes=tuple(nodes_by_index.values()),
          total_pressure_Pa=pressure,
          message=(
            f'characteristic node ({centerline_index}, {boundary_index}) failed: '
            f'{point_result.message}'
          ),
        )
      point = point_result.point_m
      if centerline_index == boundary_index:
        expected = minus[boundary_index]
        discrepancy = _distance(point, (expected.x_m, expected.y_m))
        if discrepancy > position_tolerance_m:
          return _failure(
            MocSourceStripStatus.GEOMETRY_FAILURE,
            plus,
            minus,
            nodes=tuple(nodes_by_index.values()),
            total_pressure_Pa=pressure,
            maximum_geometry_residual_m=discrepancy,
            message=(
              f'diagonal source node ({centerline_index}, {boundary_index}) '
              f'does not reproduce its minus source point; residual={discrepancy}'
            ),
          )
        point = (expected.x_m, expected.y_m)
      nodes_by_index[(centerline_index, boundary_index)] = MocCharacteristicNode(
        centerline_index=centerline_index,
        boundary_index=boundary_index,
        point_m=(float(point[0]), float(point[1])),
        state=point_result.state,
        point_result=point_result,
        total_pressure_Pa=pressure,
      )
  ####

  nodes = tuple(nodes_by_index.values())

  def node_point(centerline_index: int, boundary_index: int) -> tuple[float, float]:
    return nodes_by_index[(centerline_index, boundary_index)].point_m

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(len(plus) - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='source-axis-strip',
          vertices_xr_m=(
            (plus[index].x_m, plus[index].y_m),
            (plus[index + 1].x_m, plus[index + 1].y_m),
            node_point(index + 1, 0),
            node_point(index, 0),
          ),
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    for row in range(1, len(plus) - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='source-interior',
            vertices_xr_m=(
              node_point(row, column),
              node_point(row + 1, column),
              node_point(row + 1, column + 1),
              node_point(row, column + 1),
            ),
            centerline_indices=(row, row + 1),
            boundary_indices=(column, column + 1),
          )
        )
    for index in range(len(plus) - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='source-boundary-strip',
          vertices_xr_m=(
            node_point(index, index),
            node_point(index + 1, index),
            (minus[index + 1].x_m, minus[index + 1].y_m),
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        )
      )
  except (KeyError, ValueError) as error:
    return _failure(
      MocSourceStripStatus.GEOMETRY_FAILURE,
      plus,
      minus,
      nodes=nodes,
      cells=cells_list,
      total_pressure_Pa=pressure,
      message=f'source characteristic cell geometry failed: {error}',
    )
  ####

  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocSourceStripStatus.TOPOLOGY_FAILURE,
      plus,
      minus,
      nodes=nodes,
      cells=cells,
      topology=topology,
      total_pressure_Pa=pressure,
      message=f'source characteristic strip topology failed: {topology.message}',
    )
  ####
  maximum_geometry_residual = max(
    (
      abs(node.point_result.geometry_residual)
      for node in nodes
      if node.point_result.geometry_residual is not None
    ),
    default=None,
  )
  maximum_invariant_residual = max(
    (
      abs(value)
      for node in nodes
      for value in (
        node.point_result.invariant_residual_plus,
        node.point_result.invariant_residual_minus,
      )
      if value is not None
    ),
    default=None,
  )
  return MocSourceCharacteristicStripResult(
    status=MocSourceStripStatus.CONVERGED_OPEN,
    plus_source_states=plus,
    minus_source_states=minus,
    nodes=nodes,
    cells=cells,
    topology=topology,
    total_pressure_Pa=pressure,
    maximum_geometry_residual_m=maximum_geometry_residual,
    maximum_absolute_invariant_residual=maximum_invariant_residual,
    message=(
      'triangular source-boundary characteristic strip converged; '
      'shock and downstream closure remain separate'
    ),
    source_window_start_index=source_window_start_index,
    source_window_total_count=source_total_count,
  )
####


def assemble_source_characteristic_strip_window(
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  total_pressure_Pa: float,
  *,
  source_window_start_index: int,
  source_window_total_count: int,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocSourceCharacteristicStripResult:
  """Assemble an explicitly labeled local window of a larger source strip.

  A terminal source window is a deliberate domain boundary.  It is useful when
  the full upstream triangular continuation has reached a characteristic
  caustic but a smaller terminal patch is still geometrically valid.  The
  omitted prefix is never reconstructed or treated as valid upstream data.
  """

  return assemble_source_characteristic_strip(
    plus_source_states,
    minus_source_states,
    total_pressure_Pa,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    source_window_start_index=source_window_start_index,
    source_window_total_count=source_window_total_count,
  )
####


def extend_source_characteristic_strip_constant_k_plus(
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  additional_sample_count: int,
  axis_step_m: float,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
  source_window_start_index: int = 0,
) -> MocSourceStripContinuationResult:
  """Extend an open source strip with a constant-``K+`` simple-wave law.

  The terminal outer-boundary ``K+`` invariant is held fixed.  New axis
  source states use ``theta = 0`` and the corresponding Prandtl--Meyer angle;
  each new outer-boundary state is then obtained from the ambient-pressure
  free-boundary primitive.  This is a deterministic upstream continuation
  suitable for investigating a continued shock-cell chain, but it is not a
  replacement for solving the physical shock/free-boundary closure.
  """

  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  try:
    total_pressure = float(total_pressure_Pa)
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=float('nan'),
      continuation_k_plus=None,
      message='pressures must be finite numeric values',
    )
  if (
    not isfinite(total_pressure)
    or total_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or total_pressure <= ambient_pressure
  ):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=float('nan'),
      continuation_k_plus=None,
      message='total pressure must exceed a finite positive ambient pressure',
    )
  if (
    isinstance(additional_sample_count, bool)
    or not isinstance(additional_sample_count, int)
    or additional_sample_count < 1
  ):
    try:
      reported_axis_step = float(axis_step_m)
    except (TypeError, ValueError):
      reported_axis_step = float('nan')
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=reported_axis_step,
      continuation_k_plus=None,
      message='additional_sample_count must be a positive integer',
    )
  try:
    axis_step = float(axis_step_m)
  except (TypeError, ValueError):
    axis_step = float('nan')
  if not isfinite(axis_step) or axis_step <= 0.0:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=None,
      message='axis_step_m must be finite and positive',
    )
  if not isfinite(float(pressure_tolerance)) or pressure_tolerance <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  if (
    isinstance(source_window_start_index, bool)
    or not isinstance(source_window_start_index, int)
    or source_window_start_index < 0
  ):
    raise ValueError('source_window_start_index must be a non-negative integer')

  initial_strip = assemble_source_characteristic_strip(
    plus,
    minus,
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if not initial_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=None,
      message=f'initial source strip is not converged: {initial_strip.message}',
    )

  continuation_k_plus = minus[-1].k_plus
  target_nu = -continuation_k_plus
  if target_nu <= 0.0:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      message='constant-K+ continuation requires a strictly positive axis Prandtl-Meyer angle',
    )
  axis_inverse = inverse_prandtl_meyer_angle_rad(target_nu, plus[-1].gamma)
  if not axis_inverse.converged or axis_inverse.value is None:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      message=(
        'constant-K+ continuation cannot construct a supersonic axis state: '
        f'{axis_inverse.message}'
      ),
    )

  extended_plus = list(plus)
  extended_minus = list(minus)

  def continuation_failure(message: str) -> MocSourceStripContinuationResult:
    last_converged_strip = _latest_converged_source_strip(
      initial_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    frontier, remesh = _source_strip_continuation_frontier(
      last_converged_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
      strip=initial_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      frontier=frontier,
      remesh=remesh,
      last_converged_strip=last_converged_strip,
      message=message,
    )

  for _ in range(additional_sample_count):
    previous_plus = extended_plus[-1]
    previous_minus = extended_minus[-1]
    incoming = CharacteristicState(
      x_m=previous_plus.x_m + axis_step,
      y_m=0.0,
      theta_rad=0.0,
      mach=axis_inverse.value,
      gamma=previous_plus.gamma,
    )
    boundary_result = solve_ambient_pressure_free_boundary_point(
      incoming,
      previous_minus,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    if (
      not boundary_result.converged
      or boundary_result.state is None
      or boundary_result.point_m is None
    ):
      return continuation_failure(
        'constant-K+ ambient boundary continuation failed after '
        f'{len(extended_minus) - len(minus)} added samples: '
        f'{boundary_result.message}'
      )
    if boundary_result.state.x_m <= previous_minus.x_m + position_tolerance_m:
      return continuation_failure(
        'constant-K+ ambient boundary continuation stopped without downstream progress'
      )
    extended_plus.append(incoming)
    extended_minus.append(boundary_result.state)

  full_strip = assemble_source_characteristic_strip(
    extended_plus,
    extended_minus,
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  last_converged_strip = (
    full_strip
    if full_strip.converged
    else _latest_converged_source_strip(
      initial_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  )
  frontier = None
  remesh = None
  if not full_strip.converged:
    frontier, remesh = _source_strip_continuation_frontier(
      last_converged_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  if source_window_start_index == 0 and full_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.CONVERGED_EXTENDED,
      strip=full_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      full_strip=full_strip,
      source_window_start_index=0,
      source_window_total_count=len(extended_plus),
      last_converged_strip=last_converged_strip,
      message=(
        'constant-K+ simple-wave source continuation converged as an open '
        'upstream strip; physical shock fitting and downstream closure remain pending'
      ),
    )

  if source_window_start_index >= len(extended_plus) - 2:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=full_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      full_strip=full_strip,
      source_window_start_index=source_window_start_index,
      source_window_total_count=len(extended_plus),
      frontier=frontier,
      remesh=remesh,
      last_converged_strip=last_converged_strip,
      message=(
        'constant-K+ source continuation reached its requested samples, but '
        'the requested terminal source window has fewer than three samples'
      ),
    )

  selected_strip = assemble_source_characteristic_strip_window(
    extended_plus[source_window_start_index:],
    extended_minus[source_window_start_index:],
    total_pressure,
    source_window_start_index=source_window_start_index,
    source_window_total_count=len(extended_plus),
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  if selected_strip.converged:
    status = (
      MocSourceStripContinuationStatus.CONVERGED_TERMINAL_WINDOW
      if source_window_start_index > 0
      else MocSourceStripContinuationStatus.CONVERGED_EXTENDED
    )
    return MocSourceStripContinuationResult(
      status=status,
      strip=selected_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      full_strip=full_strip,
      source_window_start_index=source_window_start_index,
      source_window_total_count=len(extended_plus),
      frontier=frontier,
      remesh=remesh,
      last_converged_strip=(
        selected_strip if selected_strip.converged else last_converged_strip
      ),
      message=(
        'constant-K+ source continuation exposes a converged terminal source '
        'window; the full continuation reached a characteristic caustic and '
        'physical shock fitting/downstream closure remain pending'
        if not full_strip.converged
        else (
          'constant-K+ source continuation converged with an explicitly '
          'selected terminal source window; physical shock fitting and '
          'downstream closure remain pending'
        )
      ),
    )

  if not full_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=full_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=axis_step,
      continuation_k_plus=continuation_k_plus,
      full_strip=full_strip,
      source_window_start_index=source_window_start_index,
      source_window_total_count=len(extended_plus),
      frontier=frontier,
      remesh=remesh,
      last_converged_strip=last_converged_strip,
      message=(
        'constant-K+ source continuation reached its requested samples, but '
        f'the extended strip failed: {full_strip.message}; '
        f'the selected terminal window also failed: {selected_strip.message}'
      ),
    )
  return MocSourceStripContinuationResult(
    status=MocSourceStripContinuationStatus.STRIP_FAILURE,
    strip=selected_strip,
    plus_source_states=tuple(extended_plus),
    minus_source_states=tuple(extended_minus),
    added_sample_count=len(extended_minus) - len(minus),
    axis_step_m=axis_step,
    continuation_k_plus=continuation_k_plus,
    full_strip=full_strip,
    source_window_start_index=source_window_start_index,
    source_window_total_count=len(extended_plus),
    frontier=frontier,
    remesh=remesh,
    last_converged_strip=last_converged_strip,
    message=(
      'constant-K+ source continuation reached its requested samples, but '
      f'the selected terminal window failed: {selected_strip.message}'
    ),
  )
####


def _finish_centerline_reflection_continuation(
  initial_strip: MocSourceCharacteristicStripResult,
  full_strip: MocSourceCharacteristicStripResult,
  extended_plus: Sequence[CharacteristicState],
  extended_minus: Sequence[CharacteristicState],
  *,
  original_sample_count: int,
  source_window_start_index: int,
  frontier: MocSourceStripFrontierResult | None,
  remesh: MocSourceStripRemeshResult | None,
  message: str,
  last_converged_strip: MocSourceCharacteristicStripResult | None = None,
) -> MocSourceStripContinuationResult:
  """Attach source-window semantics to a completed reflection march."""

  plus = tuple(extended_plus)
  minus = tuple(extended_minus)
  added_sample_count = len(minus) - original_sample_count
  common = {
    'plus_source_states': plus,
    'minus_source_states': minus,
    'added_sample_count': added_sample_count,
    'axis_step_m': None,
    'continuation_k_plus': None,
    'source_window_start_index': source_window_start_index,
    'source_window_total_count': len(plus),
    'continuation_law': 'centerline-c-minus-reflection-plus-ambient-pressure',
    'frontier': frontier,
    'remesh': remesh,
    'last_converged_strip': (
      full_strip if full_strip.converged
      else initial_strip if last_converged_strip is None
      else last_converged_strip
    ),
  }
  if source_window_start_index == 0:
    if full_strip.converged:
      return MocSourceStripContinuationResult(
        status=MocSourceStripContinuationStatus.CONVERGED_CENTERLINE_REFLECTION,
        strip=full_strip,
        full_strip=full_strip,
        message=message,
        **common,
      )
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=full_strip,
      full_strip=full_strip,
      message=f'{message}; extended strip failed: {full_strip.message}',
      **common,
    )
  if source_window_start_index >= len(plus) - 2:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=full_strip,
      full_strip=full_strip,
      message=(
        f'{message}; requested terminal source window has fewer than three '
        'samples'
      ),
      **common,
    )
  selected_strip = assemble_source_characteristic_strip_window(
    plus[source_window_start_index:],
    minus[source_window_start_index:],
    full_strip.total_pressure_Pa,
    source_window_start_index=source_window_start_index,
    source_window_total_count=len(plus),
  )
  if selected_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.CONVERGED_TERMINAL_WINDOW,
      strip=selected_strip,
      full_strip=full_strip,
      message=(
        f'{message}; the selected terminal source window is converged while '
        'the full source domain remains retained separately'
      ),
      **common,
    )
  return MocSourceStripContinuationResult(
    status=MocSourceStripContinuationStatus.STRIP_FAILURE,
    strip=selected_strip,
    full_strip=full_strip,
    message=(
      f'{message}; selected terminal window failed: '
      f'{selected_strip.message}'
    ),
    **common,
  )
####


def extend_source_characteristic_strip_centerline_reflection(
  plus_source_states: Sequence[CharacteristicState],
  minus_source_states: Sequence[CharacteristicState],
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  additional_sample_count: int,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
  source_window_start_index: int = 0,
) -> MocSourceStripContinuationResult:
  """Extend a source strip with a symmetry-reflection boundary law.

  Each step solves the incoming outer-boundary ``C-`` characteristic to the
  symmetry line with ``theta=0``.  That reflected axis state then supplies a
  ``C+`` characteristic to the next ambient-pressure, streamline-tangent
  boundary point.  Unlike the diagnostic constant-``K+`` extension, the
  reflected ``K+`` value and the axis location are solved at every step; no
  arbitrary axis spacing or frozen invariant is imposed.

  The result remains an open upstream field.  It is suitable for supplying a
  bounded upstream state/pressure domain to a future shock solver, but it
  does not itself fit a shock or close a continued shock-cell chain.
  """

  plus = tuple(plus_source_states)
  minus = tuple(minus_source_states)
  try:
    total_pressure = float(total_pressure_Pa)
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=None,
      continuation_k_plus=None,
      message='pressures must be finite numeric values',
      continuation_law='centerline-c-minus-reflection-plus-ambient-pressure',
    )
  if (
    not isfinite(total_pressure)
    or total_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or total_pressure <= ambient_pressure
  ):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=None,
      continuation_k_plus=None,
      message='total pressure must exceed a finite positive ambient pressure',
      continuation_law='centerline-c-minus-reflection-plus-ambient-pressure',
    )
  if (
    isinstance(additional_sample_count, bool)
    or not isinstance(additional_sample_count, int)
    or additional_sample_count < 1
  ):
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.INVALID_INPUT,
      strip=None,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=None,
      continuation_k_plus=None,
      message='additional_sample_count must be a positive integer',
      continuation_law='centerline-c-minus-reflection-plus-ambient-pressure',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if isinstance(maximum_iterations, bool) or maximum_iterations < 1:
    raise ValueError('maximum_iterations must be a positive integer')
  if (
    isinstance(source_window_start_index, bool)
    or not isinstance(source_window_start_index, int)
    or source_window_start_index < 0
  ):
    raise ValueError('source_window_start_index must be a non-negative integer')
  initial_strip = assemble_source_characteristic_strip(
    plus,
    minus,
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  law = 'centerline-c-minus-reflection-plus-ambient-pressure'
  if not initial_strip.converged:
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.STRIP_FAILURE,
      strip=initial_strip,
      plus_source_states=plus,
      minus_source_states=minus,
      added_sample_count=0,
      axis_step_m=None,
      continuation_k_plus=None,
      message=f'initial source strip is not converged: {initial_strip.message}',
      continuation_law=law,
    )
  extended_plus = list(plus)
  extended_minus = list(minus)

  def continuation_failure(message: str) -> MocSourceStripContinuationResult:
    """Retain the longest valid prefix when a boundary step fails."""

    last_converged_strip = _latest_converged_source_strip(
      initial_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    frontier, remesh = _source_strip_continuation_frontier(
      last_converged_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    return MocSourceStripContinuationResult(
      status=MocSourceStripContinuationStatus.BOUNDARY_FAILURE,
      strip=initial_strip,
      plus_source_states=tuple(extended_plus),
      minus_source_states=tuple(extended_minus),
      added_sample_count=len(extended_minus) - len(minus),
      axis_step_m=None,
      continuation_k_plus=None,
      message=message,
      continuation_law=law,
      source_window_start_index=source_window_start_index,
      source_window_total_count=len(extended_plus),
      frontier=frontier,
      remesh=remesh,
      last_converged_strip=last_converged_strip,
    )

  for step in range(additional_sample_count):
    previous_plus = extended_plus[-1]
    previous_minus = extended_minus[-1]
    axis_result = centerline_characteristic_point(
      previous_minus,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if not axis_result.converged or axis_result.state is None or axis_result.point_m is None:
      return continuation_failure(
        f'centerline reflection failed at step {step}: {axis_result.message}'
      )
    axis_state = axis_result.state
    if axis_state.x_m <= previous_plus.x_m + position_tolerance_m:
      return continuation_failure(
        f'centerline reflection step {step} has no downstream axis progress'
      )
    boundary_result = solve_ambient_pressure_free_boundary_point(
      axis_state,
      previous_minus,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    if (
      not boundary_result.converged
      or boundary_result.state is None
      or boundary_result.point_m is None
    ):
      return continuation_failure(
        'ambient boundary after centerline reflection failed at step '
        f'{step}: {boundary_result.message}'
      )
    if boundary_result.point_m[0] <= previous_minus.x_m + position_tolerance_m:
      return continuation_failure(
        f'ambient boundary after centerline reflection step {step} '
        'has no downstream progress'
      )
    if abs(boundary_result.state.k_plus - axis_state.k_plus) > invariant_tolerance:
      return continuation_failure(
        f'ambient boundary after centerline reflection step {step} '
        'did not preserve the reflected C+ invariant'
      )
    extended_plus.append(axis_state)
    extended_minus.append(boundary_result.state)
  full_strip = assemble_source_characteristic_strip(
    extended_plus,
    extended_minus,
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  last_converged_strip = (
    full_strip
    if full_strip.converged
    else _latest_converged_source_strip(
      initial_strip,
      extended_plus,
      extended_minus,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  )
  frontier, remesh = _source_strip_continuation_frontier(
    last_converged_strip,
    extended_plus,
    extended_minus,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  return _finish_centerline_reflection_continuation(
    initial_strip,
    full_strip,
    extended_plus,
    extended_minus,
    original_sample_count=len(minus),
    source_window_start_index=source_window_start_index,
    frontier=frontier,
    remesh=remesh,
    message=(
      'centerline C- reflection and ambient-pressure C+ boundary march '
      'converged as an open upstream source strip; shock fitting and '
      'downstream closure remain pending'
    ),
    last_converged_strip=last_converged_strip,
  )
####


def _cell_samples(
  strip: MocSourceCharacteristicStripResult,
  cell: MocCharacteristicCell,
  node_by_key: Mapping[tuple[int, int], MocCharacteristicNode],
) -> tuple[tuple[tuple[float, float], ...], tuple[CharacteristicState, ...]] | None:
  def node_sample(key: tuple[int, int]) -> tuple[tuple[float, float], CharacteristicState] | None:
    node = node_by_key.get(key)
    return None if node is None else (node.point_m, node.state)

  if cell.cell_kind == 'source-axis-strip':
    first, second = cell.centerline_indices
    samples = (
      ((strip.plus_source_states[first].x_m, strip.plus_source_states[first].y_m), strip.plus_source_states[first]),
      ((strip.plus_source_states[second].x_m, strip.plus_source_states[second].y_m), strip.plus_source_states[second]),
      node_sample((second, 0)),
      node_sample((first, 0)),
    )
  elif cell.cell_kind == 'source-interior':
    row, next_row = cell.centerline_indices
    column, next_column = cell.boundary_indices
    samples = (
      node_sample((row, column)),
      node_sample((next_row, column)),
      node_sample((next_row, next_column)),
      node_sample((row, next_column)),
    )
  elif cell.cell_kind == 'source-boundary-strip':
    first, second = cell.boundary_indices
    samples = (
      node_sample((first, first)),
      node_sample((second, first)),
      ((strip.minus_source_states[second].x_m, strip.minus_source_states[second].y_m), strip.minus_source_states[second]),
    )
  else:
    return None
  if any(sample is None for sample in samples):
    return None
  resolved = tuple(sample for sample in samples if sample is not None)
  return tuple(cell.vertices_xr_m), tuple(sample[1] for sample in resolved)


def _triangle_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  (ax, ay), (bx, by), (cx, cy) = vertices
  denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
  if abs(denominator) <= max(tolerance_m * tolerance_m, 1.0e-24):
    return None
  px, py = point
  first = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
  second = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10 or max(first, second, third) > 1.0 + 1.0e-10:
    return None
  return first, second, third


def _polygon_interpolation_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  if len(vertices) == 3:
    return _triangle_weights(point, vertices, tolerance_m=tolerance_m)
  first = _triangle_weights(
    point,
    (vertices[0], vertices[1], vertices[2]),
    tolerance_m=tolerance_m,
  )
  if first is not None:
    return first[0], first[1], first[2], 0.0
  second = _triangle_weights(
    point,
    (vertices[0], vertices[2], vertices[3]),
    tolerance_m=tolerance_m,
  )
  if second is not None:
    return second[0], 0.0, second[1], second[2]
  return None
####
