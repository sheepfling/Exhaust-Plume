"""Independent audit for the continued-band local-closure chain.

The planner records provenance, but this operator recomputes the underlying
continuation, remesh, and reflected/free-boundary audits and then checks every
inter-stage link.  It intentionally reports local closure evidence separately
from physical shock-cell-chain promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.chain import MocChainTerminationReason
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_closure import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_remesh_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_CLOSURE_CHAIN_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_CLOSURE_CHAIN_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-'
  'closure-chain-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent multi-stage closure-chain audit."""

  CONVERGED_LOCAL_AUDIT = (
    'converged_local_entropy_characteristic_continuation_closure_chain_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'entropy_characteristic_continuation_closure_chain_seed_failure'
  STEP_FAILURE = 'entropy_characteristic_continuation_closure_chain_step_failure'
  LINK_FAILURE = 'entropy_characteristic_continuation_closure_chain_link_failure'
  REMESH_FAILURE = 'entropy_characteristic_continuation_closure_chain_remesh_failure'
  CLOSURE_FAILURE = 'entropy_characteristic_continuation_closure_chain_closure_failure'
  TERMINATION_FAILURE = 'entropy_characteristic_continuation_closure_chain_termination_failure'
  FLAG_FAILURE = 'entropy_characteristic_continuation_closure_chain_flag_failure'
####


def _source_kind(source: Any) -> str:
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult):
    return 'internal-entropy-characteristic-field'
  ####
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult):
    return 'variable-entropy-characteristic-continuation'
  ####
  return type(source).__name__
####


def _handoff_fingerprint(boundary: Any) -> str | None:
  try:
    values = tuple(boundary)
  except TypeError:
    return None
  ####
  if not values:
    return None
  ####
  try:
    payload = '\n'.join(
      '|'.join(
        value.hex()
        for value in (
          sample.state.x_m,
          sample.state.y_m,
          sample.state.theta_rad,
          sample.state.mach,
          sample.state.gamma,
          sample.total_pressure_Pa,
        )
      )
      for sample in values
    )
  except (AttributeError, TypeError, ValueError):
    return None
  ####
  return sha256(payload.encode('ascii')).hexdigest()
####


def _state_payload(state: CharacteristicState) -> str:
  return '|'.join(
    value.hex()
    for value in (
      state.x_m,
      state.y_m,
      state.theta_rad,
      state.mach,
      state.gamma,
    )
  )
####


def _field_fingerprint(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
) -> str:
  payload = [
    f'status:{field.status.value}',
    f'boundary-kind:{field.continuation_boundary_kind.value}',
    f'boundary-indices:{field.continuation_boundary_node_indices!r}',
  ]
  payload.extend(
    f'node:{node.node_index}|{node.point_m[0].hex()}|'
    f'{node.point_m[1].hex()}|{_state_payload(node.state)}|'
    f'{node.total_pressure_Pa.hex()}'
    for node in field.nodes
  )
  payload.append('cells')
  payload.extend(
    f'{cell.cell_index}|{cell.cell_kind}|' + '|'.join(
      value.hex() for point in cell.vertices_xr_m for value in point
    )
    for cell in field.cells
  )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()
####


def _continuation_fingerprint(
  continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
) -> str:
  return sha256(repr(continuation.as_report()).encode('utf-8')).hexdigest()
####


def _source_fingerprint(source: Any) -> str | None:
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult):
    return _field_fingerprint(source)
  ####
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult):
    return _continuation_fingerprint(source)
  ####
  return None
####


def _closure_fingerprint(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult,
) -> str:
  payload = [
    f'status:{result.status.value}',
    f'source-kind:{result.source_kind}',
    f'incoming:{_handoff_fingerprint(result.incoming_handoff)}',
    f'continuation:{None if result.continuation is None else _continuation_fingerprint(result.continuation)}',
    f'remesh-status:{None if result.remesh is None else result.remesh.status.value}',
    f'remesh-source-link:{result.remesh_source_link_verified}',
    f'remesh-residual:{None if result.remesh is None else result.remesh.maximum_cell_euler_residual}',
    f'closure-status:{None if result.closure is None else result.closure.status.value}',
    f'closure-remesh-link:{result.closure_remesh_link_verified}',
    f'closure-shock-count:{None if result.closure is None else result.closure.shock_sample_count}',
  ]
  return sha256('\n'.join(payload).encode('utf-8')).hexdigest()
