"""Companion-boundary characteristic strip for the Euler shock lane.

The conservative shock curve is a mixed characteristic boundary: one
characteristic family enters the downstream domain from the shock while the
other must come from a second boundary.  This module assembles that explicit
one-layer strip without treating a prescribed companion boundary as a closed
shock cell or as a production-quality Euler field.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  MocEulerShockBoundaryOrientation,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicPointResult,
  CharacteristicState,
  MocPrimitiveStatus,
  interior_characteristic_point,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode

__all__ = (
  'MocEulerCompanionFieldStatus',
  'MocEulerCompanionFieldResult',
  'assemble_euler_consistent_companion_characteristic_strip',
)


class MocEulerCompanionFieldStatus(str, Enum):
  """Outcome of an explicit companion-boundary characteristic strip."""

  CONVERGED_OPEN_COMPANION_FIELD = 'converged_open_companion_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'shock_boundary_required'
  COMPANION_BOUNDARY_REQUIRED = 'companion_boundary_required'
  CHARACTERISTIC_ORIENTATION_FAILURE = 'characteristic_orientation_failure'
  PRESSURE_FAILURE = 'pressure_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerCompanionFieldResult:
  """A bounded shock/companion characteristic strip.

  The strip is deliberately open in the physical sense.  Its cells form a
  polygonal patch, but the companion boundary is caller-supplied and no
  ambient, reflected free-boundary, or downstream chain closure is inferred.
  """

  status: MocEulerCompanionFieldStatus
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary: MocEulerShockBoundaryCurveResult | None = None
  shock_boundary_points_m: tuple[tuple[float, float], ...] = ()
  companion_boundary_points_m: tuple[tuple[float, float], ...] = ()
  interior_points_m: tuple[tuple[float, float], ...] = ()
  shock_boundary_states: tuple[CharacteristicState, ...] = ()
  shock_boundary_total_pressure_Pa: tuple[float, ...] = ()
  companion_boundary_states: tuple[CharacteristicState, ...] = ()
  companion_boundary_total_pressure_Pa: tuple[float, ...] = ()
  interior_states: tuple[CharacteristicState, ...] = ()
  interior_total_pressure_Pa: tuple[float, ...] = ()
  point_results: tuple[CharacteristicPointResult, ...] = ()
  shock_boundary_orientation: MocEulerShockBoundaryOrientation | None = None
  shock_boundary_local_euler_verified: bool = False
  companion_boundary_contract_verified: bool = False
  pressure_lineage_verified: bool = False
  maximum_geometry_residual_m: float | None = None
  maximum_absolute_invariant_residual: float | None = None
  minimum_forward_margin_m: float | None = None
  maximum_companion_pressure_residual: float | None = None
  position_tolerance_m: float = 1.0e-10
  invariant_tolerance: float = 1.0e-10
  pressure_tolerance: float = 1.0e-10
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerCompanionFieldStatus):
      raise TypeError('status must be a MocEulerCompanionFieldStatus')
    for name in (
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    if len(self.nodes) != len(self.point_results):
      raise ValueError('nodes and point_results must have equal lengths')
    if len(self.nodes) != len(self.interior_states):
      raise ValueError('nodes and interior states must have equal lengths')
    if len(self.nodes) != len(self.interior_total_pressure_Pa):
      raise ValueError('nodes and interior pressures must have equal lengths')
    if len(self.shock_boundary_points_m) != len(self.shock_boundary_states):
      raise ValueError('shock boundary points and states must have equal lengths')
    if self.shock_boundary_total_pressure_Pa and len(
      self.shock_boundary_total_pressure_Pa
    ) != len(self.shock_boundary_points_m):
      raise ValueError(
        'shock boundary points and pressures must have equal lengths'
      )
    if len(self.companion_boundary_points_m) != len(self.companion_boundary_states):
      raise ValueError('companion boundary points and states must have equal lengths')
    if self.companion_boundary_total_pressure_Pa and len(
      self.companion_boundary_total_pressure_Pa
    ) != len(self.companion_boundary_points_m):
      raise ValueError(
        'companion boundary points and pressures must have equal lengths'
      )
    if len(self.interior_points_m) != len(self.nodes):
      raise ValueError('interior points and nodes must have equal lengths')
    for name, states in (
      ('shock_boundary_states', self.shock_boundary_states),
      ('companion_boundary_states', self.companion_boundary_states),
      ('interior_states', self.interior_states),
    ):
      if any(not isinstance(state, CharacteristicState) for state in states):
        raise TypeError(f'{name} must contain CharacteristicState values')
    for name, points in (
      ('shock_boundary_points_m', self.shock_boundary_points_m),
      ('companion_boundary_points_m', self.companion_boundary_points_m),
      ('interior_points_m', self.interior_points_m),
    ):
      if any(
        len(point) != 2 or not all(isfinite(float(value)) for value in point)
        for point in points
      ):
        raise ValueError(f'{name} must contain finite coordinate pairs')
    if any(
      not isfinite(float(value)) or value <= 0.0
      for value in self.interior_total_pressure_Pa
    ):
      raise ValueError('interior total pressures must be finite and positive')
    for name, pressures in (
      ('shock_boundary_total_pressure_Pa', self.shock_boundary_total_pressure_Pa),
      (
        'companion_boundary_total_pressure_Pa',
        self.companion_boundary_total_pressure_Pa,
      ),
    ):
      if any(not isfinite(float(value)) or value <= 0.0 for value in pressures):
        raise ValueError(f'{name} must contain finite positive values')
    for name in (
      'maximum_geometry_residual_m',
      'maximum_absolute_invariant_residual',
      'minimum_forward_margin_m',
      'maximum_companion_pressure_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or (name != 'minimum_forward_margin_m' and numeric < 0.0):
        raise ValueError(f'{name} must be finite and valid when supplied')
      object.__setattr__(self, name, numeric)
    if self.shock_boundary_orientation is not None and not isinstance(
      self.shock_boundary_orientation,
      MocEulerShockBoundaryOrientation,
    ):
      raise TypeError(
        'shock_boundary_orientation must be a MocEulerShockBoundaryOrientation'
      )
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult when supplied'
      )
    for name in (
      'shock_boundary_local_euler_verified',
      'companion_boundary_contract_verified',
      'pressure_lineage_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the bounded strip assembled numerically."""

    return self.status is MocEulerCompanionFieldStatus.CONVERGED_OPEN_COMPANION_FIELD
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether every interior node carries a bounded state and pressure."""

    return bool(
      self.converged
      and self.nodes
      and len(self.interior_states) == len(self.nodes)
      and len(self.interior_total_pressure_Pa) == len(self.nodes)
    )
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit chain boundary represented by this field.

    A companion strip has a topologically bounded patch, but its second
    characteristic boundary is an input to the strip rather than a solved
    ambient/free-boundary closure.  Consequently a converged strip must
    enter a continued-chain planner as a non-physical stop.  Keeping this
    conversion on the typed result prevents a caller from treating
    ``converged`` or ``forms_closed_zone`` as permission to relabel the strip
    as a resolved chain cell.
    """

    if self.converged:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'Euler companion characteristic strip is locally assembled but its '
        'companion/ambient downstream closure is open; no continued cell may '
        'be promoted from this field'
      )
    elif self.status is MocEulerCompanionFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
      message = 'Euler companion characteristic strip rejected its inputs'
    elif self.status is MocEulerCompanionFieldStatus.SHOCK_BOUNDARY_REQUIRED:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = (
        'Euler companion characteristic strip has no locally verified shock '
        'boundary to seed the downstream field'
      )
    elif self.status is MocEulerCompanionFieldStatus.COMPANION_BOUNDARY_REQUIRED:
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
      message = (
        'Euler companion characteristic strip is missing its second '
        'characteristic boundary; no state-carrying cell handoff exists'
      )
    elif self.status is MocEulerCompanionFieldStatus.CHARACTERISTIC_ORIENTATION_FAILURE:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      message = (
        'Euler companion characteristic strip received a boundary whose '
        'characteristic orientation is not supported by this stencil'
      )
    elif self.status is MocEulerCompanionFieldStatus.TOPOLOGY_FAILURE:
      reason = MocChainTerminationReason.TOPOLOGY_INVALID
      message = (
        'Euler companion characteristic strip did not produce a valid '
        'connected bounded mesh'
      )
    elif self.status in (
      MocEulerCompanionFieldStatus.PRESSURE_FAILURE,
      MocEulerCompanionFieldStatus.INVARIANT_FAILURE,
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
      message = (
        'Euler companion characteristic strip did not preserve a usable '
        'state/pressure handoff'
      )
    else:
      reason = MocChainTerminationReason.SOLVER_ERROR
      message = (
        'Euler companion characteristic strip failed before a continued '
        'cell handoff was available'
      )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={
        'euler_companion_field_status': self.status.value,
        'node_count': self.node_count,
        'cell_count': self.cell_count,
        'shock_boundary_orientation': (
          None
          if self.shock_boundary_orientation is None
          else self.shock_boundary_orientation.value
        ),
        'shock_boundary_local_euler_verified': (
          self.shock_boundary_local_euler_verified
        ),
        'companion_boundary_contract_verified': (
          self.companion_boundary_contract_verified
        ),
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'topology_forms_closed_zone': self.topology.forms_closed_zone,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'required_next_boundary': (
          'ambient/free-boundary plus downstream entropy-coupled closure'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'state_sampling_available': self.state_sampling_available,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'shock_boundary_status': (
        None if self.shock_boundary is None else self.shock_boundary.status.value
      ),
      'shock_boundary_sample_count': len(self.shock_boundary_points_m),
      'companion_boundary_sample_count': len(self.companion_boundary_points_m),
      'interior_sample_count': len(self.interior_points_m),
      'shock_boundary_points_m': [list(point) for point in self.shock_boundary_points_m],
      'companion_boundary_points_m': [
        list(point) for point in self.companion_boundary_points_m
      ],
      'interior_points_m': [list(point) for point in self.interior_points_m],
      'shock_boundary_orientation': (
        None
        if self.shock_boundary_orientation is None
        else self.shock_boundary_orientation.value
      ),
      'shock_boundary_local_euler_verified': self.shock_boundary_local_euler_verified,
      'shock_boundary_maximum_jump_residual': (
        None
        if self.shock_boundary is None
        else self.shock_boundary.maximum_shock_jump_residual
      ),
      'companion_boundary_contract_verified': self.companion_boundary_contract_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_companion_pressure_residual': self.maximum_companion_pressure_residual,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }
  ####


def _failure(
  status: MocEulerCompanionFieldStatus,
  message: str,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  **values: Any,
) -> MocEulerCompanionFieldResult:
  return MocEulerCompanionFieldResult(
    status=status,
    nodes=tuple(values.pop('nodes', ())),
    cells=tuple(values.pop('cells', ())),
    topology=values.pop('topology', validate_moc_mesh(())),
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    message=message,
    **values,
  )


def assemble_euler_consistent_companion_characteristic_strip(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  companion_boundary: Sequence[MocChainBoundarySample],
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
) -> MocEulerCompanionFieldResult:
  """Assemble a one-layer ``C+``/``C-`` strip from explicit boundaries.

  The locally conservative shock supplies the ``C+`` source at each sample.
  The companion boundary supplies the ``C-`` source at the matching sample.
  Matching total pressure is required so this narrow strip has one explicit
  isentropic pressure lineage; variable-entropy companion fields belong to a
  separate solver.  The returned patch remains open to physical closure and
  cannot seed a continued shock-cell chain.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'strip tolerances must be numeric',
    )
  if not isfinite(position_tolerance) or position_tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if not isfinite(invariant_tolerance_value) or invariant_tolerance_value <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  if not isfinite(pressure_tolerance_value) or pressure_tolerance_value <= 0.0:
    raise ValueError('pressure_tolerance must be finite and positive')
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return _failure(
      MocEulerCompanionFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      'companion strip requires a locally Euler-verified shock boundary',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
    )
  if shock_boundary.orientation is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY:
    return _failure(
      MocEulerCompanionFieldStatus.CHARACTERISTIC_ORIENTATION_FAILURE,
      'companion strip requires a mixed-characteristic shock boundary; the shock-only two-family stencil is not valid here',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  try:
    companion = tuple(companion_boundary)
  except TypeError:
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'companion_boundary must be an iterable of MocChainBoundarySample values',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  if len(companion) != len(shock_boundary.shock_points_m) or len(companion) < 2:
    return _failure(
      MocEulerCompanionFieldStatus.COMPANION_BOUNDARY_REQUIRED,
      'companion boundary must contain one state/pressure sample for every shock sample',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in companion):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'companion_boundary must contain MocChainBoundarySample values',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  gamma = shock_boundary.downstream_states[0].gamma
  if any(abs(sample.state.gamma - gamma) > invariant_tolerance_value for sample in companion):
    return _failure(
      MocEulerCompanionFieldStatus.INVALID_INPUT,
      'shock and companion boundaries must use the same gamma',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    )
  companion_pressure_residuals = tuple(
    sample.total_pressure_Pa - expected
    for sample, expected in zip(
      companion,
      shock_boundary.downstream_total_pressure_Pa,
      strict=True,
    )
  )
  maximum_pressure_residual = max(
    (abs(value) for value in companion_pressure_residuals),
    default=None,
  )
  if any(
    abs(residual) > pressure_tolerance_value * max(1.0, abs(expected))
    for residual, expected in zip(
      companion_pressure_residuals,
      shock_boundary.downstream_total_pressure_Pa,
      strict=True,
    )
  ):
    return _failure(
      MocEulerCompanionFieldStatus.PRESSURE_FAILURE,
      'companion boundary total pressure does not match the shock downstream pressure lineage',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      shock_boundary_points_m=shock_boundary.shock_points_m,
      companion_boundary_points_m=tuple(sample.point_m for sample in companion),
      shock_boundary_states=shock_boundary.downstream_states,
      companion_boundary_states=tuple(sample.state for sample in companion),
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
      maximum_companion_pressure_residual=maximum_pressure_residual,
    )
  ####

  nodes: list[MocCharacteristicNode] = []
  point_results: list[CharacteristicPointResult] = []
  interior_states: list[CharacteristicState] = []
  interior_points: list[tuple[float, float]] = []
  interior_pressures: list[float] = []
  forward_margins: list[float] = []
  for index, (shock_state, companion_sample) in enumerate(
    zip(shock_boundary.downstream_states, companion, strict=True)
  ):
    point_result = interior_characteristic_point(
      shock_state,
      companion_sample.state,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
    )
    point_results.append(point_result)
    if not point_result.converged or point_result.point_m is None or point_result.state is None:
      status = (
        MocEulerCompanionFieldStatus.INVARIANT_FAILURE
        if point_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
        else MocEulerCompanionFieldStatus.GEOMETRY_FAILURE
      )
      return _failure(
        status,
        f'companion characteristic intersection {index} failed: {point_result.message}',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        point_results=tuple(point_results[:-1]),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_geometry_residual_m=max(
          (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
          default=None,
        ),
        maximum_absolute_invariant_residual=max(
          (
            abs(value)
            for result in point_results
            for value in (
              result.invariant_residual_plus,
              result.invariant_residual_minus,
            )
            if value is not None
          ),
          default=None,
        ),
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
    point = (float(point_result.point_m[0]), float(point_result.point_m[1]))
    minimum_y = min(shock_state.y_m, companion_sample.state.y_m)
    maximum_y = max(shock_state.y_m, companion_sample.state.y_m)
    if point[1] < minimum_y - position_tolerance or point[1] > maximum_y + position_tolerance:
      return _failure(
        MocEulerCompanionFieldStatus.GEOMETRY_FAILURE,
        f'companion characteristic intersection {index} lies outside its two boundary samples',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        point_results=tuple(point_results[:-1]),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
    forward_margin = point[0] - max(shock_state.x_m, companion_sample.state.x_m)
    if forward_margin <= position_tolerance:
      return _failure(
        MocEulerCompanionFieldStatus.GEOMETRY_FAILURE,
        f'companion characteristic intersection {index} has no forward margin from its boundaries',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        point_results=tuple(point_results[:-1]),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
    forward_margins.append(forward_margin)
    interior_states.append(point_result.state)
    interior_points.append(point)
    pressure = shock_boundary.downstream_total_pressure_Pa[index]
    interior_pressures.append(pressure)
    nodes.append(
      MocCharacteristicNode(
        centerline_index=1,
        boundary_index=index,
        point_m=point,
        state=point_result.state,
        point_result=point_result,
        total_pressure_Pa=pressure,
      )
    )
  ####

  cells: list[MocCharacteristicCell] = []
  for index in range(len(nodes) - 1):
    try:
      cells.append(
        MocCharacteristicCell(
          cell_index=index,
          cell_kind='euler-shock-companion-characteristic-strip',
          vertices_xr_m=(
            shock_boundary.shock_points_m[index],
            shock_boundary.shock_points_m[index + 1],
            nodes[index + 1].point_m,
            nodes[index].point_m,
          ),
          centerline_indices=(1,),
          boundary_indices=(index, index + 1),
        )
      )
    except ValueError as error:
      return _failure(
        MocEulerCompanionFieldStatus.GEOMETRY_FAILURE,
        f'companion characteristic cell {index} geometry failed: {error}',
        position_tolerance_m=position_tolerance,
        invariant_tolerance=invariant_tolerance_value,
        pressure_tolerance=pressure_tolerance_value,
        nodes=tuple(nodes),
        cells=tuple(cells),
        point_results=tuple(point_results),
        interior_states=tuple(interior_states),
        interior_points_m=tuple(interior_points),
        interior_total_pressure_Pa=tuple(interior_pressures),
        shock_boundary_points_m=shock_boundary.shock_points_m,
        companion_boundary_points_m=tuple(sample.point_m for sample in companion),
        shock_boundary_states=shock_boundary.downstream_states,
        companion_boundary_states=tuple(sample.state for sample in companion),
        shock_boundary_orientation=shock_boundary.orientation,
        shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
        companion_boundary_contract_verified=True,
        pressure_lineage_verified=True,
        maximum_geometry_residual_m=max(
          (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
          default=None,
        ),
        maximum_absolute_invariant_residual=max(
          (
            abs(value)
            for result in point_results
            for value in (
              result.invariant_residual_plus,
              result.invariant_residual_minus,
            )
            if value is not None
          ),
          default=None,
        ),
        minimum_forward_margin_m=min(forward_margins, default=None),
        maximum_companion_pressure_residual=maximum_pressure_residual,
      )
  cell_tuple = tuple(cells)
  topology = validate_moc_mesh(cell_tuple)
  if not topology.connected or topology.nonmanifold_edge_count or not topology.forms_closed_zone:
    return _failure(
      MocEulerCompanionFieldStatus.TOPOLOGY_FAILURE,
      f'companion characteristic strip topology failed: {topology.message}',
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      nodes=tuple(nodes),
      cells=cell_tuple,
      topology=topology,
      point_results=tuple(point_results),
      interior_states=tuple(interior_states),
      interior_points_m=tuple(interior_points),
      interior_total_pressure_Pa=tuple(interior_pressures),
      shock_boundary_points_m=shock_boundary.shock_points_m,
      companion_boundary_points_m=tuple(sample.point_m for sample in companion),
      shock_boundary_states=shock_boundary.downstream_states,
      companion_boundary_states=tuple(sample.state for sample in companion),
      shock_boundary_orientation=shock_boundary.orientation,
      shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
      companion_boundary_contract_verified=True,
      pressure_lineage_verified=True,
      maximum_geometry_residual_m=max(
        (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
        default=None,
      ),
      maximum_absolute_invariant_residual=max(
        (
          abs(value)
          for result in point_results
          for value in (
            result.invariant_residual_plus,
            result.invariant_residual_minus,
          )
          if value is not None
        ),
        default=None,
      ),
      minimum_forward_margin_m=min(forward_margins, default=None),
      maximum_companion_pressure_residual=maximum_pressure_residual,
    )
  return MocEulerCompanionFieldResult(
    status=MocEulerCompanionFieldStatus.CONVERGED_OPEN_COMPANION_FIELD,
    nodes=tuple(nodes),
    cells=cell_tuple,
    topology=topology,
    shock_boundary=shock_boundary,
    shock_boundary_points_m=shock_boundary.shock_points_m,
    companion_boundary_points_m=tuple(sample.point_m for sample in companion),
    interior_points_m=tuple(interior_points),
    shock_boundary_states=shock_boundary.downstream_states,
    shock_boundary_total_pressure_Pa=shock_boundary.downstream_total_pressure_Pa,
    companion_boundary_states=tuple(sample.state for sample in companion),
    companion_boundary_total_pressure_Pa=tuple(
      sample.total_pressure_Pa for sample in companion
    ),
    interior_states=tuple(interior_states),
    interior_total_pressure_Pa=tuple(interior_pressures),
    point_results=tuple(point_results),
    shock_boundary_orientation=shock_boundary.orientation,
    shock_boundary_local_euler_verified=shock_boundary.local_euler_verified,
    companion_boundary_contract_verified=True,
    pressure_lineage_verified=True,
    maximum_geometry_residual_m=max(
      (abs(result.geometry_residual) for result in point_results if result.geometry_residual is not None),
      default=None,
    ),
    maximum_absolute_invariant_residual=max(
      (
        abs(value)
        for result in point_results
        for value in (
          result.invariant_residual_plus,
          result.invariant_residual_minus,
        )
        if value is not None
      ),
      default=None,
    ),
    minimum_forward_margin_m=min(forward_margins, default=None),
    maximum_companion_pressure_residual=maximum_pressure_residual,
    position_tolerance_m=position_tolerance,
    invariant_tolerance=invariant_tolerance_value,
    pressure_tolerance=pressure_tolerance_value,
    message=(
      'Euler-consistent shock and explicit companion boundary formed an open '
      'one-layer characteristic strip; ambient/free-boundary closure and '
      'continued-cell promotion remain blocked'
    ),
  )
