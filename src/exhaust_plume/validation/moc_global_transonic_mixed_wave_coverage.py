"""Geometry coverage audit for the mixed-wave-to-field handoff.

The local mixed-wave interface and the solver-owned transonic field placement
are separate research seams.  This module records whether the retained shock
and ambient boundary traces actually span the selected field cross-section.
It never extends, extrapolates, or invents a connecting surface; an uncovered
placement remains an explicit joint-closure blocker.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementResult,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_interface import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
)

__all__ = (
  'MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage',
  'assess_reflected_domain_global_transonic_mixed_wave_interface_coverage',
)


DEFAULT_POSITION_TOLERANCE_M = 1.0e-9


class MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus(
  str,
  Enum,
):
  """Typed outcome of the interface-to-placement coverage audit."""

  CONVERGED_COVERAGE = (
    'converged-global-transonic-mixed-wave-interface-coverage'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_GEOMETRY_REQUIRED = (
    'global-transonic-mixed-wave-interface-geometry-required'
  )
  PLACEMENT_REQUIRED = 'global-transonic-mixed-wave-placement-required'
  PLACEMENT_UPSTREAM_OF_TERMINAL = (
    'global-transonic-mixed-wave-placement-upstream-of-terminal'
  )
  PLACEMENT_OUTSIDE_INTERFACE = (
    'global-transonic-mixed-wave-placement-outside-interface'
  )


def _finite(name: str, value: object) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric):
    raise ValueError(f'{name} must be finite')
  ####
  return numeric


def _x_extent(points: tuple[tuple[float, float], ...]) -> tuple[float, float]:
  if not points:
    raise ValueError('boundary trace must contain at least one point')
  ####
  coordinates = tuple(
    _finite('boundary point x coordinate', point[0])
    for point in points
  )
  return min(coordinates), max(coordinates)


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage:
  """Retained coverage evidence for one exact interface/placement pair."""

  status: MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
  interface_x_min_m: float | None = None
  interface_x_max_m: float | None = None
  shock_boundary_x_max_m: float | None = None
  ambient_boundary_x_max_m: float | None = None
  limiting_boundary_x_max_m: float | None = None
  terminal_x_m: float | None = None
  placement_x_m: float | None = None
  downstream_gap_m: float | None = None
  shock_boundary_sample_count: int = 0
  ambient_boundary_sample_count: int = 0
  placement_sample_count: int = 0
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus'
      )
    ####
    tolerance = _finite('position_tolerance_m', self.position_tolerance_m)
    if tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be positive')
    ####
    object.__setattr__(self, 'position_tolerance_m', tolerance)
    ####
    for name in (
      'interface_x_min_m',
      'interface_x_max_m',
      'shock_boundary_x_max_m',
      'ambient_boundary_x_max_m',
      'limiting_boundary_x_max_m',
      'terminal_x_m',
      'placement_x_m',
      'downstream_gap_m',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = _finite(name, value)
      if name == 'downstream_gap_m' and numeric < 0.0:
        raise ValueError('downstream_gap_m must be nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'shock_boundary_sample_count',
      'ambient_boundary_sample_count',
      'placement_sample_count',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if (
      self.interface_x_min_m is not None
      and self.interface_x_max_m is not None
      and self.interface_x_max_m < self.interface_x_min_m
    ):
      raise ValueError('interface x extent must be ordered')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether both retained boundaries span the selected placement."""

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .CONVERGED_COVERAGE
      and self.shock_boundary_x_max_m is not None
      and self.ambient_boundary_x_max_m is not None
      and self.limiting_boundary_x_max_m is not None
      and self.terminal_x_m is not None
      and self.placement_x_m is not None
      and self.downstream_gap_m == 0.0
    )
  ####

  @property
  def joint_interface_coverage_verified(self) -> bool:
    """Whether the joint geometry gate passed without an extension law."""

    return self.converged
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Coverage evidence never promotes a downstream chain."""

    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """This research audit cannot authorize production claims."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': (
        'research-global-transonic-mixed-wave-interface-coverage-v1'
      ),
      'status': self.status.value,
      'converged': self.converged,
      'joint_interface_coverage_verified': (
        self.joint_interface_coverage_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'interface_x_min_m': self.interface_x_min_m,
      'interface_x_max_m': self.interface_x_max_m,
      'shock_boundary_x_max_m': self.shock_boundary_x_max_m,
      'ambient_boundary_x_max_m': self.ambient_boundary_x_max_m,
      'limiting_boundary_x_max_m': self.limiting_boundary_x_max_m,
      'terminal_x_m': self.terminal_x_m,
      'placement_x_m': self.placement_x_m,
      'downstream_gap_m': self.downstream_gap_m,
      'shock_boundary_sample_count': self.shock_boundary_sample_count,
      'ambient_boundary_sample_count': self.ambient_boundary_sample_count,
      'placement_sample_count': self.placement_sample_count,
      'position_tolerance_m': self.position_tolerance_m,
      'message': self.message,
    }
  ####


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus,
  message: str,
  *,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
  **fields: Any,
) -> MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage:
  return MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage(
    status=status,
    position_tolerance_m=position_tolerance_m,
    message=message,
    **fields,
  )


