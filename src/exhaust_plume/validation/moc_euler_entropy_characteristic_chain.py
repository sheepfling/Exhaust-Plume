"""Independent audit for the entropy-characteristic field chain boundary.

The model-side planner records a sequence of locally closed internal fields
and exact ``POST_SHOCK_FIELD_PERIMETER`` handoffs.  This operator re-audits
each field with the independent internal-field operator, reconstructs the
handoff fingerprints, checks fresh downstream domains, and verifies that the
planner never promoted an open field to a physical ``MocChainCell``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainTerminationReason,
  MocChainBoundarySample,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.planner import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_field,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_CHAIN_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_field_chain',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_CHAIN_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-field-chain-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent open-field sequence audit."""

  CONVERGED_LOCAL_CHAIN_AUDIT = (
    'converged_euler_ambient_first_wedge_entropy_characteristic_field_chain_audit'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_chain_field_failure'
  )
  HANDOFF_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_chain_handoff_failure'
  )
  DOMAIN_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_chain_domain_failure'
  )
  TERMINATION_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_chain_termination_failure'
  )
  FLAG_FAILURE = (
    'euler_ambient_first_wedge_entropy_characteristic_field_chain_flag_failure'
  )
####


def _handoff_fingerprint(
  boundary: tuple[MocChainBoundarySample, ...],
) -> str | None:
  """Reconstruct the exact state/pressure handoff digest independently."""

  if not boundary:
    return None
  ####
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
    for sample in boundary
  )
  return sha256(payload.encode('ascii')).hexdigest()
####


def _field_fingerprint(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
) -> str:
  """Reconstruct a deterministic raw identity without planner metadata."""

  payload = [
    f'status:{field.status.value}',
    f'boundary-kind:{field.continuation_boundary_kind.value}',
    f'boundary-indices:{field.continuation_boundary_node_indices!r}',
  ]
  for node in field.nodes:
    state = node.state
    payload.append(
      f'node:{node.node_index}|{node.point_m[0].hex()}|'
      f'{node.point_m[1].hex()}|{state.x_m.hex()}|{state.y_m.hex()}|'
      f'{state.theta_rad.hex()}|{state.mach.hex()}|{state.gamma.hex()}|'
      f'{node.total_pressure_Pa.hex()}'
    )
  ####
  payload.append('cells')
  payload.extend(
    f'{cell.cell_index}|{cell.cell_kind}|' + '|'.join(
      value.hex() for point in cell.vertices_xr_m for value in point
    )
    for cell in field.cells
  )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()
####


