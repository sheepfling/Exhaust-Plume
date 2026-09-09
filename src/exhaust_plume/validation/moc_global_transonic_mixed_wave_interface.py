"""Solver-owned mixed-wave interface evidence below the canonical MOC lane.

This module is deliberately narrower than a global transonic closure.  It
consumes one exact, locally verified entropy-carrying characteristic field,
matches a local signed-wave path to the requested ambient pressure, and uses
that result to drive a solver-generated shock trace.  The trace is then
continued to a typed subsonic terminal and an independently marched ambient
boundary.

The downstream angle profile is an explicit research law: linear interpolation
from the pressure-targeted outer turn to the requested centerline turn.  It is
solver-owned and checked, but it is not a physical global feedback solution.
The result therefore remains below chain promotion and production claims.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientShockBoundaryMarchResult,
  march_post_shock_ambient_boundary,
)
from exhaust_plume.models.moc.chain import MocChainBoundarySample
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
)
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  solve_marched_attached_shock_field,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeFreeBoundaryResult,
  MocMixedRegimePerimeterRequest,
  solve_mixed_regime_downstream_free_boundary,
)
from exhaust_plume.models.moc.mixed_wave import (
  MocMixedWavePathResult,
  solve_mixed_wave_pressure_target_path,
)
from exhaust_plume.models.moc.post_shock import (
  MocShockBoundaryFitResult,
  fit_attached_shock_boundary,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_INTERFACE_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult',
  'solve_reflected_domain_global_transonic_mixed_wave_interface',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_INTERFACE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-interface'
)
DEFAULT_POSITION_TOLERANCE_M = 1.0e-10
DEFAULT_INVARIANT_TOLERANCE = 1.0e-10
DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD = 2.0e-2
DEFAULT_PRESSURE_TOLERANCE = 1.0e-8


class MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus(str, Enum):
  """Typed outcome of one local mixed-wave interface attempt."""

  CONVERGED_RESEARCH_TERMINAL = (
    'converged-research-global-transonic-mixed-wave-terminal'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_FIELD_FAILURE = 'global-transonic-mixed-wave-source-field-failure'
  PRESSURE_TARGET_FAILURE = (
    'global-transonic-mixed-wave-pressure-target-failure'
  )
  ANGLE_LAW_FAILURE = 'global-transonic-mixed-wave-angle-law-failure'
  SHOCK_FAILURE = 'global-transonic-mixed-wave-shock-failure'
  SHOCK_FIT_FAILURE = 'global-transonic-mixed-wave-shock-fit-failure'
  AMBIENT_BOUNDARY_FAILURE = (
    'global-transonic-mixed-wave-ambient-boundary-failure'
  )
  MIXED_REGIME_TERMINAL_REQUIRED = (
    'global-transonic-mixed-wave-terminal-required'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult:
  """Research-only local interface evidence with explicit claim gates."""

  status: MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus
  source_field: (
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None
  )
  ambient_pressure_Pa: float | None
  target_centerline_y_m: float
  target_centerline_flow_angle_rad: float
  frontier: tuple[MocChainBoundarySample, ...] = ()
  mixed_wave_path: MocMixedWavePathResult | None = None
  downstream_flow_angles_rad: tuple[float, ...] = ()
  shock: MocFreeBoundaryShockResult | None = None
  shock_fit: MocShockBoundaryFitResult | None = None
  ambient_boundary: MocAmbientShockBoundaryMarchResult | None = None
  perimeter_request: MocMixedRegimePerimeterRequest | None = None
  subsonic_reference: MocMixedRegimeFreeBoundaryResult | None = None
  effective_inlet_height_m: float | None = None
  downstream_length_m: float | None = None
  source_field_consumed: bool = False
  frontier_verified: bool = False
  pressure_target_verified: bool = False
  angle_law_verified: bool = False
  shock_geometry_verified: bool = False
  shock_fit_verified: bool = False
  ambient_boundary_verified: bool = False
  terminal_verified: bool = False
  subsonic_reference_verified: bool = False
  centerline_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus,
    ):
      raise TypeError('status must be a typed mixed-wave interface status')
    ####
    if self.source_field is not None and not isinstance(
      self.source_field,
      MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
    ):
      raise TypeError('source_field must be a typed characteristic field or None')
    ####
    if self.ambient_pressure_Pa is not None:
      pressure = float(self.ambient_pressure_Pa)
      if not isfinite(pressure) or pressure <= 0.0:
        raise ValueError('ambient_pressure_Pa must be finite and positive')
      ####
      object.__setattr__(self, 'ambient_pressure_Pa', pressure)
    ####
    for name in (
      'target_centerline_y_m',
      'target_centerline_flow_angle_rad',
    ):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      ####
      object.__setattr__(self, name, value)
    ####
    frontier = tuple(self.frontier)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in frontier):
      raise TypeError('frontier must contain MocChainBoundarySample values')
    ####
    object.__setattr__(self, 'frontier', frontier)
    angles = tuple(float(value) for value in self.downstream_flow_angles_rad)
    if any(not isfinite(value) for value in angles):
      raise ValueError('downstream_flow_angles_rad must be finite')
    ####
    object.__setattr__(self, 'downstream_flow_angles_rad', angles)
    ####
    for name, expected_type in (
      ('mixed_wave_path', MocMixedWavePathResult),
      ('shock', MocFreeBoundaryShockResult),
      ('shock_fit', MocShockBoundaryFitResult),
      ('ambient_boundary', MocAmbientShockBoundaryMarchResult),
      ('perimeter_request', MocMixedRegimePerimeterRequest),
      ('subsonic_reference', MocMixedRegimeFreeBoundaryResult),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} must be {expected_type.__name__} or None')
      ####
    ####
    for name in ('effective_inlet_height_m', 'downstream_length_m'):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'source_field_consumed',
      'frontier_verified',
      'pressure_target_verified',
      'angle_law_verified',
      'shock_geometry_verified',
      'shock_fit_verified',
      'ambient_boundary_verified',
      'terminal_verified',
      'subsonic_reference_verified',
      'centerline_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('mixed-wave interface evidence must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('mixed-wave interface evidence cannot allow production claims')
    ####
    if self.pressure_target_verified and (
      self.mixed_wave_path is None or not self.mixed_wave_path.converged
    ):
      raise ValueError(
        'pressure_target_verified requires a converged mixed-wave path'
      )
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def terminal_model_verified(self) -> bool:
    """Whether the retained shock result carries a typed subsonic terminal."""

    return bool(
      self.terminal_verified
      and self.shock is not None
      and self.shock.normal_shock_terminal is not None
      and self.shock.normal_shock_terminal.subsonic
    )
  ####

  @property
  def local_interface_verified(self) -> bool:
    """Whether all local evidence needed for this research seam passed."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus
      .CONVERGED_RESEARCH_TERMINAL
      and self.source_field_consumed
      and self.frontier_verified
      and self.pressure_target_verified
      and self.angle_law_verified
      and self.shock_geometry_verified
      and self.shock_fit_verified
      and self.ambient_boundary_verified
      and self.terminal_model_verified
      and self.chain_promotion_blocked
      and not self.centerline_boundary_verified
      and not self.global_coupling_verified
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_INTERFACE_OPERATOR_ID,
      'status': self.status.value,
      'local_interface_verified': self.local_interface_verified,
      'terminal_model_verified': self.terminal_model_verified,
      'source_field_consumed': self.source_field_consumed,
      'frontier_verified': self.frontier_verified,
      'pressure_target_verified': self.pressure_target_verified,
      'angle_law_verified': self.angle_law_verified,
      'shock_geometry_verified': self.shock_geometry_verified,
      'shock_fit_verified': self.shock_fit_verified,
      'ambient_boundary_verified': self.ambient_boundary_verified,
      'terminal_verified': self.terminal_verified,
      'subsonic_reference_verified': self.subsonic_reference_verified,
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'target_centerline_y_m': self.target_centerline_y_m,
      'target_centerline_flow_angle_rad': self.target_centerline_flow_angle_rad,
      'frontier': [
        {
          'point_m': sample.point_m,
          'mach': sample.state.mach,
          'flow_angle_rad': sample.state.theta_rad,
          'total_pressure_Pa': sample.total_pressure_Pa,
        }
        for sample in self.frontier
      ],
      'downstream_flow_angles_rad': self.downstream_flow_angles_rad,
      'mixed_wave_path': (
        None if self.mixed_wave_path is None else self.mixed_wave_path.as_report()
      ),
      'shock': None if self.shock is None else self.shock.as_report(),
      'shock_fit': (
        None if self.shock_fit is None else {
          'converged': self.shock_fit.converged,
          'sample_count': len(self.shock_fit.boundary_states),
          'maximum_shock_angle_residual_rad': (
            self.shock_fit.maximum_shock_angle_residual_rad
          ),
          'message': self.shock_fit.message,
        }
      ),
      'ambient_boundary': (
        None
        if self.ambient_boundary is None
        else self.ambient_boundary.as_report()
      ),
      'perimeter_request': (
        None
        if self.perimeter_request is None
        else {
          'source': self.perimeter_request.source,
          'terminal_point_m': self.perimeter_request.terminal_point_m,
          'terminal_downstream_mach': (
            self.perimeter_request.terminal_downstream_mach
          ),
          'terminal_downstream_pressure_Pa': (
            self.perimeter_request.terminal_downstream_pressure_Pa
          ),
          'terminal_downstream_total_pressure_Pa': (
            self.perimeter_request.terminal_downstream_total_pressure_Pa
          ),
          'supersonic_patch_sample_count': len(
            self.perimeter_request.supersonic_patch
          ),
        }
      ),
      'subsonic_reference': (
        None
        if self.subsonic_reference is None
        else self.subsonic_reference.as_report()
      ),
      'effective_inlet_height_m': self.effective_inlet_height_m,
      'downstream_length_m': self.downstream_length_m,
      'claim_status': (
        'research-only local mixed-wave terminal; centerline boundary, '
        'global feedback, physical shock-cell promotion, external validation, '
        'and production claims remain blocked'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus,
  *,
  source_field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None,
  ambient_pressure_Pa: float | None,
  target_centerline_y_m: float,
  target_centerline_flow_angle_rad: float,
  frontier: tuple[MocChainBoundarySample, ...] = (),
  mixed_wave_path: MocMixedWavePathResult | None = None,
  downstream_flow_angles_rad: tuple[float, ...] = (),
  shock: MocFreeBoundaryShockResult | None = None,
  shock_fit: MocShockBoundaryFitResult | None = None,
  ambient_boundary: MocAmbientShockBoundaryMarchResult | None = None,
  perimeter_request: MocMixedRegimePerimeterRequest | None = None,
  subsonic_reference: MocMixedRegimeFreeBoundaryResult | None = None,
  effective_inlet_height_m: float | None = None,
  downstream_length_m: float | None = None,
  source_field_consumed: bool = False,
  frontier_verified: bool = False,
  pressure_target_verified: bool = False,
  angle_law_verified: bool = False,
  shock_geometry_verified: bool = False,
  shock_fit_verified: bool = False,
  ambient_boundary_verified: bool = False,
  terminal_verified: bool = False,
  subsonic_reference_verified: bool = False,
  message: str,
) -> MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult:
  return MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult(
    status=status,
    source_field=source_field,
    ambient_pressure_Pa=ambient_pressure_Pa,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    frontier=frontier,
    mixed_wave_path=mixed_wave_path,
    downstream_flow_angles_rad=downstream_flow_angles_rad,
    shock=shock,
    shock_fit=shock_fit,
    ambient_boundary=ambient_boundary,
    perimeter_request=perimeter_request,
    subsonic_reference=subsonic_reference,
    effective_inlet_height_m=effective_inlet_height_m,
    downstream_length_m=downstream_length_m,
    source_field_consumed=source_field_consumed,
    frontier_verified=frontier_verified,
    pressure_target_verified=pressure_target_verified,
    angle_law_verified=angle_law_verified,
    shock_geometry_verified=shock_geometry_verified,
    shock_fit_verified=shock_fit_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    terminal_verified=terminal_verified,
    subsonic_reference_verified=subsonic_reference_verified,
    message=message,
  )
