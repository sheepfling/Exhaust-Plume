"""Boundary-conditioned triangular post-shock cell assembly.

This module is the next seam after the diagnostic shrinking-front field.  It
does not choose a shock or invent an outer boundary.  Instead, it consumes a
branch-checked shock boundary and an independently sampled ambient-pressure
outer boundary, couples shock-sourced ``C+`` and ambient-sourced ``C-`` rays
through a triangular net, and
requires the remaining perimeter to reproduce the centerline.  That contract
is suitable for a future free-boundary shooter and cannot silently promote the
existing topological fan.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import cos, hypot, isfinite, sin, sqrt
from typing import TYPE_CHECKING, Any, Callable, Sequence

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientBoundaryStatus,
  MocAmbientPressureBoundaryResult,
  validate_ambient_pressure_boundary,
)
from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockStripResult,
  MocAmbientShockStripStatus,
)
from exhaust_plume.models.moc.chain import (
  MocCellClosureStatus,
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainGeometryFidelity,
  MocChainResult,
  MocChainStatus,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  continue_moc_cell_chain,
  validate_characteristic_trace,
)
from exhaust_plume.models.moc.post_shock import (
  MocShockBoundaryFitResult,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeFieldResult,
  MocMixedRegimePerimeterRequest,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  CharacteristicPointResult,
  MocPrimitiveStatus,
  centerline_characteristic_point,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  assemble_terminal_trace_centerline_patch,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  MocTerminalPatchShockCouplingStatus,
  MocTerminalReflectionPatchShockSolveResult,
  solve_marched_attached_shock_from_terminal_reflection_patch,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

if TYPE_CHECKING:
  from exhaust_plume.models.moc.shock_chain import MocTerminalShockCellFieldResult

__all__ = (
  'MocPhysicalPostShockFieldStatus',
  'MocPhysicalPostShockFieldResult',
  'MocAmbientClosedPostShockChainCandidate',
  'MocPhysicalPostShockFieldContinuationSolve',
  'MocPhysicalPostShockTerminalPatchTransitionResult',
  'assemble_ambient_boundary_post_shock_field',
  'assemble_ambient_boundary_post_shock_field_with_centerline_reflection',
  'solve_ambient_closed_post_shock_terminal_patch_transition',
  'solve_ambient_closed_post_shock_chain_cell_from_physical_field_terminal_patch_or_termination',
  'solve_ambient_closed_post_shock_chain_cell_from_terminal_reflection_patch_ambient_closure_or_termination',
  'solve_ambient_closed_post_shock_chain_cell_from_candidate_or_termination',
  'solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination',
  'continue_ambient_closed_post_shock_chain',
)


class MocPhysicalPostShockFieldStatus(str, Enum):
  """Structured outcome for a coupled shock/outer/centerline cell."""

  CONVERGED_AMBIENT_CLOSED = 'converged_ambient_closed_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_FAILURE = 'shock_boundary_failure'
  AMBIENT_BOUNDARY_FAILURE = 'ambient_boundary_failure'
  GEOMETRY_FAILURE = 'geometry_failure'
  INVARIANT_FAILURE = 'invariant_failure'
  AXIS_FAILURE = 'centerline_closure_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


@dataclass(frozen=True, slots=True)
class MocAmbientClosedPostShockChainCandidate:
  """One explicit next-shock/ambient boundary candidate.

  The candidate owns geometry and the scalar ambient-boundary samples only.
  Upstream states and pressures are deliberately absent: the continued-cell
  solver must sample those from the currently accepted physical field.  This
  makes the object useful for a prescribed-boundary planner fixture without
  allowing the fixture to smuggle a synthetic upstream field into the chain.
  """

  shock_points_m: tuple[tuple[float, float], ...]
  downstream_flow_angles_rad: tuple[float, ...]
  ambient_boundary: tuple[MocAmbientBoundarySample, ...]
  ambient_pressure_Pa: float
  end_x_m: float
  model: str = 'explicit-ambient-closed-next-shock-candidate'

  def __post_init__(self) -> None:
    try:
      shock_points = tuple(
        (float(point[0]), float(point[1]))
        for point in self.shock_points_m
      )
      downstream_angles = tuple(
        float(angle) for angle in self.downstream_flow_angles_rad
      )
      ambient_boundary = tuple(self.ambient_boundary)
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError(
        'shock points, downstream angles, and ambient boundary must be '
        'finite sequences'
      ) from error
    if len(shock_points) < 3:
      raise ValueError(
        'an ambient-closed next-shock candidate requires at least three '
        'shock points'
      )
    if len(shock_points) != len(downstream_angles):
      raise ValueError(
        'shock points and downstream flow angles must have equal lengths'
      )
    if len(ambient_boundary) != len(shock_points):
      raise ValueError(
        'ambient boundary must contain exactly one sample per shock point'
      )
    if any(
      not all(isfinite(value) for value in point)
      for point in shock_points
    ):
      raise ValueError('shock points must contain finite coordinates')
    if any(not isfinite(angle) for angle in downstream_angles):
      raise ValueError('downstream flow angles must be finite')
    if any(
      second[0] <= first[0] or second[1] > first[1]
      for first, second in zip(shock_points, shock_points[1:])
    ):
      raise ValueError(
        'shock points must be strictly downstream and nonincreasing in y'
      )
    if abs(shock_points[-1][1]) > 1.0e-10:
      raise ValueError(
        'the final candidate shock point must lie on the y=0 centerline'
      )
    if any(
      not isinstance(sample, MocAmbientBoundarySample)
      for sample in ambient_boundary
    ):
      raise TypeError(
        'ambient boundary must contain MocAmbientBoundarySample values'
      )
    if (
      abs(ambient_boundary[0].point_m[0] - shock_points[0][0]) > 1.0e-10
      or abs(ambient_boundary[0].point_m[1] - shock_points[0][1]) > 1.0e-10
    ):
      raise ValueError(
        'ambient boundary and candidate shock must share their attachment point'
      )
    try:
      ambient_pressure = float(self.ambient_pressure_Pa)
      end_x = float(self.end_x_m)
    except (TypeError, ValueError) as error:
      raise ValueError(
        'ambient_pressure_Pa and end_x_m must be numeric'
      ) from error
    if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
      raise ValueError('ambient_pressure_Pa must be finite and positive')
    if not isfinite(end_x) or end_x <= shock_points[0][0]:
      raise ValueError(
        'end_x_m must be finite and downstream of the candidate shock start'
      )
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'shock_points_m', shock_points)
    object.__setattr__(self, 'downstream_flow_angles_rad', downstream_angles)
    object.__setattr__(self, 'ambient_boundary', ambient_boundary)
    object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    object.__setattr__(self, 'end_x_m', end_x)
    object.__setattr__(self, 'model', model)
  ####

  @property
  def sample_count(self) -> int:
    """Number of paired shock and ambient-boundary samples."""

    return len(self.shock_points_m)
  ####

  @property
  def shock_start_point_m(self) -> tuple[float, float]:
    """Return the explicit shock/ambient attachment point."""

    return self.shock_points_m[0]
  ####

  @property
  def shock_end_point_m(self) -> tuple[float, float]:
    """Return the explicit centerline endpoint of the candidate shock."""

    return self.shock_points_m[-1]
  ####

  def as_report(self) -> dict[str, Any]:
    """Serialize geometry provenance without duplicating boundary states."""

    return {
      'model': self.model,
      'planning_only': True,
      'production_claim_allowed': False,
      'sample_count': self.sample_count,
      'shock_start_point_m': self.shock_start_point_m,
      'shock_end_point_m': self.shock_end_point_m,
      'shock_points_m': self.shock_points_m,
      'downstream_flow_angles_rad': self.downstream_flow_angles_rad,
      'ambient_boundary_points_m': tuple(
        sample.point_m for sample in self.ambient_boundary
      ),
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'end_x_m': self.end_x_m,
      'upstream_state_model': 'bounded-previous-ambient-closed-physical-field',
      'boundary_provenance': 'explicit-prescribed-next-shock-and-ambient-samples',
      'claim_status': (
        'prescribed-ambient-closed-next-cell-candidate; '
        'canonical-reflected-free-boundary-pending'
      ),
    }
####


@dataclass(frozen=True, slots=True)
class MocPhysicalPostShockFieldResult:
  """A post-shock field accepted against an explicit ambient perimeter."""

  status: MocPhysicalPostShockFieldStatus
  characteristic_layer_count: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_states: tuple[CharacteristicState, ...]
  centerline_boundary_total_pressure_Pa: tuple[float, ...]
  ambient_boundary: MocAmbientPressureBoundaryResult
  maximum_geometry_residual_m: float | None
  maximum_absolute_invariant_residual: float | None
  minimum_post_shock_total_pressure_ratio: float | None
  maximum_post_shock_total_pressure_ratio: float | None
  message: str = ''
  characteristic_family_orientation_verified: bool = False
  incoming_handoff_states: tuple[CharacteristicState, ...] = ()
  incoming_handoff_total_pressure_Pa: tuple[float, ...] = ()
  upstream_shock_boundary_states: tuple[CharacteristicState, ...] = ()
  upstream_shock_boundary_total_pressure_Pa: tuple[float, ...] = ()
  post_shock_boundary_states: tuple[CharacteristicState, ...] = ()
  post_shock_boundary_total_pressure_Pa: tuple[float, ...] = ()
  zero_strength_shock_start_allowed: bool = False
  zero_strength_shock_endpoints_allowed: bool = False

  def __post_init__(self) -> None:
    if not isinstance(self.zero_strength_shock_start_allowed, bool):
      raise TypeError('zero_strength_shock_start_allowed must be a bool')
    if not isinstance(self.zero_strength_shock_endpoints_allowed, bool):
      raise TypeError('zero_strength_shock_endpoints_allowed must be a bool')
    if len(self.incoming_handoff_states) != len(
      self.incoming_handoff_total_pressure_Pa
    ):
      raise ValueError(
        'incoming handoff states and total-pressure samples must have equal lengths'
      )
    if len(self.upstream_shock_boundary_states) != len(
      self.upstream_shock_boundary_total_pressure_Pa
    ):
      raise ValueError(
        'upstream shock states and total-pressure samples must have equal lengths'
      )
    if len(self.post_shock_boundary_states) != len(
      self.post_shock_boundary_total_pressure_Pa
    ):
      raise ValueError(
        'post-shock boundary states and total-pressure samples must have equal lengths'
      )
    if self.post_shock_boundary_states and len(self.post_shock_boundary_states) != len(
      self.shock_boundary_points_m
    ):
      raise ValueError(
        'post-shock boundary states must match the shock boundary point count'
      )
    if any(
      not isinstance(state, CharacteristicState)
      for state in (
        *self.incoming_handoff_states,
        *self.upstream_shock_boundary_states,
        *self.post_shock_boundary_states,
      )
    ):
      raise TypeError(
        'physical post-shock handoff states must be CharacteristicState values'
      )
    for name, pressures in (
      ('incoming_handoff_total_pressure_Pa', self.incoming_handoff_total_pressure_Pa),
      (
        'upstream_shock_boundary_total_pressure_Pa',
        self.upstream_shock_boundary_total_pressure_Pa,
      ),
      (
        'post_shock_boundary_total_pressure_Pa',
        self.post_shock_boundary_total_pressure_Pa,
      ),
    ):
      if any(not isfinite(float(value)) or value <= 0.0 for value in pressures):
        raise ValueError(f'{name} must contain finite positive values')
    object.__setattr__(self, 'incoming_handoff_states', tuple(self.incoming_handoff_states))
    object.__setattr__(
      self,
      'incoming_handoff_total_pressure_Pa',
      tuple(float(value) for value in self.incoming_handoff_total_pressure_Pa),
    )
    object.__setattr__(
      self,
      'upstream_shock_boundary_states',
      tuple(self.upstream_shock_boundary_states),
    )
    object.__setattr__(
      self,
      'upstream_shock_boundary_total_pressure_Pa',
      tuple(float(value) for value in self.upstream_shock_boundary_total_pressure_Pa),
    )
    object.__setattr__(
      self,
      'post_shock_boundary_states',
      tuple(self.post_shock_boundary_states),
    )
    object.__setattr__(
      self,
      'post_shock_boundary_total_pressure_Pa',
      tuple(float(value) for value in self.post_shock_boundary_total_pressure_Pa),
    )

  @property
  def converged(self) -> bool:
    return self.status is MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return all(self._physical_closure_gates().values())
  ####

  def _physical_closure_gates(self) -> dict[str, bool]:
    """Return independently checkable gates for physical-field promotion.

    ``MocPhysicalPostShockFieldResult`` is a frozen result object, so callers
    can construct one directly for diagnostics.  Promotion must not therefore
    rely on the status enum and one producer-supplied boolean alone.  These
    checks revalidate the evidence that the chain adapter consumes: a bounded
    mesh, the three declared physical paths, centerline state data, compatible
    characteristic nodes, an accepted ambient boundary, and strict shock
    total-pressure loss.

    The assembler remains responsible for the full numerical solve.  This
    method is the final immutable-result guard against a malformed or stale
    result being relabeled as a closed physical cell.
    """

    tolerance_m = 1.0e-8
    residual_tolerance = 1.0e-8
    topology_verified = bool(
      self.converged
      and self.cells
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
    )
    ambient_boundary_verified = bool(
      self.ambient_boundary.converged
      and self.ambient_boundary.physical_closure_verified
      and len(self.ambient_boundary_points_m) == self.ambient_boundary.sample_count
      and all(
        abs(first[0] - second[0]) <= tolerance_m
        and abs(first[1] - second[1]) <= tolerance_m
        for first, second in zip(
          self.ambient_boundary_points_m,
          self.ambient_boundary.points_m,
          strict=True,
        )
      )
    )
    paths_verified = False
    if (
      len(self.shock_boundary_points_m) >= 3
      and len(self.ambient_boundary_points_m) >= 2
      and len(self.centerline_boundary_points_m) >= 2
    ):
      try:
        edge_counts = _edge_counts(self.cells, tolerance_m)
        paths_verified = all(
          _path_edges_present(path, edge_counts, tolerance_m)
          for path in (
            self.shock_boundary_points_m,
            self.ambient_boundary_points_m,
            self.centerline_boundary_points_m,
          )
        )
      except (TypeError, ValueError):
        paths_verified = False
    shock_geometry_verified = bool(
      len(self.shock_boundary_points_m) >= 3
      and all(
        len(point) == 2 and all(isfinite(float(value)) for value in point)
        for point in self.shock_boundary_points_m
      )
      and all(
        second[0] > first[0] + tolerance_m
        and second[1] <= first[1] + tolerance_m
        for first, second in zip(
          self.shock_boundary_points_m,
          self.shock_boundary_points_m[1:],
        )
      )
    )
    centerline_state_verified = bool(
      len(self.centerline_boundary_points_m) >= 2
      and len(self.centerline_boundary_states) == len(self.centerline_boundary_points_m)
      and len(self.centerline_boundary_total_pressure_Pa) == len(self.centerline_boundary_points_m)
      and all(
        isinstance(state, CharacteristicState)
        and abs(state.x_m - point[0]) <= tolerance_m
        and abs(state.y_m - point[1]) <= tolerance_m
        and abs(point[1]) <= tolerance_m
        and abs(state.theta_rad) <= residual_tolerance
        and isfinite(float(pressure))
        and float(pressure) > 0.0
        for point, state, pressure in zip(
          self.centerline_boundary_points_m,
          self.centerline_boundary_states,
          self.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      )
      and all(
        second[0] > first[0] + tolerance_m
        for first, second in zip(
          self.centerline_boundary_points_m,
          self.centerline_boundary_points_m[1:],
        )
      )
    )
    characteristic_nodes_verified = bool(self.nodes)
    if characteristic_nodes_verified:
      for node in self.nodes:
        point_result = getattr(node, 'point_result', None)
        state = getattr(node, 'state', None)
        point = getattr(node, 'point_m', None)
        pressure = getattr(node, 'total_pressure_Pa', None)
        invariant_residuals = (
          getattr(point_result, 'invariant_residual_plus', None),
          getattr(point_result, 'invariant_residual_minus', None),
        )
        characteristic_nodes_verified = characteristic_nodes_verified and bool(
          isinstance(node, MocCharacteristicNode)
          and isinstance(state, CharacteristicState)
          and isinstance(point, tuple)
          and len(point) == 2
          and all(isfinite(float(value)) for value in point)
          and abs(state.x_m - point[0]) <= tolerance_m
          and abs(state.y_m - point[1]) <= tolerance_m
          and isinstance(point_result, CharacteristicPointResult)
          and point_result.converged
          and point_result.geometry_residual is not None
          and isfinite(float(point_result.geometry_residual))
          and abs(float(point_result.geometry_residual)) <= residual_tolerance
          and all(
            value is not None
            and isfinite(float(value))
            and abs(float(value)) <= residual_tolerance
            for value in invariant_residuals
          )
          and pressure is not None
          and isfinite(float(pressure))
          and float(pressure) > 0.0
        )
    residuals_verified = bool(
      self.maximum_geometry_residual_m is not None
      and self.maximum_absolute_invariant_residual is not None
      and isfinite(float(self.maximum_geometry_residual_m))
      and isfinite(float(self.maximum_absolute_invariant_residual))
      and self.maximum_geometry_residual_m >= 0.0
      and self.maximum_absolute_invariant_residual >= 0.0
      and self.maximum_geometry_residual_m <= residual_tolerance
      and self.maximum_absolute_invariant_residual <= residual_tolerance
    )
    return {
      'status_converged': self.converged,
      'topology_verified': topology_verified,
      'shock_geometry_verified': shock_geometry_verified,
      'ambient_boundary_verified': ambient_boundary_verified,
      'physical_boundary_paths_verified': paths_verified,
      'centerline_state_verified': centerline_state_verified,
      'characteristic_nodes_verified': characteristic_nodes_verified,
      'characteristic_residuals_verified': residuals_verified,
      'shock_pressure_loss_verified': self.pressure_loss_verified,
      'family_orientation_verified': self.characteristic_family_orientation_verified,
    }
  ####

  @property
  def physical_closure_gates(self) -> dict[str, bool]:
    """Return the immutable promotion gates used by the chain adapter."""

    return self._physical_closure_gates()
  ####

  @property
  def incoming_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the exact prior-cell handoff consumed by this field solve."""

    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.incoming_handoff_states,
        self.incoming_handoff_total_pressure_Pa,
        strict=True,
      )
    )
  ####

  @property
  def carries_incoming_handoff(self) -> bool:
    return bool(self.incoming_handoff_states)
  ####

  @property
  def upstream_shock_coupling_verified(self) -> bool:
    """Whether the accepted field retained a fitted upstream shock domain."""

    return bool(
      self.converged
      and len(self.shock_boundary_points_m) >= 3
      and len(self.upstream_shock_boundary_states) == len(self.shock_boundary_points_m)
      and len(self.upstream_shock_boundary_total_pressure_Pa) == len(self.shock_boundary_points_m)
      and all(
        abs(state.x_m - point[0]) <= 1.0e-10
        and abs(state.y_m - point[1]) <= 1.0e-10
        for state, point in zip(
          self.upstream_shock_boundary_states,
          self.shock_boundary_points_m,
          strict=True,
        )
      )
    )
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether every assembled cell vertex has solver-carried field data.

    The closed field historically retained its mesh and centerline trace but
    not the downstream state on the fitted shock.  Such a result could be
    inspected, but it could not safely serve as the bounded upstream domain
    for another shock solve.  This gate is deliberately stricter than local
    physical closure and is the promotion boundary for field-coupled
    continuation.
    """

    if not (
      self.physical_closure_verified
      and self.cells
      and len(self.post_shock_boundary_states) == len(self.shock_boundary_points_m)
      and len(self.post_shock_boundary_total_pressure_Pa) == len(self.shock_boundary_points_m)
      and len(self.ambient_boundary.states) == len(self.ambient_boundary.points_m)
      and len(self.ambient_boundary.total_pressure_Pa) == len(self.ambient_boundary.points_m)
      and len(self.centerline_boundary_states) == len(self.centerline_boundary_points_m)
      and len(self.centerline_boundary_total_pressure_Pa) == len(self.centerline_boundary_points_m)
      and all(node.total_pressure_Pa is not None for node in self.nodes)
    ):
      return False
    try:
      return len(self._cell_samples(position_tolerance_m=1.0e-10)) == len(self.cells)
    except (TypeError, ValueError):
      return False
  ####

  def _cell_samples(
    self,
    *,
    position_tolerance_m: float,
  ) -> tuple[
    tuple[
      tuple[tuple[float, float], ...],
      tuple[CharacteristicState, ...],
      tuple[float | None, ...],
    ],
    ...,
  ]:
    """Resolve each closed-field cell vertex to retained state data."""

    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    sources: list[
      tuple[tuple[float, float], CharacteristicState, float | None]
    ] = []
    sources.extend(
      (
        (state.x_m, state.y_m),
        state,
        pressure,
      )
      for state, pressure in zip(
        self.post_shock_boundary_states,
        self.post_shock_boundary_total_pressure_Pa,
        strict=True,
      )
    )
    sources.extend(
      (
        point,
        state,
        pressure,
      )
      for point, state, pressure in zip(
        self.ambient_boundary.points_m,
        self.ambient_boundary.states,
        self.ambient_boundary.total_pressure_Pa,
        strict=True,
      )
    )
    sources.extend(
      (
        point,
        state,
        pressure,
      )
      for point, state, pressure in zip(
        self.centerline_boundary_points_m,
        self.centerline_boundary_states,
        self.centerline_boundary_total_pressure_Pa,
        strict=True,
      )
    )
    sources.extend(
      (
        node.point_m,
        node.state,
        node.total_pressure_Pa,
      )
      for node in self.nodes
    )

    def resolve(
      point: tuple[float, float],
    ) -> tuple[CharacteristicState, float | None] | None:
      for source_point, state, pressure in sources:
        if hypot(point[0] - source_point[0], point[1] - source_point[1]) <= position_tolerance_m:
          return state, pressure
      return None

    resolved_cells: list[
      tuple[
        tuple[tuple[float, float], ...],
        tuple[CharacteristicState, ...],
        tuple[float | None, ...],
      ]
    ] = []
    for cell in self.cells:
      resolved = tuple(resolve(point) for point in cell.vertices_xr_m)
      if any(value is None for value in resolved):
        continue
      samples = tuple(value for value in resolved if value is not None)
      resolved_cells.append(
        (
          tuple(cell.vertices_xr_m),
          tuple(value[0] for value in samples),
          tuple(value[1] for value in samples),
        )
      )
    return tuple(resolved_cells)

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Interpolate a state only inside the retained closed MOC cells."""

    point = _finite_interpolation_point(point_m, position_tolerance_m)
    if not self.state_sampling_available:
      return None
    for vertices, states, _pressures in self._cell_samples(
      position_tolerance_m=position_tolerance_m,
    ):
      weights = _polygon_interpolation_weights(
        point,
        vertices,
        tolerance_m=position_tolerance_m,
      )
      if weights is None:
        continue
      gamma = states[0].gamma
      theta = sum(
        weight * state.theta_rad
        for weight, state in zip(weights, states, strict=True)
      )
      nu = sum(
        weight * state.nu_rad
        for weight, state in zip(weights, states, strict=True)
      )
      inverse = inverse_prandtl_meyer_angle_rad(nu, gamma)
      if not inverse.converged or inverse.value is None:
        return None
      return CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=theta,
        mach=inverse.value,
        gamma=gamma,
      )
    return None
  ####

  def total_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Interpolate total pressure without inventing a new shock-loss lineage."""

    point = _finite_interpolation_point(point_m, position_tolerance_m)
    if not self.state_sampling_available:
      return None
    for vertices, _states, pressures in self._cell_samples(
      position_tolerance_m=position_tolerance_m,
    ):
      if any(pressure is None for pressure in pressures):
        continue
      weights = _polygon_interpolation_weights(
        point,
        vertices,
        tolerance_m=position_tolerance_m,
      )
      if weights is None:
        continue
      return sum(
        weight * pressure
        for weight, pressure in zip(weights, pressures, strict=True)
        if pressure is not None
      )
    return None
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the bounded isentropic static pressure at a field sample."""

    state = self.state_at(point_m, position_tolerance_m=position_tolerance_m)
    total_pressure = self.total_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or total_pressure is None:
      return None
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    return total_pressure / pressure_ratio
  ####

  def as_open_shock_ambient_strip(
    self,
    *,
    trace_position_tolerance_m: float = 1.0e-3,
    trace_forward_tolerance_m: float | None = None,
    trace_invariant_tolerance: float = 1.0e-10,
  ) -> MocAmbientShockStripResult:
    """Expose the accepted field's open shock/ambient source submesh.

    The reflected physical field contains the shock/ambient characteristic
    strip and the centerline-closing cells.  A continued shock cannot consume
    the whole closed mesh as if it were a new upstream domain: the solver must
    first select the open source strip, validate its terminal shock-sourced
    ``C+`` trace, and then assemble the centerline reflection patch.  This
    projection is therefore a typed seam between the first-cell closure and a
    subsequent shock-cell solve; it never changes this result or promotes the
    projected strip to a chain cell.

    The physical field's terminal trace is piecewise linear at the retained
    sampling resolution.  ``trace_position_tolerance_m`` is consequently an
    explicit geometry-discretization tolerance, rather than the tighter
    characteristic invariant tolerance used for the carried state data.  A
    smaller ``trace_forward_tolerance_m`` can be supplied when the first
    segment is a short, nearly Mach-wave endpoint; it affects only the
    downstream/forward test, not the characteristic-line residual.
    """

    for name, value in (
      ('trace_position_tolerance_m', trace_position_tolerance_m),
      ('trace_invariant_tolerance', trace_invariant_tolerance),
    ):
      numeric_value = float(value)
      if not isfinite(numeric_value) or numeric_value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    trace_position_tolerance_m = float(trace_position_tolerance_m)
    trace_invariant_tolerance = float(trace_invariant_tolerance)
    if trace_forward_tolerance_m is None:
      trace_forward_tolerance = float(trace_position_tolerance_m)
    else:
      trace_forward_tolerance = float(trace_forward_tolerance_m)
      if not isfinite(trace_forward_tolerance) or trace_forward_tolerance <= 0.0:
        raise ValueError(
          'trace_forward_tolerance_m must be finite and positive'
        )
    if not self.converged or not self.physical_closure_verified:
      raise ValueError(
        'only a converged ambient-closed physical field can expose an '
        'open shock/ambient source strip'
      )
    if not self.state_sampling_available:
      raise ValueError(
        'the physical field must expose a complete bounded state sampler '
        'before its open source strip can be consumed'
      )
    if not self.upstream_shock_coupling_verified:
      raise ValueError(
        'the physical field must retain fitted upstream shock samples '
        'before its open source strip can be consumed'
      )

    shock_points = tuple(self.shock_boundary_points_m)
    ambient_points = tuple(self.ambient_boundary_points_m)
    expected_count = len(shock_points)
    if expected_count < 3 or len(ambient_points) != expected_count:
      raise ValueError(
        'an accepted physical field must contain equal shock and ambient '
        'sample counts of at least three before projection'
      )
    if (
      len(self.post_shock_boundary_states) != expected_count
      or len(self.post_shock_boundary_total_pressure_Pa) != expected_count
      or len(self.ambient_boundary.states) != expected_count
      or len(self.ambient_boundary.total_pressure_Pa) != expected_count
    ):
      raise ValueError(
        'an accepted physical field is missing a complete shock/ambient '
        'state and total-pressure projection'
      )

    node_by_index = {
      (node.centerline_index, node.boundary_index): node
      for node in self.nodes
    }
    terminal_points = [shock_points[-1]]
    terminal_states = [self.post_shock_boundary_states[-1]]
    terminal_pressures = [self.post_shock_boundary_total_pressure_Pa[-1]]
    try:
      for boundary_index in range(expected_count - 1):
        terminal_node = node_by_index[(expected_count - 1, boundary_index)]
        if terminal_node.total_pressure_Pa is None:
          raise ValueError(
            f'terminal source node {boundary_index} has no total pressure'
          )
        terminal_points.append(terminal_node.point_m)
        terminal_states.append(terminal_node.state)
        terminal_pressures.append(float(terminal_node.total_pressure_Pa))
    except KeyError as error:
      raise ValueError(
        'accepted physical field is missing a terminal shock/ambient source '
        f'node: {error}'
      ) from error
    terminal_points.append(ambient_points[-1])
    terminal_states.append(self.ambient_boundary.states[-1])
    terminal_pressures.append(self.ambient_boundary.total_pressure_Pa[-1])
    terminal_samples = tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        terminal_states,
        terminal_pressures,
        strict=True,
      )
    )
    terminal_trace = validate_characteristic_trace(
      terminal_samples,
      CharacteristicFamily.PLUS,
      position_tolerance_m=trace_position_tolerance_m,
      forward_position_tolerance_m=trace_forward_tolerance,
      invariant_tolerance=trace_invariant_tolerance,
    )
    if not terminal_trace.converged:
      raise ValueError(
        'accepted physical field terminal shock/ambient trace is not a '
        f'usable C+ source: {terminal_trace.message}'
      )

    open_cell_kinds = frozenset({
      'post-shock-shock-strip',
      'post-shock-ambient-outer-strip',
      'post-shock-ambient-interior',
    })
    open_cells = tuple(
      cell for cell in self.cells if cell.cell_kind in open_cell_kinds
    )
    topology = validate_moc_mesh(open_cells)
    if (
      not open_cells
      or not topology.connected
      or not topology.forms_closed_zone
      or topology.nonmanifold_edge_count
    ):
      raise ValueError(
        'accepted physical field open shock/ambient source submesh failed '
        f'topology validation: {topology.message}'
      )
    return MocAmbientShockStripResult(
      status=MocAmbientShockStripStatus.CONVERGED_OPEN,
      characteristic_layer_count=expected_count - 1,
      nodes=self.nodes,
      cells=open_cells,
      topology=topology,
      shock_boundary_points_m=shock_points,
      ambient_boundary_points_m=ambient_points,
      terminal_trace_points_m=tuple(terminal_points),
      terminal_trace_states=tuple(terminal_states),
      terminal_trace_total_pressure_Pa=tuple(
        float(value) for value in terminal_pressures
      ),
      ambient_boundary=self.ambient_boundary,
      maximum_geometry_residual_m=self.maximum_geometry_residual_m,
      maximum_absolute_invariant_residual=self.maximum_absolute_invariant_residual,
      minimum_post_shock_total_pressure_ratio=self.minimum_post_shock_total_pressure_ratio,
      maximum_post_shock_total_pressure_ratio=self.maximum_post_shock_total_pressure_ratio,
      message=(
        'accepted ambient-closed physical field projected to its open '
        'shock/ambient source strip; terminal C+ trace is retained for '
        'centerline reflection'
      ),
      terminal_trace_position_tolerance_m=float(trace_position_tolerance_m),
      terminal_trace_invariant_tolerance=float(trace_invariant_tolerance),
    )
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
  def pressure_loss_verified(self) -> bool:
    strict_loss = (
      self.minimum_post_shock_total_pressure_ratio is not None
      and self.maximum_post_shock_total_pressure_ratio is not None
      and self.minimum_post_shock_total_pressure_ratio > 0.0
      and self.maximum_post_shock_total_pressure_ratio < 1.0
    )
    if strict_loss:
      return True
    if not (
      self.zero_strength_shock_start_allowed
      or self.zero_strength_shock_endpoints_allowed
    ):
      return False
    if (
      len(self.post_shock_boundary_total_pressure_Pa) < 2
      or len(self.upstream_shock_boundary_total_pressure_Pa)
      != len(self.post_shock_boundary_total_pressure_Pa)
    ):
      return False
    ratios = tuple(
      downstream / upstream
      for upstream, downstream in zip(
        self.upstream_shock_boundary_total_pressure_Pa,
        self.post_shock_boundary_total_pressure_Pa,
        strict=True,
      )
    )
    start_allowed = bool(
      self.zero_strength_shock_start_allowed
      and abs(ratios[0] - 1.0) <= 1.0e-10
      and all(0.0 < ratio < 1.0 for ratio in ratios[1:])
    )
    endpoints_allowed = bool(
      self.zero_strength_shock_endpoints_allowed
      and abs(ratios[0] - 1.0) <= 1.0e-10
      and abs(ratios[-1] - 1.0) <= 1.0e-10
      and all(0.0 < ratio < 1.0 for ratio in ratios[1:-1])
    )
    return start_allowed or endpoints_allowed
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'physical_closure_gates': self.physical_closure_gates,
      'characteristic_family_orientation_verified': (
        self.characteristic_family_orientation_verified
      ),
      'upstream_shock_coupling_verified': self.upstream_shock_coupling_verified,
      'state_sampling_available': self.state_sampling_available,
      'post_shock_boundary_sample_count': len(self.post_shock_boundary_states),
      'incoming_handoff_sample_count': len(self.incoming_handoff_states),
      'characteristic_layer_count': self.characteristic_layer_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'ambient_boundary': self.ambient_boundary.as_report(),
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
      'zero_strength_shock_start_allowed': (
        self.zero_strength_shock_start_allowed
      ),
      'zero_strength_shock_endpoints_allowed': (
        self.zero_strength_shock_endpoints_allowed
      ),
      'message': self.message,
    }
  ####

  def as_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainCell:
    """Promote only a fully ambient-closed cell into the resolved chain."""

    if not self.physical_closure_verified:
      raise ValueError(
        'only a converged ambient-closed post-shock field with verified '
        'shock-C+/ambient-C- family orientation can become a chain cell'
      )
    chain_diagnostics: dict[str, Any] = {
      'source': 'ambient-pressure-coupled-post-shock-field',
      'physical_closure_verified': True,
      'upstream_shock_coupling_verified': self.upstream_shock_coupling_verified,
      'characteristic_layer_count': self.characteristic_layer_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'maximum_geometry_residual_m': self.maximum_geometry_residual_m,
      'maximum_absolute_invariant_residual': self.maximum_absolute_invariant_residual,
      'minimum_post_shock_total_pressure_ratio': self.minimum_post_shock_total_pressure_ratio,
      'maximum_post_shock_total_pressure_ratio': self.maximum_post_shock_total_pressure_ratio,
      'ambient_boundary_maximum_absolute_pressure_residual': (
        self.ambient_boundary.maximum_absolute_pressure_residual
      ),
      'ambient_boundary_maximum_absolute_tangent_residual': (
        self.ambient_boundary.maximum_absolute_tangent_residual
      ),
      'boundary_geometry': {
        'incoming_handoff_points_m': [
          [state.x_m, state.y_m] for state in self.incoming_handoff_states
        ],
        'shock_boundary_points_m': [
          list(point) for point in self.shock_boundary_points_m
        ],
        'ambient_boundary_points_m': [
          list(point) for point in self.ambient_boundary_points_m
        ],
        'centerline_boundary_points_m': [
          list(point) for point in self.centerline_boundary_points_m
        ],
      },
      'boundary_pressure_traces': {
        'incoming_handoff_total_pressure_Pa': list(
          self.incoming_handoff_total_pressure_Pa
        ),
        'upstream_shock_total_pressure_Pa': list(
          self.upstream_shock_boundary_total_pressure_Pa
        ),
        'post_shock_total_pressure_Pa': list(
          self.post_shock_boundary_total_pressure_Pa
        ),
        'ambient_total_pressure_Pa': list(
          self.ambient_boundary.total_pressure_Pa
        ),
        'centerline_total_pressure_Pa': list(
          self.centerline_boundary_total_pressure_Pa
        ),
      },
    }
    if diagnostics is not None:
      reserved = set(chain_diagnostics) & set(diagnostics)
      if reserved:
        raise ValueError(f'diagnostics cannot override reserved closure keys: {sorted(reserved)!r}')
      chain_diagnostics.update(diagnostics)
    return MocChainCell(
      cell_index=cell_index,
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      mesh=self.cells,
      geometry_fidelity=MocChainGeometryFidelity.RESOLVED_PLANAR_MOC,
      physical_closure=MocCellClosureStatus.CLOSED,
      diagnostics=chain_diagnostics,
      continuation_boundary=tuple(
        MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
        for state, pressure in zip(
          self.centerline_boundary_states,
          self.centerline_boundary_total_pressure_Pa,
          strict=True,
        )
      ),
      continuation_boundary_kind=MocChainBoundaryKind.CENTERLINE_TRACE,
    )
  ####

  def as_coupled_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainCell:
    """Promote only a field with explicit upstream shock coupling."""

    if not self.upstream_shock_coupling_verified:
      raise ValueError(
        'coupled physical-field chain promotion requires a converged field '
        'with upstream shock states and total-pressure samples'
      )
    coupled_diagnostics = {
      'upstream_coupling_promotion_gate': 'passed',
    }
    if diagnostics is not None:
      if 'upstream_shock_coupling_verified' in diagnostics:
        raise ValueError('reserved coupling diagnostics cannot be overridden')
      coupled_diagnostics.update(diagnostics)
    return self.as_chain_cell(
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      cell_index=cell_index,
      diagnostics=coupled_diagnostics,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocPhysicalPostShockFieldContinuationSolve:
  """One ambient-closed physical field returned for a continued cell."""

  field: MocPhysicalPostShockFieldResult
  end_x_m: float

  def __post_init__(self) -> None:
    if not isinstance(self.field, MocPhysicalPostShockFieldResult):
      raise TypeError('field must be a MocPhysicalPostShockFieldResult')
    if not isfinite(float(self.end_x_m)) or self.end_x_m <= 0.0:
      raise ValueError('end_x_m must be finite and positive')
  ####


@dataclass(frozen=True, slots=True)
class MocPhysicalPostShockTerminalPatchTransitionResult:
  """Retained artifacts for a physical-field terminal-patch transition.

  The chain adapter historically returned only the final termination decision.
  That was sufficient for stopping a supersonic chain, but it discarded the
  typed source strip, reflection patch, and terminal shock objects needed by
  a downstream mixed-regime planner.  This result keeps those objects
  together without changing their claim ceiling: the normal-shock endpoint
  is a valid chain stop, while the mixed-regime request is still an explicit
  handoff and never a promoted supersonic cell.
  """

  decision: MocChainTerminationDecision
  source_strip: MocAmbientShockStripResult | None = None
  reflection_patch: MocTerminalReflectionPatchResult | None = None
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None = None
  terminal_field: 'MocTerminalShockCellFieldResult | None' = None
  mixed_regime_request: MocMixedRegimePerimeterRequest | None = None
  mixed_regime_field: MocMixedRegimeFieldResult | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.decision, MocChainTerminationDecision):
      raise TypeError('decision must be a MocChainTerminationDecision')
    if self.source_strip is not None and not isinstance(
      self.source_strip,
      MocAmbientShockStripResult,
    ):
      raise TypeError(
        'source_strip must be a MocAmbientShockStripResult or None'
      )
    if self.reflection_patch is not None and not isinstance(
      self.reflection_patch,
      MocTerminalReflectionPatchResult,
    ):
      raise TypeError(
        'reflection_patch must be a MocTerminalReflectionPatchResult or None'
      )
    if self.downstream_shock is not None and not isinstance(
      self.downstream_shock,
      MocTerminalReflectionPatchShockSolveResult,
    ):
      raise TypeError(
        'downstream_shock must be a '
        'MocTerminalReflectionPatchShockSolveResult or None'
      )
    if self.mixed_regime_request is not None and not isinstance(
      self.mixed_regime_request,
      MocMixedRegimePerimeterRequest,
    ):
      raise TypeError(
        'mixed_regime_request must be a MocMixedRegimePerimeterRequest or None'
      )
    if self.terminal_field is not None:
      # Keep the import local.  shock_chain imports the coupled solver, which
      # imports this module; importing it at module scope would create a
      # cycle during package initialization.
      from exhaust_plume.models.moc.shock_chain import (
        MocTerminalShockCellFieldResult,
      )

      if not isinstance(self.terminal_field, MocTerminalShockCellFieldResult):
        raise TypeError(
          'terminal_field must be a MocTerminalShockCellFieldResult or None'
        )
      if self.mixed_regime_request is not None:
        if not self.terminal_field.converged:
          raise ValueError(
            'mixed_regime_request requires a converged terminal_field'
          )
        if (
          self.terminal_field.mixed_regime_perimeter_request()
          != self.mixed_regime_request
        ):
          raise ValueError(
            'mixed_regime_request must retain the terminal_field seam'
          )
    elif self.mixed_regime_request is not None:
      raise ValueError(
        'mixed_regime_request requires the retained terminal_field'
      )
    if self.mixed_regime_field is not None:
      if not isinstance(self.mixed_regime_field, MocMixedRegimeFieldResult):
        raise TypeError(
          'mixed_regime_field must be a MocMixedRegimeFieldResult or None'
        )
      if self.terminal_field is None:
        raise ValueError(
          'mixed_regime_field requires the retained terminal_field'
        )
      if self.mixed_regime_request is None:
        raise ValueError(
          'mixed_regime_field requires the retained mixed_regime_request'
        )
      if not self.mixed_regime_field.physical_closure_verified:
        raise ValueError(
          'only a physically closed mixed-regime field can be attached'
        )
      if self.mixed_regime_field.boundary.terminal != (
        self.terminal_field.terminal_normal_shock
      ):
        raise ValueError(
          'mixed_regime_field must retain the exact terminal shock seam'
        )
      if (
        self.mixed_regime_field.boundary.supersonic_patch
        != self.terminal_field.terminal_shock_supersonic_downstream_states
      ):
        raise ValueError(
          'mixed_regime_field must retain the exact terminal supersonic patch'
        )
      if (
        self.terminal_field.mixed_regime_field is not self.mixed_regime_field
        and self.terminal_field.mixed_regime_field
        != self.mixed_regime_field
      ):
        raise ValueError(
          'terminal_field must retain the exact attached mixed-regime field'
        )
    object.__setattr__(self, 'mixed_regime_request', self.mixed_regime_request)
    object.__setattr__(self, 'mixed_regime_field', self.mixed_regime_field)

  @property
  def converged(self) -> bool:
    """Whether the transition produced the typed normal-shock chain stop."""

    return self.decision.physical_termination

  @property
  def physical_terminal_verified(self) -> bool:
    """Whether a verified subsonic terminal was retained."""

    return self.decision.physical_termination

  @property
  def mixed_regime_seam_available(self) -> bool:
    """Whether a complete terminal request is available downstream."""

    return self.mixed_regime_request is not None

  @property
  def mixed_regime_field_complete(self) -> bool:
    """Whether the exact downstream field has been attached to the terminal."""

    return bool(
      self.mixed_regime_field is not None
      and self.mixed_regime_field.physical_closure_verified
      and self.terminal_field is not None
      and self.terminal_field.mixed_regime_field is self.mixed_regime_field
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the retained supersonic and downstream fields both closed."""

    return bool(
      self.terminal_field is not None
      and self.terminal_field.physical_closure_verified
      and self.mixed_regime_field_complete
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal patch transition is a stop, never a new supersonic cell."""

    return True

  def as_mixed_regime_perimeter_request(self) -> MocMixedRegimePerimeterRequest:
    """Return the exact scalar seam for a downstream mixed-regime solver."""

    if self.mixed_regime_request is None:
      raise ValueError(
        'this terminal-patch transition did not produce a mixed-regime seam'
      )
    return self.mixed_regime_request

  def with_mixed_regime_field(
    self,
    mixed_regime_field: MocMixedRegimeFieldResult,
  ) -> 'MocPhysicalPostShockTerminalPatchTransitionResult':
    """Attach an exact downstream field without promoting a chain cell.

    The terminal transition owns the normal-shock and supersonic patch seam,
    while the mixed-regime solver owns the downstream field.  Attachment is
    therefore explicit and identity-checked.  A passing field can make the
    transition physically closed at this result layer, but
    ``chain_promotion_blocked`` remains true because this transition is a
    terminal stop rather than a new supersonic cell.
    """

    if not isinstance(mixed_regime_field, MocMixedRegimeFieldResult):
      raise TypeError(
        'mixed_regime_field must be a MocMixedRegimeFieldResult'
      )
    if self.terminal_field is None or not self.converged:
      raise ValueError(
        'a mixed-regime field requires a converged terminal-patch field'
      )
    if self.mixed_regime_request is None:
      raise ValueError(
        'a mixed-regime field requires the exact mixed-regime request'
      )
    if not mixed_regime_field.physical_closure_verified:
      raise ValueError(
        'only a physically closed mixed-regime field can be attached'
      )
    if mixed_regime_field.boundary.terminal != self.terminal_field.terminal_normal_shock:
      raise ValueError(
        'mixed-regime field does not retain the exact terminal shock seam'
      )
    if mixed_regime_field.boundary.supersonic_patch != (
      self.terminal_field.terminal_shock_supersonic_downstream_states
    ):
      raise ValueError(
        'mixed-regime field does not retain the exact terminal supersonic patch'
      )
    if mixed_regime_field != self.mixed_regime_field:
      updated_terminal_field = self.terminal_field.with_mixed_regime_field(
        mixed_regime_field
      )
    else:
      updated_terminal_field = self.terminal_field
    return replace(
      self,
      terminal_field=updated_terminal_field,
      mixed_regime_field=mixed_regime_field,
    )

  def attach_mixed_regime_closure(
    self,
    closure: MocMixedRegimeClosureResult,
  ) -> 'MocPhysicalPostShockTerminalPatchTransitionResult':
    """Attach one accepted closure while preserving the exact terminal seam."""

    if not isinstance(closure, MocMixedRegimeClosureResult):
      raise TypeError(
        'closure must be a MocMixedRegimeClosureResult'
      )
    if self.mixed_regime_request is None:
      raise ValueError(
        'a mixed-regime closure requires the exact mixed-regime request'
      )
    if closure.request != self.mixed_regime_request:
      raise ValueError(
        'mixed-regime closure does not retain this terminal-patch seam'
      )
    if not closure.converged or closure.field is None:
      raise ValueError(
        'only a converged mixed-regime closure with an accepted field can be attached'
      )
    return self.with_mixed_regime_field(closure.field)

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.decision.reason.value,
      'converged': self.converged,
      'physical_terminal_verified': self.physical_terminal_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'mixed_regime_seam_available': self.mixed_regime_seam_available,
      'decision': self.decision.as_report(),
      'source_strip': (
        None if self.source_strip is None else self.source_strip.as_report()
      ),
      'reflection_patch': (
        None
        if self.reflection_patch is None
        else self.reflection_patch.as_report()
      ),
      'downstream_shock': (
        None
        if self.downstream_shock is None
        else self.downstream_shock.as_report()
      ),
      'terminal_field': (
        None
        if self.terminal_field is None
        else self.terminal_field.as_report()
      ),
      'mixed_regime_request': (
        None
        if self.mixed_regime_request is None
        else self.mixed_regime_request.as_report()
      ),
      'mixed_regime_field': (
        None
        if self.mixed_regime_field is None
        else self.mixed_regime_field.as_report()
      ),
    }
  ####