####


def _source_extent(source: Any) -> tuple[float, float] | None:
  values: list[float] = []
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult):
    points = tuple(node.point_m for node in source.nodes)
  elif isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult):
    points = tuple(
      point
      for cell in source.cells
      for point in cell.vertices_xr_m
    )
    points += tuple(
      (state.x_m, state.y_m)
      for state in (
        *source.centerline_states,
        *source.outer_states,
        *(() if source.terminal_centerline_state is None else (source.terminal_centerline_state,)),
      )
    )
  else:
    return None
  ####
  for point in points:
    try:
      value = float(point[0])
    except (IndexError, TypeError, ValueError):
      return None
    ####
    if not isfinite(value):
      return None
    ####
    values.append(value)
  ####
  return None if not values else (min(values), max(values))
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit:
  """Independent evidence for a sequence of local closure candidates."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus
  operator_id: str
  planner_resolved: bool
  seed_field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None
  continuation_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit, ...
  ]
  remesh_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit, ...
  ]
  closure_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit, ...
  ]
  accepted_closure_count: int
  step_count: int
  incoming_handoff_links_verified: bool
  source_links_verified: bool
  gradient_links_verified: bool
  fresh_domains_verified: bool
  remesh_links_verified: bool
  closure_links_verified: bool
  local_closure_gates_verified: bool
  step_records_verified: bool
  termination_verified: bool
  planner_resolved_consistent: bool
  physical_chain_cell_count: int
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  external_validation_required: bool
  fidelity_flags_verified: bool
  message: str
  diagnostics: dict[str, Any] | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus,
    ):
      raise TypeError('status must be a closure-chain audit status')
    ####
    if not isinstance(self.operator_id, str) or not self.operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    for name, expected_type in (
      ('seed_field_audit', (MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit, type(None))),
    ):
      if not isinstance(getattr(self, name), expected_type):
        raise TypeError(f'{name} must have its typed audit or None')
      ####
    ####
    for name, item_type in (
      ('continuation_audits', MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit),
      ('remesh_audits', MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit),
      ('closure_audits', MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit),
    ):
      values = tuple(getattr(self, name))
      if any(not isinstance(value, item_type) for value in values):
        raise TypeError(f'{name} must contain typed audits')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in (
      'planner_resolved',
      'incoming_handoff_links_verified',
      'source_links_verified',
      'gradient_links_verified',
      'fresh_domains_verified',
      'remesh_links_verified',
      'closure_links_verified',
      'local_closure_gates_verified',
      'step_records_verified',
      'termination_verified',
      'planner_resolved_consistent',
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
    if self.physical_chain_cell_count < 0:
      raise ValueError('physical_chain_cell_count must be nonnegative')
    ####
    if self.physical_closure_verified:
      raise ValueError('closure-chain audit cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('closure-chain audit must retain the promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError('closure-chain audit cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
    object.__setattr__(self, 'diagnostics', {} if self.diagnostics is None else dict(self.diagnostics))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus
      .CONVERGED_LOCAL_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.seed_field_audit is not None
      and self.seed_field_audit.local_consistency_verified
      and all(audit.local_consistency_verified for audit in self.continuation_audits)
      and all(audit.local_consistency_verified for audit in self.remesh_audits)
      and all(audit.local_consistency_verified for audit in self.closure_audits)
      and self.incoming_handoff_links_verified
      and self.source_links_verified
      and self.gradient_links_verified
      and self.fresh_domains_verified
      and self.remesh_links_verified
      and self.closure_links_verified
      and self.local_closure_gates_verified
      and self.step_records_verified
      and self.termination_verified
      and self.planner_resolved_consistent
      and self.fidelity_flags_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def local_physical_closure_count(self) -> int:
    return sum(audit.reflected_free_boundary_verified for audit in self.closure_audits)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'planner_resolved': self.planner_resolved,
      'planner_resolved_consistent': self.planner_resolved_consistent,
      'accepted_closure_count': self.accepted_closure_count,
      'step_count': self.step_count,
      'local_physical_closure_count': self.local_physical_closure_count,
      'incoming_handoff_links_verified': self.incoming_handoff_links_verified,
      'source_links_verified': self.source_links_verified,
      'gradient_links_verified': self.gradient_links_verified,
      'fresh_domains_verified': self.fresh_domains_verified,
      'remesh_links_verified': self.remesh_links_verified,
      'closure_links_verified': self.closure_links_verified,
      'local_closure_gates_verified': self.local_closure_gates_verified,
      'step_records_verified': self.step_records_verified,
      'termination_verified': self.termination_verified,
      'physical_chain_cell_count': self.physical_chain_cell_count,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'seed_field_audit': None if self.seed_field_audit is None else self.seed_field_audit.as_report(),
      'continuation_audits': [audit.as_report() for audit in self.continuation_audits],
      'remesh_audits': [audit.as_report() for audit in self.remesh_audits],
      'closure_audits': [audit.as_report() for audit in self.closure_audits],
      'diagnostics': dict(self.diagnostics or {}),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus,
  message: str,
  *,
  planner_resolved: bool = False,
  seed_field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None = None,
  continuation_audits: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit, ...] = (),
  remesh_audits: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit, ...] = (),
  closure_audits: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit, ...] = (),
  accepted_closure_count: int = 0,
  step_count: int = 0,
  incoming_handoff_links_verified: bool = False,
  source_links_verified: bool = False,
  gradient_links_verified: bool = False,
  fresh_domains_verified: bool = False,
  remesh_links_verified: bool = False,
  closure_links_verified: bool = False,
  local_closure_gates_verified: bool = False,
  step_records_verified: bool = False,
  termination_verified: bool = False,
  planner_resolved_consistent: bool = False,
  fidelity_flags_verified: bool = False,
  diagnostics: dict[str, Any] | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_CLOSURE_CHAIN_AUDIT_OPERATOR_ID
    ),
    planner_resolved=planner_resolved,
    seed_field_audit=seed_field_audit,
    continuation_audits=continuation_audits,
    remesh_audits=remesh_audits,
    closure_audits=closure_audits,
    accepted_closure_count=accepted_closure_count,
    step_count=step_count,
    incoming_handoff_links_verified=incoming_handoff_links_verified,
    source_links_verified=source_links_verified,
    gradient_links_verified=gradient_links_verified,
    fresh_domains_verified=fresh_domains_verified,
    remesh_links_verified=remesh_links_verified,
    closure_links_verified=closure_links_verified,
    local_closure_gates_verified=local_closure_gates_verified,
    step_records_verified=step_records_verified,
    termination_verified=termination_verified,
    planner_resolved_consistent=planner_resolved_consistent,
    physical_chain_cell_count=0,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    fidelity_flags_verified=fidelity_flags_verified,
    message=message,
    diagnostics=diagnostics,
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain(
  result: Any,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit:
  """Recompute every retained stage and exact inter-stage provenance link."""

  from exhaust_plume.models.moc.planner import (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
  )

  status_type = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAuditStatus
  )
  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
  ):
    return _failure(status_type.INVALID_INPUT, 'result must be a typed closure-chain planner result')
  ####
  tolerances = (
    float(position_tolerance_m),
    float(state_tolerance),
    float(characteristic_residual_tolerance),
    float(pressure_lineage_tolerance),
    float(cell_residual_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('closure-chain audit tolerances must be finite and positive')
  ####

  try:
    seed_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
      result.seed,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(status_type.SEED_FAILURE, f'independent seed audit raised: {error}', step_count=len(result.steps))
  ####
  if not seed_audit.local_consistency_verified:
    return _failure(
      status_type.SEED_FAILURE,
      'seed field failed its independent local audit',
      seed_field_audit=seed_audit,
      accepted_closure_count=len(result.closures),
      step_count=len(result.steps),
    )
  ####

  continuation_audits: list[MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit] = []
  remesh_audits: list[MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshAudit] = []
  closure_audits: list[MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryAudit] = []
  current: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ) = result.seed
  incoming_links_verified = True
  source_links_verified = True
  gradient_links_verified = True
  fresh_domains_verified = True
  remesh_links_verified = True
  closure_links_verified = True
  local_closure_gates_verified = True

  for candidate in result.closures:
    continuation = candidate.continuation
    remesh = candidate.remesh
    closure = candidate.closure
    if continuation is None or remesh is None or closure is None:
      return _failure(
        status_type.STEP_FAILURE,
        'accepted closure candidate did not retain all continuation stages',
        seed_field_audit=seed_audit,
        continuation_audits=tuple(continuation_audits),
        remesh_audits=tuple(remesh_audits),
        closure_audits=tuple(closure_audits),
        accepted_closure_count=len(result.closures),
        step_count=len(result.steps),
      )
    ####
    try:
      continuation_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
        continuation,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
        characteristic_residual_tolerance=characteristic_residual_tolerance,
        pressure_lineage_tolerance=pressure_lineage_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
      )
      remesh_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_remesh(
        remesh,
        position_tolerance_m=position_tolerance_m,
        characteristic_residual_tolerance=remesh.characteristic_residual_tolerance,
        pressure_lineage_tolerance=remesh.pressure_lineage_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
      )
      closure_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary(
        closure,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
        shock_residual_tolerance=characteristic_residual_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        status_type.STEP_FAILURE,
        f'independent closure-stage audit raised: {error}',
        seed_field_audit=seed_audit,
        continuation_audits=tuple(continuation_audits),
        remesh_audits=tuple(remesh_audits),
        closure_audits=tuple(closure_audits),
        accepted_closure_count=len(result.closures),
        step_count=len(result.steps),
      )
    ####
    continuation_audits.append(continuation_audit)
    remesh_audits.append(remesh_audit)
    closure_audits.append(closure_audit)
    incoming_links_verified = bool(
      incoming_links_verified
      and candidate.incoming_handoff == current.continuation_boundary
      and continuation.incoming_handoff == current.continuation_boundary
    )
    source_links_verified = bool(
      source_links_verified and continuation.source_field is current
    )
    gradient_links_verified = bool(
      gradient_links_verified
      and current.source_pressure_gradient is not None
      and continuation.source_pressure_gradient == current.source_pressure_gradient
    )
    current_extent = _source_extent(current)
    next_extent = _source_extent(continuation)
    fresh_domains_verified = bool(
      fresh_domains_verified
      and current_extent is not None
      and next_extent is not None
      and next_extent[0] >= current_extent[1] - position_tolerance_m
      and next_extent[1] > current_extent[1] + position_tolerance_m
    )
    remesh_links_verified = bool(
      remesh_links_verified
      and remesh.source_continuation is continuation
    )
    closure_links_verified = bool(
      closure_links_verified and closure.remesh is remesh
    )
    local_closure_gates_verified = bool(
      local_closure_gates_verified
      and continuation_audit.local_consistency_verified
      and remesh_audit.local_consistency_verified
      and remesh_audit.cell_euler_residuals_verified
      and closure_audit.local_consistency_verified
      and candidate.local_closure_verified
      and candidate.source_euler_gate_verified
    )
    current = continuation
  ####

  accepted_steps = tuple(
    step for step in result.steps
    if (
      step.result_kind == 'closure-solve-returned'
      and step.result_local_closure_verified is True
    )
  )
  step_records_verified = bool(
    len(accepted_steps) == len(result.closures)
    and all(
      step.next_closure_index == index + 1
      and step.current_result_kind == _source_kind(
        result.seed if index == 0 else result.closures[index - 1].continuation
      )
      and step.current_result_fingerprint == _source_fingerprint(
        result.seed if index == 0 else result.closures[index - 1].continuation
      )
      and step.incoming_handoff_sample_count == len(
        (
          result.seed
          if index == 0
          else result.closures[index - 1].continuation
        ).continuation_boundary
      )
      and step.incoming_handoff_fingerprint == _handoff_fingerprint(
        (
          result.seed
          if index == 0
          else result.closures[index - 1].continuation
        ).continuation_boundary
      )
      and step.incoming_handoff_link_verified
      and step.result_kind == 'closure-solve-returned'
      and step.result_source_kind == _source_kind(
        result.seed if index == 0 else result.closures[index - 1].continuation
      )
      and step.result_fingerprint == _closure_fingerprint(candidate)
      and step.result_source_link_verified is True
      and step.result_gradient_link_verified is True
      and step.result_fresh_domain_verified is True
      and step.result_continuation_incoming_handoff_verified is True
      and step.result_remesh_source_link_verified is True
      and step.result_closure_remesh_link_verified is True
      and step.result_continuation_local_consistency_verified is True
      and step.result_remesh_local_consistency_verified is True
      and step.result_source_cell_euler_residuals_verified is True
      and step.result_reflected_free_boundary_verified is True
      and step.result_local_closure_verified is True
      for index, (step, candidate) in enumerate(
        zip(accepted_steps, result.closures, strict=True)
      )
    )
  )
  final_steps = tuple(
    step for step in result.steps
    if step.result_source_link_verified is None
  )
  termination_verified = bool(
    len(final_steps) == 1
    and final_steps[0].next_closure_index == len(result.closures) + 1
    and final_steps[0].current_result_kind == _source_kind(current)
    and final_steps[0].current_result_fingerprint == _source_fingerprint(current)
    and final_steps[0].incoming_handoff_sample_count == len(current.continuation_boundary)
    and final_steps[0].incoming_handoff_fingerprint == _handoff_fingerprint(current.continuation_boundary)
    and final_steps[0].incoming_handoff_link_verified
    and final_steps[0].result_kind in (
      'termination-returned',
      'closure-rejected',
      'limit-reached-with-result',
    )
    and final_steps[0].result_termination_reason is result.termination.reason
    and final_steps[0].result_physical_termination is result.termination.physical_termination
    and not result.termination.physical_termination
  )
  expected_resolved = bool(
    seed_audit.local_consistency_verified
    and len(continuation_audits) == len(result.closures)
    and len(remesh_audits) == len(result.closures)
    and len(closure_audits) == len(result.closures)
    and all(audit.local_consistency_verified for audit in continuation_audits)
    and all(audit.local_consistency_verified for audit in remesh_audits)
    and all(audit.local_consistency_verified for audit in closure_audits)
    and incoming_links_verified
    and source_links_verified
    and gradient_links_verified
    and fresh_domains_verified
    and remesh_links_verified
    and closure_links_verified
    and local_closure_gates_verified
    and step_records_verified
    and termination_verified
    and result.termination.reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  planner_resolved_consistent = result.resolved == expected_resolved
  fidelity_flags_verified = bool(
    result.physical_chain_cell_count == 0
    and not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.external_validation_required
    and not result.termination.physical_termination
    and all(
      not candidate.physical_closure_verified
      and candidate.chain_promotion_blocked
      and not candidate.production_claim_allowed
      and candidate.external_validation_required
      and candidate.closure is not None
      and candidate.closure.chain_promotion_blocked
      and not candidate.closure.production_claim_allowed
      for candidate in result.closures
    )
  )
  common = dict(
    planner_resolved=result.resolved,
    seed_field_audit=seed_audit,
    continuation_audits=tuple(continuation_audits),
    remesh_audits=tuple(remesh_audits),
    closure_audits=tuple(closure_audits),
    accepted_closure_count=len(result.closures),
    step_count=len(result.steps),
    incoming_handoff_links_verified=incoming_links_verified,
    source_links_verified=source_links_verified,
    gradient_links_verified=gradient_links_verified,
    fresh_domains_verified=fresh_domains_verified,
    remesh_links_verified=remesh_links_verified,
    closure_links_verified=closure_links_verified,
    local_closure_gates_verified=local_closure_gates_verified,
    step_records_verified=step_records_verified,
    termination_verified=termination_verified,
    planner_resolved_consistent=planner_resolved_consistent,
    fidelity_flags_verified=fidelity_flags_verified,
  )
  if not fidelity_flags_verified:
    return _failure(
      status_type.FLAG_FAILURE,
      'closure-chain weakened its explicit non-promotion boundary',
      **common,
    )
  ####
  if expected_resolved and planner_resolved_consistent:
    return _failure(
      status_type.CONVERGED_LOCAL_AUDIT,
      'independent audit confirmed the continued local reflected-closure sequence; global intercell reconciliation and external validation remain required',
      **common,
    )
  ####
  if not (
    incoming_links_verified
    and source_links_verified
    and gradient_links_verified
    and remesh_links_verified
    and closure_links_verified
  ):
    audit_status = status_type.LINK_FAILURE
  elif not local_closure_gates_verified:
    audit_status = status_type.CLOSURE_FAILURE
  elif not termination_verified or not planner_resolved_consistent:
    audit_status = status_type.TERMINATION_FAILURE
  elif not step_records_verified:
    audit_status = status_type.STEP_FAILURE
  else:
    audit_status = status_type.STEP_FAILURE
  ####
  return _failure(
    audit_status,
    'closure-chain did not pass the independent sequence gates',
    **common,
  )
####
