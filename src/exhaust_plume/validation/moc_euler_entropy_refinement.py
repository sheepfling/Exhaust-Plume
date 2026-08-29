"""Independent validation of entropy-carrying subcell refinement.

The solver-owned entropy projection is intentionally below the internal MOC
field gate.  This operator reconstructs its barycentric projection, topology,
pressure lineage, and conservative residuals from raw cell samples.  A ladder
measurement then verifies the declared resolution order and residual trend
without treating an interpolated subcell as a physical shock-cell handoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, hypot, isfinite, log
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
)
from exhaust_plume.models.moc.euler_entropy_refinement import (
  MocEulerAmbientFirstWedgeEntropyCarryRefinementResult,
  MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.topology import validate_moc_mesh
from exhaust_plume.validation.moc_euler import _cell_flux_residual
from exhaust_plume.validation.moc_euler_entropy import (
  measure_moc_euler_ambient_first_wedge_entropy_carry,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_carry_refinement',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementCase',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus',
  'MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurement',
  'measure_moc_euler_ambient_first_wedge_entropy_carry_refinement_ladder',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-carry-refinement-audit'
)


class MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus(str, Enum):
  """Outcome of the independent single-resolution refinement audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_carry_refinement_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_source_failure'
  )
  TOPOLOGY_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_topology_failure'
  )
  STATE_PROJECTION_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_state_projection_failure'
  )
  PRESSURE_LINEAGE_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_pressure_lineage_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_euler_residual_failure'
  )
  FLAG_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_flag_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit:
  """Raw gates for one projected entropy-carrying subcell resolution."""

  status: MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus
  solver_status: str | None
  source_trial_status: str | None
  subdivision_level: int
  subdivision_side_count: int
  cell_count: int
  sampled_cell_count: int
  state_sample_count: int
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  source_trial_gates_verified: bool
  topology_verified: bool
  state_samples_finite: bool
  state_projection_verified: bool
  pressure_lineage_carried: bool
  cell_euler_residuals_finite: bool
  cell_euler_residuals_verified: bool
  internal_characteristic_closure_verified: bool
  solver_status_consistent: bool
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  position_tolerance_m: float = 1.0e-10
  projection_tolerance: float = 1.0e-9
  pressure_lineage_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''
  operator_id: str = (
    MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_REFINEMENT_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus'
      )
    for name in (
      'subdivision_level',
      'subdivision_side_count',
      'cell_count',
      'sampled_cell_count',
      'state_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.solver_status is not None:
      object.__setattr__(self, 'solver_status', str(self.solver_status))
    if self.source_trial_status is not None:
      object.__setattr__(
        self,
        'source_trial_status',
        str(self.source_trial_status),
      )
    residuals = tuple(float(value) for value in self.cell_euler_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'cell_euler_residuals must contain finite nonnegative values'
      )
    if len(residuals) != self.cell_count:
      raise ValueError('cell_euler_residuals must match cell_count')
    object.__setattr__(self, 'cell_euler_residuals', residuals)
    if self.maximum_cell_euler_residual is not None:
      maximum = float(self.maximum_cell_euler_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative when supplied'
        )
      object.__setattr__(self, 'maximum_cell_euler_residual', maximum)
    for name in (
      'source_trial_gates_verified',
      'topology_verified',
      'state_samples_finite',
      'state_projection_verified',
      'pressure_lineage_carried',
      'cell_euler_residuals_finite',
      'cell_euler_residuals_verified',
      'internal_characteristic_closure_verified',
      'solver_status_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.internal_characteristic_closure_verified:
      raise ValueError(
        'the projection audit cannot claim internal characteristic closure'
      )
    if self.physical_closure_verified:
      raise ValueError(
        'the projection audit cannot claim physical closure'
      )
    if self.production_claim_allowed:
      raise ValueError(
        'the projection audit cannot claim production validity'
      )
    for name in (
      'position_tolerance_m',
      'projection_tolerance',
      'pressure_lineage_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.source_trial_gates_verified
      and self.topology_verified
      and self.state_samples_finite
      and self.state_projection_verified
      and self.pressure_lineage_carried
      and self.cell_euler_residuals_finite
      and self.cell_euler_residuals_verified
      and not self.internal_characteristic_closure_verified
      and self.solver_status_consistent
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'solver_status': self.solver_status,
      'source_trial_status': self.source_trial_status,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'subdivision_level': self.subdivision_level,
      'subdivision_side_count': self.subdivision_side_count,
      'cell_count': self.cell_count,
      'sampled_cell_count': self.sampled_cell_count,
      'state_sample_count': self.state_sample_count,
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'source_trial_gates_verified': self.source_trial_gates_verified,
        'topology_verified': self.topology_verified,
        'state_samples_finite': self.state_samples_finite,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_carried': self.pressure_lineage_carried,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'cell_euler_residuals_verified': self.cell_euler_residuals_verified,
        'internal_characteristic_closure_verified': False,
        'solver_status_consistent': self.solver_status_consistent,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
      'position_tolerance_m': self.position_tolerance_m,
      'projection_tolerance': self.projection_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-entropy-carrying-subcell-projection-audit; internal '
        'characteristic closure, reflected free boundary, and external '
        'validation remain pending'
      ),
      'message': self.message,
    }


def _audit_failure(
  status: MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus,
  message: str,
  *,
  result: MocEulerAmbientFirstWedgeEntropyCarryRefinementResult | None = None,
  source_trial_gates_verified: bool = False,
  topology_verified: bool = False,
  state_samples_finite: bool = False,
  state_projection_verified: bool = False,
  pressure_lineage_carried: bool = False,
  residuals: Sequence[float] = (),
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  solver_status_consistent: bool = False,
  position_tolerance_m: float = 1.0e-10,
  projection_tolerance: float = 1.0e-9,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit:
  result_status = None if result is None else result.status.value
  source_trial_status = (
    None
    if result is None or result.source_trial is None
    else result.source_trial.status.value
  )
  result_level = 0 if result is None else result.subdivision_level
  result_side_count = 0 if result is None else result.subdivision_side_count
  result_cell_count = 0 if result is None else result.cell_count
  values = tuple(float(value) for value in residuals)
  return MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit(
    status=status,
    solver_status=result_status,
    source_trial_status=source_trial_status,
    subdivision_level=result_level,
    subdivision_side_count=result_side_count,
    cell_count=result_cell_count,
    sampled_cell_count=0 if result is None else len(result.cell_samples),
    state_sample_count=0 if result is None else result.state_sample_count,
    cell_euler_residuals=values,
    maximum_cell_euler_residual=max(values, default=None),
    source_trial_gates_verified=source_trial_gates_verified,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    internal_characteristic_closure_verified=False,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=(
      False if result is None else result.physical_closure_verified
    ),
    chain_promotion_blocked=(
      True if result is None else result.chain_promotion_blocked
    ),
    production_claim_allowed=(
      False if result is None else result.production_claim_allowed
    ),
    position_tolerance_m=position_tolerance_m,
    projection_tolerance=projection_tolerance,
    pressure_lineage_tolerance=pressure_lineage_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )


def _triangle_weights(
  point: tuple[float, float],
  vertices: tuple[tuple[float, float], ...],
  tolerance_m: float,
) -> tuple[float, float, float] | None:
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
  if min(first, second, third) < -tolerance_m:
    return None
  if max(first, second, third) > 1.0 + tolerance_m:
    return None
  return first, second, third


def _projected_values(
  point: tuple[float, float],
  source_vertices: tuple[tuple[float, float], ...],
  source_states: tuple[CharacteristicState, ...],
  source_pressures: tuple[float, ...],
  *,
  position_tolerance_m: float,
) -> tuple[float, float, float] | None:
  weights = _triangle_weights(point, source_vertices, position_tolerance_m)
  if weights is None:
    return None
  expected_theta = sum(
    weight * state.theta_rad
    for weight, state in zip(weights, source_states, strict=True)
  )
  expected_nu = sum(
    weight * state.nu_rad
    for weight, state in zip(weights, source_states, strict=True)
  )
  expected_pressure = exp(
    sum(
      weight * log(pressure)
      for weight, pressure in zip(weights, source_pressures, strict=True)
    )
  )
  return expected_theta, expected_nu, expected_pressure


def measure_moc_euler_ambient_first_wedge_entropy_carry_refinement(
  result: MocEulerAmbientFirstWedgeEntropyCarryRefinementResult,
  *,
  position_tolerance_m: float = 1.0e-10,
  projection_tolerance: float = 1.0e-9,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit:
  """Recompute one projected refinement result from raw samples."""

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCarryRefinementResult,
  ):
    return _audit_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.INVALID_INPUT,
      'result must be a '
      'MocEulerAmbientFirstWedgeEntropyCarryRefinementResult',
    )
  try:
    position_tolerance = float(position_tolerance_m)
    projection_limit = float(projection_tolerance)
    lineage_limit = float(pressure_lineage_tolerance)
    residual_limit = float(cell_residual_tolerance)
  except (TypeError, ValueError):
    return _audit_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.INVALID_INPUT,
      'entropy-carrying refinement audit tolerances must be numeric',
      result=result,
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('projection_tolerance', projection_limit),
    ('pressure_lineage_tolerance', lineage_limit),
    ('cell_residual_tolerance', residual_limit),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  source_trial = result.source_trial
  if not isinstance(
    source_trial,
    MocEulerAmbientFirstWedgeEntropyCarryResult,
  ):
    return _audit_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.SOURCE_FAILURE,
      'refinement result does not retain its entropy-carrying source trial',
      result=result,
      position_tolerance_m=position_tolerance,
      projection_tolerance=projection_limit,
      pressure_lineage_tolerance=lineage_limit,
      cell_residual_tolerance=residual_limit,
    )
  source_audit = measure_moc_euler_ambient_first_wedge_entropy_carry(
    source_trial,
    position_tolerance_m=position_tolerance,
    characteristic_residual_tolerance=source_trial.characteristic_residual_tolerance,
    edge_alignment_tolerance=source_trial.edge_alignment_tolerance,
    cell_residual_tolerance=source_trial.cell_residual_tolerance,
    pressure_lineage_tolerance=lineage_limit,
  )
  source_trial_gates_verified = bool(
    source_audit.topology_verified
    and source_audit.state_samples_finite
    and source_audit.pressure_lineage_verified
    and source_audit.incoming_characteristic_geometry_verified
    and source_audit.characteristic_geometry_verified
    and source_audit.variable_entropy_compatibility_verified
    and source_audit.axis_streamline_entropy_verified
  )
  if not source_trial_gates_verified:
    return _audit_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.SOURCE_FAILURE,
      'independent source-trial audit did not pass the required entropy and '
      'characteristic gates',
      result=result,
      source_trial_gates_verified=False,
      position_tolerance_m=position_tolerance,
      projection_tolerance=projection_limit,
      pressure_lineage_tolerance=lineage_limit,
      cell_residual_tolerance=residual_limit,
    )
  source_vertices = tuple(
    (float(point[0]), float(point[1]))
    for point in source_trial.vertices_xr_m
  )
  source_states = tuple(source_trial.states)
  source_pressures = tuple(float(value) for value in source_trial.total_pressure_Pa)
  if len(source_vertices) != 3 or len(source_states) != 3 or len(source_pressures) != 3:
    return _audit_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.SOURCE_FAILURE,
      'source trial does not retain exactly three projection vertices',
      result=result,
      source_trial_gates_verified=True,
      position_tolerance_m=position_tolerance,
      projection_tolerance=projection_limit,
      pressure_lineage_tolerance=lineage_limit,
      cell_residual_tolerance=residual_limit,
    )
  raw_topology = validate_moc_mesh(result.cells)
  topology_verified = bool(
    result.cells
    and raw_topology.connected
    and raw_topology.forms_closed_zone
    and raw_topology.nonmanifold_edge_count == 0
  )
  if not topology_verified:
    return _audit_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.TOPOLOGY_FAILURE,
      f'independent projected subcell topology audit failed: {raw_topology.message}',
      result=result,
      source_trial_gates_verified=True,
      topology_verified=False,
      position_tolerance_m=position_tolerance,
      projection_tolerance=projection_limit,
      pressure_lineage_tolerance=lineage_limit,
      cell_residual_tolerance=residual_limit,
    )
  state_samples_finite = True
  state_projection_verified = True
  pressure_lineage_carried = bool(
    abs(source_pressures[2] - source_pressures[0])
    <= lineage_limit * max(1.0, abs(source_pressures[0]), abs(source_pressures[2]))
  )
  recomputed_residuals: list[float] = []
  for cell, sample in zip(result.cells, result.cell_samples, strict=True):
    cell_vertices = tuple(
      (float(point[0]), float(point[1])) for point in cell.vertices_xr_m
    )
    sample_vertices = tuple(
      (float(point[0]), float(point[1])) for point in sample.vertices_xr_m
    )
    if len(cell_vertices) != 3 or cell_vertices != sample_vertices:
      state_samples_finite = False
      state_projection_verified = False
      continue
    if cell.cell_kind != 'post-shock-ambient-terminal-entropy-projection':
      state_projection_verified = False
    for point, state, pressure in zip(
      sample_vertices,
      sample.states,
      sample.total_pressure_Pa,
      strict=True,
    ):
      if not isinstance(state, CharacteristicState) or not all(
        isfinite(value)
        for value in (
          state.x_m,
          state.y_m,
          state.theta_rad,
          state.mach,
          state.gamma,
          float(pressure),
        )
      ) or state.mach <= 1.0 or state.gamma <= 1.0 or float(pressure) <= 0.0:
        state_samples_finite = False
        state_projection_verified = False
        continue
      if hypot(state.x_m - point[0], state.y_m - point[1]) > position_tolerance:
        state_samples_finite = False
        state_projection_verified = False
      expected = _projected_values(
        point,
        source_vertices,
        source_states,
        source_pressures,
        position_tolerance_m=position_tolerance,
      )
      if expected is None:
        state_projection_verified = False
        continue
      expected_theta, expected_nu, expected_pressure = expected
      if (
        abs(state.theta_rad - expected_theta) > projection_limit
        or abs(state.nu_rad - expected_nu) > projection_limit
        or abs(float(pressure) - expected_pressure)
        > projection_limit * max(1.0, abs(expected_pressure), abs(float(pressure)))
      ):
        state_projection_verified = False
      if abs(point[1]) <= position_tolerance and (
        abs(float(pressure) - source_pressures[0])
        > lineage_limit * max(1.0, abs(source_pressures[0]), abs(float(pressure)))
      ):
        pressure_lineage_carried = False
    try:
      recomputed_residuals.append(
        _cell_flux_residual(
          sample_vertices,
          tuple(sample.states),
          tuple(float(value) for value in sample.total_pressure_Pa),
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      state_samples_finite = False
      state_projection_verified = False
  residuals = tuple(recomputed_residuals)
  residuals_finite = bool(
    len(residuals) == len(result.cells)
    and bool(residuals)
    and all(isfinite(value) for value in residuals)
  )
  maximum_residual = max(residuals, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= residual_limit
  )
  if not state_samples_finite:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.STATE_PROJECTION_FAILURE
    expected_status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.STATE_PROJECTION_FAILURE.value
    message = 'independent projected subcell state audit failed'
  elif not state_projection_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.STATE_PROJECTION_FAILURE
    expected_status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.STATE_PROJECTION_FAILURE.value
    message = 'independent barycentric theta/nu/pressure projection audit failed'
  elif not pressure_lineage_carried:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.PRESSURE_LINEAGE_FAILURE
    expected_status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.PRESSURE_LINEAGE_FAILURE.value
    message = 'independent projected axis pressure-lineage audit failed'
  elif not residuals_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.EULER_RESIDUAL_FAILURE
    expected_status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.EULER_RESIDUAL_FAILURE.value
    message = 'independent projected subcell Euler residual audit failed'
  elif (
    result.internal_characteristic_closure_verified
    or result.physical_closure_verified
    or not result.chain_promotion_blocked
    or result.production_claim_allowed
  ):
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.FLAG_FAILURE
    expected_status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.CONVERGED_DIAGNOSTIC_REFINEMENT.value
    message = 'projected refinement returned weakened fidelity flags'
  else:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementAuditStatus.CONVERGED_LOCAL_AUDIT
    expected_status = MocEulerAmbientFirstWedgeEntropyCarryRefinementStatus.CONVERGED_DIAGNOSTIC_REFINEMENT.value
    message = 'independent projected subcell audit passed; internal MOC closure remains blocked'
  solver_status_consistent = result.status.value == expected_status
  if not solver_status_consistent:
    message += (
      f'; solver status {result.status.value!r} does not match independent '
      f'expected status {expected_status!r}'
    )
  return MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit(
    status=status,
    solver_status=result.status.value,
    source_trial_status=source_trial.status.value,
    subdivision_level=result.subdivision_level,
    subdivision_side_count=result.subdivision_side_count,
    cell_count=result.cell_count,
    sampled_cell_count=len(result.cell_samples),
    state_sample_count=result.state_sample_count,
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=maximum_residual,
    source_trial_gates_verified=source_trial_gates_verified,
    topology_verified=topology_verified,
    state_samples_finite=state_samples_finite,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    internal_characteristic_closure_verified=False,
    solver_status_consistent=solver_status_consistent,
    physical_closure_verified=result.physical_closure_verified,
    chain_promotion_blocked=result.chain_promotion_blocked,
    production_claim_allowed=result.production_claim_allowed,
    position_tolerance_m=position_tolerance,
    projection_tolerance=projection_limit,
    pressure_lineage_tolerance=lineage_limit,
    cell_residual_tolerance=residual_limit,
    message=message,
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryRefinementCase:
  """One declared resolution in a projection refinement ladder."""

  subdivision_level: int
  result: MocEulerAmbientFirstWedgeEntropyCarryRefinementResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.subdivision_level, bool)
      or not isinstance(self.subdivision_level, int)
      or self.subdivision_level < 1
    ):
      raise ValueError('subdivision_level must be a positive integer')
    if not isinstance(
      self.result,
      MocEulerAmbientFirstWedgeEntropyCarryRefinementResult,
    ):
      raise TypeError(
        'result must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryRefinementResult'
      )
    if self.result.subdivision_level != self.subdivision_level:
      raise ValueError('case level must match result subdivision_level')


class MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus(str, Enum):
  """Outcome of the independent multi-resolution projection audit."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged_euler_ambient_first_wedge_entropy_carry_refinement_ladder'
  )
  INVALID_INPUT = 'invalid_input'
  LEVEL_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_level_failure'
  )
  PROJECTION_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_projection_failure'
  )
  RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_residual_failure'
  )
  MONOTONICITY_FAILURE = (
    'euler_ambient_first_wedge_entropy_carry_refinement_monotonicity_failure'
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurement:
  """Resolution trend evidence below internal characteristic closure."""

  status: MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus
  cases: tuple[MocEulerAmbientFirstWedgeEntropyCarryRefinementCase, ...]
  audits: tuple[MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit, ...]
  subdivision_levels: tuple[int, ...]
  subdivision_side_counts: tuple[int, ...]
  cell_counts: tuple[int, ...]
  state_sample_counts: tuple[int, ...]
  maximum_cell_euler_residuals: tuple[float, ...]
  levels_verified: bool
  audits_verified: bool
  topology_verified: bool
  state_projection_verified: bool
  pressure_lineage_verified: bool
  cell_euler_residuals_finite: bool
  final_cell_euler_residual_verified: bool
  residual_nonincreasing_verified: bool
  residual_reduction_verified: bool
  internal_characteristic_closure_verified: bool = False
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  refinement_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''
  operator_id: str = (
    MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CARRY_REFINEMENT_AUDIT_OPERATOR_ID
    + '-ladder'
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus'
      )
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    if any(
      not isinstance(case, MocEulerAmbientFirstWedgeEntropyCarryRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed refinement cases')
    if any(
      not isinstance(audit, MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit)
      for audit in audits
    ):
      raise TypeError('audits must contain typed refinement audits')
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    for name in (
      'subdivision_levels',
      'subdivision_side_counts',
      'cell_counts',
      'state_sample_counts',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
      ):
        raise ValueError(f'{name} must contain nonnegative integers')
      object.__setattr__(self, name, values)
    residuals = tuple(float(value) for value in self.maximum_cell_euler_residuals)
    if len(residuals) != len(cases):
      raise ValueError('maximum_cell_euler_residuals must match the case count')
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'maximum_cell_euler_residuals must contain finite nonnegative values'
      )
    object.__setattr__(self, 'maximum_cell_euler_residuals', residuals)
    for name in (
      'levels_verified',
      'audits_verified',
      'topology_verified',
      'state_projection_verified',
      'pressure_lineage_verified',
      'cell_euler_residuals_finite',
      'final_cell_euler_residual_verified',
      'residual_nonincreasing_verified',
      'residual_reduction_verified',
      'internal_characteristic_closure_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.internal_characteristic_closure_verified:
      raise ValueError('a projection ladder cannot claim internal MOC closure')
    if self.physical_closure_verified:
      raise ValueError('a projection ladder cannot claim physical closure')
    if self.production_claim_allowed:
      raise ValueError('a projection ladder cannot claim production validity')
    for name in ('refinement_tolerance', 'cell_residual_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.levels_verified
      and self.audits_verified
      and self.topology_verified
      and self.state_projection_verified
      and self.pressure_lineage_verified
      and self.cell_euler_residuals_finite
      and self.final_cell_euler_residual_verified
      and self.residual_nonincreasing_verified
      and self.residual_reduction_verified
      and not self.internal_characteristic_closure_verified
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
      'subdivision_levels': list(self.subdivision_levels),
      'subdivision_side_counts': list(self.subdivision_side_counts),
      'cell_counts': list(self.cell_counts),
      'state_sample_counts': list(self.state_sample_counts),
      'maximum_cell_euler_residuals': list(self.maximum_cell_euler_residuals),
      'audits': [audit.as_report() for audit in self.audits],
      'checks': {
        'levels_verified': self.levels_verified,
        'audits_verified': self.audits_verified,
        'topology_verified': self.topology_verified,
        'state_projection_verified': self.state_projection_verified,
        'pressure_lineage_verified': self.pressure_lineage_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'final_cell_euler_residual_verified': self.final_cell_euler_residual_verified,
        'residual_nonincreasing_verified': self.residual_nonincreasing_verified,
        'residual_reduction_verified': self.residual_reduction_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'refinement_tolerance': self.refinement_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'canonical_reflected_free_boundary_verified': False,
      'external_validation_verified': False,
      'claim_status': (
        'independent-entropy-carrying-resolution-ladder; projected residual '
        'reduction is not internal characteristic closure or chain promotion'
      ),
      'message': self.message,
    }


def _measurement_failure(
  status: MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[MocEulerAmbientFirstWedgeEntropyCarryRefinementCase] = (),
  audits: Sequence[MocEulerAmbientFirstWedgeEntropyCarryRefinementAudit] = (),
  refinement_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurement:
  case_values = tuple(cases)
  audit_values = tuple(audits)
  paired_count = min(len(case_values), len(audit_values))
  case_values = case_values[:paired_count]
  audit_values = audit_values[:paired_count]
  return MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurement(
    status=status,
    cases=case_values,
    audits=audit_values,
    subdivision_levels=tuple(case.subdivision_level for case in case_values),
    subdivision_side_counts=tuple(
      audit.subdivision_side_count for audit in audit_values
    ),
    cell_counts=tuple(audit.cell_count for audit in audit_values),
    state_sample_counts=tuple(
      audit.state_sample_count for audit in audit_values
    ),
    maximum_cell_euler_residuals=tuple(
      audit.maximum_cell_euler_residual or 0.0 for audit in audit_values
    ),
    levels_verified=False,
    audits_verified=False,
    topology_verified=False,
    state_projection_verified=False,
    pressure_lineage_verified=False,
    cell_euler_residuals_finite=False,
    final_cell_euler_residual_verified=False,
    residual_nonincreasing_verified=False,
    residual_reduction_verified=False,
    refinement_tolerance=refinement_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_entropy_carry_refinement_ladder(
  cases: Sequence[MocEulerAmbientFirstWedgeEntropyCarryRefinementCase],
  *,
  expected_subdivision_levels: Sequence[int] | None = None,
  position_tolerance_m: float = 1.0e-10,
  projection_tolerance: float = 1.0e-9,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  refinement_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurement:
  """Audit a multi-resolution entropy-carrying projection ladder."""

  try:
    items = tuple(cases)
  except TypeError:
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must be iterable',
      refinement_tolerance=refinement_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  if len(items) < 2:
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.INVALID_INPUT,
      'at least two entropy-carrying refinement cases are required',
      refinement_tolerance=refinement_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  if any(
    not isinstance(case, MocEulerAmbientFirstWedgeEntropyCarryRefinementCase)
    for case in items
  ):
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.INVALID_INPUT,
      'refinement cases must contain typed entropy-carrying cases',
      refinement_tolerance=refinement_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  audits = tuple(
    measure_moc_euler_ambient_first_wedge_entropy_carry_refinement(
      case.result,
      position_tolerance_m=position_tolerance_m,
      projection_tolerance=projection_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
    for case in items
  )
  levels = tuple(case.subdivision_level for case in items)
  side_counts = tuple(audit.subdivision_side_count for audit in audits)
  cell_counts = tuple(audit.cell_count for audit in audits)
  sample_counts = tuple(audit.state_sample_count for audit in audits)
  maximums = tuple(
    audit.maximum_cell_euler_residual or 0.0 for audit in audits
  )
  if expected_subdivision_levels is not None:
    expected_levels = tuple(expected_subdivision_levels)
    levels_verified = levels == expected_levels
  else:
    levels_verified = all(
      left < right for left, right in zip(levels, levels[1:])
    )
  levels_verified = bool(
    levels_verified
    and all(
      right == 2 * left
      for left, right in zip(side_counts, side_counts[1:])
    )
    and all(
      right > left for left, right in zip(cell_counts, cell_counts[1:])
    )
  )
  audits_verified = bool(
    all(audit.solver_status_consistent for audit in audits)
    and all(audit.source_trial_gates_verified for audit in audits)
  )
  topology_verified = all(audit.topology_verified for audit in audits)
  state_projection_verified = all(
    audit.state_samples_finite and audit.state_projection_verified
    for audit in audits
  )
  pressure_lineage_verified = all(
    audit.pressure_lineage_carried for audit in audits
  )
  residuals_finite = all(
    audit.cell_euler_residuals_finite for audit in audits
  )
  final_residual_verified = bool(audits[-1].cell_euler_residuals_verified)
  residual_nonincreasing = bool(
    all(
      right <= left + refinement_tolerance * max(1.0, abs(left))
      for left, right in zip(maximums, maximums[1:])
    )
  )
  residual_reduction = bool(maximums[-1] < maximums[0])
  if not levels_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.LEVEL_FAILURE
    message = 'entropy-carrying refinement levels or lattice growth are inconsistent'
  elif not audits_verified or not topology_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.LEVEL_FAILURE
    message = 'one or more independent entropy-carrying subcell audits failed'
  elif not state_projection_verified or not pressure_lineage_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.PROJECTION_FAILURE
    message = 'entropy-carrying state projection or pressure lineage failed'
  elif not residuals_finite or not final_residual_verified:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.RESIDUAL_FAILURE
    message = 'the final entropy-carrying subcell resolution did not pass its Euler residual gate'
  elif not residual_nonincreasing or not residual_reduction:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.MONOTONICITY_FAILURE
    message = 'entropy-carrying residuals did not decrease monotonically with refinement'
  else:
    status = MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurementStatus.CONVERGED_LOCAL_REFINEMENT
    message = (
      'independent entropy-carrying projection ladder passed topology, '
      'lineage, residual, and reduction gates; internal characteristic closure '
      'and chain promotion remain blocked'
    )
  return MocEulerAmbientFirstWedgeEntropyCarryRefinementMeasurement(
    status=status,
    cases=items,
    audits=audits,
    subdivision_levels=levels,
    subdivision_side_counts=side_counts,
    cell_counts=cell_counts,
    state_sample_counts=sample_counts,
    maximum_cell_euler_residuals=maximums,
    levels_verified=levels_verified,
    audits_verified=audits_verified,
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    cell_euler_residuals_finite=residuals_finite,
    final_cell_euler_residual_verified=final_residual_verified,
    residual_nonincreasing_verified=residual_nonincreasing,
    residual_reduction_verified=residual_reduction,
    refinement_tolerance=refinement_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
