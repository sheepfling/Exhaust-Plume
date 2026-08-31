"""Global reconciliation of continued entropy-characteristic frontiers.

The continued entropy-characteristic closure planner produces one locally
closed candidate at a time.  This module adds the missing solver-owned seam:
each candidate's exact outgoing ``C-`` remesh frontier is re-extracted,
matched to its retained continuation boundary, and compared with the next
candidate's incoming handoff.

The reconciliation is intentionally stricter than a local closure probe but
still below a physical shock-cell chain.  It verifies the compressed
two-endpoint inter-band handoff and downstream ordering.  It does not claim
pointwise dense continuity between bands, invent a state in a gap, or promote
the local candidates to ``MocChainCell`` values.
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
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_remesh_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
)

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult',
  'reconcile_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus(
  str,
  Enum,
):
  """Outcome of the solver-owned global frontier reconciliation."""

  CONVERGED_GLOBAL_RECONCILIATION = (
    'converged_global_entropy_characteristic_frontier_reconciliation'
  )
  INVALID_INPUT = 'invalid_input'
  CHAIN_REQUIRED = (
    'entropy_characteristic_frontier_reconciliation_chain_required'
  )
  LOCAL_CLOSURE_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_local_closure_failure'
  )
  FRONTIER_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_frontier_failure'
  )
  ANCHOR_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_anchor_failure'
  )
  SEQUENCE_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_sequence_failure'
  )
  TERMINATION_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_termination_failure'
  )
  FIDELITY_FAILURE = (
    'entropy_characteristic_frontier_reconciliation_fidelity_failure'
  )


def _state_sample_residuals(
  actual: MocChainBoundarySample,
  expected: MocChainBoundarySample,
) -> tuple[float, float, float, float, float]:
  """Return position, angle, Mach, gamma, and log-pressure residuals."""

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
  """Compare the outer and centerline endpoints in stored frontier order."""

  actual_values = tuple(actual)
  expected_values = tuple(expected)
  if len(actual_values) < 2 or len(expected_values) != 2:
    return (), (), (), (), ()
  residuals = tuple(
    _state_sample_residuals(actual_value, expected_value)
    for actual_value, expected_value in zip(
      (actual_values[0], actual_values[-1]),
      expected_values,
      strict=True,
    )
  )
  return (
    tuple(value[0] for value in residuals),
    tuple(value[1] for value in residuals),
    tuple(value[2] for value in residuals),
    tuple(value[3] for value in residuals),
    tuple(value[4] for value in residuals),
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
      _state_sample_residuals(actual_value, expected_value)
      for actual_value, expected_value in zip(
        actual_values,
        expected_values,
        strict=True,
      )
    )
  )


def _maximum(values: Sequence[float]) -> float | None:
  return None if not values else max(values)


def _frontier_fingerprint(
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


def _frontier_sequence_fingerprint(
  frontiers: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult],
) -> str | None:
  values = tuple(frontiers)
  if not values:
    return None
  return sha256(
    '\n'.join(_frontier_fingerprint(frontier) for frontier in values).encode(
      'ascii'
    )
  ).hexdigest()


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor:
  """Evidence tying one exact remesh frontier to its continuation band."""

  frontier_index: int
  frontier: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult
  continuation_boundary: tuple[MocChainBoundarySample, ...]
  frontier_record_link_verified: bool
  endpoint_position_residuals_m: tuple[float, ...]
  endpoint_flow_angle_residuals_rad: tuple[float, ...]
  endpoint_mach_residuals: tuple[float, ...]
  endpoint_gamma_residuals: tuple[float, ...]
  endpoint_log_pressure_residuals: tuple[float, ...]
  continuation_boundary_verified: bool
  verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.frontier_index, bool)
      or not isinstance(self.frontier_index, int)
      or self.frontier_index < 1
    ):
      raise ValueError('frontier_index must be a positive integer')
    if not isinstance(
      self.frontier,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
    ):
      raise TypeError('frontier must be a typed remesh frontier result')
    boundary = tuple(self.continuation_boundary)
    if any(not isinstance(value, MocChainBoundarySample) for value in boundary):
      raise TypeError('continuation_boundary must contain typed samples')
    object.__setattr__(self, 'continuation_boundary', boundary)
    for name in (
      'endpoint_position_residuals_m',
      'endpoint_flow_angle_residuals_rad',
      'endpoint_mach_residuals',
      'endpoint_gamma_residuals',
      'endpoint_log_pressure_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    for name in (
      'frontier_record_link_verified',
      'continuation_boundary_verified',
      'verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def maximum_position_residual_m(self) -> float | None:
    return _maximum(self.endpoint_position_residuals_m)

  @property
  def maximum_flow_angle_residual_rad(self) -> float | None:
    return _maximum(self.endpoint_flow_angle_residuals_rad)

  @property
  def maximum_mach_residual(self) -> float | None:
    return _maximum(self.endpoint_mach_residuals)

  @property
  def maximum_gamma_residual(self) -> float | None:
    return _maximum(self.endpoint_gamma_residuals)

  @property
  def maximum_log_pressure_residual(self) -> float | None:
    return _maximum(self.endpoint_log_pressure_residuals)

  def as_report(self) -> dict[str, Any]:
    return {
      'frontier_index': self.frontier_index,
      'frontier_record_link_verified': self.frontier_record_link_verified,
      'continuation_boundary_sample_count': len(self.continuation_boundary),
      'continuation_boundary_verified': self.continuation_boundary_verified,
      'endpoint_position_residuals_m': list(self.endpoint_position_residuals_m),
      'endpoint_flow_angle_residuals_rad': list(self.endpoint_flow_angle_residuals_rad),
      'endpoint_mach_residuals': list(self.endpoint_mach_residuals),
      'endpoint_gamma_residuals': list(self.endpoint_gamma_residuals),
      'endpoint_log_pressure_residuals': list(self.endpoint_log_pressure_residuals),
      'maximum_position_residual_m': self.maximum_position_residual_m,
      'maximum_flow_angle_residual_rad': self.maximum_flow_angle_residual_rad,
      'maximum_mach_residual': self.maximum_mach_residual,
      'maximum_gamma_residual': self.maximum_gamma_residual,
      'maximum_log_pressure_residual': self.maximum_log_pressure_residual,
      'verified': self.verified,
      'frontier': self.frontier.as_report(),
      'continuation_boundary': [
        {
          'point_m': list(sample.point_m),
          'theta_rad': sample.state.theta_rad,
          'mach': sample.state.mach,
          'gamma': sample.state.gamma,
          'total_pressure_Pa': sample.total_pressure_Pa,
        }
        for sample in self.continuation_boundary
      ],
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam:
  """Evidence for the compressed handoff between adjacent frontier bands."""

  seam_index: int
  upstream_frontier: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult
  downstream_frontier: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult
  shared_handoff: tuple[MocChainBoundarySample, ...]
  upstream_endpoint_link_verified: bool
  downstream_endpoint_link_verified: bool
  source_band_bridge_verified: bool
  frontier_order_verified: bool
  frontier_spacing_m: float | None
  endpoint_position_residuals_m: tuple[float, ...]
  endpoint_flow_angle_residuals_rad: tuple[float, ...]
  endpoint_mach_residuals: tuple[float, ...]
  endpoint_gamma_residuals: tuple[float, ...]
  endpoint_log_pressure_residuals: tuple[float, ...]
  verified: bool
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.seam_index, bool)
      or not isinstance(self.seam_index, int)
      or self.seam_index < 1
    ):
      raise ValueError('seam_index must be a positive integer')
    for name in ('upstream_frontier', 'downstream_frontier'):
      if not isinstance(
        getattr(self, name),
        MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult,
      ):
        raise TypeError(f'{name} must be a typed remesh frontier result')
    handoff = tuple(self.shared_handoff)
    if any(not isinstance(value, MocChainBoundarySample) for value in handoff):
      raise TypeError('shared_handoff must contain typed samples')
    object.__setattr__(self, 'shared_handoff', handoff)
    for name in (
      'endpoint_position_residuals_m',
      'endpoint_flow_angle_residuals_rad',
      'endpoint_mach_residuals',
      'endpoint_gamma_residuals',
      'endpoint_log_pressure_residuals',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
      object.__setattr__(self, name, values)
    if self.frontier_spacing_m is not None:
      spacing = float(self.frontier_spacing_m)
      if not isfinite(spacing):
        raise ValueError('frontier_spacing_m must be finite or None')
      object.__setattr__(self, 'frontier_spacing_m', spacing)
    for name in (
      'upstream_endpoint_link_verified',
      'downstream_endpoint_link_verified',
      'source_band_bridge_verified',
      'frontier_order_verified',
      'verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def maximum_position_residual_m(self) -> float | None:
    return _maximum(self.endpoint_position_residuals_m)

  @property
  def maximum_flow_angle_residual_rad(self) -> float | None:
    return _maximum(self.endpoint_flow_angle_residuals_rad)

  @property
  def maximum_mach_residual(self) -> float | None:
    return _maximum(self.endpoint_mach_residuals)

  @property
  def maximum_gamma_residual(self) -> float | None:
    return _maximum(self.endpoint_gamma_residuals)

  @property
  def maximum_log_pressure_residual(self) -> float | None:
    return _maximum(self.endpoint_log_pressure_residuals)

  def as_report(self) -> dict[str, Any]:
    return {
      'seam_index': self.seam_index,
      'shared_handoff_sample_count': len(self.shared_handoff),
      'upstream_endpoint_link_verified': self.upstream_endpoint_link_verified,
      'downstream_endpoint_link_verified': self.downstream_endpoint_link_verified,
      'source_band_bridge_verified': self.source_band_bridge_verified,
      'frontier_order_verified': self.frontier_order_verified,
      'frontier_spacing_m': self.frontier_spacing_m,
      'endpoint_position_residuals_m': list(self.endpoint_position_residuals_m),
      'endpoint_flow_angle_residuals_rad': list(self.endpoint_flow_angle_residuals_rad),
      'endpoint_mach_residuals': list(self.endpoint_mach_residuals),
      'endpoint_gamma_residuals': list(self.endpoint_gamma_residuals),
      'endpoint_log_pressure_residuals': list(self.endpoint_log_pressure_residuals),
      'maximum_position_residual_m': self.maximum_position_residual_m,
      'maximum_flow_angle_residual_rad': self.maximum_flow_angle_residual_rad,
      'maximum_mach_residual': self.maximum_mach_residual,
      'maximum_gamma_residual': self.maximum_gamma_residual,
      'maximum_log_pressure_residual': self.maximum_log_pressure_residual,
      'verified': self.verified,
      'upstream_frontier': self.upstream_frontier.as_report(),
      'downstream_frontier': self.downstream_frontier.as_report(),
      'shared_handoff': [
        {
          'point_m': list(sample.point_m),
          'theta_rad': sample.state.theta_rad,
          'mach': sample.state.mach,
          'gamma': sample.state.gamma,
          'total_pressure_Pa': sample.total_pressure_Pa,
        }
        for sample in self.shared_handoff
      ],
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult:
  """Global frontier evidence below physical shock-cell promotion."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus
  planner: Any | None
  anchors: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor, ...]
  seams: tuple[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam, ...]
  position_tolerance_m: float = 1.0e-8
  state_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  maximum_allowed_frontier_spacing_m: float | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus,
    ):
      raise TypeError('status must be a frontier-reconciliation status')
    if self.planner is not None:
      from exhaust_plume.models.moc.planner import (
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
      )

      if not isinstance(
        self.planner,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
      ):
        raise TypeError('planner must be a typed continuation-closure planner or None')
    anchors = tuple(self.anchors)
    seams = tuple(self.seams)
    if any(
      not isinstance(
        value,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor,
      )
      for value in anchors
    ):
      raise TypeError('anchors must contain typed frontier anchors')
    if any(
      not isinstance(
        value,
        MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam,
      )
      for value in seams
    ):
      raise TypeError('seams must contain typed frontier seams')
    if tuple(value.frontier_index for value in anchors) != tuple(
      range(1, len(anchors) + 1)
    ):
      raise ValueError('frontier anchors must be consecutively indexed')
    if tuple(value.seam_index for value in seams) != tuple(
      range(1, len(seams) + 1)
    ):
      raise ValueError('frontier seams must be consecutively indexed')
    object.__setattr__(self, 'anchors', anchors)
    object.__setattr__(self, 'seams', seams)
    for name in (
      'position_tolerance_m',
      'state_tolerance',
      'pressure_tolerance',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      object.__setattr__(self, name, value)
    if self.maximum_allowed_frontier_spacing_m is not None:
      value = float(self.maximum_allowed_frontier_spacing_m)
      if not isfinite(value) or value <= 0.0:
        raise ValueError(
          'maximum_allowed_frontier_spacing_m must be finite and positive'
        )
      object.__setattr__(self, 'maximum_allowed_frontier_spacing_m', value)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus
      .CONVERGED_GLOBAL_RECONCILIATION
    )

  @property
  def frontier_count(self) -> int:
    return len(self.anchors)

  @property
  def seam_count(self) -> int:
    return len(self.seams)

  @property
  def frontiers(self) -> tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult, ...
  ]:
    return tuple(anchor.frontier for anchor in self.anchors)

  @property
  def frontier_sample_counts(self) -> tuple[int, ...]:
    return tuple(frontier.sample_count for frontier in self.frontiers)

  @property
  def frontier_fingerprints(self) -> tuple[str, ...]:
    return tuple(_frontier_fingerprint(frontier) for frontier in self.frontiers)

  @property
  def global_frontier_fingerprint(self) -> str | None:
    return _frontier_sequence_fingerprint(self.frontiers)

  @property
  def frontier_x_extents_m(self) -> tuple[tuple[float, float], ...]:
    return tuple(
      (frontier.samples[0].state.x_m, frontier.samples[-1].state.x_m)
      for frontier in self.frontiers
      if frontier.samples
    )

  @property
  def frontier_anchor_links_verified(self) -> bool:
    return bool(self.anchors) and all(
      anchor.frontier_record_link_verified
      and anchor.continuation_boundary_verified
      and anchor.verified
      for anchor in self.anchors
    )

  @property
  def frontier_order_verified(self) -> bool:
    return bool(self.anchors) and all(
      seam.frontier_order_verified for seam in self.seams
    ) if self.seams else bool(self.anchors)

  @property
  def source_band_bridges_verified(self) -> bool:
    return bool(self.anchors) and (
      self.seam_count == max(0, self.frontier_count - 1)
      and all(seam.source_band_bridge_verified for seam in self.seams)
    )

  @property
  def seams_verified(self) -> bool:
    return bool(
      self.anchors
      and (self.seam_count == 0 or all(seam.verified for seam in self.seams))
    )

  @property
  def termination_verified(self) -> bool:
    if self.planner is None:
      return False
    return bool(
      self.planner.termination.reason
      is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
      and not self.planner.termination.physical_termination
    )

  @property
  def local_closure_gates_verified(self) -> bool:
    return bool(
      self.planner is not None
      and self.planner.resolved
      and self.planner.closure_count == self.frontier_count
      and all(result.local_closure_verified for result in self.planner.closures)
    )

  @property
  def maximum_endpoint_position_residual_m(self) -> float | None:
    return _maximum(
      tuple(
        value
        for item in (*self.anchors, *self.seams)
        for value in item.endpoint_position_residuals_m
      )
    )

  @property
  def maximum_endpoint_flow_angle_residual_rad(self) -> float | None:
    return _maximum(
      tuple(
        value
        for item in (*self.anchors, *self.seams)
        for value in item.endpoint_flow_angle_residuals_rad
      )
    )

  @property
  def maximum_endpoint_mach_residual(self) -> float | None:
    return _maximum(
      tuple(
        value
        for item in (*self.anchors, *self.seams)
        for value in item.endpoint_mach_residuals
      )
    )

  @property
  def maximum_endpoint_gamma_residual(self) -> float | None:
    return _maximum(
      tuple(
        value
        for item in (*self.anchors, *self.seams)
        for value in item.endpoint_gamma_residuals
      )
    )

  @property
  def maximum_endpoint_log_pressure_residual(self) -> float | None:
    return _maximum(
      tuple(
        value
        for item in (*self.anchors, *self.seams)
        for value in item.endpoint_log_pressure_residuals
      )
    )

  @property
  def frontier_spacing_m(self) -> tuple[float, ...]:
    return tuple(
      seam.frontier_spacing_m
      for seam in self.seams
      if seam.frontier_spacing_m is not None
    )

  @property
  def maximum_frontier_spacing_m(self) -> float | None:
    return _maximum(self.frontier_spacing_m)

  @property
  def minimum_frontier_spacing_m(self) -> float | None:
    values = self.frontier_spacing_m
    return None if not values else min(values)

  @property
  def frontier_sequence_verified(self) -> bool:
    return bool(
      self.frontier_anchor_links_verified
      and self.frontier_order_verified
      and self.source_band_bridges_verified
      and (self.seam_count == 0 or self.seams_verified)
    )

  @property
  def global_reconciled(self) -> bool:
    return bool(
      self.converged
      and self.local_closure_gates_verified
      and self.frontier_sequence_verified
      and self.termination_verified
    )

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  @property
  def physical_closure_verified(self) -> bool:
    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  @property
  def external_validation_required(self) -> bool:
    return True

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'global_reconciled': self.global_reconciled,
      'frontier_count': self.frontier_count,
      'seam_count': self.seam_count,
      'frontier_sample_counts': list(self.frontier_sample_counts),
      'frontier_fingerprints': list(self.frontier_fingerprints),
      'global_frontier_fingerprint': self.global_frontier_fingerprint,
      'frontier_x_extents_m': [list(value) for value in self.frontier_x_extents_m],
      'frontier_spacing_m': list(self.frontier_spacing_m),
      'minimum_frontier_spacing_m': self.minimum_frontier_spacing_m,
      'maximum_frontier_spacing_m': self.maximum_frontier_spacing_m,
      'maximum_allowed_frontier_spacing_m': self.maximum_allowed_frontier_spacing_m,
      'maximum_endpoint_position_residual_m': self.maximum_endpoint_position_residual_m,
      'maximum_endpoint_flow_angle_residual_rad': self.maximum_endpoint_flow_angle_residual_rad,
      'maximum_endpoint_mach_residual': self.maximum_endpoint_mach_residual,
      'maximum_endpoint_gamma_residual': self.maximum_endpoint_gamma_residual,
      'maximum_endpoint_log_pressure_residual': self.maximum_endpoint_log_pressure_residual,
      'checks': {
        'frontier_anchor_links_verified': self.frontier_anchor_links_verified,
        'frontier_order_verified': self.frontier_order_verified,
        'source_band_bridges_verified': self.source_band_bridges_verified,
        'seams_verified': self.seams_verified,
        'frontier_sequence_verified': self.frontier_sequence_verified,
        'local_closure_gates_verified': self.local_closure_gates_verified,
        'termination_verified': self.termination_verified,
        'pointwise_dense_continuity_verified': False,
        'physical_chain_cell_count': 0,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': True,
      },
      'planner': (
        None
        if self.planner is None
        else {
          'resolved': self.planner.resolved,
          'closure_count': self.planner.closure_count,
          'termination_reason': self.planner.termination.reason.value,
          'termination_physical': self.planner.termination.physical_termination,
        }
      ),
      'anchors': [anchor.as_report() for anchor in self.anchors],
      'seams': [seam.as_report() for seam in self.seams],
      'position_tolerance_m': self.position_tolerance_m,
      'state_tolerance': self.state_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'physical_chain_cell_count': 0,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': True,
      'message': self.message,
    }


