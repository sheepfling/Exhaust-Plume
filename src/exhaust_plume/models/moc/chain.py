"""Fidelity-isolated continuation contracts for a planar MOC cell chain.

The existing shock-train module is deliberately reduced-order.  This module
provides the separate continuation boundary for a future re-solved planar
MOC chain.  It accepts only explicitly closed, resolved MOC cells and never
converts a scaled template or a prescribed-boundary diagnostic into a MOC
cell.

The continuation callback is intentionally small.  A later solver can use it
to re-solve the next local characteristic problem, while this module owns the
common axial ordering, topology, fidelity, and safety-limit checks.  Carried
boundaries are typed as either a single characteristic trace, a composite
post-shock field perimeter, or a true axial section so one boundary is not
silently treated as another.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite, sqrt
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh

__all__ = (
  'MocCellClosureStatus',
  'MocChainBoundarySample',
  'MocChainBoundaryKind',
  'MocCharacteristicTraceStatus',
  'MocCharacteristicTraceResult',
  'MocChainCell',
  'MocChainContinuationPolicy',
  'MocChainGeometryFidelity',
  'MocChainTerminationDecision',
  'MocChainResult',
  'MocChainStatus',
  'MocChainTerminationReason',
  'continue_moc_cell_chain',
)


class MocCellClosureStatus(str, Enum):
  """Physical closure state of one planar-MOC cell."""

  CLOSED = 'closed'
  OPEN = 'open'
  PENDING = 'pending'
####


class MocChainGeometryFidelity(str, Enum):
  """Geometry provenance allowed at the MOC-chain boundary."""

  RESOLVED_PLANAR_MOC = 'resolved-planar-moc'
  PRESCRIBED_BOUNDARY_DIAGNOSTIC = 'prescribed-boundary-diagnostic'
  SCALED_REDUCED_ORDER = 'scaled-reduced-order'
####


class MocChainBoundaryKind(str, Enum):
  """Geometric meaning of a carried downstream state boundary."""

  TERMINAL_CHARACTERISTIC_TRACE = 'terminal-characteristic-trace'
  POST_SHOCK_FIELD_PERIMETER = 'post-shock-field-perimeter'
  CENTERLINE_TRACE = 'centerline-trace'
  AXIAL_SECTION = 'axial-section'
####


class MocCharacteristicTraceStatus(str, Enum):
  """Outcome of validating a carried characteristic trace."""

  CONVERGED = 'converged'
  INVALID_INPUT = 'invalid_input'
  INVARIANT_FAILURE = 'invariant_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
####


class MocChainStatus(str, Enum):
  """Structured outcome for continuation and its safety boundaries."""

  PHYSICALLY_TERMINATED = 'physically-terminated'
  SOLVER_TERMINATED = 'solver-terminated'
  TRUNCATED = 'truncated'
  OPEN_CELL = 'open-cell'
  TOPOLOGY_FAILURE = 'topology-failure'
  FIDELITY_BOUNDARY = 'fidelity-boundary'
  STATE_BOUNDARY = 'state-boundary'
  INVALID_INPUT = 'invalid-input'
  SOLVER_FAILURE = 'solver-failure'
####


class MocChainTerminationReason(str, Enum):
  """Why a chain continuation stopped."""

  PHYSICAL_TERMINATION = 'physical-termination'
  SOLVER_RETURNED_NO_NEXT_CELL = 'solver-returned-no-next-cell'
  MAX_CELL_LIMIT = 'max-cell-limit'
  AXIAL_DOMAIN_LIMIT = 'axial-domain-limit'
  OPEN_PHYSICAL_CLOSURE = 'open-physical-closure'
  TOPOLOGY_INVALID = 'topology-invalid'
  FIDELITY_NOT_ALLOWED = 'fidelity-not-allowed'
  INVALID_INPUT = 'invalid-input'
  SOLVER_ERROR = 'solver-error'
  STATE_NOT_CARRIED = 'state-not-carried'
####


@dataclass(frozen=True, slots=True)
class MocChainBoundarySample:
  """One typed characteristic state and total pressure carried downstream."""

  state: CharacteristicState
  total_pressure_Pa: float

  def __post_init__(self) -> None:
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('chain boundary state must be a CharacteristicState')
    pressure = float(self.total_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('chain boundary total pressure must be finite and positive')
    object.__setattr__(self, 'total_pressure_Pa', pressure)
  ####

  @property
  def point_m(self) -> tuple[float, float]:
    return self.state.x_m, self.state.y_m
####


@dataclass(frozen=True, slots=True)
class MocCharacteristicTraceResult:
  """Evidence that a typed boundary is one downstream characteristic.

  This validator is deliberately narrower than physical cell closure.  A
  trace can be a valid internal ``C+``/``C-`` characteristic and still need a
  centerline, compression-system, or ambient-boundary solve before it can
  seed a continued cell.
  """

  status: MocCharacteristicTraceStatus
  family: CharacteristicFamily | None
  samples: tuple[MocChainBoundarySample, ...]
  maximum_absolute_invariant_residual: float | None
  maximum_geometry_residual_m: float | None
  minimum_forward_margin_m: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCharacteristicTraceStatus.CONVERGED
  ####

  @property
  def sample_count(self) -> int:
    return len(self.samples)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'family': None if self.family is None else self.family.value,
      'sample_count': self.sample_count,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'message': self.message,
    }
  ####


def validate_characteristic_trace(
  samples: Sequence[MocChainBoundarySample],
  family: CharacteristicFamily,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
) -> MocCharacteristicTraceResult:
  """Validate a downstream, state-carrying ``C+`` or ``C-`` trace.

  Compatibility is checked against the first sample and geometry is checked
  with the averaged characteristic direction for each segment.  The
  downstream-x requirement matches the chain handoff contract.  This helper
  does not infer an axis or any other physical closure from a successful
  trace.
  """

  if not isinstance(family, CharacteristicFamily):
    return MocCharacteristicTraceResult(
      status=MocCharacteristicTraceStatus.INVALID_INPUT,
      family=None,
      samples=(),
      maximum_absolute_invariant_residual=None,
      maximum_geometry_residual_m=None,
      minimum_forward_margin_m=None,
      message='family must be a CharacteristicFamily',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    trace = tuple(samples)
  except TypeError:
    return MocCharacteristicTraceResult(
      status=MocCharacteristicTraceStatus.INVALID_INPUT,
      family=family,
      samples=(),
      maximum_absolute_invariant_residual=None,
      maximum_geometry_residual_m=None,
      minimum_forward_margin_m=None,
      message='samples must be an iterable of MocChainBoundarySample values',
    )
  if len(trace) < 2:
    return MocCharacteristicTraceResult(
      status=MocCharacteristicTraceStatus.INVALID_INPUT,
      family=family,
      samples=trace,
      maximum_absolute_invariant_residual=None,
      maximum_geometry_residual_m=None,
      minimum_forward_margin_m=None,
      message='a characteristic trace requires at least two samples',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in trace):
    return MocCharacteristicTraceResult(
      status=MocCharacteristicTraceStatus.INVALID_INPUT,
      family=family,
      samples=trace,
      maximum_absolute_invariant_residual=None,
      maximum_geometry_residual_m=None,
      minimum_forward_margin_m=None,
      message='samples must contain MocChainBoundarySample values',
    )
  gamma = trace[0].state.gamma
  reference_invariant = (
    trace[0].state.k_plus if family is CharacteristicFamily.PLUS
    else trace[0].state.k_minus
  )
  invariant_residuals: list[float] = []
  geometry_residuals: list[float] = []
  forward_margins: list[float] = []
  for index, (first, second) in enumerate(zip(trace[:-1], trace[1:], strict=True)):
    first_state = first.state
    second_state = second.state
    if abs(second_state.gamma - gamma) > invariant_tolerance:
      return MocCharacteristicTraceResult(
        status=MocCharacteristicTraceStatus.INVALID_INPUT,
        family=family,
        samples=trace,
        maximum_absolute_invariant_residual=max(map(abs, invariant_residuals), default=None),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        minimum_forward_margin_m=min(forward_margins, default=None),
        message=f'trace sample {index + 1} uses a different gamma',
      )
    invariant = (
      second_state.k_plus if family is CharacteristicFamily.PLUS
      else second_state.k_minus
    ) - reference_invariant
    invariant_residuals.append(invariant)
    if abs(invariant) > invariant_tolerance:
      return MocCharacteristicTraceResult(
        status=MocCharacteristicTraceStatus.INVARIANT_FAILURE,
        family=family,
        samples=trace,
        maximum_absolute_invariant_residual=max(map(abs, invariant_residuals)),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        minimum_forward_margin_m=min(forward_margins, default=None),
        message=(
          f'trace sample {index + 1} does not preserve the '
          f'{family.value} invariant'
        ),
      )
    displacement = (
      second_state.x_m - first_state.x_m,
      second_state.y_m - first_state.y_m,
    )
    if displacement[0] <= position_tolerance_m:
      return MocCharacteristicTraceResult(
        status=MocCharacteristicTraceStatus.GEOMETRY_FAILURE,
        family=family,
        samples=trace,
        maximum_absolute_invariant_residual=max(map(abs, invariant_residuals)),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        minimum_forward_margin_m=min(forward_margins, default=None),
        message=(
          f'trace sample {index + 1} is not strictly downstream in x'
        ),
      )
    first_direction = first_state.direction(family)
    second_direction = second_state.direction(family)
    averaged_direction = (
      0.5 * (first_direction[0] + second_direction[0]),
      0.5 * (first_direction[1] + second_direction[1]),
    )
    direction_norm = sqrt(
      averaged_direction[0] ** 2 + averaged_direction[1] ** 2
    )
    if direction_norm <= position_tolerance_m:
      return MocCharacteristicTraceResult(
        status=MocCharacteristicTraceStatus.GEOMETRY_FAILURE,
        family=family,
        samples=trace,
        maximum_absolute_invariant_residual=max(map(abs, invariant_residuals)),
        maximum_geometry_residual_m=max(geometry_residuals, default=None),
        minimum_forward_margin_m=min(forward_margins, default=None),
        message=f'trace segment {index} has an undefined averaged direction',
      )
    unit_direction = (
      averaged_direction[0] / direction_norm,
      averaged_direction[1] / direction_norm,
    )
    forward_margin = (
      displacement[0] * unit_direction[0]
      + displacement[1] * unit_direction[1]
    )
    geometry_residual = abs(
      displacement[0] * unit_direction[1]
      - displacement[1] * unit_direction[0]
    )
    geometry_residuals.append(geometry_residual)
    forward_margins.append(forward_margin)
    if forward_margin <= position_tolerance_m or geometry_residual > position_tolerance_m:
      return MocCharacteristicTraceResult(
        status=MocCharacteristicTraceStatus.GEOMETRY_FAILURE,
        family=family,
        samples=trace,
        maximum_absolute_invariant_residual=max(map(abs, invariant_residuals)),
        maximum_geometry_residual_m=max(geometry_residuals),
        minimum_forward_margin_m=min(forward_margins),
        message=f'trace segment {index} is not a forward {family.value} characteristic',
      )
  ####
  return MocCharacteristicTraceResult(
    status=MocCharacteristicTraceStatus.CONVERGED,
    family=family,
    samples=trace,
    maximum_absolute_invariant_residual=max(map(abs, invariant_residuals), default=None),
    maximum_geometry_residual_m=max(geometry_residuals, default=None),
    minimum_forward_margin_m=min(forward_margins, default=None),
  )
####


@dataclass(frozen=True, slots=True)
class MocChainTerminationDecision:
  """Explicit solver-side decision to stop a continued cell chain.

  Returning ``None`` from a continuation callback remains a backward-compatible
  numerical stop and never implies physical equilibration.  A solver that has
  actually satisfied its physical termination condition must return this
  typed decision with ``physical_termination=True`` instead.  The distinction
  is intentionally made at the callback boundary so a planner or a numerical
  safety limit cannot accidentally be reported as a physical end state.
  """

  physical_termination: bool
  reason: MocChainTerminationReason = MocChainTerminationReason.PHYSICAL_TERMINATION
  message: str = ''
  diagnostics: dict[str, Any] | MappingProxyType = field(default_factory=dict)

  def __post_init__(self) -> None:
    if not isinstance(self.physical_termination, bool):
      raise TypeError('physical_termination must be a bool')
    if not isinstance(self.reason, MocChainTerminationReason):
      raise TypeError('reason must be a MocChainTerminationReason')
    if self.physical_termination != (
        self.reason is MocChainTerminationReason.PHYSICAL_TERMINATION
    ):
      raise ValueError(
        'physical termination decisions must use the physical-termination reason'
      )
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####


@dataclass(frozen=True, slots=True)
class MocChainCell:
  """One explicitly bounded cell supplied to the MOC continuation lane.

  ``mesh`` contains polygon-like objects exposing ``vertices_xr_m``.  The
  cell's physical closure is separate from the mesh topology: a topologically
  bounded polygon is not promoted to a physical shock closure unless the
  producing solver explicitly marks ``physical_closure=CLOSED``.

  A ``POST_SHOCK_FIELD_PERIMETER`` is an ordered, state-carrying edge made of
  multiple characteristic segments.  It is deliberately distinct from a
  single invariant-preserving ``TERMINAL_CHARACTERISTIC_TRACE``.
  """

  cell_index: int
  start_x_m: float
  end_x_m: float
  mesh: tuple[object, ...]
  geometry_fidelity: MocChainGeometryFidelity
  physical_closure: MocCellClosureStatus
  diagnostics: dict[str, Any] | MappingProxyType = field(default_factory=dict)
  continuation_boundary: tuple[MocChainBoundarySample, ...] = ()
  continuation_boundary_kind: MocChainBoundaryKind = (
    MocChainBoundaryKind.TERMINAL_CHARACTERISTIC_TRACE
  )

  def __post_init__(self) -> None:
    if isinstance(self.cell_index, bool) or self.cell_index < 1:
      raise ValueError('cell_index must be a positive integer')
    for name in ('start_x_m', 'end_x_m'):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
    if self.end_x_m <= self.start_x_m:
      raise ValueError('cell end_x_m must be strictly downstream of start_x_m')
    if not isinstance(self.geometry_fidelity, MocChainGeometryFidelity):
      raise TypeError('geometry_fidelity must be a MocChainGeometryFidelity')
    if not isinstance(self.physical_closure, MocCellClosureStatus):
      raise TypeError('physical_closure must be a MocCellClosureStatus')
    if not isinstance(self.continuation_boundary_kind, MocChainBoundaryKind):
      raise TypeError(
        'continuation_boundary_kind must be a MocChainBoundaryKind'
      )
    mesh = tuple(self.mesh)
    if not mesh:
      raise ValueError('mesh must contain at least one polygon-like cell')
    object.__setattr__(self, 'mesh', mesh)
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
    boundary = tuple(self.continuation_boundary)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in boundary):
      raise TypeError(
        'continuation_boundary must contain MocChainBoundarySample values'
      )
    if self.continuation_boundary_kind is MocChainBoundaryKind.AXIAL_SECTION and boundary:
      section_x = boundary[0].state.x_m
      if any(abs(sample.state.x_m - section_x) > 1.0e-10 for sample in boundary[1:]):
        raise ValueError(
          'an axial-section continuation boundary must lie on one x plane'
        )
    object.__setattr__(self, 'continuation_boundary', boundary)
  ####

  @property
  def topology(self) -> MocTopologyResult:
    """Return topology diagnostics for this cell's supplied mesh."""

    return validate_moc_mesh(self.mesh)
  ####

  @property
  def mesh_is_well_formed(self) -> bool:
    """Whether the supplied polygons form one connected bounded patch."""

    topology = self.topology
    return topology.connected and topology.forms_closed_zone and not topology.nonmanifold_edge_count
  ####

  @property
  def resolved(self) -> bool:
    """Whether the cell is eligible for a resolved-MOC chain."""

    return (
      self.geometry_fidelity is MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
      and self.physical_closure is MocCellClosureStatus.CLOSED
      and self.mesh_is_well_formed
    )