def _empty_ambient_boundary(ambient_pressure_Pa: float) -> MocAmbientPressureBoundaryResult:
  return MocAmbientPressureBoundaryResult(
    status=MocAmbientBoundaryStatus.INVALID_INPUT,
    points_m=(),
    states=(),
    total_pressure_Pa=(),
    static_pressure_Pa=(),
    pressure_residuals=(),
    tangent_residuals=(),
    ambient_pressure_Pa=ambient_pressure_Pa,
    maximum_absolute_pressure_residual=None,
    maximum_absolute_tangent_residual=None,
    message='ambient boundary was not assembled',
  )


def _failure(
  status: MocPhysicalPostShockFieldStatus,
  *,
  ambient_boundary: MocAmbientPressureBoundaryResult,
  characteristic_layer_count: int = 0,
  nodes: Sequence[MocCharacteristicNode] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  shock_points: Sequence[tuple[float, float]] = (),
  ambient_points: Sequence[tuple[float, float]] = (),
  axis_points: Sequence[tuple[float, float]] = (),
  axis_states: Sequence[CharacteristicState] = (),
  axis_pressures: Sequence[float] = (),
  pressure_ratios: Sequence[float] = (),
  maximum_geometry_residual_m: float | None = None,
  maximum_absolute_invariant_residual: float | None = None,
  message: str,
) -> MocPhysicalPostShockFieldResult:
  return MocPhysicalPostShockFieldResult(
    status=status,
    characteristic_layer_count=characteristic_layer_count,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=validate_moc_mesh(()) if topology is None else topology,
    shock_boundary_points_m=tuple(shock_points),
    ambient_boundary_points_m=tuple(ambient_points),
    centerline_boundary_points_m=tuple(axis_points),
    centerline_boundary_states=tuple(axis_states),
    centerline_boundary_total_pressure_Pa=tuple(float(value) for value in axis_pressures),
    ambient_boundary=ambient_boundary,
    maximum_geometry_residual_m=maximum_geometry_residual_m,
    maximum_absolute_invariant_residual=maximum_absolute_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios, default=None),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios, default=None),
    message=message,
  )