def assess_reflected_domain_global_transonic_mixed_wave_interface_coverage(
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  placement: MocTransonicShockInterfaceFieldPlacementResult,
  *,
  position_tolerance_m: float = DEFAULT_POSITION_TOLERANCE_M,
) -> MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage:
  """Measure exact shock/ambient trace coverage at one field placement.

  The placement is considered covered only when both the retained shock trace
  and the independently marched ambient trace reach its cross-section.  The
  function deliberately returns a typed gap when they do not; it does not
  extrapolate either trace or infer a missing surface.
  """

  try:
    tolerance = _finite('position_tolerance_m', position_tolerance_m)
    if tolerance <= 0.0:
      raise ValueError('position_tolerance_m must be positive')
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INVALID_INPUT,
      f'coverage tolerance is invalid: {error}',
    )
  ####
  if not isinstance(
    interface,
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INVALID_INPUT,
      'interface must be a typed global transonic mixed-wave interface result',
      position_tolerance_m=tolerance,
    )
  ####
  if not isinstance(
    placement,
    MocTransonicShockInterfaceFieldPlacementResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INVALID_INPUT,
      'placement must be a typed transonic field placement result',
      position_tolerance_m=tolerance,
    )
  ####
  if not interface.local_interface_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INTERFACE_GEOMETRY_REQUIRED,
      'coverage requires the local mixed-wave interface gates to pass',
      position_tolerance_m=tolerance,
    )
  ####
  ambient_boundary = interface.ambient_boundary
  shock_ambient_strip = interface.shock_ambient_strip
  perimeter_request = interface.perimeter_request
  if (
    ambient_boundary is None
    or not interface.ambient_boundary_verified
    or shock_ambient_strip is None
    or not interface.shock_ambient_strip_verified
    or perimeter_request is None
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INTERFACE_GEOMETRY_REQUIRED,
      'the exact interface retained no verified shock/ambient characteristic '
      'strip and terminal geometry',
      position_tolerance_m=tolerance,
    )
  ####
  placement_x = placement.cross_section_x_m
  if (
    not placement.converged
    or placement_x is None
    or not placement.sample_points_m
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .PLACEMENT_REQUIRED,
      'coverage requires a converged solver-owned placement with a cross-section',
      position_tolerance_m=tolerance,
      placement_sample_count=len(placement.sample_points_m),
    )
  ####
  shock_points = tuple(shock_ambient_strip.shock_boundary_points_m)
  ambient_points = tuple(shock_ambient_strip.ambient_boundary_points_m)
  if not shock_points or not ambient_points:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INTERFACE_GEOMETRY_REQUIRED,
      'the exact interface must retain nonempty shock and ambient traces '
      'before coverage can be assessed',
      position_tolerance_m=tolerance,
      shock_boundary_sample_count=len(shock_points),
      ambient_boundary_sample_count=len(ambient_points),
      placement_sample_count=len(placement.sample_points_m),
    )
  ####
  try:
    shock_x_min, shock_x_max = _x_extent(shock_points)
    ambient_x_min, ambient_x_max = _x_extent(ambient_points)
    terminal_x = _finite(
      'terminal x coordinate',
      perimeter_request.terminal_point_m[0],
    )
    placement_x = _finite('placement x coordinate', placement_x)
  except (IndexError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .INTERFACE_GEOMETRY_REQUIRED,
      f'interface geometry could not be measured: {error}',
      position_tolerance_m=tolerance,
      shock_boundary_sample_count=len(shock_points),
      ambient_boundary_sample_count=len(ambient_points),
      placement_sample_count=len(placement.sample_points_m),
    )
  ####
  interface_x_min = min(shock_x_min, ambient_x_min, terminal_x)
  interface_x_max = max(shock_x_max, ambient_x_max, terminal_x)
  limiting_x_max = min(shock_x_max, ambient_x_max)
  downstream_gap = max(0.0, placement_x - limiting_x_max)
  common_fields = {
    'interface_x_min_m': interface_x_min,
    'interface_x_max_m': interface_x_max,
    'shock_boundary_x_max_m': shock_x_max,
    'ambient_boundary_x_max_m': ambient_x_max,
    'limiting_boundary_x_max_m': limiting_x_max,
    'terminal_x_m': terminal_x,
    'placement_x_m': placement_x,
    'downstream_gap_m': downstream_gap,
    'shock_boundary_sample_count': len(shock_points),
    'ambient_boundary_sample_count': len(ambient_points),
    'placement_sample_count': len(placement.sample_points_m),
    'position_tolerance_m': tolerance,
  }
  ####
  if placement_x < terminal_x - tolerance:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .PLACEMENT_UPSTREAM_OF_TERMINAL,
      'solver-owned field placement lies upstream of the exact mixed-wave '
      'terminal; the downstream handoff ordering is not verified',
      **common_fields,
    )
  ####
  if downstream_gap > tolerance:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .PLACEMENT_OUTSIDE_INTERFACE,
      'the solver-owned field placement lies beyond the shorter exact shock '
      f'and ambient traces by {downstream_gap:.6g} m; no connecting surface '
      'or endpoint extension was inferred',
      **common_fields,
    )
  ####
  converged_fields = dict(common_fields)
  converged_fields['downstream_gap_m'] = 0.0
  return MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage(
    status=(
      MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverageStatus
      .CONVERGED_COVERAGE
    ),
    **converged_fields,
    message=(
      'both exact shock and ambient traces span the solver-owned placement; '
      'this geometry audit remains research-only and does not close the field'
    ),
  )
