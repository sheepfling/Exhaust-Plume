"""Typed scalar handoff for the subsonic side of a planar MOC terminal.

The supersonic MOC lane cannot represent a subsonic downstream state as a
``CharacteristicState``.  This module therefore defines the next, narrower
contract: a caller may provide scalar subsonic samples and an explicitly
closed perimeter after a verified terminal shock.  The validator checks the
shock seam, the open supersonic patch, scalar state validity, pressure
lineage, and perimeter geometry.

This is a boundary handoff, not a subsonic characteristic solver.  A passing
handoff still reports ``physical_closure_verified=False`` and cannot seed a
continued shock-cell chain.  A future mixed-regime solver can consume this
contract and add a real subsonic mesh/field acceptance gate without changing
the supersonic ``CharacteristicState`` type.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import Sequence

from exhaust_plume.models.moc.compression import (
  MocNormalShockTerminalResult,
  MocSubsonicShockBoundaryResult,
)
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState

__all__ = (
  'MocMixedRegimeBoundaryStatus',
  'MocMixedRegimeFieldSample',
  'MocMixedRegimeBoundaryResult',
  'validate_mixed_regime_boundary',
)


class MocMixedRegimeBoundaryStatus(str, Enum):
  """Structured outcome for the scalar mixed-regime boundary handoff."""

  CONVERGED_BOUNDARY_HANDOFF = 'converged_subsonic_boundary_handoff'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'mixed_regime_terminal_failure'
  SUPERSONIC_PATCH_FAILURE = 'supersonic_patch_failure'
  SUBSONIC_FIELD_FAILURE = 'subsonic_field_failure'
  GEOMETRY_FAILURE = 'mixed_regime_geometry_failure'
  PRESSURE_FAILURE = 'mixed_regime_pressure_failure'


@dataclass(frozen=True, slots=True)
class MocMixedRegimeFieldSample:
  """One scalar state sample on a proposed subsonic perimeter.

  This deliberately contains no ``CharacteristicState``.  The scalar fields
  are sufficient for seam and thermodynamic checks, but not for entering the
  supersonic compatibility network.
  """

  point_m: tuple[float, float]
  mach: float
  flow_angle_rad: float
  static_pressure_Pa: float
  total_pressure_Pa: float
  gamma: float

  def __post_init__(self) -> None:
    try:
      point = (float(self.point_m[0]), float(self.point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('mixed-regime sample point must contain two finite coordinates') from None
    if not all(isfinite(value) for value in point):
      raise ValueError('mixed-regime sample point must contain two finite coordinates')
    values = (
      ('mach', self.mach, 0.0, 1.0),
      ('flow_angle_rad', self.flow_angle_rad, None, None),
      ('static_pressure_Pa', self.static_pressure_Pa, 0.0, None),
      ('total_pressure_Pa', self.total_pressure_Pa, 0.0, None),
      ('gamma', self.gamma, 1.0, None),
    )
    for name, raw_value, lower, upper in values:
      value = float(raw_value)
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      if lower is not None and value <= lower:
        raise ValueError(f'{name} must be greater than {lower}')
      if upper is not None and value >= upper:
        raise ValueError(f'{name} must be less than {upper}')
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'mach', float(self.mach))
    object.__setattr__(self, 'flow_angle_rad', float(self.flow_angle_rad))
    object.__setattr__(self, 'static_pressure_Pa', float(self.static_pressure_Pa))
    object.__setattr__(self, 'total_pressure_Pa', float(self.total_pressure_Pa))
    object.__setattr__(self, 'gamma', float(self.gamma))


MocMixedRegimeTerminal = MocNormalShockTerminalResult | MocSubsonicShockBoundaryResult


@dataclass(frozen=True, slots=True)
class MocMixedRegimeBoundaryResult:
  """Validation result for a scalar subsonic perimeter handoff.

  ``converged`` means that the handoff itself passed.  It intentionally does
  not mean that a subsonic field was solved: ``physical_closure_verified`` and
  ``mixed_regime_field_complete`` remain false until a future solver supplies
  and validates a real subsonic mesh.
  """

  status: MocMixedRegimeBoundaryStatus
  terminal: MocMixedRegimeTerminal | None
  supersonic_patch_sample_count: int
  subsonic_samples: tuple[MocMixedRegimeFieldSample, ...]
  perimeter_points_m: tuple[tuple[float, float], ...]
  supersonic_patch_verified: bool
  subsonic_state_samples_verified: bool
  terminal_continuity_verified: bool
  perimeter_geometry_verified: bool
  total_pressure_lineage_verified: bool
  maximum_terminal_mach_residual: float | None
  maximum_terminal_flow_angle_residual_rad: float | None
  maximum_terminal_static_pressure_residual_Pa: float | None
  maximum_terminal_total_pressure_residual_Pa: float | None
  maximum_total_pressure_gain_Pa: float | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF

  @property
  def mixed_regime_field_complete(self) -> bool:
    """Whether a subsonic characteristic/finite-volume field was supplied."""

    return False

  @property
  def physical_closure_verified(self) -> bool:
    """A scalar perimeter handoff is not physical cell closure."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  def as_report(self) -> dict[str, object]:
    terminal_report = None if self.terminal is None else self.terminal.as_report()
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'mixed_regime_field_complete': self.mixed_regime_field_complete,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'supersonic_patch_sample_count': self.supersonic_patch_sample_count,
      'subsonic_sample_count': len(self.subsonic_samples),
      'perimeter_sample_count': len(self.perimeter_points_m),
      'supersonic_patch_verified': self.supersonic_patch_verified,
      'subsonic_state_samples_verified': self.subsonic_state_samples_verified,
      'terminal_continuity_verified': self.terminal_continuity_verified,
      'perimeter_geometry_verified': self.perimeter_geometry_verified,
      'total_pressure_lineage_verified': self.total_pressure_lineage_verified,
      'maximum_terminal_mach_residual': self.maximum_terminal_mach_residual,
      'maximum_terminal_flow_angle_residual_rad': self.maximum_terminal_flow_angle_residual_rad,
      'maximum_terminal_static_pressure_residual_Pa': self.maximum_terminal_static_pressure_residual_Pa,
      'maximum_terminal_total_pressure_residual_Pa': self.maximum_terminal_total_pressure_residual_Pa,
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'terminal': terminal_report,
      'message': self.message,
    }