def _point_key(
  point: tuple[float, float],
  position_tolerance_m: float,
) -> tuple[int, int]:
  return round(point[0] / position_tolerance_m), round(point[1] / position_tolerance_m)


def _edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  position_tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _point_key(first, position_tolerance_m)
  second_key = _point_key(second, position_tolerance_m)
  return (first_key, second_key) if first_key <= second_key else (second_key, first_key)


def _edge_counts(
  cells: Sequence[MocCharacteristicCell],
  position_tolerance_m: float,
) -> dict[tuple[tuple[int, int], tuple[int, int]], int]:
  counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  for cell in cells:
    vertices = tuple(cell.vertices_xr_m)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      edge = _edge_key(first, second, position_tolerance_m)
      counts[edge] = counts.get(edge, 0) + 1
  return counts


def _path_edges_present(
  points: Sequence[tuple[float, float]],
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int],
  position_tolerance_m: float,
) -> bool:
  return all(
    edge_counts.get(_edge_key(first, second, position_tolerance_m), 0) == 1
    for first, second in zip(points, points[1:])
  )


def _finite_interpolation_point(
  point_m: tuple[float, float],
  position_tolerance_m: float,
) -> tuple[float, float]:
  if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
    raise ValueError('point_m must contain two finite coordinates')
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  return float(point_m[0]), float(point_m[1])


