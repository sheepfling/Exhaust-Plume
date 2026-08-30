"""Solver-owned characteristic remesh for a bounded entropy continuation.

The continuation source band is useful as a coarse alternating characteristic
construction, but its barycentric refinement is only a projection.  This
module solves the two characteristic boundary edges of each source triangle
as short variable-entropy boundary-value problems and reuses one exact edge
trace wherever neighboring triangles meet.  The four-interval case also
solves a bounded interior C+/C- row stencil; global closure remains separate.

The resulting mesh is research evidence.  It has no shock jump, no globally
closed reflected free boundary, and no physical shock-cell-chain promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, hypot, isfinite, log
from typing import Any, Sequence

from scipy.optimize import least_squares

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_carry import _cell_euler_residual
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  _characteristic_geometry_residual,
  _compatibility_source,
  _transport_total_pressure,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult',
  'remesh_euler_ambient_first_wedge_entropy_characteristic_continuation',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus(
  str,
  Enum,
):
  """Outcome of the bounded solver-owned characteristic remesh."""

  CONVERGED_LOCAL_CHARACTERISTIC_REMESH = (
    'converged_local_entropy_characteristic_continuation_remesh'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_REQUIRED = (
    'entropy_characteristic_continuation_remesh_source_required'
  )
  EDGE_SOLVE_FAILURE = (
    'entropy_characteristic_continuation_remesh_edge_solve_failure'
  )
  TOPOLOGY_FAILURE = (
    'entropy_characteristic_continuation_remesh_topology_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'entropy_characteristic_continuation_remesh_euler_residual_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge:
  """One shared, solver-owned characteristic edge trace."""

  edge_index: int
  family: CharacteristicFamily
  start_state: CharacteristicState
  end_state: CharacteristicState
  start_total_pressure_Pa: float
  end_total_pressure_Pa: float
  points_xr_m: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  total_pressure_Pa: tuple[float, ...]
  geometry_residuals: tuple[float, ...]
  compatibility_residuals: tuple[float, ...]
  pressure_residuals: tuple[float, ...]

  def __post_init__(self) -> None:
    if (
      isinstance(self.edge_index, bool)
      or not isinstance(self.edge_index, int)
      or self.edge_index < 0
    ):
      raise ValueError('edge_index must be a nonnegative integer')
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    if not isinstance(self.start_state, CharacteristicState):
      raise TypeError('start_state must be a CharacteristicState')
    if not isinstance(self.end_state, CharacteristicState):
      raise TypeError('end_state must be a CharacteristicState')
    start_pressure = float(self.start_total_pressure_Pa)
    end_pressure = float(self.end_total_pressure_Pa)
    if not all(
      isfinite(value) and value > 0.0
      for value in (start_pressure, end_pressure)
    ):
      raise ValueError('edge endpoint pressures must be finite and positive')
    object.__setattr__(self, 'start_total_pressure_Pa', start_pressure)
    object.__setattr__(self, 'end_total_pressure_Pa', end_pressure)
    points = tuple(
      (float(point[0]), float(point[1])) for point in self.points_xr_m
    )
    if len(points) < 2 or any(
      not all(isfinite(value) for value in point) for point in points
    ):
      raise ValueError('edge points must contain at least two finite points')
    states = tuple(self.states)
    pressures = tuple(float(value) for value in self.total_pressure_Pa)
    if len(states) != len(points) or len(pressures) != len(points):
      raise ValueError('edge points, states, and pressures must align')
    if any(not isinstance(state, CharacteristicState) for state in states):
      raise TypeError('edge states must contain CharacteristicState values')
    if any(not isfinite(value) or value <= 0.0 for value in pressures):
      raise ValueError('edge pressures must be finite and positive')
    for point, state in zip(points, states, strict=True):
      if hypot(state.x_m - point[0], state.y_m - point[1]) > 1.0e-10:
        raise ValueError('edge states must lie on edge points')
    for name in (
      'geometry_residuals',
      'compatibility_residuals',
      'pressure_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if len(values) != len(points) - 1:
        raise ValueError(f'{name} must match the edge segment count')
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must be finite and nonnegative')
      object.__setattr__(self, name, values)
    if hypot(
      self.start_state.x_m - points[0][0],
      self.start_state.y_m - points[0][1],
    ) > 1.0e-10 or hypot(
      self.end_state.x_m - points[-1][0],
      self.end_state.y_m - points[-1][1],
    ) > 1.0e-10:
      raise ValueError('edge endpoints must match the trace endpoints')
    object.__setattr__(self, 'points_xr_m', points)
    object.__setattr__(self, 'states', states)
    object.__setattr__(self, 'total_pressure_Pa', pressures)

  @property
  def maximum_geometry_residual(self) -> float:
    return max(self.geometry_residuals, default=0.0)

  @property
  def maximum_compatibility_residual(self) -> float:
    return max(self.compatibility_residuals, default=0.0)

  @property
  def maximum_pressure_residual(self) -> float:
    return max(self.pressure_residuals, default=0.0)

  def as_report(self) -> dict[str, Any]:
    return {
      'edge_index': self.edge_index,
      'family': self.family.value,
      'start_point_m': [self.start_state.x_m, self.start_state.y_m],
      'end_point_m': [self.end_state.x_m, self.end_state.y_m],
      'point_count': len(self.points_xr_m),
      'points_xr_m': [list(point) for point in self.points_xr_m],
      'start_total_pressure_Pa': self.start_total_pressure_Pa,
      'end_total_pressure_Pa': self.end_total_pressure_Pa,
      'total_pressure_Pa': list(self.total_pressure_Pa),
      'geometry_residuals': list(self.geometry_residuals),
      'compatibility_residuals': list(self.compatibility_residuals),
      'pressure_residuals': list(self.pressure_residuals),
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection:
  """One solver-owned interior C+/C- characteristic intersection."""

  intersection_index: int
  parent_cell_index: int
  plus_source_row_index: int
  minus_source_row_index: int
  plus_source: CharacteristicState
  minus_source: CharacteristicState
  state: CharacteristicState
  plus_source_total_pressure_Pa: float
  minus_source_total_pressure_Pa: float
  plus_total_pressure_Pa: float
  minus_total_pressure_Pa: float
  total_pressure_Pa: float
  plus_geometry_residual: float
  minus_geometry_residual: float
  plus_compatibility_residual: float
  minus_compatibility_residual: float
  plus_pressure_residual: float
  minus_pressure_residual: float
  plus_forward_direction_sign: int
  minus_forward_direction_sign: int
  plus_forward_margin_m: float
  minus_forward_margin_m: float

  def __post_init__(self) -> None:
    if (
      isinstance(self.intersection_index, bool)
      or not isinstance(self.intersection_index, int)
      or self.intersection_index < 0
    ):
      raise ValueError('intersection_index must be a nonnegative integer')
    for name in (
      'parent_cell_index',
      'plus_source_row_index',
      'minus_source_row_index',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if (
      self.plus_source_row_index >= 4
      or self.minus_source_row_index >= 4
      or self.plus_source_row_index >= self.minus_source_row_index
    ):
      raise ValueError(
        'intersection source row indices must be ordered values below four'
      )
    for name in ('plus_source', 'minus_source', 'state'):
      if not isinstance(getattr(self, name), CharacteristicState):
        raise TypeError(f'{name} must be a CharacteristicState')
    for name in ('plus_forward_direction_sign', 'minus_forward_direction_sign'):
      value = getattr(self, name)
      if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value not in (-1, 1)
      ):
        raise ValueError(f'{name} must be either -1 or 1')
    for name in (
      'plus_source_total_pressure_Pa',
      'minus_source_total_pressure_Pa',
      'plus_total_pressure_Pa',
      'minus_total_pressure_Pa',
      'total_pressure_Pa',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    for name in (
      'plus_geometry_residual',
      'minus_geometry_residual',
      'plus_compatibility_residual',
      'minus_compatibility_residual',
      'plus_pressure_residual',
      'minus_pressure_residual',
      'plus_forward_margin_m',
      'minus_forward_margin_m',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      object.__setattr__(self, name, value)
    if (
      hypot(
        self.plus_source.x_m - self.state.x_m,
        self.plus_source.y_m - self.state.y_m,
      ) <= 0.0
      or hypot(
        self.minus_source.x_m - self.state.x_m,
        self.minus_source.y_m - self.state.y_m,
      ) <= 0.0
    ):
      raise ValueError('intersection state must be distinct from both sources')

  @property
  def maximum_geometry_residual(self) -> float:
    return max(self.plus_geometry_residual, self.minus_geometry_residual)

  @property
  def maximum_compatibility_residual(self) -> float:
    return max(
      self.plus_compatibility_residual,
      self.minus_compatibility_residual,
    )

  @property
  def maximum_pressure_residual(self) -> float:
    return max(self.plus_pressure_residual, self.minus_pressure_residual)

  @property
  def forward_verified(self) -> bool:
    return bool(
      self.plus_forward_margin_m > 0.0
      and self.minus_forward_margin_m > 0.0
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'intersection_index': self.intersection_index,
      'parent_cell_index': self.parent_cell_index,
      'plus_source_row_index': self.plus_source_row_index,
      'minus_source_row_index': self.minus_source_row_index,
      'plus_source_point_m': [self.plus_source.x_m, self.plus_source.y_m],
      'minus_source_point_m': [self.minus_source.x_m, self.minus_source.y_m],
      'point_m': [self.state.x_m, self.state.y_m],
      'theta_rad': self.state.theta_rad,
      'mach': self.state.mach,
      'plus_source_total_pressure_Pa': self.plus_source_total_pressure_Pa,
      'minus_source_total_pressure_Pa': self.minus_source_total_pressure_Pa,
      'plus_total_pressure_Pa': self.plus_total_pressure_Pa,
      'minus_total_pressure_Pa': self.minus_total_pressure_Pa,
      'total_pressure_Pa': self.total_pressure_Pa,
      'plus_geometry_residual': self.plus_geometry_residual,
      'minus_geometry_residual': self.minus_geometry_residual,
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'plus_compatibility_residual': self.plus_compatibility_residual,
      'minus_compatibility_residual': self.minus_compatibility_residual,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'plus_pressure_residual': self.plus_pressure_residual,
      'minus_pressure_residual': self.minus_pressure_residual,
      'plus_forward_direction_sign': self.plus_forward_direction_sign,
      'minus_forward_direction_sign': self.minus_forward_direction_sign,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'plus_forward_margin_m': self.plus_forward_margin_m,
      'minus_forward_margin_m': self.minus_forward_margin_m,
      'forward_verified': self.forward_verified,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult:
  """A locally solved continuation remesh below physical shock-cell closure."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
  source_continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult | None
  subdivision_side_count: int
  cells: tuple[MocCharacteristicCell, ...]
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...]
  characteristic_edges: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge, ...
  ]
  interior_characteristic_intersections: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection, ...
  ]
  topology: MocTopologyResult
  source_pressure_gradient: tuple[float, float] | None
  maximum_geometry_residual: float | None
  maximum_compatibility_residual: float | None
  maximum_pressure_residual: float | None
  maximum_intersection_geometry_residual: float | None
  maximum_intersection_compatibility_residual: float | None
  maximum_intersection_pressure_residual: float | None
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  pressure_lineage_carried: bool
  continuation_boundary_verified: bool
  topology_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  interior_characteristic_rows_required: bool = False
  interior_characteristic_intersections_verified: bool = False
  interior_characteristic_closure_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  position_tolerance_m: float = 1.0e-8
  characteristic_residual_tolerance: float = 1.0e-6
  pressure_lineage_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  maximum_iterations: int = 48
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus,
    ):
      raise TypeError('status must be a continuation-remesh status')
    if self.source_continuation is not None and not isinstance(
      self.source_continuation,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ):
      raise TypeError('source_continuation must be typed or None')
    if (
      isinstance(self.subdivision_side_count, bool)
      or not isinstance(self.subdivision_side_count, int)
      or self.subdivision_side_count < 1
    ):
      raise ValueError('subdivision_side_count must be a positive integer')
    cells = tuple(self.cells)
    samples = tuple(self.cell_samples)
    edges = tuple(self.characteristic_edges)
    if len(cells) != len(samples):
      raise ValueError('cells and cell_samples must have equal lengths')
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError('cells must contain MocCharacteristicCell values')
    if any(
      not isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      for sample in samples
    ):
      raise TypeError('cell_samples must contain typed cell samples')
    if any(
      not isinstance(
        edge,
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge,
      )
      for edge in edges
    ):
      raise TypeError('characteristic_edges must contain typed edge traces')
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'cell_samples', samples)
    object.__setattr__(self, 'characteristic_edges', edges)
    intersections = tuple(self.interior_characteristic_intersections)
    if any(
      not isinstance(
        intersection,
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection,
      )
      for intersection in intersections
    ):
      raise TypeError(
        'interior_characteristic_intersections must contain typed intersections'
      )
    object.__setattr__(self, 'interior_characteristic_intersections', intersections)
    if self.source_pressure_gradient is not None:
      gradient = tuple(float(value) for value in self.source_pressure_gradient)
      if len(gradient) != 2 or not all(isfinite(value) for value in gradient):
        raise ValueError('source_pressure_gradient must contain finite values')
      object.__setattr__(self, 'source_pressure_gradient', gradient)
    for name in (
      'maximum_geometry_residual',
      'maximum_compatibility_residual',
      'maximum_pressure_residual',
      'maximum_intersection_geometry_residual',
      'maximum_intersection_compatibility_residual',
      'maximum_intersection_pressure_residual',
      'maximum_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        object.__setattr__(self, name, numeric)
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if len(residuals) != len(cells) or any(
      not isfinite(value) or value < 0.0 for value in residuals
    ):
      raise ValueError('cell_euler_residuals must match finite cells')
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    for name in (
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'pressure_lineage_carried',
      'continuation_boundary_verified',
      'topology_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'interior_characteristic_rows_required',
      'interior_characteristic_intersections_verified',
      'interior_characteristic_closure_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.interior_characteristic_closure_verified:
      raise ValueError('this bounded remesh cannot claim interior closure')
    if (
      self.interior_characteristic_intersections_verified
      and not self.interior_characteristic_rows_required
    ):
      raise ValueError(
        'interior characteristic intersections require interior rows'
      )
    if self.physical_closure_verified:
      raise ValueError('continuation remesh cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError('continuation remesh must retain the promotion block')
    if self.production_claim_allowed:
      raise ValueError('continuation remesh cannot claim production validity')
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'pressure_lineage_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
      .CONVERGED_LOCAL_CHARACTERISTIC_REMESH
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

  @property
  def diagnostic_sampling_available(self) -> bool:
    """Whether this bounded remesh can serve a diagnostic source callback.

    This sampler is intentionally distinct from the production field
    ``state_sampling_available`` contract.  The remesh can be locally
    characteristic while its conservative Euler residual remains above the
    acceptance gate, so these samples may be used only to probe whether a
    later reflected/free-boundary solve stays inside the retained band.
    """

    return bool(
      self.local_characteristic_remesh_verified
      and self.cells
      and len(self.cell_samples) == len(self.cells)
    )

  def _diagnostic_weights_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float,
  ) -> tuple[tuple[float, float, float], MocEulerAmbientFirstWedgeCellSample] | None:
    if not self.diagnostic_sampling_available:
      return None
    try:
      point = (float(point_m[0]), float(point_m[1]))
      tolerance = float(position_tolerance_m)
    except (IndexError, TypeError, ValueError):
      return None
    if not all(isfinite(value) for value in point):
      return None
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

  def diagnostic_state_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> CharacteristicState | None:
    """Interpolate a state only inside this bounded diagnostic remesh."""

    sampled = self._diagnostic_weights_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    weights, sample = sampled
    try:
      point = (float(point_m[0]), float(point_m[1]))
    except (IndexError, TypeError, ValueError):
      return None
    theta = sum(
      weight * state.theta_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    nu = sum(
      weight * state.nu_rad
      for weight, state in zip(weights, sample.states, strict=True)
    )
    inversion = inverse_prandtl_meyer_angle_rad(nu, sample.states[0].gamma)
    if not inversion.converged or inversion.value is None:
      return None
    return CharacteristicState(
      x_m=point[0],
      y_m=point[1],
      theta_rad=theta,
      mach=inversion.value,
      gamma=sample.states[0].gamma,
    )

  def diagnostic_total_pressure_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> float | None:
    """Interpolate carried total pressure inside the diagnostic remesh."""

    sampled = self._diagnostic_weights_at(
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

  def diagnostic_static_pressure_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> float | None:
    """Return isentropic static pressure for a bounded diagnostic sample."""

    state = self.diagnostic_state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    total_pressure = self.diagnostic_total_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or total_pressure is None:
      return None
    return total_pressure / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))

  @property
  def local_characteristic_remesh_verified(self) -> bool:
    return bool(
      self.converged
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.pressure_lineage_carried
      and self.continuation_boundary_verified
      and self.topology_verified
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
      and self.cell_euler_residuals_finite
      and (
        not self.interior_characteristic_rows_required
        or self.interior_characteristic_intersections_verified
      )
      and not self.interior_characteristic_closure_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  @property
  def continuation_boundary_kind(self) -> MocChainBoundaryKind:
    return MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER

  @property
  def continuation_boundary(self):
    if self.source_continuation is None:
      return ()
    return self.source_continuation.continuation_boundary

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
        .INVALID_INPUT
      )
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    next_gate = (
      'reflected-free-boundary-shock-closure-and-independent-euler-'
      'validation-before-continued-shock-cell-chain'
      if self.interior_characteristic_intersections_verified
      else 'interior-variable-entropy-characteristic-rows-and-reflected-'
      'free-boundary-shock-closure'
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'solver-owned continuation remesh is locally characteristic but has '
        'no globally closed reflected free-boundary shock, conservative Euler '
        'acceptance, or external validation; physical promotion remains blocked'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'continuation_remesh_status': self.status.value,
        'subdivision_side_count': self.subdivision_side_count,
        'cell_count': self.cell_count,
        'characteristic_edge_count': len(self.characteristic_edges),
        'state_sample_count': self.state_sample_count,
        'maximum_geometry_residual': self.maximum_geometry_residual,
        'maximum_compatibility_residual': self.maximum_compatibility_residual,
        'maximum_pressure_residual': self.maximum_pressure_residual,
        'maximum_intersection_geometry_residual': (
          self.maximum_intersection_geometry_residual
        ),
        'maximum_intersection_compatibility_residual': (
          self.maximum_intersection_compatibility_residual
        ),
        'maximum_intersection_pressure_residual': (
          self.maximum_intersection_pressure_residual
        ),
        'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'interior_characteristic_rows_required': (
          self.interior_characteristic_rows_required
        ),
        'interior_characteristic_intersections_verified': (
          self.interior_characteristic_intersections_verified
        ),
        'interior_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'physical_chain_cell_count': 0,
        'external_validation_required': True,
        'required_next_gate': next_gate,
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_characteristic_remesh_verified': (
        self.local_characteristic_remesh_verified
      ),
      'continuation_boundary_kind': self.continuation_boundary_kind.value,
      'continuation_boundary_verified': self.continuation_boundary_verified,
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'characteristic_edge_count': len(self.characteristic_edges),
      'state_sample_count': self.state_sample_count,
      'maximum_geometry_residual': self.maximum_geometry_residual,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'maximum_pressure_residual': self.maximum_pressure_residual,
      'maximum_intersection_geometry_residual': (
        self.maximum_intersection_geometry_residual
      ),
      'maximum_intersection_compatibility_residual': (
        self.maximum_intersection_compatibility_residual
      ),
      'maximum_intersection_pressure_residual': (
        self.maximum_intersection_pressure_residual
      ),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'characteristic_edges': [
        edge.as_report() for edge in self.characteristic_edges
      ],
      'interior_characteristic_intersections': [
        intersection.as_report()
        for intersection in self.interior_characteristic_intersections
      ],
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'checks': {
        'characteristic_geometry_verified': self.characteristic_geometry_verified,
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'topology_verified': self.topology_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'interior_characteristic_rows_required': (
          self.interior_characteristic_rows_required
        ),
        'interior_characteristic_intersections_verified': (
          self.interior_characteristic_intersections_verified
        ),
        'interior_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'source_continuation_status': (
        None
        if self.source_continuation is None
        else self.source_continuation.status.value
      ),
      'source_pressure_gradient': (
        None
        if self.source_pressure_gradient is None
        else list(self.source_pressure_gradient)
      ),
      'external_validation_required': True,
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'maximum_iterations': self.maximum_iterations,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class _EdgeSolve:
  points: tuple[tuple[float, float], ...]
  states: tuple[CharacteristicState, ...]
  pressures: tuple[float, ...]
  geometry_residuals: tuple[float, ...]
  compatibility_residuals: tuple[float, ...]
  pressure_residuals: tuple[float, ...]


def _edge_key(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
) -> tuple[tuple[float, float], tuple[float, float], str]:
  return (
    (round(start.x_m, 12), round(start.y_m, 12)),
    (round(end.x_m, 12), round(end.y_m, 12)),
    family.value,
  )


def _reverse_edge(edge: _EdgeSolve) -> _EdgeSolve:
  return _EdgeSolve(
    points=tuple(reversed(edge.points)),
    states=tuple(reversed(edge.states)),
    pressures=tuple(reversed(edge.pressures)),
    geometry_residuals=tuple(reversed(edge.geometry_residuals)),
    compatibility_residuals=tuple(reversed(edge.compatibility_residuals)),
    pressure_residuals=tuple(reversed(edge.pressure_residuals)),
  )


def _boundary_state(
  first: CharacteristicState,
  second: CharacteristicState,
  first_pressure: float,
  second_pressure: float,
  fraction: float,
) -> tuple[tuple[float, float], CharacteristicState, float]:
  point = (
    first.x_m + fraction * (second.x_m - first.x_m),
    first.y_m + fraction * (second.y_m - first.y_m),
  )
  theta = first.theta_rad + fraction * (second.theta_rad - first.theta_rad)
  nu = first.nu_rad + fraction * (second.nu_rad - first.nu_rad)
  inversion = inverse_prandtl_meyer_angle_rad(nu, first.gamma)
  if not inversion.converged or inversion.value is None:
    raise ValueError('boundary remesh state left the supersonic Mach domain')
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=theta,
    mach=inversion.value,
    gamma=first.gamma,
  )
  pressure = exp(
    (1.0 - fraction) * log(first_pressure) + fraction * log(second_pressure)
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('boundary remesh pressure was not positive')
  return point, state, pressure


def _triangle_interpolation_weights(
  point: tuple[float, float],
  vertices: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> tuple[float, float, float] | None:
  """Return barycentric weights for a bounded nondegenerate triangle."""

  if len(vertices) != 3:
    return None
  (ax, ay), (bx, by), (cx, cy) = vertices
  denominator = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
  if not isfinite(denominator) or abs(denominator) <= max(
    tolerance_m * tolerance_m,
    1.0e-24,
  ):
    return None
  px, py = point
  first = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
  second = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10:
    return None
  if max(first, second, third) > 1.0 + 1.0e-10:
    return None
  return first, second, third


def _solve_edge(
  start: CharacteristicState,
  end: CharacteristicState,
  start_pressure: float,
  end_pressure: float,
  family: CharacteristicFamily,
  side_count: int,
  gradient: tuple[float, float],
  *,
  characteristic_residual_tolerance: float,
  pressure_lineage_tolerance: float,
  maximum_iterations: int,
) -> _EdgeSolve:
  def compatibility(
    first: CharacteristicState,
    second: CharacteristicState,
  ) -> float:
    actual = (
      second.k_plus
      if family is CharacteristicFamily.PLUS
      else second.k_minus
    )
    initial = (
      first.k_plus if family is CharacteristicFamily.PLUS else first.k_minus
    )
    return actual - initial - _compatibility_source(first, second, gradient)

  if side_count == 1:
    geometry_residual = abs(
      _characteristic_geometry_residual(start, end, family)
    )
    compatibility_residual = abs(compatibility(start, end))
    transported_pressure = _transport_total_pressure(
      start,
      start_pressure,
      (end.x_m, end.y_m),
      gradient,
    )
    pressure_residual = abs(log(end_pressure / transported_pressure))
    if geometry_residual > characteristic_residual_tolerance:
      raise ValueError(
        'characteristic edge geometry residual exceeded tolerance'
      )
    if compatibility_residual > characteristic_residual_tolerance:
      raise ValueError(
        'characteristic edge compatibility residual exceeded tolerance'
      )
    if pressure_residual > pressure_lineage_tolerance:
      raise ValueError(
        'characteristic edge pressure-lineage residual exceeded tolerance'
      )
    return _EdgeSolve(
      points=((start.x_m, start.y_m), (end.x_m, end.y_m)),
      states=(start, end),
      pressures=(float(start_pressure), float(end_pressure)),
      geometry_residuals=(geometry_residual,),
      compatibility_residuals=(compatibility_residual,),
      pressure_residuals=(pressure_residual,),
    )
  if side_count == 4:
    midpoint_edge = _solve_edge(
      start,
      end,
      start_pressure,
      end_pressure,
      family,
      2,
      gradient,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      maximum_iterations=maximum_iterations,
    )
    midpoint = midpoint_edge.states[1]
    midpoint_pressure = midpoint_edge.pressures[1]
    first_edge = _solve_edge(
      start,
      midpoint,
      start_pressure,
      midpoint_pressure,
      family,
      2,
      gradient,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      maximum_iterations=maximum_iterations,
    )
    second_edge = _solve_edge(
      midpoint,
      end,
      midpoint_pressure,
      end_pressure,
      family,
      2,
      gradient,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      maximum_iterations=maximum_iterations,
    )
    return _EdgeSolve(
      points=first_edge.points + second_edge.points[1:],
      states=first_edge.states + second_edge.states[1:],
      pressures=first_edge.pressures + second_edge.pressures[1:],
      geometry_residuals=(
        first_edge.geometry_residuals + second_edge.geometry_residuals
      ),
      compatibility_residuals=(
        first_edge.compatibility_residuals
        + second_edge.compatibility_residuals
      ),
      pressure_residuals=(
        first_edge.pressure_residuals + second_edge.pressure_residuals
      ),
    )
  if side_count != 2:
    raise ValueError(
      'the bounded characteristic remesh currently supports one, two, or '
      'four edge intervals'
    )
  _midpoint, midpoint_guess, _midpoint_pressure = _boundary_state(
    start,
    end,
    start_pressure,
    end_pressure,
    0.5,
  )

  def residual(vector: Sequence[float]) -> tuple[float, float, float, float]:
    candidate = CharacteristicState(
      x_m=float(vector[0]),
      y_m=float(vector[1]),
      theta_rad=float(vector[2]),
      mach=float(vector[3]),
      gamma=start.gamma,
    )
    return (
      _characteristic_geometry_residual(start, candidate, family),
      _characteristic_geometry_residual(candidate, end, family),
      compatibility(start, candidate),
      compatibility(candidate, end),
    )

  try:
    solved = least_squares(
      residual,
      (
        midpoint_guess.x_m,
        midpoint_guess.y_m,
        midpoint_guess.theta_rad,
        midpoint_guess.mach,
      ),
      bounds=(
        (
          min(start.x_m, end.x_m) - 100.0,
          min(start.y_m, end.y_m) - 100.0,
          -3.0,
          1.0001,
        ),
        (
          max(start.x_m, end.x_m) + 100.0,
          max(start.y_m, end.y_m) + 100.0,
          3.0,
          64.0,
        ),
      ),
      max_nfev=max(128, maximum_iterations * 32),
      xtol=1.0e-13,
      ftol=1.0e-13,
      gtol=1.0e-13,
      x_scale='jac',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    raise ValueError(f'characteristic edge solve failed: {error}') from error
  candidate = CharacteristicState(
    x_m=float(solved.x[0]),
    y_m=float(solved.x[1]),
    theta_rad=float(solved.x[2]),
    mach=float(solved.x[3]),
    gamma=start.gamma,
  )
  residuals = residual(solved.x)
  geometry_residuals = (
    abs(residuals[0]),
    abs(residuals[1]),
  )
  compatibility_residuals = (
    abs(residuals[2]),
    abs(residuals[3]),
  )
  start_transport = _transport_total_pressure(
    start,
    start_pressure,
    (candidate.x_m, candidate.y_m),
    gradient,
  )
  end_transport = _transport_total_pressure(
    end,
    end_pressure,
    (candidate.x_m, candidate.y_m),
    gradient,
  )
  candidate_pressure = exp(0.5 * (log(start_transport) + log(end_transport)))
  pressure_residuals = (
    abs(log(candidate_pressure / start_transport)),
    abs(log(candidate_pressure / end_transport)),
  )
  maximum_characteristic_residual = max(
    *geometry_residuals,
    *compatibility_residuals,
  )
  if maximum_characteristic_residual > characteristic_residual_tolerance:
    raise ValueError(
      'characteristic edge geometry or compatibility residual exceeded '
      f'tolerance ({maximum_characteristic_residual})'
    )
  # A bounded least-squares solve can exhaust its evaluation budget after
  # reaching a useful root because the two segment compatibility equations
  # are only locally additive.  The explicit residual gate above is the
  # acceptance criterion for this short diagnostic boundary solve.
  if max(pressure_residuals) > pressure_lineage_tolerance:
    raise ValueError(
      'characteristic edge pressure-lineage residual exceeded tolerance'
    )
  return _EdgeSolve(
    points=(
      (start.x_m, start.y_m),
      (candidate.x_m, candidate.y_m),
      (end.x_m, end.y_m),
    ),
    states=(start, candidate, end),
    pressures=(float(start_pressure), candidate_pressure, float(end_pressure)),
    geometry_residuals=geometry_residuals,
    compatibility_residuals=compatibility_residuals,
    pressure_residuals=pressure_residuals,
  )


def _forward_margin_m(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
  direction_sign: int,
) -> float:
  """Return the downstream row-direction projection for a characteristic."""

  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  direction = start.direction(family)
  return float(direction_sign) * (
    displacement[0] * direction[0] + displacement[1] * direction[1]
  )


def _solve_interior_intersection(
  intersection_index: int,
  parent_cell_index: int,
  plus_source_row_index: int,
  minus_source_row_index: int,
  plus_source: CharacteristicState,
  minus_source: CharacteristicState,
  plus_pressure: float,
  minus_pressure: float,
  gradient: tuple[float, float],
  *,
  plus_forward_direction_sign: int,
  minus_forward_direction_sign: int,
  position_tolerance_m: float,
  characteristic_residual_tolerance: float,
  pressure_lineage_tolerance: float,
  maximum_iterations: int,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection:
  """Solve a forward C+/C- crossing from two base-row source states."""

  _point, boundary_guess, _guess_pressure = _boundary_state(
    plus_source,
    minus_source,
    plus_pressure,
    minus_pressure,
    0.5,
  )
  source_span = hypot(
    minus_source.x_m - plus_source.x_m,
    minus_source.y_m - plus_source.y_m,
  )
  plus_direction = plus_source.direction(CharacteristicFamily.PLUS)
  minus_direction = minus_source.direction(CharacteristicFamily.MINUS)
  row_direction = (
    plus_forward_direction_sign * plus_direction[0]
    + minus_forward_direction_sign * minus_direction[0],
    plus_forward_direction_sign * plus_direction[1]
    + minus_forward_direction_sign * minus_direction[1],
  )
  guess = CharacteristicState(
    x_m=boundary_guess.x_m + 0.25 * source_span * row_direction[0],
    y_m=boundary_guess.y_m + 0.25 * source_span * row_direction[1],
    theta_rad=boundary_guess.theta_rad,
    mach=boundary_guess.mach,
    gamma=boundary_guess.gamma,
  )

  def compatibility(
    first: CharacteristicState,
    second: CharacteristicState,
    family: CharacteristicFamily,
  ) -> float:
    actual = (
      second.k_plus
      if family is CharacteristicFamily.PLUS
      else second.k_minus
    )
    initial = (
      first.k_plus if family is CharacteristicFamily.PLUS else first.k_minus
    )
    return actual - initial - _compatibility_source(first, second, gradient)

  def residual(vector: Sequence[float]) -> tuple[float, float, float, float]:
    candidate = CharacteristicState(
      x_m=float(vector[0]),
      y_m=float(vector[1]),
      theta_rad=float(vector[2]),
      mach=float(vector[3]),
      gamma=plus_source.gamma,
    )
    return (
      _characteristic_geometry_residual(
        plus_source,
        candidate,
        CharacteristicFamily.PLUS,
      ),
      _characteristic_geometry_residual(
        minus_source,
        candidate,
        CharacteristicFamily.MINUS,
      ),
      compatibility(plus_source, candidate, CharacteristicFamily.PLUS),
      compatibility(minus_source, candidate, CharacteristicFamily.MINUS),
    )

  try:
    solved = least_squares(
      residual,
      (guess.x_m, guess.y_m, guess.theta_rad, guess.mach),
      bounds=(
        (
          min(plus_source.x_m, minus_source.x_m) - 100.0,
          min(plus_source.y_m, minus_source.y_m) - 100.0,
          -3.0,
          1.0001,
        ),
        (
          max(plus_source.x_m, minus_source.x_m) + 100.0,
          max(plus_source.y_m, minus_source.y_m) + 100.0,
          3.0,
          64.0,
        ),
      ),
      max_nfev=max(128, maximum_iterations * 32),
      xtol=1.0e-13,
      ftol=1.0e-13,
      gtol=1.0e-13,
      x_scale='jac',
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    raise ValueError(f'interior characteristic intersection failed: {error}') from error
  candidate = CharacteristicState(
    x_m=float(solved.x[0]),
    y_m=float(solved.x[1]),
    theta_rad=float(solved.x[2]),
    mach=float(solved.x[3]),
    gamma=plus_source.gamma,
  )
  residuals = residual(solved.x)
  plus_geometry_residual = abs(residuals[0])
  minus_geometry_residual = abs(residuals[1])
  plus_compatibility_residual = abs(residuals[2])
  minus_compatibility_residual = abs(residuals[3])
  maximum_characteristic_residual = max(
    plus_geometry_residual,
    minus_geometry_residual,
    plus_compatibility_residual,
    minus_compatibility_residual,
  )
  if maximum_characteristic_residual > characteristic_residual_tolerance:
    raise ValueError(
      'interior characteristic geometry or compatibility residual exceeded '
      f'tolerance ({maximum_characteristic_residual})'
    )
  plus_transport = _transport_total_pressure(
    plus_source,
    plus_pressure,
    (candidate.x_m, candidate.y_m),
    gradient,
  )
  minus_transport = _transport_total_pressure(
    minus_source,
    minus_pressure,
    (candidate.x_m, candidate.y_m),
    gradient,
  )
  candidate_pressure = exp(
    0.5 * (log(plus_transport) + log(minus_transport))
  )
  plus_pressure_residual = abs(log(candidate_pressure / plus_transport))
  minus_pressure_residual = abs(log(candidate_pressure / minus_transport))
  if max(plus_pressure_residual, minus_pressure_residual) > pressure_lineage_tolerance:
    raise ValueError(
      'interior characteristic pressure-lineage residual exceeded tolerance'
    )
  plus_forward_margin = _forward_margin_m(
    plus_source,
    candidate,
    CharacteristicFamily.PLUS,
    plus_forward_direction_sign,
  )
  minus_forward_margin = _forward_margin_m(
    minus_source,
    candidate,
    CharacteristicFamily.MINUS,
    minus_forward_direction_sign,
  )
  if (
    plus_forward_margin <= position_tolerance_m
    or minus_forward_margin <= position_tolerance_m
  ):
    raise ValueError(
      'interior characteristic intersection is not forward from both sources'
    )
  return MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection(
    intersection_index=intersection_index,
    parent_cell_index=parent_cell_index,
    plus_source_row_index=plus_source_row_index,
    minus_source_row_index=minus_source_row_index,
    plus_source=plus_source,
    minus_source=minus_source,
    state=candidate,
    plus_source_total_pressure_Pa=plus_pressure,
    minus_source_total_pressure_Pa=minus_pressure,
    plus_total_pressure_Pa=plus_transport,
    minus_total_pressure_Pa=minus_transport,
    total_pressure_Pa=candidate_pressure,
    plus_geometry_residual=plus_geometry_residual,
    minus_geometry_residual=minus_geometry_residual,
    plus_compatibility_residual=plus_compatibility_residual,
    minus_compatibility_residual=minus_compatibility_residual,
    plus_pressure_residual=plus_pressure_residual,
    minus_pressure_residual=minus_pressure_residual,
    plus_forward_direction_sign=plus_forward_direction_sign,
    minus_forward_direction_sign=minus_forward_direction_sign,
    plus_forward_margin_m=plus_forward_margin,
    minus_forward_margin_m=minus_forward_margin,
  )


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus,
  source_continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult | None,
  *,
  subdivision_side_count: int = 1,
  cells: Sequence[MocCharacteristicCell] = (),
  samples: Sequence[MocEulerAmbientFirstWedgeCellSample] = (),
  characteristic_edges: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge
  ] = (),
  interior_characteristic_intersections: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection
  ] = (),
  topology: MocTopologyResult | None = None,
  source_pressure_gradient: tuple[float, float] | None = None,
  geometry_residual: float | None = None,
  compatibility_residual: float | None = None,
  pressure_residual: float | None = None,
  intersection_geometry_residual: float | None = None,
  intersection_compatibility_residual: float | None = None,
  intersection_pressure_residual: float | None = None,
  residuals: Sequence[float] = (),
  maximum_residual: float | None = None,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  pressure_lineage_carried: bool = False,
  continuation_boundary_verified: bool = False,
  topology_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  interior_characteristic_rows_required: bool = False,
  interior_characteristic_intersections_verified: bool = False,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-6,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  maximum_iterations: int = 48,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult:
  cells = tuple(cells)
  samples = tuple(samples)
  residual_values = tuple(float(value) for value in residuals)
  if len(residual_values) != len(cells):
    if len(samples) == len(cells):
      try:
        residual_values = tuple(
          _cell_euler_residual(
            sample.vertices_xr_m,
            sample.states,
            sample.total_pressure_Pa,
          )
          for sample in samples
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        residual_values = (0.0,) * len(cells)
    else:
      residual_values = (0.0,) * len(cells)
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult(
    status=status,
    source_continuation=source_continuation,
    subdivision_side_count=subdivision_side_count,
    cells=cells,
    cell_samples=samples,
    characteristic_edges=tuple(characteristic_edges),
    interior_characteristic_intersections=tuple(
      interior_characteristic_intersections
    ),
    topology=validate_moc_mesh(()) if topology is None else topology,
    source_pressure_gradient=source_pressure_gradient,
    maximum_geometry_residual=geometry_residual,
    maximum_compatibility_residual=compatibility_residual,
    maximum_pressure_residual=pressure_residual,
    maximum_intersection_geometry_residual=intersection_geometry_residual,
    maximum_intersection_compatibility_residual=(
      intersection_compatibility_residual
    ),
    maximum_intersection_pressure_residual=intersection_pressure_residual,
    cell_euler_residuals=residual_values,
    maximum_cell_euler_residual=maximum_residual,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_compatibility_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    continuation_boundary_verified=continuation_boundary_verified,
    topology_verified=topology_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    interior_characteristic_rows_required=interior_characteristic_rows_required,
    interior_characteristic_intersections_verified=(
      interior_characteristic_intersections_verified
    ),
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    maximum_iterations=maximum_iterations,
    message=message,
  )


def remesh_euler_ambient_first_wedge_entropy_characteristic_continuation(
  source_continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  *,
  subdivision_side_count: int = 2,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-6,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  maximum_iterations: int = 48,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult:
  """Solve shared characteristic edge traces on each continuation triangle."""

  status_type = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
  )
  if not isinstance(
    source_continuation,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      None,
      message='source_continuation must be a typed continuation result',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    characteristic_tolerance = float(characteristic_residual_tolerance)
    pressure_tolerance = float(pressure_lineage_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      status_type.INVALID_INPUT,
      source_continuation,
      message='continuation remesh tolerances must be numeric',
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      characteristic_tolerance,
      pressure_tolerance,
      cell_tolerance,
    )
  ):
    raise ValueError('continuation remesh tolerances must be positive')
  if (
    isinstance(subdivision_side_count, bool)
    or not isinstance(subdivision_side_count, int)
    or subdivision_side_count not in (1, 2, 4)
  ):
    raise ValueError(
      'subdivision_side_count must be one, two, or four for the bounded '
      'characteristic remesh'
    )
  if (
    isinstance(maximum_iterations, bool)
    or not isinstance(maximum_iterations, int)
    or maximum_iterations < 1
  ):
    raise ValueError('maximum_iterations must be a positive integer')
  common = {
    'subdivision_side_count': subdivision_side_count,
    'position_tolerance_m': position_tolerance,
    'characteristic_residual_tolerance': characteristic_tolerance,
    'pressure_lineage_tolerance': pressure_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'maximum_iterations': maximum_iterations,
  }
  if not (
    source_continuation.converged
    and source_continuation.local_consistency_verified
    and source_continuation.cell_samples
    and source_continuation.source_pressure_gradient is not None
  ):
    return _failure(
      status_type.SOURCE_REQUIRED,
      source_continuation,
      message=(
        'characteristic remesh requires a converged locally consistent '
        'continuation with source cells and pressure gradient'
      ),
      **common,
    )
  gradient = source_continuation.source_pressure_gradient
  assert gradient is not None
  edge_cache: dict[
    tuple[tuple[float, float], tuple[float, float], str],
    _EdgeSolve,
  ] = {}
  edge_values: list[MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge] = []
  intersections: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection
  ] = []
  cells: list[MocCharacteristicCell] = []
  samples: list[MocEulerAmbientFirstWedgeCellSample] = []
  try:
    for parent_index, parent in enumerate(source_continuation.cell_samples):
      if len(parent.vertices_xr_m) != 3:
        raise ValueError(f'parent cell {parent_index} is not triangular')
      even = parent_index % 2 == 0
      base_indices = (0, 1, 2) if even else (1, 2, 0)
      states = tuple(parent.states[index] for index in base_indices)
      pressures = tuple(
        float(parent.total_pressure_Pa[index]) for index in base_indices
      )
      base_start, base_end, apex = states
      base_start_pressure, base_end_pressure, apex_pressure = pressures
      if even:
        edge_specs = (
          (
            states[0],
            states[2],
            pressures[0],
            pressures[2],
            CharacteristicFamily.PLUS,
          ),
          (
            states[2],
            states[1],
            pressures[2],
            pressures[1],
            CharacteristicFamily.MINUS,
          ),
        )
      else:
        edge_specs = (
          (
            states[2],
            states[0],
            pressures[2],
            pressures[0],
            CharacteristicFamily.PLUS,
          ),
          (
            states[1],
            states[2],
            pressures[1],
            pressures[2],
            CharacteristicFamily.MINUS,
          ),
        )
      local_edges: list[_EdgeSolve] = []
      for edge_start, edge_end, edge_start_pressure, edge_end_pressure, family in edge_specs:
        direct_key = _edge_key(edge_start, edge_end, family)
        reverse_key = _edge_key(edge_end, edge_start, family)
        if direct_key in edge_cache:
          solved_edge = edge_cache[direct_key]
        elif reverse_key in edge_cache:
          solved_edge = _reverse_edge(edge_cache[reverse_key])
        else:
          solved_edge = _solve_edge(
            edge_start,
            edge_end,
            edge_start_pressure,
            edge_end_pressure,
            family,
            subdivision_side_count,
            gradient,
            characteristic_residual_tolerance=characteristic_tolerance,
            pressure_lineage_tolerance=pressure_tolerance,
            maximum_iterations=maximum_iterations,
          )
          edge_cache[direct_key] = solved_edge
          edge_values.append(
            MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge(
              edge_index=len(edge_values),
              family=family,
              start_state=edge_start,
              end_state=edge_end,
              start_total_pressure_Pa=edge_start_pressure,
              end_total_pressure_Pa=edge_end_pressure,
              points_xr_m=solved_edge.points,
              states=solved_edge.states,
              total_pressure_Pa=solved_edge.pressures,
              geometry_residuals=solved_edge.geometry_residuals,
              compatibility_residuals=solved_edge.compatibility_residuals,
              pressure_residuals=solved_edge.pressure_residuals,
            )
          )
        local_edges.append(solved_edge)
      if even:
        left_edge, right_edge = local_edges[0], _reverse_edge(local_edges[1])
      else:
        left_edge, right_edge = _reverse_edge(local_edges[0]), local_edges[1]
      base_row = [
        _boundary_state(
          base_start,
          base_end,
          base_start_pressure,
          base_end_pressure,
          index / subdivision_side_count,
        )
        for index in range(subdivision_side_count + 1)
      ]
      if subdivision_side_count == 1:
        rows = [
          base_row,
          [
            (
              (apex.x_m, apex.y_m),
              apex,
              apex_pressure,
            )
          ],
        ]
      elif subdivision_side_count == 2:
        rows = [
          base_row,
          [
            (
              left_edge.points[1],
              left_edge.states[1],
              left_edge.pressures[1],
            ),
            (
              right_edge.points[1],
              right_edge.states[1],
              right_edge.pressures[1],
            ),
          ],
          [
            (
              (apex.x_m, apex.y_m),
              apex,
              apex_pressure,
            )
          ],
        ]
      else:
        intersection_by_pair: dict[
          tuple[int, int],
          MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection,
        ] = {}
        for plus_index, minus_index in ((1, 2), (1, 3), (2, 3)):
          intersection = _solve_interior_intersection(
            len(intersections),
            parent_index,
            plus_index,
            minus_index,
            base_row[plus_index][1],
            base_row[minus_index][1],
            base_row[plus_index][2],
            base_row[minus_index][2],
            gradient,
            plus_forward_direction_sign=1 if even else -1,
            minus_forward_direction_sign=-1 if even else 1,
            position_tolerance_m=position_tolerance,
            characteristic_residual_tolerance=characteristic_tolerance,
            pressure_lineage_tolerance=pressure_tolerance,
            maximum_iterations=maximum_iterations,
          )
          intersections.append(intersection)
          intersection_by_pair[(plus_index, minus_index)] = intersection

        def row_item(
          state: CharacteristicState,
          pressure: float,
        ) -> tuple[tuple[float, float], CharacteristicState, float]:
          return ((state.x_m, state.y_m), state, pressure)

        rows = [
          base_row,
          [
            row_item(left_edge.states[1], left_edge.pressures[1]),
            row_item(
              intersection_by_pair[(1, 2)].state,
              intersection_by_pair[(1, 2)].total_pressure_Pa,
            ),
            row_item(
              intersection_by_pair[(1, 3)].state,
              intersection_by_pair[(1, 3)].total_pressure_Pa,
            ),
            row_item(right_edge.states[1], right_edge.pressures[1]),
          ],
          [
            row_item(left_edge.states[2], left_edge.pressures[2]),
            row_item(
              intersection_by_pair[(2, 3)].state,
              intersection_by_pair[(2, 3)].total_pressure_Pa,
            ),
            row_item(right_edge.states[2], right_edge.pressures[2]),
          ],
          [
            row_item(left_edge.states[3], left_edge.pressures[3]),
            row_item(right_edge.states[3], right_edge.pressures[3]),
          ],
          [
            row_item(apex, apex_pressure),
          ],
        ]
      for row_index in range(len(rows) - 1):
        row = rows[row_index]
        next_row = rows[row_index + 1]
        next_count = len(next_row)
        for index in range(next_count):
          triangle = (row[index], row[index + 1], next_row[index])
          cell_vertices = tuple(item[0] for item in triangle)
          cell_states = tuple(item[1] for item in triangle)
          cell_pressures = tuple(item[2] for item in triangle)
          cells.append(
            MocCharacteristicCell(
              cell_index=len(cells),
              cell_kind='entropy-continuation-characteristic-remesh',
              vertices_xr_m=cell_vertices,
              centerline_indices=(),
              boundary_indices=(),
            )
          )
          samples.append(
            MocEulerAmbientFirstWedgeCellSample(
              vertices_xr_m=cell_vertices,
              states=cell_states,
              total_pressure_Pa=cell_pressures,
            )
          )
          if index < next_count - 1:
            triangle = (row[index + 1], next_row[index + 1], next_row[index])
            cell_vertices = tuple(item[0] for item in triangle)
            cell_states = tuple(item[1] for item in triangle)
            cell_pressures = tuple(item[2] for item in triangle)
            cells.append(
              MocCharacteristicCell(
                cell_index=len(cells),
                cell_kind='entropy-continuation-characteristic-remesh',
                vertices_xr_m=cell_vertices,
                centerline_indices=(),
                boundary_indices=(),
              )
            )
            samples.append(
              MocEulerAmbientFirstWedgeCellSample(
                vertices_xr_m=cell_vertices,
                states=cell_states,
                total_pressure_Pa=cell_pressures,
              )
            )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.EDGE_SOLVE_FAILURE,
      source_continuation,
      cells=cells,
      samples=samples,
      characteristic_edges=edge_values,
      interior_characteristic_intersections=intersections,
      source_pressure_gradient=gradient,
      characteristic_geometry_verified=False,
      variable_entropy_compatibility_verified=False,
      pressure_lineage_carried=False,
      continuation_boundary_verified=source_continuation.continuation_boundary_verified,
      interior_characteristic_rows_required=subdivision_side_count > 2,
      interior_characteristic_intersections_verified=False,
      message=f'characteristic continuation remesh failed: {error}',
      **common,
    )
  topology = validate_moc_mesh(tuple(cells))
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _failure(
      status_type.TOPOLOGY_FAILURE,
      source_continuation,
      cells=cells,
      samples=samples,
      characteristic_edges=edge_values,
      interior_characteristic_intersections=intersections,
      topology=topology,
      source_pressure_gradient=gradient,
      topology_verified=False,
      continuation_boundary_verified=source_continuation.continuation_boundary_verified,
      interior_characteristic_rows_required=subdivision_side_count > 2,
      interior_characteristic_intersections_verified=False,
      message=f'characteristic continuation remesh topology failed: {topology.message}',
      **common,
    )
  maximum_geometry = max(
    (edge.maximum_geometry_residual for edge in edge_values),
    default=0.0,
  )
  maximum_compatibility = max(
    (edge.maximum_compatibility_residual for edge in edge_values),
    default=0.0,
  )
  maximum_pressure = max(
    (edge.maximum_pressure_residual for edge in edge_values),
    default=0.0,
  )
  maximum_intersection_geometry = max(
    (intersection.maximum_geometry_residual for intersection in intersections),
    default=None,
  )
  maximum_intersection_compatibility = max(
    (
      intersection.maximum_compatibility_residual
      for intersection in intersections
    ),
    default=None,
  )
  maximum_intersection_pressure = max(
    (intersection.maximum_pressure_residual for intersection in intersections),
    default=None,
  )
  rows_required = subdivision_side_count > 2
  intersections_verified = bool(
    rows_required
    and (
      len(intersections) == 3 * len(source_continuation.cell_samples)
      and all(intersection.forward_verified for intersection in intersections)
      and (
        maximum_intersection_geometry is not None
        and maximum_intersection_geometry <= characteristic_tolerance
      )
      and (
        maximum_intersection_compatibility is not None
        and maximum_intersection_compatibility <= characteristic_tolerance
      )
      and (
        maximum_intersection_pressure is not None
        and maximum_intersection_pressure <= pressure_tolerance
      )
    )
  )
  maximum_geometry = max(
    maximum_geometry,
    maximum_intersection_geometry or 0.0,
  )
  maximum_compatibility = max(
    maximum_compatibility,
    maximum_intersection_compatibility or 0.0,
  )
  maximum_pressure = max(
    maximum_pressure,
    maximum_intersection_pressure or 0.0,
  )
  geometry_verified = bool(
    maximum_geometry <= characteristic_tolerance
    and (not rows_required or intersections_verified)
  )
  compatibility_verified = bool(
    maximum_compatibility <= characteristic_tolerance
    and (not rows_required or intersections_verified)
  )
  pressure_verified = bool(
    maximum_pressure <= pressure_tolerance
    and (not rows_required or intersections_verified)
  )
  lineage_verified = bool(
    pressure_verified
    and source_continuation.pressure_lineage_verified
    and source_continuation.continuation_boundary_verified
  )
  residuals = tuple(
    _cell_euler_residual(
      sample.vertices_xr_m,
      sample.states,
      sample.total_pressure_Pa,
    )
    for sample in samples
  )
  residuals_finite = bool(residuals and all(isfinite(value) for value in residuals))
  maximum_residual = max(residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= cell_tolerance
  )
  continuation_boundary_verified = bool(
    source_continuation.continuation_boundary_verified
    and source_continuation.continuation_boundary
  )
  char_status = (
    status_type.CONVERGED_LOCAL_CHARACTERISTIC_REMESH
    if geometry_verified
    and compatibility_verified
    and lineage_verified
    and continuation_boundary_verified
    else status_type.EDGE_SOLVE_FAILURE
  )
  message = (
    'solver-owned variable-entropy characteristic remesh and local interior '
    'row stencil converged; reflected/free-boundary closure, Euler '
    'conservation acceptance, external validation, and physical chain '
    'promotion remain pending'
    if rows_required
    and intersections_verified
    and char_status is status_type.CONVERGED_LOCAL_CHARACTERISTIC_REMESH
    else 'solver-owned variable-entropy characteristic edge remesh converged; '
    'interior characteristic rows, reflected/free-boundary closure, Euler '
    'conservation acceptance, and physical chain promotion remain pending'
    if char_status is status_type.CONVERGED_LOCAL_CHARACTERISTIC_REMESH
    else 'characteristic continuation remesh failed one or more local edge gates'
  )
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult(
    status=char_status,
    source_continuation=source_continuation,
    subdivision_side_count=subdivision_side_count,
    cells=tuple(cells),
    cell_samples=tuple(samples),
    characteristic_edges=tuple(edge_values),
    interior_characteristic_intersections=tuple(intersections),
    topology=topology,
    source_pressure_gradient=gradient,
    maximum_geometry_residual=maximum_geometry,
    maximum_compatibility_residual=maximum_compatibility,
    maximum_pressure_residual=maximum_pressure,
    maximum_intersection_geometry_residual=maximum_intersection_geometry,
    maximum_intersection_compatibility_residual=(
      maximum_intersection_compatibility
    ),
    maximum_intersection_pressure_residual=maximum_intersection_pressure,
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=maximum_residual,
    characteristic_geometry_verified=geometry_verified,
    variable_entropy_compatibility_verified=compatibility_verified,
    pressure_lineage_carried=lineage_verified,
    continuation_boundary_verified=continuation_boundary_verified,
    topology_verified=topology_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    interior_characteristic_rows_required=rows_required,
    interior_characteristic_intersections_verified=intersections_verified,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=characteristic_tolerance,
    pressure_lineage_tolerance=pressure_tolerance,
    cell_residual_tolerance=cell_tolerance,
    maximum_iterations=maximum_iterations,
    message=message,
  )
