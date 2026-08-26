"""A promotion-safe characteristic-family restart at a detected caustic.

The reflected source strip can reach a point where its old triangular source
family is no longer forward.  This module does not stitch the two one-sided
states together or call that event a shock.  It uses one selected one-sided
state as a new-family anchor, reflects its ``C-`` characteristic to the
symmetry line, and marches an ambient-pressure/tangent ``C+`` boundary.  The
result is an open boundary handoff for a future remesher or shock solver; it
is not a closed upstream field or a chain-cell seed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from exhaust_plume.models.moc.boundary import (
  MocFreeBoundaryPointResult,
  solve_ambient_pressure_free_boundary_point,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  centerline_characteristic_point,
)
from exhaust_plume.models.moc.source_strip import (
  MocSourceCharacteristicStripResult,
  MocSourceStripCausticShockSeedResult,
  assemble_source_characteristic_strip,
)

__all__ = (
  'MocCausticFamilyRestartStatus',
  'MocCausticFamilyRestartResult',
  'restart_characteristic_family_from_caustic',
)


class MocCausticFamilyRestartStatus(str, Enum):
  """Outcome of the open new-family boundary restart."""

  CONVERGED_OPEN_BOUNDARY = 'converged_open_caustic_family_boundary'
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'caustic_seed_failure'
  CENTERLINE_FAILURE = 'caustic_restart_centerline_failure'
  AMBIENT_BOUNDARY_FAILURE = 'caustic_restart_ambient_boundary_failure'


@dataclass(frozen=True, slots=True)
class MocCausticFamilyRestartResult:
  """An open, one-sided new-family boundary after a characteristic caustic."""

  status: MocCausticFamilyRestartStatus
  seed: MocSourceStripCausticShockSeedResult | None
  anchor_edge_index: int | None
  anchor_point_m: tuple[float, float] | None
  anchor_state: CharacteristicState | None
  centerline_states: tuple[CharacteristicState, ...]
  boundary_states: tuple[CharacteristicState, ...]
  boundary_points_m: tuple[tuple[float, float], ...]
  total_pressure_Pa: float | None
  ambient_pressure_Pa: float | None
  maximum_absolute_pressure_residual: float | None
  maximum_absolute_tangent_residual: float | None
  maximum_absolute_geometry_residual_m: float | None
  minimum_forward_progress_m: float | None
  source_strip: MocSourceCharacteristicStripResult | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCausticFamilyRestartStatus.CONVERGED_OPEN_BOUNDARY

  @property
  def physical_closure_verified(self) -> bool:
    """The restart has no downstream shock or closed characteristic mesh."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def boundary_sample_count(self) -> int:
    return len(self.boundary_states)

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'anchor_edge_index': self.anchor_edge_index,
      'anchor_point_m': self.anchor_point_m,
      'anchor_state': (
        None
        if self.anchor_state is None
        else {
          'x_m': self.anchor_state.x_m,
          'y_m': self.anchor_state.y_m,
          'theta_rad': self.anchor_state.theta_rad,
          'mach': self.anchor_state.mach,
          'gamma': self.anchor_state.gamma,
        }
      ),
      'centerline_sample_count': len(self.centerline_states),
      'boundary_sample_count': self.boundary_sample_count,
      'boundary_points_m': [list(point) for point in self.boundary_points_m],
      'total_pressure_Pa': self.total_pressure_Pa,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'maximum_absolute_pressure_residual': self.maximum_absolute_pressure_residual,
      'maximum_absolute_tangent_residual': self.maximum_absolute_tangent_residual,
      'maximum_absolute_geometry_residual_m': self.maximum_absolute_geometry_residual_m,
      'minimum_forward_progress_m': self.minimum_forward_progress_m,
      'source_strip': (
        None
        if self.source_strip is None
        else {
          'status': self.source_strip.status.value,
          'converged': self.source_strip.converged,
          'node_count': self.source_strip.node_count,
          'cell_count': self.source_strip.cell_count,
          'topology_status': self.source_strip.topology.status.value,
          'topology_forms_closed_zone': self.source_strip.topology.forms_closed_zone,
          'topology_nonmanifold_edge_count': self.source_strip.topology.nonmanifold_edge_count,
          'message': self.source_strip.message,
        }
      ),
      'message': self.message,
    }