####

  @property
  def carries_state(self) -> bool:
    """Whether this cell has a typed downstream boundary for re-solving."""

    return bool(self.continuation_boundary)
####

  @property
  def continuation_total_pressure_range_Pa(self) -> tuple[float, float] | None:
    """Return the carried boundary's total-pressure range, if present.

    This is a bookkeeping diagnostic for a continued chain.  It does not
    assert a physical shock loss by itself; that remains the responsibility of
    the producing field's closure diagnostics and the handoff validation.
    """

    if not self.continuation_boundary:
      return None
    pressures = tuple(
      sample.total_pressure_Pa for sample in self.continuation_boundary
    )
    return min(pressures), max(pressures)
####


@dataclass(frozen=True, slots=True)
class MocChainContinuationPolicy:
  """Safety and fidelity policy for a re-solved planar-MOC chain."""

  max_cells: int = 16
  max_axial_distance_m: float | None = None
  position_tolerance_m: float = 1.0e-10
  allowed_fidelities: tuple[MocChainGeometryFidelity, ...] = (
    MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
  )
  require_state_carry: bool = False
  state_tolerance: float = 1.0e-10

  def __post_init__(self) -> None:
    if isinstance(self.max_cells, bool) or self.max_cells < 1:
      raise ValueError('max_cells must be a positive integer')
    if self.max_axial_distance_m is not None and (
        not isfinite(float(self.max_axial_distance_m))
        or self.max_axial_distance_m <= 0.0
    ):
      raise ValueError('max_axial_distance_m must be finite and positive when supplied')
    if not isfinite(float(self.position_tolerance_m)) or self.position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    if not isfinite(float(self.state_tolerance)) or self.state_tolerance <= 0.0:
      raise ValueError('state_tolerance must be finite and positive')
    fidelities = tuple(self.allowed_fidelities)
    if not fidelities or any(
        not isinstance(fidelity, MocChainGeometryFidelity)
        for fidelity in fidelities
    ):
      raise ValueError('allowed_fidelities must contain at least one valid fidelity')
    if len(set(fidelities)) != len(fidelities):
      raise ValueError('allowed_fidelities must not contain duplicates')
    if any(
        fidelity is not MocChainGeometryFidelity.RESOLVED_PLANAR_MOC
        for fidelity in fidelities
    ):
      raise ValueError(
        'a resolved planar-MOC chain may allow only '
        'RESOLVED_PLANAR_MOC fidelity'
      )
    if not isinstance(self.require_state_carry, bool):
      raise TypeError('require_state_carry must be a bool')
    object.__setattr__(self, 'allowed_fidelities', fidelities)
  ####


