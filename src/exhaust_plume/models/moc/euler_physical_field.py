"""Exact-Euler ambient-closed physical-field bridge.

The exact shock and ambient-boundary modules deliberately stop at an open
characteristic strip because the shared attachment is a singular first
wedge.  This module adds the next solver-owned seam: it consumes a locally
Euler-verified shock curve, the solver-owned ambient march, and the existing
centerline-reflection assembler to produce a bounded physical-field
candidate.

The returned field is retained for diagnostics and for a future research
chain planner.  It is not silently promoted: the independent conservative
cell audit, refinement evidence, reflected free-boundary closure, and
external validation remain explicit gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
)
from exhaust_plume.models.moc.euler_ambient_field import (
  MocEulerAmbientBoundaryMarchResult,
  march_euler_ambient_boundary,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
  MocEulerShockBoundaryOrientation,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
  assemble_ambient_boundary_post_shock_field_with_centerline_reflection,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockBoundaryState,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
)

__all__ = (
  'MocEulerAmbientPhysicalFieldStatus',
  'MocEulerAmbientPhysicalFieldResult',
  'assemble_euler_ambient_physical_field',
)


class MocEulerAmbientPhysicalFieldStatus(str, Enum):
  """Outcome of the exact shock-to-ambient closed-field bridge."""

  CONVERGED_AMBIENT_CLOSED = 'converged_euler_ambient_closed_physical_field'
  INVALID_INPUT = 'invalid_input'
  SHOCK_BOUNDARY_REQUIRED = 'euler_physical_shock_boundary_required'
  AMBIENT_BOUNDARY_FAILURE = 'euler_physical_ambient_boundary_failure'
  FIELD_FAILURE = 'euler_physical_field_failure'


@dataclass(frozen=True, slots=True)
class MocEulerAmbientPhysicalFieldResult:
  """A bounded exact-Euler physical-field candidate with a hard claim stop.

  ``converged`` means that the exact shock, ambient march, and reflected
  centerline mesh assembled.  ``physical_closure_verified`` reports that
  boundary/topology closure.  It intentionally does not imply that the
  discretized cells satisfy an independent conservative residual tolerance;
  that evidence belongs to :mod:`exhaust_plume.validation.moc_euler`.
  """

  status: MocEulerAmbientPhysicalFieldStatus
  shock_boundary: MocEulerShockBoundaryCurveResult | None
  ambient_march: MocEulerAmbientBoundaryMarchResult | None
  field: MocPhysicalPostShockFieldResult | None
  ambient_pressure_Pa: float | None
  entropy_residuals: tuple[float, ...]
  maximum_entropy_residual: float | None
  shock_boundary_verified: bool
  ambient_boundary_verified: bool
  entropy_lineage_verified: bool
  physical_field_verified: bool
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerAmbientPhysicalFieldStatus):
      raise TypeError(
        'status must be a MocEulerAmbientPhysicalFieldStatus'
      )
    if self.shock_boundary is not None and not isinstance(
      self.shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'shock_boundary must be a MocEulerShockBoundaryCurveResult or None'
      )
    if self.ambient_march is not None and not isinstance(
      self.ambient_march,
      MocEulerAmbientBoundaryMarchResult,
    ):
      raise TypeError(
        'ambient_march must be a MocEulerAmbientBoundaryMarchResult or None'
      )
    if self.field is not None and not isinstance(
      self.field,
      MocPhysicalPostShockFieldResult,
    ):
      raise TypeError(
        'field must be a MocPhysicalPostShockFieldResult or None'
      )
    if self.ambient_pressure_Pa is not None:
      ambient_pressure = float(self.ambient_pressure_Pa)
      if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
        raise ValueError(
          'ambient_pressure_Pa must be finite and positive when supplied'
        )
      object.__setattr__(self, 'ambient_pressure_Pa', ambient_pressure)
    residuals = tuple(float(value) for value in self.entropy_residuals)
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError(
        'entropy_residuals must contain finite nonnegative values'
      )
    object.__setattr__(self, 'entropy_residuals', residuals)
    if self.maximum_entropy_residual is not None:
      maximum = float(self.maximum_entropy_residual)
      if not isfinite(maximum) or maximum < 0.0:
        raise ValueError(
          'maximum_entropy_residual must be finite and nonnegative when supplied'
        )
      object.__setattr__(self, 'maximum_entropy_residual', maximum)
    for name in (
      'shock_boundary_verified',
      'ambient_boundary_verified',
      'entropy_lineage_verified',
      'physical_field_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    """Whether the exact field bridge assembled a bounded closed mesh."""

    return bool(
      self.status is MocEulerAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
      and self.shock_boundary_verified
      and self.ambient_boundary_verified
      and self.physical_field_verified
      and self.field is not None
      and self.field.converged
    )

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the retained field passed its boundary/topology closure gates."""

    return bool(
      self.converged
      and self.field is not None
      and self.field.physical_closure_verified
    )

  @property
  def state_sampling_available(self) -> bool:
    """Whether the closed candidate carries a bounded state sampler."""

    return bool(
      self.converged
      and self.field is not None
      and self.field.state_sampling_available
    )

  @property
  def downstream_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Expose the centerline trace without authorizing chain promotion."""

    if not self.state_sampling_available or self.field is None:
      return ()
    return tuple(
      MocChainBoundarySample(state=state, total_pressure_Pa=pressure)
      for state, pressure in zip(
        self.field.centerline_boundary_states,
        self.field.centerline_boundary_total_pressure_Pa,
        strict=True,
      )
    )

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Return the explicit research-chain boundary for this candidate."""

    if self.converged:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.FIDELITY_NOT_ALLOWED,
        message=(
          'exact Euler ambient physical field closed its local boundary, but '
          'independent conservative-cell, refinement, reflected free-boundary, '
          'and external-validation gates still block chain promotion'
        ),
        diagnostics={
          'ambient_physical_field_status': self.status.value,
          'physical_closure_verified': self.physical_closure_verified,
          'entropy_lineage_verified': self.entropy_lineage_verified,
          'chain_promotion_blocked': True,
          'production_claim_allowed': False,
          'required_next_gate': 'independent-euler-cell-audit-and-refinement',
        },
      )
    if self.status is MocEulerAmbientPhysicalFieldStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    elif self.status is MocEulerAmbientPhysicalFieldStatus.SHOCK_BOUNDARY_REQUIRED:
      reason = MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY
    elif self.status is MocEulerAmbientPhysicalFieldStatus.AMBIENT_BOUNDARY_FAILURE:
      reason = MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    else:
      reason = MocChainTerminationReason.FIDELITY_NOT_ALLOWED
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=self.message,
      diagnostics={
        'ambient_physical_field_status': self.status.value,
        'physical_closure_verified': False,
        'chain_promotion_blocked': True,
        'production_claim_allowed': False,
      },
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'shock_boundary_verified': self.shock_boundary_verified,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'entropy_lineage_verified': self.entropy_lineage_verified,
      'entropy_residuals': list(self.entropy_residuals),
      'maximum_entropy_residual': self.maximum_entropy_residual,
      'physical_field_verified': self.physical_field_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'state_sampling_available': self.state_sampling_available,
      'downstream_handoff_sample_count': len(self.downstream_handoff),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'shock_boundary': (
        None
        if self.shock_boundary is None
        else self.shock_boundary.as_report()
      ),
      'ambient_march': (
        None if self.ambient_march is None else self.ambient_march.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'chain_termination_decision': (
        self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }


def _failure(
  status: MocEulerAmbientPhysicalFieldStatus,
  *,
  shock_boundary: MocEulerShockBoundaryCurveResult | None,
  ambient_march: MocEulerAmbientBoundaryMarchResult | None,
  field: MocPhysicalPostShockFieldResult | None,
  ambient_pressure_Pa: float | None,
  entropy_residuals: tuple[float, ...] = (),
  message: str,
) -> MocEulerAmbientPhysicalFieldResult:
  return MocEulerAmbientPhysicalFieldResult(
    status=status,
    shock_boundary=shock_boundary,
    ambient_march=ambient_march,
    field=field,
    ambient_pressure_Pa=ambient_pressure_Pa,
    entropy_residuals=entropy_residuals,
    maximum_entropy_residual=max(entropy_residuals, default=None),
    shock_boundary_verified=False,
    ambient_boundary_verified=bool(
      ambient_march is not None and ambient_march.converged
    ),
    entropy_lineage_verified=False,
    physical_field_verified=bool(
      field is not None and field.physical_closure_verified
    ),
    message=message,
  )


def _as_post_shock_fit(
  shock_boundary: MocEulerShockBoundaryCurveResult,
) -> MocShockBoundaryFitResult:
  """Adapt exact shock evidence to the physical assembler's boundary type."""

  return MocShockBoundaryFitResult(
    status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
    boundary_states=tuple(
      MocPostShockBoundaryState(
        point_m=point,
        state=state,
        upstream_total_pressure_Pa=upstream_pressure,
        downstream_total_pressure_Pa=downstream_pressure,
      )
      for point, state, upstream_pressure, downstream_pressure in zip(
        shock_boundary.shock_points_m,
        shock_boundary.downstream_states,
        shock_boundary.upstream_total_pressure_Pa,
        shock_boundary.downstream_total_pressure_Pa,
        strict=True,
      )
    ),
    shock_angle_residuals_rad=shock_boundary.tangent_residuals_rad,
    maximum_shock_angle_residual_rad=(
      shock_boundary.maximum_tangent_residual_rad
    ),
    upstream_states=shock_boundary.upstream_states,
    upstream_total_pressure_Pa=shock_boundary.upstream_total_pressure_Pa,
    message='adapted from exact Euler shock evidence for physical assembly',
  )


def assemble_euler_ambient_physical_field(
  shock_boundary: MocEulerShockBoundaryCurveResult,
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  maximum_boundary_iterations: int = 16,
) -> MocEulerAmbientPhysicalFieldResult:
  """Assemble a reflected exact-Euler field from solver-owned boundaries.

  The exact shock object remains the source of truth for Rankine--Hugoniot
  evidence.  The small adapter to ``MocShockBoundaryFitResult`` exists only
  because the established physical mesh assembler is intentionally shared by
  the research lane; it does not re-fit or replace the exact shock states.
  """

  if not isinstance(shock_boundary, MocEulerShockBoundaryCurveResult):
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.INVALID_INPUT,
      shock_boundary=None,
      ambient_march=None,
      field=None,
      ambient_pressure_Pa=None,
      message='shock_boundary must be a MocEulerShockBoundaryCurveResult',
    )
  try:
    ambient_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
    position_tolerance = float(position_tolerance_m)
    invariant_tolerance_value = float(invariant_tolerance)
    pressure_tolerance_value = float(pressure_tolerance)
    tangent_tolerance_value = float(tangent_tolerance)
  except (TypeError, ValueError):
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.INVALID_INPUT,
      shock_boundary=shock_boundary,
      ambient_march=None,
      field=None,
      ambient_pressure_Pa=None,
      message='ambient physical-field pressures, coordinates, and tolerances must be numeric',
    )
  if not isfinite(ambient_pressure) or ambient_pressure <= 0.0:
    raise ValueError('ambient_pressure_Pa must be finite and positive')
  for name, value in (
    ('position_tolerance_m', position_tolerance),
    ('invariant_tolerance', invariant_tolerance_value),
    ('pressure_tolerance', pressure_tolerance_value),
    ('tangent_tolerance', tangent_tolerance_value),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if not isfinite(target_y):
    raise ValueError('target_centerline_y_m must be finite')
  if isinstance(maximum_boundary_iterations, bool) or maximum_boundary_iterations < 1:
    raise ValueError('maximum_boundary_iterations must be a positive integer')
  if not shock_boundary.converged or not shock_boundary.local_euler_verified:
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary=shock_boundary,
      ambient_march=None,
      field=None,
      ambient_pressure_Pa=ambient_pressure,
      message=(
        'exact physical-field assembly requires a locally Euler-verified '
        f'shock curve: {shock_boundary.message}'
      ),
    )
  if shock_boundary.orientation is not MocEulerShockBoundaryOrientation.MIXED_CHARACTERISTIC_BOUNDARY:
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.SHOCK_BOUNDARY_REQUIRED,
      shock_boundary=shock_boundary,
      ambient_march=None,
      field=None,
      ambient_pressure_Pa=ambient_pressure,
      message=(
        'exact physical-field assembly requires a mixed-characteristic shock '
        'orientation so the shock supplies the downstream C+ sources'
      ),
    )
  try:
    ambient_march = march_euler_ambient_boundary(
      shock_boundary,
      ambient_pressure,
      target_centerline_y_m=target_y,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      maximum_iterations=maximum_boundary_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary=shock_boundary,
      ambient_march=None,
      field=None,
      ambient_pressure_Pa=ambient_pressure,
      message=f'exact ambient boundary march raised: {error}',
    )
  if not ambient_march.converged:
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.AMBIENT_BOUNDARY_FAILURE,
      shock_boundary=shock_boundary,
      ambient_march=ambient_march,
      field=None,
      ambient_pressure_Pa=ambient_pressure,
      message=(
        'exact ambient boundary did not converge before physical-field '
        f'assembly: {ambient_march.message}'
      ),
    )
  entropy_residuals = tuple(
    abs(value - shock_boundary.downstream_total_pressure_Pa[0])
    / shock_boundary.downstream_total_pressure_Pa[0]
    for value in shock_boundary.downstream_total_pressure_Pa
  )
  maximum_entropy_residual = max(entropy_residuals, default=0.0)
  entropy_lineage_verified = maximum_entropy_residual <= pressure_tolerance_value
  try:
    field = assemble_ambient_boundary_post_shock_field_with_centerline_reflection(
      _as_post_shock_fit(shock_boundary),
      tuple(
        MocAmbientBoundarySample(
          point_m=sample.point_m,
          state=sample.state,
          total_pressure_Pa=sample.total_pressure_Pa,
        )
        for sample in ambient_march.boundary_samples
      ),
      ambient_pressure,
      position_tolerance_m=position_tolerance,
      invariant_tolerance=invariant_tolerance_value,
      pressure_tolerance=pressure_tolerance_value,
      tangent_tolerance=tangent_tolerance_value,
      allow_zero_strength_shock_start=(
        shock_boundary.zero_strength_endpoints_allowed
      ),
      allow_zero_strength_endpoints=(
        shock_boundary.zero_strength_endpoints_allowed
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.FIELD_FAILURE,
      shock_boundary=shock_boundary,
      ambient_march=ambient_march,
      field=None,
      ambient_pressure_Pa=ambient_pressure,
      entropy_residuals=entropy_residuals,
      message=f'exact Euler physical-field assembly raised: {error}',
    )
  if not field.converged or not field.physical_closure_verified:
    return _failure(
      MocEulerAmbientPhysicalFieldStatus.FIELD_FAILURE,
      shock_boundary=shock_boundary,
      ambient_march=ambient_march,
      field=field,
      ambient_pressure_Pa=ambient_pressure,
      entropy_residuals=entropy_residuals,
      message=(
        'exact shock and ambient boundaries assembled, but the reflected '
        f'physical field did not pass closure gates: {field.message}'
      ),
    )
  return MocEulerAmbientPhysicalFieldResult(
    status=MocEulerAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
    shock_boundary=shock_boundary,
    ambient_march=ambient_march,
    field=field,
    ambient_pressure_Pa=ambient_pressure,
    entropy_residuals=entropy_residuals,
    maximum_entropy_residual=maximum_entropy_residual,
    shock_boundary_verified=True,
    ambient_boundary_verified=True,
    entropy_lineage_verified=entropy_lineage_verified,
    physical_field_verified=True,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'exact Euler shock, solver-owned ambient boundary, and centerline '
      'reflection formed a bounded physical-field candidate; independent '
      'cell conservation/refinement and production validation remain pending'
    ),
  )
