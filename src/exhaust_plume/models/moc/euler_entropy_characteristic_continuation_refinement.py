"""Bounded refinement evidence for the variable-entropy continuation band.

The solver-owned continuation is a coarse alternating characteristic source
band.  This module refines each returned triangular cell on a barycentric
lattice in the compatible variables ``theta``, ``nu``, and ``log(p0)``.  It
is intentionally a projection/refinement diagnostic: it does not claim that
the projected points are a newly solved characteristic net, and it cannot
create a physical shock-cell-chain cell.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, hypot, isfinite, log
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_carry import _cell_euler_residual
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.topology import MocTopologyResult, validate_moc_mesh
from exhaust_plume.models.moc.zone import MocCharacteristicCell

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult',
  'refine_euler_ambient_first_wedge_entropy_characteristic_continuation',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus(
  str,
  Enum,
):
  """Outcome of one bounded continuation-band refinement."""

  CONVERGED_DIAGNOSTIC_REFINEMENT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_continuation_diagnostic_refinement'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_REQUIRED = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_source_required'
  )
  STATE_PROJECTION_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_state_projection_failure'
  )
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_topology_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_euler_residual_failure'
  )


def _lattice_point(
  vertices: tuple[tuple[float, float], ...],
  side_count: int,
  first_index: int,
  second_index: int,
) -> tuple[float, float]:
  first, second, third = vertices
  first_weight = first_index / side_count
  second_weight = second_index / side_count
  third_weight = 1.0 - first_weight - second_weight
  return tuple(
    third_weight * first[index]
    + first_weight * second[index]
    + second_weight * third[index]
    for index in (0, 1)
  )


def _project_sample(
  vertices: tuple[tuple[float, float], ...],
  states: tuple[CharacteristicState, ...],
  pressures: tuple[float, ...],
  side_count: int,
  first_index: int,
  second_index: int,
) -> tuple[CharacteristicState, float]:
  point = _lattice_point(
    vertices,
    side_count,
    first_index,
    second_index,
  )
  first_weight = first_index / side_count
  second_weight = second_index / side_count
  weights = (
    1.0 - first_weight - second_weight,
    first_weight,
    second_weight,
  )
  theta = sum(
    weight * state.theta_rad
    for weight, state in zip(weights, states, strict=True)
  )
  nu = sum(
    weight * state.nu_rad
    for weight, state in zip(weights, states, strict=True)
  )
  inversion = inverse_prandtl_meyer_angle_rad(nu, states[0].gamma)
  if not inversion.converged or inversion.value is None:
    raise ValueError('continuation refinement left the supersonic Mach domain')
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=theta,
    mach=inversion.value,
    gamma=states[0].gamma,
  )
  total_pressure = exp(
    sum(
      weight * log(pressure)
      for weight, pressure in zip(weights, pressures, strict=True)
    )
  )
  if not isfinite(total_pressure) or total_pressure <= 0.0:
    raise ValueError('continuation refinement total pressure was not positive')
  return state, total_pressure


def _triangle_weights(
  point: tuple[float, float],
  vertices: Sequence[tuple[float, float]],
  tolerance_m: float,
) -> tuple[float, float, float] | None:
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
  if min(first, second, third) < -1.0e-10 or max(
    first,
    second,
    third,
  ) > 1.0 + 1.0e-10:
    return None
  return first, second, third


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult:
  """One projection-refinement resolution below physical MOC closure."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
  source_continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult | None
  subdivision_side_count: int
  cells: tuple[MocCharacteristicCell, ...]
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...]
  topology: MocTopologyResult
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  state_projection_verified: bool
  pressure_lineage_carried: bool
  continuation_boundary_verified: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  internal_characteristic_closure_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  position_tolerance_m: float = 1.0e-8
  projection_tolerance: float = 1.0e-9
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus,
    ):
      raise TypeError('status must be a continuation-refinement status')
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
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if len(cells) != len(samples) or len(cells) != len(residuals):
      raise ValueError('cells, samples, and residuals must have equal lengths')
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError('cells must contain MocCharacteristicCell values')
    if any(
      not isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      for sample in samples
    ):
      raise TypeError('cell_samples must contain typed cell samples')
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('cell_euler_residuals must be finite and nonnegative')
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    if self.maximum_cell_euler_residual is not None:
      maximum = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative'
        )
      object.__setattr__(self, 'maximum_cell_euler_residual', maximum)
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'cell_samples', samples)
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    for name in (
      'state_projection_verified',
      'pressure_lineage_carried',
      'continuation_boundary_verified',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'internal_characteristic_closure_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.internal_characteristic_closure_verified:
      raise ValueError('projection refinement cannot claim characteristic closure')
    if self.physical_closure_verified:
      raise ValueError('projection refinement cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError('projection refinement must retain the promotion block')
    if self.production_claim_allowed:
      raise ValueError('projection refinement cannot claim production validity')
    for name in (
      'position_tolerance_m',
      'projection_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .CONVERGED_DIAGNOSTIC_REFINEMENT
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
  def continuation_boundary_kind(self) -> MocChainBoundaryKind:
    return MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER

  @property
  def continuation_boundary(self):
    if self.source_continuation is None:
      return ()
    return self.source_continuation.continuation_boundary

  @property
  def local_projection_verified(self) -> bool:
    return bool(
      self.converged
      and self.state_projection_verified
      and self.pressure_lineage_carried
      and self.continuation_boundary_verified
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and not self.internal_characteristic_closure_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  @property
  def state_sampling_available(self) -> bool:
    return bool(self.local_projection_verified and self.cells and self.cell_samples)

  def _sample_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float,
  ) -> tuple[tuple[float, float, float], MocEulerAmbientFirstWedgeCellSample] | None:
    try:
      point = (float(point_m[0]), float(point_m[1]))
    except (IndexError, TypeError, ValueError):
      return None
    if not all(isfinite(value) for value in point):
      return None
    for sample in self.cell_samples:
      weights = _triangle_weights(
        point,
        sample.vertices_xr_m,
        position_tolerance_m,
      )
      if weights is not None:
        return weights, sample
    return None

  def state_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> CharacteristicState | None:
    sampled = self._sample_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    weights, sample = sampled
    point = (float(point_m[0]), float(point_m[1]))
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

  def total_pressure_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> float | None:
    sampled = self._sample_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if sampled is None:
      return None
    weights, sample = sampled
    return exp(
      sum(
        weight * log(pressure)
        for weight, pressure in zip(weights, sample.total_pressure_Pa, strict=True)
      )
    )

  def static_pressure_at(
    self,
    point_m: Sequence[float],
    *,
    position_tolerance_m: float = 1.0e-8,
  ) -> float | None:
    state = self.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    total_pressure = self.total_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or total_pressure is None:
      return None
    return total_pressure / (
      1.0 + 0.5 * (state.gamma - 1.0) * state.mach * state.mach
    ) ** (state.gamma / (state.gamma - 1.0))

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
        .INVALID_INPUT
      )
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'continuation-band projection refinement is diagnostic only; '
        'characteristic re-closure, reflected shock closure, and external '
        'validation remain required'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'continuation_refinement_status': self.status.value,
        'subdivision_side_count': self.subdivision_side_count,
        'cell_count': self.cell_count,
        'state_sample_count': self.state_sample_count,
        'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'physical_chain_cell_count': 0,
        'external_validation_required': True,
        'required_next_gate': (
          'solver-owned-intra-cycle-characteristic-remesh-and-reflected-'
          'shock-free-boundary-closure'
        ),
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_projection_verified': self.local_projection_verified,
      'continuation_boundary_kind': self.continuation_boundary_kind.value,
      'continuation_boundary_verified': self.continuation_boundary_verified,
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'state_sample_count': self.state_sample_count,
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'boundary_component_count': self.topology.boundary_component_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'source_continuation_status': (
        None
        if self.source_continuation is None
        else self.source_continuation.status.value
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': True,
      'position_tolerance_m': self.position_tolerance_m,
      'projection_tolerance': self.projection_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus,
  source_continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult | None,
  *,
  subdivision_side_count: int = 1,
  cells: Sequence[MocCharacteristicCell] = (),
  samples: Sequence[MocEulerAmbientFirstWedgeCellSample] = (),
  topology: MocTopologyResult | None = None,
  residuals: Sequence[float] = (),
  maximum_residual: float | None = None,
  state_projection_verified: bool = False,
  pressure_lineage_carried: bool = False,
  continuation_boundary_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  position_tolerance_m: float = 1.0e-8,
  projection_tolerance: float = 1.0e-9,
  cell_residual_tolerance: float = 1.0e-2,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult(
    status=status,
    source_continuation=source_continuation,
    subdivision_side_count=subdivision_side_count,
    cells=tuple(cells),
    cell_samples=tuple(samples),
    topology=validate_moc_mesh(()) if topology is None else topology,
    cell_euler_residuals=tuple(residuals),
    maximum_cell_euler_residual=maximum_residual,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    continuation_boundary_verified=continuation_boundary_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    position_tolerance_m=position_tolerance_m,
    projection_tolerance=projection_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )


def refine_euler_ambient_first_wedge_entropy_characteristic_continuation(
  source_continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  *,
  subdivision_side_count: int = 12,
  position_tolerance_m: float = 1.0e-8,
  projection_tolerance: float = 1.0e-9,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult:
  """Project every continuation triangle onto a declared barycentric lattice."""

  if not isinstance(
    source_continuation,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .INVALID_INPUT,
      None,
      message='source_continuation must be a typed continuation result',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    projection_limit = float(projection_tolerance)
    residual_limit = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .INVALID_INPUT,
      source_continuation,
      message='continuation refinement tolerances must be numeric',
    )
  if not all(
    isfinite(value) and value > 0.0
    for value in (position_tolerance, projection_limit, residual_limit)
  ):
    raise ValueError('continuation refinement tolerances must be finite and positive')
  if (
    isinstance(subdivision_side_count, bool)
    or not isinstance(subdivision_side_count, int)
    or subdivision_side_count < 1
    or subdivision_side_count > 32
  ):
    raise ValueError('subdivision_side_count must be an integer from one through 32')
  common = {
    'subdivision_side_count': subdivision_side_count,
    'position_tolerance_m': position_tolerance,
    'projection_tolerance': projection_limit,
    'cell_residual_tolerance': residual_limit,
  }
  if not (
    source_continuation.converged
    and source_continuation.local_consistency_verified
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .SOURCE_REQUIRED,
      source_continuation,
      message=(
        'continuation refinement requires a converged locally consistent '
        'bounded source band'
      ),
      **common,
    )
  if not source_continuation.cell_samples:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .SOURCE_REQUIRED,
      source_continuation,
      message='continuation refinement requires triangular source samples',
      **common,
    )

  cells: list[MocCharacteristicCell] = []
  samples: list[MocEulerAmbientFirstWedgeCellSample] = []
  residuals: list[float] = []
  state_projection_verified = True
  pressure_lineage_carried = True
  try:
    for parent_index, parent in enumerate(source_continuation.cell_samples):
      vertices = tuple(
        (float(point[0]), float(point[1])) for point in parent.vertices_xr_m
      )
      states = tuple(parent.states)
      pressures = tuple(float(value) for value in parent.total_pressure_Pa)
      if len(vertices) != 3 or len(states) != 3 or len(pressures) != 3:
        raise ValueError(
          f'parent continuation cell {parent_index} is not a triangle'
        )
      if any(
        not all(isfinite(value) for value in point)
        or not isinstance(state, CharacteristicState)
        or not all(
          isfinite(value)
          for value in (
            state.x_m,
            state.y_m,
            state.theta_rad,
            state.mach,
            state.gamma,
            pressure,
          )
        )
        or state.mach <= 1.0
        or state.gamma <= 1.0
        or pressure <= 0.0
        for point, state, pressure in zip(
          vertices,
          states,
          pressures,
          strict=True,
        )
      ):
        raise ValueError(f'parent continuation cell {parent_index} is non-finite')
      lattice: dict[tuple[int, int], tuple[CharacteristicState, float]] = {}
      for first_index in range(subdivision_side_count + 1):
        for second_index in range(
          subdivision_side_count + 1 - first_index
        ):
          lattice[(first_index, second_index)] = _project_sample(
            vertices,
            states,
            pressures,
            subdivision_side_count,
            first_index,
            second_index,
          )
      for first_index in range(subdivision_side_count):
        for second_index in range(subdivision_side_count - first_index):
          for keys in (
            (
              (first_index, second_index),
              (first_index + 1, second_index),
              (first_index, second_index + 1),
            ),
          ):
            cell_vertices = tuple(
              _lattice_point(
                vertices,
                subdivision_side_count,
                key[0],
                key[1],
              )
              for key in keys
            )
            cell_states = tuple(lattice[key][0] for key in keys)
            cell_pressures = tuple(lattice[key][1] for key in keys)
            cell = MocCharacteristicCell(
              cell_index=len(cells),
              cell_kind='entropy-continuation-projection-refinement',
              vertices_xr_m=cell_vertices,
              centerline_indices=(),
              boundary_indices=(),
            )
            sample = MocEulerAmbientFirstWedgeCellSample(
              vertices_xr_m=cell_vertices,
              states=cell_states,
              total_pressure_Pa=cell_pressures,
            )
            cells.append(cell)
            samples.append(sample)
            residuals.append(
              _cell_euler_residual(
                cell_vertices,
                cell_states,
                cell_pressures,
              )
            )
          if first_index + second_index <= subdivision_side_count - 2:
            keys = (
              (first_index + 1, second_index),
              (first_index + 1, second_index + 1),
              (first_index, second_index + 1),
            )
            cell_vertices = tuple(
              _lattice_point(
                vertices,
                subdivision_side_count,
                key[0],
                key[1],
              )
              for key in keys
            )
            cell_states = tuple(lattice[key][0] for key in keys)
            cell_pressures = tuple(lattice[key][1] for key in keys)
            cell = MocCharacteristicCell(
              cell_index=len(cells),
              cell_kind='entropy-continuation-projection-refinement',
              vertices_xr_m=cell_vertices,
              centerline_indices=(),
              boundary_indices=(),
            )
            sample = MocEulerAmbientFirstWedgeCellSample(
              vertices_xr_m=cell_vertices,
              states=cell_states,
              total_pressure_Pa=cell_pressures,
            )
            cells.append(cell)
            samples.append(sample)
            residuals.append(
              _cell_euler_residual(
                cell_vertices,
                cell_states,
                cell_pressures,
              )
            )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .STATE_PROJECTION_FAILURE,
      source_continuation,
      cells=cells,
      samples=samples,
      residuals=residuals,
      maximum_residual=max(residuals, default=None),
      state_projection_verified=False,
      pressure_lineage_carried=False,
      continuation_boundary_verified=source_continuation.continuation_boundary_verified,
      residuals_finite=bool(residuals and all(isfinite(value) for value in residuals)),
      message=f'continuation projection refinement failed: {error}',
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
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .TOPOLOGY_FAILURE,
      source_continuation,
      cells=cells,
      samples=samples,
      topology=topology,
      residuals=residuals,
      maximum_residual=max(residuals, default=None),
      state_projection_verified=False,
      pressure_lineage_carried=False,
      continuation_boundary_verified=source_continuation.continuation_boundary_verified,
      residuals_finite=bool(residuals and all(isfinite(value) for value in residuals)),
      message=f'continuation projection topology failed: {topology.message}',
      **common,
    )
  for sample in samples:
    for point, state, pressure in zip(
      sample.vertices_xr_m,
      sample.states,
      sample.total_pressure_Pa,
      strict=True,
    ):
      state_projection_verified = bool(
        state_projection_verified
        and hypot(state.x_m - point[0], state.y_m - point[1])
        <= position_tolerance
        and isfinite(state.nu_rad)
        and state.mach > 1.0
        and state.gamma > 1.0
      )
      pressure_lineage_carried = bool(
        pressure_lineage_carried
        and isfinite(pressure)
        and pressure > 0.0
      )
  continuation_boundary_verified = bool(
    source_continuation.continuation_boundary_verified
    and source_continuation.continuation_boundary
  )
  residuals_finite = bool(residuals and all(isfinite(value) for value in residuals))
  maximum_residual = max(residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= residual_limit
  )
  if not state_projection_verified or not pressure_lineage_carried:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .STATE_PROJECTION_FAILURE
    )
    message = 'continuation projection refinement failed state or pressure checks'
  elif not residuals_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .EULER_RESIDUAL_FAILURE
    )
    message = (
      'continuation projection refinement is finite but its maximum Euler '
      f'residual remains above tolerance ({maximum_residual})'
    )
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .CONVERGED_DIAGNOSTIC_REFINEMENT
    )
    message = (
      'continuation projection refinement passed topology, lineage, and '
      'Euler residual gates; characteristic re-closure remains unsolved'
    )
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult(
    status=status,
    source_continuation=source_continuation,
    subdivision_side_count=subdivision_side_count,
    cells=tuple(cells),
    cell_samples=tuple(samples),
    topology=topology,
    cell_euler_residuals=tuple(residuals),
    maximum_cell_euler_residual=maximum_residual,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    continuation_boundary_verified=continuation_boundary_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    position_tolerance_m=position_tolerance,
    projection_tolerance=projection_limit,
    cell_residual_tolerance=residual_limit,
    message=message,
  )