def _triangle_interpolation_weights(
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
  vertices: tuple[tuple[float, ...], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  if len(vertices) == 3:
    triangle = tuple((float(vertex[0]), float(vertex[1])) for vertex in vertices)
    return _triangle_interpolation_weights(
      point,
      triangle,
      tolerance_m=tolerance_m,
    )
  if len(vertices) != 4:
    return None
  first = _triangle_interpolation_weights(
    point,
    (
      (float(vertices[0][0]), float(vertices[0][1])),
      (float(vertices[1][0]), float(vertices[1][1])),
      (float(vertices[2][0]), float(vertices[2][1])),
    ),
    tolerance_m=tolerance_m,
  )
  if first is not None:
    return first[0], first[1], first[2], 0.0
  second = _triangle_interpolation_weights(
    point,
    (
      (float(vertices[0][0]), float(vertices[0][1])),
      (float(vertices[2][0]), float(vertices[2][1])),
      (float(vertices[3][0]), float(vertices[3][1])),
    ),
    tolerance_m=tolerance_m,
  )
  if second is not None:
    return second[0], 0.0, second[1], second[2]
  return None


def _shock_endpoint_characteristic_point(
  plus_source: CharacteristicState,
  minus_endpoint: CharacteristicState,
  endpoint: tuple[float, float],
  *,
  position_tolerance_m: float,
  invariant_tolerance: float,
) -> CharacteristicPointResult:
  """Validate a shock-sourced ``C+`` arriving at an ambient endpoint.

  The ambient sample is itself the ``C-`` source, so a generic two-ray
  intersection sees a zero-length second ray and correctly rejects it as an
  interior point.  A physical shock/ambient boundary needs the one-sided
  endpoint contract instead: the ambient endpoint must preserve the shock
  ``K+`` invariant and lie forward on the shock-sourced ``C+`` ray.
  """

  if abs(plus_source.gamma - minus_endpoint.gamma) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVALID_INPUT,
      state=None,
      point_m=None,
      invariant_residual_plus=None,
      invariant_residual_minus=None,
      geometry_residual=None,
      iterations=0,
      message='shock and ambient endpoint states use different gamma values',
    )
  plus_residual = minus_endpoint.k_plus - plus_source.k_plus
  displacement = (
    endpoint[0] - plus_source.x_m,
    endpoint[1] - plus_source.y_m,
  )
  if sqrt(displacement[0] ** 2 + displacement[1] ** 2) <= position_tolerance_m:
    if abs(plus_residual) > invariant_tolerance:
      return CharacteristicPointResult(
        status=MocPrimitiveStatus.INVARIANT_FAILURE,
        state=minus_endpoint,
        point_m=endpoint,
        invariant_residual_plus=plus_residual,
        invariant_residual_minus=0.0,
        geometry_residual=0.0,
        iterations=0,
        intersection_status='shared-attachment',
        message='shared shock/ambient attachment does not preserve C+ compatibility',
      )
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.CONVERGED,
      state=minus_endpoint,
      point_m=endpoint,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=0.0,
      iterations=0,
      intersection_status='shared-attachment',
    )
  if abs(plus_residual) > invariant_tolerance:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.INVARIANT_FAILURE,
      state=minus_endpoint,
      point_m=endpoint,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=None,
      iterations=0,
      message='ambient endpoint does not preserve the shock C+ invariant',
    )
  start_angle = plus_source.theta_rad + plus_source.mu_rad
  end_angle = minus_endpoint.theta_rad + minus_endpoint.mu_rad
  direction_angle = 0.5 * (start_angle + end_angle)
  direction = (cos(direction_angle), sin(direction_angle))
  forward_parameter = displacement[0] * direction[0] + displacement[1] * direction[1]
  geometry_residual = abs(
    displacement[0] * direction[1] - displacement[1] * direction[0]
  )
  if forward_parameter <= position_tolerance_m:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      state=None,
      point_m=endpoint,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=geometry_residual,
      iterations=0,
      message='shock-to-ambient C+ endpoint has no forward margin',
    )
  if geometry_residual > position_tolerance_m:
    return CharacteristicPointResult(
      status=MocPrimitiveStatus.GEOMETRY_FAILURE,
      state=None,
      point_m=endpoint,
      invariant_residual_plus=plus_residual,
      invariant_residual_minus=0.0,
      geometry_residual=geometry_residual,
      iterations=0,
      message='shock-to-ambient C+ endpoint is not on its averaged characteristic',
    )
  return CharacteristicPointResult(
    status=MocPrimitiveStatus.CONVERGED,
    state=minus_endpoint,
    point_m=endpoint,
    invariant_residual_plus=plus_residual,
    invariant_residual_minus=0.0,
    geometry_residual=geometry_residual,
    iterations=0,
    intersection_status='boundary-endpoint',
  )