def _failure(
  status: MocCausticFamilyRestartStatus,
  *,
  seed: MocSourceStripCausticShockSeedResult | None,
  anchor_edge_index: int | None,
  anchor_point_m: tuple[float, float] | None = None,
  anchor_state: CharacteristicState | None = None,
  centerline_states: tuple[CharacteristicState, ...] = (),
  boundary_states: tuple[CharacteristicState, ...] = (),
  boundary_points_m: tuple[tuple[float, float], ...] = (),
  total_pressure_Pa: float | None = None,
  ambient_pressure_Pa: float | None = None,
  maximum_absolute_pressure_residual: float | None = None,
  maximum_absolute_tangent_residual: float | None = None,
  maximum_absolute_geometry_residual_m: float | None = None,
  minimum_forward_progress_m: float | None = None,
  source_strip: MocSourceCharacteristicStripResult | None = None,
  message: str,
) -> MocCausticFamilyRestartResult:
  return MocCausticFamilyRestartResult(
    status=status,
    seed=seed,
    anchor_edge_index=anchor_edge_index,
    anchor_point_m=anchor_point_m,
    anchor_state=anchor_state,
    centerline_states=centerline_states,
    boundary_states=boundary_states,
    boundary_points_m=boundary_points_m,
    total_pressure_Pa=total_pressure_Pa,
    ambient_pressure_Pa=ambient_pressure_Pa,
    maximum_absolute_pressure_residual=maximum_absolute_pressure_residual,
    maximum_absolute_tangent_residual=maximum_absolute_tangent_residual,
    maximum_absolute_geometry_residual_m=maximum_absolute_geometry_residual_m,
    minimum_forward_progress_m=minimum_forward_progress_m,
    source_strip=source_strip,
    message=message,
  )


def _state_result_reportable(result: MocFreeBoundaryPointResult) -> bool:
  return (
    result.converged
    and result.state is not None
    and result.point_m is not None
  )


