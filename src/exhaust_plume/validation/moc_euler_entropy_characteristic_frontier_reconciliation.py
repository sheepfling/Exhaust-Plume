"""Independent audit and cross-case refinement for global frontiers.

The model-side reconciliation owns the exact remesh-frontier comparison.  This
module deliberately repeats the important measurements from the retained
planner stages, re-extracts every outgoing frontier, and checks the stored
reconciliation record.  It also supplies a small case matrix for changing the
outer-angle bracket while holding the local remesh resolution fixed.

These checks establish repeatable local global-frontier evidence.  They do not
establish pointwise continuity through a band gap or authorize physical
shock-cell-chain promotion.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from math import hypot, isfinite, log
from typing import Any, Sequence

from exhaust_plume.models.moc.chain import MocChainBoundarySample, MocChainTerminationReason
from exhaust_plume.models.moc.euler_entropy_characteristic_frontier import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
  extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_frontier_reconciliation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult,
  MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
)
from exhaust_plume.validation.moc_euler_entropy_characteristic_continuation_closure import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit,
  measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain,
)

__all__ = (
  'MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FRONTIER_RECONCILIATION_AUDIT_OPERATOR_ID',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_frontier_reconciliation',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementMeasurement',
  'measure_moc_euler_ambient_first_wedge_entropy_characteristic_frontier_reconciliation_refinement_ladder',
)


MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FRONTIER_RECONCILIATION_AUDIT_OPERATOR_ID = (
  'op.moc.euler-ambient-first-wedge-entropy-characteristic-frontier-'
  'reconciliation-audit'
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus(
  str,
  Enum,
):
  """Outcome of the independent global-frontier audit."""

  CONVERGED_GLOBAL_AUDIT = (
    'converged_global_entropy_characteristic_frontier_reconciliation_audit'
  )
  INVALID_INPUT = 'invalid_input'
  CHAIN_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_chain_audit_failure'
  )
  FRONTIER_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_frontier_audit_failure'
  )
  ANCHOR_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_anchor_audit_failure'
  )
  SEQUENCE_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_sequence_audit_failure'
  )
  TERMINATION_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_termination_audit_failure'
  )
  FLAG_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_fidelity_flag_audit_failure'
  )


def _sample_residuals(
  actual: MocChainBoundarySample,
  expected: MocChainBoundarySample,
) -> tuple[float, float, float, float, float]:
  return (
    hypot(
      actual.state.x_m - expected.state.x_m,
      actual.state.y_m - expected.state.y_m,
    ),
    abs(actual.state.theta_rad - expected.state.theta_rad),
    abs(actual.state.mach - expected.state.mach),
    abs(actual.state.gamma - expected.state.gamma),
    abs(log(actual.total_pressure_Pa / expected.total_pressure_Pa)),
  )


def _samples_match(
  actual: Sequence[MocChainBoundarySample],
  expected: Sequence[MocChainBoundarySample],
  *,
  position_tolerance_m: float,
  state_tolerance: float,
  pressure_tolerance: float,
) -> bool:
  actual_values = tuple(actual)
  expected_values = tuple(expected)
  if len(actual_values) != len(expected_values):
    return False
  return all(
    residual[0] <= position_tolerance_m
    and residual[1] <= state_tolerance
    and residual[2] <= state_tolerance
    and residual[3] <= state_tolerance
    and residual[4] <= pressure_tolerance
    for residual in (
      _sample_residuals(actual_value, expected_value)
      for actual_value, expected_value in zip(
        actual_values,
        expected_values,
        strict=True,
      )
    )
  )


def _endpoint_residuals(
  actual: Sequence[MocChainBoundarySample],
  expected: Sequence[MocChainBoundarySample],
) -> tuple[
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
  tuple[float, ...],
]:
  actual_values = tuple(actual)
  expected_values = tuple(expected)
  if len(actual_values) < 2 or len(expected_values) != 2:
    return (), (), (), (), ()
  residuals = tuple(
    _sample_residuals(actual_value, expected_value)
    for actual_value, expected_value in zip(
      (actual_values[0], actual_values[-1]),
      expected_values,
      strict=True,
    )
  )
  return tuple(
    tuple(residual[index] for residual in residuals)
    for index in range(5)
  )  # type: ignore[return-value]


def _residuals_within(
  residuals: tuple[
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
  ],
  *,
  position_tolerance_m: float,
  state_tolerance: float,
  pressure_tolerance: float,
) -> bool:
  return bool(
    len(residuals[0]) == 2
    and all(value <= position_tolerance_m for value in residuals[0])
    and all(value <= state_tolerance for values in residuals[1:4] for value in values)
    and all(value <= pressure_tolerance for value in residuals[4])
  )


def _fingerprint(
  frontier: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
) -> str:
  payload = [
    f'status:{frontier.status.value}',
    f'edge-index:{frontier.edge_index}',
    f'family:{None if frontier.family is None else frontier.family.value}',
  ]
  payload.extend(
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
    for sample in frontier.samples
  )
  return sha256('\n'.join(payload).encode('ascii')).hexdigest()


def _arrays_close(
  actual: Sequence[float],
  expected: Sequence[float],
  tolerance: float,
) -> bool:
  return bool(
    len(actual) == len(expected)
    and all(abs(left - right) <= tolerance for left, right in zip(actual, expected, strict=True))
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit:
  """Independent evidence for one global frontier reconciliation result."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus
  operator_id: str
  reconciliation: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult | None
  closure_chain_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit | None
  planner_resolved: bool
  reextracted_frontier_count: int
  reextracted_frontier_fingerprints: tuple[str, ...]
  result_frontier_fingerprints_verified: bool
  frontier_records_verified: bool
  anchor_links_verified: bool
  frontier_order_verified: bool
  source_band_bridges_verified: bool
  seams_verified: bool
  termination_verified: bool
  planner_result_consistent: bool
  fidelity_flags_verified: bool
  maximum_endpoint_position_residual_m: float | None
  maximum_endpoint_flow_angle_residual_rad: float | None
  maximum_endpoint_mach_residual: float | None
  maximum_endpoint_gamma_residual: float | None
  maximum_endpoint_log_pressure_residual: float | None
  minimum_frontier_spacing_m: float | None
  maximum_frontier_spacing_m: float | None
  physical_chain_cell_count: int
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  external_validation_required: bool
  message: str
  diagnostics: dict[str, Any] | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus,
    ):
      raise TypeError('status must be a frontier-reconciliation audit status')
    if not isinstance(self.operator_id, str) or not self.operator_id:
      raise ValueError('operator_id must be a non-empty string')
    if self.reconciliation is not None and not isinstance(
      self.reconciliation,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult,
    ):
      raise TypeError('reconciliation must be typed or None')
    if self.closure_chain_audit is not None and not isinstance(
      self.closure_chain_audit,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit,
    ):
      raise TypeError('closure_chain_audit must be typed or None')
    if (
      isinstance(self.reextracted_frontier_count, bool)
      or not isinstance(self.reextracted_frontier_count, int)
      or self.reextracted_frontier_count < 0
    ):
      raise ValueError('reextracted_frontier_count must be nonnegative')
    fingerprints = tuple(str(value) for value in self.reextracted_frontier_fingerprints)
    if any(not value for value in fingerprints):
      raise ValueError('reextracted_frontier_fingerprints must be non-empty strings')
    object.__setattr__(self, 'reextracted_frontier_fingerprints', fingerprints)
    for name in (
      'planner_resolved',
      'result_frontier_fingerprints_verified',
      'frontier_records_verified',
      'anchor_links_verified',
      'frontier_order_verified',
      'source_band_bridges_verified',
      'seams_verified',
      'termination_verified',
      'planner_result_consistent',
      'fidelity_flags_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_chain_cell_count < 0:
      raise ValueError('physical_chain_cell_count must be nonnegative')
    if self.physical_closure_verified:
      raise ValueError('frontier reconciliation audit cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError('frontier reconciliation audit must retain promotion block')
    if self.production_claim_allowed:
      raise ValueError('frontier reconciliation audit cannot claim production validity')
    for name in (
      'maximum_endpoint_position_residual_m',
      'maximum_endpoint_flow_angle_residual_rad',
      'maximum_endpoint_mach_residual',
      'maximum_endpoint_gamma_residual',
      'maximum_endpoint_log_pressure_residual',
      'minimum_frontier_spacing_m',
      'maximum_frontier_spacing_m',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative or None')
        object.__setattr__(self, name, numeric)
    object.__setattr__(self, 'operator_id', str(self.operator_id))
    object.__setattr__(self, 'message', str(self.message))
    object.__setattr__(self, 'diagnostics', {} if self.diagnostics is None else dict(self.diagnostics))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus
      .CONVERGED_GLOBAL_AUDIT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.closure_chain_audit is not None
      and self.closure_chain_audit.local_consistency_verified
      and self.planner_resolved
      and self.result_frontier_fingerprints_verified
      and self.frontier_records_verified
      and self.anchor_links_verified
      and self.frontier_order_verified
      and self.source_band_bridges_verified
      and self.seams_verified
      and self.termination_verified
      and self.planner_result_consistent
      and self.fidelity_flags_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  @property
  def frontier_count(self) -> int:
    return self.reextracted_frontier_count

  @property
  def seam_count(self) -> int:
    return max(0, self.reextracted_frontier_count - 1)

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'planner_resolved': self.planner_resolved,
      'reextracted_frontier_count': self.reextracted_frontier_count,
      'reextracted_frontier_fingerprints': list(self.reextracted_frontier_fingerprints),
      'result_frontier_fingerprints_verified': self.result_frontier_fingerprints_verified,
      'frontier_records_verified': self.frontier_records_verified,
      'anchor_links_verified': self.anchor_links_verified,
      'frontier_order_verified': self.frontier_order_verified,
      'source_band_bridges_verified': self.source_band_bridges_verified,
      'seams_verified': self.seams_verified,
      'termination_verified': self.termination_verified,
      'planner_result_consistent': self.planner_result_consistent,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'maximum_endpoint_position_residual_m': self.maximum_endpoint_position_residual_m,
      'maximum_endpoint_flow_angle_residual_rad': self.maximum_endpoint_flow_angle_residual_rad,
      'maximum_endpoint_mach_residual': self.maximum_endpoint_mach_residual,
      'maximum_endpoint_gamma_residual': self.maximum_endpoint_gamma_residual,
      'maximum_endpoint_log_pressure_residual': self.maximum_endpoint_log_pressure_residual,
      'minimum_frontier_spacing_m': self.minimum_frontier_spacing_m,
      'maximum_frontier_spacing_m': self.maximum_frontier_spacing_m,
      'physical_chain_cell_count': 0,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': self.external_validation_required,
      'closure_chain_audit': (
        None
        if self.closure_chain_audit is None
        else self.closure_chain_audit.as_report()
      ),
      'diagnostics': dict(self.diagnostics or {}),
      'message': self.message,
    }


def _audit_failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus,
  message: str,
  *,
  reconciliation: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult | None = None,
  closure_chain_audit: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainAudit | None = None,
  planner_resolved: bool = False,
  reextracted_frontier_count: int = 0,
  reextracted_frontier_fingerprints: Sequence[str] = (),
  result_frontier_fingerprints_verified: bool = False,
  frontier_records_verified: bool = False,
  anchor_links_verified: bool = False,
  frontier_order_verified: bool = False,
  source_band_bridges_verified: bool = False,
  seams_verified: bool = False,
  termination_verified: bool = False,
  planner_result_consistent: bool = False,
  fidelity_flags_verified: bool = False,
  maximum_endpoint_position_residual_m: float | None = None,
  maximum_endpoint_flow_angle_residual_rad: float | None = None,
  maximum_endpoint_mach_residual: float | None = None,
  maximum_endpoint_gamma_residual: float | None = None,
  maximum_endpoint_log_pressure_residual: float | None = None,
  minimum_frontier_spacing_m: float | None = None,
  maximum_frontier_spacing_m: float | None = None,
  diagnostics: dict[str, Any] | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit(
    status=status,
    operator_id=(
      MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FRONTIER_RECONCILIATION_AUDIT_OPERATOR_ID
    ),
    reconciliation=reconciliation,
    closure_chain_audit=closure_chain_audit,
    planner_resolved=planner_resolved,
    reextracted_frontier_count=reextracted_frontier_count,
    reextracted_frontier_fingerprints=tuple(reextracted_frontier_fingerprints),
    result_frontier_fingerprints_verified=result_frontier_fingerprints_verified,
    frontier_records_verified=frontier_records_verified,
    anchor_links_verified=anchor_links_verified,
    frontier_order_verified=frontier_order_verified,
    source_band_bridges_verified=source_band_bridges_verified,
    seams_verified=seams_verified,
    termination_verified=termination_verified,
    planner_result_consistent=planner_result_consistent,
    fidelity_flags_verified=fidelity_flags_verified,
    maximum_endpoint_position_residual_m=maximum_endpoint_position_residual_m,
    maximum_endpoint_flow_angle_residual_rad=maximum_endpoint_flow_angle_residual_rad,
    maximum_endpoint_mach_residual=maximum_endpoint_mach_residual,
    maximum_endpoint_gamma_residual=maximum_endpoint_gamma_residual,
    maximum_endpoint_log_pressure_residual=maximum_endpoint_log_pressure_residual,
    minimum_frontier_spacing_m=minimum_frontier_spacing_m,
    maximum_frontier_spacing_m=maximum_frontier_spacing_m,
    physical_chain_cell_count=0,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    external_validation_required=True,
    message=message,
    diagnostics=diagnostics,
  )


def _maximum(values: Sequence[float]) -> float | None:
  return None if not values else max(values)


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_frontier_reconciliation(
  result: Any,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit:
  """Re-extract frontiers and independently verify the reconciliation result."""

  from exhaust_plume.models.moc.planner import (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
  )

  status_type = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAuditStatus
  )
  if not isinstance(
    result,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult,
  ):
    return _audit_failure(status_type.INVALID_INPUT, 'result must be a typed frontier-reconciliation result')
  try:
    tolerances = tuple(
      float(value)
      for value in (
        position_tolerance_m,
        state_tolerance,
        pressure_tolerance,
        characteristic_residual_tolerance,
        pressure_lineage_tolerance,
        cell_residual_tolerance,
      )
    )
  except (TypeError, ValueError):
    return _audit_failure(
      status_type.INVALID_INPUT,
      'frontier-reconciliation audit tolerances must be numeric',
      reconciliation=result,
    )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('frontier-reconciliation audit tolerances must be finite and positive')
  (
    position_tolerance,
    resolved_state_tolerance,
    resolved_pressure_tolerance,
    characteristic_tolerance,
    pressure_lineage,
    cell_tolerance,
  ) = tolerances
  planner = result.planner
  if not isinstance(
    planner,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
  ):
    return _audit_failure(
      status_type.INVALID_INPUT,
      'reconciliation result did not retain its typed planner',
      reconciliation=result,
    )
  try:
    chain_audit = measure_moc_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain(
      planner,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_lineage,
      cell_residual_tolerance=cell_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _audit_failure(
      status_type.CHAIN_FAILURE,
      f'independent closure-chain audit raised: {error}',
      reconciliation=result,
    )
  if not chain_audit.local_consistency_verified:
    return _audit_failure(
      status_type.CHAIN_FAILURE,
      'the retained planner failed its independent closure-chain audit',
      reconciliation=result,
      closure_chain_audit=chain_audit,
      planner_resolved=planner.resolved,
      diagnostics={'chain_audit_status': chain_audit.status.value},
    )

  fresh_frontiers: list[MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult] = []
  fingerprints: list[str] = []
  for index, candidate in enumerate(planner.closures, start=1):
    continuation = candidate.continuation
    remesh = candidate.remesh
    if not isinstance(
      continuation,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ) or not isinstance(
      remesh,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
    ):
      return _audit_failure(
        status_type.FRONTIER_FAILURE,
        f'candidate {index} did not retain typed continuation and remesh stages',
        reconciliation=result,
        closure_chain_audit=chain_audit,
        planner_resolved=planner.resolved,
        reextracted_frontier_count=len(fresh_frontiers),
        reextracted_frontier_fingerprints=fingerprints,
      )
    frontier = extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier(
      remesh,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
    )
    if not frontier.converged or frontier.sample_count < 2:
      return _audit_failure(
        status_type.FRONTIER_FAILURE,
        f'independent frontier extraction failed for candidate {index}',
        reconciliation=result,
        closure_chain_audit=chain_audit,
        planner_resolved=planner.resolved,
        reextracted_frontier_count=len(fresh_frontiers),
        reextracted_frontier_fingerprints=fingerprints,
      )
    fresh_frontiers.append(frontier)
    fingerprints.append(_fingerprint(frontier))

  frontier_fingerprints_verified = bool(
    tuple(fingerprints) == result.frontier_fingerprints
  )
  frontier_records_verified = True
  anchor_links_verified = True
  for index, (candidate, frontier) in enumerate(
    zip(planner.closures, fresh_frontiers, strict=True),
    start=1,
  ):
    anchor = result.anchors[index - 1] if index <= len(result.anchors) else None
    recorded = (
      None
      if candidate.closure is None or candidate.closure.frontier_coverage is None
      else candidate.closure.frontier_coverage.frontier
    )
    continuation = candidate.continuation
    recorded_ok = bool(
      recorded is not None
      and recorded.converged
      and _samples_match(
        frontier.samples,
        recorded.samples,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
      )
    )
    if continuation is None:
      endpoint_residuals = ((), (), (), (), ())
    else:
      endpoint_residuals = _endpoint_residuals(
        frontier.samples,
        continuation.continuation_boundary,
      )
    endpoint_ok = _residuals_within(
      endpoint_residuals,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
    )
    anchor_ok = bool(
      isinstance(anchor, MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor)
      and _samples_match(
        frontier.samples,
        anchor.frontier.samples,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
      )
      and anchor.frontier_record_link_verified == recorded_ok
      and anchor.continuation_boundary_verified == endpoint_ok
      and _arrays_close(anchor.endpoint_position_residuals_m, endpoint_residuals[0], position_tolerance)
      and _arrays_close(anchor.endpoint_flow_angle_residuals_rad, endpoint_residuals[1], resolved_state_tolerance)
      and _arrays_close(anchor.endpoint_mach_residuals, endpoint_residuals[2], resolved_state_tolerance)
      and _arrays_close(anchor.endpoint_gamma_residuals, endpoint_residuals[3], resolved_state_tolerance)
      and _arrays_close(anchor.endpoint_log_pressure_residuals, endpoint_residuals[4], resolved_pressure_tolerance)
      and anchor.verified == bool(recorded_ok and endpoint_ok)
    )
    frontier_records_verified = bool(frontier_records_verified and recorded_ok)
    anchor_links_verified = bool(anchor_links_verified and anchor_ok)

  shape_verified = bool(
    len(result.anchors) == len(fresh_frontiers)
    and len(result.seams) == max(0, len(fresh_frontiers) - 1)
  )
  frontier_order_verified = True
  source_band_bridges_verified = True
  seams_verified = shape_verified
  spacings: list[float] = []
  for index, (upstream, downstream) in enumerate(
    zip(planner.closures, planner.closures[1:]),
    start=1,
  ):
    seam = result.seams[index - 1] if index <= len(result.seams) else None
    upstream_continuation = upstream.continuation
    downstream_continuation = downstream.continuation
    shared = tuple(downstream.incoming_handoff)
    upstream_residuals = _endpoint_residuals(
      fresh_frontiers[index - 1].samples,
      shared,
    )
    downstream_residuals = (
      ((), (), (), (), ())
      if downstream_continuation is None
      else _endpoint_residuals(
        fresh_frontiers[index].samples,
        downstream_continuation.continuation_boundary,
      )
    )
    upstream_ok = _residuals_within(
      upstream_residuals,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
    )
    downstream_ok = _residuals_within(
      downstream_residuals,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
    )
    spacing = (
      fresh_frontiers[index].samples[0].state.x_m
      - fresh_frontiers[index - 1].samples[-1].state.x_m
    )
    spacings.append(spacing)
    order_ok = bool(isfinite(spacing) and spacing >= -position_tolerance)
    if result.maximum_allowed_frontier_spacing_m is not None:
      order_ok = bool(
        order_ok
        and spacing
        <= result.maximum_allowed_frontier_spacing_m + position_tolerance
      )
    bridge_ok = bool(
      upstream_continuation is not None
      and downstream_continuation is not None
      and downstream.source_field is upstream_continuation
      and downstream.incoming_handoff == upstream_continuation.continuation_boundary
      and downstream_continuation.incoming_handoff == shared
      and downstream.fresh_domain_verified
      and downstream_continuation.local_consistency_verified
      and downstream.remesh_source_link_verified
    )
    expected_seam_ok = bool(upstream_ok and downstream_ok and order_ok and bridge_ok)
    seam_ok = bool(
      isinstance(seam, MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam)
      and seam.upstream_endpoint_link_verified == upstream_ok
      and seam.downstream_endpoint_link_verified == downstream_ok
      and seam.source_band_bridge_verified == bridge_ok
      and seam.frontier_order_verified == order_ok
      and seam.frontier_spacing_m is not None
      and abs(seam.frontier_spacing_m - spacing) <= position_tolerance
      and seam.verified == expected_seam_ok
    )
    frontier_order_verified = bool(frontier_order_verified and order_ok and seam_ok)
    source_band_bridges_verified = bool(source_band_bridges_verified and bridge_ok and seam_ok)
    seams_verified = bool(seams_verified and seam_ok)
  # The independently measured arrays are retained below without relying on
  # the result's aggregate properties.
  endpoint_values = [
    _endpoint_residuals(
      fresh_frontier.samples,
      planner.closures[index].continuation.continuation_boundary,
    )
    for index, fresh_frontier in enumerate(fresh_frontiers)
    if planner.closures[index].continuation is not None
  ]
  endpoint_values.extend(
    _endpoint_residuals(
      fresh_frontiers[index].samples,
      tuple(planner.closures[index + 1].incoming_handoff),
    )
    for index in range(max(0, len(fresh_frontiers) - 1))
  )
  position_residuals = tuple(value for item in endpoint_values for value in item[0])
  angle_residuals = tuple(value for item in endpoint_values for value in item[1])
  mach_residuals = tuple(value for item in endpoint_values for value in item[2])
  gamma_residuals = tuple(value for item in endpoint_values for value in item[3])
  pressure_residuals = tuple(value for item in endpoint_values for value in item[4])
  termination_verified = bool(
    planner.termination.reason is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
    and not planner.termination.physical_termination
    and result.termination_verified
  )
  fidelity_flags_verified = bool(
    result.physical_chain_cell_count == 0
    and not result.physical_closure_verified
    and result.chain_promotion_blocked
    and not result.production_claim_allowed
    and result.external_validation_required
    and planner.physical_chain_cell_count == 0
    and not planner.physical_closure_verified
    and planner.chain_promotion_blocked
    and not planner.production_claim_allowed
    and planner.external_validation_required
  )
  planner_result_consistent = bool(
    result.converged
    == (
      planner.resolved
      and shape_verified
      and frontier_fingerprints_verified
      and frontier_records_verified
      and anchor_links_verified
      and frontier_order_verified
      and source_band_bridges_verified
      and seams_verified
      and termination_verified
      and fidelity_flags_verified
    )
    and result.converged
  )
  common = dict(
    reconciliation=result,
    closure_chain_audit=chain_audit,
    planner_resolved=planner.resolved,
    reextracted_frontier_count=len(fresh_frontiers),
    reextracted_frontier_fingerprints=fingerprints,
    result_frontier_fingerprints_verified=frontier_fingerprints_verified,
    frontier_records_verified=frontier_records_verified,
    anchor_links_verified=anchor_links_verified,
    frontier_order_verified=frontier_order_verified,
    source_band_bridges_verified=source_band_bridges_verified,
    seams_verified=seams_verified,
    termination_verified=termination_verified,
    planner_result_consistent=planner_result_consistent,
    fidelity_flags_verified=fidelity_flags_verified,
    maximum_endpoint_position_residual_m=_maximum(position_residuals),
    maximum_endpoint_flow_angle_residual_rad=_maximum(angle_residuals),
    maximum_endpoint_mach_residual=_maximum(mach_residuals),
    maximum_endpoint_gamma_residual=_maximum(gamma_residuals),
    maximum_endpoint_log_pressure_residual=_maximum(pressure_residuals),
    minimum_frontier_spacing_m=None if not spacings else min(spacings),
    maximum_frontier_spacing_m=None if not spacings else max(spacings),
  )
  if not fidelity_flags_verified:
    return _audit_failure(
      status_type.FLAG_FAILURE,
      'independent audit found weakened non-promotion flags',
      **common,
    )
  if not termination_verified:
    return _audit_failure(
      status_type.TERMINATION_FAILURE,
      'independent audit found an invalid frontier-chain termination',
      **common,
    )
  if not shape_verified or not frontier_fingerprints_verified or not frontier_records_verified:
    return _audit_failure(
      status_type.FRONTIER_FAILURE,
      'independent frontier extraction did not match the stored reconciliation',
      **common,
    )
  if not anchor_links_verified:
    return _audit_failure(
      status_type.ANCHOR_FAILURE,
      'independent endpoint and anchor checks failed',
      **common,
    )
  if not frontier_order_verified or not source_band_bridges_verified or not seams_verified:
    return _audit_failure(
      status_type.SEQUENCE_FAILURE,
      'independent adjacent-frontier seam checks failed',
      **common,
    )
  if not planner_result_consistent:
    return _audit_failure(
      status_type.TERMINATION_FAILURE,
      'stored reconciliation convergence does not match independent gates',
      **common,
    )
  return _audit_failure(
    status_type.CONVERGED_GLOBAL_AUDIT,
    'independent audit confirmed exact frontier records, endpoint anchors, '
    'band ordering, and non-promotion flags; dense pointwise continuity and '
    'physical shock-cell closure remain unclaimed',
    **common,
  )


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase:
  """One parameterized local frontier-reconciliation case."""

  case_id: str
  outer_flow_angle_half_width_rad: float
  cycle_count: int
  subdivision_side_count: int
  closure_count: int
  result: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be a non-empty string')
    object.__setattr__(self, 'case_id', case_id)
    angle = float(self.outer_flow_angle_half_width_rad)
    if not isfinite(angle) or angle <= 0.0:
      raise ValueError('outer_flow_angle_half_width_rad must be finite and positive')
    object.__setattr__(self, 'outer_flow_angle_half_width_rad', angle)
    for name in ('cycle_count', 'subdivision_side_count', 'closure_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
    if not isinstance(
      self.result,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult,
    ):
      raise TypeError('result must be a typed frontier-reconciliation result')
    if self.result.frontier_count != self.closure_count:
      raise ValueError('closure_count must match the reconciliation frontier count')
    if self.result.planner is not None:
      if len(self.result.planner.closures) != self.closure_count:
        raise ValueError('closure_count must match the planner closure count')
      if any(
        candidate.subdivision_side_count != self.subdivision_side_count
        or candidate.cycle_count != self.cycle_count
        for candidate in self.result.planner.closures
      ):
        raise ValueError('case solver parameters must match retained closure candidates')

  def as_report(self) -> dict[str, Any]:
    return {
      'case_id': self.case_id,
      'outer_flow_angle_half_width_rad': self.outer_flow_angle_half_width_rad,
      'cycle_count': self.cycle_count,
      'subdivision_side_count': self.subdivision_side_count,
      'closure_count': self.closure_count,
      'result_status': self.result.status.value,
      'result_converged': self.result.converged,
      'frontier_count': self.result.frontier_count,
      'seam_count': self.result.seam_count,
      'frontier_sample_counts': list(self.result.frontier_sample_counts),
    }


class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus(
  str,
  Enum,
):
  """Outcome of the cross-case frontier refinement ladder."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged_global_entropy_characteristic_frontier_reconciliation_refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'frontier_reconciliation_refinement_case_failure'
  PARAMETER_FAILURE = 'frontier_reconciliation_refinement_parameter_failure'
  SHAPE_FAILURE = 'frontier_reconciliation_refinement_shape_failure'
  RESIDUAL_FAILURE = 'frontier_reconciliation_refinement_residual_failure'


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementMeasurement:
  """Cross-case stability evidence below physical closure."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
  cases: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase, ...]
  audits: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit, ...]
  case_ids: tuple[str, ...]
  outer_flow_angle_half_widths_rad: tuple[float, ...]
  cycle_counts: tuple[int, ...]
  subdivision_side_counts: tuple[int, ...]
  closure_counts: tuple[int, ...]
  frontier_counts: tuple[int, ...]
  seam_counts: tuple[int, ...]
  frontier_sample_counts: tuple[tuple[int, ...], ...]
  maximum_endpoint_position_residuals_m: tuple[float, ...]
  maximum_endpoint_flow_angle_residuals_rad: tuple[float, ...]
  maximum_endpoint_mach_residuals: tuple[float, ...]
  maximum_endpoint_gamma_residuals: tuple[float, ...]
  maximum_endpoint_log_pressure_residuals: tuple[float, ...]
  minimum_frontier_spacings_m: tuple[float, ...]
  maximum_frontier_spacings_m: tuple[float, ...]
  case_ids_verified: bool
  parameter_refinement_verified: bool
  shape_verified: bool
  audits_verified: bool
  frontier_records_verified: bool
  anchor_links_verified: bool
  frontier_order_verified: bool
  source_band_bridges_verified: bool
  seams_verified: bool
  termination_verified: bool
  residuals_finite: bool
  residuals_bounded: bool
  refinement_stable_verified: bool
  physical_chain_cell_count: int = 0
  physical_closure_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  external_validation_required: bool = True
  position_tolerance_m: float = 1.0e-8
  state_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  message: str = ''
  operator_id: str = (
    MOC_EULER_AMBIENT_FIRST_WEDGE_ENTROPY_CHARACTERISTIC_FRONTIER_RECONCILIATION_AUDIT_OPERATOR_ID
    + '-refinement'
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus,
    ):
      raise TypeError('status must be a frontier-refinement status')
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    if any(
      not isinstance(
        case,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase,
      )
      for case in cases
    ):
      raise TypeError('cases must contain typed frontier-refinement cases')
    if any(
      not isinstance(
        audit,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit,
      )
      for audit in audits
    ):
      raise TypeError('audits must contain typed frontier-reconciliation audits')
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    for name in (
      'case_ids',
      'outer_flow_angle_half_widths_rad',
      'cycle_counts',
      'subdivision_side_counts',
      'closure_counts',
      'frontier_counts',
      'seam_counts',
      'frontier_sample_counts',
      'maximum_endpoint_position_residuals_m',
      'maximum_endpoint_flow_angle_residuals_rad',
      'maximum_endpoint_mach_residuals',
      'maximum_endpoint_gamma_residuals',
      'maximum_endpoint_log_pressure_residuals',
      'minimum_frontier_spacings_m',
      'maximum_frontier_spacings_m',
    ):
      values = tuple(getattr(self, name))
      if len(values) != len(cases):
        raise ValueError(f'{name} must match the case count')
      object.__setattr__(self, name, values)
    for name in (
      'case_ids_verified',
      'parameter_refinement_verified',
      'shape_verified',
      'audits_verified',
      'frontier_records_verified',
      'anchor_links_verified',
      'frontier_order_verified',
      'source_band_bridges_verified',
      'seams_verified',
      'termination_verified',
      'residuals_finite',
      'residuals_bounded',
      'refinement_stable_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'external_validation_required',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.physical_chain_cell_count < 0:
      raise ValueError('physical_chain_cell_count must be nonnegative')
    if self.physical_closure_verified:
      raise ValueError('frontier refinement cannot claim physical closure')
    if not self.chain_promotion_blocked:
      raise ValueError('frontier refinement must retain promotion block')
    if self.production_claim_allowed:
      raise ValueError('frontier refinement cannot claim production validity')
    for name in (
      'maximum_endpoint_position_residuals_m',
      'maximum_endpoint_flow_angle_residuals_rad',
      'maximum_endpoint_mach_residuals',
      'maximum_endpoint_gamma_residuals',
      'maximum_endpoint_log_pressure_residuals',
      'minimum_frontier_spacings_m',
      'maximum_frontier_spacings_m',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    angles = tuple(float(value) for value in self.outer_flow_angle_half_widths_rad)
    if any(not isfinite(value) or value <= 0.0 for value in angles):
      raise ValueError('outer_flow_angle_half_widths_rad must be finite and positive')
    object.__setattr__(self, 'outer_flow_angle_half_widths_rad', angles)
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
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
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.case_ids_verified
      and self.parameter_refinement_verified
      and self.shape_verified
      and self.audits_verified
      and self.frontier_records_verified
      and self.anchor_links_verified
      and self.frontier_order_verified
      and self.source_band_bridges_verified
      and self.seams_verified
      and self.termination_verified
      and self.residuals_finite
      and self.residuals_bounded
      and self.refinement_stable_verified
      and self.external_validation_required
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'case_ids': list(self.case_ids),
      'outer_flow_angle_half_widths_rad': list(self.outer_flow_angle_half_widths_rad),
      'cycle_counts': list(self.cycle_counts),
      'subdivision_side_counts': list(self.subdivision_side_counts),
      'closure_counts': list(self.closure_counts),
      'frontier_counts': list(self.frontier_counts),
      'seam_counts': list(self.seam_counts),
      'frontier_sample_counts': [list(value) for value in self.frontier_sample_counts],
      'maximum_endpoint_position_residuals_m': list(self.maximum_endpoint_position_residuals_m),
      'maximum_endpoint_flow_angle_residuals_rad': list(self.maximum_endpoint_flow_angle_residuals_rad),
      'maximum_endpoint_mach_residuals': list(self.maximum_endpoint_mach_residuals),
      'maximum_endpoint_gamma_residuals': list(self.maximum_endpoint_gamma_residuals),
      'maximum_endpoint_log_pressure_residuals': list(self.maximum_endpoint_log_pressure_residuals),
      'minimum_frontier_spacings_m': list(self.minimum_frontier_spacings_m),
      'maximum_frontier_spacings_m': list(self.maximum_frontier_spacings_m),
      'checks': {
        'case_ids_verified': self.case_ids_verified,
        'parameter_refinement_verified': self.parameter_refinement_verified,
        'shape_verified': self.shape_verified,
        'audits_verified': self.audits_verified,
        'frontier_records_verified': self.frontier_records_verified,
        'anchor_links_verified': self.anchor_links_verified,
        'frontier_order_verified': self.frontier_order_verified,
        'source_band_bridges_verified': self.source_band_bridges_verified,
        'seams_verified': self.seams_verified,
        'termination_verified': self.termination_verified,
        'residuals_finite': self.residuals_finite,
        'residuals_bounded': self.residuals_bounded,
        'refinement_stable_verified': self.refinement_stable_verified,
        'pointwise_dense_continuity_verified': False,
        'physical_chain_cell_count': 0,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': True,
      },
      'cases': [case.as_report() for case in self.cases],
      'audits': [audit.as_report() for audit in self.audits],
      'physical_chain_cell_count': 0,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': True,
      'message': self.message,
    }


def _measurement_failure(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase] = (),
  audits: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationAudit] = (),
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementMeasurement:
  case_values = tuple(cases)
  audit_values = tuple(audits)
  paired = min(len(case_values), len(audit_values))
  case_values = case_values[:paired]
  audit_values = audit_values[:paired]
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementMeasurement(
    status=status,
    cases=case_values,
    audits=audit_values,
    case_ids=tuple(case.case_id for case in case_values),
    outer_flow_angle_half_widths_rad=tuple(case.outer_flow_angle_half_width_rad for case in case_values),
    cycle_counts=tuple(case.cycle_count for case in case_values),
    subdivision_side_counts=tuple(case.subdivision_side_count for case in case_values),
    closure_counts=tuple(case.closure_count for case in case_values),
    frontier_counts=tuple(audit.frontier_count for audit in audit_values),
    seam_counts=tuple(audit.seam_count for audit in audit_values),
    frontier_sample_counts=tuple(
      tuple(audit.reconciliation.frontier_sample_counts)
      if audit.reconciliation is not None
      else ()
      for audit in audit_values
    ),
    maximum_endpoint_position_residuals_m=tuple(
      audit.maximum_endpoint_position_residual_m or 0.0 for audit in audit_values
    ),
    maximum_endpoint_flow_angle_residuals_rad=tuple(
      audit.maximum_endpoint_flow_angle_residual_rad or 0.0 for audit in audit_values
    ),
    maximum_endpoint_mach_residuals=tuple(
      audit.maximum_endpoint_mach_residual or 0.0 for audit in audit_values
    ),
    maximum_endpoint_gamma_residuals=tuple(
      audit.maximum_endpoint_gamma_residual or 0.0 for audit in audit_values
    ),
    maximum_endpoint_log_pressure_residuals=tuple(
      audit.maximum_endpoint_log_pressure_residual or 0.0 for audit in audit_values
    ),
    minimum_frontier_spacings_m=tuple(
      audit.minimum_frontier_spacing_m or 0.0 for audit in audit_values
    ),
    maximum_frontier_spacings_m=tuple(
      audit.maximum_frontier_spacing_m or 0.0 for audit in audit_values
    ),
    case_ids_verified=False,
    parameter_refinement_verified=False,
    shape_verified=False,
    audits_verified=False,
    frontier_records_verified=False,
    anchor_links_verified=False,
    frontier_order_verified=False,
    source_band_bridges_verified=False,
    seams_verified=False,
    termination_verified=False,
    residuals_finite=False,
    residuals_bounded=False,
    refinement_stable_verified=False,
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    message=message,
  )


def measure_moc_euler_ambient_first_wedge_entropy_characteristic_frontier_reconciliation_refinement_ladder(
  cases: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase],
  *,
  expected_case_ids: Sequence[str] | None = None,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementMeasurement:
  """Audit a parameter-refined frontier case matrix."""

  try:
    items = tuple(cases)
  except TypeError:
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus.INVALID_INPUT,
      'frontier-refinement cases must be iterable',
    )
  if len(items) < 2:
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus.INVALID_INPUT,
      'at least two frontier-refinement cases are required',
    )
  if any(
    not isinstance(
      case,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementCase,
    )
    for case in items
  ):
    return _measurement_failure(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus.INVALID_INPUT,
      'cases must contain typed frontier-refinement cases',
    )
  tolerances = tuple(
    float(value)
    for value in (
      position_tolerance_m,
      state_tolerance,
      pressure_tolerance,
      characteristic_residual_tolerance,
      pressure_lineage_tolerance,
      cell_residual_tolerance,
    )
  )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    raise ValueError('frontier-refinement tolerances must be finite and positive')
  (
    position_tolerance,
    resolved_state_tolerance,
    resolved_pressure_tolerance,
    characteristic_tolerance,
    pressure_lineage,
    cell_tolerance,
  ) = tolerances
  audits = tuple(
    measure_moc_euler_ambient_first_wedge_entropy_characteristic_frontier_reconciliation(
      case.result,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      characteristic_residual_tolerance=characteristic_tolerance,
      pressure_lineage_tolerance=pressure_lineage,
      cell_residual_tolerance=cell_tolerance,
    )
    for case in items
  )
  case_ids = tuple(case.case_id for case in items)
  case_ids_verified = bool(
    len(set(case_ids)) == len(case_ids)
    and (
      expected_case_ids is None
      or case_ids == tuple(str(value) for value in expected_case_ids)
    )
  )
  angles = tuple(case.outer_flow_angle_half_width_rad for case in items)
  parameter_refinement_verified = bool(
    all(left < right for left, right in zip(angles, angles[1:]))
    and all(
      case.cycle_count == items[0].cycle_count
      and case.subdivision_side_count == items[0].subdivision_side_count
      and case.closure_count == items[0].closure_count
      for case in items
    )
  )
  frontier_counts = tuple(audit.frontier_count for audit in audits)
  seam_counts = tuple(audit.seam_count for audit in audits)
  sample_counts = tuple(
    () if audit.reconciliation is None else audit.reconciliation.frontier_sample_counts
    for audit in audits
  )
  shape_verified = bool(
    all(value == frontier_counts[0] for value in frontier_counts)
    and all(value == seam_counts[0] for value in seam_counts)
    and all(value == sample_counts[0] for value in sample_counts)
    and all(value == items[0].closure_count for value in frontier_counts)
    and all(value == max(0, items[0].closure_count - 1) for value in seam_counts)
  )
  audits_verified = all(audit.local_consistency_verified for audit in audits)
  frontier_records_verified = all(audit.frontier_records_verified for audit in audits)
  anchor_links_verified = all(audit.anchor_links_verified for audit in audits)
  frontier_order_verified = all(audit.frontier_order_verified for audit in audits)
  source_band_bridges_verified = all(audit.source_band_bridges_verified for audit in audits)
  seams_verified = all(audit.seams_verified for audit in audits)
  termination_verified = all(audit.termination_verified for audit in audits)
  maxima = (
    tuple(audit.maximum_endpoint_position_residual_m or 0.0 for audit in audits),
    tuple(audit.maximum_endpoint_flow_angle_residual_rad or 0.0 for audit in audits),
    tuple(audit.maximum_endpoint_mach_residual or 0.0 for audit in audits),
    tuple(audit.maximum_endpoint_gamma_residual or 0.0 for audit in audits),
    tuple(audit.maximum_endpoint_log_pressure_residual or 0.0 for audit in audits),
  )
  minimum_spacings = tuple(audit.minimum_frontier_spacing_m or 0.0 for audit in audits)
  maximum_spacings = tuple(audit.maximum_frontier_spacing_m or 0.0 for audit in audits)
  residuals_finite = bool(
    all(isfinite(value) and value >= 0.0 for values in (*maxima, minimum_spacings, maximum_spacings) for value in values)
  )
  residuals_bounded = bool(
    all(value <= position_tolerance for value in maxima[0])
    and all(value <= resolved_state_tolerance for values in maxima[1:4] for value in values)
    and all(value <= resolved_pressure_tolerance for value in maxima[4])
    and all(isfinite(value) and value >= -position_tolerance for value in minimum_spacings)
    and all(isfinite(value) and value >= -position_tolerance for value in maximum_spacings)
  )
  refinement_stable_verified = bool(
    audits_verified
    and shape_verified
    and frontier_records_verified
    and anchor_links_verified
    and frontier_order_verified
    and source_band_bridges_verified
    and seams_verified
    and termination_verified
    and residuals_finite
    and residuals_bounded
  )
  if not case_ids_verified or not parameter_refinement_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
      .PARAMETER_FAILURE
    )
    message = 'frontier-refinement case IDs or ordered parameter ladder is inconsistent'
  elif not shape_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
      .SHAPE_FAILURE
    )
    message = 'frontier-refinement cases did not retain a common frontier/seam shape'
  elif not audits_verified or not frontier_records_verified or not anchor_links_verified or not frontier_order_verified or not source_band_bridges_verified or not seams_verified or not termination_verified:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
      .CASE_FAILURE
    )
    message = 'one or more independent global-frontier case audits failed'
  elif not residuals_finite or not residuals_bounded:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
      .RESIDUAL_FAILURE
    )
    message = 'frontier-refinement endpoint residuals or band spacing are not bounded'
  else:
    status = (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementStatus
      .CONVERGED_LOCAL_REFINEMENT
    )
    message = (
      'cross-case frontier reconciliation passed for the ordered outer-angle '
      'bracket ladder; this is local global-frontier evidence, not dense '
      'pointwise continuity or physical shock-cell promotion'
    )
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationRefinementMeasurement(
    status=status,
    cases=items,
    audits=audits,
    case_ids=case_ids,
    outer_flow_angle_half_widths_rad=angles,
    cycle_counts=tuple(case.cycle_count for case in items),
    subdivision_side_counts=tuple(case.subdivision_side_count for case in items),
    closure_counts=tuple(case.closure_count for case in items),
    frontier_counts=frontier_counts,
    seam_counts=seam_counts,
    frontier_sample_counts=sample_counts,
    maximum_endpoint_position_residuals_m=maxima[0],
    maximum_endpoint_flow_angle_residuals_rad=maxima[1],
    maximum_endpoint_mach_residuals=maxima[2],
    maximum_endpoint_gamma_residuals=maxima[3],
    maximum_endpoint_log_pressure_residuals=maxima[4],
    minimum_frontier_spacings_m=minimum_spacings,
    maximum_frontier_spacings_m=maximum_spacings,
    case_ids_verified=case_ids_verified,
    parameter_refinement_verified=parameter_refinement_verified,
    shape_verified=shape_verified,
    audits_verified=audits_verified,
    frontier_records_verified=frontier_records_verified,
    anchor_links_verified=anchor_links_verified,
    frontier_order_verified=frontier_order_verified,
    source_band_bridges_verified=source_band_bridges_verified,
    seams_verified=seams_verified,
    termination_verified=termination_verified,
    residuals_finite=residuals_finite,
    residuals_bounded=residuals_bounded,
    refinement_stable_verified=refinement_stable_verified,
    position_tolerance_m=position_tolerance,
    state_tolerance=resolved_state_tolerance,
    pressure_tolerance=resolved_pressure_tolerance,
    message=message,
  )
