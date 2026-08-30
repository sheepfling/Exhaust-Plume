"""Independent audit for the bounded variable-entropy continuation chain.

The planner chain records a sequence of solver-owned alternating source bands.
This operator rechecks each band, its exact source identity, the carried
state/total-pressure frontier, variable-entropy gradient lineage, and fresh
downstream domain from the returned objects.  It deliberately reports zero
physical shock cells: a source-band sequence is evidence for the next
reflected/free-boundary implementation, not a substitute for that solve.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_CHAIN_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_chain',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_CHAIN_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-continuation-chain-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent multi-band continuation audit."""

  CONVERGED_LOCAL_CONTINUATION_CHAIN_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_continuation_chain_audit'
  )
  INVALID_INPUT = 'invalid_input'
  SEED_FAILURE = 'entropy_characteristic_continuation_chain_seed_failure'
  STEP_FAILURE = 'entropy_characteristic_continuation_chain_step_failure'
  HANDOFF_FAILURE = 'entropy_characteristic_continuation_chain_handoff_failure'
  FRESH_DOMAIN_FAILURE = (
    'entropy_characteristic_continuation_chain_fresh_domain_failure'
  )
  TERMINATION_FAILURE = (
    'entropy_characteristic_continuation_chain_termination_failure'
  )
  FLAG_FAILURE = 'entropy_characteristic_continuation_chain_flag_failure'


def _handoff_fingerprint(handoff: tuple[Any, ...]) -> str | None:
  if not handoff:
    return None
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
      for sample in handoff
    )
  except (AttributeError, TypeError, ValueError):
    return None
  return sha256(payload.encode('ascii')).hexdigest()


def _source_extent(
  source: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ),
) -> tuple[float, float] | None:
  values: list[float] = []
  if isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    points = tuple(node.point_m for node in source.nodes)
    values.extend(float(point[0]) for point in points)
  elif isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
    for cell in source.cells:
      values.extend(float(point[0]) for point in cell.vertices_xr_m)
    values.extend(float(state.x_m) for state in source.centerline_states)
    values.extend(float(state.x_m) for state in source.outer_states)
    if source.terminal_centerline_state is not None:
      values.append(float(source.terminal_centerline_state.x_m))
  else:
    return None
  if not values or not all(isfinite(value) for value in values):
    return None
  return min(values), max(values)


def _source_kind(
  source: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ),
) -> str:
  if isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    return 'internal-entropy-characteristic-field'
  return 'variable-entropy-characteristic-continuation'