def assemble_ambient_boundary_post_shock_field(
  shock_fit: MocShockBoundaryFitResult,
  ambient_boundary: Sequence[MocAmbientBoundarySample],
  ambient_pressure_Pa: float,
  *,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  centerline_reflection: bool = False,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  allow_zero_strength_shock_start: bool = False,
  allow_zero_strength_endpoints: bool = False,
) -> MocPhysicalPostShockFieldResult:
  """Assemble a shock/ambient/centerline triangular characteristic field.

  The ambient samples are the physical outer boundary and are ordered from
  the shock attachment toward downstream.  Shock states supply the ``C+``
  sources and ambient states supply the ``C-`` sources.  A diagonal
  intersection must reproduce each ambient boundary point.  By default the
  function retains the historical boundary-conditioned triangular strip and
  accepts one explicit downstream axis corner as a diagnostic input.  When
  ``centerline_reflection`` is true, the ambient trace must contain exactly
  the ``N`` shock samples; every ambient-sourced ``C-`` characteristic is
  then continued to ``y=0`` and terminal axis cells are added.  That explicit
  reflected mode is the physical centerline closure path and never treats
  the terminal C+ row as the axis.

  ``allow_zero_strength_shock_start`` is reserved for a shock curve that
  begins on an already pressure-matched ambient boundary.  It permits one
  exact Mach-wave endpoint at the first shock sample; later samples still
  require strict total-pressure loss.
  ``allow_zero_strength_endpoints`` additionally permits the final centerline
  sample to use the same endpoint model; all interior samples remain strict.
  """

  if not isinstance(shock_fit, MocShockBoundaryFitResult):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='shock_fit must be a MocShockBoundaryFitResult',
    )
  if not isfinite(float(ambient_pressure_Pa)) or ambient_pressure_Pa <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  if not isinstance(centerline_reflection, bool):
    raise TypeError('centerline_reflection must be a bool')
  if not isinstance(allow_zero_strength_shock_start, bool):
    raise TypeError('allow_zero_strength_shock_start must be a bool')
  if not isinstance(allow_zero_strength_endpoints, bool):
    raise TypeError('allow_zero_strength_endpoints must be a bool')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    incoming_samples = () if incoming_handoff is None else tuple(incoming_handoff)
  except TypeError:
    incoming_samples = ()
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in incoming_samples):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='incoming_handoff must contain MocChainBoundarySample values',
    )
  if incoming_handoff is not None and len(incoming_samples) < 3:
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='incoming_handoff requires at least three state samples',
    )
  incoming_states = tuple(sample.state for sample in incoming_samples)
  incoming_pressures = tuple(sample.total_pressure_Pa for sample in incoming_samples)
  if not shock_fit.converged:
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.SHOCK_FAILURE,
      ambient_boundary=ambient_result,
      message=f'shock boundary fit is not converged: {shock_fit.message}',
    )
  samples = tuple(ambient_boundary)
  if any(not isinstance(sample, MocAmbientBoundarySample) for sample in samples):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message='ambient_boundary must contain MocAmbientBoundarySample values',
    )
  shock_samples = tuple(shock_fit.boundary_states)
  if len(shock_samples) < 3 or len(samples) not in (
    len(shock_samples),
    len(shock_samples) + 1,
  ):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      message=(
        'shock and ambient boundaries must contain at least three samples, '
        'with either equal counts or one explicit ambient downstream axis '
        'corner'
      ),
    )
  if centerline_reflection and len(samples) != len(shock_samples):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      ambient_points=tuple(sample.point_m for sample in samples),
      message=(
        'centerline-reflection assembly requires one physical ambient '
        'sample per fitted shock sample; an explicit axis corner is not a '
        'C- source'
      ),
    )
  upstream_shock_states = tuple(shock_fit.upstream_states)
  upstream_shock_pressures = tuple(shock_fit.upstream_total_pressure_Pa)
  if bool(upstream_shock_states) != bool(upstream_shock_pressures):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      message=(
        'shock-fit upstream coupling must provide both upstream states and '
        'upstream total-pressure samples'
      ),
    )
  if upstream_shock_states and (
    len(upstream_shock_states) != len(shock_samples)
    or len(upstream_shock_pressures) != len(shock_samples)
  ):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      message='shock-fit upstream coupling samples must match the shock boundary count',
    )
  if upstream_shock_states and any(
    abs(state.x_m - sample.point_m[0]) > position_tolerance_m
    or abs(state.y_m - sample.point_m[1]) > position_tolerance_m
    or abs(pressure - sample.upstream_total_pressure_Pa)
      > pressure_tolerance * max(1.0, abs(pressure), abs(sample.upstream_total_pressure_Pa))
    for state, pressure, sample in zip(
      upstream_shock_states,
      upstream_shock_pressures,
      shock_samples,
      strict=True,
    )
  ):
    ambient_result = _empty_ambient_boundary(float(ambient_pressure_Pa))
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      message='shock-fit upstream coupling does not match the fitted shock samples',
    )
  ambient_result = validate_ambient_pressure_boundary(
    samples,
    ambient_pressure_Pa,
    position_tolerance_m=position_tolerance_m,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
  )
  if not ambient_result.converged:
    return _failure(
      MocPhysicalPostShockFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=tuple(sample.point_m for sample in shock_samples),
      ambient_points=tuple(sample.point_m for sample in samples),
      message=f'ambient boundary is not accepted: {ambient_result.message}',
    )
  shock_points = tuple(sample.point_m for sample in shock_samples)
  ambient_points = tuple(sample.point_m for sample in samples)
  if (
    any(
      abs(shock.point_m[0] - shock.state.x_m) > position_tolerance_m
      or abs(shock.point_m[1] - shock.state.y_m) > position_tolerance_m
      for shock in shock_samples
    )
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.INVALID_INPUT,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary state coordinates do not match their fitted points',
    )
  if any(point[1] < -position_tolerance_m for point in shock_points):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary crossed below the symmetry line',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    for first, second in zip(shock_points, shock_points[1:])
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary must be strictly downstream and nonincreasing in y',
    )
  if (
    sqrt(
      (shock_points[0][0] - ambient_points[0][0]) ** 2
      + (shock_points[0][1] - ambient_points[0][1]) ** 2
    ) > position_tolerance_m
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock and ambient boundaries must share their attachment point',
    )
  if abs(shock_points[-1][1]) > position_tolerance_m:
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='shock boundary must terminate on the symmetry line',
    )
  if not centerline_reflection and abs(ambient_points[-1][1]) > position_tolerance_m:
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      message='ambient boundary must terminate on the symmetry line',
    )
  pressure_ratios = tuple(
    sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
    for sample in shock_samples
  )
  zero_strength_start = bool(
    allow_zero_strength_shock_start
    and abs(pressure_ratios[0] - 1.0) <= 1.0e-10
    and all(0.0 < ratio < 1.0 for ratio in pressure_ratios[1:])
  )
  zero_strength_endpoints = bool(
    allow_zero_strength_endpoints
    and abs(pressure_ratios[0] - 1.0) <= 1.0e-10
    and abs(pressure_ratios[-1] - 1.0) <= 1.0e-10
    and all(0.0 < ratio < 1.0 for ratio in pressure_ratios[1:-1])
  )
  if (
    any(ratio <= 0.0 or ratio >= 1.0 for ratio in pressure_ratios)
    and not (zero_strength_start or zero_strength_endpoints)
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.SHOCK_FAILURE,
      ambient_boundary=ambient_result,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message='shock boundary must carry strict total-pressure loss at every sample',
    )
  ####

  expected_count = len(shock_samples)
  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for plus_index in range(expected_count):
    plus_source = shock_samples[plus_index].state
    for minus_index in range(plus_index + 1):
      minus_source = samples[minus_index].state
      if plus_index == minus_index:
        point_result = _shock_endpoint_characteristic_point(
          plus_source,
          minus_source,
          ambient_points[plus_index],
          position_tolerance_m=position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
        if not point_result.converged or point_result.point_m is None or point_result.state is None:
          status = (
            MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
            if point_result.status.value == 'invariant_failure'
            else MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE
          )
          return _failure(
            status,
            ambient_boundary=ambient_result,
            characteristic_layer_count=expected_count - 1,
            nodes=tuple(nodes_by_index.values()),
            shock_points=shock_points,
            ambient_points=ambient_points,
            pressure_ratios=pressure_ratios,
            message=f'diagonal shock coupling {plus_index} failed: {point_result.message}',
          )
        point = point_result.point_m
        state = point_result.state
      else:
        point_result = interior_characteristic_point(
          plus_source,
          minus_source,
          position_tolerance_m=position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
        if not point_result.converged or point_result.point_m is None or point_result.state is None:
          status = (
            MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
            if point_result.status.value == 'invariant_failure'
            else MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE
          )
          return _failure(
            status,
            ambient_boundary=ambient_result,
            characteristic_layer_count=expected_count - 1,
            nodes=tuple(nodes_by_index.values()),
            shock_points=shock_points,
            ambient_points=ambient_points,
            pressure_ratios=pressure_ratios,
            message=f'characteristic node ({plus_index}, {minus_index}) failed: {point_result.message}',
          )
        point = point_result.point_m
        state = point_result.state
      nodes_by_index[(plus_index, minus_index)] = MocCharacteristicNode(
        centerline_index=plus_index,
        boundary_index=minus_index,
        point_m=(float(point[0]), float(point[1])),
        state=state,
        point_result=point_result,
        total_pressure_Pa=samples[minus_index].total_pressure_Pa,
      )
  ####

  axis_results: tuple[CharacteristicPointResult, ...] = ()
  if centerline_reflection:
    resolved_axis_results: list[CharacteristicPointResult] = []
    for index, sample in enumerate(samples):
      try:
        axis_result = centerline_characteristic_point(
          sample.state,
          CharacteristicFamily.MINUS,
          position_tolerance_m=position_tolerance_m,
          invariant_tolerance=invariant_tolerance,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return _failure(
          MocPhysicalPostShockFieldStatus.AXIS_FAILURE,
          ambient_boundary=ambient_result,
          characteristic_layer_count=expected_count - 1,
          nodes=tuple(nodes_by_index.values()),
          shock_points=shock_points,
          ambient_points=ambient_points,
          axis_points=tuple(
            result.point_m
            for result in resolved_axis_results
            if result.point_m is not None
          ),
          axis_states=tuple(
            result.state
            for result in resolved_axis_results
            if result.state is not None
          ),
          axis_pressures=tuple(
            samples[axis_index].total_pressure_Pa
            for axis_index in range(len(resolved_axis_results))
          ),
          pressure_ratios=pressure_ratios,
          message=f'ambient C- centerline reflection {index} raised: {error}',
        )
      if (
        not axis_result.converged
        or axis_result.point_m is None
        or axis_result.state is None
      ):
        status = (
          MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
          if axis_result.status is MocPrimitiveStatus.INVARIANT_FAILURE
          else MocPhysicalPostShockFieldStatus.AXIS_FAILURE
        )
        return _failure(
          status,
          ambient_boundary=ambient_result,
          characteristic_layer_count=expected_count - 1,
          nodes=tuple(nodes_by_index.values()),
          shock_points=shock_points,
          ambient_points=ambient_points,
          axis_points=tuple(
            result.point_m
            for result in resolved_axis_results
            if result.point_m is not None
          ),
          axis_states=tuple(
            result.state
            for result in resolved_axis_results
            if result.state is not None
          ),
          axis_pressures=tuple(
            samples[axis_index].total_pressure_Pa
            for axis_index in range(len(resolved_axis_results))
          ),
          pressure_ratios=pressure_ratios,
          message=(
            f'ambient C- centerline reflection {index} failed: '
            f'{axis_result.message}'
          ),
        )
      resolved_axis_results.append(axis_result)
    axis_results = tuple(resolved_axis_results)
    axis_x_values = tuple(
      result.point_m[0]
      for result in axis_results
      if result.point_m is not None
    )
    if (
      len(axis_x_values) != expected_count
      or any(
        second <= first + position_tolerance_m
        for first, second in zip(axis_x_values, axis_x_values[1:])
      )
      or axis_x_values[0] <= shock_points[-1][0] + position_tolerance_m
    ):
      return _failure(
        MocPhysicalPostShockFieldStatus.AXIS_FAILURE,
        ambient_boundary=ambient_result,
        characteristic_layer_count=expected_count - 1,
        nodes=tuple(nodes_by_index.values()),
        shock_points=shock_points,
        ambient_points=ambient_points,
        axis_points=tuple(result.point_m for result in axis_results if result.point_m is not None),
        axis_states=tuple(result.state for result in axis_results if result.state is not None),
        axis_pressures=tuple(sample.total_pressure_Pa for sample in samples),
        pressure_ratios=pressure_ratios,
        message=(
          'ambient C- centerline reflections must form a strictly downstream '
          'axis trace after the fitted shock endpoint'
        ),
      )
  ####

  def node_point(plus_index: int, minus_index: int) -> tuple[float, float]:
    return nodes_by_index[(plus_index, minus_index)].point_m

  def axis_state(plus_index: int, minus_index: int) -> CharacteristicState:
    return nodes_by_index[(plus_index, minus_index)].state

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(expected_count - 1):
      if index == 0:
        shock_vertices = (
          shock_points[index],
          shock_points[index + 1],
          node_point(index + 1, 0),
        )
      else:
        shock_vertices = (
          shock_points[index],
          shock_points[index + 1],
          node_point(index + 1, 0),
          node_point(index, 0),
        )
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-shock-strip',
          vertices_xr_m=shock_vertices,
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    for index in range(expected_count - 1):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-ambient-outer-strip',
          vertices_xr_m=(
            node_point(index, index),
            node_point(index + 1, index),
            ambient_points[index + 1],
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        )
      )
    if centerline_reflection:
      assert len(axis_results) == expected_count
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-ambient-centerline-triangle',
          vertices_xr_m=(
            shock_points[-1],
            node_point(expected_count - 1, 0),
            axis_results[0].point_m,
          ),
          centerline_indices=(expected_count,),
          boundary_indices=(0,),
        )
      )
      for column in range(expected_count - 2):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='post-shock-ambient-centerline-strip',
            vertices_xr_m=(
              node_point(expected_count - 1, column),
              node_point(expected_count - 1, column + 1),
              axis_results[column + 1].point_m,
              axis_results[column].point_m,
            ),
            centerline_indices=(expected_count,),
            boundary_indices=(column, column + 1),
          )
        )
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-ambient-centerline-terminal',
          vertices_xr_m=(
            node_point(expected_count - 1, expected_count - 2),
            ambient_points[-1],
            axis_results[-1].point_m,
            axis_results[-2].point_m,
          ),
          centerline_indices=(expected_count,),
          boundary_indices=(expected_count - 2, expected_count - 1),
        )
      )
    elif len(ambient_points) == expected_count + 1:
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='post-shock-ambient-axis-corner',
          vertices_xr_m=(
            node_point(expected_count - 1, expected_count - 2),
            ambient_points[expected_count - 1],
            ambient_points[expected_count],
          ),
          centerline_indices=(expected_count - 1,),
          boundary_indices=(expected_count - 1, expected_count),
        )
      )
    for row in range(1, expected_count - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='post-shock-ambient-interior',
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
  except (KeyError, ValueError) as error:
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=tuple(cells_list),
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message=f'coupled characteristic cell geometry failed: {error}',
    )
  ####

  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      MocPhysicalPostShockFieldStatus.TOPOLOGY_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      pressure_ratios=pressure_ratios,
      message=f'coupled shock/ambient field topology failed: {topology.message}',
    )
  ####

  if centerline_reflection:
    assert len(axis_results) == expected_count
    axis_points_natural = [shock_points[-1]]
    axis_states_natural = [shock_samples[-1].state]
    axis_pressures_natural = [shock_samples[-1].downstream_total_pressure_Pa]
    axis_points_natural.extend(
      result.point_m for result in axis_results
    )
    axis_states_natural.extend(
      result.state for result in axis_results
    )
    axis_pressures_natural.extend(
      sample.total_pressure_Pa for sample in samples
    )
  else:
    axis_points_natural = [shock_points[-1]]
    axis_states_natural = [shock_samples[-1].state]
    axis_pressures_natural = [shock_samples[-1].downstream_total_pressure_Pa]
    axis_points_natural.extend(
      node_point(expected_count - 1, column)
      for column in range(expected_count - 2, -1, -1)
    )
    axis_states_natural.extend(
      axis_state(expected_count - 1, column)
      for column in range(expected_count - 2, -1, -1)
    )
    axis_pressures_natural.extend(
      shock_samples[column].downstream_total_pressure_Pa
      for column in range(expected_count - 2, -1, -1)
    )
    axis_points_natural.append(ambient_points[-1])
    axis_states_natural.append(samples[-1].state)
    axis_pressures_natural.append(samples[-1].total_pressure_Pa)
  natural_axis = (
    tuple(axis_points_natural),
    tuple(axis_states_natural),
    tuple(axis_pressures_natural),
  )
  reversed_axis = (
    tuple(reversed(axis_points_natural)),
    tuple(reversed(axis_states_natural)),
    tuple(reversed(axis_pressures_natural)),
  )
  if all(
    second[0] > first[0] + position_tolerance_m
    for first, second in zip(natural_axis[0], natural_axis[0][1:])
  ):
    axis_points, axis_states, axis_pressures = natural_axis
  elif all(
    second[0] > first[0] + position_tolerance_m
    for first, second in zip(reversed_axis[0], reversed_axis[0][1:])
  ):
    axis_points, axis_states, axis_pressures = reversed_axis
  else:
    axis_points, axis_states, axis_pressures = natural_axis
  if any(
    abs(point[1]) > position_tolerance_m or abs(state.theta_rad) > invariant_tolerance
    for point, state in zip(axis_points, axis_states, strict=True)
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.AXIS_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      message='coupled field closing perimeter does not reproduce centerline y=0 and theta=0',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    for first, second in zip(axis_points, axis_points[1:])
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.AXIS_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      message='coupled field centerline closure is not strictly downstream',
    )
  ####

  edge_counts = _edge_counts(cells, position_tolerance_m)
  if not (
    _path_edges_present(shock_points, edge_counts, position_tolerance_m)
    and _path_edges_present(ambient_points, edge_counts, position_tolerance_m)
    and _path_edges_present(axis_points, edge_counts, position_tolerance_m)
  ):
    return _failure(
      MocPhysicalPostShockFieldStatus.GEOMETRY_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      message='coupled field is missing an explicit shock, ambient, or centerline perimeter edge',
    )
  geometry_residuals = tuple(
    abs(node.point_result.geometry_residual)
    for node in nodes_by_index.values()
    if node.point_result.geometry_residual is not None
  ) + tuple(
    abs(result.geometry_residual)
    for result in axis_results
    if result.geometry_residual is not None
  )
  maximum_geometry_residual = max(geometry_residuals, default=None)
  invariant_residuals = tuple(
    abs(value)
    for node in nodes_by_index.values()
    for value in (
      node.point_result.invariant_residual_plus,
      node.point_result.invariant_residual_minus,
    )
    if value is not None
  ) + tuple(
    abs(result.invariant_residual_minus)
    for result in axis_results
    if result.invariant_residual_minus is not None
  )
  maximum_invariant_residual = max(invariant_residuals, default=None)
  characteristic_family_orientation_verified = all(
    node.point_result.converged
    and node.point_result.invariant_residual_plus is not None
    and node.point_result.invariant_residual_minus is not None
    and node.point_result.geometry_residual is not None
    for node in nodes_by_index.values()
  )
  if not characteristic_family_orientation_verified:
    return _failure(
      MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE,
      ambient_boundary=ambient_result,
      characteristic_layer_count=expected_count - 1,
      nodes=tuple(nodes_by_index.values()),
      cells=cells,
      topology=topology,
      shock_points=shock_points,
      ambient_points=ambient_points,
      axis_points=axis_points,
      axis_states=axis_states,
      axis_pressures=axis_pressures,
      pressure_ratios=pressure_ratios,
      maximum_geometry_residual_m=maximum_geometry_residual,
      maximum_absolute_invariant_residual=maximum_invariant_residual,
      message=(
        'coupled field did not retain complete C+/C- compatibility evidence '
        'for every characteristic node'
      ),
    )
  return MocPhysicalPostShockFieldResult(
    status=MocPhysicalPostShockFieldStatus.CONVERGED_AMBIENT_CLOSED,
    characteristic_layer_count=(
      expected_count if centerline_reflection else expected_count - 1
    ),
    nodes=tuple(nodes_by_index.values()),
    cells=cells,
    topology=topology,
    shock_boundary_points_m=shock_points,
    ambient_boundary_points_m=ambient_points,
    centerline_boundary_points_m=axis_points,
    centerline_boundary_states=axis_states,
    centerline_boundary_total_pressure_Pa=axis_pressures,
    ambient_boundary=ambient_result,
    maximum_geometry_residual_m=maximum_geometry_residual,
    maximum_absolute_invariant_residual=maximum_invariant_residual,
    minimum_post_shock_total_pressure_ratio=min(pressure_ratios),
    maximum_post_shock_total_pressure_ratio=max(pressure_ratios),
    message=(
      'ambient-pressure outer boundary, fitted shock, and centerline closing '
      'perimeter converged through a coupled triangular characteristic field '
      'with verified shock-C+/ambient-C- family orientation'
    ),
    characteristic_family_orientation_verified=characteristic_family_orientation_verified,
    incoming_handoff_states=incoming_states,
    incoming_handoff_total_pressure_Pa=incoming_pressures,
    upstream_shock_boundary_states=upstream_shock_states,
    upstream_shock_boundary_total_pressure_Pa=upstream_shock_pressures,
    post_shock_boundary_states=tuple(sample.state for sample in shock_samples),
    post_shock_boundary_total_pressure_Pa=tuple(
      sample.downstream_total_pressure_Pa for sample in shock_samples
    ),
    zero_strength_shock_start_allowed=zero_strength_start,
    zero_strength_shock_endpoints_allowed=zero_strength_endpoints,
  )