def _field_x_extent(
  field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
) -> tuple[float, float] | None:
  points = tuple(node.point_m for node in field.nodes)
  if not points:
    return None
  ####
  values = tuple(float(point[0]) for point in points)
  if not all(isfinite(value) for value in values):
    return None
  ####
  return min(values), max(values)
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit:
  """Independent result for one field retained in a chain sequence."""

  field_index: int
  field_fingerprint: str
  audit: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit

  def __post_init__(self) -> None:
    if (
      isinstance(self.field_index, bool)
      or not isinstance(self.field_index, int)
      or self.field_index < 1
    ):
      raise ValueError('field_index must be a positive integer')
    ####
    if not isinstance(self.field_fingerprint, str) or not self.field_fingerprint:
      raise ValueError('field_fingerprint must be a non-empty string')
    ####
    if not isinstance(
      self.audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit,
    ):
      raise TypeError(
        'audit must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldAudit'
      )
    ####
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return self.audit.local_consistency_verified
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'field_index': self.field_index,
      'field_fingerprint': self.field_fingerprint,
      'local_consistency_verified': self.local_consistency_verified,
      'audit': self.audit.as_report(),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAudit:
  """Independent gates for a typed open entropy-field sequence."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus
  operator_id: str
  planner_kind: str
  field_count: int
  continued_field_count: int
  field_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit, ...
  ]
  handoff_links_verified: bool
  fresh_domains_verified: bool
  termination_verified: bool
  planner_resolved_consistent: bool
  physical_chain_cell_count: int
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  termination_reason: MocChainTerminationReason | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus'
      )
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be a non-empty string')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    planner_kind = str(self.planner_kind)
    if not planner_kind:
      raise ValueError('planner_kind must be a non-empty string')
    ####
    object.__setattr__(self, 'planner_kind', planner_kind)
    for name in ('field_count', 'continued_field_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.continued_field_count > self.field_count:
      raise ValueError('continued_field_count cannot exceed field_count')
    ####
    audits = tuple(self.field_audits)
    if len(audits) != self.field_count:
      raise ValueError('field_audits must align with field_count')
    ####
    if any(
      not isinstance(
        value,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit,
      )
      for value in audits
    ):
      raise TypeError(
        'field_audits must contain '
        'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit values'
      )
    ####
    object.__setattr__(self, 'field_audits', audits)
    if isinstance(self.physical_chain_cell_count, bool) or not isinstance(
      self.physical_chain_cell_count,
      int,
    ) or self.physical_chain_cell_count < 0:
      raise ValueError('physical_chain_cell_count must be a nonnegative integer')
    ####
    if self.termination_reason is not None and not isinstance(
      self.termination_reason,
      MocChainTerminationReason,
    ):
      raise TypeError(
        'termination_reason must be a MocChainTerminationReason or None'
      )
    ####
    for name in (
      'handoff_links_verified',
      'fresh_domains_verified',
      'termination_verified',
      'planner_resolved_consistent',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('a field-chain audit cannot claim physical closure')
    ####
    if self.physical_chain_cell_count != 0:
      raise ValueError('an open field-chain audit cannot contain physical cells')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('an open field-chain audit must block promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('an open field-chain audit cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus
      .CONVERGED_LOCAL_CHAIN_AUDIT
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.field_audits
      and all(value.local_consistency_verified for value in self.field_audits)
      and self.handoff_links_verified
      and self.fresh_domains_verified
      and self.termination_verified
      and self.planner_resolved_consistent
      and self.physical_chain_cell_count == 0
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'planner_kind': self.planner_kind,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'field_count': self.field_count,
      'continued_field_count': self.continued_field_count,
      'field_audits': [value.as_report() for value in self.field_audits],
      'checks': {
        'handoff_links_verified': self.handoff_links_verified,
        'fresh_domains_verified': self.fresh_domains_verified,
        'termination_verified': self.termination_verified,
        'planner_resolved_consistent': self.planner_resolved_consistent,
        'physical_chain_cell_count': self.physical_chain_cell_count,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
      'termination_reason': (
        None
        if self.termination_reason is None
        else self.termination_reason.value
      ),
      'claim_status': (
        'independent-open-entropy-characteristic-field-chain-audit; '
        'reflected free-boundary and physical shock-cell closure remain pending'
      ),
      'message': self.message,
    }
  ####
####


def _make_audit(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus,
  planner: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult,
  field_audits: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit, ...
  ],
  *,
  handoff_links_verified: bool = False,
  fresh_domains_verified: bool = False,
  termination_verified: bool = False,
  planner_resolved_consistent: bool = False,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FIELD_CHAIN_AUDIT_OPERATOR_ID
    ),
    planner_kind=planner.planner_kind.value,
    field_count=planner.field_count,
    continued_field_count=planner.continued_field_count,
    field_audits=field_audits,
    handoff_links_verified=handoff_links_verified,
    fresh_domains_verified=fresh_domains_verified,
    termination_verified=termination_verified,
    planner_resolved_consistent=planner_resolved_consistent,
    physical_chain_cell_count=planner.physical_chain_cell_count,
    physical_closure_verified=planner.physical_closure_verified,
    chain_promotion_blocked=planner.chain_promotion_blocked,
    production_claim_allowed=planner.production_claim_allowed,
    termination_reason=planner.termination.reason,
    message=message,
  )
####


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_field_chain(
  planner: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult,
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAudit:
  """Recompute field, handoff, domain, and termination gates independently."""

  if not isinstance(
    planner,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult,
  ):
    raise TypeError(
      'planner must be a '
      'MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainPlannerResult'
    )
  ####
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####

  field_audits: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit
  ] = []
  for field_index, field in enumerate(planner.fields, start=1):
    if not isinstance(
      field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      return _make_audit(
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.FIELD_FAILURE,
        planner,
        tuple(field_audits),
        message=f'field {field_index} has an invalid result type',
      )
    ####
    field_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_field(
      field,
      position_tolerance_m=position_tolerance_m,
    )
    field_audits.append(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainFieldAudit(
        field_index=field_index,
        field_fingerprint=_field_fingerprint(field),
        audit=field_audit,
      )
    )
  ####
  field_audits_tuple = tuple(field_audits)
  if not field_audits_tuple or not all(
    value.local_consistency_verified for value in field_audits_tuple
  ):
    return _make_audit(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.FIELD_FAILURE,
      planner,
      field_audits_tuple,
      message='one or more retained fields failed its independent local audit',
    )
  ####

  handoff_links_verified = True
  fresh_domains_verified = True
  expected_step_indices = tuple(range(2, len(planner.steps) + 2))
  if tuple(step.next_field_index for step in planner.steps) != expected_step_indices:
    handoff_links_verified = False
  ####
  for step in planner.steps:
    current_index = step.next_field_index - 2
    if current_index < 0 or current_index >= len(planner.fields):
      handoff_links_verified = False
      continue
    ####
    current = planner.fields[current_index]
    incoming = current.continuation_boundary
    handoff_links_verified = handoff_links_verified and bool(
      step.incoming_handoff_link_verified
      and step.incoming_handoff_sample_count == len(incoming)
      and step.incoming_handoff_fingerprint == _handoff_fingerprint(incoming)
    )
    if step.result_kind == 'field-solve-returned':
      next_index = current_index + 1
      if next_index >= len(planner.fields):
        handoff_links_verified = False
        continue
      ####
      next_field = planner.fields[next_index]
      outgoing = next_field.continuation_boundary
      handoff_links_verified = handoff_links_verified and bool(
        step.result_field_fingerprint == _field_fingerprint(next_field)
        and step.result_continuation_boundary_sample_count == len(outgoing)
        and step.result_continuation_boundary_verified
        and step.result_handoff_fingerprint == _handoff_fingerprint(outgoing)
      )
      current_extent = _field_x_extent(current)
      next_extent = _field_x_extent(next_field)
      fresh_domains_verified = fresh_domains_verified and bool(
        current_extent is not None
        and next_extent is not None
        and next_extent[0] > current_extent[1] + tolerance
      )
    elif step.result_kind not in {
      'termination-returned',
    }:
      handoff_links_verified = False
    ####
  ####
  if planner.continued_field_count == 0:
    fresh_domains_verified = True
  ####
  if not handoff_links_verified:
    return _make_audit(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.HANDOFF_FAILURE,
      planner,
      field_audits_tuple,
      handoff_links_verified=False,
      fresh_domains_verified=fresh_domains_verified,
      message='planner steps do not retain the exact field perimeter links',
    )
  ####
  if not fresh_domains_verified:
    return _make_audit(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.DOMAIN_FAILURE,
      planner,
      field_audits_tuple,
      handoff_links_verified=True,
      fresh_domains_verified=False,
      message='one or more accepted fields overlap or backtrack in x',
    )
  ####

  termination_verified = bool(
    not planner.termination.physical_termination
    and planner.termination.reason
    in {
      MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
      MocChainTerminationReason.MAX_CELL_LIMIT,
    }
    and bool(planner.steps)
    and planner.steps[-1].result_termination_reason == planner.termination.reason
  )
  expected_resolved = bool(
    planner.termination.reason
    is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
  )
  planner_resolved_consistent = bool(planner.resolved == expected_resolved)
  if not termination_verified:
    return _make_audit(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.TERMINATION_FAILURE,
      planner,
      field_audits_tuple,
      handoff_links_verified=True,
      fresh_domains_verified=True,
      termination_verified=False,
      planner_resolved_consistent=planner_resolved_consistent,
      message='planner termination is not a verified non-physical sequence stop',
    )
  ####
  if not planner_resolved_consistent or planner.physical_chain_cell_count != 0:
    return _make_audit(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.FLAG_FAILURE,
      planner,
      field_audits_tuple,
      handoff_links_verified=True,
      fresh_domains_verified=True,
      termination_verified=True,
      planner_resolved_consistent=planner_resolved_consistent,
      message='planner resolved/physical fidelity flags disagree with raw gates',
    )
  ####
  return _make_audit(
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldChainAuditStatus.CONVERGED_LOCAL_CHAIN_AUDIT,
    planner,
    field_audits_tuple,
    handoff_links_verified=True,
    fresh_domains_verified=True,
    termination_verified=True,
    planner_resolved_consistent=True,
    message=(
      'independent entropy-characteristic field-chain audit passed; '
      'physical reflected/free-boundary closure remains blocked'
    ),
  )
####
