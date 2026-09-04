"""Independent audit for the solver-owned characteristic-edge remesh.

This operator intentionally repeats the local characteristic geometry,
variable-entropy compatibility, pressure transport, topology, and Euler
flux calculations instead of importing the remesh solver's private helpers.
It therefore reports whether the bounded remesh is internally coherent while
keeping conservative Euler acceptance and physical shock-cell promotion as
separate gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, exp, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import MocChainBoundaryKind
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus,
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge,
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection,
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
from exhaust_plume.validation.moc_euler import _cell_flux_residual
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REMESH_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REMESH_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-remesh-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent bounded characteristic-remesh audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = (
    'entropy_characteristic_continuation_remesh_source_failure'
  )
  EDGE_FAILURE = 'entropy_characteristic_continuation_remesh_edge_failure'
  INTERSECTION_FAILURE = (
    'entropy_characteristic_continuation_remesh_intersection_failure'
  )
  TOPOLOGY_FAILURE = (
    'entropy_characteristic_continuation_remesh_topology_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'entropy_characteristic_continuation_remesh_euler_residual_failure'
  )
  STATUS_FAILURE = 'entropy_characteristic_continuation_remesh_status_failure'
  FLAG_FAILURE = 'entropy_characteristic_continuation_remesh_flag_failure'
####


def _transport_total_pressure(
  start: CharacteristicState,
  start_total_pressure_Pa: float,
  point: tuple[float, float],
  gradient: tuple[float, float],
) -> float:
  """Independently transport total pressure along the declared gradient."""

  return float(start_total_pressure_Pa) * exp(
    gradient[0] * (point[0] - start.x_m)
    + gradient[1] * (point[1] - start.y_m)
  )
####


def _compatibility_source(
  start: CharacteristicState,
  end: CharacteristicState,
  gradient: tuple[float, float],
) -> float:
  """Recompute the short-segment entropy source term."""

  length = hypot(end.x_m - start.x_m, end.y_m - start.y_m)
  average_theta = 0.5 * (start.theta_rad + end.theta_rad)
  normal_gradient = (
    gradient[0] * -sin(average_theta)
    + gradient[1] * cos(average_theta)
  )
  average_mach = 0.5 * (start.mach + end.mach)
  average_gamma = 0.5 * (start.gamma + end.gamma)
  return (
    -sqrt(max(average_mach * average_mach - 1.0, 0.0))
    / (average_gamma * average_mach**3)
    * normal_gradient
    * length
  )
####


def _characteristic_geometry_residual(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
) -> float:
  """Recompute the normalized characteristic-line geometry residual."""

  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  length = hypot(*displacement)
  start_direction = start.direction(family)
  end_direction = end.direction(family)
  average_direction = (
    0.5 * (start_direction[0] + end_direction[0]),
    0.5 * (start_direction[1] + end_direction[1]),
  )
  average_length = hypot(*average_direction)
  if length <= 0.0 or average_length <= 0.0:
    return float('inf')
  ####
  return abs(
    displacement[0] * average_direction[1]
    - displacement[1] * average_direction[0]
  ) / (length * average_length)
####


def _family_invariant(
  state: CharacteristicState,
  family: CharacteristicFamily,
) -> float:
  return state.k_plus if family is CharacteristicFamily.PLUS else state.k_minus
####


def _compatibility_residual(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
  gradient: tuple[float, float],
) -> float:
  return abs(
    _family_invariant(end, family)
    - _family_invariant(start, family)
    - _compatibility_source(start, end, gradient)
  )
####


def _pressure_residuals(
  points: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  gradient: tuple[float, float],
) -> tuple[float, ...]:
  """Reproduce the edge pressure residual convention independently."""

  if len(points) == 3:
    midpoint = points[1]
    from_start = _transport_total_pressure(
      states[0],
      pressures[0],
      midpoint,
      gradient,
    )
    from_end = _transport_total_pressure(
      states[2],
      pressures[2],
      midpoint,
      gradient,
    )
    return (
      abs(log(pressures[1] / from_start)),
      abs(log(pressures[1] / from_end)),
    )
  ####
  return tuple(
    abs(
      log(
        pressures[index + 1]
        / _transport_total_pressure(
          states[index],
          pressures[index],
          points[index + 1],
          gradient,
        )
      )
    )
    for index in range(len(points) - 1)
  )
####


def _close(value: float, expected: float, tolerance: float) -> bool:
  return bool(abs(value - expected) <= max(1.0e-12, tolerance))
####


def _sequence_close(
  actual: Sequence[float],
  expected: Sequence[float],
  tolerance: float,
) -> bool:
  return bool(
    len(actual) == len(expected)
    and all(_close(float(a), float(e), tolerance) for a, e in zip(actual, expected, strict=True))
  )
####


def _state_close(
  actual: CharacteristicState,
  expected: CharacteristicState,
  position_tolerance_m: float,
  state_tolerance: float,
) -> bool:
  return bool(
    hypot(actual.x_m - expected.x_m, actual.y_m - expected.y_m)
    <= position_tolerance_m
    and abs(actual.theta_rad - expected.theta_rad) <= state_tolerance
    and abs(actual.mach - expected.mach) <= state_tolerance
    and abs(actual.gamma - expected.gamma) <= state_tolerance
  )
####


def _boundary_state(
  first: CharacteristicState,
  second: CharacteristicState,
  first_pressure: float,
  second_pressure: float,
  fraction: float,
) -> tuple[tuple[float, float], CharacteristicState, float]:
  """Reconstruct the independent base-row state convention."""

  point = (
    first.x_m + fraction * (second.x_m - first.x_m),
    first.y_m + fraction * (second.y_m - first.y_m),
  )
  theta = first.theta_rad + fraction * (second.theta_rad - first.theta_rad)
  nu = first.nu_rad + fraction * (second.nu_rad - first.nu_rad)
  inversion = inverse_prandtl_meyer_angle_rad(nu, first.gamma)
  if not inversion.converged or inversion.value is None:
    raise ValueError('base-row state left the supersonic Mach domain')
  ####
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
  return point, state, pressure
####


def _point_present(
  point: tuple[float, float],
  mesh_points: Sequence[tuple[float, float]],
  tolerance_m: float,
) -> bool:
  return any(
    hypot(point[0] - candidate[0], point[1] - candidate[1])
    <= tolerance_m
    for candidate in mesh_points
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit:
  """Independent evidence for one solver-owned characteristic remesh."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus
  operator_id: str
  solver_status: str | None
  source_continuation_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit | None
  subdivision_side_count: int
  cell_count: int
  sampled_cell_count: int
  state_sample_count: int
  characteristic_edge_count: int
  maximum_geometry_residual: float | None
  maximum_compatibility_residual: float | None
  maximum_pressure_residual: float | None
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  source_continuation_gates_verified: bool
  topology_verified: bool
  cell_samples_verified: bool
  edge_points_covered: bool
  edge_traces_verified: bool
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  pressure_lineage_carried: bool
  continuation_boundary_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  solver_status_consistent: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  external_validation_required: bool
  fidelity_flags_verified: bool
  topology: MocTopologyResult
  continuation_boundary_kind: MocChainBoundaryKind
  interior_characteristic_intersection_count: int = 0
  maximum_intersection_geometry_residual: float | None = None
  maximum_intersection_compatibility_residual: float | None = None
  maximum_intersection_pressure_residual: float | None = None
  interior_characteristic_rows_required: bool = False
  interior_characteristic_intersections_verified: bool = False
  position_tolerance_m: float = 1.0e-8
  characteristic_residual_tolerance: float = 1.0e-6
  pressure_lineage_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus,
    ):
      raise TypeError('status must be a continuation-remesh audit status')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    if self.solver_status is not None:
      object.__setattr__(self, 'solver_status', str(self.solver_status))
    ####
    if self.source_continuation_audit is not None and not isinstance(
      self.source_continuation_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
    ):
      raise TypeError('source_continuation_audit must be typed or None')
    ####
    for name in (
      'subdivision_side_count',
      'cell_count',
      'sampled_cell_count',
      'state_sample_count',
      'characteristic_edge_count',
      'interior_characteristic_intersection_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if len(residuals) != self.cell_count:
      raise ValueError('cell_euler_residuals must match cell_count')
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('cell_euler_residuals must be finite and nonnegative')
    ####
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    if self.maximum_cell_euler_residual is not None:
      maximum = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'maximum_cell_euler_residual', maximum)
    ####
    for name in (
      'maximum_geometry_residual',
      'maximum_compatibility_residual',
      'maximum_pressure_residual',
      'maximum_intersection_geometry_residual',
      'maximum_intersection_compatibility_residual',
      'maximum_intersection_pressure_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    if not isinstance(self.continuation_boundary_kind, MocChainBoundaryKind):
      raise TypeError('continuation_boundary_kind must be a MocChainBoundaryKind')
    ####
    for name in (
      'source_continuation_gates_verified',
      'topology_verified',
      'cell_samples_verified',
      'edge_points_covered',
      'edge_traces_verified',
      'interior_characteristic_rows_required',
      'interior_characteristic_intersections_verified',
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'pressure_lineage_carried',
      'continuation_boundary_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'solver_status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('remesh audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('remesh audit must retain the promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError('remesh audit cannot claim production validity')
    ####
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'pressure_lineage_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def structural_consistency_verified(self) -> bool:
    """Return non-Euler structural gates for this bounded local seam."""

    return bool(
      self.source_continuation_gates_verified
      and self.topology_verified
      and self.cell_samples_verified
      and self.edge_points_covered
      and self.edge_traces_verified
      and (
        not self.interior_characteristic_rows_required
        or self.interior_characteristic_intersections_verified
      )
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.pressure_lineage_carried
      and self.continuation_boundary_verified
      and self.cell_euler_residuals_finite
      and self.solver_status_consistent
      and self.fidelity_flags_verified
      and self.external_validation_required
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Return local remesh consistency without promoting Euler closure."""

    return bool(self.converged and self.structural_consistency_verified)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'structural_consistency_verified': self.structural_consistency_verified,
      'source_continuation_audit': (
        None
        if self.source_continuation_audit is None
        else self.source_continuation_audit.as_report()
      ),
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'sampled_cell_count': self.sampled_cell_count,
      'state_sample_count': self.state_sample_count,
      'characteristic_edge_count': self.characteristic_edge_count,
      'interior_characteristic_intersection_count': (
        self.interior_characteristic_intersection_count
      ),
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
      'interior_characteristic_rows_required': (
        self.interior_characteristic_rows_required
      ),
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'source_continuation_gates_verified': self.source_continuation_gates_verified,
        'topology_verified': self.topology_verified,
        'cell_samples_verified': self.cell_samples_verified,
        'edge_points_covered': self.edge_points_covered,
        'edge_traces_verified': self.edge_traces_verified,
        'interior_characteristic_intersections_verified': (
          self.interior_characteristic_intersections_verified
        ),
        'characteristic_geometry_verified': self.characteristic_geometry_verified,
        'variable_entropy_compatibility_verified': self.variable_entropy_compatibility_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'solver_status_consistent': self.solver_status_consistent,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': self.external_validation_required,
        'fidelity_flags_verified': self.fidelity_flags_verified,
      },
      'continuation_boundary_kind': self.continuation_boundary_kind.value,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus,
  message: str,
  *,
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult | None = None,
  source_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit | None = None,
  topology: MocTopologyResult | None = None,
  cell_euler_residuals: Sequence[float] | None = None,
  interior_characteristic_rows_required: bool = False,
  interior_characteristic_intersections_verified: bool = False,
  maximum_intersection_geometry_residual: float | None = None,
  maximum_intersection_compatibility_residual: float | None = None,
  maximum_intersection_pressure_residual: float | None = None,
  source_gates: bool = False,
  topology_verified: bool = False,
  cell_samples_verified: bool = False,
  edge_points_covered: bool = False,
  edge_traces_verified: bool = False,
  geometry_verified: bool = False,
  compatibility_verified: bool = False,
  pressure_lineage_carried: bool = False,
  continuation_boundary_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  status_consistent: bool = False,
  fidelity_flags_verified: bool = False,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-6,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit:
  cell_count = 0 if result is None else result.cell_count
  residuals = (
    tuple(float(value) for value in cell_euler_residuals)
    if cell_euler_residuals is not None
    else (tuple(result.cell_euler_residuals) if result is not None else ())
  )
  if len(residuals) != cell_count:
    residuals = tuple(result.cell_euler_residuals) if result is not None else ()
  ####
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REMESH_AUDIT_OPERATOR_ID
    ),
    solver_status=None if result is None else result.status.value,
    source_continuation_audit=source_audit,
    subdivision_side_count=1 if result is None else result.subdivision_side_count,
    cell_count=cell_count,
    sampled_cell_count=0 if result is None else len(result.cell_samples),
    state_sample_count=0 if result is None else result.state_sample_count,
    characteristic_edge_count=0 if result is None else len(result.characteristic_edges),
    maximum_geometry_residual=(
      None if result is None else result.maximum_geometry_residual
    ),
    maximum_compatibility_residual=(
      None if result is None else result.maximum_compatibility_residual
    ),
    maximum_pressure_residual=(
      None if result is None else result.maximum_pressure_residual
    ),
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=max(residuals, default=None),
    source_continuation_gates_verified=source_gates,
    topology_verified=topology_verified,
    cell_samples_verified=cell_samples_verified,
    edge_points_covered=edge_points_covered,
    edge_traces_verified=edge_traces_verified,
    characteristic_geometry_verified=geometry_verified,
    variable_entropy_compatibility_verified=compatibility_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    continuation_boundary_verified=continuation_boundary_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    solver_status_consistent=status_consistent,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    fidelity_flags_verified=fidelity_flags_verified,
    topology=validate_moc_mesh(()) if topology is None else topology,
    continuation_boundary_kind=(
      MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
    ),
    interior_characteristic_intersection_count=(
      0 if result is None else len(result.interior_characteristic_intersections)
    ),
    maximum_intersection_geometry_residual=(
      maximum_intersection_geometry_residual
      if result is None
      else result.maximum_intersection_geometry_residual
    ),
    maximum_intersection_compatibility_residual=(
      maximum_intersection_compatibility_residual
      if result is None
      else result.maximum_intersection_compatibility_residual
    ),
    maximum_intersection_pressure_residual=(
      maximum_intersection_pressure_residual
      if result is None
      else result.maximum_intersection_pressure_residual
    ),
    interior_characteristic_rows_required=(
      interior_characteristic_rows_required
      if result is None
      else result.interior_characteristic_rows_required
    ),
    interior_characteristic_intersections_verified=(
      interior_characteristic_intersections_verified
      if result is None
      else result.interior_characteristic_intersections_verified
    ),
    position_tolerance_m=position_tolerance_m,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def _audit_edge(
  edge: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshEdge,
  gradient: tuple[float, float],
  *,
  characteristic_tolerance: float,
  pressure_tolerance: float,
  position_tolerance_m: float,
) -> tuple[bool, bool, bool, float, float, float]:
  points = tuple(edge.points_xr_m)
  states = tuple(edge.states)
  pressures = tuple(float(value) for value in edge.total_pressure_Pa)
  if len(points) < 2 or len(points) != len(states) or len(points) != len(pressures):
    return False, False, False, float('inf'), float('inf'), float('inf')
  ####
  if any(
    hypot(state.x_m - point[0], state.y_m - point[1]) > position_tolerance_m
    for point, state in zip(points, states, strict=True)
  ):
    return False, False, False, float('inf'), float('inf'), float('inf')
  ####
  if not (
    _state_close(
      states[0],
      edge.start_state,
      position_tolerance_m,
      characteristic_tolerance,
    )
    and _state_close(
      states[-1],
      edge.end_state,
      position_tolerance_m,
      characteristic_tolerance,
    )
    and abs(pressures[0] - edge.start_total_pressure_Pa)
    <= max(1.0e-12, pressure_tolerance * edge.start_total_pressure_Pa)
    and abs(pressures[-1] - edge.end_total_pressure_Pa)
    <= max(1.0e-12, pressure_tolerance * edge.end_total_pressure_Pa)
  ):
    return False, False, False, float('inf'), float('inf'), float('inf')
  ####
  geometry = tuple(
    abs(_characteristic_geometry_residual(first, second, edge.family))
    for first, second in zip(states[:-1], states[1:], strict=True)
  )
  compatibility = tuple(
    _compatibility_residual(first, second, edge.family, gradient)
    for first, second in zip(states[:-1], states[1:], strict=True)
  )
  pressure = _pressure_residuals(points, states, pressures, gradient)
  arrays_match = bool(
    _sequence_close(edge.geometry_residuals, geometry, characteristic_tolerance)
    and _sequence_close(
      edge.compatibility_residuals,
      compatibility,
      characteristic_tolerance,
    )
    and _sequence_close(edge.pressure_residuals, pressure, pressure_tolerance)
  )
  maximum_geometry = max(geometry, default=float('inf'))
  maximum_compatibility = max(compatibility, default=float('inf'))
  maximum_pressure = max(pressure, default=float('inf'))
  maxima_match = bool(
    edge.maximum_geometry_residual <= max(1.0e-12, characteristic_tolerance)
    and _close(edge.maximum_geometry_residual, maximum_geometry, characteristic_tolerance)
    and _close(
      edge.maximum_compatibility_residual,
      maximum_compatibility,
      characteristic_tolerance,
    )
    and _close(edge.maximum_pressure_residual, maximum_pressure, pressure_tolerance)
  )
  geometry_verified = bool(
    arrays_match
    and maxima_match
    and maximum_geometry <= characteristic_tolerance
  )
  compatibility_verified = bool(
    arrays_match
    and maxima_match
    and maximum_compatibility <= characteristic_tolerance
  )
  pressure_verified = bool(
    arrays_match and maxima_match and maximum_pressure <= pressure_tolerance
  )
  return (
    geometry_verified,
    compatibility_verified,
    pressure_verified,
    maximum_geometry,
    maximum_compatibility,
    maximum_pressure,
  )
####


def _forward_margin_m(
  start: CharacteristicState,
  end: CharacteristicState,
  family: CharacteristicFamily,
  direction_sign: int,
) -> float:
  displacement = (end.x_m - start.x_m, end.y_m - start.y_m)
  direction = start.direction(family)
  return float(direction_sign) * (
    displacement[0] * direction[0] + displacement[1] * direction[1]
  )
####


def _intersection_metadata_verified(
  intersection: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection,
  source: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  *,
  subdivision_side_count: int,
  characteristic_tolerance: float,
  pressure_tolerance: float,
  position_tolerance_m: float,
) -> bool:
  if (
    intersection.parent_cell_index >= len(source.cell_samples)
    or intersection.plus_source_row_index < 1
    or intersection.minus_source_row_index >= subdivision_side_count
    or intersection.plus_source_row_index >= intersection.minus_source_row_index
  ):
    return False
  ####
  parent = source.cell_samples[intersection.parent_cell_index]
  base_indices = (
    (0, 1, 2)
    if intersection.parent_cell_index % 2 == 0
    else (1, 2, 0)
  )
  states = tuple(parent.states[index] for index in base_indices)
  pressures = tuple(
    float(parent.total_pressure_Pa[index]) for index in base_indices
  )
  plus_fraction = intersection.plus_source_row_index / subdivision_side_count
  minus_fraction = intersection.minus_source_row_index / subdivision_side_count
  _plus_point, plus_state, plus_pressure = _boundary_state(
    states[0],
    states[1],
    pressures[0],
    pressures[1],
    plus_fraction,
  )
  _minus_point, minus_state, minus_pressure = _boundary_state(
    states[0],
    states[1],
    pressures[0],
    pressures[1],
    minus_fraction,
  )
  expected_plus_sign = 1 if intersection.parent_cell_index % 2 == 0 else -1
  expected_minus_sign = -1 if intersection.parent_cell_index % 2 == 0 else 1
  return bool(
    _state_close(
      intersection.plus_source,
      plus_state,
      position_tolerance_m,
      characteristic_tolerance,
    )
    and _state_close(
      intersection.minus_source,
      minus_state,
      position_tolerance_m,
      characteristic_tolerance,
    )
    and _log_close(
      intersection.plus_source_total_pressure_Pa,
      plus_pressure,
      pressure_tolerance,
    )
    and _log_close(
      intersection.minus_source_total_pressure_Pa,
      minus_pressure,
      pressure_tolerance,
    )
    and intersection.plus_forward_direction_sign == expected_plus_sign
    and intersection.minus_forward_direction_sign == expected_minus_sign
  )
####


def _log_close(actual: float, expected: float, tolerance: float) -> bool:
  try:
    return bool(abs(log(float(actual) / float(expected))) <= tolerance)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError, ZeroDivisionError):
    return False
  ####
####


def _audit_intersection(
  intersection: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshIntersection,
  gradient: tuple[float, float],
  *,
  characteristic_tolerance: float,
  pressure_tolerance: float,
  position_tolerance_m: float,
) -> tuple[bool, float, float, float]:
  """Recompute one interior crossing without calling the solver helper."""

  plus_source = intersection.plus_source
  minus_source = intersection.minus_source
  state = intersection.state
  plus_geometry = abs(
    _characteristic_geometry_residual(
      plus_source,
      state,
      CharacteristicFamily.PLUS,
    )
  )
  minus_geometry = abs(
    _characteristic_geometry_residual(
      minus_source,
      state,
      CharacteristicFamily.MINUS,
    )
  )
  plus_compatibility = _compatibility_residual(
    plus_source,
    state,
    CharacteristicFamily.PLUS,
    gradient,
  )
  minus_compatibility = _compatibility_residual(
    minus_source,
    state,
    CharacteristicFamily.MINUS,
    gradient,
  )
  plus_transport = _transport_total_pressure(
    plus_source,
    intersection.plus_source_total_pressure_Pa,
    (state.x_m, state.y_m),
    gradient,
  )
  minus_transport = _transport_total_pressure(
    minus_source,
    intersection.minus_source_total_pressure_Pa,
    (state.x_m, state.y_m),
    gradient,
  )
  pressure = exp(0.5 * (log(plus_transport) + log(minus_transport)))
  plus_pressure = abs(log(pressure / plus_transport))
  minus_pressure = abs(log(pressure / minus_transport))
  plus_forward_margin = _forward_margin_m(
    plus_source,
    state,
    CharacteristicFamily.PLUS,
    intersection.plus_forward_direction_sign,
  )
  minus_forward_margin = _forward_margin_m(
    minus_source,
    state,
    CharacteristicFamily.MINUS,
    intersection.minus_forward_direction_sign,
  )
  maximum_geometry = max(plus_geometry, minus_geometry)
  maximum_compatibility = max(plus_compatibility, minus_compatibility)
  maximum_pressure = max(plus_pressure, minus_pressure)
  stored_values_match = bool(
    _close(
      intersection.plus_geometry_residual,
      plus_geometry,
      characteristic_tolerance,
    )
    and _close(
      intersection.minus_geometry_residual,
      minus_geometry,
      characteristic_tolerance,
    )
    and _close(
      intersection.plus_compatibility_residual,
      plus_compatibility,
      characteristic_tolerance,
    )
    and _close(
      intersection.minus_compatibility_residual,
      minus_compatibility,
      characteristic_tolerance,
    )
    and _close(
      intersection.plus_pressure_residual,
      plus_pressure,
      pressure_tolerance,
    )
    and _close(
      intersection.minus_pressure_residual,
      minus_pressure,
      pressure_tolerance,
    )
    and _log_close(
      intersection.plus_total_pressure_Pa,
      plus_transport,
      pressure_tolerance,
    )
    and _log_close(
      intersection.minus_total_pressure_Pa,
      minus_transport,
      pressure_tolerance,
    )
    and _log_close(
      intersection.total_pressure_Pa,
      pressure,
      pressure_tolerance,
    )
    and abs(plus_forward_margin - intersection.plus_forward_margin_m)
    <= position_tolerance_m
    and abs(minus_forward_margin - intersection.minus_forward_margin_m)
    <= position_tolerance_m
  )
  verified = bool(
    stored_values_match
    and maximum_geometry <= characteristic_tolerance
    and maximum_compatibility <= characteristic_tolerance
    and maximum_pressure <= pressure_tolerance
    and plus_forward_margin > position_tolerance_m
    and minus_forward_margin > position_tolerance_m
    and intersection.forward_verified
  )
  return verified, maximum_geometry, maximum_compatibility, maximum_pressure
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-6,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit:
  """Independently recompute all bounded-remesh acceptance evidence."""

  audit_status = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAuditStatus
  )
  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  ):
    return _failure(
      audit_status.INVALID_INPUT,
      'result must be a typed continuation-remesh result',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    characteristic_tolerance = float(characteristic_residual_tolerance)
    pressure_tolerance = float(pressure_lineage_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      audit_status.INVALID_INPUT,
      'continuation-remesh audit tolerances must be numeric',
      result=result,
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (
      position_tolerance,
      characteristic_tolerance,
      pressure_tolerance,
      cell_tolerance,
    )
  ):
    return _failure(
      audit_status.INVALID_INPUT,
      'continuation-remesh audit tolerances must be finite and positive',
      result=result,
    )
  ####
  source = result.source_continuation
  if not isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
    return _failure(
      audit_status.SOURCE_FAILURE,
      'remesh did not retain a typed source continuation',
      result=result,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  try:
    source_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
      source,
      position_tolerance_m=position_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      audit_status.SOURCE_FAILURE,
      f'independent source continuation audit raised: {error}',
      result=result,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  source_gates = bool(source_audit.local_consistency_verified)
  if not source_gates:
    return _failure(
      audit_status.SOURCE_FAILURE,
      'source continuation failed its independent local audit',
      result=result,
      source_audit=source_audit,
      source_gates=False,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  topology = validate_moc_mesh(result.cells)
  topology_verified = bool(
    result.cells
    and topology.status is result.topology.status
    and topology.cell_count == result.topology.cell_count
    and topology.edge_count == result.topology.edge_count
    and topology.boundary_edge_count == result.topology.boundary_edge_count
    and topology.boundary_component_count == result.topology.boundary_component_count
    and topology.nonmanifold_edge_count == result.topology.nonmanifold_edge_count
    and topology.connected == result.topology.connected
    and topology.forms_closed_zone == result.topology.forms_closed_zone
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _failure(
      audit_status.TOPOLOGY_FAILURE,
      'independent continuation-remesh topology audit failed',
      result=result,
      source_audit=source_audit,
      topology=topology,
      source_gates=True,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  cell_samples_verified = bool(
    len(result.cells) == len(result.cell_samples)
    and all(
      isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      and tuple(cell.vertices_xr_m) == tuple(sample.vertices_xr_m)
      and all(
        isinstance(state, CharacteristicState)
        and hypot(state.x_m - point[0], state.y_m - point[1])
        <= position_tolerance
        for point, state in zip(sample.vertices_xr_m, sample.states, strict=True)
      )
      for cell, sample in zip(result.cells, result.cell_samples, strict=True)
    )
  )
  gradient = source.source_pressure_gradient
  if gradient is None or len(gradient) != 2:
    return _failure(
      audit_status.SOURCE_FAILURE,
      'source continuation did not retain a pressure gradient',
      result=result,
      source_audit=source_audit,
      topology=topology,
      source_gates=True,
      topology_verified=True,
      cell_samples_verified=cell_samples_verified,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_tolerance,
      cell_residual_tolerance=cell_tolerance,
    )
  ####
  gradient = (float(gradient[0]), float(gradient[1]))
  edge_points = tuple(
    point
    for edge in result.characteristic_edges
    for point in edge.points_xr_m
  )
  mesh_points = tuple(
    point
    for sample in result.cell_samples
    for point in sample.vertices_xr_m
  )
  edge_points_covered = bool(
    edge_points
    and all(_point_present(point, mesh_points, position_tolerance) for point in edge_points)
  )
  edge_ids = tuple(edge.edge_index for edge in result.characteristic_edges)
  edge_traces_verified = bool(
    result.characteristic_edges
    and len(set(edge_ids)) == len(edge_ids)
    and all(isinstance(edge.family, CharacteristicFamily) for edge in result.characteristic_edges)
  )
  maximum_geometry = 0.0
  maximum_compatibility = 0.0
  maximum_pressure = 0.0
  geometry_verified = edge_traces_verified
  compatibility_verified = edge_traces_verified
  pressure_verified = edge_traces_verified
  try:
    for edge in result.characteristic_edges:
      (
        edge_geometry_verified,
        edge_compatibility_verified,
        edge_pressure_verified,
        edge_geometry,
        edge_compatibility,
        edge_pressure,
      ) = _audit_edge(
        edge,
        gradient,
        characteristic_tolerance=characteristic_tolerance,
        pressure_tolerance=pressure_tolerance,
        position_tolerance_m=position_tolerance,
      )
      geometry_verified = geometry_verified and edge_geometry_verified
      compatibility_verified = (
        compatibility_verified and edge_compatibility_verified
      )
      pressure_verified = pressure_verified and edge_pressure_verified
      maximum_geometry = max(maximum_geometry, edge_geometry)
      maximum_compatibility = max(maximum_compatibility, edge_compatibility)
      maximum_pressure = max(maximum_pressure, edge_pressure)
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    geometry_verified = False
    compatibility_verified = False
    pressure_verified = False
    maximum_geometry = float('inf')
    maximum_compatibility = float('inf')
    maximum_pressure = float('inf')
  ####
  intersections = tuple(result.interior_characteristic_intersections)
  maximum_intersection_geometry: float | None = None
  maximum_intersection_compatibility: float | None = None
  maximum_intersection_pressure: float | None = None
  intersections_verified = not result.interior_characteristic_rows_required
  if result.interior_characteristic_rows_required:
    intersection_ids = tuple(
      intersection.intersection_index for intersection in intersections
    )
    expected_intersection_count = (
      (result.subdivision_side_count - 1)
      * (result.subdivision_side_count - 2)
      // 2
      * len(source.cell_samples)
    )
    intersections_verified = bool(
      len(intersections) == expected_intersection_count
      and len(set(intersection_ids)) == len(intersection_ids)
    )
    maximum_intersection_geometry = 0.0
    maximum_intersection_compatibility = 0.0
    maximum_intersection_pressure = 0.0
    try:
      for intersection in intersections:
        (
          intersection_verified,
          intersection_geometry,
          intersection_compatibility,
          intersection_pressure,
        ) = _audit_intersection(
          intersection,
          gradient,
          characteristic_tolerance=characteristic_tolerance,
          pressure_tolerance=pressure_tolerance,
          position_tolerance_m=position_tolerance,
        )
        metadata_verified = _intersection_metadata_verified(
          intersection,
          source,
          subdivision_side_count=result.subdivision_side_count,
          characteristic_tolerance=characteristic_tolerance,
          pressure_tolerance=pressure_tolerance,
          position_tolerance_m=position_tolerance,
        )
        intersections_verified = bool(
          intersections_verified
          and metadata_verified
          and intersection_verified
        )
        maximum_intersection_geometry = max(
          maximum_intersection_geometry,
          intersection_geometry,
        )
        maximum_intersection_compatibility = max(
          maximum_intersection_compatibility,
          intersection_compatibility,
        )
        maximum_intersection_pressure = max(
          maximum_intersection_pressure,
          intersection_pressure,
        )
      ####
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      intersections_verified = False
      maximum_intersection_geometry = float('inf')
      maximum_intersection_compatibility = float('inf')
      maximum_intersection_pressure = float('inf')
    ####
    intersections_verified = bool(
      intersections_verified
      and result.interior_characteristic_intersections_verified
      and result.maximum_intersection_geometry_residual is not None
      and result.maximum_intersection_compatibility_residual is not None
      and result.maximum_intersection_pressure_residual is not None
      and _close(
        result.maximum_intersection_geometry_residual,
        maximum_intersection_geometry,
        characteristic_tolerance,
      )
      and _close(
        result.maximum_intersection_compatibility_residual,
        maximum_intersection_compatibility,
        characteristic_tolerance,
      )
      and _close(
        result.maximum_intersection_pressure_residual,
        maximum_intersection_pressure,
        pressure_tolerance,
      )
    )
  ####
  continuation_boundary_verified = bool(
    result.continuation_boundary_kind is MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER
    and result.continuation_boundary_verified
    and source.continuation_boundary_verified
    and result.continuation_boundary == source.continuation_boundary
  )
  pressure_lineage_carried = bool(
    pressure_verified
    and source.pressure_lineage_verified
    and source_audit.pressure_lineage_verified
    and continuation_boundary_verified
  )
  residuals: tuple[float, ...]
  try:
    residuals = tuple(
      _cell_flux_residual(
        tuple(sample.vertices_xr_m),
        tuple(sample.states),
        tuple(float(value) for value in sample.total_pressure_Pa),
      )
      for sample in result.cell_samples
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    residuals = ()
  ####
  residuals_finite = bool(
    len(residuals) == result.cell_count
    and bool(residuals)
    and all(isfinite(value) and value >= 0.0 for value in residuals)
  )
  maximum_residual = max(residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= cell_tolerance
  )
  if len(residuals) == len(result.cell_euler_residuals):
    residuals_match = all(
      _close(actual, expected, 1.0e-12)
      for actual, expected in zip(
        result.cell_euler_residuals,
        residuals,
        strict=True,
      )
    )
  else:
    residuals_match = False
  ####
  cell_samples_verified = bool(cell_samples_verified and residuals_match)
  source_gates = bool(source_gates and source_audit.local_consistency_verified)
  structural_gates = bool(
    source_gates
    and topology_verified
    and cell_samples_verified
    and edge_points_covered
    and geometry_verified
    and compatibility_verified
    and pressure_lineage_carried
    and continuation_boundary_verified
    and residuals_finite
    and intersections_verified
  )
  flags_verified = bool(
    not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.external_validation_required
  )
  expected_status = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
    .CONVERGED_LOCAL_CHARACTERISTIC_REMESH.value
    if structural_gates
    else MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
    .EDGE_SOLVE_FAILURE.value
  )
  if not topology_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshStatus
      .TOPOLOGY_FAILURE.value
    )
  ####
  solver_status_consistent = bool(result.status.value == expected_status)
  if not flags_verified:
    audit_result_status = audit_status.FLAG_FAILURE
  elif not topology_verified:
    audit_result_status = audit_status.TOPOLOGY_FAILURE
  elif not edge_traces_verified or not geometry_verified or not compatibility_verified:
    audit_result_status = audit_status.EDGE_FAILURE
  elif not intersections_verified:
    audit_result_status = audit_status.INTERSECTION_FAILURE
  elif not pressure_lineage_carried or not continuation_boundary_verified:
    audit_result_status = audit_status.EDGE_FAILURE
  elif not residuals_finite:
    audit_result_status = audit_status.EULER_RESIDUAL_FAILURE
  elif not solver_status_consistent:
    audit_result_status = audit_status.STATUS_FAILURE
  else:
    audit_result_status = audit_status.CONVERGED_LOCAL_AUDIT
  ####
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit(
    status=audit_result_status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REMESH_AUDIT_OPERATOR_ID
    ),
    solver_status=result.status.value,
    source_continuation_audit=source_audit,
    subdivision_side_count=result.subdivision_side_count,
    cell_count=result.cell_count,
    sampled_cell_count=len(result.cell_samples),
    state_sample_count=result.state_sample_count,
    characteristic_edge_count=len(result.characteristic_edges),
    maximum_geometry_residual=maximum_geometry,
    maximum_compatibility_residual=maximum_compatibility,
    maximum_pressure_residual=maximum_pressure,
    interior_characteristic_intersection_count=len(intersections),
    maximum_intersection_geometry_residual=maximum_intersection_geometry,
    maximum_intersection_compatibility_residual=(
      maximum_intersection_compatibility
    ),
    maximum_intersection_pressure_residual=maximum_intersection_pressure,
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=maximum_residual,
    source_continuation_gates_verified=source_gates,
    topology_verified=topology_verified,
    cell_samples_verified=cell_samples_verified,
    edge_points_covered=edge_points_covered,
    edge_traces_verified=edge_traces_verified,
    characteristic_geometry_verified=geometry_verified,
    variable_entropy_compatibility_verified=compatibility_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    continuation_boundary_verified=continuation_boundary_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    fidelity_flags_verified=flags_verified,
    topology=topology,
    continuation_boundary_kind=result.continuation_boundary_kind,
    interior_characteristic_rows_required=(
      result.interior_characteristic_rows_required
    ),
    interior_characteristic_intersections_verified=intersections_verified,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=characteristic_tolerance,
    pressure_lineage_tolerance=pressure_tolerance,
    cell_residual_tolerance=cell_tolerance,
    message=(
      'independent characteristic-edge remesh audit passed; conservative '
      'Euler acceptance, interior multi-row closure, reflected/free-boundary '
      'shock closure, external validation, and physical chain promotion remain '
      'separate gates'
      if audit_result_status is audit_status.CONVERGED_LOCAL_AUDIT
      else 'independent characteristic-edge remesh audit failed one or more gates'
    ),
  )
####
