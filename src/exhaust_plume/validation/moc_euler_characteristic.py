"""Independent variable-entropy characteristic evidence for the MOC lane.

The retained ambient-closed field carries a total-pressure value at each
characteristic node, but its state construction still uses the isentropic
``K+``/``K-`` compatibility equations.  For a calorically perfect gas with a
common total enthalpy, a variable total-pressure field adds an entropy source
to both characteristic compatibility equations.  This module measures that
source on the bounded first-wedge remesh without changing the solver result.

The operator is deliberately an audit, not a correction.  A passing local
compatibility check would still be below physical first-cell closure until a
solver-owned entropy-carrying field, global reflected boundary, and external
validation are present.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import cos, hypot, isfinite, log, sin, sqrt
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeRemeshResult,
)
from exhaust_plume.models.moc.euler_terminal_wedge import (
  MocEulerAmbientFirstWedgeCharacteristicResult,
  MocEulerAmbientFirstWedgeCharacteristicStatus,
  MocEulerAmbientFirstWedgeCharacteristicFieldResult,
  MocEulerAmbientFirstWedgeCharacteristicFieldStatus,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldStatus,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
)
from exhaust_plume.models.moc.topology import validate_moc_mesh
from exhaust_plume.validation.moc_euler import _cell_flux_residual

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeCharacteristicAuditStatus',
  'MocEulerAmbientFirstWedgeCharacteristicEdgeAudit',
  'MocEulerAmbientFirstWedgeCharacteristicAudit',
  'measure_moc_euler_ambient_first_wedge_characteristic_audit',
  'MOC_EULER_AMBIENT_FIRST_WEDGE_TERMINAL_CHARACTERISTIC_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus',
  'MocEulerAmbientFirstWedgeTerminalCharacteristicAudit',
  'measure_moc_euler_ambient_first_wedge_terminal_characteristic_audit',
  'MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus',
  'MocEulerAmbientFirstWedgeCharacteristicFieldAudit',
  'measure_moc_euler_ambient_first_wedge_characteristic_field_audit',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-characteristic-audit'
)


class MocEulerAmbientFirstWedgeCharacteristicAuditStatus(str, Enum):
  """Outcome of the independent variable-entropy compatibility audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_characteristic_audit'
  )
  INVALID_INPUT = 'invalid_input'
  REMESH_FAILURE = 'euler_ambient_first_wedge_characteristic_remesh_failure'
  GEOMETRY_FAILURE = 'euler_ambient_first_wedge_characteristic_geometry_failure'
  COMPATIBILITY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_compatibility_failure'
  )
  FLAG_FAILURE = 'euler_ambient_first_wedge_characteristic_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicEdgeAudit:
  """Generalized compatibility evidence for one characteristic-aligned edge."""

  cell_index: int
  edge_index: int
  family: CharacteristicFamily
  start_vertex: tuple[float, float]
  end_vertex: tuple[float, float]
  edge_length_m: float
  alignment_residual: float
  k_residual: float
  entropy_source_prediction: float
  compatibility_residual: float

  def __post_init__(self) -> None:
    for name in ('cell_index', 'edge_index'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    ####
    for name in ('start_vertex', 'end_vertex'):
      point = getattr(self, name)
      if len(point) != 2 or not all(isfinite(float(value)) for value in point):
        raise ValueError(f'{name} must contain a finite coordinate pair')
      ####
      object.__setattr__(
        self,
        name,
        (float(point[0]), float(point[1])),
      )
    ####
    for name in (
      'edge_length_m',
      'alignment_residual',
      'k_residual',
      'entropy_source_prediction',
      'compatibility_residual',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'cell_index': self.cell_index,
      'edge_index': self.edge_index,
      'family': self.family.value,
      'start_vertex': list(self.start_vertex),
      'end_vertex': list(self.end_vertex),
      'edge_length_m': self.edge_length_m,
      'alignment_residual': self.alignment_residual,
      'k_residual': self.k_residual,
      'entropy_source_prediction': self.entropy_source_prediction,
      'compatibility_residual': self.compatibility_residual,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicAudit:
  """Independent variable-entropy compatibility evidence for one remesh."""

  status: MocEulerAmbientFirstWedgeCharacteristicAuditStatus
  remesh_status: str | None
  subdivision_level: int
  cell_count: int
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit, ...]
  maximum_compatibility_residual: float | None
  maximum_k_plus_residual: float | None
  maximum_k_minus_residual: float | None
  characteristic_edges_finite: bool
  edge_alignment_verified: bool
  characteristic_compatibility_verified: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  message: str = ''
  operator_id: str = MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeCharacteristicAuditStatus'
      )
    ####
    if self.remesh_status is not None:
      object.__setattr__(self, 'remesh_status', str(self.remesh_status))
    ####
    for name in ('subdivision_level', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(edge, MocEulerAmbientFirstWedgeCharacteristicEdgeAudit)
      for edge in edges
    ):
      raise TypeError(
        'characteristic_edges must contain typed characteristic edge audits'
      )
    ####
    object.__setattr__(self, 'characteristic_edges', edges)
    for name in (
      'maximum_compatibility_residual',
      'maximum_k_plus_residual',
      'maximum_k_minus_residual',
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
    for name in (
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'characteristic_edges_finite',
      'edge_alignment_verified',
      'characteristic_compatibility_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.characteristic_edges_finite
      and self.edge_alignment_verified
      and self.characteristic_compatibility_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'remesh_status': self.remesh_status,
      'subdivision_level': self.subdivision_level,
      'cell_count': self.cell_count,
      'characteristic_edge_count': len(self.characteristic_edges),
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'maximum_k_plus_residual': self.maximum_k_plus_residual,
      'maximum_k_minus_residual': self.maximum_k_minus_residual,
      'checks': {
        'characteristic_edges_finite': self.characteristic_edges_finite,
        'edge_alignment_verified': self.edge_alignment_verified,
        'characteristic_compatibility_verified': (
          self.characteristic_compatibility_verified
        ),
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'characteristic_edges': [edge.as_report() for edge in self.characteristic_edges],
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-variable-entropy-characteristic-audit; solver-owned '
        'entropy-carrying remesh, canonical closure, and external validation '
        'remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeCharacteristicAuditStatus,
  message: str,
  *,
  remesh_status: str | None = None,
  subdivision_level: int = 0,
  cell_count: int = 0,
  characteristic_edges: Sequence[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit] = (),
  maximum_compatibility_residual: float | None = None,
  maximum_k_plus_residual: float | None = None,
  maximum_k_minus_residual: float | None = None,
  characteristic_edges_finite: bool = False,
  edge_alignment_verified: bool = False,
  characteristic_compatibility_verified: bool = False,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
) -> MocEulerAmbientFirstWedgeCharacteristicAudit:
  return MocEulerAmbientFirstWedgeCharacteristicAudit(
    status=status,
    remesh_status=remesh_status,
    subdivision_level=subdivision_level,
    cell_count=cell_count,
    characteristic_edges=tuple(characteristic_edges),
    maximum_compatibility_residual=maximum_compatibility_residual,
    maximum_k_plus_residual=maximum_k_plus_residual,
    maximum_k_minus_residual=maximum_k_minus_residual,
    characteristic_edges_finite=characteristic_edges_finite,
    edge_alignment_verified=edge_alignment_verified,
    characteristic_compatibility_verified=characteristic_compatibility_verified,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    message=message,
  )
####


def _log_pressure_gradient(
  vertices: tuple[tuple[float, float], ...],
  pressures: tuple[float, ...],
) -> tuple[float, float] | None:
  if len(vertices) != 3 or len(pressures) != 3:
    return None
  ####
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return None
  ####
  (x1, y1), (x2, y2), (x3, y3) = vertices
  twice_area = (
    x1 * (y2 - y3)
    + x2 * (y3 - y1)
    + x3 * (y1 - y2)
  )
  if not isfinite(twice_area) or abs(twice_area) <= 1.0e-24:
    return None
  ####
  log_pressures = tuple(log(value) for value in pressures)
  return (
    (
      log_pressures[0] * (y2 - y3)
      + log_pressures[1] * (y3 - y1)
      + log_pressures[2] * (y1 - y2)
    ) / twice_area,
    (
      log_pressures[0] * (x3 - x2)
      + log_pressures[1] * (x1 - x3)
      + log_pressures[2] * (x2 - x1)
    ) / twice_area,
  )
####


def _candidate_edge(
  start: tuple[float, float],
  end: tuple[float, float],
  start_state: Any,
  end_state: Any,
  family: CharacteristicFamily,
) -> tuple[float, float, float] | None:
  direction = start_state.direction(family)
  other_direction = end_state.direction(family)
  averaged = (
    0.5 * (direction[0] + other_direction[0]),
    0.5 * (direction[1] + other_direction[1]),
  )
  direction_length = hypot(*averaged)
  edge = (end[0] - start[0], end[1] - start[1])
  edge_length = hypot(*edge)
  if direction_length <= 0.0 or edge_length <= 0.0:
    return None
  ####
  unit_direction = (
    averaged[0] / direction_length,
    averaged[1] / direction_length,
  )
  forward = edge[0] * unit_direction[0] + edge[1] * unit_direction[1]
  if forward <= 0.0:
    return None
  ####
  alignment = abs(
    edge[0] * unit_direction[1] - edge[1] * unit_direction[0]
  ) / edge_length
  return alignment, edge_length, forward
####


def measure_moc_euler_ambient_first_wedge_characteristic_audit(
  remesh: MocEulerAmbientFirstWedgeRemeshResult,
  *,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
) -> MocEulerAmbientFirstWedgeCharacteristicAudit:
  """Measure entropy-corrected ``K+``/``K-`` compatibility on remesh edges.

  For fixed total enthalpy and a calorically perfect gas, the source term used
  here is

  ``dK±/dl = -sqrt(M²-1)/(gamma*M³) * d(log(p0))/dn``.

  ``p0`` is the carried total pressure and ``n`` is the local normal to the
  averaged flow direction.  This is a local consistency diagnostic; it does
  not modify states or infer a global streamline map.
  """

  if not isinstance(remesh, MocEulerAmbientFirstWedgeRemeshResult):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.INVALID_INPUT,
      'remesh must be a MocEulerAmbientFirstWedgeRemeshResult',
    )
  ####
  try:
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.INVALID_INPUT,
      'characteristic and edge-alignment tolerances must be numeric',
      remesh_status=remesh.status.value,
      subdivision_level=remesh.subdivision_level,
      cell_count=remesh.cell_count,
    )
  ####
  if not isfinite(residual_tolerance) or residual_tolerance <= 0.0:
    raise ValueError('characteristic_residual_tolerance must be finite and positive')
  ####
  if not isfinite(alignment_tolerance) or alignment_tolerance <= 0.0:
    raise ValueError('edge_alignment_tolerance must be finite and positive')
  ####
  common = {
    'remesh_status': remesh.status.value,
    'subdivision_level': remesh.subdivision_level,
    'cell_count': remesh.cell_count,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
  }
  if not remesh.converged:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.REMESH_FAILURE,
      'characteristic audit requires a converged bounded first-wedge remesh',
      **common,
    )
  ####
  if len(remesh.cells) != len(remesh.cell_samples):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE,
      'remesh cells and samples are not aligned',
      **common,
    )
  ####

  edges: list[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit] = []
  edge_alignment_verified = True
  for cell_index, sample in enumerate(remesh.cell_samples):
    gradient = _log_pressure_gradient(
      sample.vertices_xr_m,
      sample.total_pressure_Pa,
    )
    if gradient is None:
      return _failure(
        MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE,
        f'cell {cell_index} has no finite non-degenerate pressure gradient',
        characteristic_edges=edges,
        edge_alignment_verified=False,
        **common,
      )
    ####
    cell_edges: list[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit] = []
    vertices = sample.vertices_xr_m
    states = sample.states
    for edge_index, (first, second) in enumerate(
      zip(range(3), (1, 2, 0), strict=True)
    ):
      candidates: list[tuple[float, float, CharacteristicFamily, int, int]] = []
      for family in (CharacteristicFamily.PLUS, CharacteristicFamily.MINUS):
        for start_index, end_index in ((first, second), (second, first)):
          candidate = _candidate_edge(
            vertices[start_index],
            vertices[end_index],
            states[start_index],
            states[end_index],
            family,
          )
          if candidate is not None:
            alignment, length, forward = candidate
            candidates.append(
              (alignment, length, family, start_index, end_index)
            )
          ####
        ####
      ####
      if not candidates:
        continue
      ####
      alignment, length, family, start_index, end_index = min(
        candidates,
        key=lambda value: value[0],
      )
      if alignment > alignment_tolerance:
        continue
      ####
      start_state = states[start_index]
      end_state = states[end_index]
      average_theta = 0.5 * (
        start_state.theta_rad + end_state.theta_rad
      )
      average_mach = 0.5 * (start_state.mach + end_state.mach)
      gamma = 0.5 * (start_state.gamma + end_state.gamma)
      normal = (-sin(average_theta), cos(average_theta))
      normal_gradient = gradient[0] * normal[0] + gradient[1] * normal[1]
      coefficient = -sqrt(max(average_mach * average_mach - 1.0, 0.0)) / (
        gamma * average_mach ** 3
      )
      source_prediction = abs(coefficient * normal_gradient * length)
      if family is CharacteristicFamily.PLUS:
        k_residual = abs(end_state.k_plus - start_state.k_plus)
        signed_source = coefficient * normal_gradient * length
      else:
        k_residual = abs(end_state.k_minus - start_state.k_minus)
        signed_source = coefficient * normal_gradient * length
      ####
      actual_compatibility = (
        end_state.k_plus - start_state.k_plus
        if family is CharacteristicFamily.PLUS
        else end_state.k_minus - start_state.k_minus
      )
      compatibility_residual = abs(actual_compatibility - signed_source)
      edge_audit = MocEulerAmbientFirstWedgeCharacteristicEdgeAudit(
        cell_index=cell_index,
        edge_index=edge_index,
        family=family,
        start_vertex=vertices[start_index],
        end_vertex=vertices[end_index],
        edge_length_m=length,
        alignment_residual=alignment,
        k_residual=k_residual,
        entropy_source_prediction=source_prediction,
        compatibility_residual=compatibility_residual,
      )
      edges.append(edge_audit)
      cell_edges.append(edge_audit)
    ####
    if len(cell_edges) < 2:
      edge_alignment_verified = False
    ####
  ####

  if not edges:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE,
      'no characteristic-aligned edges were available for the entropy audit',
      characteristic_edges=edges,
      edge_alignment_verified=False,
      **common,
    )
  ####
  finite = all(
    isfinite(edge.compatibility_residual)
    and isfinite(edge.k_residual)
    and isfinite(edge.entropy_source_prediction)
    for edge in edges
  )
  maximum = max(edge.compatibility_residual for edge in edges)
  plus_values = tuple(
    edge.compatibility_residual
    for edge in edges
    if edge.family is CharacteristicFamily.PLUS
  )
  minus_values = tuple(
    edge.compatibility_residual
    for edge in edges
    if edge.family is CharacteristicFamily.MINUS
  )
  maximum_plus = max(plus_values, default=None)
  maximum_minus = max(minus_values, default=None)
  compatibility_verified = bool(
    finite
    and edge_alignment_verified
    and maximum <= residual_tolerance
  )
  if not finite:
    status = MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE
    message = 'first-wedge characteristic audit returned non-finite residuals'
  elif not edge_alignment_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE
    message = (
      'first-wedge remesh did not retain two characteristic-aligned edges '
      'per triangular cell'
    )
  elif not compatibility_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicAuditStatus.COMPATIBILITY_FAILURE
    message = (
      'isentropic K+/K- transport does not satisfy the variable-entropy '
      'characteristic source term; an entropy-carrying remesh is required'
    )
  elif (
    remesh.physical_closure_verified
    or not remesh.chain_promotion_blocked
    or remesh.production_claim_allowed
  ):
    status = MocEulerAmbientFirstWedgeCharacteristicAuditStatus.FLAG_FAILURE
    message = 'first-wedge characteristic audit received weakened fidelity flags'
  else:
    status = MocEulerAmbientFirstWedgeCharacteristicAuditStatus.CONVERGED_LOCAL_AUDIT
    message = (
      'independent variable-entropy characteristic compatibility passed; '
      'physical closure and chain promotion remain blocked'
    )
  ####
  return MocEulerAmbientFirstWedgeCharacteristicAudit(
    status=status,
    remesh_status=remesh.status.value,
    subdivision_level=remesh.subdivision_level,
    cell_count=remesh.cell_count,
    characteristic_edges=tuple(edges),
    maximum_compatibility_residual=maximum,
    maximum_k_plus_residual=maximum_plus,
    maximum_k_minus_residual=maximum_minus,
    characteristic_edges_finite=finite,
    edge_alignment_verified=edge_alignment_verified,
    characteristic_compatibility_verified=compatibility_verified,
    physical_closure_verified=remesh.physical_closure_verified,
    chain_promotion_blocked=remesh.chain_promotion_blocked,
    production_claim_allowed=remesh.production_claim_allowed,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    message=message,
  )