def _failure(
  status: MocMixedRegimeBoundaryStatus,
  *,
  terminal: MocMixedRegimeTerminal | None = None,
  supersonic_patch_sample_count: int = 0,
  subsonic_samples: Sequence[MocMixedRegimeFieldSample] = (),
  perimeter_points_m: Sequence[tuple[float, float]] = (),
  supersonic_patch_verified: bool = False,
  subsonic_state_samples_verified: bool = False,
  terminal_continuity_verified: bool = False,
  perimeter_geometry_verified: bool = False,
  total_pressure_lineage_verified: bool = False,
  maximum_terminal_mach_residual: float | None = None,
  maximum_terminal_flow_angle_residual_rad: float | None = None,
  maximum_terminal_static_pressure_residual_Pa: float | None = None,
  maximum_terminal_total_pressure_residual_Pa: float | None = None,
  maximum_total_pressure_gain_Pa: float | None = None,
  message: str,
) -> MocMixedRegimeBoundaryResult:
  return MocMixedRegimeBoundaryResult(
    status=status,
    terminal=terminal,
    supersonic_patch_sample_count=supersonic_patch_sample_count,
    subsonic_samples=tuple(subsonic_samples),
    perimeter_points_m=tuple(perimeter_points_m),
    supersonic_patch_verified=supersonic_patch_verified,
    subsonic_state_samples_verified=subsonic_state_samples_verified,
    terminal_continuity_verified=terminal_continuity_verified,
    perimeter_geometry_verified=perimeter_geometry_verified,
    total_pressure_lineage_verified=total_pressure_lineage_verified,
    maximum_terminal_mach_residual=maximum_terminal_mach_residual,
    maximum_terminal_flow_angle_residual_rad=maximum_terminal_flow_angle_residual_rad,
    maximum_terminal_static_pressure_residual_Pa=maximum_terminal_static_pressure_residual_Pa,
    maximum_terminal_total_pressure_residual_Pa=maximum_terminal_total_pressure_residual_Pa,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain_Pa,
    message=message,
  )


