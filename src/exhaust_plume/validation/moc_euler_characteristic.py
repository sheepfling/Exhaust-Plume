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
from exhaust_plume.models.moc.primitives import CharacteristicFamily

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_CHARACTERISTIC_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeCharacteristicAuditStatus',
  'MocEulerAmbientFirstWedgeCharacteristicEdgeAudit',
  'MocEulerAmbientFirstWedgeCharacteristicAudit',
  'measure_moc_euler_ambient_first_wedge_characteristic_audit',
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
    if not isinstance(self.family, CharacteristicFamily):
      raise TypeError('family must be a CharacteristicFamily')
    for name in ('start_vertex', 'end_vertex'):
      point = getattr(self, name)
      if len(point) != 2 or not all(isfinite(float(value)) for value in point):
        raise ValueError(f'{name} must contain a finite coordinate pair')
      object.__setattr__(
        self,
        name,
        (float(point[0]), float(point[1])),
      )
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
      object.__setattr__(self, name, value)

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
    if self.remesh_status is not None:
      object.__setattr__(self, 'remesh_status', str(self.remesh_status))
    for name in ('subdivision_level', 'cell_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    edges = tuple(self.characteristic_edges)
    if any(
      not isinstance(edge, MocEulerAmbientFirstWedgeCharacteristicEdgeAudit)
      for edge in edges
    ):
      raise TypeError(
        'characteristic_edges must contain typed characteristic edge audits'
      )
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
        object.__setattr__(self, name, numeric)
    for name in (
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
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
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.CONVERGED_LOCAL_AUDIT
    )

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


def _log_pressure_gradient(
  vertices: tuple[tuple[float, float], ...],
  pressures: tuple[float, ...],
) -> tuple[float, float] | None:
  if len(vertices) != 3 or len(pressures) != 3:
    return None
  if any(not isfinite(value) or value <= 0.0 for value in pressures):
    return None
  (x1, y1), (x2, y2), (x3, y3) = vertices
  twice_area = (
    x1 * (y2 - y3)
    + x2 * (y3 - y1)
    + x3 * (y1 - y2)
  )
  if not isfinite(twice_area) or abs(twice_area) <= 1.0e-24:
    return None
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
  unit_direction = (
    averaged[0] / direction_length,
    averaged[1] / direction_length,
  )
  forward = edge[0] * unit_direction[0] + edge[1] * unit_direction[1]
  if forward <= 0.0:
    return None
  alignment = abs(
    edge[0] * unit_direction[1] - edge[1] * unit_direction[0]
  ) / edge_length
  return alignment, edge_length, forward


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
  if not isfinite(residual_tolerance) or residual_tolerance <= 0.0:
    raise ValueError('characteristic_residual_tolerance must be finite and positive')
  if not isfinite(alignment_tolerance) or alignment_tolerance <= 0.0:
    raise ValueError('edge_alignment_tolerance must be finite and positive')
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
  if len(remesh.cells) != len(remesh.cell_samples):
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE,
      'remesh cells and samples are not aligned',
      **common,
    )

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
      if not candidates:
        continue
      alignment, length, family, start_index, end_index = min(
        candidates,
        key=lambda value: value[0],
      )
      if alignment > alignment_tolerance:
        continue
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
    if len(cell_edges) < 2:
      edge_alignment_verified = False

  if not edges:
    return _failure(
      MocEulerAmbientFirstWedgeCharacteristicAuditStatus.GEOMETRY_FAILURE,
      'no characteristic-aligned edges were available for the entropy audit',
      characteristic_edges=edges,
      edge_alignment_verified=False,
      **common,
    )
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
