"""Independent audit for the solver-owned entropy characteristic field.

The model-side solver constructs a four-triangle internal characteristic field
from the entropy-carrying first-wedge trial.  This operator recomputes its
source pressure gradient, pressure lineages, family geometry, generalized
compatibility residuals, topology, and cell Euler residuals from raw nodes and
cell samples.  Passing this audit is local characteristic evidence only: the
reflected free boundary, downstream shock coupling, external observations,
and continued-chain promotion remain closed gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus,
)
from exhaust_plume.models.moc.chain import MocChainBoundaryKind
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.topology import validate_moc_mesh
from exhaust_plume.validation.moc_euler import _cell_flux_residual
from exhaust_plume.validation.moc_euler_entropy import (
  measure_moc_euler_ambient_first_wedge_entropy_carry,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_field',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-field-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus(str, Enum):
  """Outcome of the independent internal-field audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_field_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_source_failure'
  )
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_topology_failure'
  )
  STATE_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_state_failure'
  )
  PRESSURE_LINEAGE_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_pressure_lineage_failure'
  )
  GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_geometry_failure'
  )
  ENTROPY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_compatibility_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_euler_residual_failure'
  )
  CONTINUATION_BOUNDARY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_continuation_boundary_failure'
  )
  FLAG_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_flag_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit:
  """Raw family-compatibility evidence for one internal-field edge."""

  edge_index: int
  start_node: int
  end_node: int
  family: CharacteristicFamily
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
    for name in ('start_node', 'end_node'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
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
      object.__setattr__(self, name, value)

  def as_report(self) -> dict[str, Any]:
    return {
      'edge_index': self.edge_index,
      'start_node': self.start_node,
      'end_node': self.end_node,
      'family': self.family.value,
      'edge_length_m': self.edge_length_m,
      'forward_margin_m': self.forward_margin_m,
      'alignment_residual': self.alignment_residual,
      'k_residual': self.k_residual,
      'entropy_source_prediction': self.entropy_source_prediction,
      'compatibility_residual': self.compatibility_residual,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit:
  """Independent gates for the four-triangle internal field."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus
  operator_id: str
  solver_status: str | None
  source_trial_status: str | None
  node_count: int
  cell_count: int
  sampled_cell_count: int
  characteristic_edges: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit, ...
  ]
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  maximum_edge_alignment_residual: float | None
  minimum_forward_margin_m: float | None
  maximum_k_residual: float | None
  maximum_entropy_compatibility_residual: float | None
  source_trial_gates_verified: bool
  topology_verified: bool
  state_samples_finite: bool
  continuation_boundary_verified: bool
  pressure_lineage_verified: bool
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  internal_characteristic_closure_verified: bool
  solver_status_consistent: bool
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
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus'
      )
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    for name in ('solver_status', 'source_trial_status'):
      value = getattr(self, name)
      if value is not None:
        object.__setattr__(self, name, str(value))
    for name in ('node_count', 'cell_count', 'sampled_cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(
        edge,
        MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit,
      )
      for edge in edges
    ):
      raise TypeError(
        'characteristic_edges must contain typed internal-field edge audits'
      )
    object.__setattr__(self, 'characteristic_edges', edges)
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'cell_euler_residuals must contain finite nonnegative values'
      )
    if len(residuals) != self.cell_count:
      raise ValueError('cell_euler_residuals must match cell_count')
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    for name in (
      'maximum_cell_euler_residual',
      'maximum_edge_alignment_residual',
      'minimum_forward_margin_m',
      'maximum_k_residual',
      'maximum_entropy_compatibility_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or (
        numeric < 0.0 and name != 'minimum_forward_margin_m'
      ):
        raise ValueError(f'{name} must be finite and valid when supplied')
      object.__setattr__(self, name, numeric)
    for name in (
      'source_trial_gates_verified',
      'topology_verified',
      'state_samples_finite',
      'continuation_boundary_verified',
      'pressure_lineage_verified',
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'internal_characteristic_closure_verified',
      'solver_status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_closure_verified:
      raise ValueError('an internal field audit cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError(
        'an internal field audit must retain the chain-promotion block'
      )
    if self.production_claim_allowed:
      raise ValueError(
        'an internal field audit cannot claim production validity'
      )
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
      object.__setattr__(self, name, value)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.source_trial_gates_verified
      and self.topology_verified
      and self.state_samples_finite
      and self.continuation_boundary_verified
      and self.pressure_lineage_verified
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and self.internal_characteristic_closure_verified
      and self.solver_status_consistent
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'source_trial_status': self.source_trial_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'sampled_cell_count': self.sampled_cell_count,
      'characteristic_edges': [
        edge.as_report() for edge in self.characteristic_edges
      ],
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'maximum_edge_alignment_residual': self.maximum_edge_alignment_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_k_residual': self.maximum_k_residual,
      'maximum_entropy_compatibility_residual': (
        self.maximum_entropy_compatibility_residual
      ),
      'checks': {
        'source_trial_gates_verified': self.source_trial_gates_verified,
        'topology_verified': self.topology_verified,
        'state_samples_finite': self.state_samples_finite,
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'characteristic_geometry_verified': (
          self.characteristic_geometry_verified
        ),
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': (
          self.internal_characteristic_closure_verified
        ),
        'solver_status_consistent': self.solver_status_consistent,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-solver-owned-internal-characteristic-field-audit; '
        'reflected free-boundary coupling, external validation, and continued '
        'chain promotion remain pending'
      ),
      'message': self.message,
    }


_EXPECTED_EDGE_DEFINITIONS: tuple[
  tuple[int, int, CharacteristicFamily], ...
] = (
  (0, 3, CharacteristicFamily.PLUS),
  (3, 1, CharacteristicFamily.PLUS),
  (1, 4, CharacteristicFamily.MINUS),
  (4, 2, CharacteristicFamily.MINUS),
  (3, 5, CharacteristicFamily.MINUS),
  (5, 4, CharacteristicFamily.PLUS),
)
_EXPECTED_CELL_NODE_INDICES: tuple[tuple[int, int, int], ...] = (
  (0, 3, 5),
  (3, 1, 4),
  (3, 4, 5),
  (5, 4, 2),
)
_EXPECTED_CELL_KIND = 'post-shock-ambient-entropy-characteristic-subcell'
_EXPECTED_NODE_KINDS = (
  'shock-endpoint',
  'ambient-edge-endpoint',
  'centerline-reflection-endpoint',
  'shock-edge-interior',
  'ambient-edge-interior',
  'internal-centerline',
)
_EXPECTED_PRESSURE_LINEAGES = (
  'shock-endpoint',
  'ambient-source',
  'shock-centerline',
  'shock-to-ambient-edge',
  'ambient-to-shock-edge',
  'shock-centerline',
)


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus,
  message: str,
  *,
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None = None,
  source_trial_gates_verified: bool = False,
  topology_verified: bool = False,
  state_samples_finite: bool = False,
  continuation_boundary_verified: bool = False,
  pressure_lineage_verified: bool = False,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  internal_characteristic_closure_verified: bool = False,
  solver_status_consistent: bool = False,
  characteristic_edges: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit
  ] = (),
  cell_euler_residuals: Sequence[float] = (),
  maximum_cell_euler_residual: float | None = None,
  maximum_edge_alignment_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  maximum_k_residual: float | None = None,
  maximum_entropy_compatibility_residual: float | None = None,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit:
  solver_status = None if result is None else result.status.value
  source_status = (
    None
    if result is None or result.source_trial is None
    else result.source_trial.status.value
  )
  cell_count = 0 if result is None else len(result.cells)
  residuals = tuple(float(value) for value in cell_euler_residuals)
  if len(residuals) < cell_count:
    residuals += (0.0,) * (cell_count - len(residuals))
  elif len(residuals) > cell_count:
    residuals = residuals[:cell_count]
  if maximum_cell_euler_residual is None and cell_euler_residuals:
    maximum_cell_euler_residual = max(float(value) for value in cell_euler_residuals)
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID
    ),
    solver_status=solver_status,
    source_trial_status=source_status,
    node_count=0 if result is None else len(result.nodes),
    cell_count=cell_count,
    sampled_cell_count=0 if result is None else len(result.cell_samples),
    characteristic_edges=tuple(characteristic_edges),
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    maximum_edge_alignment_residual=maximum_edge_alignment_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    maximum_k_residual=maximum_k_residual,
    maximum_entropy_compatibility_residual=(
      maximum_entropy_compatibility_residual
    ),
    source_trial_gates_verified=source_trial_gates_verified,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    continuation_boundary_verified=continuation_boundary_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_compatibility_verified,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    internal_characteristic_closure_verified=internal_characteristic_closure_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=(
      False if result is None else result.physical_closure_verified
    ),
    chain_promotion_blocked=(
      True if result is None else result.chain_promotion_blocked
    ),
    production_claim_allowed=(
      False if result is None else result.production_claim_allowed
    ),
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    message=message,
  )


def _log_pressure_gradient(
  vertices: tuple[tuple[float, float], ...],
  pressures: tuple[float, ...],
) -> tuple[float, float] | None:
  if len(vertices) != 3 or len(pressures) != 3:
    return None
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return None
  (x1, y1), (x2, y2), (x3, y3) = vertices
  denominator = (
    x1 * (y2 - y3)
    + x2 * (y3 - y1)
    + x3 * (y1 - y2)
  )
  if not isfinite(denominator) or abs(denominator) <= 1.0e-24:
    return None
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


@dataclass(frozen=True, slots=True)
class _RawEdgeMetric:
  alignment: float
  forward_margin: float
  edge_length: float
  actual: float
  source: float

  @property
  def compatibility(self) -> float:
    return abs(self.actual - self.source)


def _edge_metric(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  start_index: int,
  end_index: int,
  family: CharacteristicFamily,
  gradient: tuple[float, float],
) -> _RawEdgeMetric | None:
  start_state = states[start_index]
  end_state = states[end_index]
  first_direction = start_state.direction(family)
  second_direction = end_state.direction(family)
  averaged = (
    0.5 * (first_direction[0] + second_direction[0]),
    0.5 * (first_direction[1] + second_direction[1]),
  )
  direction_length = hypot(*averaged)
  displacement = (
    vertices[end_index][0] - vertices[start_index][0],
    vertices[end_index][1] - vertices[start_index][1],
  )
  edge_length = hypot(*displacement)
  if (
    not isfinite(direction_length)
    or direction_length <= 0.0
    or not isfinite(edge_length)
    or edge_length <= 0.0
  ):
    return None
  direction = (
    averaged[0] / direction_length,
    averaged[1] / direction_length,
  )
  forward_margin = displacement[0] * direction[0] + displacement[1] * direction[1]
  alignment = abs(
    displacement[0] * direction[1]
    - displacement[1] * direction[0]
  ) / edge_length
  average_theta = 0.5 * (start_state.theta_rad + end_state.theta_rad)
  normal = (-sin(average_theta), cos(average_theta))
  normal_gradient = gradient[0] * normal[0] + gradient[1] * normal[1]
  average_mach = 0.5 * (start_state.mach + end_state.mach)
  average_gamma = 0.5 * (start_state.gamma + end_state.gamma)
  source = (
    -sqrt(max(average_mach * average_mach - 1.0, 0.0))
    / (average_gamma * average_mach**3)
    * normal_gradient
    * edge_length
  )
  actual = (
    end_state.k_plus - start_state.k_plus
    if family is CharacteristicFamily.PLUS
    else end_state.k_minus - start_state.k_minus
  )
  values = (alignment, forward_margin, edge_length, actual, source)
  if not all(isfinite(value) for value in values):
    return None
  return _RawEdgeMetric(*values)


def _segment_fraction(
  point: tuple[float, float],
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> float | None:
  dx = second[0] - first[0]
  dy = second[1] - first[1]
  length = hypot(dx, dy)
  if not isfinite(length) or length <= 0.0:
    return None
  fraction = ((point[0] - first[0]) * dx + (point[1] - first[1]) * dy) / (length * length)
  distance = abs(
    (point[0] - first[0]) * dy - (point[1] - first[1]) * dx
  ) / length
  if (
    not isfinite(fraction)
    or not isfinite(distance)
    or fraction < -tolerance_m
    or fraction > 1.0 + tolerance_m
    or distance > tolerance_m
  ):
    return None
  return min(1.0, max(0.0, fraction))


def _close(first: float, second: float, tolerance: float) -> bool:
  return abs(float(first) - float(second)) <= tolerance * max(
    1.0,
    abs(float(first)),
    abs(float(second)),
  )


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit:
  """Recompute the internal-field gates from raw result evidence."""

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.INVALID_INPUT,
      'result must be a '
      'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    lineage_tolerance = float(pressure_lineage_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.INVALID_INPUT,
      'internal characteristic field audit tolerances must be numeric',
      result=result,
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
    ('pressure_lineage_tolerance', lineage_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  common = {
    'result': result,
    'position_tolerance_m': position_tolerance,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'pressure_lineage_tolerance': lineage_tolerance,
  }
  source_trial = result.source_trial
  if not isinstance(
    source_trial,
    MocEulerAmbientFirstWedgeEntropyCarryResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.SOURCE_FAILURE,
      'internal field does not retain its entropy-carrying source trial',
      **common,
    )
  source_audit = measure_moc_euler_ambient_first_wedge_entropy_carry(
    source_trial,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=source_trial.characteristic_residual_tolerance,
    edge_alignment_tolerance=source_trial.edge_alignment_tolerance,
    cell_residual_tolerance=source_trial.cell_residual_tolerance,
    pressure_lineage_tolerance=lineage_tolerance,
  )
  source_trial_gates_verified = bool(
    source_audit.topology_verified
    and source_audit.state_samples_finite
    and source_audit.pressure_lineage_verified
    and source_audit.incoming_characteristic_geometry_verified
    and source_audit.characteristic_geometry_verified
    and source_audit.variable_entropy_compatibility_verified
    and source_audit.axis_streamline_entropy_verified
  )
  if not source_trial_gates_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.SOURCE_FAILURE,
      'independent entropy source-trial gates did not pass',
      source_trial_gates_verified=False,
      **common,
    )
  source_vertices = tuple(source_trial.vertices_xr_m)
  source_pressures = tuple(source_trial.total_pressure_Pa)
  gradient = _log_pressure_gradient(source_vertices, source_pressures)
  if gradient is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.SOURCE_FAILURE,
      'source-trial pressure gradient could not be reconstructed',
      source_trial_gates_verified=True,
      **common,
    )
  nodes = tuple(result.nodes)
  topology = validate_moc_mesh(result.cells)
  topology_verified = bool(
    len(result.cells) == len(_EXPECTED_CELL_NODE_INDICES)
    and topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
    and result.topology == topology
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.TOPOLOGY_FAILURE,
      f'independent internal-field topology audit failed: {topology.message}',
      source_trial_gates_verified=True,
      topology_verified=False,
      **common,
    )
  state_samples_finite = bool(
    len(nodes) == 6
    and tuple(node.node_index for node in nodes) == tuple(range(6))
    and all(
      node.node_kind == _EXPECTED_NODE_KINDS[index]
      and node.pressure_lineage == _EXPECTED_PRESSURE_LINEAGES[index]
      and isinstance(node.state, CharacteristicState)
      and all(
        isfinite(value)
        for value in (
          node.point_m[0],
          node.point_m[1],
          node.state.x_m,
          node.state.y_m,
          node.state.theta_rad,
          node.state.mach,
          node.state.gamma,
          node.total_pressure_Pa,
        )
      )
      and node.state.mach > 1.0
      and node.state.gamma > 1.0
      and hypot(
        node.state.x_m - node.point_m[0],
        node.state.y_m - node.point_m[1],
      ) <= position_tolerance
      for index, node in enumerate(nodes)
    )
  )
  state_samples_finite = state_samples_finite and bool(
    len(result.cell_samples) == len(result.cells)
  )
  sample_state_consistent = True
  for cell_index, (cell, sample, expected_indices) in enumerate(
    zip(result.cells, result.cell_samples, _EXPECTED_CELL_NODE_INDICES, strict=False)
  ):
    expected_vertices = tuple(nodes[index].point_m for index in expected_indices) if len(nodes) == 6 else ()
    sample_state_consistent = sample_state_consistent and bool(
      cell.cell_kind == _EXPECTED_CELL_KIND
      and len(cell.vertices_xr_m) == 3
      and len(sample.vertices_xr_m) == 3
      and all(
        hypot(
          cell_point[0] - expected_point[0],
          cell_point[1] - expected_point[1],
        ) <= position_tolerance
        for cell_point, expected_point in zip(cell.vertices_xr_m, expected_vertices, strict=True)
      )
      and all(
        hypot(
          sample_point[0] - expected_point[0],
          sample_point[1] - expected_point[1],
        ) <= position_tolerance
        for sample_point, expected_point in zip(sample.vertices_xr_m, expected_vertices, strict=True)
      )
      and all(
        hypot(
          sample_state.x_m - nodes[node_index].state.x_m,
          sample_state.y_m - nodes[node_index].state.y_m,
        ) <= position_tolerance
        and abs(sample_state.theta_rad - nodes[node_index].state.theta_rad)
        <= residual_tolerance
        and abs(sample_state.mach - nodes[node_index].state.mach)
        <= residual_tolerance
        and abs(sample_pressure - nodes[node_index].total_pressure_Pa)
        <= lineage_tolerance * max(
          1.0,
          abs(sample_pressure),
          abs(nodes[node_index].total_pressure_Pa),
        )
        for node_index, sample_state, sample_pressure in zip(
          expected_indices,
          sample.states,
          sample.total_pressure_Pa,
          strict=True,
        )
      )
    )
  state_samples_finite = state_samples_finite and sample_state_consistent
  if not state_samples_finite:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.STATE_FAILURE,
      'independent internal-field node and cell-sample audit failed',
      source_trial_gates_verified=True,
      topology_verified=True,
      state_samples_finite=False,
      **common,
    )
  points = tuple(node.point_m for node in nodes)
  states = tuple(node.state for node in nodes)
  pressures = tuple(node.total_pressure_Pa for node in nodes)
  continuation_boundary_verified = False
  try:
    frontier = tuple(result.continuation_boundary)
    expected_frontier_indices = (1, 4, 2)
    expected_frontier_nodes = tuple(
      nodes[index] for index in expected_frontier_indices
    )
    continuation_boundary_verified = bool(
      result.continuation_boundary_kind
      is MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
      and result.continuation_boundary_node_indices == expected_frontier_indices
      and len(frontier) == len(expected_frontier_nodes)
      and all(
        sample.state.x_m == node.state.x_m
        and sample.state.y_m == node.state.y_m
        and sample.state.theta_rad == node.state.theta_rad
        and sample.state.mach == node.state.mach
        and sample.state.gamma == node.state.gamma
        and _close(
          sample.total_pressure_Pa,
          node.total_pressure_Pa,
          lineage_tolerance,
        )
        for sample, node in zip(frontier, expected_frontier_nodes, strict=True)
      )
      and all(
        current.state.x_m > previous.state.x_m + position_tolerance
        and current.state.y_m >= -position_tolerance
        for previous, current in zip(frontier, frontier[1:])
      )
    )
  except (TypeError, ValueError):
    continuation_boundary_verified = False
  if not continuation_boundary_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.CONTINUATION_BOUNDARY_FAILURE,
      'independent internal-field continuation frontier audit failed',
      source_trial_gates_verified=True,
      topology_verified=True,
      state_samples_finite=True,
      continuation_boundary_verified=False,
      **common,
    )
  pressure_lineage_verified = bool(
    len(nodes) == 6
    and all(
      hypot(points[index][0] - source_vertices[index][0], points[index][1] - source_vertices[index][1])
      <= position_tolerance
      for index in (0, 1, 2)
    )
    and _close(pressures[0], source_pressures[0], lineage_tolerance)
    and _close(pressures[1], source_pressures[1], lineage_tolerance)
    and _close(pressures[2], source_pressures[2], lineage_tolerance)
    and _close(pressures[5], source_pressures[0], lineage_tolerance)
  )
  fraction_p = _segment_fraction(
    points[3],
    source_vertices[0],
    source_vertices[1],
    position_tolerance,
  )
  fraction_q = _segment_fraction(
    points[4],
    source_vertices[1],
    source_vertices[2],
    position_tolerance,
  )
  if fraction_p is None or fraction_q is None:
    pressure_lineage_verified = False
  else:
    pressure_lineage_verified = pressure_lineage_verified and bool(
      _close(
        log(pressures[3]),
        (1.0 - fraction_p) * log(source_pressures[0])
        + fraction_p * log(source_pressures[1]),
        lineage_tolerance,
      )
      and _close(
        log(pressures[4]),
        (1.0 - fraction_q) * log(source_pressures[1])
        + fraction_q * log(source_pressures[2]),
        lineage_tolerance,
      )
    )
  if not pressure_lineage_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.PRESSURE_LINEAGE_FAILURE,
      'independent internal-field pressure-lineage audit failed',
      source_trial_gates_verified=True,
      topology_verified=True,
      state_samples_finite=True,
      continuation_boundary_verified=True,
      pressure_lineage_verified=False,
      **common,
    )
  edge_definition_verified = result.edge_vertex_indices == _EXPECTED_EDGE_DEFINITIONS
  raw_metrics = tuple(
    _edge_metric(points, states, start, end, family, gradient)
    for start, end, family in _EXPECTED_EDGE_DEFINITIONS
  )
  characteristic_edges: list[MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit] = []
  characteristic_geometry_verified = edge_definition_verified
  variable_entropy_verified = edge_definition_verified
  edge_cache_consistent = len(result.characteristic_edges) == len(_EXPECTED_EDGE_DEFINITIONS)
  for edge_index, ((start, end, family), metric) in enumerate(
    zip(_EXPECTED_EDGE_DEFINITIONS, raw_metrics, strict=True)
  ):
    if metric is None:
      characteristic_geometry_verified = False
      variable_entropy_verified = False
      edge_cache_consistent = False
      continue
    characteristic_geometry_verified = characteristic_geometry_verified and bool(
      metric.forward_margin > position_tolerance
      and metric.alignment <= alignment_tolerance
    )
    variable_entropy_verified = variable_entropy_verified and bool(
      metric.compatibility <= residual_tolerance
    )
    characteristic_edges.append(
      MocEulerAmbientFirstWedgeEntropyCharacteristicEdgeAudit(
        edge_index=edge_index,
        start_node=start,
        end_node=end,
        family=family,
        edge_length_m=metric.edge_length,
        forward_margin_m=max(0.0, metric.forward_margin),
        alignment_residual=metric.alignment,
        k_residual=abs(metric.actual),
        entropy_source_prediction=abs(metric.source),
        compatibility_residual=metric.compatibility,
      )
    )
    if edge_index < len(result.characteristic_edges):
      cached = result.characteristic_edges[edge_index]
      edge_cache_consistent = edge_cache_consistent and bool(
        cached.edge_index == edge_index
        and cached.family is family
        and cached.start_vertex == points[start]
        and cached.end_vertex == points[end]
        and _close(cached.edge_length_m, metric.edge_length, 1.0e-10)
        and _close(cached.forward_margin_m, metric.forward_margin, 1.0e-10)
        and _close(cached.alignment_residual, metric.alignment, 1.0e-10)
        and _close(cached.k_residual, abs(metric.actual), 1.0e-10)
        and _close(cached.entropy_source_prediction, abs(metric.source), 1.0e-10)
        and _close(cached.compatibility_residual, metric.compatibility, 1.0e-10)
      )
  edge_count_verified = len(characteristic_edges) == len(_EXPECTED_EDGE_DEFINITIONS)
  characteristic_geometry_verified = characteristic_geometry_verified and bool(
    edge_count_verified
    and abs(points[2][1]) <= position_tolerance
    and abs(points[5][1]) <= position_tolerance
    and abs(states[2].theta_rad) <= residual_tolerance
    and abs(states[5].theta_rad) <= residual_tolerance
  )
  variable_entropy_verified = variable_entropy_verified and edge_count_verified
  if not characteristic_geometry_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.GEOMETRY_FAILURE,
      'independent internal-field characteristic geometry audit failed',
      source_trial_gates_verified=True,
      topology_verified=True,
      state_samples_finite=True,
      continuation_boundary_verified=True,
      pressure_lineage_verified=True,
      characteristic_geometry_verified=False,
      characteristic_edges=characteristic_edges,
      **common,
    )
  if not variable_entropy_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.ENTROPY_FAILURE,
      'independent internal-field compatibility audit failed',
      source_trial_gates_verified=True,
      topology_verified=True,
      state_samples_finite=True,
      continuation_boundary_verified=True,
      pressure_lineage_verified=True,
      characteristic_geometry_verified=True,
      variable_entropy_compatibility_verified=False,
      characteristic_edges=characteristic_edges,
      **common,
    )
  residuals: list[float] = []
  residuals_finite = True
  for sample in result.cell_samples:
    try:
      residuals.append(
        _cell_flux_residual(
          tuple(sample.vertices_xr_m),
          tuple(sample.states),
          tuple(sample.total_pressure_Pa),
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      residuals_finite = False
      residuals.append(0.0)
  residuals_finite = bool(
    residuals_finite
    and len(residuals) == len(result.cells)
    and bool(residuals)
    and all(isfinite(value) for value in residuals)
  )
  maximum_residual = max(residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= cell_tolerance
  )
  cached_residuals_consistent = bool(
    len(result.cell_euler_residuals) == len(residuals)
    and all(
      _close(cached, raw, 1.0e-10)
      for cached, raw in zip(result.cell_euler_residuals, residuals, strict=True)
    )
    and (
      result.maximum_cell_euler_residual is None
      if maximum_residual is None
      else result.maximum_cell_euler_residual is not None
      and _close(result.maximum_cell_euler_residual, maximum_residual, 1.0e-10)
    )
  )
  internal_closure_verified = bool(
    source_trial_gates_verified
    and topology_verified
    and state_samples_finite
    and continuation_boundary_verified
    and pressure_lineage_verified
    and characteristic_geometry_verified
    and variable_entropy_verified
  )
  flags_consistent = bool(
    result.pressure_lineage_verified == pressure_lineage_verified
    and result.characteristic_geometry_verified == characteristic_geometry_verified
    and result.continuation_boundary_verified == continuation_boundary_verified
    and result.variable_entropy_compatibility_verified == variable_entropy_verified
    and result.cell_euler_residuals_finite == residuals_finite
    and result.cell_euler_residuals_verified == residuals_verified
    and result.internal_characteristic_closure_verified == internal_closure_verified
    and result.physical_closure_verified is False
    and result.chain_promotion_blocked is True
    and result.production_claim_allowed is False
    and edge_cache_consistent
    and cached_residuals_consistent
    and result.source_pressure_gradient is not None
    and all(
      _close(cached, raw, 1.0e-10)
      for cached, raw in zip(result.source_pressure_gradient, gradient, strict=True)
    )
  )
  if not residuals_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.EULER_RESIDUAL_FAILURE
    )
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.EULER_RESIDUAL_FAILURE
    message = 'independent internal-field Euler cell residual audit failed'
  else:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus
      .CONVERGED_INTERNAL_CHARACTERISTIC_FIELD
    )
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.CONVERGED_LOCAL_AUDIT
    message = 'independent internal characteristic field audit passed; physical closure remains blocked'
  solver_status_consistent = bool(
    flags_consistent and result.status is expected_status
  )
  if not solver_status_consistent:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAuditStatus.FLAG_FAILURE
    message += '; solver flags or status do not match the independently recomputed gates'
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID
    ),
    solver_status=result.status.value,
    source_trial_status=source_trial.status.value,
    node_count=len(nodes),
    cell_count=len(result.cells),
    sampled_cell_count=len(result.cell_samples),
    characteristic_edges=tuple(characteristic_edges),
    cell_euler_residuals=tuple(residuals),
    maximum_cell_euler_residual=maximum_residual,
    maximum_edge_alignment_residual=max(
      edge.alignment_residual for edge in characteristic_edges
    ),
    minimum_forward_margin_m=min(
      edge.forward_margin_m for edge in characteristic_edges
    ),
    maximum_k_residual=max(edge.k_residual for edge in characteristic_edges),
    maximum_entropy_compatibility_residual=max(
      edge.compatibility_residual for edge in characteristic_edges
    ),
    source_trial_gates_verified=True,
    topology_verified=True,
    state_samples_finite=True,
    continuation_boundary_verified=True,
    pressure_lineage_verified=True,
    characteristic_geometry_verified=True,
    variable_entropy_compatibility_verified=True,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    internal_characteristic_closure_verified=internal_closure_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    cell_residual_tolerance=cell_tolerance,
    pressure_lineage_tolerance=lineage_tolerance,
    message=message,
  )