@dataclass(frozen=True, slots=True)
class MocChainResult:
  """Continuation output with explicit termination and fidelity metadata."""

  cells: tuple[MocChainCell, ...]
  status: MocChainStatus
  termination_reason: MocChainTerminationReason
  physical_termination: bool
  message: str = ''
  diagnostics: dict[str, Any] | MappingProxyType = field(default_factory=dict)

  def __post_init__(self) -> None:
    object.__setattr__(self, 'cells', tuple(self.cells))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def end_x_m(self) -> float | None:
    return None if not self.cells else self.cells[-1].end_x_m
  ####

  @property
  def resolved(self) -> bool:
    return bool(self.cells) and all(cell.resolved for cell in self.cells)
  ####

  def as_report(self) -> dict[str, Any]:
    fidelity_counts: dict[str, int] = {}
    for cell in self.cells:
      key = cell.geometry_fidelity.value
      fidelity_counts[key] = fidelity_counts.get(key, 0) + 1
    pressure_ranges = tuple(
      (cell.cell_index, cell.continuation_total_pressure_range_Pa)
      for cell in self.cells
      if cell.continuation_total_pressure_range_Pa is not None
    )
    pressure_maxima = tuple(
      pressure_range[1]
      for _cell_index, pressure_range in pressure_ranges
      if pressure_range is not None
    )
    pressure_maxima_nonincreasing = None
    if len(pressure_maxima) >= 2:
      pressure_maxima_nonincreasing = all(
        current <= previous + 1.0e-12 * max(1.0, abs(previous), abs(current))
        for previous, current in zip(pressure_maxima, pressure_maxima[1:])
      )
    return {
      'status': self.status.value,
      'termination_reason': self.termination_reason.value,
      'physical_termination': self.physical_termination,
      'cell_count': self.cell_count,
      'end_x_m': self.end_x_m,
      'resolved': self.resolved,
      'state_carry_count': sum(cell.carries_state for cell in self.cells),
      'continuation_boundary_kinds': sorted({
        cell.continuation_boundary_kind.value for cell in self.cells
        if cell.carries_state
      }),
      'continuation_total_pressure_ranges_Pa': [
        {
          'cell_index': cell_index,
          'minimum_Pa': pressure_range[0],
          'maximum_Pa': pressure_range[1],
        }
        for cell_index, pressure_range in pressure_ranges
      ],
      'continuation_boundary_maxima_nonincreasing': pressure_maxima_nonincreasing,
      'geometry_fidelity_counts': fidelity_counts,
      'diagnostics': dict(self.diagnostics),
      'message': self.message,
    }
