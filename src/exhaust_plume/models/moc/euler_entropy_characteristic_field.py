"""Solver-owned internal characteristic closure for the Euler first wedge.

The entropy-carrying terminal trial provides three trusted corner states but
its single polygon is still too coarse to support a continued characteristic
field.  This module solves a deliberately small four-triangle subcell field:
the two incoming edges are split at ``P`` and ``Q`` and a centerline point
``C`` is solved from the cross-family characteristics.

The construction is a higher-fidelity research lane, not a replacement for
the fast visual provider or the accepted ambient field.  Total pressure is
carried by a declared log-linear source-gradient model inherited from the
entropy trial.  That makes the internal family compatibility measurable while
leaving global reflected free-boundary closure, downstream shock coupling,
and external validation as explicit gates.  No physical chain cell is
created here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

import numpy as np
from scipy.optimize import least_squares

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
  _cell_euler_residual,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.euler_terminal_wedge import (
  MocEulerAmbientFirstWedgeCharacteristicEdge,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicNode',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult',
  'solve_euler_ambient_first_wedge_entropy_characteristic_field',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus(str, Enum):
  """Outcome of the solver-owned internal characteristic subcell field."""

  CONVERGED_INTERNAL_CHARACTERISTIC_FIELD = (
    'converged_euler_ambient_first_wedge_internal_characteristic_field'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_REQUIRED = (
    'euler_ambient_first_wedge_entropy_characteristic_source_required'
  )
  SOURCE_GATE_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_source_gate_failure'
  )
  SOLVER_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_solver_failure'
  )
  PRESSURE_LINEAGE_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_pressure_lineage_failure'
  )
  CHARACTERISTIC_GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_geometry_failure'
  )
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_topology_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_euler_residual_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicNode:
  """One node in the four-triangle solver-owned subcell field."""

  node_index: int
  node_kind: str
  pressure_lineage: str
  point_m: tuple[float, float]
  state: CharacteristicState
  total_pressure_Pa: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.node_index, bool)
      or not isinstance(self.node_index, int)
      or self.node_index < 0
    ):
      raise ValueError('node_index must be a nonnegative integer')
    for name in ('node_kind', 'pressure_lineage'):
      value = str(getattr(self, name))
      if not value:
        raise ValueError(f'{name} must be a non-empty string')
      object.__setattr__(self, name, value)
    try:
      point = (float(self.point_m[0]), float(self.point_m[1]))
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError('point_m must contain two numeric coordinates') from error
    if not all(isfinite(value) for value in point):
      raise ValueError('point_m must contain finite coordinates')
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('state must be a CharacteristicState')
    if hypot(self.state.x_m - point[0], self.state.y_m - point[1]) > 1.0e-10:
      raise ValueError('state must lie on point_m')
    pressure = float(self.total_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('total_pressure_Pa must be finite and positive')
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'total_pressure_Pa', pressure)

  def as_report(self) -> dict[str, Any]:
    return {
      'node_index': self.node_index,
      'node_kind': self.node_kind,
      'pressure_lineage': self.pressure_lineage,
      'point_m': list(self.point_m),
      'mach': self.state.mach,
      'flow_angle_rad': self.state.theta_rad,
      'nu_rad': self.state.nu_rad,
      'k_plus': self.state.k_plus,
      'k_minus': self.state.k_minus,
      'total_pressure_Pa': self.total_pressure_Pa,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult:
  """Auditable internal characteristic field below physical promotion."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus
  source_trial: MocEulerAmbientFirstWedgeEntropyCarryResult | None
  nodes: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...]
  edge_vertex_indices: tuple[tuple[int, int, CharacteristicFamily], ...]
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdge, ...]
  topology: MocTopologyResult
  source_pressure_gradient: tuple[float, float] | None
  solver_iterations: int
  solver_success: bool
  solver_cost: float | None
  solver_optimality: float | None
  maximum_edge_alignment_residual: float | None
  minimum_forward_margin_m: float | None
  maximum_k_residual: float | None
  maximum_entropy_compatibility_residual: float | None
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  pressure_lineage_verified: bool
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  internal_characteristic_closure_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  position_tolerance_m: float = 1.0e-10
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  pressure_lineage_tolerance: float = 1.0e-8
  compatibility_weight: float = 1.0e7
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus'
      )
    if self.source_trial is not None and not isinstance(
      self.source_trial,
      MocEulerAmbientFirstWedgeEntropyCarryResult,
    ):
      raise TypeError(
        'source_trial must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryResult or None'
      )
    nodes = tuple(self.nodes)
    if any(
      not isinstance(node, MocEulerAmbientFirstWedgeEntropyCharacteristicNode)
      for node in nodes
    ):
      raise TypeError(
        'nodes must contain '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicNode values'
      )
    if tuple(node.node_index for node in nodes) != tuple(range(len(nodes))):
      raise ValueError('nodes must have contiguous node indices')
    cells = tuple(self.cells)
    samples = tuple(self.cell_samples)
    if len(cells) != len(samples):
      raise ValueError('cells and cell_samples must have equal lengths')
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError('cells must contain MocCharacteristicCell values')
    if any(
      not isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      for sample in samples
    ):
      raise TypeError(
        'cell_samples must contain MocEulerAmbientFirstWedgeCellSample values'
      )
    edges = tuple(self.edge_vertex_indices)
    for edge in edges:
      if len(edge) != 3 or not isinstance(edge[2], CharacteristicFamily):
        raise TypeError(
          'edge_vertex_indices must contain (start, end, CharacteristicFamily)'
        )
      if any(
        isinstance(index, bool)
        or not isinstance(index, int)
        or index < 0
        or index >= len(nodes)
        for index in edge[:2]
      ):
        raise ValueError('edge vertex indices must reference existing nodes')
    characteristic_edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(edge, MocEulerAmbientFirstWedgeCharacteristicEdge)
      for edge in characteristic_edges
    ):
      raise TypeError(
        'characteristic_edges must contain typed characteristic edge values'
      )
    if len(characteristic_edges) != len(edges):
      raise ValueError('characteristic_edges must align with edge_vertex_indices')
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    if self.source_pressure_gradient is not None:
      gradient = tuple(float(value) for value in self.source_pressure_gradient)
      if len(gradient) != 2 or not all(isfinite(value) for value in gradient):
        raise ValueError('source_pressure_gradient must contain finite x/y values')
      object.__setattr__(self, 'source_pressure_gradient', gradient)
    for name in ('solver_success',):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if (
      isinstance(self.solver_iterations, bool)
      or not isinstance(self.solver_iterations, int)
      or self.solver_iterations < 0
    ):
      raise ValueError('solver_iterations must be a nonnegative integer')
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'cell_euler_residuals must contain finite nonnegative values'
      )
    if len(residuals) != len(cells):
      raise ValueError('cell_euler_residuals must match cells')
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    for name in (
      'solver_cost',
      'solver_optimality',
      'maximum_edge_alignment_residual',
      'minimum_forward_margin_m',
      'maximum_k_residual',
      'maximum_entropy_compatibility_residual',
      'maximum_cell_euler_residual',
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
      'pressure_lineage_verified',
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'internal_characteristic_closure_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_closure_verified:
      raise ValueError(
        'an internal characteristic field cannot claim physical closure'
      )
    if not self.chain_promotion_blocked:
      raise ValueError(
        'an internal characteristic field must remain blocked from chain promotion'
      )
    if self.production_claim_allowed:
      raise ValueError(
        'an internal characteristic field cannot claim production validity'
      )
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
      'cell_residual_tolerance',
      'pressure_lineage_tolerance',
      'compatibility_weight',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    object.__setattr__(self, 'nodes', nodes)
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'cell_samples', samples)
    object.__setattr__(self, 'edge_vertex_indices', edges)
    object.__setattr__(self, 'characteristic_edges', characteristic_edges)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus
      .CONVERGED_INTERNAL_CHARACTERISTIC_FIELD
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.pressure_lineage_verified
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and self.internal_characteristic_closure_verified
      and self.continuation_boundary_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  @property
  def node_count(self) -> int:
    return len(self.nodes)

  @property
  def cell_count(self) -> int:
    return len(self.cells)

  @property
  def vertices_xr_m(self) -> tuple[tuple[float, float], ...]:
    return tuple(node.point_m for node in self.nodes)

  @property
  def states(self) -> tuple[CharacteristicState, ...]:
    return tuple(node.state for node in self.nodes)

  @property
  def total_pressure_Pa(self) -> tuple[float, ...]:
    return tuple(node.total_pressure_Pa for node in self.nodes)

  @property
  def state_sampling_available(self) -> bool:
    """Whether the retained local field can provide bounded state samples.

    The sampler is deliberately gated by the local characteristic/Euler
    checks.  A field with only a successful nonlinear solve, or with a
    weakened cached flag, must not become an upstream source for a later
    shock attempt.
    """

    return bool(
      self.local_consistency_verified
      and self.cells
      and len(self.cell_samples) == len(self.cells)
    )

  @staticmethod
  def _finite_point(
    point_m: tuple[float, float],
  ) -> tuple[float, float] | None:
    try:
      point = (float(point_m[0]), float(point_m[1]))
    except (IndexError, TypeError, ValueError):
      return None
    if not all(isfinite(value) for value in point):
      return None
    return point

  def _sample_weights_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> tuple[
    tuple[float, ...],
    MocEulerAmbientFirstWedgeCellSample,
  ] | None:
    """Return barycentric weights for the first bounded containing cell."""

    if not self.state_sampling_available:
      return None
    point = self._finite_point(point_m)
    if point is None:
      return None
    tolerance = float(position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    for sample in self.cell_samples:
      weights = _triangle_interpolation_weights(
        point,
        sample.vertices_xr_m,
        tolerance_m=tolerance,
      )
      if weights is not None:
        return weights, sample
    return None

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Interpolate a supersonic state only inside the retained local mesh.

    ``theta`` and Prandtl--Meyer angle are interpolated on the bounded
    triangle, then the Mach number is reconstructed from the latter.  No
    state is extrapolated beyond the four solver-owned subcells.
    """

    sampled = self._sample_weights_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    weights, sample = sampled
    theta = sum(
      weight * state.theta_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    nu = sum(
      weight * state.nu_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    point = self._finite_point(point_m)
    if point is None:
      return None
    return _state_from_theta_nu(
      point,
      theta,
      nu,
      sample.states[0].gamma,
    )

  def total_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Interpolate carried total pressure in the bounded entropy field."""

    sampled = self._sample_weights_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    weights, sample = sampled
    return exp(
      sum(
        weight * log(pressure)
        for weight, pressure in zip(
          weights,
          sample.total_pressure_Pa,
          strict=True,
        )
      )
    )

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the isentropic static pressure for a bounded field sample."""

    state = self.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    total_pressure = self.total_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or total_pressure is None:
      return None
    return total_pressure / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))

  @property
  def continuation_boundary_node_indices(self) -> tuple[int, ...]:
    """Return the explicit diagnostic frontier node order.

    The frontier is the split ambient-side edge ``1 -> 4 -> 2``.  It is
    exposed as metadata for a future reflected/free-boundary solver; this
    result still cannot seed a physical ``MocChainCell``.
    """

    return _CONTINUATION_BOUNDARY_NODE_INDICES

  @property
  def continuation_boundary_kind(self) -> MocChainBoundaryKind:
    """Return the typed meaning of the carried diagnostic frontier."""

    return MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER

  @property
  def continuation_boundary(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the exact state/pressure frontier for downstream coupling.

    An incomplete solver result exposes no handoff.  The caller must still
    apply the local-consistency and physical free-boundary gates before using
    these samples in a continued-cell solve.
    """

    if any(index >= len(self.nodes) for index in self.continuation_boundary_node_indices):
      return ()
    return tuple(
      MocChainBoundarySample(
        state=self.nodes[index].state,
        total_pressure_Pa=self.nodes[index].total_pressure_Pa,
      )
      for index in self.continuation_boundary_node_indices
    )

  @property
  def continuation_boundary_verified(self) -> bool:
    """Whether the explicit frontier is finite and strictly downstream."""

    boundary = self.continuation_boundary
    return bool(
      len(boundary) == len(self.continuation_boundary_node_indices)
      and all(
        current.state.x_m > previous.state.x_m + self.position_tolerance_m
        for previous, current in zip(boundary, boundary[1:])
      )
      and all(sample.state.y_m >= -self.position_tolerance_m for sample in boundary)
    )

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is (
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.INVALID_INPUT
      )
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'internal entropy-carrying characteristic field remains below chain '
        'promotion; reflected free-boundary coupling and external validation '
        'are still required'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'internal_characteristic_field_status': self.status.value,
        'node_count': self.node_count,
        'cell_count': self.cell_count,
        'continuation_boundary_kind': self.continuation_boundary_kind.value,
        'continuation_boundary_node_indices': (
          self.continuation_boundary_node_indices
        ),
        'continuation_boundary_sample_count': len(self.continuation_boundary),
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'internal_characteristic_closure_verified': (
          self.internal_characteristic_closure_verified
        ),
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'required_next_gate': (
          'reflected-free-boundary-coupling-and-external-validation-before-'
          'continued-shock-cell-chain'
        ),
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'continuation_boundary_kind': self.continuation_boundary_kind.value,
      'continuation_boundary_node_indices': list(
        self.continuation_boundary_node_indices
      ),
      'continuation_boundary_sample_count': len(self.continuation_boundary),
      'state_sampling_available': self.state_sampling_available,
      'continuation_boundary_verified': self.continuation_boundary_verified,
      'continuation_boundary': [
        {
          'point_m': [sample.state.x_m, sample.state.y_m],
          'mach': sample.state.mach,
          'flow_angle_rad': sample.state.theta_rad,
          'total_pressure_Pa': sample.total_pressure_Pa,
        }
        for sample in self.continuation_boundary
      ],
      'nodes': [node.as_report() for node in self.nodes],
      'cells': [
        {
          'cell_index': cell.cell_index,
          'cell_kind': cell.cell_kind,
          'vertices_xr_m': [list(point) for point in cell.vertices_xr_m],
        }
        for cell in self.cells
      ],
      'cell_samples': [
        sample.as_report() for sample in self.cell_samples
      ],
      'edge_vertex_indices': [
        {
          'start_node': edge[0],
          'end_node': edge[1],
          'family': edge[2].value,
        }
        for edge in self.edge_vertex_indices
      ],
      'characteristic_edges': [
        edge.as_report() for edge in self.characteristic_edges
      ],
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'source_trial_status': (
        None if self.source_trial is None else self.source_trial.status.value
      ),
      'source_pressure_gradient': self.source_pressure_gradient,
      'solver_iterations': self.solver_iterations,
      'solver_success': self.solver_success,
      'solver_cost': self.solver_cost,
      'solver_optimality': self.solver_optimality,
      'maximum_edge_alignment_residual': self.maximum_edge_alignment_residual,
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_k_residual': self.maximum_k_residual,
      'maximum_entropy_compatibility_residual': (
        self.maximum_entropy_compatibility_residual
      ),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
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
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'compatibility_weight': self.compatibility_weight,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'claim_status': (
        'solver-owned-internal-entropy-carrying-characteristic-field; '
        'reflected free-boundary coupling and external validation remain '
        'pending'
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class _EdgeMetric:
  alignment: float
  forward_margin: float
  edge_length: float
  actual: float
  source: float

  @property
  def compatibility(self) -> float:
    return abs(self.actual - self.source)


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _triangle_interpolation_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  """Return inclusive barycentric weights for a nondegenerate triangle."""

  if len(vertices) != 3:
    return None
  (ax, ay), (bx, by), (cx, cy) = vertices
  denominator = (
    (by - cy) * (ax - cx)
    + (cx - bx) * (ay - cy)
  )
  if not isfinite(denominator) or abs(denominator) <= max(
    tolerance_m * tolerance_m,
    1.0e-24,
  ):
    return None
  px, py = point
  first = (
    (by - cy) * (px - cx)
    + (cx - bx) * (py - cy)
  ) / denominator
  second = (
    (cy - ay) * (px - cx)
    + (ax - cx) * (py - cy)
  ) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10:
    return None
  if max(first, second, third) > 1.0 + 1.0e-10:
    return None
  return first, second, third


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus,
  source_trial: MocEulerAmbientFirstWedgeEntropyCarryResult | None,
  message: str,
  *,
  nodes: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  cell_samples: Sequence[MocEulerAmbientFirstWedgeCellSample] = (),
  edge_vertex_indices: Sequence[tuple[int, int, CharacteristicFamily]] = (),
  characteristic_edges: Sequence[MocEulerAmbientFirstWedgeCharacteristicEdge] = (),
  topology: MocTopologyResult | None = None,
  source_pressure_gradient: tuple[float, float] | None = None,
  solver_iterations: int = 0,
  solver_success: bool = False,
  solver_cost: float | None = None,
  solver_optimality: float | None = None,
  maximum_edge_alignment_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  maximum_k_residual: float | None = None,
  maximum_entropy_compatibility_residual: float | None = None,
  cell_euler_residuals: Sequence[float] = (),
  maximum_cell_euler_residual: float | None = None,
  pressure_lineage_verified: bool = False,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  internal_characteristic_closure_verified: bool = False,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
  compatibility_weight: float = 1.0e7,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult(
    status=status,
    source_trial=source_trial,
    nodes=tuple(nodes),
    cells=tuple(cells),
    cell_samples=tuple(cell_samples),
    edge_vertex_indices=tuple(edge_vertex_indices),
    characteristic_edges=tuple(characteristic_edges),
    topology=_empty_topology() if topology is None else topology,
    source_pressure_gradient=source_pressure_gradient,
    solver_iterations=solver_iterations,
    solver_success=solver_success,
    solver_cost=solver_cost,
    solver_optimality=solver_optimality,
    maximum_edge_alignment_residual=maximum_edge_alignment_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    maximum_k_residual=maximum_k_residual,
    maximum_entropy_compatibility_residual=(
      maximum_entropy_compatibility_residual
    ),
    cell_euler_residuals=tuple(cell_euler_residuals),
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=(
      variable_entropy_compatibility_verified
    ),
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    internal_characteristic_closure_verified=(
      internal_characteristic_closure_verified
    ),
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    compatibility_weight=compatibility_weight,
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


def _state_from_theta_nu(
  point: tuple[float, float],
  theta: float,
  nu: float,
  gamma: float,
) -> CharacteristicState | None:
  inversion = inverse_prandtl_meyer_angle_rad(nu, gamma)
  if not inversion.converged or inversion.value is None:
    return None
  try:
    return CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=theta,
      mach=inversion.value,
      gamma=gamma,
    )
  except (TypeError, ValueError):
    return None


def _interpolate_source_state(
  first: CharacteristicState,
  second: CharacteristicState,
  point: tuple[float, float],
  fraction: float,
) -> CharacteristicState | None:
  theta = first.theta_rad + fraction * (second.theta_rad - first.theta_rad)
  nu = first.nu_rad + fraction * (second.nu_rad - first.nu_rad)
  return _state_from_theta_nu(point, theta, nu, first.gamma)


def _edge_metric(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  start_index: int,
  end_index: int,
  family: CharacteristicFamily,
  gradient: tuple[float, float],
) -> _EdgeMetric | None:
  start_state = states[start_index]
  end_state = states[end_index]
  start_direction = start_state.direction(family)
  end_direction = end_state.direction(family)
  averaged = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
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
  forward_margin = (
    displacement[0] * direction[0] + displacement[1] * direction[1]
  )
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
  return _EdgeMetric(*values)


def _state_for_vector(
  vector: Sequence[float],
  source_vertices: tuple[tuple[float, float], ...],
  source_states: tuple[CharacteristicState, ...],
  source_pressures: tuple[float, ...],
) -> tuple[
  tuple[tuple[float, float], ...],
  tuple[CharacteristicState, ...],
  tuple[float, ...],
] | None:
  first, second, third = source_vertices
  fraction_p = float(vector[0])
  theta_p = float(vector[1])
  mach_p = float(vector[2])
  fraction_q = float(vector[3])
  theta_q = float(vector[4])
  mach_q = float(vector[5])
  centerline_x = float(vector[6])
  centerline_mach = float(vector[7])
  point_p = (
    first[0] + fraction_p * (second[0] - first[0]),
    first[1] + fraction_p * (second[1] - first[1]),
  )
  point_q = (
    second[0] + fraction_q * (third[0] - second[0]),
    second[1] + fraction_q * (third[1] - second[1]),
  )
  point_c = (centerline_x, 0.0)
  try:
    state_p = CharacteristicState(
      x_m=point_p[0],
      y_m=point_p[1],
      theta_rad=theta_p,
      mach=mach_p,
      gamma=source_states[0].gamma,
    )
    state_q = CharacteristicState(
      x_m=point_q[0],
      y_m=point_q[1],
      theta_rad=theta_q,
      mach=mach_q,
      gamma=source_states[0].gamma,
    )
    state_c = CharacteristicState(
      x_m=point_c[0],
      y_m=point_c[1],
      theta_rad=0.0,
      mach=centerline_mach,
      gamma=source_states[0].gamma,
    )
  except (TypeError, ValueError):
    return None
  pressure_p = exp(
    (1.0 - fraction_p) * log(source_pressures[0])
    + fraction_p * log(source_pressures[1])
  )
  pressure_q = exp(
    (1.0 - fraction_q) * log(source_pressures[1])
    + fraction_q * log(source_pressures[2])
  )
  vertices = (first, second, third, point_p, point_q, point_c)
  states = (
    source_states[0],
    source_states[1],
    source_states[2],
    state_p,
    state_q,
    state_c,
  )
  pressures = (
    source_pressures[0],
    source_pressures[1],
    source_pressures[2],
    pressure_p,
    pressure_q,
    source_pressures[0],
  )
  if not all(isfinite(value) and value > 0.0 for value in pressures):
    return None
  return vertices, states, pressures


_EDGE_DEFINITIONS: tuple[tuple[int, int, CharacteristicFamily], ...] = (
  (0, 3, CharacteristicFamily.PLUS),
  (3, 1, CharacteristicFamily.PLUS),
  (1, 4, CharacteristicFamily.MINUS),
  (4, 2, CharacteristicFamily.MINUS),
  (3, 5, CharacteristicFamily.MINUS),
  (5, 4, CharacteristicFamily.PLUS),
)

# The field's outer/downstream frontier is the split source edge from the
# ambient-side node to the centerline endpoint.  It is a diagnostic handoff,
# not a solved physical perimeter; keeping the indices explicit prevents a
# future chain planner from inferring a frontier from cell order.
_CONTINUATION_BOUNDARY_NODE_INDICES = (1, 4, 2)

_INITIAL_EDGE_FRACTION = 0.6
_FRACTION_ANCHOR_WEIGHT = 1.0e-4


def _residual_vector(
  vector: Sequence[float],
  source_vertices: tuple[tuple[float, float], ...],
  source_states: tuple[CharacteristicState, ...],
  source_pressures: tuple[float, ...],
  gradient: tuple[float, float],
  compatibility_weight: float,
) -> np.ndarray:
  resolved = _state_for_vector(
    vector,
    source_vertices,
    source_states,
    source_pressures,
  )
  if resolved is None:
    return np.full(2 * len(_EDGE_DEFINITIONS), 1.0e6, dtype=float)
  vertices, states, _pressures = resolved
  compatibility_residuals: list[float] = []
  for start_index, end_index, family in _EDGE_DEFINITIONS:
    metric = _edge_metric(
      vertices,
      states,
      start_index,
      end_index,
      family,
      gradient,
    )
    if metric is None:
      return np.full(2 * len(_EDGE_DEFINITIONS), 1.0e6, dtype=float)
    compatibility_residuals.append(
      compatibility_weight * (metric.actual - metric.source)
    )
  # The six compatibility equations leave two geometric degrees of freedom.
  # Keep the deterministic interior split near the source-trial edge midspan;
  # all six edge alignments remain independent acceptance gates below.  This
  # avoids claiming that an overdetermined least-squares compromise is an
  # exact characteristic intersection.
  compatibility_residuals.extend((
    _FRACTION_ANCHOR_WEIGHT * (float(vector[0]) - _INITIAL_EDGE_FRACTION),
    _FRACTION_ANCHOR_WEIGHT * (float(vector[3]) - _INITIAL_EDGE_FRACTION),
  ))
  return np.asarray(compatibility_residuals, dtype=float)


def _build_nodes(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
) -> tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicNode, ...]:
  kinds = (
    'shock-endpoint',
    'ambient-edge-endpoint',
    'centerline-reflection-endpoint',
    'shock-edge-interior',
    'ambient-edge-interior',
    'internal-centerline',
  )
  lineages = (
    'shock-endpoint',
    'ambient-source',
    'shock-centerline',
    'shock-to-ambient-edge',
    'ambient-to-shock-edge',
    'shock-centerline',
  )
  return tuple(
    MocEulerAmbientFirstWedgeEntropyCharacteristicNode(
      node_index=index,
      node_kind=kinds[index],
      pressure_lineage=lineages[index],
      point_m=vertices[index],
      state=states[index],
      total_pressure_Pa=pressures[index],
    )
    for index in range(len(vertices))
  )


def _build_cells(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
) -> tuple[
  tuple[MocCharacteristicCell, ...],
  tuple[MocEulerAmbientFirstWedgeCellSample, ...],
]:
  cell_node_indices = (
    (0, 3, 5),
    (3, 1, 4),
    (3, 4, 5),
    (5, 4, 2),
  )
  cells: list[MocCharacteristicCell] = []
  samples: list[MocEulerAmbientFirstWedgeCellSample] = []
  for cell_index, indices in enumerate(cell_node_indices):
    cell_vertices = tuple(vertices[index] for index in indices)
    cell_states = tuple(states[index] for index in indices)
    cell_pressures = tuple(pressures[index] for index in indices)
    cells.append(
      MocCharacteristicCell(
        cell_index=cell_index,
        cell_kind='post-shock-ambient-entropy-characteristic-subcell',
        vertices_xr_m=cell_vertices,
        centerline_indices=(5,) if 5 in indices else (),
        boundary_indices=tuple(index for index in indices if index != 5),
      )
    )
    samples.append(
      MocEulerAmbientFirstWedgeCellSample(
        vertices_xr_m=cell_vertices,
        states=cell_states,
        total_pressure_Pa=cell_pressures,
      )
    )
  return tuple(cells), tuple(samples)


def solve_euler_ambient_first_wedge_entropy_characteristic_field(
  source_trial: MocEulerAmbientFirstWedgeEntropyCarryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
  pressure_lineage_tolerance: float = 1.0e-8,
  compatibility_weight: float = 1.0e7,
  maximum_iterations: int = 48,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult:
  """Solve the bounded four-triangle internal characteristic field.

  ``source_trial`` may have failed only its coarse Euler residual gate.  Its
  source characteristic and pressure-lineage gates must still be available;
  otherwise this solver returns a typed source-gate failure.  The nonlinear
  solve minimizes both edge alignment and generalized variable-entropy
  compatibility, with compatibility deliberately weighted strongly.  The
  resulting field is still not a free-boundary or chain solve.
  """

  if not isinstance(
    source_trial,
    MocEulerAmbientFirstWedgeEntropyCarryResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.INVALID_INPUT,
      None,
      'source_trial must be a '
      'MocEulerAmbientFirstWedgeEntropyCarryResult',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
    lineage_tolerance = float(pressure_lineage_tolerance)
    compatibility_scale = float(compatibility_weight)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.INVALID_INPUT,
      source_trial,
      'internal characteristic field tolerances must be numeric',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
    ('pressure_lineage_tolerance', lineage_tolerance),
    ('compatibility_weight', compatibility_scale),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  common = {
    'position_tolerance_m': position_tolerance,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'pressure_lineage_tolerance': lineage_tolerance,
    'compatibility_weight': compatibility_scale,
  }
  if source_trial.source_candidate is None or source_trial.source_field is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOURCE_REQUIRED,
      source_trial,
      'internal characteristic field requires the source candidate and field '
      'retained by the entropy trial',
      **common,
    )
  if not (
    source_trial.pressure_lineage_verified
    and source_trial.characteristic_geometry_verified
    and source_trial.variable_entropy_compatibility_verified
    and source_trial.axis_streamline_entropy_verified
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOURCE_GATE_FAILURE,
      source_trial,
      'entropy trial lacks the characteristic and pressure gates required by '
      'the internal field solve',
      **common,
    )
  source_vertices = tuple(source_trial.vertices_xr_m)
  source_states = tuple(source_trial.states)
  source_pressures = tuple(source_trial.total_pressure_Pa)
  if not (
    len(source_vertices) == len(source_states) == len(source_pressures) == 3
    and all(isfinite(value) and value > 0.0 for value in source_pressures)
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOURCE_REQUIRED,
      source_trial,
      'entropy trial must retain exactly three finite positive source states '
      'and total-pressure values',
      **common,
    )
  gradient = _log_pressure_gradient(source_vertices, source_pressures)
  if gradient is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOURCE_REQUIRED,
      source_trial,
      'entropy trial does not provide a finite source total-pressure gradient',
      **common,
    )
  if abs(source_pressures[2] - source_pressures[0]) > lineage_tolerance * max(
    1.0,
    abs(source_pressures[0]),
    abs(source_pressures[2]),
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.PRESSURE_LINEAGE_FAILURE,
      source_trial,
      'source centerline pressure does not retain the shock-endpoint lineage',
      source_pressure_gradient=gradient,
      pressure_lineage_verified=False,
      **common,
    )
  first, second, third = source_vertices
  x_lower = min(first[0], second[0], third[0]) + position_tolerance
  x_upper = max(first[0], second[0], third[0]) - position_tolerance
  if not isfinite(x_lower) or not isfinite(x_upper) or x_upper <= x_lower:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOURCE_REQUIRED,
      source_trial,
      'source triangle does not leave a valid centerline solve interval',
      source_pressure_gradient=gradient,
      **common,
    )
  initial_fraction = _INITIAL_EDGE_FRACTION
  initial_p = _interpolate_source_state(
    source_states[0],
    source_states[1],
    (
      first[0] + initial_fraction * (second[0] - first[0]),
      first[1] + initial_fraction * (second[1] - first[1]),
    ),
    initial_fraction,
  )
  initial_q = _interpolate_source_state(
    source_states[1],
    source_states[2],
    (
      second[0] + initial_fraction * (third[0] - second[0]),
      second[1] + initial_fraction * (third[1] - second[1]),
    ),
    initial_fraction,
  )
  if initial_p is None or initial_q is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOURCE_REQUIRED,
      source_trial,
      'source edge interpolation left the supersonic Prandtl--Meyer domain',
      source_pressure_gradient=gradient,
      **common,
    )
  initial_centerline_mach = max(
    1.05,
    0.5 * (initial_p.mach + initial_q.mach),
  )
  initial = np.asarray(
    (
      initial_fraction,
      initial_p.theta_rad,
      initial_p.mach,
      initial_fraction,
      initial_q.theta_rad,
      initial_q.mach,
      0.5 * (x_lower + x_upper),
      initial_centerline_mach,
    ),
    dtype=float,
  )
  theta_lower = min(state.theta_rad for state in source_states) - 1.0
  theta_upper = max(state.theta_rad for state in source_states) + 1.0
  bounds = (
    np.asarray((0.01, theta_lower, 1.0001, 0.01, theta_lower, 1.0001, x_lower, 1.0001)),
    np.asarray((0.99, theta_upper, 8.0, 0.99, theta_upper, 8.0, x_upper, 8.0)),
  )
  try:
    solved = least_squares(
      lambda vector: _residual_vector(
        vector,
        source_vertices,
        source_states,
        source_pressures,
        gradient,
        compatibility_scale,
      ),
      initial,
      bounds=bounds,
      max_nfev=max(16, maximum_iterations * 20),
      xtol=1.0e-13,
      ftol=1.0e-13,
      gtol=1.0e-13,
      x_scale='jac',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOLVER_FAILURE,
      source_trial,
      f'internal characteristic least-squares solve failed: {error}',
      source_pressure_gradient=gradient,
      **common,
    )
  resolved = _state_for_vector(
    solved.x,
    source_vertices,
    source_states,
    source_pressures,
  )
  if resolved is None or not solved.success:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.SOLVER_FAILURE,
      source_trial,
      'internal characteristic least-squares solve did not converge in its '
      f'declared budget: {solved.message}',
      source_pressure_gradient=gradient,
      solver_iterations=int(getattr(solved, 'nfev', 0)),
      solver_success=bool(getattr(solved, 'success', False)),
      solver_cost=float(getattr(solved, 'cost', 0.0)),
      solver_optimality=float(getattr(solved, 'optimality', 0.0)),
      **common,
    )
  vertices, states, pressures = resolved
  metrics = tuple(
    _edge_metric(
      vertices,
      states,
      start_index,
      end_index,
      family,
      gradient,
    )
    for start_index, end_index, family in _EDGE_DEFINITIONS
  )
  if any(metric is None for metric in metrics):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      source_trial,
      'internal characteristic field produced an invalid edge metric',
      source_pressure_gradient=gradient,
      solver_iterations=int(solved.nfev),
      solver_success=True,
      solver_cost=float(solved.cost),
      solver_optimality=float(solved.optimality),
      **common,
    )
  typed_metrics = tuple(metric for metric in metrics if metric is not None)
  maximum_alignment = max(metric.alignment for metric in typed_metrics)
  minimum_forward = min(metric.forward_margin for metric in typed_metrics)
  maximum_k = max(abs(metric.actual) for metric in typed_metrics)
  maximum_compatibility = max(metric.compatibility for metric in typed_metrics)
  characteristic_geometry_verified = bool(
    maximum_alignment <= alignment_tolerance
    and minimum_forward > position_tolerance
    and abs(vertices[2][1]) <= position_tolerance
    and abs(vertices[5][1]) <= position_tolerance
    and abs(states[2].theta_rad) <= residual_tolerance
    and abs(states[5].theta_rad) <= residual_tolerance
  )
  variable_entropy_verified = bool(
    characteristic_geometry_verified
    and maximum_compatibility <= residual_tolerance
  )
  pressure_lineage_verified = bool(
    abs(pressures[0] - pressures[2])
    <= lineage_tolerance * max(1.0, abs(pressures[0]), abs(pressures[2]))
    and abs(pressures[0] - pressures[5])
    <= lineage_tolerance * max(1.0, abs(pressures[0]), abs(pressures[5]))
    and abs(log(pressures[3]) - (
      (1.0 - float(solved.x[0])) * log(source_pressures[0])
      + float(solved.x[0]) * log(source_pressures[1])
    )) <= lineage_tolerance
    and abs(log(pressures[4]) - (
      (1.0 - float(solved.x[3])) * log(source_pressures[1])
      + float(solved.x[3]) * log(source_pressures[2])
    )) <= lineage_tolerance
  )
  try:
    nodes = _build_nodes(vertices, states, pressures)
    cells, cell_samples = _build_cells(vertices, states, pressures)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.CHARACTERISTIC_GEOMETRY_FAILURE,
      source_trial,
      f'internal characteristic subcell assembly failed: {error}',
      source_pressure_gradient=gradient,
      solver_iterations=int(solved.nfev),
      solver_success=True,
      solver_cost=float(solved.cost),
      solver_optimality=float(solved.optimality),
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_compatibility,
      pressure_lineage_verified=pressure_lineage_verified,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      **common,
    )
  topology = validate_moc_mesh(cells)
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.TOPOLOGY_FAILURE,
      source_trial,
      f'internal characteristic subcell topology failed: {topology.message}',
      nodes=nodes,
      cells=cells,
      cell_samples=cell_samples,
      topology=topology,
      source_pressure_gradient=gradient,
      solver_iterations=int(solved.nfev),
      solver_success=True,
      solver_cost=float(solved.cost),
      solver_optimality=float(solved.optimality),
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_compatibility,
      pressure_lineage_verified=pressure_lineage_verified,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      **common,
    )
  characteristic_edges = tuple(
    MocEulerAmbientFirstWedgeCharacteristicEdge(
      edge_index=index,
      family=family,
      start_vertex=vertices[start_index],
      end_vertex=vertices[end_index],
      edge_length_m=metric.edge_length,
      forward_margin_m=metric.forward_margin,
      alignment_residual=metric.alignment,
      k_residual=abs(metric.actual),
      entropy_source_prediction=abs(metric.source),
      compatibility_residual=metric.compatibility,
    )
    for index, ((start_index, end_index, family), metric) in enumerate(
      zip(_EDGE_DEFINITIONS, typed_metrics, strict=True)
    )
  )
  residuals: list[float] = []
  try:
    for sample in cell_samples:
      residuals.append(
        _cell_euler_residual(
          sample.vertices_xr_m,
          sample.states,
          sample.total_pressure_Pa,
        )
      )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.EULER_RESIDUAL_FAILURE,
      source_trial,
      f'internal characteristic cell Euler residual failed: {error}',
      nodes=nodes,
      cells=cells,
      cell_samples=cell_samples,
      edge_vertex_indices=_EDGE_DEFINITIONS,
      characteristic_edges=characteristic_edges,
      topology=topology,
      source_pressure_gradient=gradient,
      solver_iterations=int(solved.nfev),
      solver_success=True,
      solver_cost=float(solved.cost),
      solver_optimality=float(solved.optimality),
      maximum_edge_alignment_residual=maximum_alignment,
      minimum_forward_margin_m=minimum_forward,
      maximum_k_residual=maximum_k,
      maximum_entropy_compatibility_residual=maximum_compatibility,
      pressure_lineage_verified=pressure_lineage_verified,
      characteristic_geometry_verified=characteristic_geometry_verified,
      variable_entropy_compatibility_verified=variable_entropy_verified,
      **common,
    )
  maximum_cell_residual = max(residuals, default=None)
  residuals_finite = bool(residuals and all(isfinite(value) for value in residuals))
  residuals_verified = bool(
    residuals_finite
    and maximum_cell_residual is not None
    and maximum_cell_residual <= cell_tolerance
  )
  internal_closure_verified = bool(
    topology_verified
    and pressure_lineage_verified
    and characteristic_geometry_verified
    and variable_entropy_verified
  )
  if not pressure_lineage_verified:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.PRESSURE_LINEAGE_FAILURE
    message = 'internal characteristic field did not preserve the declared pressure lineages'
  elif not characteristic_geometry_verified or not variable_entropy_verified:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.CHARACTERISTIC_GEOMETRY_FAILURE
    message = 'internal characteristic field did not satisfy its family geometry and compatibility gates'
  elif not residuals_verified:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.EULER_RESIDUAL_FAILURE
    message = 'internal characteristic field requires further conservative subcell refinement'
  else:
    status = MocEulerAmbientFirstWedgeEntropyCharacteristicFieldStatus.CONVERGED_INTERNAL_CHARACTERISTIC_FIELD
    message = 'internal entropy-carrying characteristic field passed local gates; reflected free-boundary closure remains blocked'
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult(
    status=status,
    source_trial=source_trial,
    nodes=nodes,
    cells=cells,
    cell_samples=cell_samples,
    edge_vertex_indices=_EDGE_DEFINITIONS,
    characteristic_edges=characteristic_edges,
    topology=topology,
    source_pressure_gradient=gradient,
    solver_iterations=int(solved.nfev),
    solver_success=True,
    solver_cost=float(solved.cost),
    solver_optimality=float(solved.optimality),
    maximum_edge_alignment_residual=maximum_alignment,
    minimum_forward_margin_m=minimum_forward,
    maximum_k_residual=maximum_k,
    maximum_entropy_compatibility_residual=maximum_compatibility,
    cell_euler_residuals=tuple(residuals),
    maximum_cell_euler_residual=maximum_cell_residual,
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    internal_characteristic_closure_verified=internal_closure_verified,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    cell_residual_tolerance=cell_tolerance,
    pressure_lineage_tolerance=lineage_tolerance,
    compatibility_weight=compatibility_scale,
    message=message,
  )
