"""Independent audit for continuation-band projection refinement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import exp, isfinite, log
from typing import Any, Iterator, Sequence

from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_refinement import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus,
)
from exhaust_plume.models.moc.euler_first_wedge_remesh import (
  MocEulerAmbientFirstWedgeCellSample,
)
from exhaust_plume.models.moc.primitives import (
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
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurement',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_ladder',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-refinement-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent continuation-refinement audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FAILURE = 'entropy_characteristic_continuation_refinement_source_failure'
  TOPOLOGY_FAILURE = 'entropy_characteristic_continuation_refinement_topology_failure'
  STATE_PROJECTION_FAILURE = (
    'entropy_characteristic_continuation_refinement_state_projection_failure'
  )
  EULER_RESIDUAL_FAILURE = (
    'entropy_characteristic_continuation_refinement_euler_residual_failure'
  )
  STATUS_FAILURE = 'entropy_characteristic_continuation_refinement_status_failure'
  FLAG_FAILURE = 'entropy_characteristic_continuation_refinement_flag_failure'
####


def _triangle_projected_values(
  parent: MocEulerAmbientFirstWedgeCellSample,
  side_count: int,
  first_index: int,
  second_index: int,
) -> tuple[tuple[float, float], CharacteristicState, float]:
  vertices = tuple(parent.vertices_xr_m)
  states = tuple(parent.states)
  pressures = tuple(float(value) for value in parent.total_pressure_Pa)
  first_weight = first_index / side_count
  second_weight = second_index / side_count
  weights = (
    1.0 - first_weight - second_weight,
    first_weight,
    second_weight,
  )
  point = tuple(
    sum(weights[index] * vertices[index][coordinate] for index in range(3))
    for coordinate in (0, 1)
  )
  theta = sum(
    weights[index] * states[index].theta_rad for index in range(3)
  )
  nu = sum(weights[index] * states[index].nu_rad for index in range(3))
  inversion = inverse_prandtl_meyer_angle_rad(nu, states[0].gamma)
  if not inversion.converged or inversion.value is None:
    raise ValueError('independent refinement projection left the Mach domain')
  ####
  state = CharacteristicState(
    x_m=point[0],
    y_m=point[1],
    theta_rad=theta,
    mach=inversion.value,
    gamma=states[0].gamma,
  )
  pressure = exp(
    sum(weights[index] * log(pressures[index]) for index in range(3))
  )
  return point, state, pressure
####


def _expected_subcell_values(
  parents: tuple[MocEulerAmbientFirstWedgeCellSample, ...],
  side_count: int,
) -> Iterator[tuple[tuple[float, float], CharacteristicState, float]]:
  for parent in parents:
    for first_index in range(side_count):
      for second_index in range(side_count - first_index):
        for keys in (
          (
            (first_index, second_index),
            (first_index + 1, second_index),
            (first_index, second_index + 1),
          ),
        ):
          for key in keys:
            yield _triangle_projected_values(
              parent,
              side_count,
              key[0],
              key[1],
            )
          ####
        ####
        if first_index + second_index <= side_count - 2:
          keys = (
            (first_index + 1, second_index),
            (first_index + 1, second_index + 1),
            (first_index, second_index + 1),
          )
          for key in keys:
            yield _triangle_projected_values(
              parent,
              side_count,
              key[0],
              key[1],
            )
          ####
        ####
      ####
    ####
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit:
  """Independent evidence for one refined continuation-band resolution."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
  operator_id: str
  solver_status: str | None
  source_continuation_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit | None
  subdivision_side_count: int
  cell_count: int
  sampled_cell_count: int
  state_sample_count: int
  cell_euler_residuals: tuple[float, ...]
  maximum_cell_euler_residual: float | None
  source_continuation_gates_verified: bool
  topology_verified: bool
  state_projection_verified: bool
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
  position_tolerance_m: float = 1.0e-8
  projection_tolerance: float = 1.0e-9
  cell_residual_tolerance: float = 1.0e-2
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus,
    ):
      raise TypeError('status must be a refinement audit status')
    ####
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
    if not isinstance(self.topology, MocTopologyResult):
      raise TypeError('topology must be a MocTopologyResult')
    ####
    for name in (
      'source_continuation_gates_verified',
      'topology_verified',
      'state_projection_verified',
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
      raise ValueError('refinement audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('refinement audit must retain the promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError('refinement audit cannot claim production validity')
    ####
    for name in (
      'position_tolerance_m',
      'projection_tolerance',
      'cell_residual_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
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
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.structural_consistency_verified
      and self.cell_euler_residuals_verified
    )
  ####

  @property
  def structural_consistency_verified(self) -> bool:
    """Return the gates that do not require the final residual threshold."""

    return bool(
      self.source_continuation_gates_verified
      and self.topology_verified
      and self.state_projection_verified
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
      'cell_euler_residuals': list(self.cell_euler_residuals),
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'checks': {
        'source_continuation_gates_verified': self.source_continuation_gates_verified,
        'topology_verified': self.topology_verified,
        'state_projection_verified': self.state_projection_verified,
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
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus,
  message: str,
  *,
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult | None = None,
  source_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit | None = None,
  topology: MocTopologyResult | None = None,
  residuals: tuple[float, ...] = (),
  state_projection_verified: bool = False,
  pressure_lineage_carried: bool = False,
  continuation_boundary_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  status_consistent: bool = False,
  fidelity_flags_verified: bool = False,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REFINEMENT_AUDIT_OPERATOR_ID
    ),
    solver_status=None if result is None else result.status.value,
    source_continuation_audit=source_audit,
    subdivision_side_count=1 if result is None else result.subdivision_side_count,
    cell_count=0 if result is None else len(result.cells),
    sampled_cell_count=0 if result is None else len(result.cell_samples),
    state_sample_count=0 if result is None else result.state_sample_count,
    cell_euler_residuals=residuals,
    maximum_cell_euler_residual=max(residuals, default=None),
    source_continuation_gates_verified=source_audit is not None and source_audit.local_consistency_verified,
    topology_verified=False if topology is None else topology.forms_closed_zone,
    state_projection_verified=state_projection_verified,
    pressure_lineage_carried=pressure_lineage_carried,
    continuation_boundary_verified=continuation_boundary_verified,
    cell_euler_residuals_finite=residuals_finite,
    cell_euler_residuals_verified=residuals_verified,
    solver_status_consistent=status_consistent,
    physical_closure_verified=False,
    chain_promotion_blocked=True if result is None else result.chain_promotion_blocked,
    production_claim_allowed=False if result is None else result.production_claim_allowed,
    external_validation_required=True,
    fidelity_flags_verified=fidelity_flags_verified,
    topology=validate_moc_mesh(()) if topology is None else topology,
    message=message,
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult,
  *,
  position_tolerance_m: float = 1.0e-8,
  projection_tolerance: float = 1.0e-9,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit:
  """Recompute projection, topology, lineage, and Euler residual evidence."""

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .INVALID_INPUT,
      'result must be a typed continuation-refinement result',
    )
  ####
  tolerances = (
    float(position_tolerance_m),
    float(projection_tolerance),
    float(cell_residual_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('refinement audit tolerances must be finite and positive')
  ####
  source = result.source_continuation
  if source is None:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .SOURCE_FAILURE,
      'refinement did not retain its source continuation',
      result=result,
    )
  ####
  try:
    source_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
      source,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=projection_tolerance,
      pressure_lineage_tolerance=projection_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .SOURCE_FAILURE,
      f'independent source continuation audit raised: {error}',
      result=result,
    )
  ####
  if not source_audit.local_consistency_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .SOURCE_FAILURE,
      'source continuation failed its independent audit',
      result=result,
      source_audit=source_audit,
    )
  ####
  topology = validate_moc_mesh(result.cells)
  topology_verified = bool(
    result.cells
    and topology.forms_closed_zone
    and topology.nonmanifold_edge_count == 0
    and topology.status is result.topology.status
    and topology.cell_count == result.topology.cell_count
    and topology.edge_count == result.topology.edge_count
  )
  if not topology_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .TOPOLOGY_FAILURE,
      'independent continuation-refinement topology audit failed',
      result=result,
      source_audit=source_audit,
      topology=topology,
      continuation_boundary_verified=result.continuation_boundary_verified,
    )
  ####
  state_projection_verified = True
  pressure_lineage_carried = True
  expected_values = _expected_subcell_values(
    tuple(source.cell_samples),
    result.subdivision_side_count,
  )
  expected_count = result.cell_count * 3
  actual_count = 0
  try:
    for sample in result.cell_samples:
      if not isinstance(sample, MocEulerAmbientFirstWedgeCellSample):
        state_projection_verified = False
        break
      ####
      for point, state, pressure in zip(
        sample.vertices_xr_m,
        sample.states,
        sample.total_pressure_Pa,
        strict=True,
      ):
        actual_count += 1
        expected_point, expected_state, expected_pressure = next(expected_values)
        if (
          any(
            abs(point[index] - expected_point[index]) > position_tolerance_m
            for index in (0, 1)
          )
          or not isinstance(state, CharacteristicState)
          or abs(state.theta_rad - expected_state.theta_rad) > projection_tolerance
          or abs(state.nu_rad - expected_state.nu_rad) > projection_tolerance
          or abs(state.mach - expected_state.mach) > projection_tolerance
          or abs(state.gamma - expected_state.gamma) > projection_tolerance
          or abs(log(float(pressure) / expected_pressure)) > projection_tolerance
        ):
          state_projection_verified = False
        ####
        if not isfinite(float(pressure)) or float(pressure) <= 0.0:
          pressure_lineage_carried = False
        ####
      ####
    ####
    if actual_count != expected_count:
      state_projection_verified = False
    ####
    try:
      next(expected_values)
      state_projection_verified = False
    except StopIteration:
      pass
    ####
  except (ArithmeticError, FloatingPointError, StopIteration, TypeError, ValueError):
    state_projection_verified = False
  ####
  if not result.continuation_boundary_verified or not source.continuation_boundary_verified:
    continuation_boundary_verified = False
  else:
    continuation_boundary_verified = bool(
      result.continuation_boundary == source.continuation_boundary
    )
  ####
  residuals: list[float] = []
  try:
    for cell, sample in zip(result.cells, result.cell_samples, strict=True):
      if tuple(cell.vertices_xr_m) != tuple(sample.vertices_xr_m):
        state_projection_verified = False
      ####
      residuals.append(
        _cell_flux_residual(
          tuple(sample.vertices_xr_m),
          tuple(sample.states),
          tuple(float(value) for value in sample.total_pressure_Pa),
        )
      )
    ####
  except (ArithmeticError, FloatingPointError, TypeError, ValueError):
    residuals = []
  ####
  residuals_tuple = tuple(residuals)
  residuals_finite = bool(
    len(residuals_tuple) == result.cell_count
    and bool(residuals_tuple)
    and all(isfinite(value) and value >= 0.0 for value in residuals_tuple)
  )
  maximum_residual = max(residuals_tuple, default=None)
  residuals_verified = bool(
    residuals_finite
    and maximum_residual is not None
    and maximum_residual <= cell_residual_tolerance
  )
  flags_verified = bool(
    not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
  )
  expected_status = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
    .CONVERGED_DIAGNOSTIC_REFINEMENT.value
    if state_projection_verified
    and pressure_lineage_carried
    and continuation_boundary_verified
    and topology_verified
    and residuals_finite
    and residuals_verified
    else MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
    .EULER_RESIDUAL_FAILURE.value
  )
  if not state_projection_verified or not pressure_lineage_carried:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .STATE_PROJECTION_FAILURE.value
    )
  elif not topology_verified:
    expected_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementStatus
      .TOPOLOGY_FAILURE.value
    )
  ####
  solver_status_consistent = result.status.value == expected_status
  if not flags_verified:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .FLAG_FAILURE
    )
  elif not state_projection_verified or not pressure_lineage_carried:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .STATE_PROJECTION_FAILURE
    )
  elif not topology_verified:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .TOPOLOGY_FAILURE
    )
  elif not residuals_verified:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .EULER_RESIDUAL_FAILURE
    )
  elif not solver_status_consistent:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .STATUS_FAILURE
    )
  else:
    audit_status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
  ####
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit(
    status=audit_status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REFINEMENT_AUDIT_OPERATOR_ID
    ),
    solver_status=result.status.value,
    source_continuation_audit=source_audit,
    subdivision_side_count=result.subdivision_side_count,
    cell_count=result.cell_count,
    sampled_cell_count=len(result.cell_samples),
    state_sample_count=result.state_sample_count,
    cell_euler_residuals=residuals_tuple,
    maximum_cell_euler_residual=maximum_residual,
    source_continuation_gates_verified=True,
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
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
    position_tolerance_m=position_tolerance_m,
    projection_tolerance=projection_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=(
      'independent continuation projection audit passed; characteristic '
      're-closure and physical shock-cell promotion remain blocked'
      if audit_status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAuditStatus
      .CONVERGED_LOCAL_AUDIT
      else 'independent continuation projection audit failed one or more gates'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase:
  """One declared barycentric resolution in a continuation-band ladder."""

  subdivision_side_count: int
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult

  def __post_init__(self) -> None:
    if (
      isinstance(self.subdivision_side_count, bool)
      or not isinstance(self.subdivision_side_count, int)
      or self.subdivision_side_count < 1
    ):
      raise ValueError('subdivision_side_count must be a positive integer')
    ####
    if not isinstance(
      self.result,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult,
    ):
      raise TypeError(
        'result must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementResult'
      )
    ####
    if self.result.subdivision_side_count != self.subdivision_side_count:
      raise ValueError(
        'case side count must match result subdivision_side_count'
      )
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'subdivision_side_count': self.subdivision_side_count,
      'result_status': self.result.status.value,
      'result_converged': self.result.converged,
      'result_cell_count': self.result.cell_count,
      'result_maximum_cell_euler_residual': (
        self.result.maximum_cell_euler_residual
      ),
    }
  ####
