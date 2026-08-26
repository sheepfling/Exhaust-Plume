"""Typed scalar handoff for the subsonic side of a planar MOC terminal.

The supersonic MOC lane cannot represent a subsonic downstream state as a
``CharacteristicState``.  This module therefore defines the next, narrower
contract: a caller may provide scalar subsonic samples and an explicitly
closed perimeter after a verified terminal shock.  The validator checks the
shock seam, the open supersonic patch, scalar state validity, pressure
lineage, and perimeter geometry.

This is a boundary handoff, not a subsonic characteristic solver.  A passing
handoff still reports ``physical_closure_verified=False`` and cannot seed a
continued shock-cell chain.  A future mixed-regime solver can consume this
contract and add a real subsonic mesh/field acceptance gate without changing
the supersonic ``CharacteristicState`` type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, sin
from typing import Sequence

from exhaust_plume.models.moc.compression import (
  MocNormalShockTerminalResult,
  MocSubsonicShockBoundaryResult,
)
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocMixedRegimeBoundaryStatus',
  'MocMixedRegimeFieldSample',
  'MocMixedRegimePerimeterRequest',
  'MocMixedRegimeBoundaryResult',
  'MocMixedRegimeFieldStatus',
  'MocMixedRegimeFieldResult',
  'validate_mixed_regime_boundary',
  'solve_mixed_regime_subsonic_field',
)


class MocMixedRegimeBoundaryStatus(str, Enum):
  """Structured outcome for the scalar mixed-regime boundary handoff."""

  CONVERGED_BOUNDARY_HANDOFF = 'converged_subsonic_boundary_handoff'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'mixed_regime_terminal_failure'
  SUPERSONIC_PATCH_FAILURE = 'supersonic_patch_failure'
  SUBSONIC_FIELD_FAILURE = 'subsonic_field_failure'
  GEOMETRY_FAILURE = 'mixed_regime_geometry_failure'
  PRESSURE_FAILURE = 'mixed_regime_pressure_failure'


class MocMixedRegimeFieldStatus(str, Enum):
  """Outcome for the separate elliptic subsonic field solver."""

  CONVERGED_ELLIPTIC_FIELD = 'converged_elliptic_subsonic_field'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_FAILURE = 'mixed_regime_boundary_failure'
  GEOMETRY_FAILURE = 'mixed_regime_mesh_geometry_failure'
  TOPOLOGY_FAILURE = 'mixed_regime_mesh_topology_failure'
  THERMODYNAMIC_FAILURE = 'mixed_regime_thermodynamic_failure'
  RESIDUAL_FAILURE = 'mixed_regime_elliptic_residual_failure'


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFieldSample:
  """One scalar state sample on a proposed subsonic perimeter.

  This deliberately contains no ``CharacteristicState``.  The scalar fields
  are sufficient for seam and thermodynamic checks, but not for entering the
  supersonic compatibility network.
  """

  point_m: tuple[float, float]
  mach: float
  flow_angle_rad: float
  static_pressure_Pa: float
  total_pressure_Pa: float
  gamma: float

  def __post_init__(self) -> None:
    try:
      point = (float(self.point_m[0]), float(self.point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('mixed-regime sample point must contain two finite coordinates') from None
    if not all(isfinite(value) for value in point):
      raise ValueError('mixed-regime sample point must contain two finite coordinates')
    values = (
      ('mach', self.mach, 0.0, 1.0),
      ('flow_angle_rad', self.flow_angle_rad, None, None),
      ('static_pressure_Pa', self.static_pressure_Pa, 0.0, None),
      ('total_pressure_Pa', self.total_pressure_Pa, 0.0, None),
      ('gamma', self.gamma, 1.0, None),
    )
    for name, raw_value, lower, upper in values:
      value = float(raw_value)
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      if lower is not None and value <= lower:
        raise ValueError(f'{name} must be greater than {lower}')
      if upper is not None and value >= upper:
        raise ValueError(f'{name} must be less than {upper}')
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'mach', float(self.mach))
    object.__setattr__(self, 'flow_angle_rad', float(self.flow_angle_rad))
    object.__setattr__(self, 'static_pressure_Pa', float(self.static_pressure_Pa))
    object.__setattr__(self, 'total_pressure_Pa', float(self.total_pressure_Pa))
    object.__setattr__(self, 'gamma', float(self.gamma))


MocMixedRegimeTerminal = MocNormalShockTerminalResult | MocSubsonicShockBoundaryResult


@dataclass(frozen=True, slots=True)
class MocMixedRegimePerimeterRequest:
  """Solver-owned data required to close a subsonic terminal region.

  The terminal shock and the open supersonic patch provide the downstream
  scalar seam, but they do not determine the remaining subsonic perimeter.
  This request exposes the data a mixed-regime solver must consume while
  deliberately carrying no guessed perimeter points.  In particular, the
  open supersonic zone is evidence for the upstream seam, never a substitute
  for the downstream boundary condition.
  """

  terminal_point_m: tuple[float, float]
  terminal_downstream_mach: float
  terminal_downstream_flow_angle_rad: float
  terminal_downstream_pressure_Pa: float
  terminal_downstream_total_pressure_Pa: float
  terminal_total_pressure_ratio: float
  supersonic_patch: tuple[MocPostShockBoundaryState, ...]
  required_boundary_conditions: tuple[str, ...] = (
    'explicitly closed downstream perimeter',
    'terminal scalar seam continuity',
    'no total-pressure gain over the terminal shock',
  )
  source: str = 'solver-owned-terminal-shock-mixed-regime-handoff'

  def __post_init__(self) -> None:
    try:
      point = (float(self.terminal_point_m[0]), float(self.terminal_point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('terminal_point_m must contain two finite coordinates') from None
    if not all(isfinite(value) for value in point):
      raise ValueError('terminal_point_m must contain two finite coordinates')
    for name, value, lower in (
      ('terminal_downstream_mach', self.terminal_downstream_mach, 0.0),
      ('terminal_downstream_pressure_Pa', self.terminal_downstream_pressure_Pa, 0.0),
      ('terminal_downstream_total_pressure_Pa', self.terminal_downstream_total_pressure_Pa, 0.0),
      ('terminal_total_pressure_ratio', self.terminal_total_pressure_ratio, 0.0),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= lower:
        raise ValueError(f'{name} must be finite and greater than {lower}')
    if self.terminal_downstream_mach >= 1.0:
      raise ValueError('terminal_downstream_mach must be subsonic')
    if self.terminal_total_pressure_ratio >= 1.0:
      raise ValueError('terminal_total_pressure_ratio must show strict total-pressure loss')
    angle = float(self.terminal_downstream_flow_angle_rad)
    if not isfinite(angle):
      raise ValueError('terminal_downstream_flow_angle_rad must be finite')
    patch = tuple(self.supersonic_patch)
    if not patch:
      raise ValueError('supersonic_patch must contain at least one boundary state')
    if any(not isinstance(sample, MocPostShockBoundaryState) for sample in patch):
      raise TypeError('supersonic_patch must contain MocPostShockBoundaryState values')
    if any(sample.state.mach <= 1.0 for sample in patch):
      raise ValueError('supersonic_patch must contain only supersonic states')
    conditions = tuple(str(condition) for condition in self.required_boundary_conditions)
    if not conditions:
      raise ValueError('required_boundary_conditions must not be empty')
    object.__setattr__(self, 'terminal_point_m', point)
    object.__setattr__(self, 'terminal_downstream_mach', float(self.terminal_downstream_mach))
    object.__setattr__(self, 'terminal_downstream_flow_angle_rad', angle)
    object.__setattr__(self, 'terminal_downstream_pressure_Pa', float(self.terminal_downstream_pressure_Pa))
    object.__setattr__(self, 'terminal_downstream_total_pressure_Pa', float(self.terminal_downstream_total_pressure_Pa))
    object.__setattr__(self, 'terminal_total_pressure_ratio', float(self.terminal_total_pressure_ratio))
    object.__setattr__(self, 'supersonic_patch', patch)
    object.__setattr__(self, 'required_boundary_conditions', conditions)
  ####

  @property
  def perimeter_supplied(self) -> bool:
    """Whether a downstream geometry was supplied to this request."""

    return False
  ####

  @property
  def open_supersonic_zone_is_a_perimeter(self) -> bool:
    """The open supersonic patch cannot close the subsonic region."""

    return False
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': 'mixed-regime-perimeter-required',
      'source': self.source,
      'perimeter_supplied': self.perimeter_supplied,
      'open_supersonic_zone_is_a_perimeter': self.open_supersonic_zone_is_a_perimeter,
      'terminal_point_m': self.terminal_point_m,
      'terminal_downstream_mach': self.terminal_downstream_mach,
      'terminal_downstream_flow_angle_rad': self.terminal_downstream_flow_angle_rad,
      'terminal_downstream_pressure_Pa': self.terminal_downstream_pressure_Pa,
      'terminal_downstream_total_pressure_Pa': self.terminal_downstream_total_pressure_Pa,
      'terminal_total_pressure_ratio': self.terminal_total_pressure_ratio,
      'supersonic_patch_sample_count': len(self.supersonic_patch),
      'supersonic_patch_points_m': tuple(sample.point_m for sample in self.supersonic_patch),
      'supersonic_patch_mach': tuple(sample.state.mach for sample in self.supersonic_patch),
      'supersonic_patch_downstream_total_pressure_Pa': tuple(
        sample.downstream_total_pressure_Pa for sample in self.supersonic_patch
      ),
      'required_boundary_conditions': self.required_boundary_conditions,
      'message': (
        'the mixed-regime solver must provide the closed downstream perimeter; '
        'no geometry was inferred from the open supersonic zone'
      ),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeBoundaryResult:
  """Validation result for a scalar subsonic perimeter handoff.

  ``converged`` means that the handoff itself passed.  It intentionally does
  not mean that a subsonic field was solved: ``physical_closure_verified`` and
  ``mixed_regime_field_complete`` remain false until a future solver supplies
  and validates a real subsonic mesh.
  """

  status: MocMixedRegimeBoundaryStatus
  terminal: MocMixedRegimeTerminal | None
  supersonic_patch_sample_count: int
  subsonic_samples: tuple[MocMixedRegimeFieldSample, ...]
  perimeter_points_m: tuple[tuple[float, float], ...]
  supersonic_patch_verified: bool
  subsonic_state_samples_verified: bool
  terminal_continuity_verified: bool
  perimeter_geometry_verified: bool
  total_pressure_lineage_verified: bool
  maximum_terminal_mach_residual: float | None
  maximum_terminal_flow_angle_residual_rad: float | None
  maximum_terminal_static_pressure_residual_Pa: float | None
  maximum_terminal_total_pressure_residual_Pa: float | None
  maximum_total_pressure_gain_Pa: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF

  @property
  def mixed_regime_field_complete(self) -> bool:
    """Whether a subsonic characteristic/finite-volume field was supplied."""

    return False

  @property
  def physical_closure_verified(self) -> bool:
    """A scalar perimeter handoff is not physical cell closure."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  def as_report(self) -> dict[str, object]:
    terminal_report = None if self.terminal is None else self.terminal.as_report()
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'supersonic_patch_sample_count': self.supersonic_patch_sample_count,
      'subsonic_sample_count': len(self.subsonic_samples),
      'perimeter_sample_count': len(self.perimeter_points_m),
      'supersonic_patch_verified': self.supersonic_patch_verified,
      'subsonic_state_samples_verified': self.subsonic_state_samples_verified,
      'terminal_continuity_verified': self.terminal_continuity_verified,
      'perimeter_geometry_verified': self.perimeter_geometry_verified,
      'total_pressure_lineage_verified': self.total_pressure_lineage_verified,
      'maximum_terminal_mach_residual': self.maximum_terminal_mach_residual,
      'maximum_terminal_flow_angle_residual_rad': self.maximum_terminal_flow_angle_residual_rad,
      'maximum_terminal_static_pressure_residual_Pa': self.maximum_terminal_static_pressure_residual_Pa,
      'maximum_terminal_total_pressure_residual_Pa': self.maximum_terminal_total_pressure_residual_Pa,
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'terminal': terminal_report,
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFieldResult:
  """A mesh-backed elliptic continuation of a scalar subsonic perimeter.

  The solver uses a conservative first reference model for the subsonic side:
  primitive scalar fields are harmonically extended to one interior control
  point and the dimensionless velocity field is checked for a zero discrete
  divergence on every triangular control volume.  This is intentionally a
  separate elliptic lane, not a supersonic MOC field; its model name and
  residuals remain in every report.

  ``physical_closure_verified`` means that this explicitly declared
  elliptic/isentrope model closed its supplied boundary and passed its local
  conservation and thermodynamic gates.  It is not external validation of the
  plume or permission to expose a public product provider.
  """

  status: MocMixedRegimeFieldStatus
  boundary: MocMixedRegimeBoundaryResult
  nodes: tuple[MocMixedRegimeFieldSample, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  interior_point_m: tuple[float, float] | None
  maximum_thermodynamic_residual: float | None
  maximum_harmonic_residual: float | None
  maximum_velocity_divergence_residual: float | None
  minimum_mach: float | None
  maximum_mach: float | None
  model: str = 'elliptic-isentropic-subsonic-reference'
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD

  @property
  def node_count(self) -> int:
    return len(self.nodes)

  @property
  def cell_count(self) -> int:
    return len(self.cells)

  @property
  def mixed_regime_field_complete(self) -> bool:
    return self.converged and self.physical_closure_verified

  @property
  def physical_closure_verified(self) -> bool:
    return bool(
      self.converged
      and self.boundary.converged
      and self.topology.connected
      and self.topology.forms_closed_zone
      and not self.topology.nonmanifold_edge_count
      and self.maximum_thermodynamic_residual is not None
      and self.maximum_harmonic_residual is not None
      and self.maximum_velocity_divergence_residual is not None
      and self.maximum_thermodynamic_residual <= 1.0e-8
      and self.maximum_harmonic_residual <= 1.0e-12
      and self.maximum_velocity_divergence_residual <= 1.0e-12
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    """A terminal subsonic field is a closure/stop, not a supersonic handoff."""

    return True

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'model': self.model,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'interior_point_m': self.interior_point_m,
      'maximum_thermodynamic_residual': self.maximum_thermodynamic_residual,
      'maximum_harmonic_residual': self.maximum_harmonic_residual,
      'maximum_velocity_divergence_residual': self.maximum_velocity_divergence_residual,
      'minimum_mach': self.minimum_mach,
      'maximum_mach': self.maximum_mach,
      'boundary': self.boundary.as_report(),
      'message': self.message,
    }


def _empty_mixed_regime_topology() -> MocTopologyResult:
  return validate_moc_mesh(())


def _field_failure(
  status: MocMixedRegimeFieldStatus,
  boundary: MocMixedRegimeBoundaryResult,
  *,
  nodes: Sequence[MocMixedRegimeFieldSample] = (),
  cells: Sequence[MocCharacteristicCell] = (),
  topology: MocTopologyResult | None = None,
  interior_point_m: tuple[float, float] | None = None,
  maximum_thermodynamic_residual: float | None = None,
  maximum_harmonic_residual: float | None = None,
  maximum_velocity_divergence_residual: float | None = None,
  message: str,
) -> MocMixedRegimeFieldResult:
  return MocMixedRegimeFieldResult(
    status=status,
    boundary=boundary,
    nodes=tuple(nodes),
    cells=tuple(cells),
    topology=_empty_mixed_regime_topology() if topology is None else topology,
    interior_point_m=interior_point_m,
    maximum_thermodynamic_residual=maximum_thermodynamic_residual,
    maximum_harmonic_residual=maximum_harmonic_residual,
    maximum_velocity_divergence_residual=maximum_velocity_divergence_residual,
    minimum_mach=min((sample.mach for sample in nodes), default=None),
    maximum_mach=max((sample.mach for sample in nodes), default=None),
    message=message,
  )


def _isentropic_total_pressure(sample: MocMixedRegimeFieldSample) -> float:
  factor = 1.0 + 0.5 * (sample.gamma - 1.0) * sample.mach * sample.mach
  return sample.static_pressure_Pa * factor ** (sample.gamma / (sample.gamma - 1.0))


def _polygon_signed_area(points: Sequence[tuple[float, float]]) -> float:
  return 0.5 * sum(
    first[0] * second[1] - second[0] * first[1]
    for first, second in zip(points, (*points[1:], points[0]), strict=True)
  )


def _convex_polygon(points: Sequence[tuple[float, float]], tolerance_m: float) -> bool:
  signs: list[float] = []
  for first, second, third in zip(
    points,
    (*points[1:], points[0]),
    (*points[2:], points[0], points[1]),
    strict=True,
  ):
    cross = (
      (second[0] - first[0]) * (third[1] - second[1])
      - (second[1] - first[1]) * (third[0] - second[0])
    )
    if abs(cross) > tolerance_m * tolerance_m:
      signs.append(cross)
  return bool(signs) and all(value > 0.0 for value in signs) or bool(signs) and all(
    value < 0.0 for value in signs
  )


def _relative_residual(actual: float, expected: float) -> float:
  return abs(actual - expected) / max(1.0, abs(actual), abs(expected))


def _triangle_velocity_divergence(
  vertices: tuple[MocMixedRegimeFieldSample, MocMixedRegimeFieldSample, MocMixedRegimeFieldSample],
) -> float:
  first, second, third = vertices
  x1, y1 = first.point_m
  x2, y2 = second.point_m
  x3, y3 = third.point_m
  area_twice = (x2 - x1) * (y3 - y1) - (y2 - y1) * (x3 - x1)
  if abs(area_twice) <= 1.0e-20:
    return float('inf')
  velocities = tuple(
    (
      sample.mach * cos(sample.flow_angle_rad),
      sample.mach * sin(sample.flow_angle_rad),
    )
    for sample in vertices
  )
  dudy = (
    (velocities[0][0] * (y2 - y3)
     + velocities[1][0] * (y3 - y1)
     + velocities[2][0] * (y1 - y2))
    / area_twice
  )
  dvdy = (
    (velocities[0][1] * (x3 - x2)
     + velocities[1][1] * (x1 - x3)
     + velocities[2][1] * (x2 - x1))
    / area_twice
  )
  return abs(dudy + dvdy)


def solve_mixed_regime_subsonic_field(
  boundary: MocMixedRegimeBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  thermodynamic_tolerance: float = 1.0e-8,
  residual_tolerance: float = 1.0e-12,
) -> MocMixedRegimeFieldResult:
  """Solve the declared elliptic/isentrope subsonic reference field.

  The input perimeter is the physical boundary condition.  The solver
  creates a convex fan mesh with one interior control point and sets each
  interior primitive to the arithmetic harmonic extension of the boundary
  values.  It then checks the isentropic total-pressure relation and the
  piecewise-linear dimensionless-velocity divergence on every triangle.

  This intentionally does not accept an open perimeter, infer missing points,
  or extrapolate a subsonic state from the supersonic MOC field.  The one-cell
  fan is a separate reference model with an explicit model label; a future
  higher-order elliptic solver can replace it behind this result contract.
  """

  if not isinstance(boundary, MocMixedRegimeBoundaryResult):
    raise TypeError('boundary must be a MocMixedRegimeBoundaryResult')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('thermodynamic_tolerance', thermodynamic_tolerance),
    ('residual_tolerance', residual_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not boundary.converged:
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      message=f'mixed-regime field requires a converged boundary handoff: {boundary.message}',
    )
  samples = boundary.subsonic_samples
  points = boundary.perimeter_points_m
  if len(samples) < 4 or len(points) != len(samples):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime field requires a closed perimeter with matching scalar samples',
    )
  if any(
    hypot(sample.point_m[0] - point[0], sample.point_m[1] - point[1])
    > position_tolerance_m
    for sample, point in zip(samples, points, strict=True)
  ):
    return _field_failure(
      MocMixedRegimeFieldStatus.BOUNDARY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime scalar sample coordinates do not match the perimeter geometry',
    )
  unique_samples = samples[:-1]
  unique_points = points[:-1]
  if len(unique_samples) < 3:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime field requires at least three unique perimeter vertices',
    )
  area = _polygon_signed_area(unique_points)
  if abs(area) <= position_tolerance_m * position_tolerance_m:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime perimeter has zero signed area',
    )
  if not _convex_polygon(unique_points, position_tolerance_m):
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=samples,
      message='mixed-regime reference field requires a convex perimeter fan',
    )
  center_point = (
    sum(point[0] for point in unique_points) / len(unique_points),
    sum(point[1] for point in unique_points) / len(unique_points),
  )
  center_sample = MocMixedRegimeFieldSample(
    point_m=center_point,
    mach=sum(sample.mach for sample in unique_samples) / len(unique_samples),
    flow_angle_rad=sum(sample.flow_angle_rad for sample in unique_samples) / len(unique_samples),
    static_pressure_Pa=sum(sample.static_pressure_Pa for sample in unique_samples) / len(unique_samples),
    total_pressure_Pa=sum(sample.total_pressure_Pa for sample in unique_samples) / len(unique_samples),
    gamma=sum(sample.gamma for sample in unique_samples) / len(unique_samples),
  )
  nodes = (*unique_samples, center_sample)
  thermodynamic_residual = max(
    _relative_residual(_isentropic_total_pressure(sample), sample.total_pressure_Pa)
    for sample in nodes
  )
  if thermodynamic_residual > thermodynamic_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.THERMODYNAMIC_FAILURE,
      boundary,
      nodes=nodes,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      message=(
        'mixed-regime scalar samples do not satisfy the isentropic '
        f'total-pressure relation: residual={thermodynamic_residual}'
      ),
    )
  harmonic_residual = max(
    value
    for value in (
      abs(center_sample.mach - sum(sample.mach for sample in unique_samples) / len(unique_samples)),
      abs(center_sample.flow_angle_rad - sum(sample.flow_angle_rad for sample in unique_samples) / len(unique_samples)),
      abs(center_sample.static_pressure_Pa - sum(sample.static_pressure_Pa for sample in unique_samples) / len(unique_samples)),
      abs(center_sample.total_pressure_Pa - sum(sample.total_pressure_Pa for sample in unique_samples) / len(unique_samples)),
    )
  )
  cells: list[MocCharacteristicCell] = []
  try:
    for index, (first, second) in enumerate(
      zip(unique_points, (*unique_points[1:], unique_points[0]), strict=True)
    ):
      cells.append(
        MocCharacteristicCell(
          cell_index=index,
          cell_kind='mixed-regime-elliptic-reference',
          vertices_xr_m=(center_point, first, second),
          centerline_indices=(),
          boundary_indices=(index, (index + 1) % len(unique_points)),
        )
      )
  except ValueError as error:
    return _field_failure(
      MocMixedRegimeFieldStatus.GEOMETRY_FAILURE,
      boundary,
      nodes=nodes,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      message=f'mixed-regime fan-cell geometry failed: {error}',
    )
  topology = validate_moc_mesh(tuple(cells))
  if not topology.connected or not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _field_failure(
      MocMixedRegimeFieldStatus.TOPOLOGY_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      message=f'mixed-regime fan topology failed: {topology.message}',
    )
  node_by_index = {index: sample for index, sample in enumerate(unique_samples)}
  node_by_index[len(unique_samples)] = center_sample
  divergence_residual = max(
    _triangle_velocity_divergence((
      center_sample,
      node_by_index[index],
      node_by_index[(index + 1) % len(unique_samples)],
    ))
    for index in range(len(unique_samples))
  )
  if harmonic_residual > residual_tolerance or divergence_residual > residual_tolerance:
    return _field_failure(
      MocMixedRegimeFieldStatus.RESIDUAL_FAILURE,
      boundary,
      nodes=nodes,
      cells=cells,
      topology=topology,
      interior_point_m=center_point,
      maximum_thermodynamic_residual=thermodynamic_residual,
      maximum_harmonic_residual=harmonic_residual,
      maximum_velocity_divergence_residual=divergence_residual,
      message=(
        'mixed-regime elliptic reference residual gate failed: '
        f'harmonic={harmonic_residual}, divergence={divergence_residual}'
      ),
    )
  return MocMixedRegimeFieldResult(
    status=MocMixedRegimeFieldStatus.CONVERGED_ELLIPTIC_FIELD,
    boundary=boundary,
    nodes=nodes,
    cells=tuple(cells),
    topology=topology,
    interior_point_m=center_point,
    maximum_thermodynamic_residual=thermodynamic_residual,
    maximum_harmonic_residual=harmonic_residual,
    maximum_velocity_divergence_residual=divergence_residual,
    minimum_mach=min(sample.mach for sample in nodes),
    maximum_mach=max(sample.mach for sample in nodes),
    message=(
      'elliptic/isentrope subsonic reference field converged on the supplied '
      'closed perimeter; this model remains separate from the supersonic MOC lane'
    ),
  )