####


MocCellContinuationSolver = Callable[
  [MocChainCell, int], MocChainCell | MocChainTerminationDecision | None
]


def _result(
    cells: tuple[MocChainCell, ...],
    *,
    status: MocChainStatus,
    reason: MocChainTerminationReason,
    physical_termination: bool = False,
    message: str,
    diagnostics: dict[str, Any] | None = None,
) -> MocChainResult:
  return MocChainResult(
    cells=cells,
    status=status,
    termination_reason=reason,
    physical_termination=physical_termination,
    message=message,
    diagnostics={} if diagnostics is None else diagnostics,
  )
####


def _validate_cell_mesh(cell: MocChainCell) -> str | None:
  topology = cell.topology
  if topology.status.value == 'invalid_input':
    return topology.message
  if not topology.connected:
    return topology.message
  if topology.nonmanifold_edge_count:
    return topology.message
  if not topology.forms_closed_zone:
    return topology.message
  return None
####


def _validate_state_carry(cell: MocChainCell) -> str | None:
  if not cell.continuation_boundary:
    return 'cell does not carry a downstream characteristic state boundary'
  if len(cell.continuation_boundary) < 3:
    return 'state-carrying MOC cells require at least three boundary samples'
  if cell.continuation_boundary_kind is MocChainBoundaryKind.AXIAL_SECTION:
    section_x = cell.continuation_boundary[0].state.x_m
    if any(
        abs(sample.state.x_m - section_x) > 1.0e-10
        for sample in cell.continuation_boundary[1:]
    ):
      return 'axial-section continuation samples do not lie on one x plane'
    return None
  previous_x: float | None = None
  for index, sample in enumerate(cell.continuation_boundary):
    x_value = sample.state.x_m
    if previous_x is not None and x_value <= previous_x:
      return f'continuation boundary sample {index} is not strictly downstream in x'
    if (
      cell.continuation_boundary_kind is MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
      and sample.state.y_m < -1.0e-10
    ):
      return f'post-shock field perimeter sample {index} lies below the symmetry line'
    previous_x = x_value
  return None