####


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus(
  str,
  Enum,
):
  """Outcome of the independent continuation-refinement ladder audit."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_ladder'
  )
  INVALID_INPUT = 'invalid_input'
  LEVEL_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_level_failure'
  )
  PROJECTION_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_projection_failure'
  )
  RESIDUAL_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_residual_failure'
  )
  MONOTONICITY_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_monotonicity_failure'
  )
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurement:
  """Resolution trend evidence below characteristic and physical closure."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
  cases: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase,
    ...,
  ]
  audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit,
    ...,
  ]
  subdivision_side_counts: tuple[int, ...]
  cell_counts: tuple[int, ...]
  state_sample_counts: tuple[int, ...]
  maximum_cell_euler_residuals: tuple[float, ...]
  levels_verified: bool
  audits_verified: bool
  topology_verified: bool
  state_projection_verified: bool
  pressure_lineage_verified: bool
  continuation_boundary_verified: bool
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
    MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_REFINEMENT_AUDIT_OPERATOR_ID
    + '-ladder'
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus,
    ):
      raise TypeError(
        'status must be a continuation-refinement measurement status'
      )
    ####
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(
        case,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed continuation-refinement cases')
    ####
    if any(
      not isinstance(
        audit,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit,
      )
      for audit in audits
    ):
      raise TypeError('audits must contain typed continuation-refinement audits')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    for name in (
      'subdivision_side_counts',
      'cell_counts',
      'state_sample_counts',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      ####
      if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in values
      ):
        raise ValueError(f'{name} must contain nonnegative integers')
      ####
      object.__setattr__(self, name, values)
    ####
    residuals = tuple(float(value) for value in self.maximum_cell_euler_residuals)
    if len(residuals) != len(cases):
      raise ValueError('maximum_cell_euler_residuals must match the case count')
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'maximum_cell_euler_residuals must contain finite nonnegative values'
      )
    ####
    object.__setattr__(self, 'maximum_cell_euler_residuals', residuals)
    for name in (
      'levels_verified',
      'audits_verified',
      'topology_verified',
      'state_projection_verified',
      'pressure_lineage_verified',
      'continuation_boundary_verified',
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
      ####
    ####
    if self.internal_characteristic_closure_verified:
      raise ValueError(
        'a continuation projection ladder cannot claim characteristic closure'
      )
    ####
    if self.physical_closure_verified:
      raise ValueError(
        'a continuation projection ladder cannot claim physical closure'
      )
    ####
    if not self.chain_promotion_blocked:
      raise ValueError(
        'a continuation projection ladder must retain the promotion block'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError(
        'a continuation projection ladder cannot claim production validity'
      )
    ####
    for name in ('refinement_tolerance', 'cell_residual_tolerance'):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
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
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.levels_verified
      and self.audits_verified
      and self.topology_verified
      and self.state_projection_verified
      and self.pressure_lineage_verified
      and self.continuation_boundary_verified
      and self.cell_euler_residuals_finite
      and self.final_cell_euler_residual_verified
      and self.residual_nonincreasing_verified
      and self.residual_reduction_verified
      and not self.internal_characteristic_closure_verified
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
      'cases': [case.as_report() for case in self.cases],
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
        'continuation_boundary_verified': self.continuation_boundary_verified,
        'cell_euler_residuals_finite': self.cell_euler_residuals_finite,
        'final_cell_euler_residual_verified': (
          self.final_cell_euler_residual_verified
        ),
        'residual_nonincreasing_verified': (
          self.residual_nonincreasing_verified
        ),
        'residual_reduction_verified': self.residual_reduction_verified,
        'internal_characteristic_closure_verified': False,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'refinement_tolerance': self.refinement_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'external_validation_verified': False,
      'claim_status': (
        'independent-continuation-band-projection-refinement-ladder; '
        'residual reduction is not solver-owned characteristic remeshing, '
        'physical closure, or chain promotion'
      ),
      'message': self.message,
    }
  ####
####


def _measurement_failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus,
  message: str,
  *,
  cases: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase
  ] = (),
  audits: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementAudit
  ] = (),
  refinement_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurement:
  case_values = tuple(cases)
  audit_values = tuple(audits)
  paired_count = min(len(case_values), len(audit_values))
  case_values = case_values[:paired_count]
  audit_values = audit_values[:paired_count]
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurement(
    status=status,
    cases=case_values,
    audits=audit_values,
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
    continuation_boundary_verified=False,
    cell_euler_residuals_finite=False,
    final_cell_euler_residual_verified=False,
    residual_nonincreasing_verified=False,
    residual_reduction_verified=False,
    refinement_tolerance=refinement_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement_ladder(
  cases: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase
  ],
  *,
  expected_subdivision_side_counts: Sequence[int] | None = None,
  position_tolerance_m: float = 1.0e-8,
  projection_tolerance: float = 1.0e-9,
  cell_residual_tolerance: float = 1.0e-2,
  refinement_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurement:
  """Audit a multi-resolution continuation-band projection ladder."""

  try:
    items = tuple(cases)
  except TypeError:
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .INVALID_INPUT,
      'continuation-refinement cases must be iterable',
      refinement_tolerance=refinement_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  ####
  if len(items) < 2:
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .INVALID_INPUT,
      'at least two continuation-refinement cases are required',
      refinement_tolerance=refinement_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  ####
  if any(
    not isinstance(
      case,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementCase,
    )
    for case in items
  ):
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .INVALID_INPUT,
      'cases must contain typed continuation-refinement cases',
      refinement_tolerance=refinement_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
  ####
  tolerances = (
    float(position_tolerance_m),
    float(projection_tolerance),
    float(cell_residual_tolerance),
    float(refinement_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('continuation-refinement ladder tolerances must be positive')
  ####
  audits = tuple(
    measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_refinement(
      case.result,
      position_tolerance_m=position_tolerance_m,
      projection_tolerance=projection_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
    )
    for case in items
  )
  side_counts = tuple(audit.subdivision_side_count for audit in audits)
  cell_counts = tuple(audit.cell_count for audit in audits)
  sample_counts = tuple(audit.state_sample_count for audit in audits)
  maximums = tuple(
    audit.maximum_cell_euler_residual or 0.0 for audit in audits
  )
  if expected_subdivision_side_counts is not None:
    expected = tuple(expected_subdivision_side_counts)
    levels_verified = side_counts == expected
  else:
    levels_verified = all(
      left < right for left, right in zip(side_counts, side_counts[1:])
    )
  ####
  levels_verified = bool(
    levels_verified
    and all(
      right > left for left, right in zip(cell_counts, cell_counts[1:])
    )
    and all(
      case.result.cell_count
      == (
        0
        if case.result.source_continuation is None
        else len(case.result.source_continuation.cell_samples)
      )
      * case.subdivision_side_count
      * case.subdivision_side_count
      for case in items
    )
  )
  audits_verified = all(
    audit.structural_consistency_verified for audit in audits
  )
  topology_verified = all(audit.topology_verified for audit in audits)
  state_projection_verified = all(
    audit.state_projection_verified for audit in audits
  )
  pressure_lineage_verified = all(
    audit.pressure_lineage_carried for audit in audits
  )
  continuation_boundary_verified = all(
    audit.continuation_boundary_verified for audit in audits
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
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .LEVEL_FAILURE
    )
    message = 'continuation-refinement resolutions or cell growth are inconsistent'
  elif not audits_verified or not topology_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .PROJECTION_FAILURE
    )
    message = 'one or more independent continuation-refinement structural audits failed'
  elif not state_projection_verified or not pressure_lineage_verified or not continuation_boundary_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .PROJECTION_FAILURE
    )
    message = 'continuation-refinement state, pressure, or boundary lineage failed'
  elif not residuals_finite or not final_residual_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .RESIDUAL_FAILURE
    )
    message = 'the final continuation-refinement resolution did not pass its Euler residual gate'
  elif not residual_nonincreasing or not residual_reduction:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .MONOTONICITY_FAILURE
    )
    message = 'continuation-refinement residuals did not decrease monotonically'
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )
    message = (
      'independent continuation-refinement ladder passed structural, lineage, '
      'residual, and reduction gates; characteristic re-closure and physical '
      'shock-cell promotion remain blocked'
    )
  ####
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRefinementMeasurement(
    status=status,
    cases=items,
    audits=audits,
    subdivision_side_counts=side_counts,
    cell_counts=cell_counts,
    state_sample_counts=sample_counts,
    maximum_cell_euler_residuals=maximums,
    levels_verified=levels_verified,
    audits_verified=audits_verified,
    topology_verified=topology_verified,
    state_projection_verified=state_projection_verified,
    pressure_lineage_verified=pressure_lineage_verified,
    continuation_boundary_verified=continuation_boundary_verified,
    cell_euler_residuals_finite=residuals_finite,
    final_cell_euler_residual_verified=final_residual_verified,
    residual_nonincreasing_verified=residual_nonincreasing,
    residual_reduction_verified=residual_reduction,
    refinement_tolerance=refinement_tolerance,
    cell_residual_tolerance=cell_residual_tolerance,
    message=message,
  )
####