def restart_characteristic_family_from_caustic(
  seed: MocSourceStripCausticShockSeedResult,
  total_pressure_Pa: float,
  ambient_pressure_Pa: float,
  *,
  anchor_edge_index: int = 0,
  sample_count: int = 6,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-10,
  maximum_iterations: int = 16,
) -> MocCausticFamilyRestartResult:
  """Restart an open reflected boundary from one side of a caustic.

  ``anchor_edge_index`` selects one already-solved one-sided C- edge.  The
  selected state is not averaged with the opposite edge and is not treated as
  a shock state.  A first C- reflection creates an axis state; each following
  C+ boundary point is solved against the previous ambient/tangent boundary.
  The optional triangular source-strip assembly is retained only as a local
  diagnostic because a caustic restart generally needs a new mesh family.
  """

  if not isinstance(seed, MocSourceStripCausticShockSeedResult):
    return _failure(
      MocCausticFamilyRestartStatus.INVALID_INPUT,
      seed=None,
      anchor_edge_index=None,
      message='seed must be a MocSourceStripCausticShockSeedResult',
    )
  try:
    total_pressure = float(total_pressure_Pa)
    ambient_pressure = float(ambient_pressure_Pa)
  except (TypeError, ValueError):
    return _failure(
      MocCausticFamilyRestartStatus.INVALID_INPUT,
      seed=seed,
      anchor_edge_index=anchor_edge_index,
      message='pressures must be finite numeric values',
    )
  if (
    not isfinite(total_pressure)
    or total_pressure <= 0.0
    or not isfinite(ambient_pressure)
    or ambient_pressure <= 0.0
    or total_pressure <= ambient_pressure
  ):
    return _failure(
      MocCausticFamilyRestartStatus.INVALID_INPUT,
      seed=seed,
      anchor_edge_index=anchor_edge_index,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      message='total pressure must exceed finite positive ambient pressure',
    )
  if (
    isinstance(anchor_edge_index, bool)
    or not isinstance(anchor_edge_index, int)
    or anchor_edge_index not in (0, 1)
  ):
    return _failure(
      MocCausticFamilyRestartStatus.INVALID_INPUT,
      seed=seed,
      anchor_edge_index=anchor_edge_index,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      message='anchor_edge_index must be 0 or 1',
    )
  if (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    return _failure(
      MocCausticFamilyRestartStatus.INVALID_INPUT,
      seed=seed,
      anchor_edge_index=anchor_edge_index,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      message='sample_count must be an integer of at least three',
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
  if not seed.converged or len(seed.edge_states) != 2:
    return _failure(
      MocCausticFamilyRestartStatus.SEED_FAILURE,
      seed=seed,
      anchor_edge_index=anchor_edge_index,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      message=f'caustic restart seed is not usable: {seed.message}',
    )
  anchor = seed.edge_states[anchor_edge_index]
  if anchor.state is None or anchor.point_m is None:
    return _failure(
      MocCausticFamilyRestartStatus.SEED_FAILURE,
      seed=seed,
      anchor_edge_index=anchor_edge_index,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      message='selected caustic edge does not carry a one-sided anchor state',
    )
  anchor_state = anchor.state
  centerline_states: list[CharacteristicState] = []
  boundary_states: list[CharacteristicState] = []
  boundary_points: list[tuple[float, float]] = []
  pressure_residuals: list[float] = []
  tangent_residuals: list[float] = []
  geometry_residuals: list[float] = []
  forward_progress: list[float] = []
  previous_boundary = anchor_state
  for step in range(sample_count):
    axis_result = centerline_characteristic_point(
      previous_boundary,
      CharacteristicFamily.MINUS,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
    if not axis_result.converged or axis_result.state is None:
      return _failure(
        MocCausticFamilyRestartStatus.CENTERLINE_FAILURE,
        seed=seed,
        anchor_edge_index=anchor_edge_index,
        anchor_point_m=anchor.point_m,
        anchor_state=anchor_state,
        centerline_states=tuple(centerline_states),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        total_pressure_Pa=total_pressure,
        ambient_pressure_Pa=ambient_pressure,
        maximum_absolute_pressure_residual=max(map(abs, pressure_residuals), default=None),
        maximum_absolute_tangent_residual=max(map(abs, tangent_residuals), default=None),
        maximum_absolute_geometry_residual_m=max(map(abs, geometry_residuals), default=None),
        minimum_forward_progress_m=min(forward_progress, default=None),
        message=f'caustic restart centerline reflection failed at step {step}: {axis_result.message}',
      )
    boundary_result = solve_ambient_pressure_free_boundary_point(
      axis_result.state,
      previous_boundary,
      CharacteristicFamily.PLUS,
      total_pressure_Pa=total_pressure,
      ambient_pressure_Pa=ambient_pressure,
      position_tolerance_m=position_tolerance_m,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_iterations,
    )
    if not _state_result_reportable(boundary_result):
      return _failure(
        MocCausticFamilyRestartStatus.AMBIENT_BOUNDARY_FAILURE,
        seed=seed,
        anchor_edge_index=anchor_edge_index,
        anchor_point_m=anchor.point_m,
        anchor_state=anchor_state,
        centerline_states=tuple(centerline_states),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        total_pressure_Pa=total_pressure,
        ambient_pressure_Pa=ambient_pressure,
        maximum_absolute_pressure_residual=max(map(abs, pressure_residuals), default=None),
        maximum_absolute_tangent_residual=max(map(abs, tangent_residuals), default=None),
        maximum_absolute_geometry_residual_m=max(map(abs, geometry_residuals), default=None),
        minimum_forward_progress_m=min(forward_progress, default=None),
        message=f'caustic restart ambient boundary failed at step {step}: {boundary_result.message}',
      )
    assert boundary_result.state is not None
    assert boundary_result.point_m is not None
    progress = boundary_result.point_m[0] - previous_boundary.x_m
    if progress <= position_tolerance_m:
      return _failure(
        MocCausticFamilyRestartStatus.AMBIENT_BOUNDARY_FAILURE,
        seed=seed,
        anchor_edge_index=anchor_edge_index,
        anchor_point_m=anchor.point_m,
        anchor_state=anchor_state,
        centerline_states=tuple(centerline_states),
        boundary_states=tuple(boundary_states),
        boundary_points_m=tuple(boundary_points),
        total_pressure_Pa=total_pressure,
        ambient_pressure_Pa=ambient_pressure,
        maximum_absolute_pressure_residual=max(map(abs, pressure_residuals), default=None),
        maximum_absolute_tangent_residual=max(map(abs, tangent_residuals), default=None),
        maximum_absolute_geometry_residual_m=max(map(abs, geometry_residuals), default=None),
        minimum_forward_progress_m=min(forward_progress, default=None),
        message='caustic restart ambient boundary did not make downstream progress',
      )
    centerline_states.append(axis_result.state)
    boundary_states.append(boundary_result.state)
    boundary_points.append(boundary_result.point_m)
    pressure_residuals.append(boundary_result.pressure_residual or 0.0)
    tangent_residuals.append(boundary_result.tangent_residual or 0.0)
    geometry_residuals.append(boundary_result.geometry_residual or 0.0)
    forward_progress.append(progress)
    previous_boundary = boundary_result.state

  source_strip = assemble_source_characteristic_strip(
    tuple(centerline_states),
    tuple(boundary_states),
    total_pressure,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
  )
  return MocCausticFamilyRestartResult(
    status=MocCausticFamilyRestartStatus.CONVERGED_OPEN_BOUNDARY,
    seed=seed,
    anchor_edge_index=anchor_edge_index,
    anchor_point_m=anchor.point_m,
    anchor_state=anchor_state,
    centerline_states=tuple(centerline_states),
    boundary_states=tuple(boundary_states),
    boundary_points_m=tuple(boundary_points),
    total_pressure_Pa=total_pressure,
    ambient_pressure_Pa=ambient_pressure,
    maximum_absolute_pressure_residual=max(map(abs, pressure_residuals), default=None),
    maximum_absolute_tangent_residual=max(map(abs, tangent_residuals), default=None),
    maximum_absolute_geometry_residual_m=max(map(abs, geometry_residuals), default=None),
    minimum_forward_progress_m=min(forward_progress, default=None),
    source_strip=source_strip,
    message=(
      'one-sided caustic family restart converged as an open '
      'centerline/ambient boundary; triangular interior remesh and shock '
      'closure remain separate gates'
    ),
  )
