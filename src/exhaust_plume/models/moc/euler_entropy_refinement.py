"""Bounded subcell refinement for the Euler entropy-carrying trial.

The entropy-carrying terminal trial closes the generalized source equations on
its three physical boundary vertices, but its coarse triangular finite-volume
residual is still too large for a field handoff.  This module provides a
solver-owned resolution probe over that same triangle.  It interpolates the
compatible ``theta``/``nu`` variables and logarithmic total pressure on a
barycentric lattice, then measures every triangular subcell.

The interpolation is deliberately labelled a projection.  It is evidence
about residual reduction, not an internal characteristic solve: no projected
subcell is eligible for a physical shock-cell chain until the characteristic
family closure and reflected/free-boundary solve are supplied separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, hypot, isfinite, log
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
  _cell_euler_residual,
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
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementResult',
  'refine_euler_ambient_first_wedge_entropy_carry',
)


class MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus(str, Enum):
  """Outcome of the bounded entropy-carrying subcell projection."""

  CONVERGED_DIAGNOSTIC_REFINEMENT = (
    'converged_euler_ambient_first_wedge_entropy_carry_diagnostic_refinement'
  )
  INVALID_INPUT = 'invalid_input'
  TRIAL_REQUIRED = (
    'euler_ambient_first_wedge_entropy_carry_refinement_trial_required'
  )
  STATE_PROJECTION_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_state_projection_failure'
  )
  PRESSURE_LINEAGE_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_pressure_lineage_failure'
  )
  GEOMETRY_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_geometry_failure'
  )
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_topology_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_euler_residual_failure'
  )
####


def _finite_point(value: Any, label: str) -> tuple[float, float]:
  try:
    point = (float(value[0]), float(value[1]))
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(f'{label} must contain two numeric coordinates') from error
  ####
  if not all(isfinite(component) for component in point):
    raise ValueError(f'{label} must contain finite coordinates')
  ####
  return point
####


def _empty_topology() -> MocTopologyResult:
  return validate_moc_mesh(())
####


def _lattice_point(
  vertices: tuple[tuple[float, float], ...],
  side_count: int,
  first_index: int,
  second_index: int,
) -> tuple[float, float]:
  first, second, third = vertices
  first_weight = first_index / side_count
  second_weight = second_index / side_count
  return (
    first[0]
    + first_weight * (second[0] - first[0])
    + second_weight * (third[0] - first[0]),
    first[1]
    + first_weight * (second[1] - first[1])
    + second_weight * (third[1] - first[1]),
  )
####


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
  third_weight = 1.0 - first_weight - second_weight
  weights = (third_weight, first_weight, second_weight)
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
    raise ValueError(
      'barycentric entropy-carrying projection left the supersonic Mach domain'
    )
  ####
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=theta,
    mach=inversion.value,
    gamma=states[0].gamma,
  )
  pressure = exp(
    sum(weight * log(pressure_value) for weight, pressure_value in zip(
      weights,
      pressures,
      strict=True,
    ))
  )
  if not isfinite(pressure) or pressure <= 0.0:
    raise ValueError('barycentric total-pressure projection was not positive')
  ####
  return state, pressure
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryRefinementResult:
  """A diagnostic subcell ladder entry below the characteristic-field gate."""

  status: MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus
  source_trial: MocEulerAmbientFirstWedgeEntropyCarryResult | None
  subdivision_level: int
  subdivision_side_count: int
  cells: tuple[MocCharacteristicCell, ...]
  cell_samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...]
  topology: MocTopologyResult
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  state_projection_verified: bool
  pressure_lineage_carried: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  internal_characteristic_closure_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  position_tolerance_m: float = 1.0e-10
  pressure_lineage_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus'
      )
    ####
    if self.source_trial is not None and not isinstance(
      self.source_trial,
      MocEulerAmbientFirstWedgeEntropyCarryResult,
    ):
      raise TypeError(
        'source_trial must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryResult or None'
      )
    ####
    for name in ('subdivision_level', 'subdivision_side_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.subdivision_level == 0 and self.subdivision_side_count != 1:
      raise ValueError('zero-level refinement must have one subcell side')
    ####
    if self.subdivision_level > 0 and self.subdivision_side_count < 2:
      raise ValueError('positive-level refinement must have at least two sides')
    ####
    cells = tuple(self.cells)
    samples = tuple(self.cell_samples)
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if len(cells) != len(samples) or len(cells) != len(residuals):
      raise ValueError(
        'cells, cell_samples, and cell_euler_residuals must have equal lengths'
      )
    ####
    if any(not isinstance(cell, MocCharacteristicCell) for cell in cells):
      raise TypeError('cells must contain MocCharacteristicCell values')
    ####
    if any(
      not isinstance(sample, MocEulerAmbientFirstWedgeCellSample)
      for sample in samples
    ):
      raise TypeError(
        'cell_samples must contain MocEulerAmbientFirstWedgeCellSample values'
      )
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'cell_euler_residuals must contain finite nonnegative values'
      )
    ####
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    if self.maximum_cell_euler_residual is not None:
      maximum = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative when supplied'
        )
      ####
      object.__setattr__(self, 'maximum_cell_euler_residual', maximum)
    ####
    for name in (
      'state_projection_verified',
      'pressure_lineage_carried',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'internal_characteristic_closure_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.internal_characteristic_closure_verified:
      raise ValueError(
        'the barycentric projection cannot claim internal characteristic closure'
      )
    ####
    if self.physical_closure_verified:
      raise ValueError(
        'a diagnostic entropy-carrying refinement cannot claim physical closure'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'a diagnostic entropy-carrying refinement cannot claim production validity'
      )
    ####
    for name in (
      'position_tolerance_m',
      'pressure_lineage_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    object.__setattr__(self, 'cells', cells)
    object.__setattr__(self, 'cell_samples', samples)
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether this projected resolution passed its local residual gate."""

    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus
      .CONVERGED_DIAGNOSTIC_REFINEMENT
    )
  ####

  @property
  def cell_count(self) -> int:
    return len(self.cells)
  ####

  @property
  def state_sample_count(self) -> int:
    return len({
      point
      for sample in self.cell_samples
      for point in sample.vertices_xr_m
    })
  ####

  @property
  def local_projection_verified(self) -> bool:
    return bool(
      self.converged
      and self.state_projection_verified
      and self.pressure_lineage_carried
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and self.topology.connected
      and self.topology.forms_closed_zone
      and self.topology.nonmanifold_edge_count == 0
      and not self.internal_characteristic_closure_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the hard boundary between projected cells and MOC cells."""

    reason = (
      MocChainTerminationReason.INVALID_INPUT
      if self.status is MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.INVALID_INPUT
      else MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        'entropy-carrying subcell projection is residual evidence only; '
        'internal characteristic closure, reflected free-boundary coupling, '
        'and external validation are still required'
        if reason is MocChainTerminationReason.FIDELITY_NOT_ALLOWED
        else self.message
      ),
      diagnostics={
        'entropy_carry_refinement_status': self.status.value,
        'subdivision_level': self.subdivision_level,
        'subdivision_side_count': self.subdivision_side_count,
        'cell_count': self.cell_count,
        'state_sample_count': self.state_sample_count,
        'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'physical_chain_cell_count': 0,
        'required_next_gate': (
          'internal-characteristic-family-closure-on-refined-entropy-field-'
          'and-reflected-free-boundary-coupling'
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_projection_verified': self.local_projection_verified,
      'source_trial_status': (
        None if self.source_trial is None else self.source_trial.status.value
      ),
      'subdivision_level': self.subdivision_level,
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'state_sample_count': self.state_sample_count,
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'topology': {
        'status': self.topology.status.value,
        'connected': self.topology.connected,
        'forms_closed_zone': self.topology.forms_closed_zone,
        'boundary_edge_count': self.topology.boundary_edge_count,
        'nonmanifold_edge_count': self.topology.nonmanifold_edge_count,
      },
      'checks': {
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'position_tolerance_m': self.position_tolerance_m,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'claim_status': (
        'solver-owned-barycentric-entropy-carrying-subcell-projection; '
        'internal-characteristic-closure and reflected free-boundary validation '
        'remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus,
  source_trial: MocEulerAmbientFirstWedgeEntropyCarryResult | None,
  *,
  subdivision_level: int = 0,
  subdivision_side_count: int = 1,
  cells: tuple[MocCharacteristicCell, ...] = (),
  samples: tuple[MocEulerAmbientFirstWedgeCellSample, ...] = (),
  topology: MocTopologyResult | None = None,
  residuals: tuple[float, ...] = (),
  maximum_residual: float | None = None,
  state_projection_verified: bool = False,
  pressure_lineage_carried: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  position_tolerance_m: float = 1.0e-10,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementResult:
  return MocEulerAmbientFirstWedgeEntropyCarryRefinementResult(
    status=status,
    source_trial=source_trial,
    subdivision_level=subdivision_level,
    subdivision_side_count=subdivision_side_count,
    cells=cells,
    cell_samples=samples,
    topology=_empty_topology() if topology is None else topology,
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=maximum_residual,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    position_tolerance_m=position_tolerance_m,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def refine_euler_ambient_first_wedge_entropy_carry(
  source_trial: MocEulerAmbientFirstWedgeEntropyCarryResult,
  *,
  subdivision_level: int = 3,
  position_tolerance_m: float = 1.0e-10,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementResult:
  """Project one entropy-carrying triangle onto a bounded subcell lattice.

  ``subdivision_level=1`` creates four triangles, level two creates sixteen,
  and level three creates sixty-four.  Only the source trial's three vertices
  are used; no state is sampled or extrapolated from a lower-fidelity field.
  """

  if not isinstance(source_trial, MocEulerAmbientFirstWedgeEntropyCarryResult):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.INVALID_INPUT,
      None,
      message=(
        'source_trial must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryResult'
      ),
    )
  ####
  try:
    position_tolerance = float(position_tolerance_m)
    lineage_tolerance = float(pressure_lineage_tolerance)
    residual_tolerance = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.INVALID_INPUT,
      source_trial,
      message='entropy-carrying refinement tolerances must be numeric',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('pressure_lineage_tolerance', lineage_tolerance),
    ('cell_residual_tolerance', residual_tolerance),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if (
    isinstance(subdivision_level, bool)
    or not isinstance(subdivision_level, int)
    or subdivision_level < 1
    or subdivision_level > 5
  ):
    raise ValueError('subdivision_level must be an integer from one through five')
  ####
  side_count = 2 ** subdivision_level
  common = {
    'subdivision_level': subdivision_level,
    'subdivision_side_count': side_count,
    'position_tolerance_m': position_tolerance,
    'pressure_lineage_tolerance': lineage_tolerance,
    'cell_residual_tolerance': residual_tolerance,
  }
  if not (
    source_trial.pressure_lineage_verified
    and source_trial.characteristic_geometry_verified
    and source_trial.variable_entropy_compatibility_verified
    and source_trial.axis_streamline_entropy_verified
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.TRIAL_REQUIRED,
      source_trial,
      message=(
        'entropy-carrying refinement requires source pressure lineage, '
        'characteristic geometry, variable-entropy compatibility, and axis '
        'streamline gates'
      ),
      **common,
    )
  ####
  try:
    vertices = tuple(
      _finite_point(point, 'entropy-carrying trial vertices')
      for point in source_trial.vertices_xr_m
    )
  except ValueError as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.GEOMETRY_FAILURE,
      source_trial,
      message=str(error),
      **common,
    )
  ####
  if len(vertices) != 3 or len(source_trial.states) != 3 or len(
    source_trial.total_pressure_Pa
  ) != 3:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.GEOMETRY_FAILURE,
      source_trial,
      message='entropy-carrying refinement requires exactly three source vertices',
      **common,
    )
  ####
  states = tuple(source_trial.states)
  pressures = tuple(float(value) for value in source_trial.total_pressure_Pa)
  if any(
    hypot(state.x_m - point[0], state.y_m - point[1]) > position_tolerance
    for state, point in zip(states, vertices, strict=True)
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.STATE_PROJECTION_FAILURE,
      source_trial,
      message='entropy-carrying source states do not lie on source vertices',
      **common,
    )
  ####
  pressure_lineage_carried = bool(
    abs(pressures[2] - pressures[0])
    <= lineage_tolerance * max(1.0, abs(pressures[0]), abs(pressures[2]))
    and all(isfinite(value) and value > 0.0 for value in pressures)
    and abs(vertices[0][1]) <= position_tolerance
    and abs(vertices[2][1]) <= position_tolerance
  )
  if not pressure_lineage_carried:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.PRESSURE_LINEAGE_FAILURE,
      source_trial,
      message='source entropy-carrying trial does not preserve axis pressure lineage',
      **common,
    )
  ####

  lattice: dict[tuple[int, int], tuple[float, float]] = {}
  samples_by_key: dict[
    tuple[int, int],
    tuple[CharacteristicState, float],
  ] = {}
  try:
    for first_index in range(side_count + 1):
      for second_index in range(side_count + 1 - first_index):
        lattice[(first_index, second_index)] = _lattice_point(
          vertices,
          side_count,
          first_index,
          second_index,
        )
        samples_by_key[(first_index, second_index)] = _project_sample(
          vertices,
          states,
          pressures,
          side_count,
          first_index,
          second_index,
        )
      ####
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.STATE_PROJECTION_FAILURE,
      source_trial,
      message=f'entropy-carrying subcell projection failed: {error}',
      **common,
    )
  ####

  cells: list[MocCharacteristicCell] = []
  samples: list[MocEulerAmbientFirstWedgeCellSample] = []
  residuals: list[float] = []
  try:
    for first_index in range(side_count):
      for second_index in range(side_count - first_index):
        keys = (
          (first_index, second_index),
          (first_index + 1, second_index),
          (first_index, second_index + 1),
        )
        cell_vertices = tuple(lattice[key] for key in keys)
        cell_samples = tuple(samples_by_key[key] for key in keys)
        cell_states = tuple(item[0] for item in cell_samples)
        cell_pressures = tuple(item[1] for item in cell_samples)
        cells.append(
          MocCharacteristicCell(
            cell_index=len(cells),
            cell_kind='post-shock-ambient-terminal-entropy-projection',
            vertices_xr_m=cell_vertices,
            centerline_indices=(),
            boundary_indices=(),
          )
        )
        samples.append(
          MocEulerAmbientFirstWedgeCellSample(
            vertices_xr_m=cell_vertices,
            states=cell_states,
            total_pressure_Pa=cell_pressures,
          )
        )
        residuals.append(
          _cell_euler_residual(cell_vertices, cell_states, cell_pressures)
        )
        if first_index + second_index <= side_count - 2:
          keys = (
            (first_index + 1, second_index),
            (first_index + 1, second_index + 1),
            (first_index, second_index + 1),
          )
          cell_vertices = tuple(lattice[key] for key in keys)
          cell_samples = tuple(samples_by_key[key] for key in keys)
          cell_states = tuple(item[0] for item in cell_samples)
          cell_pressures = tuple(item[1] for item in cell_samples)
          cells.append(
            MocCharacteristicCell(
              cell_index=len(cells),
              cell_kind='post-shock-ambient-terminal-entropy-projection',
              vertices_xr_m=cell_vertices,
              centerline_indices=(),
              boundary_indices=(),
            )
          )
          samples.append(
            MocEulerAmbientFirstWedgeCellSample(
              vertices_xr_m=cell_vertices,
              states=cell_states,
              total_pressure_Pa=cell_pressures,
            )
          )
          residuals.append(
            _cell_euler_residual(cell_vertices, cell_states, cell_pressures)
          )
        ####
      ####
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.GEOMETRY_FAILURE,
      source_trial,
      cells=tuple(cells),
      samples=tuple(samples),
      residuals=tuple(residuals),
      maximum_residual=max(residuals, default=None),
      state_projection_verified=True,
      pressure_lineage_carried=pressure_lineage_carried,
      residuals_finite=all(isfinite(value) for value in residuals),
      message=f'entropy-carrying subcell geometry failed: {error}',
      **common,
    )
  ####
  topology = validate_moc_mesh(tuple(cells))
  topology_verified = bool(
    topology.connected
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.TOPOLOGY_FAILURE,
      source_trial,
      cells=tuple(cells),
      samples=tuple(samples),
      topology=topology,
      residuals=tuple(residuals),
      maximum_residual=max(residuals, default=None),
      state_projection_verified=True,
      pressure_lineage_carried=pressure_lineage_carried,
      residuals_finite=all(isfinite(value) for value in residuals),
      message=f'entropy-carrying subcell topology failed: {topology.message}',
      **common,
    )
  ####
  residuals_finite = bool(residuals and all(isfinite(value) for value in residuals))
  maximum_residual = max(residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= residual_tolerance
  )
  state_projection_verified = bool(
    all(
      len(sample.vertices_xr_m) == 3
      and all(
        hypot(state.x_m - point[0], state.y_m - point[1])
        <= position_tolerance
        for state, point in zip(sample.states, sample.vertices_xr_m, strict=True)
      )
      for sample in samples
    )
  )
  if not state_projection_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.STATE_PROJECTION_FAILURE
    message = 'entropy-carrying subcell samples failed state/vertex projection checks'
  elif not residuals_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.EULER_RESIDUAL_FAILURE
    message = (
      'entropy-carrying subcell projection is finite but its maximum Euler '
      f'residual remains above tolerance ({maximum_residual})'
    )
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus
      .CONVERGED_DIAGNOSTIC_REFINEMENT
    )
    message = (
      'entropy-carrying subcell projection passed topology, pressure lineage, '
      'and local Euler residual gates; internal characteristic closure remains '
      'unsolved'
    )
  ####
  return MocEulerAmbientFirstWedgeEntropyCarryRefinementResult(
    status=status,
    source_trial=source_trial,
    subdivision_level=subdivision_level,
    subdivision_side_count=side_count,
    cells=tuple(cells),
    cell_samples=tuple(samples),
    topology=topology,
    cell_euler_residuals=tuple(residuals),
    maximum_cell_euler_residual=maximum_residual,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    position_tolerance_m=position_tolerance,
    pressure_lineage_tolerance=lineage_tolerance,
    cell_residual_tolerance=residual_tolerance,
    message=message,
  )
####