def _terminal_scalars(
  terminal: MocMixedRegimeTerminal,
) -> tuple[tuple[float, float], float, float, float, float, float] | None:
  point = terminal.shock_point_m
  mach = terminal.downstream_mach
  flow_angle = terminal.downstream_flow_angle_rad
  static_pressure = terminal.downstream_pressure_Pa
  total_pressure = terminal.downstream_total_pressure_Pa
  upstream_total_pressure = terminal.upstream_total_pressure_Pa
  if (
    point is None
    or mach is None
    or flow_angle is None
    or static_pressure is None
    or total_pressure is None
    or upstream_total_pressure is None
  ):
    return None
  values = (*point, mach, flow_angle, static_pressure, total_pressure, upstream_total_pressure)
  if not all(isfinite(float(value)) for value in values):
    return None
  if mach <= 0.0 or mach >= 1.0:
    return None
  if static_pressure <= 0.0 or total_pressure <= 0.0 or upstream_total_pressure <= 0.0:
    return None
  if total_pressure > upstream_total_pressure:
    return None
  return (
    (float(point[0]), float(point[1])),
    float(mach),
    float(flow_angle),
    float(static_pressure),
    float(total_pressure),
    float(upstream_total_pressure),
  )


def validate_mixed_regime_boundary(
  terminal: MocMixedRegimeTerminal,
  supersonic_patch: Sequence[MocPostShockBoundaryState],
  *,
  supersonic_patch_converged: bool,
  subsonic_samples: Sequence[MocMixedRegimeFieldSample],
  perimeter_points_m: Sequence[tuple[float, float]] | None = None,
  position_tolerance_m: float = 1.0e-10,
  state_tolerance: float = 1.0e-10,
  pressure_tolerance: float = 1.0e-8,
) -> MocMixedRegimeBoundaryResult:
  """Validate a scalar subsonic perimeter without fabricating MOC states.

  The perimeter is an ordered, explicitly closed path.  Its first and last
  samples must reproduce the terminal shock scalar state.  All points must
  lie downstream of that terminal point.  The open supersonic patch is
  validated independently so a passing scalar perimeter cannot hide a gap in
  the preceding shock-side field.
  """

  if not isinstance(terminal, (MocNormalShockTerminalResult, MocSubsonicShockBoundaryResult)):
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      message='terminal must be a normal-shock or attached subsonic boundary result',
    )
  if not isinstance(supersonic_patch_converged, bool):
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      terminal=terminal,
      message='supersonic_patch_converged must be a bool',
    )
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('state_tolerance', state_tolerance),
    ('pressure_tolerance', pressure_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  try:
    patch = tuple(supersonic_patch)
    samples = tuple(subsonic_samples)
  except TypeError:
    return _failure(
      MocMixedRegimeBoundaryStatus.INVALID_INPUT,
      terminal=terminal,
      message='supersonic_patch and subsonic_samples must be iterable',
    )
  if not terminal.converged or not terminal.subsonic:
    return _failure(
      MocMixedRegimeBoundaryStatus.TERMINAL_FAILURE,
      terminal=terminal,
      message='terminal must be a converged subsonic shock boundary',
    )
  scalars = _terminal_scalars(terminal)
  if scalars is None:
    return _failure(
      MocMixedRegimeBoundaryStatus.TERMINAL_FAILURE,
      terminal=terminal,
      message='terminal does not expose a complete finite scalar downstream state',
    )
  terminal_point, terminal_mach, terminal_angle, terminal_pressure, terminal_total_pressure, upstream_total_pressure = scalars

  if not supersonic_patch_converged or not patch:
    return _failure(
      MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      message='a converged open supersonic patch is required before subsonic closure',
    )
  for index, boundary_state in enumerate(patch):
    if not isinstance(boundary_state, MocPostShockBoundaryState):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} is not a MocPostShockBoundaryState',
      )
    state = boundary_state.state
    if state.mach <= 1.0:
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} is not supersonic',
      )
    if (
      abs(state.x_m - boundary_state.point_m[0]) > position_tolerance_m
      or abs(state.y_m - boundary_state.point_m[1]) > position_tolerance_m
    ):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} state coordinates do not match its point',
      )
    if (
      not isfinite(boundary_state.upstream_total_pressure_Pa)
      or not isfinite(boundary_state.downstream_total_pressure_Pa)
      or boundary_state.upstream_total_pressure_Pa <= 0.0
      or boundary_state.downstream_total_pressure_Pa <= 0.0
      or boundary_state.downstream_total_pressure_Pa >= boundary_state.upstream_total_pressure_Pa
    ):
      return _failure(
        MocMixedRegimeBoundaryStatus.SUPERSONIC_PATCH_FAILURE,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        message=f'supersonic patch sample {index} does not carry a strict total-pressure loss',
      )
  patch_verified = True

  if len(samples) < 4:
    return _failure(
      MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=samples,
      message='subsonic perimeter requires at least four scalar samples',
    )
  if any(not isinstance(sample, MocMixedRegimeFieldSample) for sample in samples):
    return _failure(
      MocMixedRegimeBoundaryStatus.SUBSONIC_FIELD_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=tuple(sample for sample in samples if isinstance(sample, MocMixedRegimeFieldSample)),
      message='subsonic_samples must contain MocMixedRegimeFieldSample values',
    )
  points = tuple(samples[index].point_m for index in range(len(samples)))
  if perimeter_points_m is not None:
    try:
      points = tuple((float(point[0]), float(point[1])) for point in perimeter_points_m)
    except (IndexError, TypeError, ValueError):
      return _failure(
        MocMixedRegimeBoundaryStatus.INVALID_INPUT,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        supersonic_patch_verified=patch_verified,
        subsonic_samples=samples,
        message='perimeter_points_m must contain finite two-coordinate points',
      )
    if len(points) != len(samples) or any(not all(isfinite(value) for value in point) for point in points):
      return _failure(
        MocMixedRegimeBoundaryStatus.INVALID_INPUT,
        terminal=terminal,
        supersonic_patch_sample_count=len(patch),
        supersonic_patch_verified=patch_verified,
        subsonic_samples=samples,
        perimeter_points_m=points,
        message='perimeter_points_m must match the scalar sample count and be finite',
      )
  if len(points) < 4:
    return _failure(
      MocMixedRegimeBoundaryStatus.GEOMETRY_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_samples=samples,
      perimeter_points_m=points,
      message='subsonic perimeter requires at least four geometry points',
    )

  closed = hypot(points[-1][0] - points[0][0], points[-1][1] - points[0][1]) <= position_tolerance_m
  downstream = all(point[0] >= terminal_point[0] - position_tolerance_m for point in points)
  distinct_segments = all(
    hypot(second[0] - first[0], second[1] - first[1]) > position_tolerance_m
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  terminal_geometry_residual = max(
    hypot(points[0][0] - terminal_point[0], points[0][1] - terminal_point[1]),
    hypot(points[-1][0] - terminal_point[0], points[-1][1] - terminal_point[1]),
  )
  geometry_verified = closed and downstream and distinct_segments and terminal_geometry_residual <= position_tolerance_m
  if not geometry_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.GEOMETRY_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      perimeter_geometry_verified=False,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=None,
      maximum_terminal_flow_angle_residual_rad=None,
      maximum_terminal_static_pressure_residual_Pa=None,
      maximum_terminal_total_pressure_residual_Pa=None,
      maximum_total_pressure_gain_Pa=None,
      message=(
        'subsonic perimeter must be a distinct explicitly closed downstream '
        f'path anchored at the terminal point; closed={closed}, downstream={downstream}, '
        f'distinct_segments={distinct_segments}, terminal_residual_m={terminal_geometry_residual}'
      ),
    )

  seam_samples = (samples[0], samples[-1])
  mach_residual = max(abs(sample.mach - terminal_mach) for sample in seam_samples)
  angle_residual = max(abs(sample.flow_angle_rad - terminal_angle) for sample in seam_samples)
  static_residual = max(abs(sample.static_pressure_Pa - terminal_pressure) for sample in seam_samples)
  total_residual = max(abs(sample.total_pressure_Pa - terminal_total_pressure) for sample in seam_samples)
  seam_verified = (
    mach_residual <= state_tolerance
    and angle_residual <= state_tolerance
    and static_residual <= pressure_tolerance * max(1.0, abs(terminal_pressure))
    and total_residual <= pressure_tolerance * max(1.0, abs(terminal_total_pressure))
  )
  if not seam_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      terminal_continuity_verified=False,
      perimeter_geometry_verified=True,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=mach_residual,
      maximum_terminal_flow_angle_residual_rad=angle_residual,
      maximum_terminal_static_pressure_residual_Pa=static_residual,
      maximum_terminal_total_pressure_residual_Pa=total_residual,
      message='subsonic perimeter endpoints do not reproduce the scalar terminal shock state',
    )

  maximum_total_pressure_gain = max(
    sample.total_pressure_Pa - terminal_total_pressure
    for sample in samples
  )
  lineage_verified = maximum_total_pressure_gain <= pressure_tolerance * max(
    1.0,
    abs(terminal_total_pressure),
    abs(upstream_total_pressure),
  )
  if not lineage_verified:
    return _failure(
      MocMixedRegimeBoundaryStatus.PRESSURE_FAILURE,
      terminal=terminal,
      supersonic_patch_sample_count=len(patch),
      supersonic_patch_verified=patch_verified,
      subsonic_state_samples_verified=True,
      terminal_continuity_verified=True,
      perimeter_geometry_verified=True,
      total_pressure_lineage_verified=False,
      subsonic_samples=samples,
      perimeter_points_m=points,
      maximum_terminal_mach_residual=mach_residual,
      maximum_terminal_flow_angle_residual_rad=angle_residual,
      maximum_terminal_static_pressure_residual_Pa=static_residual,
      maximum_terminal_total_pressure_residual_Pa=total_residual,
      maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
      message='subsonic perimeter contains a total-pressure gain over the terminal shock state',
    )

  return MocMixedRegimeBoundaryResult(
    status=MocMixedRegimeBoundaryStatus.CONVERGED_BOUNDARY_HANDOFF,
    terminal=terminal,
    supersonic_patch_sample_count=len(patch),
    subsonic_samples=samples,
    perimeter_points_m=points,
    supersonic_patch_verified=patch_verified,
    subsonic_state_samples_verified=True,
    terminal_continuity_verified=True,
    perimeter_geometry_verified=True,
    total_pressure_lineage_verified=True,
    maximum_terminal_mach_residual=mach_residual,
    maximum_terminal_flow_angle_residual_rad=angle_residual,
    maximum_terminal_static_pressure_residual_Pa=static_residual,
    maximum_terminal_total_pressure_residual_Pa=total_residual,
    maximum_total_pressure_gain_Pa=maximum_total_pressure_gain,
    message=(
      'scalar subsonic perimeter handoff passed shock-seam, open-supersonic-patch, '
      'geometry, and total-pressure lineage checks; a subsonic field mesh is still pending'
    ),
  )