####


def solve_reflected_domain_global_transonic_mixed_wave_interface(
  source_field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ambient_pressure_Pa: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 10,
  branch: ShockBranch = ShockBranch.WEAK,
  effective_inlet_height_m: float | None = None,
  downstream_length_m: float | None = None,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  invariant_tolerance: float = DEFAULT_INVARIANT_TOLERANCE,
  shock_angle_tolerance_rad: float = DEFAULT_SHOCK_ANGLE_TOLERANCE_RAD,
  pressure_tolerance: float = DEFAULT_PRESSURE_TOLERANCE,
) -> MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult:
  """Generate one exact-source mixed-wave interface candidate.

  The optional effective inlet height and downstream length run the scalar
  subsonic reference only.  They are intentionally not inferred from the
  terminal point and cannot make local_interface_verified claim a closed
  centerline or global boundary.
  """

  status_type = MocReflectedDomainGlobalTransonicMixedWaveInterfaceStatus
  try:
    target_pressure = float(ambient_pressure_Pa)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
  except (TypeError, ValueError):
    return _failure(
      status_type.INVALID_INPUT,
      source_field=(
        source_field
        if isinstance(
          source_field,
          MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
        )
        else None
      ),
      ambient_pressure_Pa=None,
      target_centerline_y_m=0.0,
      target_centerline_flow_angle_rad=0.0,
      message='ambient pressure and centerline targets must be numeric',
    )
  ####
  if not isfinite(target_pressure) or target_pressure <= 0.0:
    return _failure(
      status_type.INVALID_INPUT,
      source_field=source_field,
      ambient_pressure_Pa=None,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message='ambient_pressure_Pa must be finite and positive',
    )
  ####
  if not isfinite(target_y) or not isfinite(target_angle):
    return _failure(
      status_type.INVALID_INPUT,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message='centerline targets must be finite',
    )
  ####
  if target_y != 0.0 or abs(target_angle) > 1.0e-12:
    return _failure(
      status_type.INVALID_INPUT,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message=(
        'the reflected-domain research interface currently requires the '
        'symmetry line and zero centerline flow angle'
      ),
    )
  ####
  if (
    isinstance(sample_count, bool)
    or not isinstance(sample_count, int)
    or sample_count < 3
  ):
    return _failure(
      status_type.INVALID_INPUT,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message='sample_count must be an integer greater than or equal to three',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _failure(
      status_type.INVALID_INPUT,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message='branch must be a ShockBranch',
    )
  ####
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('pressure_tolerance', pressure_tolerance),
  ):
    numeric = float(value)
    if not isfinite(numeric) or numeric <= 0.0:
      return _failure(
        status_type.INVALID_INPUT,
        source_field=source_field,
        ambient_pressure_Pa=target_pressure,
        target_centerline_y_m=target_y,
        target_centerline_flow_angle_rad=target_angle,
        message=f'{name} must be finite and positive',
      )
    ####
  ####
  if (effective_inlet_height_m is None) != (downstream_length_m is None):
    return _failure(
      status_type.INVALID_INPUT,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message=(
        'effective_inlet_height_m and downstream_length_m must be supplied '
        'together for the optional scalar reference'
      ),
    )
  ####
  if effective_inlet_height_m is not None:
    for name, value in (
      ('effective_inlet_height_m', effective_inlet_height_m),
      ('downstream_length_m', downstream_length_m),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        return _failure(
          status_type.INVALID_INPUT,
          source_field=source_field,
          ambient_pressure_Pa=target_pressure,
          target_centerline_y_m=target_y,
          target_centerline_flow_angle_rad=target_angle,
          message=f'{name} must be finite and positive when supplied',
        )
      ####
  ####
  if not isinstance(
    source_field,
    MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  ):
    return _failure(
      status_type.SOURCE_FIELD_FAILURE,
      source_field=None,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      message='source_field must be a typed entropy-characteristic field',
    )
  ####
  frontier = tuple(source_field.continuation_boundary)
  frontier_verified = bool(
    source_field.converged
    and source_field.local_consistency_verified
    and source_field.state_sampling_available
    and source_field.continuation_boundary_verified
    and len(frontier) >= 3
    and all(
      current.state.x_m > previous.state.x_m + position_tolerance_m
      for previous, current in zip(frontier, frontier[1:])
    )
  )
  source_field_consumed = bool(
    source_field.local_consistency_verified
    and source_field.state_sampling_available
  )
  if not source_field_consumed or not frontier_verified:
    return _failure(
      status_type.SOURCE_FIELD_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      message=(
        'source field must pass local consistency, bounded sampling, and '
        'explicit downstream frontier gates'
      ),
    )
  ####
  try:
    source_pressures: list[float] = []
    for sample in frontier:
      pressure = source_field.static_pressure_at(
        sample.point_m,
        position_tolerance_m=position_tolerance_m,
      )
      if pressure is None:
        raise ValueError('source field returned no frontier pressure')
      ####
      numeric_pressure = float(pressure)
      if not isfinite(numeric_pressure) or numeric_pressure <= 0.0:
        raise ValueError('source field returned a nonphysical frontier pressure')
      ####
      source_pressures.append(numeric_pressure)
    ####
    mixed_wave_path = solve_mixed_wave_pressure_target_path(
      tuple(sample.state for sample in frontier),
      tuple(source_pressures),
      target_pressure,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.PRESSURE_TARGET_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      message=f'pressure-target mixed-wave path failed: {error}',
    )
  ####
  pressure_target_verified = bool(mixed_wave_path.converged)
  if not pressure_target_verified or not mixed_wave_path.samples:
    return _failure(
      status_type.PRESSURE_TARGET_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      message=(
        'pressure-target path did not produce a converged solver-owned '
        'interface law'
      ),
    )
  ####
  outer_angle = mixed_wave_path.samples[0].target_flow_angle_rad
  start_point = frontier[0].point_m
  if outer_angle is None or not isfinite(float(outer_angle)):
    return _failure(
      status_type.ANGLE_LAW_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      message='pressure-target path exposed no finite outer flow angle',
    )
  ####
  start_y = float(start_point[1])
  if not isfinite(start_y) or start_y <= target_y + position_tolerance_m:
    return _failure(
      status_type.ANGLE_LAW_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      message='frontier outer point must lie strictly above the centerline',
    )
  ####
  def downstream_angle_at(_index: int, point_m: tuple[float, float]) -> float:
    fraction = max(
      0.0,
      min(1.0, (float(point_m[1]) - target_y) / (start_y - target_y)),
    )
    return target_angle + (float(outer_angle) - target_angle) * fraction
  ####
  try:
    angle_samples = tuple(
      downstream_angle_at(index, sample.point_m)
      for index, sample in enumerate(frontier)
    )
    angle_law_verified = bool(
      all(isfinite(value) for value in angle_samples)
      and abs(downstream_angle_at(0, start_point) - float(outer_angle))
      <= shock_angle_tolerance_rad
      and abs(
        downstream_angle_at(sample_count, (start_point[0], target_y))
        - target_angle
      )
      <= shock_angle_tolerance_rad
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    angle_samples = ()
    angle_law_verified = False
    angle_law_error = str(error)
  else:
    angle_law_error = ''
  ####
  if not angle_law_verified:
    return _failure(
      status_type.ANGLE_LAW_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      message=(
        'solver-owned shock-turn law failed its endpoint checks'
        + (f': {angle_law_error}' if angle_law_error else '')
      ),
    )
  ####
  try:
    shock = solve_marched_attached_shock_field(
      source_field.state_at,
      source_field.static_pressure_at,
      start_point,
      target_centerline_y_m=target_y,
      downstream_flow_angle_at=downstream_angle_at,
      incoming_handoff=frontier,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      allow_zero_strength_start=False,
      allow_zero_strength_endpoints=False,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.SHOCK_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      angle_law_verified=angle_law_verified,
      message=f'solver-owned shock march raised: {error}',
    )
  ####
  shock_geometry_verified = bool(
    len(shock.shock_points_m) >= 3
    and len(shock.shock_points_m) == len(shock.upstream_states)
    and len(shock.shock_points_m) == len(shock.downstream_flow_angles_rad)
  )
  terminal = shock.normal_shock_terminal
  terminal_verified = bool(
    terminal is not None and terminal.converged and terminal.subsonic
  )
  if not shock.subsonic_terminal_required or not terminal_verified:
    return _failure(
      status_type.SHOCK_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      shock=shock,
      shock_geometry_verified=shock_geometry_verified,
      terminal_verified=terminal_verified,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      angle_law_verified=angle_law_verified,
      message=(
        'solver-owned shock march did not retain the required typed '
        f'subsonic terminal: {shock.message}'
      ),
    )
  ####
  shock_fit = shock.shock_fit
  if shock_fit is None:
    try:
      shock_fit = fit_attached_shock_boundary(
        shock.upstream_states,
        shock.upstream_pressure_Pa,
        shock.shock_points_m,
        shock.downstream_flow_angles_rad,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        allow_zero_strength_start=False,
        allow_zero_strength_endpoints=False,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        status_type.SHOCK_FIT_FAILURE,
        source_field=source_field,
        ambient_pressure_Pa=target_pressure,
        target_centerline_y_m=target_y,
        target_centerline_flow_angle_rad=target_angle,
        frontier=frontier,
        mixed_wave_path=mixed_wave_path,
        downstream_flow_angles_rad=angle_samples,
        shock=shock,
        shock_geometry_verified=shock_geometry_verified,
        terminal_verified=terminal_verified,
        source_field_consumed=source_field_consumed,
        frontier_verified=frontier_verified,
        pressure_target_verified=pressure_target_verified,
        angle_law_verified=angle_law_verified,
        message=f'retained shock fit raised: {error}',
      )
  ####
  shock_fit_verified = bool(shock_fit.converged)
  shock_geometry_verified = bool(
    shock_geometry_verified
    and shock_fit_verified
    and shock_fit.maximum_shock_angle_residual_rad is not None
    and isfinite(shock_fit.maximum_shock_angle_residual_rad)
    and shock_fit.maximum_shock_angle_residual_rad <= shock_angle_tolerance_rad
  )
  if not shock_fit_verified:
    return _failure(
      status_type.SHOCK_FIT_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      shock=shock,
      shock_fit=shock_fit,
      shock_geometry_verified=shock_geometry_verified,
      terminal_verified=terminal_verified,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      angle_law_verified=angle_law_verified,
      message=f'shock fit did not pass its boundary gates: {shock_fit.message}',
    )
  ####
  try:
    ambient_boundary = march_post_shock_ambient_boundary(
      shock_fit,
      target_pressure,
      target_centerline_y_m=target_y,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.AMBIENT_BOUNDARY_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      shock=shock,
      shock_fit=shock_fit,
      shock_geometry_verified=shock_geometry_verified,
      shock_fit_verified=shock_fit_verified,
      terminal_verified=terminal_verified,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      angle_law_verified=angle_law_verified,
      message=f'ambient boundary march raised: {error}',
    )
  ####
  ambient_boundary_verified = bool(
    ambient_boundary.converged
    and ambient_boundary.ambient_boundary.physical_closure_verified
  )
  if not ambient_boundary_verified:
    return _failure(
      status_type.AMBIENT_BOUNDARY_FAILURE,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      shock=shock,
      shock_fit=shock_fit,
      ambient_boundary=ambient_boundary,
      shock_geometry_verified=shock_geometry_verified,
      shock_fit_verified=shock_fit_verified,
      terminal_verified=terminal_verified,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      angle_law_verified=angle_law_verified,
      message=(
        'solver-owned ambient boundary did not pass its pressure/tangent '
        f'gates: {ambient_boundary.message}'
      ),
    )
  ####
  assert terminal is not None
  try:
    terminal_values = (
      terminal.shock_point_m,
      terminal.downstream_mach,
      terminal.downstream_flow_angle_rad,
      terminal.downstream_pressure_Pa,
      terminal.downstream_total_pressure_Pa,
      terminal.total_pressure_ratio,
    )
    if any(value is None for value in terminal_values):
      raise ValueError('typed terminal did not expose complete scalar seam values')
    ####
    assert terminal.shock_point_m is not None
    assert terminal.downstream_mach is not None
    assert terminal.downstream_flow_angle_rad is not None
    assert terminal.downstream_pressure_Pa is not None
    assert terminal.downstream_total_pressure_Pa is not None
    assert terminal.total_pressure_ratio is not None
    perimeter_request = MocMixedRegimePerimeterRequest(
      terminal=terminal,
      terminal_point_m=terminal.shock_point_m,
      terminal_downstream_mach=terminal.downstream_mach,
      terminal_downstream_flow_angle_rad=terminal.downstream_flow_angle_rad,
      terminal_downstream_pressure_Pa=terminal.downstream_pressure_Pa,
      terminal_downstream_total_pressure_Pa=terminal.downstream_total_pressure_Pa,
      terminal_total_pressure_ratio=terminal.total_pressure_ratio,
      supersonic_patch=shock_fit.boundary_states,
      source=(
        'solver-owned-global-transonic-mixed-wave-terminal-research-interface'
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.MIXED_REGIME_TERMINAL_REQUIRED,
      source_field=source_field,
      ambient_pressure_Pa=target_pressure,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      frontier=frontier,
      mixed_wave_path=mixed_wave_path,
      downstream_flow_angles_rad=angle_samples,
      shock=shock,
      shock_fit=shock_fit,
      ambient_boundary=ambient_boundary,
      shock_geometry_verified=shock_geometry_verified,
      shock_fit_verified=shock_fit_verified,
      ambient_boundary_verified=ambient_boundary_verified,
      terminal_verified=terminal_verified,
      source_field_consumed=source_field_consumed,
      frontier_verified=frontier_verified,
      pressure_target_verified=pressure_target_verified,
      angle_law_verified=angle_law_verified,
      message=f'mixed-regime perimeter request could not be formed: {error}',
    )
  ####
  subsonic_reference = None
  subsonic_reference_verified = False
  reference_message = ''
  if effective_inlet_height_m is not None and downstream_length_m is not None:
    try:
      subsonic_reference = solve_mixed_regime_downstream_free_boundary(
        perimeter_request,
        ambient_pressure_Pa=target_pressure,
        effective_inlet_height_m=float(effective_inlet_height_m),
        downstream_length_m=float(downstream_length_m),
      )
      subsonic_reference_verified = bool(
        subsonic_reference.converged
        and subsonic_reference.physical_closure_verified
      )
      if not subsonic_reference_verified:
        reference_message = (
          ' optional scalar subsonic reference did not close: '
          f'{subsonic_reference.message}'
        )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      reference_message = f' optional scalar subsonic reference raised: {error}'
  ####
  return MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult(
    status=status_type.CONVERGED_RESEARCH_TERMINAL,
    source_field=source_field,
    ambient_pressure_Pa=target_pressure,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_angle,
    frontier=frontier,
    mixed_wave_path=mixed_wave_path,
    downstream_flow_angles_rad=angle_samples,
    shock=shock,
    shock_fit=shock_fit,
    ambient_boundary=ambient_boundary,
    perimeter_request=perimeter_request,
    subsonic_reference=subsonic_reference,
    effective_inlet_height_m=effective_inlet_height_m,
    downstream_length_m=downstream_length_m,
    source_field_consumed=source_field_consumed,
    frontier_verified=frontier_verified,
    pressure_target_verified=pressure_target_verified,
    angle_law_verified=angle_law_verified,
    shock_geometry_verified=shock_geometry_verified,
    shock_fit_verified=shock_fit_verified,
    ambient_boundary_verified=ambient_boundary_verified,
    terminal_verified=terminal_verified,
    subsonic_reference_verified=subsonic_reference_verified,
    message=(
      'solver-owned pressure-targeted shock/ambient interface reached a '
      'typed subsonic terminal; centerline and global feedback remain open.'
      + reference_message
    ),
  )
####
