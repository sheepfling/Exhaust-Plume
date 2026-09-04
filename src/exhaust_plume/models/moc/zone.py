"""Assembly of the reflected planar characteristic zone.

This module assembles the compatible characteristic network between the
centerline and the pressure-matched free boundary.  It intentionally stops at
that open physical boundary: no compression state, shock endpoint, or
downstream total-pressure continuation is inferred here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite, sqrt
from typing import Sequence

import numpy as np

from exhaust_plume.geometry.contracts import GeometryStatus
from exhaust_plume.geometry.polygons import validate_polygon
from exhaust_plume.models.moc.boundary import MocReflectedBoundaryResult
from exhaust_plume.models.moc.fan import MocExpansionFanResult
from exhaust_plume.models.moc.primitives import (
  CharacteristicPointResult,
  CharacteristicState,
  interior_characteristic_point,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh

__all__ = (
  'MocCharacteristicCell',
  'MocCharacteristicNode',
  'MocFanReflectedInterfaceResult',
  'MocInterfaceStatus',
  'MocReflectedZoneShockCouplingResult',
  'MocReflectedZoneShockCouplingStatus',
  'MocZoneAssemblyStatus',
  'MocReflectedCharacteristicZoneResult',
  'assemble_reflected_characteristic_zone',
  'sample_reflected_zone_along_shock_path',
  'validate_fan_reflected_interface',
)


class MocZoneAssemblyStatus(str, Enum):
  """Outcome of assembling a reflected characteristic network."""

  CONVERGED_OPEN = 'converged_open'
  INVALID_INPUT = 'invalid_input'
  GEOMETRY_FAILURE = 'geometry_failure'
  TOPOLOGY_FAILURE = 'topology_failure'
####


class MocInterfaceStatus(str, Enum):
  """Outcome of the fan/reflected centerline interface check."""

  ALIGNED = 'aligned'
  MISALIGNED = 'misaligned'
  INVALID_INPUT = 'invalid_input'
####


class MocReflectedZoneShockCouplingStatus(str, Enum):
  """Outcome of sampling a candidate shock inside the solved reflected zone."""

  CONVERGED_REFLECTED_ZONE_FIELD = 'converged_reflected_zone_field'
  INVALID_INPUT = 'invalid_input'
  OUTSIDE_DOMAIN = 'outside_reflected_zone_domain'
  PRESSURE_FAILURE = 'pressure_failure'
####


@dataclass(frozen=True, slots=True)
class MocFanReflectedInterfaceResult:
  """Coordinate residuals between the fan grid and reflected march.

  The fan and reflected march must expose the same averaged-characteristic
  compatibility grid before their cells are combined. The fan also retains
  its direct lip-ray coordinates separately for diagnostic comparison.
  """

  status: MocInterfaceStatus
  coordinate_residuals_m: tuple[float, ...]
  maximum_coordinate_residual_m: float | None
  position_tolerance_m: float
  message: str = ''

  @property
  def aligned(self) -> bool:
    return self.status is MocInterfaceStatus.ALIGNED
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedZoneShockCouplingResult:
  """Domain-bounded upstream samples along a candidate shock path.

  A converged result means every requested point was found in the already
  solved reflected lattice.  ``OUTSIDE_DOMAIN`` is deliberately a normal
  solver outcome: it identifies the first point for which an upstream
  characteristic strip is still missing instead of extrapolating the last
  reflected state.
  """

  status: MocReflectedZoneShockCouplingStatus
  shock_points_m: tuple[tuple[float, float], ...]
  upstream_states: tuple[CharacteristicState, ...]
  upstream_pressure_Pa: tuple[float, ...]
  first_missing_sample_index: int | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocReflectedZoneShockCouplingStatus.CONVERGED_REFLECTED_ZONE_FIELD
  ####

  @property
  def sampled_count(self) -> int:
    return len(self.upstream_states)
  ####

  @property
  def last_valid_point_m(self) -> tuple[float, float] | None:
    if not self.upstream_states:
      return None
    ####
    state = self.upstream_states[-1]
    return state.x_m, state.y_m
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'requested_sample_count': len(self.shock_points_m),
      'sampled_count': self.sampled_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'last_valid_point_m': self.last_valid_point_m,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocCharacteristicNode:
  """One compatible intersection in the reflected characteristic lattice."""

  centerline_index: int
  boundary_index: int
  point_m: tuple[float, float]
  state: CharacteristicState
  point_result: CharacteristicPointResult
  total_pressure_Pa: float | None = None

  def __post_init__(self) -> None:
    if self.total_pressure_Pa is not None:
      if not isfinite(float(self.total_pressure_Pa)) or self.total_pressure_Pa <= 0.0:
        raise ValueError('total_pressure_Pa must be finite and positive when supplied')
      ####
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocCharacteristicCell:
  """A validated triangular or quadrilateral characteristic cell."""

  cell_index: int
  cell_kind: str
  vertices_xr_m: tuple[tuple[float, float], ...]
  centerline_indices: tuple[int, ...]
  boundary_indices: tuple[int, ...]
  geometry_status: GeometryStatus = GeometryStatus.VALID

  def __post_init__(self) -> None:
    if len(self.vertices_xr_m) not in (3, 4):
      raise ValueError('characteristic cells must be triangular or quadrilateral')
    ####
    validation = validate_polygon(np.asarray(self.vertices_xr_m, dtype=float))
    if not validation.is_valid:
      raise ValueError(f'characteristic cell polygon is invalid: {validation.status.value}')
    ####
    object.__setattr__(self, 'geometry_status', GeometryStatus.VALID)
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedCharacteristicZoneResult:
  """An assembled but physically open reflected characteristic zone.

  ``status`` reports numerical assembly of the characteristic network.  A
  ``CONVERGED_OPEN`` result is deliberately not a closed shock cell: the
  perimeter is topologically connected, while compression/shock closure and
  downstream total-pressure bookkeeping remain explicit pending gates.
  """

  status: MocZoneAssemblyStatus
  characteristic_count: int
  nodes: tuple[MocCharacteristicNode, ...]
  cells: tuple[MocCharacteristicCell, ...]
  topology: MocTopologyResult
  coverage_area_m2: float | None
  coverage_area_residual_m2: float | None
  physical_closure_status: str
  shock_closure_status: str
  centerline_states: tuple[CharacteristicState, ...] = ()
  boundary_states: tuple[CharacteristicState, ...] = ()
  total_pressure_Pa: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if self.total_pressure_Pa is not None and (
      not isfinite(float(self.total_pressure_Pa)) or self.total_pressure_Pa <= 0.0
    ):
      raise ValueError('total_pressure_Pa must be finite and positive when supplied')
    ####
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocZoneAssemblyStatus.CONVERGED_OPEN
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether this reflected zone has a physical shock/downstream closure."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Whether this open zone must remain outside a physical chain cell."""

    return True
  ####

  @property
  def node_count(self) -> int:
    return len(self.nodes)
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  def _domain_points(self) -> tuple[tuple[float, float], ...]:
    """Return the mesh vertices that bound the assembled reflected zone."""

    return tuple(
      (float(point[0]), float(point[1]))
      for cell in self.cells
      for point in cell.vertices_xr_m
    )
  ####

  @property
  def domain_x_extent_m(self) -> tuple[float, float] | None:
    """Return the finite axial extent available to bounded state probes."""

    points = self._domain_points()
    if not points or any(
      not all(isfinite(value) for value in point)
      for point in points
    ):
      return None
    ####
    x_values = tuple(point[0] for point in points)
    return min(x_values), max(x_values)
  ####

  @property
  def domain_y_extent_m(self) -> tuple[float, float] | None:
    """Return the finite transverse extent available to bounded state probes."""

    points = self._domain_points()
    if not points or any(
      not all(isfinite(value) for value in point)
      for point in points
    ):
      return None
    ####
    y_values = tuple(point[1] for point in points)
    return min(y_values), max(y_values)
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether the open zone carries bounded state and pressure samples."""

    return bool(
      self.converged
      and self.cells
      and len(self.centerline_states) >= 2
      and len(self.centerline_states) == len(self.boundary_states)
      and all(node.total_pressure_Pa is not None for node in self.nodes)
      and self.total_pressure_Pa is not None
      and isfinite(float(self.total_pressure_Pa))
      and self.total_pressure_Pa > 0.0
      and self.domain_x_extent_m is not None
      and self.domain_y_extent_m is not None
    )
  ####

  def as_report(self) -> dict[str, object]:
    """Serialize open-zone geometry and its bounded sampling capability."""

    return {
      'status': self.status.value,
      'converged': self.converged,
      'characteristic_count': self.characteristic_count,
      'node_count': self.node_count,
      'cell_count': self.cell_count,
      'topology_status': self.topology.status.value,
      'topology_connected': self.topology.connected,
      'topology_forms_closed_zone': self.topology.forms_closed_zone,
      'topology_nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      'coverage_area_m2': self.coverage_area_m2,
      'coverage_area_residual_m2': self.coverage_area_residual_m2,
      'physical_closure_status': self.physical_closure_status,
      'physical_closure_verified': self.physical_closure_verified,
      'shock_closure_status': self.shock_closure_status,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'claim_fidelity_ceiling': 'open-planar-moc',
      'state_sampling_available': self.state_sampling_available,
      'state_sampling_model': 'bounded-cell-barycentric-no-extrapolation',
      'domain_x_extent_m': self.domain_x_extent_m,
      'domain_y_extent_m': self.domain_y_extent_m,
      'centerline_sample_count': len(self.centerline_states),
      'boundary_sample_count': len(self.boundary_states),
      'total_pressure_Pa': self.total_pressure_Pa,
      'cell_kind_counts': {
        cell_kind: sum(cell.cell_kind == cell_kind for cell in self.cells)
        for cell_kind in sorted({cell.cell_kind for cell in self.cells})
      },
      'message': self.message,
    }
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Interpolate a compatible state inside the solved reflected lattice.

    The sampler is intentionally domain-bounded: it returns ``None`` outside
    the assembled open zone instead of extrapolating a shock-side state. This
    makes the reflected-field coupling gate explicit for the next shock solve.
    Interpolation is performed in ``theta``/Prandtl--Meyer-angle space so the
    returned state remains supersonic and uses the common gamma.
    """

    if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
      raise ValueError('point_m must contain two finite coordinates')
    ####
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    node_by_key = {
      (node.centerline_index, node.boundary_index): node
      for node in self.nodes
    }
    point = (float(point_m[0]), float(point_m[1]))
    for cell in self.cells:
      samples = _zone_cell_samples(self, cell, node_by_key)
      if samples is None:
        continue
      ####
      vertices, states = samples
      weights = _polygon_interpolation_weights(
        point,
        vertices,
        tolerance_m=position_tolerance_m,
      )
      if weights is None:
        continue
      ####
      theta = sum(
        weight * state.theta_rad
        for weight, state in zip(weights, states, strict=True)
      )
      nu = sum(
        weight * state.nu_rad
        for weight, state in zip(weights, states, strict=True)
      )
      inverse = inverse_prandtl_meyer_angle_rad(nu, states[0].gamma)
      if not inverse.converged or inverse.value is None:
        return None
      ####
      return CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=theta,
        mach=inverse.value,
        gamma=states[0].gamma,
      )
    ####
    return None
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return isentropic static pressure for a sampled reflected state."""

    if self.total_pressure_Pa is None:
      return None
    ####
    state = self.state_at(point_m, position_tolerance_m=position_tolerance_m)
    if state is None:
      return None
    ####
    pressure_ratio = (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))
    return self.total_pressure_Pa / pressure_ratio
  ####
####


def sample_reflected_zone_along_shock_path(
  zone: MocReflectedCharacteristicZoneResult,
  shock_points_m: Sequence[tuple[float, float]],
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocReflectedZoneShockCouplingResult:
  """Sample a candidate shock path without extrapolating the reflected zone.

  The path is ordered from its outer attachment toward the centerline.  This
  helper is intentionally only a coupling probe: it does not generate a
  missing characteristic strip or alter the open reflected-zone mesh.
  """

  if not isinstance(zone, MocReflectedCharacteristicZoneResult):
    return MocReflectedZoneShockCouplingResult(
      status=MocReflectedZoneShockCouplingStatus.INVALID_INPUT,
      shock_points_m=(),
      upstream_states=(),
      upstream_pressure_Pa=(),
      first_missing_sample_index=None,
      message='zone must be a MocReflectedCharacteristicZoneResult',
    )
  ####
  try:
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock_points_m
    )
  except (TypeError, IndexError, ValueError):
    return MocReflectedZoneShockCouplingResult(
      status=MocReflectedZoneShockCouplingStatus.INVALID_INPUT,
      shock_points_m=(),
      upstream_states=(),
      upstream_pressure_Pa=(),
      first_missing_sample_index=None,
      message='shock_points_m must contain finite two-coordinate points',
    )
  ####
  if len(points) < 2 or any(not all(isfinite(value) for value in point) for point in points):
    return MocReflectedZoneShockCouplingResult(
      status=MocReflectedZoneShockCouplingStatus.INVALID_INPUT,
      shock_points_m=points,
      upstream_states=(),
      upstream_pressure_Pa=(),
      first_missing_sample_index=None,
      message='shock path coupling requires at least two finite points',
    )
  ####
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  for index, (previous, current) in enumerate(zip(points, points[1:]), start=1):
    if current[0] <= previous[0] + position_tolerance_m or current[1] > previous[1] + position_tolerance_m:
      return MocReflectedZoneShockCouplingResult(
        status=MocReflectedZoneShockCouplingStatus.INVALID_INPUT,
        shock_points_m=points,
        upstream_states=(),
        upstream_pressure_Pa=(),
        first_missing_sample_index=index,
        message=(
          'shock path must be strictly downstream in x and nonincreasing in y'
        ),
      )
    ####
  ####

  states: list[CharacteristicState] = []
  pressures: list[float] = []
  for index, point in enumerate(points):
    state = zone.state_at(point, position_tolerance_m=position_tolerance_m)
    pressure = zone.static_pressure_at(point, position_tolerance_m=position_tolerance_m)
    if state is None:
      return MocReflectedZoneShockCouplingResult(
        status=MocReflectedZoneShockCouplingStatus.OUTSIDE_DOMAIN,
        shock_points_m=points,
        upstream_states=tuple(states),
        upstream_pressure_Pa=tuple(pressures),
        first_missing_sample_index=index,
        message=(
          f'reflected characteristic zone has no upstream state at shock sample {index}'
        ),
      )
    ####
    if pressure is None or not isfinite(float(pressure)) or float(pressure) <= 0.0:
      return MocReflectedZoneShockCouplingResult(
        status=MocReflectedZoneShockCouplingStatus.PRESSURE_FAILURE,
        shock_points_m=points,
        upstream_states=tuple(states),
        upstream_pressure_Pa=tuple(pressures),
        first_missing_sample_index=index,
        message=(
          f'reflected characteristic zone has no valid static pressure at shock sample {index}'
        ),
      )
    ####
    states.append(state)
    pressures.append(float(pressure))
  ####
  return MocReflectedZoneShockCouplingResult(
    status=MocReflectedZoneShockCouplingStatus.CONVERGED_REFLECTED_ZONE_FIELD,
    shock_points_m=points,
    upstream_states=tuple(states),
    upstream_pressure_Pa=tuple(pressures),
    first_missing_sample_index=None,
    message='every shock sample lies inside the solved reflected characteristic zone',
  )
####


def _zone_cell_samples(
  zone: MocReflectedCharacteristicZoneResult,
  cell: MocCharacteristicCell,
  node_by_key: dict[tuple[int, int], MocCharacteristicNode],
) -> tuple[tuple[tuple[float, float], ...], tuple[CharacteristicState, ...]] | None:
  """Return ordered vertex/state samples for one reflected-zone cell."""

  def node_sample(key: tuple[int, int]) -> tuple[tuple[float, float], CharacteristicState] | None:
    node = node_by_key.get(key)
    return None if node is None else (node.point_m, node.state)
  ####

  if cell.cell_kind == 'axis-strip':
    if len(cell.centerline_indices) != 2 or not zone.centerline_states:
      return None
    ####
    first, second = cell.centerline_indices
    if not (0 <= first < len(zone.centerline_states) and 0 <= second < len(zone.centerline_states)):
      return None
    ####
    samples = (
      (cell.vertices_xr_m[0], zone.centerline_states[first]),
      (cell.vertices_xr_m[1], zone.centerline_states[second]),
      node_sample((second, 0)),
      node_sample((first, 0)),
    )
  elif cell.cell_kind == 'interior':
    if len(cell.centerline_indices) != 2 or len(cell.boundary_indices) != 2:
      return None
    ####
    row, next_row = cell.centerline_indices
    column, next_column = cell.boundary_indices
    samples = (
      node_sample((row, column)),
      node_sample((next_row, column)),
      node_sample((next_row, next_column)),
      node_sample((row, next_column)),
    )
  elif cell.cell_kind == 'free-boundary-strip':
    if len(cell.boundary_indices) != 2:
      return None
    ####
    first, second = cell.boundary_indices
    samples = (
      node_sample((first, first)),
      node_sample((second, first)),
      node_sample((second, second)),
    )
  else:
    return None
  ####
  if any(sample is None for sample in samples):
    return None
  ####
  resolved = tuple(sample for sample in samples if sample is not None)
  return tuple(cell.vertices_xr_m), tuple(sample[1] for sample in resolved)
####


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
  ####
  px, py = point
  first = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
  second = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
  third = 1.0 - first - second
  if min(first, second, third) < -1.0e-10 or max(first, second, third) > 1.0 + 1.0e-10:
    return None
  ####
  return first, second, third
####


def _polygon_interpolation_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  *,
  tolerance_m: float,
) -> tuple[float, ...] | None:
  if len(vertices) == 3:
    return _triangle_interpolation_weights(point, vertices, tolerance_m=tolerance_m)
  ####
  first = _triangle_interpolation_weights(
    point,
    (vertices[0], vertices[1], vertices[2]),
    tolerance_m=tolerance_m,
  )
  if first is not None:
    return first[0], first[1], first[2], 0.0
  ####
  second = _triangle_interpolation_weights(
    point,
    (vertices[0], vertices[2], vertices[3]),
    tolerance_m=tolerance_m,
  )
  if second is not None:
    return second[0], 0.0, second[1], second[2]
  ####
  return None
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def validate_fan_reflected_interface(
  fan: MocExpansionFanResult,
  reflected_boundary: MocReflectedBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocFanReflectedInterfaceResult:
  """Check whether fan axis vertices match reflected centerline coordinates.

  A misaligned result is diagnostic evidence, not a numerical failure of
  either open primitive. The caller must resolve the coordinate mismatch with
  a compatible interface construction before combining their cells.
  """

  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  if not fan.converged:
    return MocFanReflectedInterfaceResult(
      status=MocInterfaceStatus.INVALID_INPUT,
      coordinate_residuals_m=(),
      maximum_coordinate_residual_m=None,
      position_tolerance_m=position_tolerance_m,
      message=f'lip fan is not converged: {fan.message}',
    )
  ####
  if not reflected_boundary.converged:
    return MocFanReflectedInterfaceResult(
      status=MocInterfaceStatus.INVALID_INPUT,
      coordinate_residuals_m=(),
      maximum_coordinate_residual_m=None,
      position_tolerance_m=position_tolerance_m,
      message=f'reflected free boundary is not converged: {reflected_boundary.message}',
    )
  ####
  if (
    len(fan.centerline_points_m) != len(reflected_boundary.centerline_states)
    or len(fan.centerline_states) != len(fan.centerline_points_m)
  ):
    return MocFanReflectedInterfaceResult(
      status=MocInterfaceStatus.INVALID_INPUT,
      coordinate_residuals_m=(),
      maximum_coordinate_residual_m=None,
      position_tolerance_m=position_tolerance_m,
      message='fan and reflected centerline arrays have inconsistent lengths',
    )
  ####
  fan_internal_residual = max(
    (
      sqrt(
        (point[0] - state.x_m) ** 2
        + (point[1] - state.y_m) ** 2
      )
      for point, state in zip(fan.centerline_points_m, fan.centerline_states)
    ),
    default=0.0,
  )
  if fan_internal_residual > position_tolerance_m:
    return MocFanReflectedInterfaceResult(
      status=MocInterfaceStatus.INVALID_INPUT,
      coordinate_residuals_m=(),
      maximum_coordinate_residual_m=fan_internal_residual,
      position_tolerance_m=position_tolerance_m,
      message='fan centerline states do not reproduce its compatibility grid',
    )
  ####
  residuals = tuple(
    sqrt(
      (fan_point[0] - state.x_m) ** 2
      + (fan_point[1] - state.y_m) ** 2
    )
    for fan_point, state in zip(fan.centerline_points_m, reflected_boundary.centerline_states)
  )
  maximum_residual = max(residuals, default=None)
  if maximum_residual is None or maximum_residual <= position_tolerance_m:
    return MocFanReflectedInterfaceResult(
      status=MocInterfaceStatus.ALIGNED,
      coordinate_residuals_m=residuals,
      maximum_coordinate_residual_m=maximum_residual,
      position_tolerance_m=position_tolerance_m,
    )
  ####
  return MocFanReflectedInterfaceResult(
    status=MocInterfaceStatus.MISALIGNED,
    coordinate_residuals_m=residuals,
    maximum_coordinate_residual_m=maximum_residual,
    position_tolerance_m=position_tolerance_m,
    message=(
      'fan lip-ray centerline points and reflected compatibility coordinates '
      'are not coincident; an explicit characteristic interface construction '
      'is required before combining their cells'
    ),
  )
####


def _failure(
  *,
  status: MocZoneAssemblyStatus,
  characteristic_count: int,
  nodes: tuple[MocCharacteristicNode, ...] = (),
  cells: tuple[MocCharacteristicCell, ...] = (),
  topology: MocTopologyResult | None = None,
  coverage_area_m2: float | None = None,
  coverage_area_residual_m2: float | None = None,
  message: str,
) -> MocReflectedCharacteristicZoneResult:
  return MocReflectedCharacteristicZoneResult(
    status=status,
    characteristic_count=characteristic_count,
    nodes=nodes,
    cells=cells,
    topology=_empty_topology() if topology is None else topology,
    coverage_area_m2=coverage_area_m2,
    coverage_area_residual_m2=coverage_area_residual_m2,
    physical_closure_status='not_assembled',
    shock_closure_status='not_assembled',
    message=message,
  )
####


def _signed_area(vertices: tuple[tuple[float, float], ...]) -> float:
  return 0.5 * sum(
    vertices[index][0] * vertices[(index + 1) % len(vertices)][1]
    - vertices[(index + 1) % len(vertices)][0] * vertices[index][1]
    for index in range(len(vertices))
  )
####


def _coverage_area(
  cells: tuple[MocCharacteristicCell, ...],
  *,
  vertex_tolerance_m: float,
) -> tuple[float, float] | None:
  """Return ``(perimeter_area, cell_area_residual)`` for one cell zone."""

  if not cells:
    return None
  ####
  signed_areas = [_signed_area(cell.vertices_xr_m) for cell in cells]
  if not all(isfinite(value) for value in signed_areas):
    return None
  ####
  if any(value == 0.0 for value in signed_areas) or (
    min(signed_areas) < 0.0 < max(signed_areas)
  ):
    return None
  ####
  edge_counts: dict[tuple[tuple[int, int], tuple[int, int]], int] = {}
  vertex_points: dict[tuple[int, int], tuple[float, float]] = {}
  for cell in cells:
    keys = []
    for point in cell.vertices_xr_m:
      key = round(point[0] / vertex_tolerance_m), round(point[1] / vertex_tolerance_m)
      keys.append(key)
      vertex_points[key] = point
    ####
    for first, second in zip(keys, (*keys[1:], keys[0])):
      edge = (first, second) if first <= second else (second, first)
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
    ####
  ####
  boundary_edges = [edge for edge, count in edge_counts.items() if count == 1]
  if not boundary_edges:
    return None
  ####
  boundary_graph: dict[tuple[int, int], list[tuple[int, int]]] = {}
  for first, second in boundary_edges:
    boundary_graph.setdefault(first, []).append(second)
    boundary_graph.setdefault(second, []).append(first)
  ####
  if not all(len(neighbors) == 2 for neighbors in boundary_graph.values()):
    return None
  ####
  start = next(iter(boundary_graph))
  cycle = [start]
  previous: tuple[int, int] | None = None
  current = start
  while True:
    neighbors = boundary_graph[current]
    next_vertex = neighbors[0] if neighbors[0] != previous else neighbors[1]
    if next_vertex == start:
      break
    ####
    if next_vertex in cycle:
      return None
    ####
    cycle.append(next_vertex)
    previous, current = current, next_vertex
    if len(cycle) > len(boundary_graph):
      return None
    ####
  ####
  if len(cycle) != len(boundary_graph):
    return None
  ####
  perimeter_vertices = tuple(vertex_points[key] for key in cycle)
  perimeter_area = abs(_signed_area(perimeter_vertices))
  cell_area = sum(abs(value) for value in signed_areas)
  return perimeter_area, cell_area - perimeter_area
####


def assemble_reflected_characteristic_zone(
  fan: MocExpansionFanResult,
  reflected_boundary: MocReflectedBoundaryResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  total_pressure_Pa: float | None = None,
) -> MocReflectedCharacteristicZoneResult:
  """Assemble the reflected centerline/free-boundary characteristic lattice.

  The lattice has three explicit parts: an axis strip, interior
  characteristic quadrilaterals, and a triangular strip terminating on the
  pressure-matched free boundary.  Boundary diagonal nodes are required to
  reproduce the supplied free-boundary points; this prevents a source-angle
  or marching-angle inconsistency from being hidden by topology alone.

  The returned mesh is an open physical solver lane.  Its ``forms_closed_zone``
  topology flag means that the finite cells have one connected polygonal
  perimeter; it does not mean that a shock or downstream physical closure has
  been solved.
  """

  if not isfinite(position_tolerance_m) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  if not isfinite(invariant_tolerance) or invariant_tolerance <= 0.0:
    raise ValueError('invariant_tolerance must be finite and positive')
  ####
  if total_pressure_Pa is not None and (
    not isfinite(float(total_pressure_Pa)) or total_pressure_Pa <= 0.0
  ):
    raise ValueError('total_pressure_Pa must be finite and positive when supplied')
  ####
  if not fan.converged:
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=0,
      message=f'lip fan is not converged: {fan.message}',
    )
  ####
  if not reflected_boundary.converged:
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=0,
      message=f'reflected free boundary is not converged: {reflected_boundary.message}',
    )
  ####
  centerline_states = reflected_boundary.centerline_states
  boundary_states = reflected_boundary.boundary_states
  if len(centerline_states) < 3:
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=0,
      message='reflected characteristic assembly requires at least two intervals',
    )
  ####
  expected_count = len(centerline_states)
  if (
    len(fan.states) != expected_count
    or len(fan.lip_states) != expected_count
    or len(fan.centerline_points_m) != expected_count
    or len(boundary_states) != expected_count
    or len(reflected_boundary.boundary_points_m) != expected_count
  ):
    return _failure(
      status=MocZoneAssemblyStatus.INVALID_INPUT,
      characteristic_count=max(0, expected_count - 1),
      message='fan, centerline, and reflected-boundary arrays have inconsistent lengths',
    )
  ####
  characteristic_count = expected_count - 1
  nodes_by_index: dict[tuple[int, int], MocCharacteristicNode] = {}
  for centerline_index in range(expected_count):
    for boundary_index in range(centerline_index + 1):
      point_result = interior_characteristic_point(
        centerline_states[centerline_index],
        boundary_states[boundary_index],
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
      )
      if not point_result.converged or point_result.state is None or point_result.point_m is None:
        nodes = tuple(nodes_by_index.values())
        return _failure(
          status=MocZoneAssemblyStatus.GEOMETRY_FAILURE,
          characteristic_count=characteristic_count,
          nodes=nodes,
          message=(
            f'characteristic node ({centerline_index}, {boundary_index}) failed: '
            f'{point_result.message}'
          ),
        )
      ####
      point = point_result.point_m
      if centerline_index == boundary_index:
        boundary_point = reflected_boundary.boundary_points_m[boundary_index]
        discrepancy = sqrt(
          (point[0] - boundary_point[0]) ** 2
          + (point[1] - boundary_point[1]) ** 2
        )
        if discrepancy > position_tolerance_m:
          nodes = tuple(nodes_by_index.values())
          return _failure(
            status=MocZoneAssemblyStatus.GEOMETRY_FAILURE,
            characteristic_count=characteristic_count,
            nodes=nodes,
            message=(
              f'boundary diagonal node ({centerline_index}, {boundary_index}) '
              f'does not reproduce the supplied boundary point; residual={discrepancy}'
            ),
          )
        ####
        point = (float(boundary_point[0]), float(boundary_point[1]))
      ####
      nodes_by_index[(centerline_index, boundary_index)] = MocCharacteristicNode(
        centerline_index=centerline_index,
        boundary_index=boundary_index,
        point_m=(float(point[0]), float(point[1])),
        state=point_result.state,
        point_result=point_result,
        total_pressure_Pa=total_pressure_Pa,
      )
    ####
  ####
  nodes = tuple(nodes_by_index.values())

  def node_point(centerline_index: int, boundary_index: int) -> tuple[float, float]:
    return nodes_by_index[(centerline_index, boundary_index)].point_m
  ####

  def axis_point(index: int) -> tuple[float, float]:
    state = centerline_states[index]
    if not isfinite(state.x_m) or not isfinite(state.y_m):
      raise ValueError(f'centerline state {index} has a non-finite coordinate')
    ####
    if abs(state.y_m) > position_tolerance_m:
      raise ValueError(f'centerline state {index} is not on the symmetry line')
    ####
    return state.x_m, 0.0
  ####

  cells_list: list[MocCharacteristicCell] = []
  try:
    for index in range(characteristic_count):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='axis-strip',
          vertices_xr_m=(
            axis_point(index),
            axis_point(index + 1),
            node_point(index + 1, 0),
            node_point(index, 0),
          ),
          centerline_indices=(index, index + 1),
          boundary_indices=(0,),
        )
      )
    ####
    for row in range(1, expected_count - 1):
      for column in range(row):
        cells_list.append(
          MocCharacteristicCell(
            cell_index=len(cells_list),
            cell_kind='interior',
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
      ####
    ####
    for index in range(characteristic_count):
      cells_list.append(
        MocCharacteristicCell(
          cell_index=len(cells_list),
          cell_kind='free-boundary-strip',
          vertices_xr_m=(
            node_point(index, index),
            node_point(index + 1, index),
            node_point(index + 1, index + 1),
          ),
          centerline_indices=(index + 1,),
          boundary_indices=(index, index + 1),
        )
      )
    ####
  except (KeyError, ValueError) as error:
    return _failure(
      status=MocZoneAssemblyStatus.GEOMETRY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=tuple(cells_list),
      message=f'characteristic cell geometry failed: {error}',
    )
  ####
  cells = tuple(cells_list)
  topology = validate_moc_mesh(cells)
  if not topology.forms_closed_zone or topology.nonmanifold_edge_count:
    return _failure(
      status=MocZoneAssemblyStatus.TOPOLOGY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=cells,
      topology=topology,
      message=f'characteristic zone topology failed: {topology.message}',
    )
  ####
  coverage = _coverage_area(cells, vertex_tolerance_m=1.0e-12)
  if coverage is None:
    return _failure(
      status=MocZoneAssemblyStatus.TOPOLOGY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=cells,
      topology=topology,
      message='characteristic zone coverage area could not be validated',
    )
  ####
  coverage_area_m2, coverage_area_residual_m2 = coverage
  if abs(coverage_area_residual_m2) > max(1.0e-12, 1.0e-9 * coverage_area_m2):
    return _failure(
      status=MocZoneAssemblyStatus.TOPOLOGY_FAILURE,
      characteristic_count=characteristic_count,
      nodes=nodes,
      cells=cells,
      topology=topology,
      coverage_area_m2=coverage_area_m2,
      coverage_area_residual_m2=coverage_area_residual_m2,
      message=(
        'characteristic zone cell-area coverage residual exceeded tolerance: '
        f'{coverage_area_residual_m2}'
      ),
    )
  ####
  return MocReflectedCharacteristicZoneResult(
    status=MocZoneAssemblyStatus.CONVERGED_OPEN,
    characteristic_count=characteristic_count,
    nodes=nodes,
    cells=cells,
    topology=topology,
    coverage_area_m2=coverage_area_m2,
    coverage_area_residual_m2=coverage_area_residual_m2,
    physical_closure_status='open',
    shock_closure_status='not_assembled',
    centerline_states=centerline_states,
    boundary_states=boundary_states,
    total_pressure_Pa=total_pressure_Pa,
  )
####
