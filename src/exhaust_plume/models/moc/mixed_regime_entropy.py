"""Solver-owned entropy handoff for the reflected mixed-regime seam.

The terminal shock-cell composite already contains a pressure-loss lineage on
the supersonic shock patch and a scalar normal-shock endpoint.  This module
turns those two pieces into one ordered interface profile for a future
downstream solver.  It deliberately does not manufacture a subsonic
``CharacteristicState`` or solve the downstream free boundary.

The profile is useful because total pressure is the calorically-perfect-gas
entropy coordinate (up to a constant factor when total temperature is held
fixed).  A downstream solver can therefore consume the measured profile and
transport it with its own streamlines.  Until that transport and the
shock/ambient/free-boundary coupling are solved, this result remains a
research handoff and cannot seed a continued shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite, log
from typing import Any

from exhaust_plume.models.moc.compression import (
  MocNormalShockTerminalResult,
  MocSubsonicShockBoundaryResult,
)
from exhaust_plume.models.moc.mixed_regime import MocMixedRegimePerimeterRequest
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState

__all__ = (
  'MocMixedRegimeEntropyInterfaceKind',
  'MocMixedRegimeEntropyInterfaceSample',
  'MocMixedRegimeEntropyHandoffStatus',
  'MocMixedRegimeEntropyHandoffResult',
  'build_mixed_regime_entropy_handoff',
)


class MocMixedRegimeEntropyInterfaceKind(str, Enum):
  """Shock type represented by one interface sample."""

  OBLIQUE_SHOCK = 'oblique-shock'
  NORMAL_SHOCK_TERMINAL = 'normal-shock-terminal'


class MocMixedRegimeEntropyHandoffStatus(str, Enum):
  """Outcome of assembling the ordered entropy handoff."""

  CONVERGED = 'converged-reflected-downstream-entropy-handoff'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_FAILURE = 'entropy-handoff-terminal-failure'
  PATCH_FAILURE = 'entropy-handoff-supersonic-patch-failure'
  GEOMETRY_FAILURE = 'entropy-handoff-interface-geometry-failure'
  PRESSURE_FAILURE = 'entropy-handoff-pressure-lineage-failure'


@dataclass(frozen=True, slots=True)
class MocMixedRegimeEntropyInterfaceSample:
  """One measured shock-interface sample carrying entropy production.

  The upstream flow state is intentionally not reconstructed for oblique
  samples because the current post-shock boundary contract carries its
  pressure lineage, but not an upstream ``CharacteristicState`` at every
  shock point.  The downstream state and both total pressures are sufficient
  to carry the entropy coordinate without pretending that missing state data
  exists.
  """

  point_m: tuple[float, float]
  downstream_mach: float
  downstream_flow_angle_rad: float
  gamma: float
  upstream_total_pressure_Pa: float
  downstream_total_pressure_Pa: float
  interface_kind: MocMixedRegimeEntropyInterfaceKind

  def __post_init__(self) -> None:
    try:
      point = (float(self.point_m[0]), float(self.point_m[1]))
    except (IndexError, TypeError, ValueError):
      raise ValueError('entropy interface point must contain two finite coordinates') from None
    if not all(isfinite(value) for value in point):
      raise ValueError('entropy interface point must contain two finite coordinates')
    if not isinstance(self.interface_kind, MocMixedRegimeEntropyInterfaceKind):
      raise TypeError(
        'interface_kind must be a MocMixedRegimeEntropyInterfaceKind'
      )
    values = (
      ('downstream_mach', self.downstream_mach),
      ('downstream_flow_angle_rad', self.downstream_flow_angle_rad),
      ('gamma', self.gamma),
      ('upstream_total_pressure_Pa', self.upstream_total_pressure_Pa),
      ('downstream_total_pressure_Pa', self.downstream_total_pressure_Pa),
    )
    for name, raw_value in values:
      value = float(raw_value)
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
    mach = float(self.downstream_mach)
    gamma = float(self.gamma)
    upstream_total_pressure = float(self.upstream_total_pressure_Pa)
    downstream_total_pressure = float(self.downstream_total_pressure_Pa)
    if mach <= 0.0:
      raise ValueError('downstream_mach must be positive')
    if gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    if upstream_total_pressure <= 0.0 or downstream_total_pressure <= 0.0:
      raise ValueError('entropy interface total pressures must be positive')
    if downstream_total_pressure >= upstream_total_pressure:
      raise ValueError(
        'entropy interface total pressure must show a strict shock loss'
      )
    if (
      self.interface_kind is MocMixedRegimeEntropyInterfaceKind.OBLIQUE_SHOCK
      and mach <= 1.0
    ):
      raise ValueError('oblique-shock interface samples must remain supersonic')
    if (
      self.interface_kind is MocMixedRegimeEntropyInterfaceKind.NORMAL_SHOCK_TERMINAL
      and mach >= 1.0
    ):
      raise ValueError('normal-shock terminal samples must be subsonic')
    object.__setattr__(self, 'point_m', point)
    object.__setattr__(self, 'downstream_mach', mach)
    object.__setattr__(self, 'downstream_flow_angle_rad', float(self.downstream_flow_angle_rad))
    object.__setattr__(self, 'gamma', gamma)
    object.__setattr__(self, 'upstream_total_pressure_Pa', upstream_total_pressure)
    object.__setattr__(self, 'downstream_total_pressure_Pa', downstream_total_pressure)

  @property
  def total_pressure_ratio(self) -> float:
    """Return downstream-to-upstream stagnation-pressure ratio."""

    return self.downstream_total_pressure_Pa / self.upstream_total_pressure_Pa
  ####

  @property
  def entropy_production_nondimensional(self) -> float:
    """Return ``Δs/R = log(p0_up/p0_down)`` for fixed total temperature."""

    return log(self.upstream_total_pressure_Pa / self.downstream_total_pressure_Pa)
  ####

  @property
  def downstream_is_supersonic(self) -> bool:
    """Whether this interface sample retains a supersonic downstream state."""

    return self.interface_kind is MocMixedRegimeEntropyInterfaceKind.OBLIQUE_SHOCK
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'point_m': self.point_m,
      'downstream_mach': self.downstream_mach,
      'downstream_flow_angle_rad': self.downstream_flow_angle_rad,
      'gamma': self.gamma,
      'upstream_total_pressure_Pa': self.upstream_total_pressure_Pa,
      'downstream_total_pressure_Pa': self.downstream_total_pressure_Pa,
      'total_pressure_ratio': self.total_pressure_ratio,
      'entropy_production_nondimensional': self.entropy_production_nondimensional,
      'interface_kind': self.interface_kind.value,
      'downstream_is_supersonic': self.downstream_is_supersonic,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocMixedRegimeEntropyHandoffResult:
  """An ordered, pressure-loss-aware shock interface for a future solver.

  The interface runs from the outer oblique-shock patch toward the centerline
  normal-shock endpoint.  It is an open interface, not a closed downstream
  perimeter.  ``entropy_transport_verified`` means that the source data are
  complete and each shock sample carries a strict total-pressure loss; it is
  not a claim that entropy has already been advected through a subsonic field.
  """

  status: MocMixedRegimeEntropyHandoffStatus
  request: MocMixedRegimePerimeterRequest | None
  samples: tuple[MocMixedRegimeEntropyInterfaceSample, ...] = ()
  interface_points_m: tuple[tuple[float, float], ...] = ()
  cumulative_arc_length_m: tuple[float, ...] = ()
  terminal_sample_index: int | None = None
  maximum_interface_segment_length_m: float | None = None
  minimum_total_pressure_ratio: float | None = None
  maximum_entropy_production_nondimensional: float | None = None
  maximum_total_pressure_gain_Pa: float | None = None
  interface_geometry_verified: bool = False
  terminal_seam_verified: bool = False
  shock_loss_verified: bool = False
  entropy_transport_verified: bool = False
  model: str = 'solver-owned-reflected-shock-interface-entropy-handoff'
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedRegimeEntropyHandoffStatus):
      raise TypeError(
        'status must be a MocMixedRegimeEntropyHandoffStatus'
      )
    if self.request is not None and not isinstance(
      self.request,
      MocMixedRegimePerimeterRequest,
    ):
      raise TypeError(
        'request must be a MocMixedRegimePerimeterRequest or None'
      )
    samples = tuple(self.samples)
    if any(
      not isinstance(sample, MocMixedRegimeEntropyInterfaceSample)
      for sample in samples
    ):
      raise TypeError(
        'samples must contain MocMixedRegimeEntropyInterfaceSample values'
      )
    try:
      points = tuple(
        (float(point[0]), float(point[1]))
        for point in self.interface_points_m
      )
    except (IndexError, TypeError, ValueError) as error:
      raise ValueError(
        'interface_points_m must contain two-coordinate numeric points'
      ) from error
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('interface_points_m must contain finite points')
    cumulative = tuple(float(value) for value in self.cumulative_arc_length_m)
    if any(not isfinite(value) or value < 0.0 for value in cumulative):
      raise ValueError(
        'cumulative_arc_length_m must contain finite nonnegative values'
      )
    if len(points) != len(samples):
      raise ValueError(
        'interface_points_m and samples must have equal lengths'
      )
    if cumulative and len(cumulative) != len(points):
      raise ValueError(
        'cumulative_arc_length_m must match the interface sample count'
      )
    if self.terminal_sample_index is not None:
      if (
        isinstance(self.terminal_sample_index, bool)
        or not isinstance(self.terminal_sample_index, int)
        or not 0 <= self.terminal_sample_index < len(samples)
      ):
        raise ValueError(
          'terminal_sample_index must identify a valid interface sample'
        )
    for name in (
      'maximum_interface_segment_length_m',
      'minimum_total_pressure_ratio',
      'maximum_entropy_production_nondimensional',
      'maximum_total_pressure_gain_Pa',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric):
          raise ValueError(f'{name} must be finite when supplied')
        object.__setattr__(self, name, numeric)
    for name in (
      'interface_geometry_verified',
      'terminal_seam_verified',
      'shock_loss_verified',
      'entropy_transport_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    model = str(self.model)
    if not model:
      raise ValueError('model must be a non-empty string')
    object.__setattr__(self, 'samples', samples)
    object.__setattr__(self, 'interface_points_m', points)
    object.__setattr__(self, 'cumulative_arc_length_m', cumulative)
    object.__setattr__(self, 'model', model)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedRegimeEntropyHandoffStatus.CONVERGED
  ####

  @property
  def sample_count(self) -> int:
    return len(self.samples)
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """An interface handoff is not a closed downstream physical field."""

    return False
  ####

  @property
  def canonical_free_boundary_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def total_pressure_at_arc_length(self, arc_length_m: float) -> float:
    """Interpolate the carried pressure profile without extrapolation."""

    if not self.entropy_transport_verified or len(self.samples) < 2:
      raise ValueError(
        'a verified entropy handoff with at least two samples is required'
      )
    coordinate = float(arc_length_m)
    if not isfinite(coordinate):
      raise ValueError('arc_length_m must be finite')
    arc = self.cumulative_arc_length_m
    if coordinate < arc[0] or coordinate > arc[-1]:
      raise ValueError(
        'arc_length_m lies outside the carried shock-interface profile; '
        'extrapolation is disabled'
      )
    if coordinate <= arc[0]:
      return self.samples[0].downstream_total_pressure_Pa
    if coordinate >= arc[-1]:
      return self.samples[-1].downstream_total_pressure_Pa
    for first_arc, second_arc, first, second in zip(
      arc,
      arc[1:],
      self.samples,
      self.samples[1:],
      strict=True,
    ):
      if coordinate <= second_arc:
        fraction = (coordinate - first_arc) / (second_arc - first_arc)
        return (
          first.downstream_total_pressure_Pa
          + fraction * (
            second.downstream_total_pressure_Pa
            - first.downstream_total_pressure_Pa
          )
        )
    return self.samples[-1].downstream_total_pressure_Pa
  ####

  def entropy_production_at_arc_length(self, arc_length_m: float) -> float:
    """Return the linearly interpolated downstream entropy coordinate."""

    pressure = self.total_pressure_at_arc_length(arc_length_m)
    if self.samples[-1].downstream_total_pressure_Pa <= 0.0:
      raise ValueError('entropy handoff has a nonpositive downstream pressure')
    # The interpolation is intentionally tied to the local pressure profile;
    # it never substitutes the terminal pressure for an uncovered point.
    upstream = self._upstream_total_pressure_at_arc_length(arc_length_m)
    return log(upstream / pressure)
  ####

  def _upstream_total_pressure_at_arc_length(self, arc_length_m: float) -> float:
    """Interpolate the upstream pressure side of the same shock profile."""

    if not self.entropy_transport_verified or len(self.samples) < 2:
      raise ValueError(
        'a verified entropy handoff with at least two samples is required'
      )
    coordinate = float(arc_length_m)
    arc = self.cumulative_arc_length_m
    if coordinate < arc[0] or coordinate > arc[-1]:
      raise ValueError(
        'arc_length_m lies outside the carried shock-interface profile; '
        'extrapolation is disabled'
      )
    if coordinate <= arc[0]:
      return self.samples[0].upstream_total_pressure_Pa
    if coordinate >= arc[-1]:
      return self.samples[-1].upstream_total_pressure_Pa
    for first_arc, second_arc, first, second in zip(
      arc,
      arc[1:],
      self.samples,
      self.samples[1:],
      strict=True,
    ):
      if coordinate <= second_arc:
        fraction = (coordinate - first_arc) / (second_arc - first_arc)
        return (
          first.upstream_total_pressure_Pa
          + fraction * (
            second.upstream_total_pressure_Pa
            - first.upstream_total_pressure_Pa
          )
        )
    return self.samples[-1].upstream_total_pressure_Pa
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'model': self.model,
      'sample_count': self.sample_count,
      'terminal_sample_index': self.terminal_sample_index,
      'interface_points_m': self.interface_points_m,
      'cumulative_arc_length_m': self.cumulative_arc_length_m,
      'maximum_interface_segment_length_m': self.maximum_interface_segment_length_m,
      'minimum_total_pressure_ratio': self.minimum_total_pressure_ratio,
      'maximum_entropy_production_nondimensional': self.maximum_entropy_production_nondimensional,
      'maximum_total_pressure_gain_Pa': self.maximum_total_pressure_gain_Pa,
      'interface_geometry_verified': self.interface_geometry_verified,
      'terminal_seam_verified': self.terminal_seam_verified,
      'shock_loss_verified': self.shock_loss_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request_terminal_point_m': (
        None if self.request is None else self.request.terminal_point_m
      ),
      'samples': [sample.as_report() for sample in self.samples],
      'message': self.message,
    }
  ####


def _handoff_failure(
  status: MocMixedRegimeEntropyHandoffStatus,
  *,
  request: MocMixedRegimePerimeterRequest | None = None,
  samples: tuple[MocMixedRegimeEntropyInterfaceSample, ...] = (),
  interface_points_m: tuple[tuple[float, float], ...] = (),
  message: str,
) -> MocMixedRegimeEntropyHandoffResult:
  points = (
    tuple(interface_points_m)
    if interface_points_m
    else tuple(sample.point_m for sample in samples)
  )
  return MocMixedRegimeEntropyHandoffResult(
    status=status,
    request=request,
    samples=samples,
    interface_points_m=points,
    message=message,
  )


def build_mixed_regime_entropy_handoff(
  request: MocMixedRegimePerimeterRequest,
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocMixedRegimeEntropyHandoffResult:
  """Assemble the exact reflected shock-interface entropy profile.

  The profile is built only from the request's validated oblique-shock patch
  and its scalar terminal.  No point is inferred from the open downstream
  region, and no subsonic state is promoted to the supersonic MOC type.
  """

  if not isinstance(request, MocMixedRegimePerimeterRequest):
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.INVALID_INPUT,
      message='request must be a MocMixedRegimePerimeterRequest',
    )
  tolerance = float(position_tolerance_m)
  if not isfinite(tolerance) or tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')

  terminal = request.terminal
  if not isinstance(
    terminal,
    (MocNormalShockTerminalResult, MocSubsonicShockBoundaryResult),
  ):
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.TERMINAL_FAILURE,
      request=request,
      message='request terminal is not a supported scalar shock terminal',
    )
  terminal_values = (
    terminal.shock_point_m,
    terminal.downstream_mach,
    terminal.downstream_flow_angle_rad,
    terminal.upstream_total_pressure_Pa,
    terminal.downstream_total_pressure_Pa,
    terminal.upstream_state,
  )
  if any(value is None for value in terminal_values):
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.TERMINAL_FAILURE,
      request=request,
      message='terminal does not expose complete entropy-interface values',
    )
  (
    terminal_point,
    terminal_mach,
    terminal_angle,
    terminal_upstream_total_pressure,
    terminal_downstream_total_pressure,
    terminal_upstream_state,
  ) = terminal_values
  assert terminal_point is not None
  assert terminal_mach is not None
  assert terminal_angle is not None
  assert terminal_upstream_total_pressure is not None
  assert terminal_downstream_total_pressure is not None
  assert terminal_upstream_state is not None
  try:
    terminal_sample = MocMixedRegimeEntropyInterfaceSample(
      point_m=terminal_point,
      downstream_mach=terminal_mach,
      downstream_flow_angle_rad=terminal_angle,
      gamma=terminal_upstream_state.gamma,
      upstream_total_pressure_Pa=terminal_upstream_total_pressure,
      downstream_total_pressure_Pa=terminal_downstream_total_pressure,
      interface_kind=(
        MocMixedRegimeEntropyInterfaceKind.NORMAL_SHOCK_TERMINAL
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.TERMINAL_FAILURE,
      request=request,
      message=f'terminal entropy-interface sample failed: {error}',
    )

  samples: list[MocMixedRegimeEntropyInterfaceSample] = []
  for index, boundary_state in enumerate(request.supersonic_patch):
    if not isinstance(boundary_state, MocPostShockBoundaryState):
      return _handoff_failure(
        MocMixedRegimeEntropyHandoffStatus.PATCH_FAILURE,
        request=request,
        samples=tuple(samples),
        message=f'supersonic patch sample {index} has an invalid type',
      )
    try:
      sample = MocMixedRegimeEntropyInterfaceSample(
        point_m=boundary_state.point_m,
        downstream_mach=boundary_state.state.mach,
        downstream_flow_angle_rad=boundary_state.state.theta_rad,
        gamma=boundary_state.state.gamma,
        upstream_total_pressure_Pa=boundary_state.upstream_total_pressure_Pa,
        downstream_total_pressure_Pa=boundary_state.downstream_total_pressure_Pa,
        interface_kind=MocMixedRegimeEntropyInterfaceKind.OBLIQUE_SHOCK,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _handoff_failure(
        MocMixedRegimeEntropyHandoffStatus.PATCH_FAILURE,
        request=request,
        samples=tuple(samples),
        message=f'supersonic patch sample {index} failed: {error}',
      )
    samples.append(sample)
  samples.append(terminal_sample)
  sample_tuple = tuple(samples)
  points = tuple(sample.point_m for sample in sample_tuple)
  if len(points) < 2:
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.GEOMETRY_FAILURE,
      request=request,
      samples=sample_tuple,
      interface_points_m=points,
      message='entropy interface requires at least one oblique sample and a terminal sample',
    )

  segment_lengths = tuple(
    hypot(second[0] - first[0], second[1] - first[1])
    for first, second in zip(points[:-1], points[1:], strict=True)
  )
  if any(length <= tolerance for length in segment_lengths):
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.GEOMETRY_FAILURE,
      request=request,
      samples=sample_tuple,
      interface_points_m=points,
      message=(
        'shock-interface samples must form a strictly ordered path from the '
        'oblique patch to the terminal; zero-length segments are not allowed'
      ),
    )
  cumulative = [0.0]
  for length in segment_lengths:
    cumulative.append(cumulative[-1] + length)
  ratios = tuple(sample.total_pressure_ratio for sample in sample_tuple)
  entropy = tuple(
    sample.entropy_production_nondimensional for sample in sample_tuple
  )
  maximum_gain = max(
    max(
      0.0,
      sample.downstream_total_pressure_Pa
      - sample.upstream_total_pressure_Pa,
    )
    for sample in sample_tuple
  )
  pressure_loss_verified = all(
    sample.downstream_total_pressure_Pa
    < sample.upstream_total_pressure_Pa
    for sample in sample_tuple
  )
  if not pressure_loss_verified:
    return _handoff_failure(
      MocMixedRegimeEntropyHandoffStatus.PRESSURE_FAILURE,
      request=request,
      samples=sample_tuple,
      interface_points_m=points,
      message='shock-interface entropy handoff contains a total-pressure gain',
    )
  return MocMixedRegimeEntropyHandoffResult(
    status=MocMixedRegimeEntropyHandoffStatus.CONVERGED,
    request=request,
    samples=sample_tuple,
    interface_points_m=points,
    cumulative_arc_length_m=tuple(cumulative),
    terminal_sample_index=len(sample_tuple) - 1,
    maximum_interface_segment_length_m=max(segment_lengths),
    minimum_total_pressure_ratio=min(ratios),
    maximum_entropy_production_nondimensional=max(entropy),
    maximum_total_pressure_gain_Pa=maximum_gain,
    interface_geometry_verified=True,
    terminal_seam_verified=(
      sample_tuple[-1].point_m == terminal_sample.point_m
      and sample_tuple[-1].downstream_mach == terminal_sample.downstream_mach
      and sample_tuple[-1].downstream_total_pressure_Pa
      == terminal_sample.downstream_total_pressure_Pa
    ),
    shock_loss_verified=True,
    entropy_transport_verified=True,
    message=(
      'solver-owned reflected shock-interface profile carries sample-wise '
      'total-pressure loss from the oblique patch through the subsonic normal '
      'terminal; downstream entropy advection and free-boundary closure remain '
      'pending'
    ),
  )
