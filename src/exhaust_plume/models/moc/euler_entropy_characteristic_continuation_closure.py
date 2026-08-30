"""Local reflected-boundary closure candidates for continued entropy bands.

The variable-entropy continuation lane and the reflected/free-boundary lane
have deliberately separate contracts.  This module composes them for one
downstream band at a time so a planner can retain the complete provenance:

``source band -> characteristic continuation -> characteristic remesh ->
outgoing-frontier bridge -> reflected/free-boundary closure``.

The returned field is a local closure candidate, not a promoted shock-cell
chain cell.  A global source-frontier reconciliation, refinement study, and
external validation are still required before production use.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_continuation,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  remesh_euler_ambient_first_wedge_entropy_characteristic_continuation,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_remesh_free_boundary import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult',
  'solve_euler_ambient_first_wedge_entropy_characteristic_continuation_closure',
)


EntropyContinuationSource = (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult
  | MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus(
  str,
  Enum,
):
  """Outcome of the composed local closure candidate."""

  CONVERGED_LOCAL_CLOSURE = (
    'converged_local_entropy_characteristic_continuation_closure'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_REQUIRED = 'entropy_characteristic_continuation_closure_source_required'
  HANDOFF_FAILURE = 'entropy_characteristic_continuation_closure_handoff_failure'
  CONTINUATION_FAILURE = (
    'entropy_characteristic_continuation_closure_continuation_failure'
  )
  REMESH_FAILURE = 'entropy_characteristic_continuation_closure_remesh_failure'
  EULER_RESIDUAL_FAILURE = (
    'entropy_characteristic_continuation_closure_euler_residual_failure'
  )
  CLOSURE_FAILURE = 'entropy_characteristic_continuation_closure_field_failure'


def _source_extent(source: EntropyContinuationSource) -> tuple[float, float] | None:
  values: list[float] = []
  if isinstance(source, MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult):
    points = tuple(node.point_m for node in source.nodes)
  elif isinstance(
    source,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  ):
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
  for point in points:
    try:
      value = float(point[0])
    except (IndexError, TypeError, ValueError):
      return None
    if not isfinite(value):
      return None
    values.append(value)
  return None if not values else (min(values), max(values))


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult:
  """Retain one continuation/remesh/closure candidate with typed lineage."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
  source_field: EntropyContinuationSource | None
  incoming_handoff: tuple[MocChainBoundarySample, ...]
  continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult | None = None
  remesh: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult | None = None
  closure: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult | None = None
  ambient_pressure_Pa: float | None = None
  outer_flow_angle_bracket: tuple[float, float] | None = None
  cycle_count: int = 4
  subdivision_side_count: int = 32
  target_centerline_y_m: float = 0.0
  target_centerline_flow_angle_rad: float = 0.0
  use_outgoing_frontier_bridge: bool = True
  allow_zero_strength_attachment: bool = True
  allow_zero_strength_endpoints: bool = True
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus,
    ):
      raise TypeError('status must be a continuation-closure status')
    if self.source_field is not None and not isinstance(
      self.source_field,
      (
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
      ),
    ):
      raise TypeError('source_field must be a typed entropy source or None')
    handoff = tuple(self.incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain typed boundary samples')
    object.__setattr__(self, 'incoming_handoff', handoff)
    if self.continuation is not None and not isinstance(
      self.continuation,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ):
      raise TypeError('continuation must be typed or None')
    if self.remesh is not None and not isinstance(
      self.remesh,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
    ):
      raise TypeError('remesh must be typed or None')
    if self.closure is not None and not isinstance(
      self.closure,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult,
    ):
      raise TypeError('closure must be typed or None')
    if self.ambient_pressure_Pa is not None:
      pressure = float(self.ambient_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      object.__setattr__(self, 'ambient_pressure_Pa', pressure)
    if self.outer_flow_angle_bracket is not None:
      bracket = tuple(float(value) for value in self.outer_flow_angle_bracket)
      if len(bracket) != 2 or not all(isfinite(value) for value in bracket):
        raise ValueError('outer_flow_angle_bracket must contain two finite values')
      if bracket[0] >= bracket[1]:
        raise ValueError('outer_flow_angle_bracket must be ordered')
      object.__setattr__(self, 'outer_flow_angle_bracket', bracket)
    for name in ('cycle_count', 'subdivision_side_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
    for name in ('target_centerline_y_m', 'target_centerline_flow_angle_rad'):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      object.__setattr__(self, name, value)
    for name in (
      'use_outgoing_frontier_bridge',
      'allow_zero_strength_attachment',
      'allow_zero_strength_endpoints',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def source_kind(self) -> str | None:
    if isinstance(
      self.source_field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      return 'internal-entropy-characteristic-field'
    if isinstance(
      self.source_field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ):
      return 'variable-entropy-characteristic-continuation'
    return None

  @property
  def source_link_verified(self) -> bool:
    return bool(
      self.source_field is not None
      and self.continuation is not None
      and self.continuation.source_field is self.source_field
    )

  @property
  def incoming_handoff_link_verified(self) -> bool:
    return bool(
      self.source_field is not None
      and self.incoming_handoff == self.source_field.continuation_boundary
      and self.continuation is not None
      and self.continuation.incoming_handoff == self.incoming_handoff
    )

  @property
  def gradient_link_verified(self) -> bool:
    return bool(
      self.source_field is not None
      and self.continuation is not None
      and self.source_field.source_pressure_gradient is not None
      and self.continuation.source_pressure_gradient
      == self.source_field.source_pressure_gradient
    )

  @property
  def fresh_domain_verified(self) -> bool:
    if self.source_field is None or self.continuation is None:
      return False
    current_extent = _source_extent(self.source_field)
    next_extent = _source_extent(self.continuation)
    if current_extent is None or next_extent is None:
      return False
    tolerance = (
      self.continuation.position_tolerance_m
      if self.continuation is not None
      else 1.0e-8
    )
    return bool(
      next_extent[0] >= current_extent[1] - tolerance
      and next_extent[1] > current_extent[1] + tolerance
    )

  @property
  def continuation_local_consistency_verified(self) -> bool:
    return bool(
      self.continuation is not None
      and self.continuation.local_consistency_verified
    )

  @property
  def remesh_source_link_verified(self) -> bool:
    return bool(
      self.continuation is not None
      and self.remesh is not None
      and self.remesh.source_continuation is self.continuation
    )

  @property
  def remesh_local_consistency_verified(self) -> bool:
    return bool(
      self.remesh is not None
      and self.remesh.local_characteristic_remesh_verified
    )

  @property
  def source_euler_gate_verified(self) -> bool:
    return bool(
      self.remesh is not None
      and self.remesh.cell_euler_residuals_verified
    )

  @property
  def closure_remesh_link_verified(self) -> bool:
    return bool(self.remesh is not None and self.closure is not None and self.closure.remesh is self.remesh)

  @property
  def local_reflected_free_boundary_verified(self) -> bool:
    return bool(
      self.closure is not None
      and self.closure.reflected_free_boundary_verified
    )

  @property
  def local_closure_verified(self) -> bool:
    """Whether the composed candidate closes locally at the requested band."""

    return bool(
      self.status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
      .CONVERGED_LOCAL_CLOSURE
      and self.source_field is not None
      and self.source_field.local_consistency_verified
      and self.incoming_handoff_link_verified
      and self.source_link_verified
      and self.gradient_link_verified
      and self.fresh_domain_verified
      and self.continuation_local_consistency_verified
      and self.remesh_source_link_verified
      and self.remesh_local_consistency_verified
      and self.source_euler_gate_verified
      and self.closure_remesh_link_verified
      and self.local_reflected_free_boundary_verified
      and self.closure is not None
      and self.closure.path_coverage_verified
      and self.closure.outgoing_frontier_bridge_verified
    )

  @property
  def converged(self) -> bool:
    return self.local_closure_verified

  @property
  def physical_chain_cell_count(self) -> int:
    return 0

  @property
  def physical_closure_verified(self) -> bool:
    """The composed evidence is intentionally not a production claim."""

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

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
      .INVALID_INPUT
    ):
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
      .SOURCE_REQUIRED,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
      .HANDOFF_FAILURE,
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
      .EULER_RESIDUAL_FAILURE
    ):
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
      .CONVERGED_LOCAL_CLOSURE
    ):
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'continuation_closure_status': self.status.value,
        'source_kind': self.source_kind,
        'source_link_verified': self.source_link_verified,
        'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
        'gradient_link_verified': self.gradient_link_verified,
        'fresh_domain_verified': self.fresh_domain_verified,
        'continuation_local_consistency_verified': (
          self.continuation_local_consistency_verified
        ),
        'remesh_source_link_verified': self.remesh_source_link_verified,
        'remesh_local_consistency_verified': (
          self.remesh_local_consistency_verified
        ),
        'source_euler_gate_verified': self.source_euler_gate_verified,
        'closure_remesh_link_verified': self.closure_remesh_link_verified,
        'local_reflected_free_boundary_verified': (
          self.local_reflected_free_boundary_verified
        ),
        'local_closure_verified': self.local_closure_verified,
        'physical_chain_cell_count': 0,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': True,
        'synthetic_downstream_field_created': False,
        'required_next_gate': (
          'global-source-frontier-reconciliation-refinement-and-external-'
          'validation-before-continued-shock-cell-chain'
        ),
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'source_kind': self.source_kind,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'source_link_verified': self.source_link_verified,
      'incoming_handoff_link_verified': self.incoming_handoff_link_verified,
      'gradient_link_verified': self.gradient_link_verified,
      'fresh_domain_verified': self.fresh_domain_verified,
      'continuation_local_consistency_verified': (
        self.continuation_local_consistency_verified
      ),
      'remesh_source_link_verified': self.remesh_source_link_verified,
      'remesh_local_consistency_verified': self.remesh_local_consistency_verified,
      'source_euler_gate_verified': self.source_euler_gate_verified,
      'closure_remesh_link_verified': self.closure_remesh_link_verified,
      'local_reflected_free_boundary_verified': (
        self.local_reflected_free_boundary_verified
      ),
      'local_closure_verified': self.local_closure_verified,
      'physical_chain_cell_count': 0,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': True,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'cycle_count': self.cycle_count,
      'subdivision_side_count': self.subdivision_side_count,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'use_outgoing_frontier_bridge': self.use_outgoing_frontier_bridge,
      'allow_zero_strength_attachment': self.allow_zero_strength_attachment,
      'allow_zero_strength_endpoints': self.allow_zero_strength_endpoints,
      'continuation': (
        None if self.continuation is None else self.continuation.as_report()
      ),
      'remesh': None if self.remesh is None else self.remesh.as_report(),
      'closure': None if self.closure is None else self.closure.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _result(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus,
  source_field: EntropyContinuationSource | None,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
  *,
  continuation: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult | None = None,
  remesh: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult | None = None,
  closure: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult | None = None,
  ambient_pressure_Pa: float | None = None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  cycle_count: int = 4,
  subdivision_side_count: int = 32,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  use_outgoing_frontier_bridge: bool = True,
  allow_zero_strength_attachment: bool = True,
  allow_zero_strength_endpoints: bool = True,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult(
    status=status,
    source_field=source_field,
    incoming_handoff=tuple(incoming_handoff),
    continuation=continuation,
    remesh=remesh,
    closure=closure,
    ambient_pressure_Pa=ambient_pressure_Pa,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    cycle_count=cycle_count,
    subdivision_side_count=subdivision_side_count,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    use_outgoing_frontier_bridge=use_outgoing_frontier_bridge,
    allow_zero_strength_attachment=allow_zero_strength_attachment,
    allow_zero_strength_endpoints=allow_zero_strength_endpoints,
    message=message,
  )


def solve_euler_ambient_first_wedge_entropy_characteristic_continuation_closure(
  source_field: EntropyContinuationSource,
  incoming_handoff: Sequence[MocChainBoundarySample],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  cycle_count: int = 4,
  subdivision_side_count: int = 32,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  position_tolerance_m: float = 1.0e-8,
  characteristic_residual_tolerance: float = 1.0e-8,
  pressure_lineage_tolerance: float = 1.0e-8,
  cell_residual_tolerance: float = 1.0e-2,
  maximum_iterations: int = 48,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  allow_zero_strength_attachment: bool = True,
  allow_zero_strength_endpoints: bool = True,
  use_outgoing_frontier_bridge: bool = True,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureResult:
  """Build one bounded local closure candidate from an exact source frontier."""

  status_type = (
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationClosureStatus
  )
  if not isinstance(
    source_field,
    (
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
    ),
  ):
    return _result(
      status_type.INVALID_INPUT,
      None,
      message='source_field must be a typed entropy field or continuation',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _result(
      status_type.INVALID_INPUT,
      source_field,
      message='incoming_handoff must be iterable',
    )
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return _result(
      status_type.INVALID_INPUT,
      source_field,
      handoff,
      message='incoming_handoff must contain typed boundary samples',
    )
  try:
    pressure = float(ambient_pressure_Pa)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
  except (TypeError, ValueError):
    return _result(
      status_type.INVALID_INPUT,
      source_field,
      handoff,
      message='closure inputs must be numeric',
    )
  if (
    not isfinite(pressure)
    or pressure <= 0.0
    or not isfinite(lower_angle)
    or not isfinite(upper_angle)
    or lower_angle >= upper_angle
  ):
    return _result(
      status_type.INVALID_INPUT,
      source_field,
      handoff,
      ambient_pressure_Pa=pressure,
      outer_flow_angle_bracket=(lower_angle, upper_angle),
      message='ambient pressure must be positive and angle bracket ordered',
    )
  if handoff != source_field.continuation_boundary or len(handoff) < 2:
    return _result(
      status_type.HANDOFF_FAILURE,
      source_field,
      handoff,
      ambient_pressure_Pa=pressure,
      outer_flow_angle_bracket=(lower_angle, upper_angle),
      message='incoming_handoff must exactly match the source continuation boundary',
    )
  if not source_field.local_consistency_verified or not source_field.state_sampling_available:
    return _result(
      status_type.SOURCE_REQUIRED,
      source_field,
      handoff,
      ambient_pressure_Pa=pressure,
      outer_flow_angle_bracket=(lower_angle, upper_angle),
      message='source must expose a locally consistent bounded state sampler',
    )
  common = {
    'ambient_pressure_Pa': pressure,
    'outer_flow_angle_bracket': (lower_angle, upper_angle),
    'cycle_count': cycle_count,
    'subdivision_side_count': subdivision_side_count,
    'target_centerline_y_m': target_centerline_y_m,
    'target_centerline_flow_angle_rad': target_centerline_flow_angle_rad,
    'use_outgoing_frontier_bridge': use_outgoing_frontier_bridge,
    'allow_zero_strength_attachment': allow_zero_strength_attachment,
    'allow_zero_strength_endpoints': allow_zero_strength_endpoints,
  }
  try:
    continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
      source_field,
      handoff,
      pressure,
      cycle_count=cycle_count,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      position_tolerance_m=position_tolerance_m,
      characteristic_residual_tolerance=characteristic_residual_tolerance,
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      maximum_iterations=maximum_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      status_type.CONTINUATION_FAILURE,
      source_field,
      handoff,
      message=f'continuation solve raised: {error}',
      **common,
    )
  if (
    not continuation.converged
    or not continuation.local_consistency_verified
    or continuation.source_field is not source_field
    or continuation.incoming_handoff != handoff
  ):
    return _result(
      status_type.CONTINUATION_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      message=(
        'continuation did not return a locally consistent band with the exact '
        'source and incoming frontier'
      ),
      **common,
    )
  try:
    remesh = remesh_euler_ambient_first_wedge_entropy_characteristic_continuation(
      continuation,
      subdivision_side_count=subdivision_side_count,
      position_tolerance_m=position_tolerance_m,
      # The remesh edge solve has a documented 1e-6 default acceptance
      # because it solves a nonlinear boundary trace; keep the continuation
      # and remesh tolerances distinct instead of making the remesh fail at
      # the continuation lane's tighter bookkeeping tolerance.
      characteristic_residual_tolerance=max(
        characteristic_residual_tolerance,
        1.0e-6,
      ),
      pressure_lineage_tolerance=pressure_lineage_tolerance,
      cell_residual_tolerance=cell_residual_tolerance,
      maximum_iterations=maximum_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      status_type.REMESH_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      message=f'continuation remesh raised: {error}',
      **common,
    )
  if (
    not remesh.converged
    or not remesh.local_characteristic_remesh_verified
    or remesh.source_continuation is not continuation
  ):
    return _result(
      status_type.REMESH_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      remesh=remesh,
      message='continuation remesh did not pass its local characteristic gates',
      **common,
    )
  if not remesh.cell_euler_residuals_verified:
    return _result(
      status_type.EULER_RESIDUAL_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      remesh=remesh,
      message=(
        'continuation remesh is locally characteristic but its conservative '
        'Euler residual gate is not accepted at this resolution'
      ),
      **common,
    )
  remesh_handoff = remesh.continuation_boundary
  if not remesh_handoff:
    return _result(
      status_type.HANDOFF_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      remesh=remesh,
      message='accepted remesh did not expose a continuation boundary',
      **common,
    )
  start_point = remesh_handoff[0].point_m
  local_ambient_pressure = remesh.diagnostic_static_pressure_at(
    start_point,
    position_tolerance_m=position_tolerance_m,
  )
  if local_ambient_pressure is None:
    return _result(
      status_type.CLOSURE_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      remesh=remesh,
      message='remesh did not provide a finite local ambient pressure at its frontier',
      **common,
    )
  try:
    closure = solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary(
      remesh,
      remesh_handoff,
      start_point,
      local_ambient_pressure,
      lower_angle,
      upper_angle,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=1.0e-10,
      attachment_pressure_tolerance=1.0e-8,
      pressure_tolerance=1.0e-8,
      tangent_tolerance=1.0e-8,
      shock_angle_tolerance_rad=1.0e-2,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
      use_outgoing_frontier_bridge=use_outgoing_frontier_bridge,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      status_type.CLOSURE_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      remesh=remesh,
      message=f'reflected/free-boundary closure raised: {error}',
      **common,
    )
  if not closure.converged or not closure.reflected_free_boundary_verified:
    return _result(
      status_type.CLOSURE_FAILURE,
      source_field,
      handoff,
      continuation=continuation,
      remesh=remesh,
      closure=closure,
      message=(
        'reflected/free-boundary closure did not pass its local closure '
        f'gates: {closure.message}'
      ),
      **common,
    )
  return _result(
    status_type.CONVERGED_LOCAL_CLOSURE,
    source_field,
    handoff,
    continuation=continuation,
    remesh=remesh,
    closure=closure,
    message=(
      'one local continued-band reflected closure is retained as research '
      'evidence; global source-frontier reconciliation and validation remain '
      'required before shock-cell-chain promotion'
    ),
    **common,
  )