####


MOC_EULER_AMBIENT_FIRST_WEDGE_TERMINAL_CHARACTERISTIC_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-terminal-characteristic-audit'
)


class MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus(str, Enum):
  """Outcome of auditing the solver-owned terminal-wedge candidate."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_terminal_characteristic_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SOLVER_FAILURE = 'euler_ambient_first_wedge_terminal_solver_failure'
  TOPOLOGY_FAILURE = 'euler_ambient_first_wedge_terminal_topology_failure'
  STATE_FAILURE = 'euler_ambient_first_wedge_terminal_state_failure'
  GEOMETRY_FAILURE = 'euler_ambient_first_wedge_terminal_geometry_failure'
  ENTROPY_FAILURE = 'euler_ambient_first_wedge_terminal_entropy_failure'
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_terminal_euler_residual_failure'
  )
  FLAG_FAILURE = 'euler_ambient_first_wedge_terminal_flag_failure'
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeTerminalCharacteristicAudit:
  """Independent gates for one solver-owned terminal-wedge candidate."""

  status: MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus
  solver_status: str | None
  source_cell_index: int | None
  cell_count: int
  vertex_count: int
  characteristic_edges: tuple[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit, ...]
  maximum_edge_alignment_residual: float | None
  minimum_forward_margin_m: float | None
  maximum_k_residual: float | None
  maximum_entropy_compatibility_residual: float | None
  cell_euler_residual: float | None
  topology_verified: bool
  state_samples_finite: bool
  pressure_lineage_verified: bool
  characteristic_geometry_verified: bool
  variable_entropy_compatibility_verified: bool
  cell_euler_residual_finite: bool
  cell_euler_residual_verified: bool
  solver_status_consistent: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''
  operator_id: str = (
    MOC_EULER_AMBIENT_FIRST_WEDGE_TERMINAL_CHARACTERISTIC_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus'
      )
    ####
    if self.solver_status is not None:
      object.__setattr__(self, 'solver_status', str(self.solver_status))
    ####
    if self.source_cell_index is not None and (
      isinstance(self.source_cell_index, bool)
      or not isinstance(self.source_cell_index, int)
      or self.source_cell_index < 0
    ):
      raise ValueError('source_cell_index must be a nonnegative integer or None')
    ####
    for name in ('cell_count', 'vertex_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(edge, MocEulerAmbientFirstWedgeCharacteristicEdgeAudit)
      for edge in edges
    ):
      raise TypeError(
        'characteristic_edges must contain typed characteristic edge audits'
      )
    ####
    object.__setattr__(self, 'characteristic_edges', edges)
    for name in (
      'maximum_edge_alignment_residual',
      'minimum_forward_margin_m',
      'maximum_k_residual',
      'maximum_entropy_compatibility_residual',
      'cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'topology_verified',
      'state_samples_finite',
      'pressure_lineage_verified',
      'characteristic_geometry_verified',
      'variable_entropy_compatibility_verified',
      'cell_euler_residual_finite',
      'cell_euler_residual_verified',
      'solver_status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.topology_verified
      and self.state_samples_finite
      and self.pressure_lineage_verified
      and self.characteristic_geometry_verified
      and self.variable_entropy_compatibility_verified
      and self.cell_euler_residual_finite
      and self.cell_euler_residual_verified
      and self.solver_status_consistent
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_cell_index': self.source_cell_index,
      'cell_count': self.cell_count,
      'vertex_count': self.vertex_count,
      'characteristic_edge_count': len(self.characteristic_edges),
      'maximum_edge_alignment_residual': (
        self.maximum_edge_alignment_residual
      ),
      'minimum_forward_margin_m': self.minimum_forward_margin_m,
      'maximum_k_residual': self.maximum_k_residual,
      'maximum_entropy_compatibility_residual': (
        self.maximum_entropy_compatibility_residual
      ),
      'cell_euler_residual': self.cell_euler_residual,
      'checks': {
        'topology_verified': self.topology_verified,
        'state_samples_finite': self.state_samples_finite,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'characteristic_geometry_verified': (
          self.characteristic_geometry_verified
        ),
        'variable_entropy_compatibility_verified': (
          self.variable_entropy_compatibility_verified
        ),
        'cell_euler_residual_finite': self.cell_euler_residual_finite,
        'cell_euler_residual_verified': self.cell_euler_residual_verified,
        'solver_status_consistent': self.solver_status_consistent,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'characteristic_residual_tolerance': (
        self.characteristic_residual_tolerance
      ),
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'characteristic_edges': [edge.as_report() for edge in self.characteristic_edges],
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-solver-owned-terminal-wedge-audit; complete entropy '
        'transport, canonical reflected closure, and external validation '
        'remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _terminal_characteristic_audit_failure(
  status: MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus,
  message: str,
  *,
  solver_status: str | None = None,
  source_cell_index: int | None = None,
  cell_count: int = 0,
  vertex_count: int = 0,
  characteristic_edges: Sequence[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit] = (),
  maximum_edge_alignment_residual: float | None = None,
  minimum_forward_margin_m: float | None = None,
  maximum_k_residual: float | None = None,
  maximum_entropy_compatibility_residual: float | None = None,
  cell_euler_residual: float | None = None,
  topology_verified: bool = False,
  state_samples_finite: bool = False,
  pressure_lineage_verified: bool = False,
  characteristic_geometry_verified: bool = False,
  variable_entropy_compatibility_verified: bool = False,
  cell_euler_residual_finite: bool = False,
  cell_euler_residual_verified: bool = False,
  solver_status_consistent: bool = False,
  physical_closure_verified: bool = False,
  chain_promotion_blocked: bool = True,
  production_claim_allowed: bool = False,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeTerminalCharacteristicAudit:
  return MocEulerAmbientFirstWedgeTerminalCharacteristicAudit(
    status=status,
    solver_status=solver_status,
    source_cell_index=source_cell_index,
    cell_count=cell_count,
    vertex_count=vertex_count,
    characteristic_edges=tuple(characteristic_edges),
    maximum_edge_alignment_residual=maximum_edge_alignment_residual,
    minimum_forward_margin_m=minimum_forward_margin_m,
    maximum_k_residual=maximum_k_residual,
    maximum_entropy_compatibility_residual=(
      maximum_entropy_compatibility_residual
    ),
    cell_euler_residual=cell_euler_residual,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=(
      variable_entropy_compatibility_verified
    ),
    cell_euler_residual_finite=cell_euler_residual_finite,
    cell_euler_residual_verified=cell_euler_residual_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=physical_closure_verified,
    chain_promotion_blocked=chain_promotion_blocked,
    production_claim_allowed=production_claim_allowed,
    characteristic_residual_tolerance=characteristic_residual_tolerance,
    edge_alignment_tolerance=edge_alignment_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def _points_match(
  left: Sequence[tuple[float, float]],
  right: Sequence[tuple[float, float]],
  tolerance: float,
) -> bool:
  return bool(
    len(left) == len(right)
    and all(
      hypot(first[0] - second[0], first[1] - second[1]) <= tolerance
      for first, second in zip(left, right, strict=True)
    )
  )
####


def measure_moc_euler_ambient_first_wedge_terminal_characteristic_audit(
  candidate: MocEulerAmbientFirstWedgeCharacteristicResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  characteristic_residual_tolerance: float = 1.0e-8,
  edge_alignment_tolerance: float = 0.25,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeTerminalCharacteristicAudit:
  """Recompute terminal-wedge gates from solver-returned raw evidence.

  The audit deliberately does not use the candidate's cached residuals or
  topology.  It reconstructs the two expected characteristic edges, the
  variable-entropy source comparison, the pressure-lineage check, and the
  normalized Euler cell residual from the returned vertices, states, and
  pressures.  A local pass remains below canonical reflected-field closure.
  """

  if not isinstance(
    candidate,
    MocEulerAmbientFirstWedgeCharacteristicResult,
  ):
    return _terminal_characteristic_audit_failure(
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.INVALID_INPUT,
      'candidate must be a MocEulerAmbientFirstWedgeCharacteristicResult',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(characteristic_residual_tolerance)
    alignment_tolerance = float(edge_alignment_tolerance)
    cell_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _terminal_characteristic_audit_failure(
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.INVALID_INPUT,
      'terminal characteristic audit tolerances must be numeric',
      solver_status=candidate.status.value,
      source_cell_index=candidate.source_cell_index,
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('characteristic_residual_tolerance', residual_tolerance),
    ('edge_alignment_tolerance', alignment_tolerance),
    ('cell_residual_tolerance', cell_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  common = {
    'solver_status': candidate.status.value,
    'source_cell_index': candidate.source_cell_index,
    'characteristic_residual_tolerance': residual_tolerance,
    'edge_alignment_tolerance': alignment_tolerance,
    'cell_residual_tolerance': cell_tolerance,
    'physical_closure_verified': candidate.physical_closure_verified,
    'chain_promotion_blocked': candidate.chain_promotion_blocked,
    'production_claim_allowed': candidate.production_claim_allowed,
  }
  cell = candidate.cell
  sample = candidate.cell_sample
  if cell is None or sample is None:
    return _terminal_characteristic_audit_failure(
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.SOLVER_FAILURE,
      'terminal characteristic candidate did not return a cell and sample',
      **common,
    )
  ####
  vertices = tuple(
    (float(point[0]), float(point[1]))
    for point in candidate.vertices_xr_m
  )
  states = tuple(candidate.states)
  pressures = tuple(float(value) for value in candidate.total_pressure_Pa)
  cell_vertices = tuple(
    (float(point[0]), float(point[1])) for point in cell.vertices_xr_m
  )
  sample_vertices = tuple(
    (float(point[0]), float(point[1])) for point in sample.vertices_xr_m
  )
  cell_count = 1
  vertex_count = len(vertices)
  topology = validate_moc_mesh((cell,))
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  state_samples_finite = bool(
    len(vertices) == len(states) == len(pressures) == 3
    and all(
      isinstance(state, CharacteristicState)
      and all(
        isfinite(value)
        for value in (
          state.x_m,
          state.y_m,
          state.theta_rad,
          state.mach,
          state.gamma,
        )
      )
      and state.mach > 1.0
      and state.gamma > 1.0
      for state in states
    )
    and all(
      isfinite(value) and value > 0.0
      for value in pressures
    )
    and all(
      hypot(state.x_m - point[0], state.y_m - point[1])
      <= position_tolerance
      for point, state in zip(vertices, states, strict=True)
    )
    and _points_match(vertices, cell_vertices, position_tolerance)
    and _points_match(vertices, sample_vertices, position_tolerance)
    and all(
      hypot(state.x_m - point[0], state.y_m - point[1])
      <= position_tolerance
      for point, state in zip(sample_vertices, sample.states, strict=True)
    )
    and all(
      abs(first - second)
      <= position_tolerance * max(1.0, abs(first), abs(second))
      for first, second in zip(pressures, sample.total_pressure_Pa, strict=True)
    )
  )
  pressure_lineage_verified = bool(
    len(pressures) == 3
    and abs(pressures[2] - pressures[1])
    <= position_tolerance * max(1.0, abs(pressures[1]), abs(pressures[2]))
  )
  if not topology_verified:
    return _terminal_characteristic_audit_failure(
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.TOPOLOGY_FAILURE,
      f'independent terminal-wedge topology audit failed: {topology.message}',
      cell_count=cell_count,
      vertex_count=vertex_count,
      topology_verified=False,
      state_samples_finite=state_samples_finite,
      pressure_lineage_verified=pressure_lineage_verified,
      **common,
    )
  ####
  if not state_samples_finite:
    return _terminal_characteristic_audit_failure(
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.STATE_FAILURE,
      'terminal-wedge raw cell, state, or pressure samples are inconsistent',
      cell_count=cell_count,
      vertex_count=vertex_count,
      topology_verified=True,
      state_samples_finite=False,
      pressure_lineage_verified=pressure_lineage_verified,
      **common,
    )
  ####
  gradient = _log_pressure_gradient(vertices, pressures)
  edges: list[MocEulerAmbientFirstWedgeCharacteristicEdgeAudit] = []
  edge_specs = (
    (0, 1, CharacteristicFamily.PLUS),
    (1, 2, CharacteristicFamily.MINUS),
  )
  geometry_evidence = True
  forward_margins: list[float] = []
  for edge_index, (start_index, end_index, family) in enumerate(edge_specs):
    candidate_edge = _candidate_edge(
      vertices[start_index],
      vertices[end_index],
      states[start_index],
      states[end_index],
      family,
    )
    if candidate_edge is None or gradient is None:
      geometry_evidence = False
      continue
    ####
    alignment, edge_length, forward_margin = candidate_edge
    start_state = states[start_index]
    end_state = states[end_index]
    average_theta = 0.5 * (start_state.theta_rad + end_state.theta_rad)
    normal = (-sin(average_theta), cos(average_theta))
    normal_gradient = gradient[0] * normal[0] + gradient[1] * normal[1]
    average_mach = 0.5 * (start_state.mach + end_state.mach)
    gamma = 0.5 * (start_state.gamma + end_state.gamma)
    coefficient = -sqrt(max(average_mach * average_mach - 1.0, 0.0)) / (
      gamma * average_mach ** 3
    )
    signed_source = coefficient * normal_gradient * edge_length
    actual = (
      end_state.k_plus - start_state.k_plus
      if family is CharacteristicFamily.PLUS
      else end_state.k_minus - start_state.k_minus
    )
    edges.append(
      MocEulerAmbientFirstWedgeCharacteristicEdgeAudit(
        cell_index=0,
        edge_index=edge_index,
        family=family,
        start_vertex=vertices[start_index],
        end_vertex=vertices[end_index],
        edge_length_m=edge_length,
        alignment_residual=alignment,
        k_residual=abs(actual),
        entropy_source_prediction=abs(signed_source),
        compatibility_residual=abs(actual - signed_source),
      )
    )
    forward_margins.append(forward_margin)
    if alignment > alignment_tolerance or forward_margin <= position_tolerance:
      geometry_evidence = False
    ####
  ####
  maximum_alignment = max(
    (edge.alignment_residual for edge in edges),
    default=None,
  )
  minimum_forward = min(
    forward_margins,
    default=None,
  )
  maximum_k = max((edge.k_residual for edge in edges), default=None)
  maximum_entropy = max(
    (edge.compatibility_residual for edge in edges),
    default=None,
  )
  characteristic_geometry_verified = bool(
    geometry_evidence
    and len(edges) == 2
    and maximum_alignment is not None
    and maximum_alignment <= alignment_tolerance
    and minimum_forward is not None
    and minimum_forward > position_tolerance
    and abs(vertices[0][1]) <= position_tolerance
    and abs(vertices[2][1]) <= position_tolerance
    and abs(states[0].theta_rad) <= residual_tolerance
    and abs(states[2].theta_rad) <= residual_tolerance
  )
  variable_entropy_verified = bool(
    characteristic_geometry_verified
    and maximum_entropy is not None
    and maximum_entropy <= residual_tolerance
  )
  try:
    cell_euler_residual = _cell_flux_residual(
      vertices,
      states,
      pressures,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    cell_euler_residual = None
  ####
  cell_euler_residual_finite = bool(
    cell_euler_residual is not None and isfinite(cell_euler_residual)
  )
  cell_euler_residual_verified = bool(
    cell_euler_residual_finite
    and cell_euler_residual <= cell_tolerance
  )
  if not characteristic_geometry_verified:
    expected_solver_status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .CHARACTERISTIC_GEOMETRY_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.GEOMETRY_FAILURE
    message = 'independent terminal-wedge characteristic geometry audit failed'
  elif not variable_entropy_verified:
    expected_solver_status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus.ENTROPY_FAILURE.value
    )
    status = MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.ENTROPY_FAILURE
    message = (
      'independent terminal-wedge audit reproduced the missing entropy '
      'source compatibility'
    )
  elif not cell_euler_residual_verified:
    expected_solver_status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .EULER_RESIDUAL_FAILURE.value
    )
    status = (
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus
      .EULER_RESIDUAL_FAILURE
    )
    message = 'independent terminal-wedge Euler residual audit failed'
  elif (
    candidate.physical_closure_verified
    or not candidate.chain_promotion_blocked
    or candidate.production_claim_allowed
  ):
    expected_solver_status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .CONVERGED_CHARACTERISTIC_WEDGE.value
    )
    status = MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus.FLAG_FAILURE
    message = 'terminal-wedge candidate returned weakened fidelity flags'
  else:
    expected_solver_status = (
      MocEulerAmbientFirstWedgeCharacteristicStatus
      .CONVERGED_CHARACTERISTIC_WEDGE.value
    )
    status = (
      MocEulerAmbientFirstWedgeTerminalCharacteristicAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
    message = (
      'independent terminal-wedge audit passed local geometry, entropy, and '
      'Euler residual gates; physical closure remains blocked'
    )
  ####
  solver_status_consistent = candidate.status.value == expected_solver_status
  if not solver_status_consistent:
    message += (
      f'; solver status {candidate.status.value!r} does not match the '
      f'independent expected status {expected_solver_status!r}'
    )
  ####
  return MocEulerAmbientFirstWedgeTerminalCharacteristicAudit(
    status=status,
    solver_status=candidate.status.value,
    source_cell_index=candidate.source_cell_index,
    cell_count=cell_count,
    vertex_count=vertex_count,
    characteristic_edges=tuple(edges),
    maximum_edge_alignment_residual=maximum_alignment,
    minimum_forward_margin_m=minimum_forward,
    maximum_k_residual=maximum_k,
    maximum_entropy_compatibility_residual=maximum_entropy,
    cell_euler_residual=cell_euler_residual,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    pressure_lineage_verified=pressure_lineage_verified,
    characteristic_geometry_verified=characteristic_geometry_verified,
    variable_entropy_compatibility_verified=variable_entropy_verified,
    cell_euler_residual_finite=cell_euler_residual_finite,
    cell_euler_residual_verified=cell_euler_residual_verified,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=candidate.physical_closure_verified,
    chain_promotion_blocked=candidate.chain_promotion_blocked,
    production_claim_allowed=candidate.production_claim_allowed,
    characteristic_residual_tolerance=residual_tolerance,
    edge_alignment_tolerance=alignment_tolerance,
    cell_residual_tolerance=cell_tolerance,
    message=message,
  )
####


MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-characteristic-field-audit'
)


class MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus(str, Enum):
  """Outcome of the independent local characteristic-field retile audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_characteristic_field_audit'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = 'euler_ambient_first_wedge_characteristic_field_failure'
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_topology_failure'
  )
  PATH_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_boundary_path_failure'
  )
  STATE_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_state_failure'
  )
  CHARACTERISTIC_GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_geometry_failure'
  )
  ENTROPY_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_entropy_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_euler_residual_failure'
  )
  FIELD_EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_full_euler_residual_failure'
  )
  FLAG_FAILURE = (
    'euler_ambient_first_wedge_characteristic_field_flag_failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeCharacteristicFieldAudit:
  """Independent raw-mesh evidence for the two-cell characteristic retile."""

  status: MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus
  solver_status: str | None
  retiled_field_status: str | None
  replaced_cell_indices: tuple[int, ...]
  cell_count: int
  sampled_cell_count: int
  cell_euler_residuals: tuple[float, ...]
  replaced_cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  maximum_replaced_cell_euler_residual: float | None
  topology_verified: bool
  boundary_paths_verified: bool
  state_samples_finite: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  retiled_field_status_barrier_verified: bool
  solver_status_consistent: bool
  terminal_characteristic_audit_status: str | None
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  residual_tolerance: float = 1.0e-2
  position_tolerance_m: float = 1.0e-10
  message: str = ''
  operator_id: str = (
    MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_FIELD_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus'
      )
    ####
    for name in ('solver_status', 'retiled_field_status', 'terminal_characteristic_audit_status'):
      value = getattr(self, name)
      if value is not None:
        object.__setattr__(self, name, str(value))
      ####
    ####
    replaced_indices = tuple(self.replaced_cell_indices)
    if any(
      isinstance(index, bool) or not isinstance(index, int) or index < 0
      for index in replaced_indices
    ):
      raise ValueError('replaced_cell_indices must contain nonnegative integers')
    ####
    object.__setattr__(self, 'replaced_cell_indices', replaced_indices)
    for name in ('cell_count', 'sampled_cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    residual_tolerance = float(self.residual_tolerance)
    position_tolerance = float(self.position_tolerance_m)
    if not isfinite(residual_tolerance) or residual_tolerance <= 0.0:
      raise ValueError('residual_tolerance must be finite and positive')
    ####
    if not isfinite(position_tolerance) or position_tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    object.__setattr__(self, 'residual_tolerance', residual_tolerance)
    object.__setattr__(self, 'position_tolerance_m', position_tolerance)
    for name in ('cell_euler_residuals', 'replaced_cell_euler_residuals'):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'maximum_cell_euler_residual',
      'maximum_replaced_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative when supplied')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'topology_verified',
      'boundary_paths_verified',
      'state_samples_finite',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'retiled_field_status_barrier_verified',
      'solver_status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError(
        'a local characteristic field audit cannot claim physical closure'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'a local characteristic field audit cannot claim production validity'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.topology_verified
      and self.boundary_paths_verified
      and self.state_samples_finite
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and self.retiled_field_status_barrier_verified
      and self.solver_status_consistent
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'retiled_field_status': self.retiled_field_status,
      'terminal_characteristic_audit_status': (
        self.terminal_characteristic_audit_status
      ),
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'replaced_cell_indices': list(self.replaced_cell_indices),
      'cell_count': self.cell_count,
      'sampled_cell_count': self.sampled_cell_count,
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'replaced_cell_euler_residuals': list(self.replaced_cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'maximum_replaced_cell_euler_residual': (
        self.maximum_replaced_cell_euler_residual
      ),
      'checks': {
        'topology_verified': self.topology_verified,
        'boundary_paths_verified': self.boundary_paths_verified,
        'state_samples_finite': self.state_samples_finite,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'retiled_field_status_barrier_verified': (
          self.retiled_field_status_barrier_verified
        ),
        'solver_status_consistent': self.solver_status_consistent,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'residual_tolerance': self.residual_tolerance,
      'position_tolerance_m': self.position_tolerance_m,
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-local-characteristic-field-retile audit; complete '
        'entropy transport, reflected free-boundary continuation, and '
        'external validation remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _characteristic_field_audit_failure(
  status: MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus,
  message: str,
  *,
  solver_status: str | None = None,
  retiled_field_status: str | None = None,
  replaced_cell_indices: Sequence[int] = (),
  cell_count: int = 0,
  sampled_cell_count: int = 0,
  cell_euler_residuals: Sequence[float] = (),
  replaced_cell_euler_residuals: Sequence[float] = (),
  maximum_cell_euler_residual: float | None = None,
  maximum_replaced_cell_euler_residual: float | None = None,
  topology_verified: bool = False,
  boundary_paths_verified: bool = False,
  state_samples_finite: bool = False,
  cell_euler_residuals_finite: bool = False,
  cell_euler_residuals_verified: bool = False,
  retiled_field_status_barrier_verified: bool = False,
  solver_status_consistent: bool = False,
  terminal_characteristic_audit_status: str | None = None,
  residual_tolerance: float = 1.0e-2,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerAmbientFirstWedgeCharacteristicFieldAudit:
  return MocEulerAmbientFirstWedgeCharacteristicFieldAudit(
    status=status,
    solver_status=solver_status,
    retiled_field_status=retiled_field_status,
    replaced_cell_indices=tuple(replaced_cell_indices),
    cell_count=cell_count,
    sampled_cell_count=sampled_cell_count,
    cell_euler_residuals=tuple(cell_euler_residuals),
    replaced_cell_euler_residuals=tuple(replaced_cell_euler_residuals),
    maximum_cell_euler_residual=maximum_cell_euler_residual,
    maximum_replaced_cell_euler_residual=maximum_replaced_cell_euler_residual,
    topology_verified=topology_verified,
    boundary_paths_verified=boundary_paths_verified,
    state_samples_finite=state_samples_finite,
    cell_euler_residuals_finite=cell_euler_residuals_finite,
    cell_euler_residuals_verified=cell_euler_residuals_verified,
    retiled_field_status_barrier_verified=retiled_field_status_barrier_verified,
    solver_status_consistent=solver_status_consistent,
    terminal_characteristic_audit_status=terminal_characteristic_audit_status,
    residual_tolerance=residual_tolerance,
    position_tolerance_m=position_tolerance_m,
    message=message,
  )
####


def _field_audit_point_key(
  point: tuple[float, float],
  tolerance_m: float,
) -> tuple[int, int]:
  return round(point[0] / tolerance_m), round(point[1] / tolerance_m)
####


def _field_audit_edge_key(
  first: tuple[float, float],
  second: tuple[float, float],
  tolerance_m: float,
) -> tuple[tuple[int, int], tuple[int, int]]:
  first_key = _field_audit_point_key(first, tolerance_m)
  second_key = _field_audit_point_key(second, tolerance_m)
  return (
    (first_key, second_key)
    if first_key <= second_key
    else (second_key, first_key)
  )
####


def _field_audit_boundary_paths_verified(
  field: Any,
  tolerance_m: float,
) -> bool:
  edge_counts: dict[
    tuple[tuple[int, int], tuple[int, int]],
    int,
  ] = {}
  for cell in field.cells:
    vertices = tuple(cell.vertices_xr_m)
    for first, second in zip(vertices, (*vertices[1:], vertices[0])):
      edge = _field_audit_edge_key(first, second, tolerance_m)
      edge_counts[edge] = edge_counts.get(edge, 0) + 1
    ####
  ####
  return all(
    edge_counts.get(_field_audit_edge_key(first, second, tolerance_m), 0) == 1
    for path in (
      tuple(field.shock_boundary_points_m),
      tuple(field.ambient_boundary_points_m),
      tuple(field.centerline_boundary_points_m),
    )
    for first, second in zip(path, path[1:])
  )
####


def _field_audit_raw_cell_samples(
  field: Any,
  tolerance_m: float,
) -> tuple[
  tuple[
    tuple[tuple[float, float], ...],
    tuple[CharacteristicState, ...],
    tuple[float, ...],
  ] | None,
  ...,
]:
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
      field.post_shock_boundary_states,
      field.post_shock_boundary_total_pressure_Pa,
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
      field.ambient_boundary.points_m,
      field.ambient_boundary.states,
      field.ambient_boundary.total_pressure_Pa,
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
      field.centerline_boundary_points_m,
      field.centerline_boundary_states,
      field.centerline_boundary_total_pressure_Pa,
      strict=True,
    )
  )
  sources.extend(
    (node.point_m, node.state, node.total_pressure_Pa)
    for node in field.nodes
  )

  def resolve(
    point: tuple[float, float],
  ) -> tuple[CharacteristicState, float] | None:
    for source_point, state, pressure in sources:
      if (
        hypot(point[0] - source_point[0], point[1] - source_point[1])
        <= tolerance_m
        and pressure is not None
      ):
        return state, float(pressure)
      ####
    ####
    return None
  ####

  samples: list[
    tuple[
      tuple[tuple[float, float], ...],
      tuple[CharacteristicState, ...],
      tuple[float, ...],
    ] | None
  ] = []
  for cell in field.cells:
    vertices = tuple(
      (float(point[0]), float(point[1])) for point in cell.vertices_xr_m
    )
    resolved = tuple(resolve(point) for point in vertices)
    if any(value is None for value in resolved):
      samples.append(None)
      continue
    ####
    complete = tuple(value for value in resolved if value is not None)
    samples.append(
      (
        vertices,
        tuple(value[0] for value in complete),
        tuple(value[1] for value in complete),
      )
    )
  ####
  return tuple(samples)
####


def measure_moc_euler_ambient_first_wedge_characteristic_field_audit(
  result: MocEulerAmbientFirstWedgeCharacteristicFieldResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeCharacteristicFieldAudit:
  """Recompute raw retiled-field topology, paths, samples, and Euler fluxes.

  This audit intentionally accepts the solver's non-converged diagnostic
  field.  It never calls the field sampler as an acceptance shortcut and
  never uses the cached field topology or residual flags as evidence.
  """

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeCharacteristicFieldResult,
  ):
    return _characteristic_field_audit_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.INVALID_INPUT,
      'result must be a '
      'MocEulerAmbientFirstWedgeCharacteristicFieldResult',
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    residual_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _characteristic_field_audit_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.INVALID_INPUT,
      'characteristic field audit tolerances must be numeric',
      solver_status=result.status.value,
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('cell_residual_tolerance', residual_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  retiled_field = result.retiled_field
  common = {
    'solver_status': result.status.value,
    'retiled_field_status': (
      None if retiled_field is None else retiled_field.status.value
    ),
    'replaced_cell_indices': result.replaced_cell_indices,
    'residual_tolerance': residual_tolerance,
    'position_tolerance_m': position_tolerance,
  }
  if retiled_field is None:
    return _characteristic_field_audit_failure(
      MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.FIELD_FAILURE,
      'characteristic field retile did not return an inspectable raw field',
      **common,
    )
  ####
  topology = validate_moc_mesh(retiled_field.cells)
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  boundary_paths_verified = _field_audit_boundary_paths_verified(
    retiled_field,
    position_tolerance,
  )
  samples = _field_audit_raw_cell_samples(retiled_field, position_tolerance)
  def sample_is_finite(sample: Any) -> bool:
    if sample is None:
      return False
    ####
    vertices, states, pressures = sample
    return bool(
      len(vertices) == len(states) == len(pressures)
      and all(
        isinstance(state, CharacteristicState)
        and all(
          isfinite(value)
          for value in (
            state.x_m,
            state.y_m,
            state.theta_rad,
            state.mach,
            state.gamma,
          )
        )
        and state.mach > 1.0
        and state.gamma > 1.0
        for state in states
      )
      and all(isfinite(float(pressure)) and float(pressure) > 0.0 for pressure in pressures)
      and all(
        hypot(state.x_m - point[0], state.y_m - point[1]) <= position_tolerance
        for point, state in zip(vertices, states, strict=True)
      )
    )
  ####
  state_samples_finite = all(sample_is_finite(sample) for sample in samples)
  sampled_cell_count = sum(sample is not None for sample in samples)
  residuals: list[float] = []
  if state_samples_finite:
    for sample in samples:
      if sample is None:
        continue
      ####
      try:
        residuals.append(_cell_flux_residual(*sample))
      except (ArithmeticError, FloatingPointError, TypeError, ValueError):
        residuals.append(float('nan'))
      ####
    ####
  ####
  residuals_finite = bool(
    len(residuals) == len(retiled_field.cells)
    and all(isfinite(value) and value >= 0.0 for value in residuals)
  )
  maximum_residual = max(residuals, default=None)
  replaced_residuals = tuple(
    residuals[index]
    for index in result.replaced_cell_indices
    if 0 <= index < len(residuals)
  )
  maximum_replaced_residual = max(replaced_residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= residual_tolerance
  )
  barrier_verified = bool(
    retiled_field.status is MocPhysicalPostShockFieldStatus.INVARIANT_FAILURE
    and not retiled_field.physical_closure_verified
    and not retiled_field.state_sampling_available
  )
  terminal_audit = None
  if result.terminal_wedge is not None:
    terminal_audit = measure_moc_euler_ambient_first_wedge_terminal_characteristic_audit(
      result.terminal_wedge,
      position_tolerance_m=position_tolerance,
      cell_residual_tolerance=residual_tolerance,
    )
  ####
  terminal_status = None if terminal_audit is None else terminal_audit.status.value
  if not topology_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.TOPOLOGY_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TOPOLOGY_FAILURE.value
    message = f'independent retiled-field topology audit failed: {topology.message}'
  elif not boundary_paths_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.PATH_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TOPOLOGY_FAILURE.value
    message = 'independent retiled-field physical boundary-path audit failed'
  elif not state_samples_finite:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.STATE_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.ADJACENT_CELL_FAILURE.value
    message = 'independent retiled-field state/pressure sampling audit failed'
  elif terminal_audit is None:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.FIELD_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.TERMINAL_WEDGE_FAILURE.value
    message = 'retiled field has no terminal characteristic evidence to audit'
  elif not terminal_audit.characteristic_geometry_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.CHARACTERISTIC_GEOMETRY_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.CHARACTERISTIC_GEOMETRY_FAILURE.value
    message = 'independent terminal characteristic geometry audit failed'
  elif not terminal_audit.variable_entropy_compatibility_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.ENTROPY_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.ENTROPY_FAILURE.value
    message = 'independent terminal characteristic entropy audit failed'
  elif not terminal_audit.cell_euler_residual_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.EULER_RESIDUAL_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.EULER_RESIDUAL_FAILURE.value
    message = 'independent terminal characteristic Euler residual audit failed'
  elif not residuals_finite or not residuals_verified:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.FIELD_EULER_RESIDUAL_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.EULER_RESIDUAL_FAILURE.value
    message = 'independent full retiled-field Euler residual audit failed'
  elif not barrier_verified or result.physical_closure_verified or not result.chain_promotion_blocked or result.production_claim_allowed:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.FLAG_FAILURE
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.CONVERGED_LOCAL_RETILE.value
    message = 'retiled-field result returned weakened fidelity flags or status barrier'
  else:
    status = MocEulerAmbientFirstWedgeCharacteristicFieldAuditStatus.CONVERGED_LOCAL_AUDIT
    expected_solver_status = MocEulerAmbientFirstWedgeCharacteristicFieldStatus.CONVERGED_LOCAL_RETILE.value
    message = 'independent retiled-field topology, paths, states, and Euler residuals passed'
  ####
  solver_status_consistent = (
    result.status.value == expected_solver_status
    and barrier_verified
  )
  if not solver_status_consistent:
    message += (
      f'; solver status {result.status.value!r} does not match the '
      f'independent expected status {expected_solver_status!r}'
    )
  ####
  return MocEulerAmbientFirstWedgeCharacteristicFieldAudit(
    status=status,
    solver_status=result.status.value,
    retiled_field_status=retiled_field.status.value,
    replaced_cell_indices=result.replaced_cell_indices,
    cell_count=len(retiled_field.cells),
    sampled_cell_count=sampled_cell_count,
    cell_euler_residuals=tuple(residuals),
    replaced_cell_euler_residuals=replaced_residuals,
    maximum_cell_euler_residual=maximum_residual,
    maximum_replaced_cell_euler_residual=maximum_replaced_residual,
    topology_verified=topology_verified,
    boundary_paths_verified=boundary_paths_verified,
    state_samples_finite=state_samples_finite,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    retiled_field_status_barrier_verified=barrier_verified,
    solver_status_consistent=solver_status_consistent,
    terminal_characteristic_audit_status=terminal_status,
    residual_tolerance=residual_tolerance,
    position_tolerance_m=position_tolerance,
    message=message,
  )
####