def _result(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus,
  planner: Any | None,
  anchors: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor] = (),
  seams: Sequence[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam] = (),
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  maximum_allowed_frontier_spacing_m: float | None = None,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult(
    status=status,
    planner=planner,
    anchors=tuple(anchors),
    seams=tuple(seams),
    position_tolerance_m=position_tolerance_m,
    state_tolerance=state_tolerance,
    pressure_tolerance=pressure_tolerance,
    maximum_allowed_frontier_spacing_m=maximum_allowed_frontier_spacing_m,
    message=message,
  )


def reconcile_euler_ambient_first_wedge_entropy_characteristic_continuation_closure_chain(
  planner: Any,
  *,
  position_tolerance_m: float = 1.0e-8,
  state_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  maximum_allowed_frontier_spacing_m: float | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationResult:
  """Reconcile exact outgoing frontiers across a local closure-chain plan."""

  from exhaust_plume.models.moc.planner import (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
  )

  status_type = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierReconciliationStatus
  )
  if not isinstance(
    planner,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureChainPlannerResult,
  ):
    return _result(
      status_type.INVALID_INPUT,
      None,
      message='planner must be a typed continuation-closure chain result',
    )
  try:
    tolerances = (
      float(position_tolerance_m),
      float(state_tolerance),
      float(pressure_tolerance),
    )
    maximum_spacing = (
      None
      if maximum_allowed_frontier_spacing_m is None
      else float(maximum_allowed_frontier_spacing_m)
    )
  except (TypeError, ValueError):
    return _result(
      status_type.INVALID_INPUT,
      planner,
      message='frontier reconciliation tolerances must be numeric',
    )
  if not all(isfinite(value) and value > 0.0 for value in tolerances):
    return _result(
      status_type.INVALID_INPUT,
      planner,
      message='frontier reconciliation tolerances must be finite and positive',
    )
  if maximum_spacing is not None and (
    not isfinite(maximum_spacing) or maximum_spacing <= 0.0
  ):
    return _result(
      status_type.INVALID_INPUT,
      planner,
      position_tolerance_m=tolerances[0],
      state_tolerance=tolerances[1],
      pressure_tolerance=tolerances[2],
      message='maximum_allowed_frontier_spacing_m must be finite and positive',
    )
  position_tolerance, resolved_state_tolerance, resolved_pressure_tolerance = tolerances
  if not planner.resolved or not planner.closures:
    return _result(
      status_type.CHAIN_REQUIRED,
      planner,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      maximum_allowed_frontier_spacing_m=maximum_spacing,
      message=(
        'a resolved continuation-closure chain with at least one local '
        'closure is required before global frontier reconciliation'
      ),
    )
  if any(not candidate.local_closure_verified for candidate in planner.closures):
    return _result(
      status_type.LOCAL_CLOSURE_FAILURE,
      planner,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      maximum_allowed_frontier_spacing_m=maximum_spacing,
      message='every retained candidate must pass its local closure gates',
    )
  if not (
    planner.physical_chain_cell_count == 0
    and not planner.physical_closure_verified
    and planner.chain_promotion_blocked
    and not planner.production_claim_allowed
    and planner.external_validation_required
  ):
    return _result(
      status_type.FIDELITY_FAILURE,
      planner,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      maximum_allowed_frontier_spacing_m=maximum_spacing,
      message='the reconciliation boundary requires explicit non-promotion flags',
    )

  anchors: list[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor] = []
  frontiers: list[MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFrontierResult] = []
  for index, candidate in enumerate(planner.closures, start=1):
    continuation = candidate.continuation
    remesh = candidate.remesh
    closure = candidate.closure
    if not isinstance(
      continuation,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ) or not isinstance(
      remesh,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
    ) or not isinstance(
      closure,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
    ):
      return _result(
        status_type.FRONTIER_FAILURE,
        planner,
        anchors,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
        maximum_allowed_frontier_spacing_m=maximum_spacing,
        message=f'closure candidate {index} did not retain all typed stages',
      )
    frontier = extract_euler_ambient_first_wedge_entropy_characteristic_remesh_frontier(
      remesh,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
    )
    if not frontier.converged or frontier.sample_count < 2:
      return _result(
        status_type.FRONTIER_FAILURE,
        planner,
        anchors,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
        maximum_allowed_frontier_spacing_m=maximum_spacing,
        message=f'closure candidate {index} did not expose a valid exact C- frontier',
      )
    frontiers.append(frontier)
    recorded_frontier = (
      None
      if closure.frontier_coverage is None
      else closure.frontier_coverage.frontier
    )
    frontier_record_link_verified = bool(
      recorded_frontier is not None
      and recorded_frontier.converged
      and _samples_match(
        frontier.samples,
        recorded_frontier.samples,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
      )
    )
    endpoint_residuals = _endpoint_residuals(
      frontier.samples,
      continuation.continuation_boundary,
    )
    continuation_boundary_verified = bool(
      len(continuation.continuation_boundary) == 2
      and all(
        residual <= tolerance
        for residuals, tolerance in zip(
          endpoint_residuals[:4],
          (
            position_tolerance,
            resolved_state_tolerance,
            resolved_state_tolerance,
            resolved_state_tolerance,
          ),
          strict=True,
        )
        for residual in residuals
      )
      and all(
        residual <= resolved_pressure_tolerance
        for residual in endpoint_residuals[4]
      )
    )
    verified = bool(
      frontier_record_link_verified
      and continuation_boundary_verified
    )
    anchors.append(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierAnchor(
        frontier_index=index,
        frontier=frontier,
        continuation_boundary=tuple(continuation.continuation_boundary),
        frontier_record_link_verified=frontier_record_link_verified,
        endpoint_position_residuals_m=endpoint_residuals[0],
        endpoint_flow_angle_residuals_rad=endpoint_residuals[1],
        endpoint_mach_residuals=endpoint_residuals[2],
        endpoint_gamma_residuals=endpoint_residuals[3],
        endpoint_log_pressure_residuals=endpoint_residuals[4],
        continuation_boundary_verified=continuation_boundary_verified,
        verified=verified,
        message=(
          'exact remesh frontier is linked to the retained continuation '
          'boundary'
          if verified
          else 'frontier-to-continuation endpoint or record link failed'
        ),
      )
    )
    if not verified:
      return _result(
        status_type.ANCHOR_FAILURE,
        planner,
        anchors,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
        maximum_allowed_frontier_spacing_m=maximum_spacing,
        message=f'frontier anchor {index} failed its endpoint or record link',
      )

  seams: list[MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam] = []
  for index, (upstream, downstream) in enumerate(
    zip(planner.closures, planner.closures[1:]),
    start=1,
  ):
    upstream_continuation = upstream.continuation
    downstream_continuation = downstream.continuation
    if upstream_continuation is None or downstream_continuation is None:
      return _result(
        status_type.SEQUENCE_FAILURE,
        planner,
        anchors,
        seams,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
        maximum_allowed_frontier_spacing_m=maximum_spacing,
        message=f'frontier seam {index} lost a continuation stage',
      )
    shared_handoff = tuple(downstream.incoming_handoff)
    upstream_residuals = _endpoint_residuals(
      frontiers[index - 1].samples,
      shared_handoff,
    )
    downstream_residuals = _endpoint_residuals(
      frontiers[index].samples,
      downstream_continuation.continuation_boundary,
    )
    upstream_link_verified = bool(
      len(shared_handoff) == 2
      and all(
        residual <= tolerance
        for residuals, tolerance in zip(
          upstream_residuals,
          (
            position_tolerance,
            resolved_state_tolerance,
            resolved_state_tolerance,
            resolved_state_tolerance,
            resolved_pressure_tolerance,
          ),
          strict=True,
        )
        for residual in residuals
      )
    )
    downstream_link_verified = bool(
      len(downstream_continuation.continuation_boundary) == 2
      and all(
        residual <= tolerance
        for residuals, tolerance in zip(
          downstream_residuals,
          (
            position_tolerance,
            resolved_state_tolerance,
            resolved_state_tolerance,
            resolved_state_tolerance,
            resolved_pressure_tolerance,
          ),
          strict=True,
        )
        for residual in residuals
      )
    )
    upstream_end_x = frontiers[index - 1].samples[-1].state.x_m
    downstream_start_x = frontiers[index].samples[0].state.x_m
    spacing = downstream_start_x - upstream_end_x
    frontier_order_verified = bool(
      isfinite(spacing) and spacing >= -position_tolerance
    )
    spacing_limit_verified = bool(
      maximum_spacing is None or spacing <= maximum_spacing + position_tolerance
    )
    source_band_bridge_verified = bool(
      downstream.source_field is upstream_continuation
      and downstream.incoming_handoff == upstream_continuation.continuation_boundary
      and downstream_continuation.incoming_handoff == shared_handoff
      and downstream.fresh_domain_verified
      and downstream_continuation.local_consistency_verified
      and downstream.remesh_source_link_verified
    )
    seam_residuals = tuple(
      tuple(left + right for left, right in zip(left_values, right_values, strict=True))
      for left_values, right_values in zip(
        upstream_residuals,
        downstream_residuals,
        strict=True,
      )
    )
    verified = bool(
      upstream_link_verified
      and downstream_link_verified
      and source_band_bridge_verified
      and frontier_order_verified
      and spacing_limit_verified
    )
    seams.append(
      MocEulerAmbientFirstWedgeEntropyCharacteristicFrontierSeam(
        seam_index=index,
        upstream_frontier=frontiers[index - 1],
        downstream_frontier=frontiers[index],
        shared_handoff=shared_handoff,
        upstream_endpoint_link_verified=upstream_link_verified,
        downstream_endpoint_link_verified=downstream_link_verified,
        source_band_bridge_verified=source_band_bridge_verified,
        frontier_order_verified=frontier_order_verified and spacing_limit_verified,
        frontier_spacing_m=spacing,
        endpoint_position_residuals_m=seam_residuals[0],
        endpoint_flow_angle_residuals_rad=seam_residuals[1],
        endpoint_mach_residuals=seam_residuals[2],
        endpoint_gamma_residuals=seam_residuals[3],
        endpoint_log_pressure_residuals=seam_residuals[4],
        verified=verified,
        message=(
          'adjacent frontiers reconcile through the exact compressed handoff; '
          'positive spacing is downstream band advance, not an inferred field'
          if verified
          else f'frontier seam {index} failed an inter-band reconciliation gate'
        ),
      )
    )
    if not verified:
      return _result(
        status_type.SEQUENCE_FAILURE,
        planner,
        anchors,
        seams,
        position_tolerance_m=position_tolerance,
        state_tolerance=resolved_state_tolerance,
        pressure_tolerance=resolved_pressure_tolerance,
        maximum_allowed_frontier_spacing_m=maximum_spacing,
        message=f'frontier seam {index} failed its global ordering or handoff gates',
      )

  termination_verified = bool(
    planner.termination.reason
    is MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL
    and not planner.termination.physical_termination
  )
  if not termination_verified:
    return _result(
      status_type.TERMINATION_FAILURE,
      planner,
      anchors,
      seams,
      position_tolerance_m=position_tolerance,
      state_tolerance=resolved_state_tolerance,
      pressure_tolerance=resolved_pressure_tolerance,
      maximum_allowed_frontier_spacing_m=maximum_spacing,
      message='frontier reconciliation requires a nonphysical solver stop',
    )
  return _result(
    status_type.CONVERGED_GLOBAL_RECONCILIATION,
    planner,
    anchors,
    seams,
    position_tolerance_m=position_tolerance,
    state_tolerance=resolved_state_tolerance,
    pressure_tolerance=resolved_pressure_tolerance,
    maximum_allowed_frontier_spacing_m=maximum_spacing,
    message=(
      'global exact C- frontier reconciliation passed across locally closed '
      'continuation bands; dense pointwise inter-band continuity, physical '
      'shock-cell closure, and production promotion remain blocked'
    ),
  )