def _failure(
  status: MocMixedRegimeBoundaryStatus,
  *,
  terminal: MocMixedRegimeTerminal | None = None,
  supersonic_patch_sample_count: int = 0,
  subsonic_samples: Sequence[MocMixedRegimeFieldSample] = (),
  perimeter_points_m: Sequence[tuple[float, float]] = (),
  supersonic_patch_verified: bool = False,
  subsonic_state_samples_verified: bool = False,
  terminal_continuity_verified: bool = False,
  perimeter_geometry_verified: bool = False,
  total_pressure_lineage_verified: bool = False,
  maximum_terminal_mach_residual: float | None = None,
  maximum_terminal_flow_angle_residual_rad: float | None = None,
  maximum_terminal_static_pressure_residual_Pa: float | None = None,
  maximum_terminal_total_pressure_residual_Pa: float | None = None,
  maximum_total_pressure_gain_Pa: float | None = None,
  message: str,
) -> MocMixedRegimeBoundaryResult:
  return MocMixedRegimeBoundaryResult(
    status=status,
    terminal=terminal,
    supersonic_patch_sample_count=supersonic_patch_sample_count,
    subsonic_samples=tuple(subsonic_samples),
    perimeter_points_m=tuple(perimeter_points_m),
    supersonic_patch_verified=supersonic_patch_verified,
    subsonic_state_samples_verified=subsonic_state_samples_verified,
    terminal_continuity_verified=terminal_continuity_verified,
    perimeter_geometry_verified=perimeter_geometry_verified,
    total_pressure_lineage_verified=total_pressure_lineage_verified,
    maximum_terminal_mach_residual=maximum_terminal_mach_residual,
    maximum_terminal_flow_angle_residual_rad=maximum_terminal_flow_angle_residual_rad,
    maximum_terminal_static_pressure_residual_Pa=maximum_terminal_static_pressure_residual_Pa,
    maximum_terminal_total_pressure_residual_Pa=maximum_terminal_total_pressure_residual_Pa,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain_Pa,
    message=message,
  )


