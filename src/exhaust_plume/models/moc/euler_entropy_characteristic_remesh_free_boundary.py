"""Free-boundary closure probe for a bounded characteristic continuation remesh.

The solver-owned remesh is a diagnostic upstream band, not an accepted Euler
field.  This module gives that band an explicit, bounded callback seam for a
reflected/free-boundary shock attempt.  Leaving the remesh is reported as a
domain boundary; no extrapolated upstream state and no physical shock-cell
chain cell are created.
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
from exhaust_plume.models.moc.coupled import (
  MocAmbientPhysicalFieldResult,
  solve_marched_attached_shock_with_ambient_centerline_physical_field,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_continuation_remesh import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus',
  'MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult',
  'solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary',
)


class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus(
  str,
  Enum,
):
  """Outcome of a reflected/free-boundary attempt from a bounded remesh."""

  CONVERGED_CLOSURE_PROBE = (
    'converged_entropy_characteristic_remesh_free_boundary_closure_probe'
  )
  INVALID_INPUT = 'invalid_input'
  REMESH_REQUIRED = 'entropy_characteristic_remesh_required'
  HANDOFF_FAILURE = 'entropy_characteristic_remesh_free_boundary_handoff_failure'
  UPSTREAM_REMESH_BOUNDARY = (
    'entropy_characteristic_remesh_free_boundary_upstream_remesh_boundary'
  )
  AMBIENT_ATTACHMENT_FAILURE = (
    'entropy_characteristic_remesh_free_boundary_ambient_attachment_failure'
  )
  REFLECTED_FIELD_FAILURE = (
    'entropy_characteristic_remesh_free_boundary_reflected_field_failure'
  )


def _finite_point(point_m: Sequence[float]) -> tuple[float, float] | None:
  try:
    point = (float(point_m[0]), float(point_m[1]))
  except (IndexError, TypeError, ValueError):
    return None
  return point if all(isfinite(value) for value in point) else None


@dataclass(frozen=True, slots=True)
class MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult:
  """A bounded closure attempt that never promotes a remesh to a chain cell."""

  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
  remesh: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult | None
  physical_field: MocAmbientPhysicalFieldResult | None
  incoming_handoff: tuple[MocChainBoundarySample, ...]
  start_point_m: tuple[float, float] | None
  ambient_pressure_Pa: float | None
  outer_flow_angle_bracket: tuple[float, float] | None
  target_centerline_y_m: float | None
  target_centerline_flow_angle_rad: float | None
  allow_zero_strength_attachment: bool
  shock_sample_count: int
  covered_sample_count: int
  first_missing_sample_index: int | None
  source_maximum_cell_euler_residual: float | None
  source_cell_euler_residuals_verified: bool
  message: str = ''
  position_tolerance_m: float = 1.0e-8

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus,
    ):
      raise TypeError('status must be a remesh free-boundary status')
    if self.remesh is not None and not isinstance(
      self.remesh,
      MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
    ):
      raise TypeError('remesh must be a typed continuation remesh or None')
    if self.physical_field is not None and not isinstance(
      self.physical_field,
      MocAmbientPhysicalFieldResult,
    ):
      raise TypeError('physical_field must be a MocAmbientPhysicalFieldResult or None')
    handoff = tuple(self.incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    object.__setattr__(self, 'incoming_handoff', handoff)
    if self.start_point_m is not None:
      point = _finite_point(self.start_point_m)
      if point is None:
        raise ValueError('start_point_m must contain two finite coordinates')
      object.__setattr__(self, 'start_point_m', point)
    if self.ambient_pressure_Pa is not None:
      pressure = float(self.ambient_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      object.__setattr__(self, 'ambient_pressure_Pa', pressure)
    if self.outer_flow_angle_bracket is not None:
      bracket = tuple(float(value) for value in self.outer_flow_angle_bracket)
      if len(bracket) != 2 or not all(isfinite(value) for value in bracket):
        raise ValueError('outer_flow_angle_bracket must contain two finite values')
      object.__setattr__(self, 'outer_flow_angle_bracket', bracket)
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric):
          raise ValueError(f'{name} must be finite when supplied')
        object.__setattr__(self, name, numeric)
    if not isinstance(self.allow_zero_strength_attachment, bool):
      raise TypeError('allow_zero_strength_attachment must be a bool')
    for name in ('shock_sample_count', 'covered_sample_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
    if self.first_missing_sample_index is not None and (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError(
        'first_missing_sample_index must be a nonnegative integer or None'
      )
    if self.source_maximum_cell_euler_residual is not None:
      residual = float(self.source_maximum_cell_euler_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'source_maximum_cell_euler_residual must be finite and nonnegative'
        )
      object.__setattr__(self, 'source_maximum_cell_euler_residual', residual)
    if not isinstance(self.source_cell_euler_residuals_verified, bool):
      raise TypeError('source_cell_euler_residuals_verified must be a bool')
    tolerance = float(self.position_tolerance_m)
    if not isfinite(tolerance) or tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    object.__setattr__(self, 'position_tolerance_m', tolerance)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def shock(self) -> MocFreeBoundaryShockResult | None:
    if self.physical_field is None or self.physical_field.ambient_attachment is None:
      return None
    return self.physical_field.ambient_attachment.shock

  @property
  def attachment_status(self) -> str | None:
    if self.physical_field is None or self.physical_field.ambient_attachment is None:
      return None
    return self.physical_field.ambient_attachment.status.value

  @property
  def physical_field_status(self) -> str | None:
    return None if self.physical_field is None else self.physical_field.status.value

  @property
  def source_remesh_verified(self) -> bool:
    return bool(
      self.remesh is not None
      and self.remesh.local_characteristic_remesh_verified
      and self.remesh.diagnostic_sampling_available
    )

  @property
  def path_coverage_verified(self) -> bool:
    return bool(
      self.shock is not None
      and self.shock.converged
      and self.shock_sample_count == self.covered_sample_count
      and self.first_missing_sample_index is None
    )

  @property
  def reflected_free_boundary_verified(self) -> bool:
    return bool(
      self.physical_field is not None
      and self.physical_field.physical_closure_verified
    )

  @property
  def closure_probe_converged(self) -> bool:
    return bool(
      self.status
      is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .CONVERGED_CLOSURE_PROBE
      and self.reflected_free_boundary_verified
    )

  @property
  def converged(self) -> bool:
    return self.closure_probe_converged

  @property
  def physical_closure_verified(self) -> bool:
    """Require both source Euler acceptance and reflected closure."""

    return bool(
      self.source_remesh_verified
      and self.source_cell_euler_residuals_verified
      and self.reflected_free_boundary_verified
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def production_claim_allowed(self) -> bool:
    return False

  @property
  def external_validation_required(self) -> bool:
    return True

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.source_remesh_verified
      and self.incoming_handoff
      and (
        self.path_coverage_verified
        or self.status
        is MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
        .UPSTREAM_REMESH_BOUNDARY
      )
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    if self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT
    ):
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status in (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .REMESH_REQUIRED,
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .HANDOFF_FAILURE,
    ):
      reason = MocChainTerminationReason.STATE_NOT_CARRIED
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .UPSTREAM_REMESH_BOUNDARY
    ):
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is (
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .CONVERGED_CLOSURE_PROBE
    ):
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    else:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'remesh_free_boundary_status': self.status.value,
        'physical_field_status': self.physical_field_status,
        'attachment_status': self.attachment_status,
        'shock_sample_count': self.shock_sample_count,
        'covered_sample_count': self.covered_sample_count,
        'first_missing_sample_index': self.first_missing_sample_index,
        'path_coverage_verified': self.path_coverage_verified,
        'source_remesh_verified': self.source_remesh_verified,
        'source_maximum_cell_euler_residual': (
          self.source_maximum_cell_euler_residual
        ),
        'source_cell_euler_residuals_verified': (
          self.source_cell_euler_residuals_verified
        ),
        'reflected_free_boundary_verified': self.reflected_free_boundary_verified,
        'physical_closure_verified': self.physical_closure_verified,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
        'external_validation_required': True,
        'synthetic_downstream_field_created': False,
        'physical_chain_cell_count': 0,
        'required_next_gate': (
          'source-euler-acceptance-reflected-free-boundary-closure-and-'
          'external-validation-before-continued-shock-cell-chain'
        ),
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'closure_probe_converged': self.closure_probe_converged,
      'local_consistency_verified': self.local_consistency_verified,
      'source_remesh_verified': self.source_remesh_verified,
      'source_maximum_cell_euler_residual': self.source_maximum_cell_euler_residual,
      'source_cell_euler_residuals_verified': (
        self.source_cell_euler_residuals_verified
      ),
      'path_coverage_verified': self.path_coverage_verified,
      'reflected_free_boundary_verified': self.reflected_free_boundary_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'external_validation_required': True,
      'incoming_handoff_sample_count': len(self.incoming_handoff),
      'start_point_m': self.start_point_m,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'allow_zero_strength_attachment': self.allow_zero_strength_attachment,
      'shock_sample_count': self.shock_sample_count,
      'covered_sample_count': self.covered_sample_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'attachment_status': self.attachment_status,
      'physical_field_status': self.physical_field_status,
      'shock': None if self.shock is None else self.shock.as_report(),
      'physical_field': (
        None if self.physical_field is None else self.physical_field.as_report()
      ),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
    }


def _result(
  status: MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus,
  remesh: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult | None,
  *,
  physical_field: MocAmbientPhysicalFieldResult | None = None,
  incoming_handoff: Sequence[MocChainBoundarySample] = (),
  start_point_m: tuple[float, float] | None = None,
  ambient_pressure_Pa: float | None = None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  target_centerline_y_m: float | None = None,
  target_centerline_flow_angle_rad: float | None = None,
  allow_zero_strength_attachment: bool = False,
  shock_sample_count: int = 0,
  covered_sample_count: int = 0,
  first_missing_sample_index: int | None = None,
  source_maximum_cell_euler_residual: float | None = None,
  source_cell_euler_residuals_verified: bool = False,
  position_tolerance_m: float = 1.0e-8,
  message: str,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult:
  return MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult(
    status=status,
    remesh=remesh,
    physical_field=physical_field,
    incoming_handoff=tuple(incoming_handoff),
    start_point_m=start_point_m,
    ambient_pressure_Pa=ambient_pressure_Pa,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    allow_zero_strength_attachment=allow_zero_strength_attachment,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_sample_count,
    first_missing_sample_index=first_missing_sample_index,
    source_maximum_cell_euler_residual=source_maximum_cell_euler_residual,
    source_cell_euler_residuals_verified=source_cell_euler_residuals_verified,
    position_tolerance_m=position_tolerance_m,
    message=message,
  )


def solve_euler_ambient_first_wedge_entropy_characteristic_remesh_free_boundary(
  remesh: MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  incoming_handoff: Sequence[MocChainBoundarySample],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-8,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
  allow_zero_strength_attachment: bool = False,
  allow_zero_strength_endpoints: bool = False,
  zero_strength_start_trace: Sequence[MocChainBoundarySample] | None = None,
) -> MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryResult:
  """Probe reflected closure without treating the remesh as a physical field."""

  source_residual = None if remesh is None else remesh.maximum_cell_euler_residual
  source_euler_verified = bool(
    remesh is not None and remesh.cell_euler_residuals_verified
  )
  if not isinstance(
    remesh,
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationRemeshResult,
  ):
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      None,
      message='remesh must be a typed continuation remesh result',
    )
  try:
    handoff = tuple(incoming_handoff)
  except TypeError:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      remesh,
      message='incoming_handoff must be iterable',
    )
  common = {
    'incoming_handoff': handoff,
    'source_maximum_cell_euler_residual': source_residual,
    'source_cell_euler_residuals_verified': source_euler_verified,
    'position_tolerance_m': position_tolerance_m,
  }
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      remesh,
      message='incoming_handoff must contain MocChainBoundarySample values',
      **common,
    )
  if not remesh.local_characteristic_remesh_verified or not remesh.diagnostic_sampling_available:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .REMESH_REQUIRED,
      remesh,
      message=(
        'remesh free-boundary closure requires a locally verified bounded '
        'characteristic remesh diagnostic sampler'
      ),
      **common,
    )
  if handoff != remesh.continuation_boundary or not handoff:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .HANDOFF_FAILURE,
      remesh,
      message='incoming_handoff must exactly match the remesh continuation boundary',
      **common,
    )
  point = _finite_point(start_point_m)
  if point is None:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      remesh,
      message='start_point_m must contain two finite coordinates',
      **common,
    )
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
    tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      remesh,
      message='free-boundary inputs must be numeric',
      **common,
    )
  base = {
    **common,
    'start_point_m': point,
    'ambient_pressure_Pa': ambient_pressure,
    'outer_flow_angle_bracket': (lower_angle, upper_angle),
    'target_centerline_y_m': target_y,
    'target_centerline_flow_angle_rad': target_angle,
    'allow_zero_strength_attachment': allow_zero_strength_attachment,
  }
  if not all(
    isfinite(value)
    for value in (
      *point,
      ambient_pressure,
      lower_angle,
      upper_angle,
      target_y,
      target_angle,
      tolerance,
    )
  ) or ambient_pressure <= 0.0 or lower_angle >= upper_angle or target_y >= point[1]:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      remesh,
      message=(
        'free-boundary inputs must be finite, pressure positive, angle '
        'bracket ordered, and centerline below the shock start'
      ),
      **base,
    )
  if not isinstance(allow_zero_strength_attachment, bool) or not isinstance(
    allow_zero_strength_endpoints,
    bool,
  ):
    raise ValueError('zero-strength options must be bool values')
  if not isinstance(branch, ShockBranch):
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .INVALID_INPUT,
      remesh,
      message='branch must be a ShockBranch',
      **base,
    )
  try:
    start_pressure = remesh.diagnostic_static_pressure_at(
      point,
      position_tolerance_m=tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    start_pressure = None
    sampler_error = str(error)
  else:
    sampler_error = ''
  if start_pressure is None:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .UPSTREAM_REMESH_BOUNDARY,
      remesh,
      message=(
        'shock start point is outside the bounded characteristic remesh; '
        f'no upstream state was extrapolated{": " + sampler_error if sampler_error else ""}'
      ),
      **base,
    )

  try:
    physical_field = solve_marched_attached_shock_with_ambient_centerline_physical_field(
      lambda sample_point: remesh.diagnostic_state_at(
        sample_point,
        position_tolerance_m=tolerance,
      ),
      lambda sample_point: remesh.diagnostic_static_pressure_at(
        sample_point,
        position_tolerance_m=tolerance,
      ),
      point,
      ambient_pressure,
      lower_angle,
      upper_angle,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      incoming_handoff=handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=tolerance,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
      allow_zero_strength_attachment=allow_zero_strength_attachment,
      zero_strength_start_trace=zero_strength_start_trace,
      allow_zero_strength_endpoints=allow_zero_strength_endpoints,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .REFLECTED_FIELD_FAILURE,
      remesh,
      message=f'remesh free-boundary coupling raised: {error}',
      physical_field=None,
      **base,
    )
  shock = physical_field.ambient_attachment
  shock_result = None if shock is None else shock.shock
  shock_sample_count = 0 if shock_result is None else len(shock_result.shock_points_m)
  covered_sample_count = (
    0 if shock_result is None else len(shock_result.upstream_states)
  )
  first_missing_sample_index = (
    None if shock_result is None else shock_result.failed_sample_index
  )
  if (
    shock_result is not None
    and shock_result.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE
  ):
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .UPSTREAM_REMESH_BOUNDARY,
      remesh,
      physical_field=physical_field,
      shock_sample_count=shock_sample_count,
      covered_sample_count=covered_sample_count,
      first_missing_sample_index=first_missing_sample_index,
      message=(
        'reflected/free-boundary shock left the bounded characteristic remesh '
        'before closure; no extrapolation or physical endpoint was inferred'
      ),
      **base,
    )
  if not physical_field.converged or not physical_field.physical_closure_verified:
    return _result(
      MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
      .REFLECTED_FIELD_FAILURE,
      remesh,
      physical_field=physical_field,
      shock_sample_count=shock_sample_count,
      covered_sample_count=covered_sample_count,
      first_missing_sample_index=first_missing_sample_index,
      message=(
        'reflected/free-boundary closure did not pass its physical field '
        f'gates: {physical_field.message}'
      ),
      **base,
    )
  return _result(
    MocEulerAmbientFirstWedgeEntropyCharacteristicRemeshFreeBoundaryStatus
    .CONVERGED_CLOSURE_PROBE,
    remesh,
    physical_field=physical_field,
    shock_sample_count=shock_sample_count,
    covered_sample_count=covered_sample_count,
    first_missing_sample_index=first_missing_sample_index,
    message=(
      'reflected/free-boundary closure converged over the bounded remesh, but '
      'source Euler acceptance and external validation remain required before '
      'any physical shock-cell-chain promotion'
    ),
    **base,
  )