####


def continue_moc_cell_chain(
    seed: MocChainCell,
    solve_next: MocCellContinuationSolver,
    policy: MocChainContinuationPolicy | None = None,
) -> MocChainResult:
  """Continue a chain using a caller-supplied re-solved MOC cell callback.

  The callback is never called for an open or diagnostically prescribed seed.
  A reduced-order candidate is rejected at the fidelity boundary rather than
  appended and relabeled.  Returning ``None`` is an explicit solver-side
  termination and is not treated as physical equilibration by this contract.
  """

  if not isinstance(seed, MocChainCell):
    return _result(
      (),
      status=MocChainStatus.INVALID_INPUT,
      reason=MocChainTerminationReason.INVALID_INPUT,
      message='seed must be a MocChainCell',
    )
  if not callable(solve_next):
    return _result(
      (),
      status=MocChainStatus.INVALID_INPUT,
      reason=MocChainTerminationReason.INVALID_INPUT,
      message='solve_next must be callable',
    )
  if policy is None:
    policy = MocChainContinuationPolicy()
  if seed.cell_index != 1:
    return _result(
      (seed,),
      status=MocChainStatus.INVALID_INPUT,
      reason=MocChainTerminationReason.INVALID_INPUT,
      message='MOC chain seed must have cell_index=1',
    )
  if seed.geometry_fidelity not in policy.allowed_fidelities:
    return _result(
      (seed,),
      status=MocChainStatus.FIDELITY_BOUNDARY,
      reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
      message=(
        f'seed fidelity {seed.geometry_fidelity.value!r} is not allowed in '
        'the resolved planar-MOC chain'
      ),
    )
  mesh_error = _validate_cell_mesh(seed)
  if mesh_error is not None:
    return _result(
      (seed,),
      status=MocChainStatus.TOPOLOGY_FAILURE,
      reason=MocChainTerminationReason.TOPOLOGY_INVALID,
      message=f'MOC chain seed mesh is not a connected bounded patch: {mesh_error}',
    )
  if seed.physical_closure is not MocCellClosureStatus.CLOSED:
    return _result(
      (seed,),
      status=MocChainStatus.OPEN_CELL,
      reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'MOC chain continuation is held until the seed has an explicit '
        f'physical closure; received {seed.physical_closure.value!r}'
      ),
    )
  if policy.require_state_carry:
    state_error = _validate_state_carry(seed)
    if state_error is not None:
      return _result(
        (seed,),
        status=MocChainStatus.STATE_BOUNDARY,
        reason=MocChainTerminationReason.STATE_NOT_CARRIED,
        message=f'MOC chain seed has no usable state carry: {state_error}',
      )
  ####

  cells = [seed]
  while True:
    current = cells[-1]
    if len(cells) >= policy.max_cells:
      return _result(
        tuple(cells),
        status=MocChainStatus.TRUNCATED,
        reason=MocChainTerminationReason.MAX_CELL_LIMIT,
        message='MOC chain reached the configured maximum cell count',
      )
    if policy.max_axial_distance_m is not None and current.end_x_m >= policy.max_axial_distance_m:
      return _result(
        tuple(cells),
        status=MocChainStatus.TRUNCATED,
        reason=MocChainTerminationReason.AXIAL_DOMAIN_LIMIT,
        message='MOC chain reached the configured axial domain limit',
      )
    try:
      candidate = solve_next(current, current.cell_index + 1)
    except (ArithmeticError, FloatingPointError, ValueError) as error:
      return _result(
        tuple(cells),
        status=MocChainStatus.SOLVER_FAILURE,
        reason=MocChainTerminationReason.SOLVER_ERROR,
        message=f'next MOC cell solver failed: {error}',
      )
    if isinstance(candidate, MocChainTerminationDecision):
      return _result(
        tuple(cells),
        status=(
          MocChainStatus.PHYSICALLY_TERMINATED
          if candidate.physical_termination
          else MocChainStatus.SOLVER_TERMINATED
        ),
        reason=candidate.reason,
        physical_termination=candidate.physical_termination,
        message=(
          candidate.message
          or (
            'MOC continuation reached an explicit physical termination condition'
            if candidate.physical_termination
            else 'MOC continuation returned an explicit solver termination decision'
          )
        ),
        diagnostics=dict(candidate.diagnostics),
      )
    if candidate is None:
      return _result(
        tuple(cells),
        status=MocChainStatus.SOLVER_TERMINATED,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'MOC continuation callback returned no next cell; physical '
          'termination was not inferred'
        ),
      )
    if not isinstance(candidate, MocChainCell):
      return _result(
        tuple(cells),
        status=MocChainStatus.INVALID_INPUT,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message='MOC continuation callback must return MocChainCell or None',
      )
    if candidate.cell_index != current.cell_index + 1:
      return _result(
        tuple(cells),
        status=MocChainStatus.INVALID_INPUT,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message='continued MOC cell indices must increase by one',
      )
    if abs(candidate.start_x_m - current.end_x_m) > policy.position_tolerance_m:
      return _result(
        tuple(cells),
        status=MocChainStatus.INVALID_INPUT,
        reason=MocChainTerminationReason.INVALID_INPUT,
        message='continued MOC cells must share an axial boundary',
      )
    if policy.max_axial_distance_m is not None and candidate.end_x_m > policy.max_axial_distance_m + policy.position_tolerance_m:
      return _result(
        tuple(cells),
        status=MocChainStatus.TRUNCATED,
        reason=MocChainTerminationReason.AXIAL_DOMAIN_LIMIT,
        message='next MOC cell exceeds the configured axial domain limit',
      )
    if candidate.geometry_fidelity not in policy.allowed_fidelities:
      return _result(
        tuple(cells),
        status=MocChainStatus.FIDELITY_BOUNDARY,
        reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
        message=(
          f'continued cell {candidate.cell_index} has fidelity '
          f'{candidate.geometry_fidelity.value!r}; reduced-order continuation '
          'belongs to the shock-train lane'
        ),
      )
    if policy.require_state_carry:
      state_error = _validate_state_carry(candidate)
      if state_error is not None:
        return _result(
          tuple(cells),
          status=MocChainStatus.STATE_BOUNDARY,
          reason=MocChainTerminationReason.STATE_NOT_CARRIED,
          message=(
            f'MOC cell {candidate.cell_index} did not carry a usable '
            f'state boundary: {state_error}'
          ),
        )
    mesh_error = _validate_cell_mesh(candidate)
    cells.append(candidate)
    if mesh_error is not None:
      return _result(
        tuple(cells),
        status=MocChainStatus.TOPOLOGY_FAILURE,
        reason=MocChainTerminationReason.TOPOLOGY_INVALID,
        message=(
          f'MOC cell {candidate.cell_index} mesh is not a connected bounded '
          f'patch: {mesh_error}'
        ),
      )
    if candidate.physical_closure is not MocCellClosureStatus.CLOSED:
      return _result(
        tuple(cells),
        status=MocChainStatus.OPEN_CELL,
        reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        message=(
          f'MOC cell {candidate.cell_index} continuation returned '
          f'{candidate.physical_closure.value!r} physical closure'
        ),
      )
  ####