def assemble_ambient_boundary_post_shock_field_with_centerline_reflection(
  shock_fit: MocShockBoundaryFitResult,
  ambient_boundary: Sequence[MocAmbientBoundarySample],
  ambient_pressure_Pa: float,
  *,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  allow_zero_strength_shock_start: bool = False,
  allow_zero_strength_endpoints: bool = False,
) -> MocPhysicalPostShockFieldResult:
  """Assemble an ambient-closed field with explicit C− axis reflection.

  The ordinary assembler retains an open terminal characteristic strip for
  boundary-conditioned diagnostics.  This entry point selects the physical
  closure mode: each ambient C− source is continued to the symmetry line,
  and the resulting axis cells are added to the mesh.  The ambient boundary
  must therefore contain only the physical shock-to-outer samples; an
  appended geometric axis corner is rejected rather than treated as another
  characteristic source.
  """

  return assemble_ambient_boundary_post_shock_field(
    shock_fit,
    ambient_boundary,
    ambient_pressure_Pa,
    incoming_handoff=incoming_handoff,
    centerline_reflection=True,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    allow_zero_strength_shock_start=allow_zero_strength_shock_start,
    allow_zero_strength_endpoints=allow_zero_strength_endpoints,
  )


def solve_ambient_closed_post_shock_terminal_patch_transition(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_field: MocPhysicalPostShockFieldResult,
  *,
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 1.0e-3,
  seam_position_tolerance_m: float = 3.0e-3,
  position_tolerance_m: float = 1.0e-3,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocPhysicalPostShockTerminalPatchTransitionResult:
  """Continue an accepted field through a reflected terminal patch.

  This is the solver-owned continuation seam for the current planar lane:

  ``closed physical field -> open shock/ambient strip -> centerline patch
  -> next attached shock -> typed normal-shock terminal``.

  The source field is not copied into a second cell.  Its open submesh is
  projected only to provide the terminal ``C+`` trace needed by the reflection
  patch, and the subsequent shock is sampled only inside that patch.  A
  completed supersonic field is not promoted here because the supplied
  downstream angle is still a research condition and the mixed-regime
  subsonic field is intentionally outside this MOC chain.  The only accepted
  chain outcome from this adapter is therefore a typed physical termination;
  incomplete or out-of-domain attempts return a non-physical stop.

  The outer end of the reflected patch is allowed to coincide with the
  current cell's axial interface.  That is the physical shared boundary for
  this construction; the older terminal-patch cell adapter continues to
  require a strictly downstream start because it consumes a pre-existing
  terminal-trace cell instead of deriving the patch from a closed field.
  """

  source_strip: MocAmbientShockStripResult | None = None
  reflection_patch: MocTerminalReflectionPatchResult | None = None
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None = None
  terminal_field: 'MocTerminalShockCellFieldResult | None' = None
  mixed_regime_request: MocMixedRegimePerimeterRequest | None = None

  def decision(
    reason: MocChainTerminationReason,
    message: str,
    diagnostics: dict[str, Any] | None = None,
    *,
    physical_termination: bool = False,
  ) -> MocPhysicalPostShockTerminalPatchTransitionResult:
    return MocPhysicalPostShockTerminalPatchTransitionResult(
      decision=MocChainTerminationDecision(
        physical_termination=physical_termination,
        reason=reason,
        message=message,
        diagnostics={} if diagnostics is None else diagnostics,
      ),
      source_strip=source_strip,
      reflection_patch=reflection_patch,
      downstream_shock=downstream_shock,
      terminal_field=terminal_field,
      mixed_regime_request=mixed_regime_request,
    )

  if not isinstance(current_cell, MocChainCell):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'current_cell must be a MocChainCell',
    )
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'next_cell_index must immediately follow current_cell.cell_index',
    )
  if not current_cell.resolved:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'terminal-patch continuation requires a resolved physical current cell',
    )
  if not isinstance(upstream_field, MocPhysicalPostShockFieldResult):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'upstream_field must be a MocPhysicalPostShockFieldResult',
    )
  if not upstream_field.converged or not upstream_field.physical_closure_verified:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'upstream physical field is not physically closed; no terminal patch was assembled',
      {'upstream_field_status': upstream_field.status.value},
    )
  if not upstream_field.state_sampling_available:
    return decision(
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      'upstream physical field has no complete bounded state/pressure sampler',
      {'upstream_field_status': upstream_field.status.value},
    )
  if not upstream_field.upstream_shock_coupling_verified:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'upstream physical field has no retained fitted upstream shock samples',
    )
  if current_cell.continuation_boundary_kind is not MocChainBoundaryKind.CENTERLINE_TRACE:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'terminal-patch physical-field continuation requires a centerline-trace handoff',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'incoming_handoff must contain MocChainBoundarySample values',
    )
  if handoff != current_cell.continuation_boundary:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'incoming_handoff must exactly match the current physical cell boundary',
    )
  expected_handoff = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      upstream_field.centerline_boundary_states,
      upstream_field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  if handoff != expected_handoff:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'incoming_handoff does not match the bounded upstream physical field',
    )
  if len(handoff) < 3:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'terminal-patch physical-field continuation requires at least three handoff samples',
    )
  if not isinstance(branch, ShockBranch):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'branch must be a ShockBranch',
    )
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'supply exactly one downstream flow-angle provider',
    )
  if downstream_flow_angle_rad is not None and not isfinite(float(downstream_flow_angle_rad)):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'downstream_flow_angle_rad must be finite',
    )
  if (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'sample_count must be an integer of at least three',
    )
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'maximum_segment_iterations must be a positive integer',
    )
  for name, value in (
    ('trace_position_tolerance_m', trace_position_tolerance_m),
    ('seam_position_tolerance_m', seam_position_tolerance_m),
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('end_x_m', end_x_m),
  ):
    try:
      numeric_value = float(value)
    except (TypeError, ValueError):
      numeric_value = float('nan')
    if not isfinite(numeric_value) or (
      numeric_value <= 0.0
      if name != 'end_x_m'
      else numeric_value <= current_cell.end_x_m + float(position_tolerance_m)
    ):
      return decision(
        MocChainTerminationReason.INVALID_INPUT,
        f'{name} must be finite and valid for terminal-patch continuation',
      )
  if not isfinite(float(target_centerline_y_m)):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'target_centerline_y_m must be finite',
    )
  if abs(float(target_centerline_y_m)) > position_tolerance_m:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'terminal reflection patch continuation currently targets y=0 only',
    )

  try:
    source_strip = upstream_field.as_open_shock_ambient_strip(
      trace_position_tolerance_m=trace_position_tolerance_m,
      trace_invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'accepted physical field could not expose a terminal shock/ambient source strip',
      {
        'termination_model': 'ambient-closed-physical-field-terminal-reflection',
        'source_strip_status': 'projection-failure',
        'source_strip_message': str(error),
        'next_cell_index': next_cell_index,
      },
    )
  try:
    patch = assemble_terminal_trace_centerline_patch(
      source_strip,
      trace_position_tolerance_m=trace_position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'terminal trace centerline reflection raised before a next shock was solved',
      {
        'termination_model': 'ambient-closed-physical-field-terminal-reflection',
        'source_strip_report': source_strip.as_report(),
        'reflection_patch_status': 'assembly-failure',
        'reflection_patch_message': str(error),
        'next_cell_index': next_cell_index,
      },
    )
  reflection_patch = patch
  seam_position_tolerance = float(seam_position_tolerance_m)
  common_diagnostics: dict[str, Any] = {
    'termination_model': 'ambient-closed-physical-field-terminal-reflection',
    'upstream_field_model': 'accepted-ambient-closed-field-open-terminal-trace',
    'source_strip_report': source_strip.as_report(),
    'reflection_patch_report': patch.as_report(),
    'incoming_handoff_sample_count': len(handoff),
    'outgoing_handoff_sample_count': len(patch.outgoing_trace_samples),
    'trace_position_tolerance_m': float(trace_position_tolerance_m),
    'seam_position_tolerance_m': seam_position_tolerance,
    'position_tolerance_m': float(position_tolerance_m),
    'invariant_tolerance': float(invariant_tolerance),
    'next_cell_index': next_cell_index,
  }
  if not isinstance(patch, MocTerminalReflectionPatchResult) or not patch.converged:
    common_diagnostics.update({
      'reflection_patch_status': patch.status.value,
      'reflection_patch_message': patch.message,
    })
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'terminal reflection patch did not converge; no next shock was fitted',
      common_diagnostics,
    )

  state_tolerance = max(float(invariant_tolerance), 1.0e-8)
  expected_axis = tuple(
    zip(
      upstream_field.centerline_boundary_points_m,
      upstream_field.centerline_boundary_states,
      upstream_field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  actual_axis = tuple(
    zip(
      patch.axis_points_m,
      patch.axis_states,
      patch.axis_total_pressure_Pa,
      strict=True,
    )
  )
  seam_error: str | None = None
  if len(actual_axis) != len(expected_axis):
    seam_error = (
      'centerline reflection patch changed the physical field axis sample '
      f'count from {len(expected_axis)} to {len(actual_axis)}'
    )
  else:
    for index, (expected, actual) in enumerate(zip(expected_axis, actual_axis, strict=True)):
      expected_point, expected_state, expected_pressure = expected
      actual_point, actual_state, actual_pressure = actual
      if any(
        abs(first - second) > seam_position_tolerance
        for first, second in zip(expected_point, actual_point, strict=True)
      ):
        seam_error = f'centerline reflection changed axis point {index}'
        break
      if any(
        abs(first - second) > state_tolerance
        for first, second in (
          (expected_state.theta_rad, actual_state.theta_rad),
          (expected_state.mach, actual_state.mach),
          (expected_state.gamma, actual_state.gamma),
        )
      ):
        seam_error = f'centerline reflection changed axis state {index}'
        break
      if abs(expected_pressure - actual_pressure) > state_tolerance * max(
        1.0,
        abs(expected_pressure),
        abs(actual_pressure),
      ):
        seam_error = f'centerline reflection changed axis total pressure {index}'
        break
  if seam_error is not None:
    common_diagnostics.update({
      'centerline_seam_verified': False,
      'centerline_seam_error': seam_error,
    })
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'terminal reflection patch did not preserve the accepted field centerline seam',
      common_diagnostics,
    )
  common_diagnostics['centerline_seam_verified'] = True

  start_point = patch.outgoing_trace_points_m[0]
  if start_point[0] < current_cell.end_x_m - position_tolerance_m:
    common_diagnostics.update({
      'first_outgoing_trace_point_m': start_point,
      'current_end_x_m': current_cell.end_x_m,
    })
    return decision(
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      'terminal reflection patch begins upstream of the current cell interface',
      common_diagnostics,
    )
  try:
    solved = solve_marched_attached_shock_from_terminal_reflection_patch(
      patch,
      start_point,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      incoming_handoff=patch.outgoing_trace_samples,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    common_diagnostics.update({
      'downstream_shock_status': 'solve-failure',
      'downstream_shock_message': str(error),
    })
    return decision(
      MocChainTerminationReason.SOLVER_ERROR,
      'terminal-patch downstream shock solve raised; no physical endpoint was inferred',
      common_diagnostics,
    )
  downstream_shock = solved
  common_diagnostics['downstream_shock_report'] = solved.as_report()
  if solved.physical_terminal_verified:
    terminal = solved.shock.normal_shock_terminal
    if terminal is None:
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'terminal-patch shock reported a physical stop without normal-shock diagnostics',
        common_diagnostics,
      )
    if terminal.shock_point_m[0] > float(end_x_m) + float(position_tolerance_m):
      common_diagnostics.update({
        'terminal_shock_point_m': terminal.shock_point_m,
        'requested_end_x_m': float(end_x_m),
      })
      return decision(
        MocChainTerminationReason.AXIAL_DOMAIN_LIMIT,
        'verified terminal shock lies beyond the requested continuation interval',
        common_diagnostics,
      )
    try:
      # Keep this import local because shock_chain imports the coupled solver,
      # which imports this module during package initialization.
      from exhaust_plume.models.moc.shock_chain import (
        assemble_terminal_shock_cell_field,
      )

      terminal_field = assemble_terminal_shock_cell_field(
        source_strip,
        patch,
        solved,
        target_centerline_y_m=target_centerline_y_m,
        # The chain seam uses a millimetre-scale tolerance for the projected
        # field/patch axis coordinates.  Mesh validity must remain at the
        # smaller geometric scale, otherwise the first source-strip cells can
        # be classified as zero-area merely because they are narrow.
        position_tolerance_m=1.0e-9,
        mesh_vertex_tolerance_m=1.0e-9,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      common_diagnostics.update({
        'terminal_field_status': 'assembly-failure',
        'terminal_field_message': str(error),
      })
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'verified terminal shock did not produce a closed supersonic terminal field',
        common_diagnostics,
      )
    common_diagnostics['terminal_field_report'] = terminal_field.as_report()
    if not terminal_field.converged or not terminal_field.supersonic_region_closed:
      common_diagnostics.update({
        'terminal_field_status': terminal_field.status.value,
        'terminal_field_message': terminal_field.message,
      })
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'verified terminal shock reached a boundary, but its supersonic field remained open',
        common_diagnostics,
      )
    try:
      mixed_regime_request = terminal_field.mixed_regime_perimeter_request()
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      common_diagnostics.update({
        'mixed_regime_request_status': 'assembly-failure',
        'mixed_regime_request_message': str(error),
      })
      return decision(
        MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
        'closed supersonic terminal field did not expose a complete mixed-regime seam',
        common_diagnostics,
      )
    common_diagnostics.update({
      'mixed_regime_request_available': True,
      'mixed_regime_request_report': mixed_regime_request.as_report(),
    })
    terminal_decision = solved.as_physical_termination_decision()
    diagnostics = dict(terminal_decision.diagnostics)
    diagnostics.update(common_diagnostics)
    diagnostics.update({
      'terminal_shock_point_m': terminal.shock_point_m,
      'requested_end_x_m': float(end_x_m),
      'physical_terminal_verified': True,
      'chain_cell_promotion': 'blocked-at-mixed-regime-boundary',
    })
    return decision(
      MocChainTerminationReason.PHYSICAL_TERMINATION,
      (
        'continued reflected physical field reached a verified normal-shock '
        'terminal; the unresolved subsonic mixed-regime field remains outside '
        'the supersonic shock-cell chain'
      ),
      diagnostics,
      physical_termination=True,
    )
  common_diagnostics.update({
    'physical_terminal_verified': False,
    'downstream_shock_status': solved.shock.status.value,
    'downstream_coupling_status': solved.coupling.status.value,
  })
  if (
    solved.shock.status.value == 'upstream_field_failure'
    or solved.coupling.status is MocTerminalPatchShockCouplingStatus.OUTSIDE_DOMAIN
  ):
    return decision(
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      'continued shock left the finite terminal reflection patch; no extrapolation or physical endpoint was inferred',
      common_diagnostics,
    )
  return decision(
    MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
    'continued shock did not produce a verified terminal or a complete next cell; no physical endpoint was inferred',
    common_diagnostics,
  )