def _source_fingerprint(
  source: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ),
) -> str:
  if isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    def state_payload(state: Any) -> str:
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

    payload = [
      f'status:{source.status.value}',
      f'boundary-kind:{source.continuation_boundary_kind.value}',
      f'boundary-indices:{source.continuation_boundary_node_indices!r}',
    ]
    payload.extend(
      f'node:{node.node_index}|{node.point_m[0].hex()}|'
      f'{node.point_m[1].hex()}|{state_payload(node.state)}|'
      f'{node.total_pressure_Pa.hex()}'
      for node in source.nodes
    )
    payload.append('cells')
    payload.extend(
      f'{cell.cell_index}|{cell.cell_kind}|' + '|'.join(
        value.hex() for point in cell.vertices_xr_m for value in point
      )
      for cell in source.cells
    )
    return sha256('\n'.join(payload).encode('ascii')).hexdigest()
  return sha256(repr(source.as_report()).encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAudit:
  """Independent evidence for a source-band continuation sequence."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
  operator_id: str
  planner_resolved: bool
  seed_field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None
  continuation_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit, ...
  ]
  accepted_continuation_count: int
  step_count: int
  incoming_handoff_links_verified: bool
  source_links_verified: bool
  gradient_links_verified: bool
  fresh_domains_verified: bool
  step_records_verified: bool
  termination_verified: bool
  planner_resolved_consistent: bool
  physical_chain_cell_count: int
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus,
    ):
      raise TypeError('status must be a continuation-chain audit status')
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    object.__setattr__(self, 'operator_id', operator_id)
    if self.seed_field_audit is not None and not isinstance(
      self.seed_field_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
    ):
      raise TypeError('seed_field_audit must be typed or None')
    audits = tuple(self.continuation_audits)
    if any(
      not isinstance(
        audit,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit,
      )
      for audit in audits
    ):
      raise TypeError('continuation_audits must contain typed audits')
    object.__setattr__(self, 'continuation_audits', audits)
    for name in ('accepted_continuation_count', 'step_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.physical_chain_cell_count != 0:
      raise ValueError('continuation-band audit cannot report physical cells')
    for name in (
      'planner_resolved',
      'incoming_handoff_links_verified',
      'source_links_verified',
      'gradient_links_verified',
      'fresh_domains_verified',
      'step_records_verified',
      'termination_verified',
      'planner_resolved_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_closure_verified:
      raise ValueError('continuation-chain audit cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError('continuation-chain audit must retain the promotion block')
    if self.production_claim_allowed:
      raise ValueError('continuation-chain audit cannot claim production validity')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .CONVERGED_LOCAL_CONTINUATION_CHAIN_AUDIT
    )

  @property
  def local_sequence_verified(self) -> bool:
    return bool(
      self.converged
      and self.seed_field_audit is not None
      and self.seed_field_audit.local_consistency_verified
      and all(audit.local_consistency_verified for audit in self.continuation_audits)
      and self.incoming_handoff_links_verified
      and self.source_links_verified
      and self.gradient_links_verified
      and self.fresh_domains_verified
      and self.step_records_verified
      and self.termination_verified
      and self.planner_resolved_consistent
      and self.fidelity_flags_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_sequence_verified': self.local_sequence_verified,
      'planner_resolved': self.planner_resolved,
      'accepted_continuation_count': self.accepted_continuation_count,
      'step_count': self.step_count,
      'incoming_handoff_links_verified': self.incoming_handoff_links_verified,
      'source_links_verified': self.source_links_verified,
      'gradient_links_verified': self.gradient_links_verified,
      'fresh_domains_verified': self.fresh_domains_verified,
      'step_records_verified': self.step_records_verified,
      'termination_verified': self.termination_verified,
      'planner_resolved_consistent': self.planner_resolved_consistent,
      'physical_chain_cell_count': 0,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'seed_field_audit': (
        None
        if self.seed_field_audit is None
        else self.seed_field_audit.as_report()
      ),
      'continuation_audits': [
        audit.as_report() for audit in self.continuation_audits
      ],
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus,
  message: str,
  *,
  planner_resolved: bool = False,
  seed_field_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit | None = None,
  continuation_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit, ...
  ] = (),
  accepted_continuation_count: int = 0,
  step_count: int = 0,
  incoming_handoff_links_verified: bool = False,
  source_links_verified: bool = False,
  gradient_links_verified: bool = False,
  fresh_domains_verified: bool = False,
  step_records_verified: bool = False,
  termination_verified: bool = False,
  planner_resolved_consistent: bool = False,
  fidelity_flags_verified: bool = False,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_CONTINUATION_CHAIN_AUDIT_OPERATOR_ID
    ),
    planner_resolved=planner_resolved,
    seed_field_audit=seed_field_audit,
    continuation_audits=continuation_audits,
    accepted_continuation_count=accepted_continuation_count,
    step_count=step_count,
    incoming_handoff_links_verified=incoming_handoff_links_verified,
    source_links_verified=source_links_verified,
    gradient_links_verified=gradient_links_verified,
    fresh_domains_verified=fresh_domains_verified,
    step_records_verified=step_records_verified,
    termination_verified=termination_verified,
    planner_resolved_consistent=planner_resolved_consistent,
    physical_chain_cell_count=0,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_flags_verified=fidelity_flags_verified,
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_chain(
  result: Any,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAudit:
  """Recompute every accepted band and inter-band link independently."""

  from exhaust_plume.models.moc.planner import (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainPlannerResult,
  )

  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainPlannerResult,
  ):
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .INVALID_INPUT,
      'result must be a typed entropy continuation-chain planner result',
    )
  tolerances = (
    float(position_tolerance_m),
    float(state_tolerance),
    float(characteristic_residual_tolerance),
    float(pressure_lineage_tolerance),
    float(cell_residual_tolerance),
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('continuation-chain audit tolerances must be finite and positive')

  try:
    seed_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
      result.seed,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .SEED_FAILURE,
      f'independent seed-field audit raised: {error}',
      step_count=len(result.steps),
    )
  if not seed_audit.local_consistency_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .SEED_FAILURE,
      'seed field failed its independent local audit',
      seed_field_audit=seed_audit,
      step_count=len(result.steps),
    )

  audits: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationAudit
  ] = []
  current: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
    | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ) = result.seed
  incoming_links_verified = True
  source_links_verified = True
  gradient_links_verified = True
  fresh_domains_verified = True
  for continuation in result.continuations:
    try:
      audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation(
        continuation,
        position_tolerance_m=position_tolerance_m,
        state_tolerance=state_tolerance,
        characteristic_residual_tolerance=characteristic_residual_tolerance,
        pressure_lineage_tolerance=pressure_lineage_tolerance,
        cell_residual_tolerance=cell_residual_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
        .STEP_FAILURE,
        f'independent continuation audit raised: {error}',
        seed_field_audit=seed_audit,
        continuation_audits=tuple(audits),
        accepted_continuation_count=len(result.continuations),
        step_count=len(result.steps),
      )
    audits.append(audit)
    incoming_links_verified = bool(
      incoming_links_verified
      and continuation.incoming_handoff == current.continuation_boundary
    )
    source_links_verified = bool(
      source_links_verified and continuation.source_field is current
    )
    gradient_links_verified = bool(
      gradient_links_verified
      and continuation.source_pressure_gradient is not None
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
    current = continuation

  n = len(result.continuations)
  accepted_steps = tuple(
    step for step in result.steps
    if step.result_source_link_verified is not None
  )
  step_records_verified = bool(
    len(accepted_steps) == n
    and all(
      step.next_continuation_index == index + 2
      and step.current_result_kind == _source_kind(
        result.seed if index == 0 else result.continuations[index - 1]
      )
      and step.current_result_fingerprint == _source_fingerprint(
        result.seed if index == 0 else result.continuations[index - 1]
      )
      and step.incoming_handoff_sample_count == len(
        (
          result.seed
          if index == 0
          else result.continuations[index - 1]
        ).continuation_boundary
      )
      and step.incoming_handoff_fingerprint == _handoff_fingerprint(
        (
          result.seed
          if index == 0
          else result.continuations[index - 1]
        ).continuation_boundary
      )
      and step.incoming_handoff_link_verified
      and step.result_kind == 'continuation-solve-returned'
      and step.result_source_kind == _source_kind(
        result.seed if index == 0 else result.continuations[index - 1]
      )
      and step.result_source_link_verified is True
      and step.result_gradient_link_verified is True
      and step.result_fresh_domain_verified is True
      and step.result_local_consistency_verified is True
      and step.result_fingerprint == _continuation_fingerprint(continuation)
      and step.result_continuation_boundary_kind
      is continuation.continuation_boundary_kind
      and step.result_continuation_boundary_sample_count
      == len(continuation.continuation_boundary)
      and step.result_continuation_boundary_verified
      is continuation.continuation_boundary_verified
      and step.result_handoff_fingerprint == _handoff_fingerprint(
        continuation.continuation_boundary
      )
      for index, (step, continuation) in enumerate(
        zip(accepted_steps, result.continuations, strict=True)
      )
    )
  )
  final_steps = tuple(
    step for step in result.steps
    if step.result_source_link_verified is None
  )
  if result.termination.reason is MocChainTerminationReason.MAX_CELL_LIMIT:
    termination_verified = bool(len(final_steps) == 0 and n > 0)
  else:
    termination_verified = bool(
      len(final_steps) == 1
      and final_steps[0].result_kind == 'termination-returned'
      and final_steps[0].current_result_kind == _source_kind(current)
      and final_steps[0].current_result_fingerprint == _source_fingerprint(current)
      and final_steps[0].incoming_handoff_sample_count
      == len(current.continuation_boundary)
      and final_steps[0].incoming_handoff_fingerprint
      == _handoff_fingerprint(current.continuation_boundary)
      and final_steps[0].incoming_handoff_link_verified
      and final_steps[0].result_termination_reason is result.termination.reason
      and final_steps[0].result_physical_termination
      is result.termination.physical_termination
      and not result.termination.physical_termination
    )
  expected_resolved = bool(
    seed_audit.local_consistency_verified
    and all(audit.local_consistency_verified for audit in audits)
    and incoming_links_verified
    and source_links_verified
    and gradient_links_verified
    and fresh_domains_verified
    and step_records_verified
    and termination_verified
    and result.termination.reason
    is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  planner_resolved_consistent = result.resolved == expected_resolved
  fidelity_flags_verified = bool(
    result.physical_chain_cell_count == 0
    and not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and all(
      not continuation.physical_closure_verified
      and continuation.chain_promotion_blocked
      and not continuation.production_claim_allowed
      for continuation in result.continuations
    )
    and not result.termination.physical_termination
  )
  common = dict(
    planner_resolved=result.resolved,
    seed_field_audit=seed_audit,
    continuation_audits=tuple(audits),
    accepted_continuation_count=n,
    step_count=len(result.steps),
    incoming_handoff_links_verified=incoming_links_verified,
    source_links_verified=source_links_verified,
    gradient_links_verified=gradient_links_verified,
    fresh_domains_verified=fresh_domains_verified,
    step_records_verified=step_records_verified,
    termination_verified=termination_verified,
    planner_resolved_consistent=planner_resolved_consistent,
    fidelity_flags_verified=fidelity_flags_verified,
  )
  if not fidelity_flags_verified:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .FLAG_FAILURE,
      'continuation chain weakened its explicit non-promotion boundary',
      **common,
    )
  if expected_resolved and planner_resolved_consistent:
    return _failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .CONVERGED_LOCAL_CONTINUATION_CHAIN_AUDIT,
      'independent audit confirmed the bounded variable-entropy continuation chain; reflected shock/free-boundary closure remains pending',
      **common,
    )
  if not incoming_links_verified or not source_links_verified or not gradient_links_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .HANDOFF_FAILURE
    )
  elif not fresh_domains_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .FRESH_DOMAIN_FAILURE
    )
  elif not termination_verified or not planner_resolved_consistent:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .TERMINATION_FAILURE
    )
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationChainAuditStatus
      .STEP_FAILURE
    )
  return _failure(
    status,
    'continuation chain did not pass the independent sequence gates',
    **common,
  )


def _continuation_fingerprint(
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
) -> str:
  return sha256(repr(result.as_report()).encode('utf-8')).hexdigest()
