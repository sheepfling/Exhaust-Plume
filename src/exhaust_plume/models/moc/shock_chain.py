"""Staged shock-cell transitions for the isolated planar-MOC lane.

This module composes the research primitives that form one physical
shock-cell transition: ambient-matched shock attachment, the physical
shock/ambient characteristic strip, centerline reflection, and a
domain-bounded next-shock probe.  It intentionally does not manufacture a
closed cell.  A transition can expose a typed next-shock handoff or a
verified normal-shock chain stop, while unresolved downstream closure remains
outside the resolved-cell provider contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import hypot, isfinite
from typing import Callable, Sequence, cast

from exhaust_plume.models.moc.ambient_shock_strip import MocAmbientShockStripResult
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.coupled import (
  MocAmbientAttachmentResult,
  MocAmbientAttachmentStatus,
  solve_marched_attached_shock_with_ambient_attachment_closure,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeBoundaryResult,
  MocMixedRegimeClosureResult,
  MocMixedRegimeDownstreamConditionKind,
  MocMixedRegimeDownstreamConditionResult,
  MocMixedRegimeFieldResult,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
  run_mixed_regime_closure_solver,
  validate_mixed_regime_boundary as validate_scalar_mixed_regime_boundary,
  validate_mixed_regime_downstream_condition,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockBoundaryState,
  MocPostShockCharacteristicZoneResult,
  MocPostShockContinuationResult,
  MocPostShockFirstLayerResult,
  assemble_post_shock_characteristic_zone,
  assemble_post_shock_first_layer,
  continue_post_shock_characteristics_to_centerline_open,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  assemble_terminal_trace_centerline_patch,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  MocTerminalReflectionPatchShockSolveResult,
  solve_marched_attached_shock_from_terminal_reflection_patch,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell, MocCharacteristicNode
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocTerminalBoundaryGraphStatus',
  'MocTerminalBoundaryGraphResult',
  'validate_terminal_boundary_graph',
  'MocTerminalShockCellFieldStatus',
  'MocTerminalShockCellFieldResult',
  'assemble_terminal_shock_cell_field',
  'MocShockCellTransitionStatus',
  'MocShockCellTransitionResult',
  'solve_marched_ambient_attachment_shock_cell_transition',
)


class MocTerminalShockCellFieldStatus(str, Enum):
  """Outcome for clipping a valid reflected field to a terminal shock."""

  CONVERGED_CLOSED_SUPERSONIC_REGION = 'converged_closed_supersonic_terminal_region'
  INVALID_INPUT = 'invalid_input'
  STRIP_FAILURE = 'strip_failure'
  PATCH_FAILURE = 'reflection_patch_failure'
  SHOCK_FAILURE = 'terminal_shock_failure'
  GEOMETRY_FAILURE = 'terminal_shock_geometry_failure'
  TOPOLOGY_FAILURE = 'terminal_shock_topology_failure'
####


class MocTerminalBoundaryGraphStatus(str, Enum):
  """Outcome of auditing the terminal field's physical boundary paths."""

  CONVERGED_UPSTREAM_GRAPH = 'converged_upstream_terminal_boundary_graph'
  CONVERGED_EXPLICIT_DOWNSTREAM_GEOMETRY = (
    'converged_explicit_downstream_terminal_boundary_geometry'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_GRAPH_FAILURE = 'upstream_terminal_boundary_graph_failure'
  DOWNSTREAM_BOUNDARY_FAILURE = 'downstream_terminal_boundary_failure'
####


@dataclass(frozen=True, slots=True)
class MocTerminalBoundaryGraphResult:
  """Audit the terminal field's paths without inventing a downstream boundary.

  The terminal shock-cell field owns four upstream/supersonic paths: the
  initial shock, ambient streamline, centerline, and terminal shock.  Those
  paths can form a closed upstream graph while the subsonic side remains
  open.  An optional downstream path is accepted only as geometry; it does
  not claim a physical boundary condition or a solved mixed-regime field.
  """

  status: MocTerminalBoundaryGraphStatus
  initial_shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_points_m: tuple[tuple[float, float], ...]
  terminal_shock_boundary_points_m: tuple[tuple[float, float], ...]
  downstream_boundary_points_m: tuple[tuple[float, float], ...] = ()
  upstream_join_residuals_m: tuple[tuple[str, float], ...] = ()
  maximum_upstream_join_residual_m: float | None = None
  upstream_graph_closed: bool = False
  downstream_boundary_geometry_supplied: bool = False
  downstream_boundary_geometry_verified: bool = False
  physical_downstream_condition_supplied: bool = False
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status in (
      MocTerminalBoundaryGraphStatus.CONVERGED_UPSTREAM_GRAPH,
      MocTerminalBoundaryGraphStatus.CONVERGED_EXPLICIT_DOWNSTREAM_GEOMETRY,
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A path audit never substitutes for a solved mixed-regime field."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    paths = {
      'initial_shock': self.initial_shock_boundary_points_m,
      'ambient_streamline': self.ambient_boundary_points_m,
      'centerline': self.centerline_boundary_points_m,
      'terminal_shock': self.terminal_shock_boundary_points_m,
      'downstream_boundary': self.downstream_boundary_points_m,
    }
    return {
      'status': self.status.value,
      'converged': self.converged,
      'upstream_graph_closed': self.upstream_graph_closed,
      'downstream_boundary_geometry_supplied': self.downstream_boundary_geometry_supplied,
      'downstream_boundary_geometry_verified': self.downstream_boundary_geometry_verified,
      'physical_downstream_condition_supplied': self.physical_downstream_condition_supplied,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'path_sample_counts': {
        name: len(points) for name, points in paths.items()
      },
      'path_start_m': {
        name: points[0] if points else None for name, points in paths.items()
      },
      'path_end_m': {
        name: points[-1] if points else None for name, points in paths.items()
      },
      'upstream_join_residuals_m': dict(self.upstream_join_residuals_m),
      'maximum_upstream_join_residual_m': self.maximum_upstream_join_residual_m,
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class MocTerminalShockCellFieldResult:
  """A closed supersonic region cut out by a verified terminal shock.

  The field is assembled from already validated shock/ambient-strip and
  centerline-reflection cells, then clipped by the solver-generated upstream
  side of the terminal shock.  This closes the first-cell *supersonic
  topology* without fabricating subsonic characteristic states.  The
  downstream normal-shock region therefore remains a separate mixed-regime
  gate and the result cannot become a resolved supersonic chain cell.
  """

  status: MocTerminalShockCellFieldStatus
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  initial_shock_boundary_points_m: tuple[tuple[float, float], ...]
  ambient_boundary_points_m: tuple[tuple[float, float], ...]
  centerline_boundary_points_m: tuple[tuple[float, float], ...]
  terminal_shock_boundary_points_m: tuple[tuple[float, float], ...]
  terminal_shock_upstream_states: tuple[CharacteristicState, ...]
  terminal_shock_upstream_pressure_Pa: tuple[float, ...]
  terminal_shock_supersonic_downstream_states: tuple[MocPostShockBoundaryState, ...]
  terminal_shock_supersonic_downstream_maximum_angle_residual_rad: float | None
  terminal_normal_shock: MocNormalShockTerminalResult | None
  source_strip_cell_count: int
  source_patch_cell_count: int
  clipped_patch_cell_count: int
  terminal_shock_boundary_edge_count: int
  terminal_shock_boundary_coverage_verified: bool
  terminal_shock_boundary_maximum_geometry_residual_m: float | None
  message: str = ''
  terminal_shock_supersonic_downstream_continuation: MocPostShockContinuationResult | None = None
  terminal_shock_supersonic_downstream_first_layer: MocPostShockFirstLayerResult | None = None
  terminal_shock_supersonic_downstream_zone: MocPostShockCharacteristicZoneResult | None = None
  mixed_regime_field: MocMixedRegimeFieldResult | None = None
  nodes: tuple[MocCharacteristicNode, ...] = ()

  @property
  def converged(self) -> bool:
    return self.status is MocTerminalShockCellFieldStatus.CONVERGED_CLOSED_SUPERSONIC_REGION
  ####

  @property
  def supersonic_region_closed(self) -> bool:
    return self.converged and self.topology.forms_closed_zone
  ####

  @property
  def characteristic_field_evidence_verified(self) -> bool:
    """Whether the closed region inherits only validated characteristic cells."""

    return self.supersonic_region_closed and bool(self.cells) and bool(self.nodes)
  ####

  @property
  def node_count(self) -> int:
    """Number of retained validated characteristic-node samples.

    A clipped terminal cell may also contain geometric cut vertices on the
    terminal shock.  Those vertices are represented by the explicit terminal
    shock boundary arrays rather than being promoted to fabricated MOC nodes.
    """

    return len(self.nodes)
  ####

  @property
  def mixed_regime_field_complete(self) -> bool:
    """Whether a solver-backed subsonic field closes the terminal side."""

    return bool(
      self.mixed_regime_field is not None
      and self.mixed_regime_field.mixed_regime_field_complete
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether both supersonic topology and mixed-regime field are closed."""

    return self.supersonic_region_closed and self.mixed_regime_field_complete
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal mixed-regime cell stops the supersonic chain."""

    return True

  @property
  def physical_termination_verified(self) -> bool:
    """Whether this closed terminal can stop a supersonic chain physically."""

    return bool(
      self.physical_closure_verified
      and self.terminal_normal_shock is not None
      and self.terminal_normal_shock.converged
    )

  def validate_mixed_regime_boundary(
    self,
    subsonic_samples: Sequence[MocMixedRegimeFieldSample],
    *,
    perimeter_points_m: Sequence[tuple[float, float]] | None = None,
    position_tolerance_m: float = 1.0e-10,
    state_tolerance: float = 1.0e-10,
    pressure_tolerance: float = 1.0e-8,
  ) -> MocMixedRegimeBoundaryResult:
    """Validate a caller-supplied scalar perimeter at the terminal seam.

    The terminal composite owns the verified supersonic patch and normal-shock
    seam, but it does not own the downstream subsonic perimeter.  Callers must
    therefore supply scalar subsonic samples and their ordered, closed
    geometry.  No ``CharacteristicState`` is constructed for the subsonic
    side and no point is inferred from the open post-shock zone.
    """

    return validate_scalar_mixed_regime_boundary(
      cast(MocNormalShockTerminalResult, self.terminal_normal_shock),
      self.terminal_shock_supersonic_downstream_states,
      supersonic_patch_converged=self.terminal_supersonic_downstream_patch_converged,
      subsonic_samples=subsonic_samples,
      perimeter_points_m=perimeter_points_m,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
  ####

  def mixed_regime_perimeter_request(self) -> MocMixedRegimePerimeterRequest:
    """Expose the exact seam a downstream mixed-regime solver must close.

    The request is intentionally incomplete: the terminal composite owns the
    normal-shock scalar state and the supersonic patch, but it does not own a
    downstream perimeter.  Returning a request instead of deriving points
    from the open zone keeps the physical closure boundary explicit.
    """

    if not self.converged or self.terminal_normal_shock is None:
      raise ValueError(
        'a mixed-regime perimeter request requires a converged terminal field '
        'with a typed normal-shock result'
      )
    terminal = self.terminal_normal_shock
    values = (
      terminal.shock_point_m,
      terminal.downstream_mach,
      terminal.downstream_flow_angle_rad,
      terminal.downstream_pressure_Pa,
      terminal.downstream_total_pressure_Pa,
      terminal.total_pressure_ratio,
    )
    if any(value is None for value in values):
      raise ValueError(
        'a mixed-regime perimeter request requires complete terminal scalar '
        'state and pressure data'
      )
    point, mach, angle, pressure, total_pressure, total_pressure_ratio = values
    assert point is not None
    assert mach is not None
    assert angle is not None
    assert pressure is not None
    assert total_pressure is not None
    assert total_pressure_ratio is not None
    return MocMixedRegimePerimeterRequest(
      terminal=terminal,
      terminal_point_m=point,
      terminal_downstream_mach=mach,
      terminal_downstream_flow_angle_rad=angle,
      terminal_downstream_pressure_Pa=pressure,
      terminal_downstream_total_pressure_Pa=total_pressure,
      terminal_total_pressure_ratio=total_pressure_ratio,
      supersonic_patch=self.terminal_shock_supersonic_downstream_states,
    )
  ####

  def mixed_regime_entropy_handoff(self):
    """Return the exact pressure-loss profile at the mixed-regime seam.

    This is a solver-owned interface artifact, not a downstream field.  It
    carries the oblique-shock patch and terminal normal-shock entropy data to
    the next solver while preserving the terminal chain stop.
    """

    from exhaust_plume.models.moc.mixed_regime_entropy import (
      MocMixedRegimeEntropyHandoffResult,
    )

    request = self.mixed_regime_perimeter_request()
    result = request.entropy_handoff()
    if not isinstance(result, MocMixedRegimeEntropyHandoffResult):
      raise TypeError('mixed-regime entropy handoff returned an invalid result')
    return result
  ####

  def validate_mixed_regime_downstream_condition(
    self,
    subsonic_samples: Sequence[MocMixedRegimeFieldSample],
    condition_kind: MocMixedRegimeDownstreamConditionKind,
    *,
    ambient_pressure_Pa: float | None = None,
    perimeter_points_m: Sequence[tuple[float, float]] | None = None,
    position_tolerance_m: float = 1.0e-10,
    state_tolerance: float = 1.0e-10,
    pressure_tolerance: float = 1.0e-8,
    tangent_tolerance_rad: float = 1.0e-8,
  ) -> MocMixedRegimeDownstreamConditionResult:
    """Validate a caller-supplied physical condition at this terminal seam.

    This convenience method keeps the terminal composite's exact shock and
    supersonic-patch seam attached to the scalar perimeter validator.  It
    still accepts no inferred geometry and does not turn a passing condition
    into a supersonic chain-cell handoff.
    """

    boundary = self.validate_mixed_regime_boundary(
      subsonic_samples,
      perimeter_points_m=perimeter_points_m,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
    return validate_mixed_regime_downstream_condition(
      boundary,
      condition_kind,
      ambient_pressure_Pa=ambient_pressure_Pa,
      position_tolerance_m=position_tolerance_m,
      tangent_tolerance_rad=tangent_tolerance_rad,
      pressure_tolerance=pressure_tolerance,
    )
  ####

  def boundary_graph(
    self,
    *,
    downstream_boundary_points_m: Sequence[tuple[float, float]] | None = None,
    position_tolerance_m: float = 1.0e-10,
  ) -> MocTerminalBoundaryGraphResult:
    """Audit the terminal paths and optionally a caller-supplied downstream path."""

    return validate_terminal_boundary_graph(
      self,
      downstream_boundary_points_m=downstream_boundary_points_m,
      position_tolerance_m=position_tolerance_m,
    )
  ####

  def solve_mixed_regime_closure(
    self,
    solve_field: Callable[
      [MocMixedRegimePerimeterRequest],
      MocMixedRegimeFieldResult | None,
    ],
  ) -> MocMixedRegimeClosureResult:
    """Submit the terminal seam to a downstream mixed-regime field solver.

    A successful callback result is still returned separately.  Callers must
    explicitly pass its accepted field to :meth:`with_mixed_regime_field`,
    which keeps the closure gate visible at the attachment site.
    """

    request = self.mixed_regime_perimeter_request()
    return run_mixed_regime_closure_solver(request, solve_field)
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the strongest typed chain stop supported by this result.

    A closed supersonic composite with no mixed-regime field is a valid
    non-promotable boundary, not a resolved chain cell.  Once a physical
    mixed-regime field has been attached, this delegates to the stricter
    physical termination decision.  This gives a planner an explicit stop
    while preserving the fidelity boundary.
    """

    if self.physical_termination_verified:
      return self.as_physical_termination_decision()
    if not self.converged or self.terminal_normal_shock is None:
      raise ValueError(
        'a terminal shock-cell chain decision requires a converged terminal '
        'field with a typed normal-shock result'
      )
    terminal = self.terminal_normal_shock
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'supersonic terminal topology converged, but the downstream '
        'mixed-regime perimeter/field is not closed; chain promotion stops '
        'at the explicit fidelity boundary'
      ),
      diagnostics={
        'termination_model': 'terminal-supersonic-region-open-mixed-regime',
        'supersonic_region_closed': self.supersonic_region_closed,
        'mixed_regime_field_complete': self.mixed_regime_field_complete,
        'terminal_shock_point_m': terminal.shock_point_m,
        'terminal_downstream_mach': terminal.downstream_mach,
        'terminal_field_cell_count': len(self.cells),
        'post_shock_patch_cell_count': (
          None
          if self.terminal_shock_supersonic_downstream_zone is None
          else self.terminal_shock_supersonic_downstream_zone.cell_count
        ),
      },
    )
  ####

  def with_mixed_regime_field(
    self,
    mixed_regime_field: MocMixedRegimeFieldResult,
  ) -> 'MocTerminalShockCellFieldResult':
    """Attach a converged subsonic field without creating a MOC state."""

    if not isinstance(mixed_regime_field, MocMixedRegimeFieldResult):
      raise TypeError('mixed_regime_field must be a MocMixedRegimeFieldResult')
    if not self.supersonic_region_closed:
      raise ValueError('a mixed-regime field requires a closed supersonic terminal region')
    if not mixed_regime_field.physical_closure_verified:
      raise ValueError('only a converged mixed-regime field can be attached')
    if self.terminal_normal_shock is None:
      raise ValueError('a mixed-regime field requires the verified normal-shock terminal')
    if mixed_regime_field.boundary.terminal != self.terminal_normal_shock:
      raise ValueError('mixed-regime field terminal does not match the terminal composite')
    if (
      mixed_regime_field.boundary.supersonic_patch_sample_count
      != len(self.terminal_shock_supersonic_downstream_states)
    ):
      raise ValueError(
        'mixed-regime field does not retain the complete supersonic terminal '
        'patch sample count'
      )
    if (
      mixed_regime_field.boundary.supersonic_patch
      != self.terminal_shock_supersonic_downstream_states
    ):
      raise ValueError(
        'mixed-regime field does not retain the exact supersonic terminal '
        'patch states and pressure-loss samples'
      )
    return replace(self, mixed_regime_field=mixed_regime_field)

  def as_physical_termination_decision(self) -> MocChainTerminationDecision:
    """Return a physical stop only after the mixed-regime field is closed."""

    if not self.physical_termination_verified:
      raise ValueError(
        'a physical terminal decision requires a closed supersonic region and '
        'a converged mixed-regime field'
      )
    terminal = self.terminal_normal_shock
    assert terminal is not None
    assert self.mixed_regime_field is not None
    return MocChainTerminationDecision(
      physical_termination=True,
      reason=MocChainTerminationReason.PHYSICAL_TERMINATION,
      message=(
        'terminal supersonic MOC region and the declared elliptic subsonic '
        'field both converged; the supersonic chain stops at the mixed-regime cell'
      ),
      diagnostics={
        'termination_model': 'normal-shock-plus-elliptic-subsonic-field',
        'shock_point_m': terminal.shock_point_m,
        'downstream_mach': terminal.downstream_mach,
        'downstream_pressure_Pa': terminal.downstream_pressure_Pa,
        'total_pressure_ratio': terminal.total_pressure_ratio,
        'mixed_regime_model': self.mixed_regime_field.model,
        'mixed_regime_node_count': self.mixed_regime_field.node_count,
        'mixed_regime_cell_count': self.mixed_regime_field.cell_count,
      },
    )
  ####

  @property
  def terminal_supersonic_downstream_patch_converged(self) -> bool:
    """Whether the oblique post-shock open patch passed its local gates."""

    return (
      self.terminal_shock_supersonic_downstream_zone is not None
      and self.terminal_shock_supersonic_downstream_zone.converged
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'supersonic_region_closed': self.supersonic_region_closed,
      'characteristic_field_evidence_verified': self.characteristic_field_evidence_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'physical_termination_verified': self.physical_termination_verified,
      'chain_termination_decision': (
        None
        if not self.converged or self.terminal_normal_shock is None
        else self.as_chain_termination_decision().as_report()
      ),
      'terminal_supersonic_downstream_patch_converged': (
        self.terminal_supersonic_downstream_patch_converged
      ),
      'mixed_regime_perimeter_request': (
        None
        if not self.converged or self.terminal_normal_shock is None
        else self.mixed_regime_perimeter_request().as_report()
      ),
      'terminal_boundary_graph': self.boundary_graph().as_report(),
      'node_count': self.node_count,
      'cell_count': len(self.cells),
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_boundary_edge_count': self.topology.boundary_edge_count,
      'topology_boundary_component_count': self.topology.boundary_component_count,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'initial_shock_boundary_sample_count': len(self.initial_shock_boundary_points_m),
      'ambient_boundary_sample_count': len(self.ambient_boundary_points_m),
      'centerline_boundary_sample_count': len(self.centerline_boundary_points_m),
      'terminal_shock_boundary_sample_count': len(self.terminal_shock_boundary_points_m),
      'terminal_shock_upstream_sample_count': len(self.terminal_shock_upstream_states),
      'terminal_shock_supersonic_downstream_sample_count': (
        len(self.terminal_shock_supersonic_downstream_states)
      ),
      'terminal_shock_supersonic_downstream_maximum_angle_residual_rad': (
        self.terminal_shock_supersonic_downstream_maximum_angle_residual_rad
      ),
      'terminal_shock_supersonic_downstream_continuation': (
        None
        if self.terminal_shock_supersonic_downstream_continuation is None
        else {
          'status': self.terminal_shock_supersonic_downstream_continuation.status.value,
          'converged': self.terminal_shock_supersonic_downstream_continuation.converged,
          'segment_count': len(self.terminal_shock_supersonic_downstream_continuation.segments),
          'centerline_point_count': len(self.terminal_shock_supersonic_downstream_continuation.centerline_states),
          'maximum_geometry_residual_m': self.terminal_shock_supersonic_downstream_continuation.maximum_geometry_residual_m,
          'maximum_absolute_invariant_residual': self.terminal_shock_supersonic_downstream_continuation.maximum_absolute_invariant_residual,
          'message': self.terminal_shock_supersonic_downstream_continuation.message,
        }
      ),
      'terminal_shock_supersonic_downstream_first_layer': (
        None
        if self.terminal_shock_supersonic_downstream_first_layer is None
        else {
          'status': self.terminal_shock_supersonic_downstream_first_layer.status.value,
          'converged': self.terminal_shock_supersonic_downstream_first_layer.converged,
          'crossing_count': len(self.terminal_shock_supersonic_downstream_first_layer.crossings),
          'minimum_forward_margin_m': self.terminal_shock_supersonic_downstream_first_layer.minimum_forward_margin_m,
          'maximum_geometry_residual_m': self.terminal_shock_supersonic_downstream_first_layer.maximum_geometry_residual_m,
          'maximum_absolute_invariant_residual': self.terminal_shock_supersonic_downstream_first_layer.maximum_absolute_invariant_residual,
          'message': self.terminal_shock_supersonic_downstream_first_layer.message,
        }
      ),
      'terminal_shock_supersonic_downstream_zone': (
        None
        if self.terminal_shock_supersonic_downstream_zone is None
        else {
          'status': self.terminal_shock_supersonic_downstream_zone.status.value,
          'converged': self.terminal_shock_supersonic_downstream_zone.converged,
          'node_count': self.terminal_shock_supersonic_downstream_zone.node_count,
          'cell_count': self.terminal_shock_supersonic_downstream_zone.cell_count,
          'topology_status': self.terminal_shock_supersonic_downstream_zone.topology.status.value,
          'topology_connected': self.terminal_shock_supersonic_downstream_zone.topology.connected,
          'topology_forms_closed_zone': self.terminal_shock_supersonic_downstream_zone.topology.forms_closed_zone,
          'physical_closure_status': self.terminal_shock_supersonic_downstream_zone.physical_closure_status,
          'shock_closure_status': self.terminal_shock_supersonic_downstream_zone.shock_closure_status,
          'maximum_geometry_residual_m': self.terminal_shock_supersonic_downstream_zone.maximum_geometry_residual_m,
          'maximum_absolute_invariant_residual': self.terminal_shock_supersonic_downstream_zone.maximum_absolute_invariant_residual,
          'message': self.terminal_shock_supersonic_downstream_zone.message,
        }
      ),
      'mixed_regime_field': (
        None
        if self.mixed_regime_field is None
        else self.mixed_regime_field.as_report()
      ),
      'mixed_regime_entropy_handoff': (
        None
        if not self.converged or self.terminal_normal_shock is None
        else self.mixed_regime_entropy_handoff().as_report()
      ),
      'source_strip_cell_count': self.source_strip_cell_count,
      'source_patch_cell_count': self.source_patch_cell_count,
      'clipped_patch_cell_count': self.clipped_patch_cell_count,
      'terminal_shock_boundary_edge_count': self.terminal_shock_boundary_edge_count,
      'terminal_shock_boundary_coverage_verified': self.terminal_shock_boundary_coverage_verified,
      'terminal_shock_boundary_maximum_geometry_residual_m': (
        self.terminal_shock_boundary_maximum_geometry_residual_m
      ),
      'terminal_normal_shock': (
        None
        if self.terminal_normal_shock is None
        else self.terminal_normal_shock.as_report()
      ),
      'message': self.message,
    }
####


def _normalise_terminal_boundary_path(
  points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...] | None:
  try:
    normalised = tuple(
      (float(point[0]), float(point[1]))
      for point in points
    )
  except (IndexError, TypeError, ValueError):
    return None
  if any(not all(isfinite(value) for value in point) for point in normalised):
    return None
  return normalised


def _terminal_path_has_distinct_segments(
  points: Sequence[tuple[float, float]],
  position_tolerance_m: float,
) -> bool:
  return all(
    hypot(second[0] - first[0], second[1] - first[1])
    > position_tolerance_m
    for first, second in zip(points[:-1], points[1:], strict=True)
  )


def _terminal_boundary_graph_result(
  status: MocTerminalBoundaryGraphStatus,
  *,
  initial_shock: Sequence[tuple[float, float]] = (),
  ambient: Sequence[tuple[float, float]] = (),
  centerline: Sequence[tuple[float, float]] = (),
  terminal_shock: Sequence[tuple[float, float]] = (),
  downstream: Sequence[tuple[float, float]] = (),
  join_residuals: Sequence[tuple[str, float]] = (),
  upstream_graph_closed: bool = False,
  downstream_supplied: bool = False,
  downstream_verified: bool = False,
  message: str,
) -> MocTerminalBoundaryGraphResult:
  residuals = tuple((str(name), float(value)) for name, value in join_residuals)
  return MocTerminalBoundaryGraphResult(
    status=status,
    initial_shock_boundary_points_m=tuple(initial_shock),
    ambient_boundary_points_m=tuple(ambient),
    centerline_boundary_points_m=tuple(centerline),
    terminal_shock_boundary_points_m=tuple(terminal_shock),
    downstream_boundary_points_m=tuple(downstream),
    upstream_join_residuals_m=residuals,
    maximum_upstream_join_residual_m=max(
      (value for _, value in residuals),
      default=None,
    ),
    upstream_graph_closed=upstream_graph_closed,
    downstream_boundary_geometry_supplied=downstream_supplied,
    downstream_boundary_geometry_verified=downstream_verified,
    message=message,
  )


def validate_terminal_boundary_graph(
  field: MocTerminalShockCellFieldResult,
  *,
  downstream_boundary_points_m: Sequence[tuple[float, float]] | None = None,
  position_tolerance_m: float = 1.0e-10,
) -> MocTerminalBoundaryGraphResult:
  """Validate the terminal graph and keep the missing downstream path explicit.

  The four paths stored by the terminal supersonic field must join in the
  order ``initial shock -> centerline -> terminal shock -> ambient``.  The
  optional downstream path is checked only as an ordered polygonal geometry;
  no scalar boundary condition or mixed-regime solution is inferred from it.
  """

  if not isinstance(field, MocTerminalShockCellFieldResult):
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.INVALID_INPUT,
      downstream_supplied=downstream_boundary_points_m is not None,
      message='field must be a MocTerminalShockCellFieldResult',
    )
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  raw_paths = (
    ('initial shock', field.initial_shock_boundary_points_m),
    ('ambient streamline', field.ambient_boundary_points_m),
    ('centerline', field.centerline_boundary_points_m),
    ('terminal shock', field.terminal_shock_boundary_points_m),
  )
  paths: list[tuple[tuple[float, float], ...]] = []
  for name, raw_path in raw_paths:
    path = _normalise_terminal_boundary_path(raw_path)
    if path is None:
      return _terminal_boundary_graph_result(
        MocTerminalBoundaryGraphStatus.INVALID_INPUT,
        downstream_supplied=downstream_boundary_points_m is not None,
        message=f'{name} boundary path contains an invalid coordinate',
      )
    paths.append(path)
  initial_shock, ambient, centerline, terminal_shock = paths

  if not field.converged or not field.supersonic_region_closed:
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.UPSTREAM_GRAPH_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      downstream_supplied=downstream_boundary_points_m is not None,
      message=(
        'terminal boundary graph requires a converged closed supersonic '
        f'field: {field.message}'
      ),
    )
  if any(len(path) < 2 for path in paths):
    missing = next(
      name for (name, _), path in zip(raw_paths, paths, strict=True)
      if len(path) < 2
    )
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.UPSTREAM_GRAPH_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      downstream_supplied=downstream_boundary_points_m is not None,
      message=f'{missing} boundary path requires at least two points',
    )
  if any(
    not _terminal_path_has_distinct_segments(path, position_tolerance_m)
    for path in paths
  ):
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.UPSTREAM_GRAPH_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      downstream_supplied=downstream_boundary_points_m is not None,
      message='terminal boundary graph contains a zero-length path segment',
    )

  terminal = field.terminal_normal_shock
  terminal_point = None if terminal is None else terminal.shock_point_m
  if terminal_point is None or not all(isfinite(float(value)) for value in terminal_point):
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.UPSTREAM_GRAPH_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      downstream_supplied=downstream_boundary_points_m is not None,
      message='terminal boundary graph requires a finite normal-shock point',
    )
  joins = (
    ('initial_shock_to_ambient_streamline', initial_shock[0], ambient[0]),
    ('initial_shock_to_centerline', initial_shock[-1], centerline[0]),
    ('centerline_to_terminal_shock', centerline[-1], terminal_shock[-1]),
    ('terminal_shock_to_ambient_streamline', terminal_shock[0], ambient[-1]),
    ('terminal_shock_to_normal_terminal', terminal_shock[-1], terminal_point),
  )
  join_residuals = tuple(
    (
      name,
      hypot(first[0] - second[0], first[1] - second[1]),
    )
    for name, first, second in joins
  )
  maximum_join_residual = max(value for _, value in join_residuals)
  upstream_graph_closed = maximum_join_residual <= position_tolerance_m
  if not upstream_graph_closed:
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.UPSTREAM_GRAPH_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      join_residuals=join_residuals,
      downstream_supplied=downstream_boundary_points_m is not None,
      message=(
        'terminal supersonic boundary paths do not join within tolerance: '
        f'maximum residual={maximum_join_residual}'
      ),
    )

  if downstream_boundary_points_m is None:
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.CONVERGED_UPSTREAM_GRAPH,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      join_residuals=join_residuals,
      upstream_graph_closed=True,
      message=(
        'supersonic terminal boundary graph is closed; downstream subsonic '
        'geometry and its physical boundary condition remain unsupplied'
      ),
    )

  downstream = _normalise_terminal_boundary_path(downstream_boundary_points_m)
  if downstream is None:
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.INVALID_INPUT,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      join_residuals=join_residuals,
      upstream_graph_closed=True,
      downstream_supplied=True,
      message='downstream boundary path contains an invalid coordinate',
    )
  if len(downstream) < 4:
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.DOWNSTREAM_BOUNDARY_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      downstream=downstream,
      join_residuals=join_residuals,
      upstream_graph_closed=True,
      downstream_supplied=True,
      message='downstream boundary path requires at least four points',
    )
  downstream_closed = (
    hypot(
      downstream[-1][0] - downstream[0][0],
      downstream[-1][1] - downstream[0][1],
    ) <= position_tolerance_m
  )
  downstream_anchored = all(
    hypot(point[0] - terminal_point[0], point[1] - terminal_point[1])
    <= position_tolerance_m
    for point in (downstream[0], downstream[-1])
  )
  downstream_of_terminal = all(
    point[0] >= terminal_point[0] - position_tolerance_m
    for point in downstream
  )
  downstream_distinct = _terminal_path_has_distinct_segments(
    downstream,
    position_tolerance_m,
  )
  downstream_area = abs(
    0.5 * sum(
      first[0] * second[1] - second[0] * first[1]
      for first, second in zip(
        downstream,
        (*downstream[1:], downstream[0]),
        strict=True,
      )
    )
  )
  downstream_geometry_verified = (
    downstream_closed
    and downstream_anchored
    and downstream_of_terminal
    and downstream_distinct
    and downstream_area > position_tolerance_m * position_tolerance_m
  )
  if not downstream_geometry_verified:
    return _terminal_boundary_graph_result(
      MocTerminalBoundaryGraphStatus.DOWNSTREAM_BOUNDARY_FAILURE,
      initial_shock=initial_shock,
      ambient=ambient,
      centerline=centerline,
      terminal_shock=terminal_shock,
      downstream=downstream,
      join_residuals=join_residuals,
      upstream_graph_closed=True,
      downstream_supplied=True,
      message=(
        'downstream boundary geometry must be a distinct nonzero-area closed '
        'path anchored at the normal-shock point and downstream of it: '
        f'closed={downstream_closed}, anchored={downstream_anchored}, '
        f'downstream={downstream_of_terminal}, distinct={downstream_distinct}, '
        f'area_m2={downstream_area}'
      ),
    )
  return _terminal_boundary_graph_result(
    MocTerminalBoundaryGraphStatus.CONVERGED_EXPLICIT_DOWNSTREAM_GEOMETRY,
    initial_shock=initial_shock,
    ambient=ambient,
    centerline=centerline,
    terminal_shock=terminal_shock,
    downstream=downstream,
    join_residuals=join_residuals,
    upstream_graph_closed=True,
    downstream_supplied=True,
    downstream_verified=True,
    message=(
      'upstream terminal graph and explicit downstream geometry passed; '
      'a physical downstream condition and mixed-regime field are still required'
    ),
  )
####


def _empty_terminal_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _terminal_field_failure(
  status: MocTerminalShockCellFieldStatus,
  *,
  cells: Sequence[MocCharacteristicCell] = (),
  nodes: Sequence[MocCharacteristicNode] = (),
  topology: MocTopologyResult | None = None,
  initial_shock_points: Sequence[tuple[float, float]] = (),
  ambient_points: Sequence[tuple[float, float]] = (),
  centerline_points: Sequence[tuple[float, float]] = (),
  terminal_shock_points: Sequence[tuple[float, float]] = (),
  upstream_states: Sequence[CharacteristicState] = (),
  upstream_pressures: Sequence[float] = (),
  supersonic_downstream_states: Sequence[MocPostShockBoundaryState] = (),
  supersonic_downstream_maximum_angle_residual_rad: float | None = None,
  terminal_normal_shock: MocNormalShockTerminalResult | None = None,
  source_strip_cell_count: int = 0,
  source_patch_cell_count: int = 0,
  clipped_patch_cell_count: int = 0,
  terminal_shock_boundary_edge_count: int = 0,
  terminal_shock_boundary_coverage_verified: bool = False,
  terminal_shock_boundary_maximum_geometry_residual_m: float | None = None,
  terminal_shock_supersonic_downstream_continuation: MocPostShockContinuationResult | None = None,
  terminal_shock_supersonic_downstream_first_layer: MocPostShockFirstLayerResult | None = None,
  terminal_shock_supersonic_downstream_zone: MocPostShockCharacteristicZoneResult | None = None,
  message: str,
) -> MocTerminalShockCellFieldResult:
  return MocTerminalShockCellFieldResult(
    status=status,
    cells=tuple(cells),
    nodes=tuple(nodes),
    topology=_empty_terminal_topology() if topology is None else topology,
    initial_shock_boundary_points_m=tuple(initial_shock_points),
    ambient_boundary_points_m=tuple(ambient_points),
    centerline_boundary_points_m=tuple(centerline_points),
    terminal_shock_boundary_points_m=tuple(terminal_shock_points),
    terminal_shock_upstream_states=tuple(upstream_states),
    terminal_shock_upstream_pressure_Pa=tuple(float(value) for value in upstream_pressures),
    terminal_shock_supersonic_downstream_states=tuple(supersonic_downstream_states),
    terminal_shock_supersonic_downstream_maximum_angle_residual_rad=(
      supersonic_downstream_maximum_angle_residual_rad
    ),
    terminal_normal_shock=terminal_normal_shock,
    source_strip_cell_count=source_strip_cell_count,
    source_patch_cell_count=source_patch_cell_count,
    clipped_patch_cell_count=clipped_patch_cell_count,
    terminal_shock_boundary_edge_count=terminal_shock_boundary_edge_count,
    terminal_shock_boundary_coverage_verified=terminal_shock_boundary_coverage_verified,
    terminal_shock_boundary_maximum_geometry_residual_m=(
      terminal_shock_boundary_maximum_geometry_residual_m
    ),
    message=message,
    terminal_shock_supersonic_downstream_continuation=(
      terminal_shock_supersonic_downstream_continuation
    ),
    terminal_shock_supersonic_downstream_first_layer=(
      terminal_shock_supersonic_downstream_first_layer
    ),
    terminal_shock_supersonic_downstream_zone=(
      terminal_shock_supersonic_downstream_zone
    ),
  )
####


def _clean_clipped_polygon(
  points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
  cleaned: list[tuple[float, float]] = []
  for point in points:
    canonical = (round(float(point[0]), 12), round(float(point[1]), 12))
    if not cleaned or canonical != cleaned[-1]:
      cleaned.append(canonical)
  if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
    cleaned.pop()
  return tuple(cleaned)
####


def _terminal_shock_x_at_y(
  shock_points: Sequence[tuple[float, float]],
  y_value: float,
  *,
  tolerance_m: float,
) -> float | None:
  if not shock_points:
    return None
  if y_value >= shock_points[0][1] - tolerance_m:
    return shock_points[0][0]
  if y_value <= shock_points[-1][1] + tolerance_m:
    return shock_points[-1][0]
  for first, second in zip(shock_points, shock_points[1:], strict=True):
    lower = min(first[1], second[1])
    upper = max(first[1], second[1])
    if lower - tolerance_m <= y_value <= upper + tolerance_m:
      if abs(second[1] - first[1]) <= tolerance_m:
        return 0.5 * (first[0] + second[0])
      fraction = (y_value - first[1]) / (second[1] - first[1])
      return first[0] + fraction * (second[0] - first[0])
  return None
####


def _terminal_shock_signed_distance(
  point: tuple[float, float],
  shock_points: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> float:
  shock_x = _terminal_shock_x_at_y(
    shock_points,
    point[1],
    tolerance_m=tolerance_m,
  )
  if shock_x is None:
    raise ValueError('point lies outside the terminal shock ordinate range')
  return point[0] - shock_x
####


def _terminal_shock_boundary_intersection(
  first: tuple[float, float],
  second: tuple[float, float],
  shock_points: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> tuple[float, float]:
  first_value = _terminal_shock_signed_distance(
    first,
    shock_points,
    tolerance_m=tolerance_m,
  )
  second_value = _terminal_shock_signed_distance(
    second,
    shock_points,
    tolerance_m=tolerance_m,
  )
  if abs(first_value) <= tolerance_m:
    return first
  if abs(second_value) <= tolerance_m:
    return second
  left = 0.0
  right = 1.0
  left_value = first_value
  for _ in range(64):
    midpoint = 0.5 * (left + right)
    point = (
      first[0] + midpoint * (second[0] - first[0]),
      first[1] + midpoint * (second[1] - first[1]),
    )
    midpoint_value = _terminal_shock_signed_distance(
      point,
      shock_points,
      tolerance_m=tolerance_m,
    )
    if abs(midpoint_value) <= tolerance_m:
      return point
    if left_value * midpoint_value <= 0.0:
      right = midpoint
    else:
      left = midpoint
      left_value = midpoint_value
  midpoint = 0.5 * (left + right)
  return (
    first[0] + midpoint * (second[0] - first[0]),
    first[1] + midpoint * (second[1] - first[1]),
  )
####


def _clip_polygon_to_terminal_shock_upstream_side(
  vertices: Sequence[tuple[float, float]],
  shock_points: Sequence[tuple[float, float]],
  *,
  tolerance_m: float,
) -> tuple[tuple[float, float], ...]:
  """Keep the side containing the first shock/ambient strip.

  The terminal shock is monotone in ``y``.  Its piecewise-linear ``x(y)``
  graph lets us clip each already-valid characteristic polygon without
  extrapolating any state.  The result is a sub-polygon of a validated source
  cell; newly exposed vertices are only geometric cut vertices on the shock.
  """

  if not vertices:
    return ()
  output: list[tuple[float, float]] = []
  previous = vertices[-1]
  previous_value = _terminal_shock_signed_distance(
    previous,
    shock_points,
    tolerance_m=tolerance_m,
  )
  previous_inside = previous_value <= tolerance_m
  for current in vertices:
    current_value = _terminal_shock_signed_distance(
      current,
      shock_points,
      tolerance_m=tolerance_m,
    )
    current_inside = current_value <= tolerance_m
    if current_inside:
      if not previous_inside:
        output.append(
          _terminal_shock_boundary_intersection(
            previous,
            current,
            shock_points,
            tolerance_m=tolerance_m,
          )
        )
      output.append(current)
    elif previous_inside:
      output.append(
        _terminal_shock_boundary_intersection(
          previous,
          current,
          shock_points,
          tolerance_m=tolerance_m,
        )
      )
    previous = current
    previous_value = current_value
    previous_inside = current_inside
  if len(output) >= 2:
    expanded: list[tuple[float, float]] = []
    for first, second in zip(output, (*output[1:], output[0])):
      expanded.append(first)
      first_distance = _terminal_shock_signed_distance(
        first,
        shock_points,
        tolerance_m=tolerance_m,
      )
      second_distance = _terminal_shock_signed_distance(
        second,
        shock_points,
        tolerance_m=tolerance_m,
      )
      if (
        abs(first_distance) <= tolerance_m
        and abs(second_distance) <= tolerance_m
        and abs(second[1] - first[1]) > tolerance_m
      ):
        corners = [
          point for point in shock_points[1:-1]
          if min(first[1], second[1]) + tolerance_m < point[1] < max(first[1], second[1]) - tolerance_m
        ]
        corners.sort(
          key=lambda point: abs(point[1] - first[1])
        )
        expanded.extend(corners)
    output = expanded
  return _clean_clipped_polygon(output)
####


def _polygon_signed_area(
  vertices: Sequence[tuple[float, float]],
) -> float:
  return 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(vertices, (*vertices[1:], vertices[0]))
  )
####


def _triangulate_clipped_polygon(
  vertices: tuple[tuple[float, float], ...],
) -> tuple[tuple[tuple[float, float], ...], ...]:
  if len(vertices) <= 4:
    return (vertices,)
  return tuple(
    (vertices[0], vertices[index], vertices[index + 1])
    for index in range(1, len(vertices) - 1)
  )
####


def _retain_terminal_region_nodes(
  source_nodes: Sequence[MocCharacteristicNode],
  cells: Sequence[MocCharacteristicCell],
  *,
  mesh_vertex_tolerance_m: float,
) -> tuple[MocCharacteristicNode, ...]:
  """Retain source nodes that still belong to the clipped terminal mesh.

  Clipping can create new vertices where a source edge meets the terminal
  shock.  Those vertices have no characteristic intersection result, so this
  helper deliberately retains only source nodes that are exact vertices of a
  surviving cell.  The terminal-shock state arrays remain the authoritative
  data for the newly exposed shock edge.
  """

  retained_points = tuple(
    point
    for cell in cells
    for point in cell.vertices_xr_m
  )
  if not retained_points:
    return ()
  retained: list[MocCharacteristicNode] = []
  seen: set[tuple[int, int]] = set()
  for node in source_nodes:
    if not any(
      abs(node.point_m[0] - point[0]) <= mesh_vertex_tolerance_m
      and abs(node.point_m[1] - point[1]) <= mesh_vertex_tolerance_m
      for point in retained_points
    ):
      continue
    key = (
      round(node.point_m[0] / mesh_vertex_tolerance_m),
      round(node.point_m[1] / mesh_vertex_tolerance_m),
    )
    if key in seen:
      continue
    seen.add(key)
    retained.append(node)
  return tuple(retained)
####


def _terminal_shock_boundary_coverage(
  cells: Sequence[MocCharacteristicCell],
  shock_points: Sequence[tuple[float, float]],
  *,
  position_tolerance_m: float,
  mesh_vertex_tolerance_m: float,
) -> tuple[int, bool, float | None]:
  """Check that the clipped mesh carries the complete terminal-shock edge."""

  if len(shock_points) < 2:
    return 0, False, None
  edge_counts: dict[
    tuple[tuple[int, int], tuple[int, int]],
    int,
  ] = {}
  edge_points: dict[
    tuple[tuple[int, int], tuple[int, int]],
    tuple[tuple[float, float], tuple[float, float]],
  ] = {}
  for cell in cells:
    vertices = cell.vertices_xr_m
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      first_key = (
        round(first[0] / mesh_vertex_tolerance_m),
        round(first[1] / mesh_vertex_tolerance_m),
      )
      second_key = (
        round(second[0] / mesh_vertex_tolerance_m),
        round(second[1] / mesh_vertex_tolerance_m),
      )
      key = (
        (first_key, second_key)
        if first_key <= second_key
        else (second_key, first_key)
      )
      edge_counts[key] = edge_counts.get(key, 0) + 1
      edge_points.setdefault(key, (first, second))

  target_low = min(point[1] for point in shock_points)
  target_high = max(point[1] for point in shock_points)
  shock_edges: list[tuple[float, float]] = []
  residuals: list[float] = []
  for key, count in edge_counts.items():
    if count != 1:
      continue
    first, second = edge_points[key]
    low = min(first[1], second[1])
    high = max(first[1], second[1])
    if high < target_low - position_tolerance_m or low > target_high + position_tolerance_m:
      continue
    ordinates = [first[1], second[1]]
    ordinates.extend(
      point[1]
      for point in shock_points
      if low - position_tolerance_m <= point[1] <= high + position_tolerance_m
    )
    edge_residual = 0.0
    for ordinate in ordinates:
      if abs(second[1] - first[1]) <= mesh_vertex_tolerance_m:
        edge_x = 0.5 * (first[0] + second[0])
      else:
        fraction = (ordinate - first[1]) / (second[1] - first[1])
        edge_x = first[0] + fraction * (second[0] - first[0])
      shock_x = _terminal_shock_x_at_y(
        shock_points,
        ordinate,
        tolerance_m=position_tolerance_m,
      )
      if shock_x is None:
        edge_residual = float('inf')
        break
      edge_residual = max(edge_residual, abs(edge_x - shock_x))
    if edge_residual <= position_tolerance_m:
      shock_edges.append((low, high))
      residuals.append(edge_residual)

  shock_edges.sort()
  merged: list[tuple[float, float]] = []
  for low, high in shock_edges:
    if merged and low <= merged[-1][1] + position_tolerance_m:
      merged[-1] = (merged[-1][0], max(merged[-1][1], high))
    else:
      merged.append((low, high))
  covered = bool(merged) and (
    merged[0][0] <= target_low + position_tolerance_m
    and merged[-1][1] >= target_high - position_tolerance_m
    and all(
      second[0] <= first[1] + position_tolerance_m
      for first, second in zip(merged, merged[1:])
    )
  )
  return len(shock_edges), covered, max(residuals, default=None)
####


def assemble_terminal_shock_cell_field(
  strip: MocAmbientShockStripResult,
  reflection_patch: MocTerminalReflectionPatchResult,
  downstream_shock: MocTerminalReflectionPatchShockSolveResult,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-9,
  mesh_vertex_tolerance_m: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-2,
) -> MocTerminalShockCellFieldResult:
  """Close the composite supersonic topology at a normal-shock terminal.

  The strip and reflected patch are already validated characteristic meshes.
  This routine removes the patch portion on the downstream side of the
  generated terminal shock and validates the union with the physical strip.
  It does not invent a subsonic ``CharacteristicState`` after the normal
  shock, so the returned topology is a terminal supersonic region rather than
  a promotion-ready mixed-regime cell.
  """

  if not isinstance(strip, MocAmbientShockStripResult):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.INVALID_INPUT,
      message='strip must be a MocAmbientShockStripResult',
    )
  if not isinstance(reflection_patch, MocTerminalReflectionPatchResult):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.INVALID_INPUT,
      message='reflection_patch must be a MocTerminalReflectionPatchResult',
    )
  if not isinstance(downstream_shock, MocTerminalReflectionPatchShockSolveResult):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.INVALID_INPUT,
      message='downstream_shock must be a MocTerminalReflectionPatchShockSolveResult',
    )
  for name, value in (
    ('target_centerline_y_m', target_centerline_y_m),
    ('position_tolerance_m', position_tolerance_m),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)):
      raise ValueError(f'{name} must be finite')
  if (
    position_tolerance_m <= 0.0
    or mesh_vertex_tolerance_m <= 0.0
    or shock_angle_tolerance_rad <= 0.0
  ):
    raise ValueError('terminal shock tolerances must be positive')
  if not strip.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.STRIP_FAILURE,
      message=f'shock/ambient strip is not converged: {strip.message}',
    )
  if not reflection_patch.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.PATCH_FAILURE,
      source_strip_cell_count=strip.cell_count,
      message=f'centerline reflection patch is not converged: {reflection_patch.message}',
    )
  if (
    not downstream_shock.physical_terminal_verified
    or downstream_shock.shock.normal_shock_terminal is None
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      message=(
        'terminal field requires complete upstream coverage and a verified '
        'normal-shock terminal'
      ),
    )

  terminal = downstream_shock.shock.normal_shock_terminal
  shock_samples = tuple(downstream_shock.shock.shock_points_m)
  upstream_states = tuple(downstream_shock.shock.upstream_states)
  upstream_pressures = tuple(downstream_shock.shock.upstream_pressure_Pa)
  if (
    len(shock_samples) < 2
    or len(shock_samples) != len(upstream_states)
    or len(shock_samples) != len(upstream_pressures)
    or not downstream_shock.coupling.converged
    or downstream_shock.coupling.sampled_count != len(shock_samples)
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='terminal shock does not carry a complete domain-bounded upstream path',
    )
  terminal_point = terminal.shock_point_m
  if terminal_point is None or not all(isfinite(float(value)) for value in terminal_point):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='normal-shock terminal does not expose a finite shock point',
    )
  if (
    terminal.upstream_state is None
    or terminal.upstream_pressure_Pa is None
    or not isfinite(float(terminal.upstream_pressure_Pa))
    or terminal.upstream_pressure_Pa <= 0.0
    or abs(terminal.upstream_state.x_m - terminal_point[0]) > position_tolerance_m
    or abs(terminal.upstream_state.y_m - terminal_point[1]) > position_tolerance_m
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=(
        'normal-shock terminal does not expose a finite upstream state and '
        'pressure at its boundary point'
      ),
    )
  downstream_angles = tuple(downstream_shock.shock.downstream_flow_angles_rad)
  if len(downstream_angles) != len(shock_samples):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=(
        'terminal shock does not carry a complete downstream turn trace for '
        'its supersonic boundary samples'
      ),
    )
  try:
    supersonic_downstream_fit = fit_attached_shock_boundary(
      upstream_states,
      upstream_pressures,
      shock_samples,
      downstream_angles,
      branch=ShockBranch.WEAK,
      position_tolerance_m=position_tolerance_m,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=f'terminal supersonic downstream state fit raised: {error}',
    )
  if not supersonic_downstream_fit.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.SHOCK_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      supersonic_downstream_states=supersonic_downstream_fit.boundary_states,
      supersonic_downstream_maximum_angle_residual_rad=(
        supersonic_downstream_fit.maximum_shock_angle_residual_rad
      ),
      message=(
        'terminal shock supersonic downstream states did not pass attached '
        f'boundary verification: {supersonic_downstream_fit.message}'
      ),
    )
  supersonic_downstream_states = supersonic_downstream_fit.boundary_states
  supersonic_downstream_maximum_angle_residual_rad = (
    supersonic_downstream_fit.maximum_shock_angle_residual_rad
  )
  supersonic_downstream_continuation = (
    continue_post_shock_characteristics_to_centerline_open(
      supersonic_downstream_states,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=1.0e-10,
    )
  )
  supersonic_downstream_first_layer = None
  supersonic_downstream_zone = None
  if supersonic_downstream_continuation.converged:
    supersonic_downstream_first_layer = assemble_post_shock_first_layer(
      supersonic_downstream_continuation,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=1.0e-10,
    )
    if supersonic_downstream_first_layer.converged:
      supersonic_downstream_zone = assemble_post_shock_characteristic_zone(
        supersonic_downstream_continuation,
        supersonic_downstream_first_layer,
        supersonic_downstream_states,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=1.0e-10,
      )
  upstream_states = (*upstream_states, terminal.upstream_state)
  upstream_pressures = (*upstream_pressures, float(terminal.upstream_pressure_Pa))
  terminal_shock_points = (*shock_samples, terminal_point)
  expected_start = reflection_patch.outgoing_trace_points_m[0]
  if (
    abs(shock_samples[0][0] - expected_start[0]) > position_tolerance_m
    or abs(shock_samples[0][1] - expected_start[1]) > position_tolerance_m
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      terminal_shock_supersonic_downstream_continuation=(
        supersonic_downstream_continuation
      ),
      terminal_shock_supersonic_downstream_first_layer=(
        supersonic_downstream_first_layer
      ),
      terminal_shock_supersonic_downstream_zone=supersonic_downstream_zone,
      message='terminal shock does not start at the reflected outgoing trace',
    )
  if abs(terminal_point[1] - float(target_centerline_y_m)) > position_tolerance_m:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      terminal_shock_supersonic_downstream_continuation=(
        supersonic_downstream_continuation
      ),
      terminal_shock_supersonic_downstream_first_layer=(
        supersonic_downstream_first_layer
      ),
      terminal_shock_supersonic_downstream_zone=supersonic_downstream_zone,
      message='normal-shock terminal does not lie on the requested centerline',
    )
  if any(
    second[0] <= first[0] + position_tolerance_m
    or second[1] > first[1] + position_tolerance_m
    or second[1] < float(target_centerline_y_m) - position_tolerance_m
    for first, second in zip(terminal_shock_points, terminal_shock_points[1:])
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      terminal_shock_supersonic_downstream_continuation=(
        supersonic_downstream_continuation
      ),
      terminal_shock_supersonic_downstream_first_layer=(
        supersonic_downstream_first_layer
      ),
      terminal_shock_supersonic_downstream_zone=supersonic_downstream_zone,
      message='terminal shock path is not strictly downstream and centerline-bounded',
    )
  if reflection_patch.axis_points_m and (
    terminal_point[0] < reflection_patch.axis_points_m[0][0] - position_tolerance_m
    or terminal_point[0] > reflection_patch.axis_points_m[-1][0] + position_tolerance_m
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='normal-shock terminal lies outside the reflected centerline interval',
    )

  input_trace = reflection_patch.input_trace_validation
  if input_trace is None or not input_trace.converged:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.PATCH_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='reflection patch does not expose a converged input trace',
    )
  if len(input_trace.samples) != len(strip.terminal_trace_points_m) or any(
    abs(sample.state.x_m - point[0]) > position_tolerance_m
    or abs(sample.state.y_m - point[1]) > position_tolerance_m
    for sample, point in zip(input_trace.samples, strip.terminal_trace_points_m, strict=True)
  ):
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='reflection patch input trace does not match the strip terminal trace',
    )

  cells: list[MocCharacteristicCell] = []
  try:
    for source in strip.cells:
      cells.append(MocCharacteristicCell(
        cell_index=len(cells),
        cell_kind=f'terminal-composite-strip-{source.cell_kind}',
        vertices_xr_m=tuple(source.vertices_xr_m),
        centerline_indices=source.centerline_indices,
        boundary_indices=source.boundary_indices,
      ))
    clipped_count = 0
    for source in reflection_patch.cells:
      clipped = _clip_polygon_to_terminal_shock_upstream_side(
        source.vertices_xr_m,
        terminal_shock_points,
        tolerance_m=position_tolerance_m,
      )
      if len(clipped) < 3 or abs(_polygon_signed_area(clipped)) <= position_tolerance_m**2:
        continue
      for polygon in _triangulate_clipped_polygon(clipped):
        if len(polygon) not in (3, 4) or abs(_polygon_signed_area(polygon)) <= position_tolerance_m**2:
          continue
        cells.append(MocCharacteristicCell(
          cell_index=len(cells),
          cell_kind=f'terminal-composite-patch-{source.cell_kind}',
          vertices_xr_m=polygon,
          centerline_indices=source.centerline_indices,
          boundary_indices=source.boundary_indices,
        ))
        clipped_count += 1
  except (TypeError, ValueError) as error:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      cells=cells,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      clipped_patch_cell_count=0,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=f'terminal shock cell clipping produced invalid geometry: {error}',
    )
  if not cells:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message='terminal shock clipping produced no characteristic cells',
    )
  nodes = _retain_terminal_region_nodes(
    (*strip.nodes, *reflection_patch.nodes),
    cells,
    mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  if not nodes:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      cells=cells,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      clipped_patch_cell_count=clipped_count,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=(
        'terminal shock clipping retained cells but no validated source '
        'characteristic nodes'
      ),
    )
  topology = validate_moc_mesh(
    cells,
    vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  (
    terminal_shock_edge_count,
    terminal_shock_coverage_verified,
    terminal_shock_geometry_residual,
  ) = _terminal_shock_boundary_coverage(
    cells,
    terminal_shock_points,
    position_tolerance_m=position_tolerance_m,
    mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
  )
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.TOPOLOGY_FAILURE,
      cells=cells,
      nodes=nodes,
      topology=topology,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      clipped_patch_cell_count=clipped_count,
      terminal_shock_boundary_edge_count=terminal_shock_edge_count,
      terminal_shock_boundary_coverage_verified=terminal_shock_coverage_verified,
      terminal_shock_boundary_maximum_geometry_residual_m=terminal_shock_geometry_residual,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=f'terminal composite topology failed: {topology.message}',
    )
  if not terminal_shock_coverage_verified:
    return _terminal_field_failure(
      MocTerminalShockCellFieldStatus.GEOMETRY_FAILURE,
      cells=cells,
      nodes=nodes,
      topology=topology,
      source_strip_cell_count=strip.cell_count,
      source_patch_cell_count=reflection_patch.cell_count,
      clipped_patch_cell_count=clipped_count,
      terminal_shock_boundary_edge_count=terminal_shock_edge_count,
      terminal_shock_boundary_coverage_verified=False,
      terminal_shock_boundary_maximum_geometry_residual_m=terminal_shock_geometry_residual,
      terminal_shock_points=terminal_shock_points,
      terminal_normal_shock=terminal,
      upstream_states=upstream_states,
      upstream_pressures=upstream_pressures,
      message=(
        'terminal composite topology is bounded but does not expose the '
        'complete solver-generated terminal-shock boundary'
      ),
    )
  centerline_points = tuple(
    point for point in reflection_patch.axis_points_m
    if point[0] <= terminal_point[0] + position_tolerance_m
  )
  if not centerline_points or abs(centerline_points[-1][0] - terminal_point[0]) > position_tolerance_m:
    centerline_points = (*centerline_points, terminal_point)
  return MocTerminalShockCellFieldResult(
    status=MocTerminalShockCellFieldStatus.CONVERGED_CLOSED_SUPERSONIC_REGION,
    cells=tuple(cells),
    nodes=nodes,
    topology=topology,
    initial_shock_boundary_points_m=strip.shock_boundary_points_m,
    ambient_boundary_points_m=strip.ambient_boundary_points_m,
    centerline_boundary_points_m=centerline_points,
    terminal_shock_boundary_points_m=terminal_shock_points,
    terminal_shock_upstream_states=upstream_states,
    terminal_shock_upstream_pressure_Pa=upstream_pressures,
    terminal_shock_supersonic_downstream_states=supersonic_downstream_states,
    terminal_shock_supersonic_downstream_maximum_angle_residual_rad=(
      supersonic_downstream_maximum_angle_residual_rad
    ),
    terminal_normal_shock=terminal,
    source_strip_cell_count=strip.cell_count,
    source_patch_cell_count=reflection_patch.cell_count,
    clipped_patch_cell_count=clipped_count,
    terminal_shock_boundary_edge_count=terminal_shock_edge_count,
    terminal_shock_boundary_coverage_verified=terminal_shock_coverage_verified,
    terminal_shock_boundary_maximum_geometry_residual_m=terminal_shock_geometry_residual,
    terminal_shock_supersonic_downstream_continuation=(
      supersonic_downstream_continuation
    ),
    terminal_shock_supersonic_downstream_first_layer=(
      supersonic_downstream_first_layer
    ),
    terminal_shock_supersonic_downstream_zone=supersonic_downstream_zone,
    message=(
      'shock/ambient strip and reflected characteristic patch were clipped '
      'to a closed supersonic region at the verified normal shock; subsonic '
      'downstream field remains outside the planar MOC lane'
    ),
  )
####


class MocShockCellTransitionStatus(str, Enum):
  """Structured outcomes for a staged shock-cell transition."""

  CONVERGED_OPEN_TRANSITION = 'converged_open_shock_cell_transition'
  PHYSICALLY_TERMINATED = 'physically_terminated_at_normal_shock'
  INVALID_INPUT = 'invalid_input'
  ATTACHMENT_FAILURE = 'attachment_failure'
  REFLECTION_FAILURE = 'centerline_reflection_failure'
  DOWNSTREAM_SHOCK_FAILURE = 'downstream_shock_failure'
####


@dataclass(frozen=True, slots=True)
class MocShockCellTransitionResult:
  """A typed open transition between adjacent planar-MOC shock regions.

  ``CONVERGED_OPEN_TRANSITION`` means that the attachment, physical
  shock/ambient strip, centerline reflection, and next-shock coupling all
  passed their local gates.  ``PHYSICALLY_TERMINATED`` means that the same
  transition reached a verified subsonic normal-shock terminal.  Neither
  result is a closed first-cell or a chain-cell promotion result: the
  downstream law used by the next-shock probe is retained as a named
  centerline-normal-shock reference.
  """

  status: MocShockCellTransitionStatus
  attachment: MocAmbientAttachmentResult
  reflection_patch: MocTerminalReflectionPatchResult | None
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None
  terminal_field: MocTerminalShockCellFieldResult | None
  downstream_condition_status: str
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status in (
      MocShockCellTransitionStatus.CONVERGED_OPEN_TRANSITION,
      MocShockCellTransitionStatus.PHYSICALLY_TERMINATED,
    )
  ####

  @property
  def physical_termination(self) -> bool:
    return self.status is MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The staged transition never promotes an open field into a cell."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def next_shock_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the reflected outgoing trace for a possible next shock."""

    if self.reflection_patch is None:
      return ()
    return self.reflection_patch.outgoing_trace_samples
  ####

  def as_physical_termination_decision(self) -> MocChainTerminationDecision:
    """Return the verified normal-shock stop when this transition has one."""

    if not self.physical_termination or self.downstream_shock is None:
      raise ValueError(
        'a physical shock-cell termination requires a verified downstream '
        'normal-shock terminal'
      )
    return self.downstream_shock.as_physical_termination_decision()
  ####

  def as_report(self) -> dict[str, object]:
    termination = (
      self.as_physical_termination_decision().as_report()
      if self.physical_termination
      else None
    )
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_termination': self.physical_termination,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'downstream_condition_status': self.downstream_condition_status,
      'next_shock_handoff_kind': 'terminal-characteristic-trace',
      'next_shock_handoff_sample_count': len(self.next_shock_handoff),
      'termination_decision_available': termination is not None,
      'physical_termination_decision': termination,
      'attachment': self.attachment.as_report(),
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
      'message': self.message,
    }
####


def _invalid_attachment(message: str) -> MocAmbientAttachmentResult:
  return MocAmbientAttachmentResult(
    status=MocAmbientAttachmentStatus.INVALID_INPUT,
    shock=None,
    ambient_march=None,
    strip=None,
    ambient_pressure_Pa=None,
    outer_downstream_flow_angle_rad=None,
    outer_flow_angle_bracket=None,
    attachment_pressure_residual=None,
    shooting_iterations=0,
    message=message,
  )
####


def solve_marched_ambient_attachment_shock_cell_transition(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  terminal_branch: ShockBranch = ShockBranch.WEAK,
  downstream_flow_angle_rad: float = 0.0,
  trace_position_tolerance_m: float = 2.0e-4,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
) -> MocShockCellTransitionResult:
  """Build one staged shock-cell transition and retain its open boundary.

  The outer shock turn is solved against ambient pressure first.  The
  resulting physical shock/ambient strip is reflected to the centerline, and
  its outgoing ``C-`` trace is passed to the domain-bounded next-shock probe.
  ``branch`` controls the ambient attachment; ``terminal_branch`` controls the
  separate downstream attached-shock probe.
  A zero downstream angle is a declared normal-shock reference condition; it
  is not silently treated as a universal downstream closure.
  """

  try:
    downstream_angle = float(downstream_flow_angle_rad)
    trace_tolerance = float(trace_position_tolerance_m)
  except (TypeError, ValueError):
    attachment = _invalid_attachment(
      'downstream flow angle and trace tolerance must be numeric',
    )
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.INVALID_INPUT,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=attachment.message,
    )
  if not isfinite(downstream_angle) or not isfinite(trace_tolerance) or trace_tolerance <= 0.0:
    attachment = _invalid_attachment(
      'downstream flow angle must be finite and trace tolerance must be positive',
    )
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.INVALID_INPUT,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=attachment.message,
    )

  try:
    attachment = solve_marched_attached_shock_with_ambient_attachment_closure(
      upstream_state_at,
      upstream_pressure_at,
      start_point_m,
      ambient_pressure_Pa,
      outer_downstream_flow_angle_lower_rad,
      outer_downstream_flow_angle_upper_rad,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    attachment = _invalid_attachment(f'ambient attachment raised: {error}')
  if not attachment.converged or attachment.strip is None:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.ATTACHMENT_FAILURE,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'ambient attachment did not converge: {attachment.message}',
    )

  try:
    reflection_patch = assemble_terminal_trace_centerline_patch(
      attachment.strip,
      trace_position_tolerance_m=trace_tolerance,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.REFLECTION_FAILURE,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'centerline reflection patch raised: {error}',
    )
  if not reflection_patch.converged or not reflection_patch.outgoing_trace_points_m:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.REFLECTION_FAILURE,
      attachment=attachment,
      reflection_patch=reflection_patch,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'centerline reflection patch did not converge: {reflection_patch.message}',
    )

  try:
    downstream_shock = solve_marched_attached_shock_from_terminal_reflection_patch(
      reflection_patch,
      reflection_patch.outgoing_trace_points_m[0],
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_rad=downstream_angle,
      incoming_handoff=reflection_patch.outgoing_trace_samples,
      sample_count=sample_count,
      branch=terminal_branch,
      position_tolerance_m=trace_tolerance,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE,
      attachment=attachment,
      reflection_patch=reflection_patch,
      downstream_shock=None,
      terminal_field=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'downstream shock probe raised: {error}',
    )

  terminal_field = None
  if downstream_shock.physical_terminal_verified:
    terminal_field = assemble_terminal_shock_cell_field(
      attachment.strip,
      reflection_patch,
      downstream_shock,
      target_centerline_y_m=target_centerline_y_m,
      position_tolerance_m=max(position_tolerance_m, 1.0e-9),
      mesh_vertex_tolerance_m=max(position_tolerance_m, 1.0e-9),
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    )
    if terminal_field.converged:
      status = MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
      message = (
        'ambient attachment, centerline reflection, and next-shock coupling '
        'reached a verified normal-shock terminal and closed the supersonic '
        'composite topology; no mixed-regime cell was promoted'
      )
    else:
      status = MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE
      message = f'terminal supersonic topology did not close: {terminal_field.message}'
  elif downstream_shock.converged:
    status = MocShockCellTransitionStatus.CONVERGED_OPEN_TRANSITION
    message = (
      'ambient attachment, centerline reflection, and next-shock coupling '
      'converged as an open transition; downstream cell closure remains pending'
    )
  else:
    status = MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE
    message = f'downstream shock probe did not converge: {downstream_shock.message}'
  return MocShockCellTransitionResult(
    status=status,
    attachment=attachment,
    reflection_patch=reflection_patch,
    downstream_shock=downstream_shock,
    terminal_field=terminal_field,
    downstream_condition_status='centerline-normal-shock-reference',
    message=message,
  )
####