def solve_ambient_closed_post_shock_chain_cell_from_physical_field_terminal_patch_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_field: MocPhysicalPostShockFieldResult,
  *,
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 1.0e-3,
  seam_position_tolerance_m: float = 3.0e-3,
  position_tolerance_m: float = 1.0e-3,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocChainTerminationDecision:
  """Return only the typed chain decision from the retained transition.

  The richer transition result is the object-level API for downstream
  mixed-regime planning.  This compatibility entry point preserves the
  existing chain callback contract for callers that only need a cell-or-stop
  decision.
  """

  result = solve_ambient_closed_post_shock_terminal_patch_transition(
    current_cell,
    next_cell_index,
    incoming_handoff,
    upstream_field,
    end_x_m=end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_flow_angle_at,
    downstream_flow_angle_rad=downstream_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    trace_position_tolerance_m=trace_position_tolerance_m,
    seam_position_tolerance_m=seam_position_tolerance_m,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  return result.decision


def solve_ambient_closed_post_shock_chain_cell_from_terminal_reflection_patch_ambient_closure_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_field: MocPhysicalPostShockFieldResult,
  *,
  end_x_m: float,
  outer_downstream_flow_angle_lower_rad: float = -0.2,
  outer_downstream_flow_angle_upper_rad: float = 0.2,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  trace_position_tolerance_m: float = 4.0e-4,
  trace_forward_tolerance_m: float = 1.0e-4,
  seam_position_tolerance_m: float = 5.0e-3,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  allow_zero_strength_attachment: bool = True,
) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
  """Solve one next physical cell from a reflected terminal patch.

  This is the first chain adapter for the solver-owned downstream lane:

  ``accepted closed field -> reflected patch -> ambient-closed next field``.

  The patch is derived from the accepted field and is used as a bounded
  upstream state/pressure source.  The next field is accepted only when the
  exact patch handoff, ambient perimeter, centerline reflection, state
  sampling, and fitted-upstream-shock coupling all pass.  The requested
  ``end_x_m`` is an axial limit, not a fabricated interface; the returned
  continuation endpoint is the next field's actual downstream ambient-boundary
  endpoint.  This function is a research-lane solver and does not authorize a
  production provider.

  ``allow_zero_strength_attachment`` is intentionally explicit and defaults
  on only for this named reflected-patch lane.  It permits the ambient-matched
  patch seam to start as a Mach wave and does not relax the strict loss gate at
  interior samples.
  """

  def decision(
    reason: MocChainTerminationReason,
    message: str,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={} if diagnostics is None else diagnostics,
    )

  if not isinstance(current_cell, MocChainCell):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'current_cell must be a MocChainCell',
    )
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'next_cell_index must immediately follow current_cell.cell_index',
    )
  if not current_cell.resolved:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'ambient-closed terminal-patch continuation requires a resolved current cell',
    )
  if not isinstance(upstream_field, MocPhysicalPostShockFieldResult):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'upstream_field must be a MocPhysicalPostShockFieldResult',
    )
  if not upstream_field.converged or not upstream_field.physical_closure_verified:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'upstream physical field is not physically closed; no reflected patch was promoted',
      {'upstream_field_status': upstream_field.status.value},
    )
  if not upstream_field.state_sampling_available:
    return decision(
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      'upstream physical field has no complete bounded state/pressure sampler',
      {'upstream_field_status': upstream_field.status.value},
    )
  if not upstream_field.upstream_shock_coupling_verified:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'upstream physical field has no retained fitted upstream shock samples',
    )
  if current_cell.continuation_boundary_kind is not MocChainBoundaryKind.CENTERLINE_TRACE:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'ambient-closed terminal-patch continuation requires a centerline-trace handoff',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'incoming_handoff must contain MocChainBoundarySample values',
    )
  if handoff != current_cell.continuation_boundary:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'incoming_handoff must exactly match the current physical cell boundary',
    )
  if len(upstream_field.centerline_boundary_states) != len(
    upstream_field.centerline_boundary_total_pressure_Pa
  ):
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'upstream physical field has mismatched centerline state and pressure samples',
    )
  expected_handoff = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      upstream_field.centerline_boundary_states,
      upstream_field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  if handoff != expected_handoff:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'incoming_handoff does not match the bounded upstream physical field',
    )
  if len(handoff) < 3:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'ambient-closed terminal-patch continuation requires at least three handoff samples',
    )
  if not isinstance(branch, ShockBranch):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'branch must be a ShockBranch',
    )
  if not isinstance(allow_zero_strength_attachment, bool):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'allow_zero_strength_attachment must be a bool',
    )
  if (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'sample_count must be an integer of at least three',
    )
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'maximum_segment_iterations must be a positive integer',
    )
  if (
    isinstance(maximum_boundary_iterations, bool)
    or not isinstance(maximum_boundary_iterations, int)
    or maximum_boundary_iterations < 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'maximum_boundary_iterations must be a positive integer',
    )
  if (
    isinstance(maximum_shooting_iterations, bool)
    or not isinstance(maximum_shooting_iterations, int)
    or maximum_shooting_iterations < 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'maximum_shooting_iterations must be a positive integer',
    )
  try:
    requested_end = float(end_x_m)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'end point, outer angle bracket, and centerline target must be numeric',
    )
  for name, value in (
    ('trace_position_tolerance_m', trace_position_tolerance_m),
    ('trace_forward_tolerance_m', trace_forward_tolerance_m),
    ('seam_position_tolerance_m', seam_position_tolerance_m),
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('attachment_pressure_tolerance', attachment_pressure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    try:
      value = float(value)
    except (TypeError, ValueError):
      value = float('nan')
    if not isfinite(value) or value <= 0.0:
      return decision(
        MocChainTerminationReason.INVALID_INPUT,
        f'{name} must be finite and positive',
      )
  trace_position_tolerance = float(trace_position_tolerance_m)
  trace_forward_tolerance = float(trace_forward_tolerance_m)
  seam_position_tolerance = float(seam_position_tolerance_m)
  position_tolerance = float(position_tolerance_m)
  invariant_tolerance = float(invariant_tolerance)
  attachment_pressure_tolerance = float(attachment_pressure_tolerance)
  pressure_tolerance = float(pressure_tolerance)
  tangent_tolerance = float(tangent_tolerance)
  shock_angle_tolerance = float(shock_angle_tolerance_rad)
  if (
    not isfinite(requested_end)
    or requested_end <= current_cell.end_x_m + position_tolerance
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'end_x_m must be finite and downstream of the current cell interface',
    )
  if not all(isfinite(value) for value in (lower_angle, upper_angle, target_y, target_angle)):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'outer angle bracket and centerline target must be finite',
    )
  if lower_angle >= upper_angle:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'outer downstream flow-angle lower bound must be below its upper bound',
    )
  if abs(target_y) > position_tolerance or abs(target_angle) > tangent_tolerance:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'terminal-reflection ambient closure currently targets y=0 and theta=0',
    )

  ambient_pressure = upstream_field.ambient_boundary.ambient_pressure_Pa
  if ambient_pressure is None or not isfinite(float(ambient_pressure)) or ambient_pressure <= 0.0:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'upstream physical field does not retain a finite ambient pressure',
    )

  source_strip: MocAmbientShockStripResult | None = None
  reflection_patch: MocTerminalReflectionPatchResult | None = None
  common_diagnostics: dict[str, Any] = {
    'termination_model': (
      'ambient-closed-physical-field-terminal-reflection-ambient-closure'
    ),
    'upstream_field_model': 'accepted-ambient-closed-field-open-terminal-trace',
    'next_cell_index': next_cell_index,
    'requested_end_x_m': requested_end,
    'outer_flow_angle_bracket': (lower_angle, upper_angle),
    'target_centerline_y_m': target_y,
    'target_centerline_flow_angle_rad': target_angle,
    'sample_count': sample_count,
    'branch': branch.value,
    'trace_position_tolerance_m': trace_position_tolerance,
    'trace_forward_tolerance_m': trace_forward_tolerance,
    'seam_position_tolerance_m': seam_position_tolerance,
    'position_tolerance_m': position_tolerance,
    'invariant_tolerance': invariant_tolerance,
    'attachment_pressure_tolerance': attachment_pressure_tolerance,
    'pressure_tolerance': pressure_tolerance,
    'tangent_tolerance': tangent_tolerance,
    'shock_angle_tolerance_rad': shock_angle_tolerance,
    'allow_zero_strength_attachment': allow_zero_strength_attachment,
    'incoming_handoff_sample_count': len(handoff),
    'ambient_pressure_Pa': float(ambient_pressure),
    'production_claim_allowed': False,
  }

  try:
    source_strip = upstream_field.as_open_shock_ambient_strip(
      trace_position_tolerance_m=trace_position_tolerance,
      trace_forward_tolerance_m=trace_forward_tolerance,
      trace_invariant_tolerance=invariant_tolerance,
    )
    common_diagnostics['source_strip_report'] = source_strip.as_report()
    reflection_patch = assemble_terminal_trace_centerline_patch(
      source_strip,
      trace_position_tolerance_m=trace_position_tolerance,
      trace_forward_tolerance_m=trace_forward_tolerance,
      invariant_tolerance=invariant_tolerance,
    )
    common_diagnostics['reflection_patch_report'] = reflection_patch.as_report()
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    common_diagnostics.update({
      'source_projection_status': 'failed',
      'source_projection_error': str(error),
    })
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'accepted physical field could not produce a reflected terminal patch',
      common_diagnostics,
    )
  if not reflection_patch.converged:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'terminal reflection patch did not converge; no next physical field was fitted',
      common_diagnostics,
    )

  state_tolerance = max(float(invariant_tolerance), 1.0e-8)
  expected_axis = tuple(
    zip(
      upstream_field.centerline_boundary_points_m,
      upstream_field.centerline_boundary_states,
      upstream_field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  actual_axis = tuple(
    zip(
      reflection_patch.axis_points_m,
      reflection_patch.axis_states,
      reflection_patch.axis_total_pressure_Pa,
      strict=True,
    )
  )
  seam_error: str | None = None
  if len(actual_axis) != len(expected_axis):
    seam_error = (
      'centerline reflection patch changed the physical field axis sample '
      f'count from {len(expected_axis)} to {len(actual_axis)}'
    )
  else:
    for index, (expected, actual) in enumerate(
      zip(expected_axis, actual_axis, strict=True)
    ):
      expected_point, expected_state, expected_pressure = expected
      actual_point, actual_state, actual_pressure = actual
      if any(
        abs(first - second) > seam_position_tolerance
        for first, second in zip(expected_point, actual_point, strict=True)
      ):
        seam_error = f'centerline reflection changed axis point {index}'
        break
      if any(
        abs(first - second) > state_tolerance
        for first, second in (
          (expected_state.theta_rad, actual_state.theta_rad),
          (expected_state.mach, actual_state.mach),
          (expected_state.gamma, actual_state.gamma),
        )
      ):
        seam_error = f'centerline reflection changed axis state {index}'
        break
      if abs(expected_pressure - actual_pressure) > state_tolerance * max(
        1.0,
        abs(expected_pressure),
        abs(actual_pressure),
      ):
        seam_error = f'centerline reflection changed axis total pressure {index}'
        break
  if seam_error is not None:
    common_diagnostics.update({
      'centerline_seam_verified': False,
      'centerline_seam_error': seam_error,
    })
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'terminal reflection patch did not preserve the accepted field centerline seam',
      common_diagnostics,
    )
  common_diagnostics['centerline_seam_verified'] = True

  patch_start = reflection_patch.outgoing_trace_points_m[0]
  if patch_start[0] < current_cell.end_x_m - position_tolerance:
    common_diagnostics.update({
      'first_outgoing_trace_point_m': patch_start,
      'current_end_x_m': current_cell.end_x_m,
    })
    return decision(
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      'terminal reflection patch begins upstream of the current cell interface',
      common_diagnostics,
    )

  from exhaust_plume.models.moc.coupled import (
    MocTerminalReflectionPatchPhysicalFieldStatus,
    solve_marched_attached_shock_with_ambient_centerline_physical_field_from_terminal_reflection_patch,
  )

  try:
    field_result = solve_marched_attached_shock_with_ambient_centerline_physical_field_from_terminal_reflection_patch(
      reflection_patch,
      float(ambient_pressure),
      lower_angle,
      upper_angle,
      start_point_m=patch_start,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      incoming_handoff=handoff,
      patch_handoff=reflection_patch.outgoing_trace_samples,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=float(invariant_tolerance),
      attachment_pressure_tolerance=float(attachment_pressure_tolerance),
      pressure_tolerance=float(pressure_tolerance),
      tangent_tolerance=float(tangent_tolerance),
      shock_angle_tolerance_rad=shock_angle_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    common_diagnostics.update({
      'terminal_patch_physical_field_status': 'solve-failure',
      'terminal_patch_physical_field_error': str(error),
    })
    return decision(
      MocChainTerminationReason.SOLVER_ERROR,
      'terminal-patch ambient-closure solve raised; no next field was promoted',
      common_diagnostics,
    )
  common_diagnostics['terminal_patch_physical_field_report'] = field_result.as_report()
  if field_result.status is MocTerminalReflectionPatchPhysicalFieldStatus.INVALID_INPUT:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'terminal-patch ambient-closure solve rejected its boundary contract',
      common_diagnostics,
    )
  if not field_result.converged or field_result.field is None:
    attachment = (
      None
      if field_result.field_result is None
      else field_result.field_result.ambient_attachment
    )
    shock_status = (
      None
      if attachment is None or attachment.shock is None
      else attachment.shock.status.value
    )
    if shock_status == 'upstream_field_failure':
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
      message = (
        'terminal-patch ambient-closure shock left the bounded reflected '
        'upstream patch; no extrapolation was used'
      )
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
      message = (
        'terminal-patch ambient-closure did not produce a physically closed '
        'next field; no chain cell was promoted'
      )
    return decision(reason, message, common_diagnostics)

  next_field = field_result.field
  if (
    not next_field.physical_closure_verified
    or not next_field.state_sampling_available
    or not next_field.upstream_shock_coupling_verified
  ):
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'terminal-patch ambient-closure field failed the chain promotion gates',
      common_diagnostics,
    )
  if next_field.incoming_handoff != handoff:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'terminal-patch ambient-closure field changed its exact incoming handoff',
      common_diagnostics,
    )
  if not next_field.ambient_boundary_points_m:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'terminal-patch ambient-closure field has no downstream ambient endpoint',
      common_diagnostics,
    )
  next_end_x = float(next_field.ambient_boundary_points_m[-1][0])
  common_diagnostics.update({
    'next_field_end_x_m': next_end_x,
    'next_field_end_point_m': next_field.ambient_boundary_points_m[-1],
    'next_field_physical_closure_verified': next_field.physical_closure_verified,
    'next_field_state_sampling_available': next_field.state_sampling_available,
    'next_field_upstream_coupling_verified': next_field.upstream_shock_coupling_verified,
    'outgoing_handoff_sample_count': len(next_field.centerline_boundary_states),
  })
  if not isfinite(next_end_x) or next_end_x <= current_cell.end_x_m + position_tolerance:
    return decision(
      MocChainTerminationReason.GEOMETRY_FAILURE,
      'terminal-patch ambient-closure field did not end downstream of the current interface',
      common_diagnostics,
    )
  if next_end_x > requested_end + position_tolerance:
    return decision(
      MocChainTerminationReason.AXIAL_DOMAIN_LIMIT,
      'terminal-patch ambient-closure field extends beyond the requested axial limit',
      common_diagnostics,
    )
  try:
    return MocPhysicalPostShockFieldContinuationSolve(
      field=next_field,
      end_x_m=next_end_x,
    )
  except (TypeError, ValueError) as error:
    common_diagnostics['continuation_solve_error'] = str(error)
    return decision(
      MocChainTerminationReason.GEOMETRY_FAILURE,
      'terminal-patch ambient-closure field could not become a continuation solve',
      common_diagnostics,
    )


