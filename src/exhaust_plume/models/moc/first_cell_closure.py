"""Solver-backed terminal closure for the planar-MOC first-cell lane.

The first-cell composite owns the shock/ambient strip, centerline reflection,
and the outgoing characteristic handoff.  This module consumes that exact
handoff to fit a terminal shock and assemble the closed supersonic side of
the first cell.  The downstream normal-shock side remains a separate scalar
mixed-regime contract; no subsonic ``CharacteristicState`` is fabricated.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Callable

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
)
from exhaust_plume.models.moc.first_cell import (
  MocFirstCellCompositeResult,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeClosureResult,
  MocMixedRegimeDownstreamPerimeterSpec,
  MocMixedRegimeFieldSample,
  MocMixedRegimeFieldResult,
  MocMixedRegimePerimeterRequest,
  run_mixed_regime_closure_solver,
  solve_mixed_regime_downstream_perimeter,
)
from exhaust_plume.models.moc.shock_chain import (
  MocTerminalShockCellFieldResult,
  assemble_terminal_shock_cell_field,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  MocTerminalReflectionPatchShockSolveResult,
  solve_marched_attached_shock_from_terminal_reflection_patch,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocFirstCellTerminalClosureStatus',
  'MocFirstCellTerminalClosureResult',
  'assemble_first_cell_terminal_shock_field',
  'solve_marched_first_cell_terminal_closure',
)


class MocFirstCellTerminalClosureStatus(str, Enum):
  """Outcome of coupling a first-cell composite to a terminal shock."""

  CONVERGED_SUPERSONIC_REGION = 'converged_first_cell_supersonic_region'
  INVALID_INPUT = 'invalid_input'
  COMPOSITE_FAILURE = 'first_cell_composite_failure'
  SHOCK_FAILURE = 'first_cell_terminal_shock_failure'
  SEAM_FAILURE = 'first_cell_terminal_shock_seam_failure'
  FIELD_FAILURE = 'first_cell_terminal_field_failure'
####


@dataclass(frozen=True, slots=True)
class MocFirstCellTerminalClosureResult:
  """A first-cell terminal-shock result with an explicit mixed-regime gate.

  ``converged`` means that the first-cell supersonic region was assembled from
  the exact composite seam.  ``physical_closure_verified`` becomes true only
  after a separately validated mixed-regime field is attached.  This result
  is therefore useful to a planner without allowing the open terminal
  boundary to masquerade as a resolved cell.
  """

  status: MocFirstCellTerminalClosureStatus
  composite: MocFirstCellCompositeResult | None
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None
  terminal_field: MocTerminalShockCellFieldResult | None
  mixed_regime_field: MocMixedRegimeFieldResult | None = None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocFirstCellTerminalClosureStatus.CONVERGED_SUPERSONIC_REGION
  ####

  @property
  def supersonic_region_closed(self) -> bool:
    return bool(
      self.converged
      and self.terminal_field is not None
      and self.terminal_field.supersonic_region_closed
    )
  ####

  @property
  def mixed_regime_field_complete(self) -> bool:
    return bool(
      self.terminal_field is not None
      and self.terminal_field.mixed_regime_field_complete
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return bool(
      self.terminal_field is not None
      and self.terminal_field.physical_closure_verified
    )
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal first cell is a stop, never a supersonic next-cell seed."""

    return True
  ####

  @property
  def physical_termination_verified(self) -> bool:
    return bool(
      self.terminal_field is not None
      and self.terminal_field.physical_termination_verified
    )
  ####

  def mixed_regime_perimeter_request(self) -> MocMixedRegimePerimeterRequest:
    """Return the exact terminal seam a downstream solver must close."""

    if self.terminal_field is None:
      raise ValueError(
        'a mixed-regime perimeter request requires a converged terminal field'
      )
    return self.terminal_field.mixed_regime_perimeter_request()
  ####

  def solve_mixed_regime_closure(
    self,
    solve_field: Callable[
      [MocMixedRegimePerimeterRequest],
      MocMixedRegimeFieldResult | None,
    ],
  ) -> MocMixedRegimeClosureResult:
    """Run a callback-owned mixed-regime solve against the exact terminal seam."""

    return run_mixed_regime_closure_solver(
      self.mixed_regime_perimeter_request(),
      solve_field,
    )
  ####

  def solve_mixed_regime_downstream_perimeter(
    self,
    specification: MocMixedRegimeDownstreamPerimeterSpec,
    sample_at: Callable[
      [MocMixedRegimePerimeterRequest, int, tuple[float, float]],
      MocMixedRegimeFieldSample | None,
    ],
    *,
    radial_divisions: int = 1,
    position_tolerance_m: float = 1.0e-10,
    state_tolerance: float = 1.0e-10,
    pressure_tolerance: float = 1.0e-8,
    tangent_tolerance_rad: float = 1.0e-8,
    thermodynamic_tolerance: float = 1.0e-8,
    residual_tolerance: float = 1.0e-12,
  ) -> MocMixedRegimeClosureResult:
    """Solve a declared downstream perimeter at this exact terminal seam.

    This is the ergonomic first-cell entry point for the separate
    elliptic/isentrope reference lane.  The specification and scalar sampler
    remain caller-owned, so the method does not infer a canonical plume
    perimeter or turn a finite-domain reference into a production cell.
    """

    return solve_mixed_regime_downstream_perimeter(
      self.mixed_regime_perimeter_request(),
      specification,
      sample_at,
      radial_divisions=radial_divisions,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance_rad=tangent_tolerance_rad,
      thermodynamic_tolerance=thermodynamic_tolerance,
      residual_tolerance=residual_tolerance,
    )
  ####

  def with_mixed_regime_field(
    self,
    mixed_regime_field: MocMixedRegimeFieldResult,
  ) -> 'MocFirstCellTerminalClosureResult':
    """Attach only a field that passes the terminal mixed-regime gates."""

    if self.terminal_field is None:
      raise ValueError(
        'a mixed-regime field requires a converged first-cell terminal field'
      )
    updated_field = self.terminal_field.with_mixed_regime_field(mixed_regime_field)
    return replace(
      self,
      terminal_field=updated_field,
      mixed_regime_field=updated_field.mixed_regime_field,
      message=(
        'first-cell supersonic region and the attached mixed-regime field '
        'passed their declared closure gates'
      ),
    )
  ####

  def attach_mixed_regime_closure(
    self,
    closure: MocMixedRegimeClosureResult,
  ) -> 'MocFirstCellTerminalClosureResult':
    """Attach one accepted closure while preserving its exact terminal seam.

    The closure result is the ownership boundary between a downstream scalar
    solver and this first-cell terminal.  Requiring the exact request here
    prevents a valid field solved for a different shock or supersonic patch
    from being attached accidentally.  This method still does not promote a
    chain cell: a mixed-regime terminal is an explicit chain stop.
    """

    if not isinstance(closure, MocMixedRegimeClosureResult):
      raise TypeError('closure must be a MocMixedRegimeClosureResult')
    if closure.request != self.mixed_regime_perimeter_request():
      raise ValueError(
        'mixed-regime closure does not retain this first-cell terminal seam'
      )
    if not closure.converged or closure.field is None:
      raise ValueError(
        'only a converged mixed-regime closure with an accepted field can be attached'
      )
    return self.with_mixed_regime_field(closure.field)
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Preserve either the open-closure or verified physical terminal stop."""

    if self.terminal_field is not None:
      return self.terminal_field.as_chain_termination_decision()
    if self.composite is not None and self.composite.topology_closed:
      return self.composite.as_chain_termination_decision()
    raise ValueError(
      'a first-cell chain decision requires a converged composite or terminal field'
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'supersonic_region_closed': self.supersonic_region_closed,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'physical_termination_verified': self.physical_termination_verified,
      'composite': (
        None if self.composite is None else self.composite.as_report()
      ),
      'downstream_shock': (
        None
        if self.downstream_shock is None
        else self.downstream_shock.as_report()
      ),
      'terminal_field': (
        None if self.terminal_field is None else self.terminal_field.as_report()
      ),
      'mixed_regime_field': (
        None
        if self.mixed_regime_field is None
        else self.mixed_regime_field.as_report()
      ),
      'message': self.message,
    }
  ####


def _result(
  status: MocFirstCellTerminalClosureStatus,
  *,
  composite: MocFirstCellCompositeResult | None = None,
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None = None,
  terminal_field: MocTerminalShockCellFieldResult | None = None,
  message: str,
) -> MocFirstCellTerminalClosureResult:
  return MocFirstCellTerminalClosureResult(
    status=status,
    composite=composite,
    downstream_shock=downstream_shock,
    terminal_field=terminal_field,
    message=message,
  )


def _validate_tolerances(
  *,
  position_tolerance_m: float,
  mesh_vertex_tolerance_m: float,
  shock_angle_tolerance_rad: float,
) -> None:
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('mesh_vertex_tolerance_m', mesh_vertex_tolerance_m),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')


def assemble_first_cell_terminal_shock_field(
  composite: MocFirstCellCompositeResult,
  downstream_shock: MocTerminalReflectionPatchShockSolveResult,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  mesh_vertex_tolerance_m: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-2,
) -> MocFirstCellTerminalClosureResult:
  """Close the first-cell supersonic side at a solver-generated terminal shock.

  The terminal shock must have consumed the composite's exact outgoing
  ``C-`` trace.  The existing terminal-field assembler then clips only the
  reflected characteristic cells upstream of that shock and rechecks the
  complete physical perimeter.  No downstream perimeter is inferred here.
  """

  if not isinstance(composite, MocFirstCellCompositeResult):
    return _result(
      MocFirstCellTerminalClosureStatus.INVALID_INPUT,
      message='composite must be a MocFirstCellCompositeResult',
    )
  if not isinstance(
    downstream_shock,
    MocTerminalReflectionPatchShockSolveResult,
  ):
    return _result(
      MocFirstCellTerminalClosureStatus.INVALID_INPUT,
      composite=composite,
      message=(
        'downstream_shock must be a '
        'MocTerminalReflectionPatchShockSolveResult'
      ),
    )
  try:
    target_y = float(target_centerline_y_m)
    _validate_tolerances(
      position_tolerance_m=position_tolerance_m,
      mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    )
  except (TypeError, ValueError) as error:
    return _result(
      MocFirstCellTerminalClosureStatus.INVALID_INPUT,
      composite=composite,
      downstream_shock=downstream_shock,
      message=f'first-cell terminal closure inputs are invalid: {error}',
    )
  if not isfinite(target_y):
    return _result(
      MocFirstCellTerminalClosureStatus.INVALID_INPUT,
      composite=composite,
      downstream_shock=downstream_shock,
      message='target_centerline_y_m must be finite',
    )
  if not composite.topology_closed or not composite.physical_boundary_conditions_verified:
    return _result(
      MocFirstCellTerminalClosureStatus.COMPOSITE_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      message=(
        'first-cell composite must have a connected closed supersonic topology '
        'and verified physical boundary paths'
      ),
    )
  if composite.strip is None or composite.patch is None:
    return _result(
      MocFirstCellTerminalClosureStatus.COMPOSITE_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      message='first-cell composite does not retain its strip and reflection patch',
    )
  expected_handoff = composite.continuation_boundary
  if tuple(downstream_shock.incoming_handoff) != expected_handoff:
    return _result(
      MocFirstCellTerminalClosureStatus.SEAM_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      message=(
        'terminal shock did not consume the exact first-cell outgoing '
        'characteristic handoff'
      ),
    )
  if not downstream_shock.physical_terminal_verified:
    return _result(
      MocFirstCellTerminalClosureStatus.SHOCK_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      message=(
        'first-cell terminal closure requires complete upstream coverage and '
        'a verified normal-shock terminal'
      ),
    )
  terminal_field = assemble_terminal_shock_cell_field(
    composite.strip,
    composite.patch,
    downstream_shock,
    target_centerline_y_m=target_y,
    position_tolerance_m=float(position_tolerance_m),
    mesh_vertex_tolerance_m=float(mesh_vertex_tolerance_m),
    shock_angle_tolerance_rad=float(shock_angle_tolerance_rad),
  )
  if not terminal_field.converged:
    return _result(
      MocFirstCellTerminalClosureStatus.FIELD_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      terminal_field=terminal_field,
      message=(
        'first-cell terminal shock was verified, but the clipped supersonic '
        f'field did not close: {terminal_field.message}'
      ),
    )
  if terminal_field.initial_shock_boundary_points_m != composite.shock_boundary_points_m:
    return _result(
      MocFirstCellTerminalClosureStatus.SEAM_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      terminal_field=terminal_field,
      message='terminal field changed the first-cell fitted shock boundary',
    )
  return _result(
    MocFirstCellTerminalClosureStatus.CONVERGED_SUPERSONIC_REGION,
    composite=composite,
    downstream_shock=downstream_shock,
    terminal_field=terminal_field,
    message=(
      'first-cell composite was closed at the solver-generated terminal '
      'shock on the supersonic side; mixed-regime closure remains separate'
    ),
  )
####


def solve_marched_first_cell_terminal_closure(
  composite: MocFirstCellCompositeResult,
  *,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  shock_position_tolerance_m: float = 2.0e-4,
  position_tolerance_m: float = 1.0e-10,
  mesh_vertex_tolerance_m: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
) -> MocFirstCellTerminalClosureResult:
  """Fit and assemble a terminal shock directly from a first-cell composite.

  This is the solver-owned bridge from the open composite's outgoing trace to
  the closed supersonic terminal-region checkpoint.  The downstream turning
  law remains explicit caller input and is retained in the nested shock
  result; supplying a zero angle is a normal-shock reference condition, not a
  universal physical closure.
  """

  if not isinstance(composite, MocFirstCellCompositeResult):
    return _result(
      MocFirstCellTerminalClosureStatus.INVALID_INPUT,
      message='composite must be a MocFirstCellCompositeResult',
    )
  if composite.patch is None or not composite.continuation_boundary_points_m:
    return _result(
      MocFirstCellTerminalClosureStatus.COMPOSITE_FAILURE,
      composite=composite,
      message='first-cell composite does not expose an outgoing terminal trace',
    )
  if not composite.topology_closed:
    return _result(
      MocFirstCellTerminalClosureStatus.COMPOSITE_FAILURE,
      composite=composite,
      message='first-cell composite topology is not closed',
    )
  try:
    downstream_shock = solve_marched_attached_shock_from_terminal_reflection_patch(
      composite.patch,
      composite.continuation_boundary_points_m[0],
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      incoming_handoff=tuple(composite.continuation_boundary),
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=shock_position_tolerance_m,
      invariant_tolerance=1.0e-10,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocFirstCellTerminalClosureStatus.SHOCK_FAILURE,
      composite=composite,
      message=f'first-cell terminal shock solve raised: {error}',
    )
  if not downstream_shock.physical_terminal_verified:
    return _result(
      MocFirstCellTerminalClosureStatus.SHOCK_FAILURE,
      composite=composite,
      downstream_shock=downstream_shock,
      message=(
        'first-cell terminal shock did not reach a verified normal-shock '
        f'terminal: {downstream_shock.message}'
      ),
    )
  return assemble_first_cell_terminal_shock_field(
    composite,
    downstream_shock,
    target_centerline_y_m=target_centerline_y_m,
    position_tolerance_m=position_tolerance_m,
    mesh_vertex_tolerance_m=mesh_vertex_tolerance_m,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
  )
####