def _terminal_scalars(
  terminal: MocMixedRegimeTerminal,
) -> tuple[tuple[float, float], float, float, float, float, float] | None:
  point = terminal.shock_point_m
  mach = terminal.downstream_mach
  flow_angle = terminal.downstream_flow_angle_rad
  static_pressure = terminal.downstream_pressure_Pa
  total_pressure = terminal.downstream_total_pressure_Pa
  upstream_total_pressure = terminal.upstream_total_pressure_Pa
  if (
    point is None
    or mach is None
    or flow_angle is None
    or static_pressure is None
    or total_pressure is None
    or upstream_total_pressure is None
  ):
    return None
  values = (*point, mach, flow_angle, static_pressure, total_pressure, upstream_total_pressure)
  if not all(isfinite(float(value)) for value in values):
    return None
  if mach <= 0.0 or mach >= 1.0:
    return None
  if static_pressure <= 0.0 or total_pressure <= 0.0 or upstream_total_pressure <= 0.0:
    return None
  if total_pressure > upstream_total_pressure:
    return None
  return (
    (float(point[0]), float(point[1])),
    float(mach),
    float(flow_angle),
    float(static_pressure),
    float(total_pressure),
    float(upstream_total_pressure),
  )


def validate_mixed_regime_boundary(
  terminal: MocMixedRegimeTerminal,
  supersonic_patch: Sequence[MocPostShockBoundaryState],
  *,
  supersonic_patch_converged: bool,
  subsonic_samples: Sequence[MocMixedRegimeFieldSample],
  perimeter_points_m: Sequence[tuple[float, float]] | None = None,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeBoundaryResult:
  """Validate a scalar subsonic perimeter without fabricating MOC states.

  The perimeter is an ordered, explicitly closed path.  Its first and last
  samples must reproduce the terminal shock scalar state.  All points must
  lie downstream of that terminal point.  The open supersonic patch is
  validated independently so a passing scalar perimeter cannot hide a gap in
  the preceding shock-side field.
  """

  if not isinstance(terminal, (MocNormalShockTerminalResult, MocSubsonicShockBoundaryResult)):
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      message='terminal must be a normal-shock or attached subsonic boundary result',
    )
  if not isinstance(supersonic_patch_converged, bool):
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      terminal=terminal,
      message='supersonic_patch_converged must be a bool',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    patch = tuple(supersonic_patch)
    samples = tuple(subsonic_samples)
  except TypeError:
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      terminal=terminal,
      message='supersonic_patch and subsonic_samples must be iterable',
    )
  if not terminal.converged or not terminal.subsonic:
    return _failure(
      MocMixedRegimeBoundaryStatus.TERMINAL_FAILURE,
      terminal=terminal,
      message='terminal must be a converged subsonic shock boundary',
    )
  scalars = _terminal_scalars(terminal)
  if scalars is None:
    return _failure(
      MocMixedRegimeBoundaryStatus.TERMINAL_FAILURE,
      terminal=terminal,
      message='terminal does not expose a complete finite scalar downstream state',
    )
  terminal_point, terminal_mach, terminal_angle, terminal_pressure, terminal_total_pressure, upstream_total_pressure = scalars

  if not supersonic_patch_converged or not patch:
    return _failure(
      MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      message='a converged open supersonic patch is required before subsonic closure',
    )
  for index, boundary_state in enumerate(patch):
    if not isinstance(boundary_state, MocPostShockBoundaryState):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} is not a MocPostShockBoundaryState',
      )
    state = boundary_state.state
    if state.mach <= 1.0:
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} is not supersonic',
      )
    if (
      abs(state.x_m - boundary_state.point_m[0]) > position_tolerance_m
      or abs(state.y_m - boundary_state.point_m[1]) > position_tolerance_m
    ):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} state coordinates do not match its point',
      )
    if (
      not isfinite(boundary_state.upstream_total_pressure_Pa)
      or not isfinite(boundary_state.downstream_total_pressure_Pa)
      or boundary_state.upstream_total_pressure_Pa <= 0.0
      or boundary_state.downstream_total_pressure_Pa <= 0.0
      or boundary_state.downstream_total_pressure_Pa >= boundary_state.upstream_total_pressure_Pa
    ):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} does not carry a strict total-pressure loss',
      )
  patch_verified = True

  if len(samples) < 4:
    return _failure(
      MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=samples,
      message='subsonic perimeter requires at least four scalar samples',
    )
  if any(not isinstance(sample, MocMixedRegimeFieldSample) for sample in samples):
    return _failure(
      MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=tuple(sample for sample in samples if isinstance(sample, MocMixedRegimeFieldSample)),
      message='subsonic_samples must contain MocMixedRegimeFieldSample values',
    )
  points = tuple(samples[index].point_m for index in range(len(samples)))
  if perimeter_points_m is not None:
    try:
      points = tuple((float(point[0]), float(point[1])) for point in perimeter_points_m)
    except (IndexError, TypeError, ValueError):
      return _failure(
        MocMixedRegimeBoundaryStatus.INVALID_INPUT,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        supersonic_patch_verified=patch_verified,
        subsonic_samples=samples,
        message='perimeter_points_m must contain finite two-coordinate points',
      )
    if len(points) != len(samples) or any(not all(isfinite(value) for value in point) for point in points):
      return _failure(
        MocMixedRegimeBoundaryStatus.INVALID_INPUT,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        supersonic_patch_verified=patch_verified,
        subsonic_samples=samples,
        perimeter_points_m=points,
        message='perimeter_points_m must match the scalar sample count and be finite',
      )
  if len(points) < 4:
    return _failure(
      MocMixedRegimeBoundaryStatus.GEOMETRY_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=samples,
      perimeter_points_m=points,
      message='subsonic perimeter requires at least four geometry points',
    )

  closed = hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1]) <= position_tolerance_m
  downstream = all(point[0] >= terminal_point[0] - position_tolerance_m for point in points)
  distinct_segments = all(
    hypot(second[0] - first[0], second[1] - first[1]) > position_tolerance_m
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  terminal_geometry_residual = max(
    hypot(points[0][0] - terminal_point[0], points[0][1] - terminal_point[1]),
    hypot(points[-1][0] - terminal_point[0], points[-1][1] - terminal_point[1]),
  )
  geometry_verified = closed and downstream and distinct_segments and terminal_geometry_residual <= position_tolerance_m
  if not geometry_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.GEOMETRY_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      perimeter_geometry_verified=False,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=None,
      maximum_terminal_flow_angle_residual_rad=None,
      maximum_terminal_static_pressure_residual_Pa=None,
      maximum_terminal_total_pressure_residual_Pa=None,
      maximum_total_pressure_gain_Pa=None,
      message=(
        'subsonic perimeter must be a distinct explicitly closed downstream '
        f'path anchored at the terminal point; closed={closed}, downstream={downstream}, '
        f'distinct_segments={distinct_segments}, terminal_residual_m={terminal_geometry_residual}'
      ),
    )

  seam_samples = (samples[0], samples[-1])
  mach_residual = max(abs(sample.mach - terminal_mach) for sample in seam_samples)
  angle_residual = max(abs(sample.flow_angle_rad - terminal_angle) for sample in seam_samples)
  static_residual = max(abs(sample.static_pressure_Pa - terminal_pressure) for sample in seam_samples)
  total_residual = max(abs(sample.total_pressure_Pa - terminal_total_pressure) for sample in seam_samples)
  seam_verified = (
    mach_residual <= state_tolerance
    and angle_residual <= state_tolerance
    and static_residual <= pressure_tolerance * max(1.0, abs(terminal_pressure))
    and total_residual <= pressure_tolerance * max(1.0, abs(terminal_total_pressure))
  )
  if not seam_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      terminal_continuity_verified=False,
      perimeter_geometry_verified=True,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=mach_residual,
      maximum_terminal_flow_angle_residual_rad=angle_residual,
      maximum_terminal_static_pressure_residual_Pa=static_residual,
      maximum_terminal_total_pressure_residual_Pa=total_residual,
      message='subsonic perimeter endpoints do not reproduce the scalar terminal shock state',
    )

  maximum_total_pressure_gain = max(
    sample.total_pressure_Pa - terminal_total_pressure
    for sample in samples
  )
  lineage_verified = maximum_total_pressure_gain <= pressure_tolerance * max(
    1.0,
    abs(terminal_total_pressure),
    abs(upstream_total_pressure),
  )
  if not lineage_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      terminal_continuity_verified=True,
      perimeter_geometry_verified=True,
      total_pressure_lineage_verified=False,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=mach_residual,
      maximum_terminal_flow_angle_residual_rad=angle_residual,
      maximum_terminal_static_pressure_residual_Pa=static_residual,
      maximum_terminal_total_pressure_residual_Pa=total_residual,
      maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
      message='subsonic perimeter contains a total-pressure gain over the terminal shock state',
    )

  return MocMixedRegimeBoundaryResult(
    status=MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF,
    terminal=terminal,
    supersonic_patch_sample_count=len(patch),
    subsonic_samples=samples,
    perimeter_points_m=points,
    supersonic_patch_verified=patch_verified,
    subsonic_state_samples_verified=True,
    terminal_continuity_verified=True,
    perimeter_geometry_verified=True,
    total_pressure_lineage_verified=True,
    maximum_terminal_mach_residual=mach_residual,
    maximum_terminal_flow_angle_residual_rad=angle_residual,
    maximum_terminal_static_pressure_residual_Pa=static_residual,
    maximum_terminal_total_pressure_residual_Pa=total_residual,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
    message=(
      'scalar subsonic perimeter handoff passed shock-seam, open-supersonic-patch, '
      'geometry, and total-pressure lineage checks; a subsonic field mesh is still pending'
    ),
  )