def _physical_chain_failure(
  status: MocChainStatus,
  reason: MocChainTerminationReason,
  *,
  message: str,
) -> MocChainResult:
  return MocChainResult(
    cells=(),
    status=status,
    termination_reason=reason,
    physical_termination=False,
    message=message,
  )


def _validate_physical_field_handoff(
  current: MocChainCell,
  next_field: MocPhysicalPostShockFieldResult,
  *,
  position_tolerance_m: float,
  state_tolerance: float,
) -> str | None:
  expected = current.continuation_boundary
  consumed = next_field.incoming_handoff
  if not consumed:
    return (
      'next ambient-closed physical field does not record the prior '
      'centerline handoff'
    )
  if len(consumed) != len(expected):
    return 'next physical field incoming handoff length does not match the current boundary'
  for index, (expected_sample, consumed_sample) in enumerate(
    zip(expected, consumed, strict=True)
  ):
    expected_state = expected_sample.state
    consumed_state = consumed_sample.state
    if (
      abs(expected_state.x_m - consumed_state.x_m) > position_tolerance_m
      or abs(expected_state.y_m - consumed_state.y_m) > position_tolerance_m
      or abs(expected_state.theta_rad - consumed_state.theta_rad) > state_tolerance
      or abs(expected_state.mach - consumed_state.mach) > state_tolerance
      or abs(expected_state.gamma - consumed_state.gamma) > state_tolerance
    ):
      return f'next physical field changed consumed state sample {index}'
    if abs(expected_sample.total_pressure_Pa - consumed_sample.total_pressure_Pa) > (
      state_tolerance
      * max(
        1.0,
        abs(expected_sample.total_pressure_Pa),
        abs(consumed_sample.total_pressure_Pa),
      )
    ):
      return f'next physical field changed consumed total pressure sample {index}'
  return None


def solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_field: MocPhysicalPostShockFieldResult,
  *,
  shock_points_m: Sequence[tuple[float, float]],
  downstream_flow_angles_rad: Sequence[float],
  ambient_boundary: Sequence[MocAmbientBoundarySample],
  ambient_pressure_Pa: float,
  end_x_m: float,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
  """Fit and assemble one next cell from a bounded physical MOC field.

  ``upstream_field`` is the only source for the next shock's upstream state
  and pressure.  The candidate shock curve and ambient-pressure perimeter are
  explicit inputs because this adapter does not yet contain the canonical
  reflected-domain/free-boundary shooter.  The ambient perimeter must contain
  exactly one physical sample per candidate shock sample; centerline corners
  are generated by the solver-owned reflection step.  A missing sample returns a typed
  ``UPSTREAM_FIELD_BOUNDARY`` stop; a failed physical perimeter returns an
  ``OPEN_PHYSICAL_CLOSURE`` stop.  Neither condition fabricates a resolved
  cell or extrapolates the preceding field.
  """

  def decision(
    reason: MocChainTerminationReason,
    message: str,
    diagnostics: dict[str, Any] | None = None,
  ) -> MocChainTerminationDecision:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=message,
      diagnostics={} if diagnostics is None else diagnostics,
    )

  if not isinstance(current_cell, MocChainCell):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'current_cell must be a MocChainCell',
    )
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'next_cell_index must immediately follow current_cell.cell_index',
    )
  if not isinstance(upstream_field, MocPhysicalPostShockFieldResult):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'upstream_field must be a MocPhysicalPostShockFieldResult',
    )
  if not upstream_field.converged or not upstream_field.physical_closure_verified:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      'upstream physical field is not physically closed; no next shock was fitted',
      {'upstream_field_status': upstream_field.status.value},
    )
  if not upstream_field.state_sampling_available:
    return decision(
      MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      'upstream physical field has no complete bounded state/pressure sampler',
      {'upstream_field_status': upstream_field.status.value},
    )
  if current_cell.continuation_boundary_kind is not MocChainBoundaryKind.CENTERLINE_TRACE:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'physical-field continuation requires a centerline-trace handoff',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'incoming_handoff must be an iterable of MocChainBoundarySample values',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'incoming_handoff must contain MocChainBoundarySample values',
    )
  if handoff != current_cell.continuation_boundary:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'incoming_handoff must exactly match the current physical cell boundary',
    )
  expected_handoff = tuple(
    MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
    for state, pressure in zip(
      upstream_field.centerline_boundary_states,
      upstream_field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  if handoff != expected_handoff:
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'incoming_handoff does not match the bounded upstream physical field',
    )
  if len(handoff) < 3:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'physical-field continuation requires at least three handoff samples',
    )
  if not isinstance(branch, ShockBranch):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'branch must be a ShockBranch',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('ambient_pressure_Pa', ambient_pressure_Pa),
    ('end_x_m', end_x_m),
  ):
    if not isfinite(float(value)) or (
      value <= 0.0
      if name != 'end_x_m'
      else value <= current_cell.end_x_m
    ):
      return decision(
        MocChainTerminationReason.INVALID_INPUT,
        f'{name} must be finite and valid for physical-field continuation',
      )
  try:
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock_points_m
    )
    target_angles = tuple(float(angle) for angle in downstream_flow_angles_rad)
    ambient_samples = tuple(ambient_boundary)
  except (IndexError, TypeError, ValueError):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'shock points, downstream angles, and ambient boundary must be finite sequences',
    )
  if len(points) < 3 or len(points) != len(target_angles):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'the next physical cell requires at least three shock points and one angle per point',
    )
  if any(
    len(point) != 2 or not all(isfinite(float(value)) for value in point)
    for point in points
  ) or any(not isfinite(angle) for angle in target_angles):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'shock points and downstream flow angles must be finite',
    )
  if points[0][0] <= current_cell.end_x_m + position_tolerance_m:
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'the next shock must start strictly downstream of the current cell',
    )
  if any(not isinstance(sample, MocAmbientBoundarySample) for sample in ambient_samples):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'ambient_boundary must contain MocAmbientBoundarySample values',
    )
  if len(ambient_samples) != len(points):
    return decision(
      MocChainTerminationReason.INVALID_INPUT,
      'ambient_boundary must contain exactly one physical sample per shock point; '
      'an explicit axis corner is not a C- source',
    )

  upstream_states: list[CharacteristicState] = []
  upstream_pressures: list[float] = []
  for index, point in enumerate(points):
    state = upstream_field.state_at(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    pressure = upstream_field.static_pressure_at(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or pressure is None:
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        (
          'candidate next shock left the bounded upstream physical field at '
          f'sample {index}; no extrapolation was performed'
        ),
        {
          'first_missing_sample_index': index,
          'sampled_count': len(upstream_states),
          'candidate_point_m': point,
          'upstream_field_model': 'bounded-ambient-closed-physical-moc-field',
        },
      )
    if (
      abs(state.x_m - point[0]) > position_tolerance_m
      or abs(state.y_m - point[1]) > position_tolerance_m
      or not isfinite(float(pressure))
      or pressure <= 0.0
    ):
      return decision(
        MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
        f'upstream physical field returned an invalid sample at index {index}',
        {'first_missing_sample_index': index, 'sampled_count': len(upstream_states)},
      )
    upstream_states.append(state)
    upstream_pressures.append(float(pressure))

  shock_fit = fit_attached_shock_boundary(
    upstream_states,
    upstream_pressures,
    points,
    target_angles,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
  )
  if not shock_fit.converged:
    return decision(
      MocChainTerminationReason.SOLVER_ERROR,
      f'next physical shock fit failed: {shock_fit.message}',
      {
        'shock_fit_status': shock_fit.status.value,
        'shock_fit_message': shock_fit.message,
        'sampled_count': len(upstream_states),
      },
    )
  try:
    field = assemble_ambient_boundary_post_shock_field_with_centerline_reflection(
      shock_fit,
      ambient_samples,
      float(ambient_pressure_Pa),
      incoming_handoff=handoff,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return decision(
      MocChainTerminationReason.SOLVER_ERROR,
      f'next ambient-closed physical field assembly failed: {error}',
      {'shock_fit_status': shock_fit.status.value},
    )
  if not field.converged or not field.physical_closure_verified:
    return decision(
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      (
        'next shock fit did not produce a physically closed ambient perimeter '
        f'and characteristic field: {field.message}'
      ),
      {
        'field_status': field.status.value,
        'physical_closure_gates': field.physical_closure_gates,
        'shock_fit_status': shock_fit.status.value,
      },
    )
  if (
    field.incoming_handoff != handoff
    or not field.upstream_shock_coupling_verified
    or not field.state_sampling_available
  ):
    return decision(
      MocChainTerminationReason.STATE_NOT_CARRIED,
      'next physical field did not retain the exact handoff and bounded shock data',
      {
        'incoming_handoff_sample_count': len(field.incoming_handoff),
        'state_sampling_available': field.state_sampling_available,
        'upstream_shock_coupling_verified': field.upstream_shock_coupling_verified,
      },
    )
  return MocPhysicalPostShockFieldContinuationSolve(
    field=field,
    end_x_m=float(end_x_m),
  )


def solve_ambient_closed_post_shock_chain_cell_from_candidate_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_field: MocPhysicalPostShockFieldResult,
  candidate: MocAmbientClosedPostShockChainCandidate,
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
) -> MocPhysicalPostShockFieldContinuationSolve | MocChainTerminationDecision:
  """Solve one structured candidate against the accepted physical field.

  This is an adapter, not a new boundary model.  It makes the explicit
  candidate seam difficult to misuse: all upstream state and pressure data
  still come from ``upstream_field`` and the existing strict continuation
  solver retains responsibility for handoff, shock-fit, ambient-boundary,
  topology, and promotion gates.
  """

  if not isinstance(candidate, MocAmbientClosedPostShockChainCandidate):
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.INVALID_INPUT,
      message=(
        'candidate must be a MocAmbientClosedPostShockChainCandidate'
      ),
    )
  return solve_ambient_closed_post_shock_chain_cell_from_physical_field_or_termination(
    current_cell,
    next_cell_index,
    incoming_handoff,
    upstream_field,
    shock_points_m=candidate.shock_points_m,
    downstream_flow_angles_rad=candidate.downstream_flow_angles_rad,
    ambient_boundary=candidate.ambient_boundary,
    ambient_pressure_Pa=candidate.ambient_pressure_Pa,
    end_x_m=candidate.end_x_m,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
  )


def continue_ambient_closed_post_shock_chain(
  seed: MocPhysicalPostShockFieldResult,
  solve_next: Callable[
    [MocChainCell, int, tuple[MocChainBoundarySample, ...]],
    MocPhysicalPostShockFieldContinuationSolve
    | MocChainTerminationDecision
    | None,
  ],
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
  require_upstream_shock_coupling: bool = True,
) -> MocChainResult:
  """Continue only fully ambient-closed physical fields.

  The callback must return a new physical field whose assembler recorded the
  exact incoming centerline handoff.  The new field is promoted only after
  its ambient perimeter, characteristic topology, and optional upstream
  shock-coupling gate have passed.  This adapter is deliberately separate from
  the generic post-shock chain reference and cannot consume a reduced-order
  or prescribed-boundary cell.
  """

  if not isinstance(seed, MocPhysicalPostShockFieldResult):
    return _physical_chain_failure(
      MocChainStatus.INVALID_INPUT,
      MocChainTerminationReason.INVALID_INPUT,
      message='seed must be a MocPhysicalPostShockFieldResult',
    )
  if not seed.converged or not seed.physical_closure_verified:
    return _physical_chain_failure(
      MocChainStatus.OPEN_CELL,
      MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'ambient-closed physical-field continuation requires a converged '
        f'physically closed seed: {seed.message}'
      ),
    )
  if not callable(solve_next):
    return _physical_chain_failure(
      MocChainStatus.INVALID_INPUT,
      MocChainTerminationReason.INVALID_INPUT,
      message='solve_next must be callable',
    )
  if not isinstance(require_upstream_shock_coupling, bool):
    return _physical_chain_failure(
      MocChainStatus.INVALID_INPUT,
      MocChainTerminationReason.INVALID_INPUT,
      message='require_upstream_shock_coupling must be a bool',
    )
  try:
    start = float(start_x_m)
    end = float(end_x_m)
  except (TypeError, ValueError):
    return _physical_chain_failure(
      MocChainStatus.INVALID_INPUT,
      MocChainTerminationReason.INVALID_INPUT,
      message='start_x_m and end_x_m must be numeric',
    )
  if not isfinite(start) or start < 0.0 or not isfinite(end) or end <= start:
    return _physical_chain_failure(
      MocChainStatus.INVALID_INPUT,
      MocChainTerminationReason.INVALID_INPUT,
      message='end_x_m must be finite and strictly downstream of start_x_m',
    )
  if policy is None:
    policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not policy.require_state_carry:
    policy = MocChainContinuationPolicy(
      max_cells=policy.max_cells,
      max_axial_distance_m=policy.max_axial_distance_m,
      position_tolerance_m=policy.position_tolerance_m,
      state_tolerance=policy.state_tolerance,
      allowed_fidelities=policy.allowed_fidelities,
      require_state_carry=True,
    )
  try:
    seed_cell = (
      seed.as_coupled_chain_cell(
        start_x_m=start,
        end_x_m=end,
        cell_index=1,
      )
      if require_upstream_shock_coupling
      else seed.as_chain_cell(
        start_x_m=start,
        end_x_m=end,
        cell_index=1,
      )
    )
  except (TypeError, ValueError) as error:
    return _physical_chain_failure(
      MocChainStatus.STATE_BOUNDARY,
      MocChainTerminationReason.STATE_NOT_CARRIED,
      message=f'physical-field chain seed has no usable state carry: {error}',
    )

  def solve_cell(
    current: MocChainCell,
    cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision | None:
    try:
      solved = solve_next(current, cell_index, current.continuation_boundary)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      raise ValueError(f'ambient-closed physical-field solve failed: {error}') from error
    if solved is None or isinstance(solved, MocChainTerminationDecision):
      return solved
    if not isinstance(solved, MocPhysicalPostShockFieldContinuationSolve):
      raise ValueError(
        'solve_next must return MocPhysicalPostShockFieldContinuationSolve, '
        'MocChainTerminationDecision, or None'
      )
    field = solved.field
    if not field.converged or not field.physical_closure_verified:
      raise ValueError(
        'next ambient-closed physical field is not physically closed: '
        f'{field.message}'
      )
    handoff_error = _validate_physical_field_handoff(
      current,
      field,
      position_tolerance_m=policy.position_tolerance_m,
      state_tolerance=policy.state_tolerance,
    )
    if handoff_error is not None:
      raise ValueError(handoff_error)
    if solved.end_x_m <= current.end_x_m + policy.position_tolerance_m:
      raise ValueError(
        'continued ambient-closed physical field must end strictly downstream '
        'of the current cell'
      )
    try:
      return (
        field.as_coupled_chain_cell(
          start_x_m=current.end_x_m,
          end_x_m=solved.end_x_m,
          cell_index=cell_index,
        )
        if require_upstream_shock_coupling
        else field.as_chain_cell(
          start_x_m=current.end_x_m,
          end_x_m=solved.end_x_m,
          cell_index=cell_index,
        )
      )
    except (TypeError, ValueError) as error:
      raise ValueError(
        f'next ambient-closed physical field could not become a chain cell: {error}'
      ) from error

  return continue_moc_cell_chain(seed_cell, solve_cell, policy)
