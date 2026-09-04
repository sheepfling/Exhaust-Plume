"""Strict one-sided upstream coupling across a characteristic caustic.

An old characteristic strip and a restarted characteristic family are two
different local solutions.  This module provides the small seam between them
without averaging their states or treating a missing region as a valid field.
The optional side selector is an explicit branch choice; when it is omitted,
an overlap is rejected as ambiguous and a point is accepted only when exactly
one of the two bounded fields covers it.

The resulting bridge is an upstream sampling contract for research shock
marches.  It is not a caustic remesher, a shock solution, or a physical cell
closure.  In particular, a path that is fully covered still remains below the
chain-promotion boundary until a solver supplies the missing branch physics
and validates the seam.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite

from exhaust_plume.models.moc.caustic_restart import MocCausticFamilyBandResult
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.source_strip import MocSourceCharacteristicStripResult

__all__ = (
  'MocCausticBridgeSide',
  'MocCausticBridgeStatus',
  'MocCausticBridgeSample',
  'MocCausticUpstreamBridge',
  'MocCausticBridgeResult',
  'build_caustic_upstream_bridge',
  'sample_caustic_upstream_bridge',
)


class MocCausticBridgeSide(str, Enum):
  """One-sided field allowed to supply a caustic-bridge state."""

  OLD_FAMILY = 'old-family'
  RESTARTED_FAMILY = 'restarted-family'
####


class MocCausticBridgeStatus(str, Enum):
  """Structured outcomes for bounded caustic-bridge sampling."""

  CONVERGED_BOUNDED_PATH = 'converged_bounded_caustic_bridge_path'
  INVALID_INPUT = 'invalid_input'
  FIELD_INPUT_FAILURE = 'caustic_bridge_field_input_failure'
  PATH_GEOMETRY_FAILURE = 'caustic_bridge_path_geometry_failure'
  DOMAIN_GAP = 'caustic_bridge_domain_gap'
  SELECTED_SIDE_DOMAIN_GAP = 'caustic_bridge_selected_side_domain_gap'
  AMBIGUOUS_OVERLAP = 'caustic_bridge_ambiguous_overlap'
  SIDE_SELECTION_FAILURE = 'caustic_bridge_side_selection_failure'
  PRESSURE_FAILURE = 'caustic_bridge_pressure_failure'
  GEOMETRY_FAILURE = 'caustic_bridge_state_geometry_failure'
  SAMPLER_FAILURE = 'caustic_bridge_sampler_failure'
####


@dataclass(frozen=True, slots=True)
class MocCausticBridgeSample:
  """One accepted point from exactly one bounded characteristic branch."""

  point_m: tuple[float, float]
  side: MocCausticBridgeSide
  state: CharacteristicState
  static_pressure_Pa: float
  old_family_available: bool
  restarted_family_available: bool

  def __post_init__(self) -> None:
    if len(self.point_m) != 2 or not all(
      isfinite(float(value)) for value in self.point_m
    ):
      raise ValueError('caustic bridge sample point must contain finite coordinates')
    ####
    if not isinstance(self.side, MocCausticBridgeSide):
      raise TypeError('caustic bridge sample side must be a MocCausticBridgeSide')
    ####
    if not isinstance(self.state, CharacteristicState):
      raise TypeError('caustic bridge sample state must be a CharacteristicState')
    ####
    pressure = float(self.static_pressure_Pa)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('caustic bridge sample pressure must be finite and positive')
    ####
    if not isinstance(self.old_family_available, bool):
      raise TypeError('old_family_available must be a bool')
    ####
    if not isinstance(self.restarted_family_available, bool):
      raise TypeError('restarted_family_available must be a bool')
    ####
    object.__setattr__(self, 'point_m', (float(self.point_m[0]), float(self.point_m[1])))
    object.__setattr__(self, 'static_pressure_Pa', pressure)
  ####
####


@dataclass(frozen=True, slots=True)
class _MocCausticBridgeResolution:
  status: MocCausticBridgeStatus
  side: MocCausticBridgeSide | None
  state: CharacteristicState | None
  static_pressure_Pa: float | None
  old_family_available: bool
  restarted_family_available: bool
  message: str = ''
####


@dataclass(frozen=True, slots=True)
class MocCausticUpstreamBridge:
  """A deterministic composition of two domain-bounded one-sided fields.

  ``side_at`` is optional.  Without it, a point is accepted only when exactly
  one field supplies a state.  With it, the selected side is authoritative and
  the other side is never used as a fallback.  This prevents a future shock
  march from silently crossing an unresolved caustic or changing branches
  because one field happens to be larger.
  """

  old_family: MocSourceCharacteristicStripResult
  restarted_family: MocCausticFamilyBandResult
  side_at: Callable[[tuple[float, float]], MocCausticBridgeSide] | None = None

  def __post_init__(self) -> None:
    if not isinstance(self.old_family, MocSourceCharacteristicStripResult):
      raise TypeError(
        'old_family must be a MocSourceCharacteristicStripResult'
      )
    ####
    if not isinstance(self.restarted_family, MocCausticFamilyBandResult):
      raise TypeError(
        'restarted_family must be a MocCausticFamilyBandResult'
      )
    ####
    if self.side_at is not None and not callable(self.side_at):
      raise TypeError('side_at must be callable when supplied')
    ####
  ####

  @property
  def fields_converged(self) -> bool:
    """Whether both supplied one-sided fields passed their local gates."""

    return self.old_family.converged and self.restarted_family.converged
  ####

  @property
  def explicit_side_selection(self) -> bool:
    return self.side_at is not None
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'old_family_status': self.old_family.status.value,
      'old_family_converged': self.old_family.converged,
      'restarted_family_status': self.restarted_family.status.value,
      'restarted_family_converged': self.restarted_family.converged,
      'fields_converged': self.fields_converged,
      'side_selection': (
        'explicit-caller-selector'
        if self.explicit_side_selection
        else 'unique-domain-coverage-only'
      ),
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
    }
  ####

  @staticmethod
  def _state_from_field(
    field: MocSourceCharacteristicStripResult | MocCausticFamilyBandResult,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> tuple[CharacteristicState | None, MocCausticBridgeStatus | None, str]:
    try:
      state = field.state_at(
        point_m,
        position_tolerance_m=position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return (
        None,
        MocCausticBridgeStatus.SAMPLER_FAILURE,
        f'caustic bridge field sampler raised: {error}',
      )
    ####
    if state is None:
      return None, None, ''
    ####
    if not isinstance(state, CharacteristicState):
      return (
        None,
        MocCausticBridgeStatus.SAMPLER_FAILURE,
        'caustic bridge field sampler returned a non-CharacteristicState value',
      )
    ####
    if hypot(state.x_m - point_m[0], state.y_m - point_m[1]) > position_tolerance_m:
      return (
        None,
        MocCausticBridgeStatus.GEOMETRY_FAILURE,
        'caustic bridge field returned a state away from the requested point',
      )
    ####
    return state, None, ''
  ####

  @staticmethod
  def _pressure_from_field(
    field: MocSourceCharacteristicStripResult | MocCausticFamilyBandResult,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> tuple[float | None, MocCausticBridgeStatus | None, str]:
    try:
      pressure = field.static_pressure_at(
        point_m,
        position_tolerance_m=position_tolerance_m,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return (
        None,
        MocCausticBridgeStatus.SAMPLER_FAILURE,
        f'caustic bridge pressure sampler raised: {error}',
      )
    ####
    if pressure is None:
      return None, MocCausticBridgeStatus.PRESSURE_FAILURE, (
        'selected caustic bridge field returned no static pressure'
      )
    ####
    pressure_value = float(pressure)
    if not isfinite(pressure_value) or pressure_value <= 0.0:
      return None, MocCausticBridgeStatus.PRESSURE_FAILURE, (
        'selected caustic bridge field returned an invalid static pressure'
      )
    ####
    return pressure_value, None, ''
  ####

  def _resolve(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float,
  ) -> _MocCausticBridgeResolution:
    if not self.fields_converged:
      return _MocCausticBridgeResolution(
        status=MocCausticBridgeStatus.FIELD_INPUT_FAILURE,
        side=None,
        state=None,
        static_pressure_Pa=None,
        old_family_available=False,
        restarted_family_available=False,
        message=(
          'both one-sided fields must be locally converged before they can '
          'feed a caustic bridge'
        ),
      )
    ####

    old_state, old_status, old_message = self._state_from_field(
      self.old_family,
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    restarted_state, restarted_status, restarted_message = self._state_from_field(
      self.restarted_family,
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if self.side_at is None:
      if old_status is not None:
        return _MocCausticBridgeResolution(
          status=old_status,
          side=None,
          state=None,
          static_pressure_Pa=None,
          old_family_available=old_state is not None,
          restarted_family_available=restarted_state is not None,
          message=old_message,
        )
      ####
      if restarted_status is not None:
        return _MocCausticBridgeResolution(
          status=restarted_status,
          side=None,
          state=None,
          static_pressure_Pa=None,
          old_family_available=old_state is not None,
          restarted_family_available=restarted_state is not None,
          message=restarted_message,
        )
      ####
      if old_state is not None and restarted_state is not None:
        return _MocCausticBridgeResolution(
          status=MocCausticBridgeStatus.AMBIGUOUS_OVERLAP,
          side=None,
          state=None,
          static_pressure_Pa=None,
          old_family_available=True,
          restarted_family_available=True,
          message=(
            'both one-sided caustic fields cover the point; an explicit '
            'branch selector is required and no state averaging is allowed'
          ),
        )
      ####
      if old_state is None and restarted_state is None:
        return _MocCausticBridgeResolution(
          status=MocCausticBridgeStatus.DOMAIN_GAP,
          side=None,
          state=None,
          static_pressure_Pa=None,
          old_family_available=False,
          restarted_family_available=False,
          message=(
            'neither one-sided caustic field covers the requested point; '
            'bridge interpolation or extrapolation is not permitted'
          ),
        )
      ####
      side = (
        MocCausticBridgeSide.OLD_FAMILY
        if old_state is not None
        else MocCausticBridgeSide.RESTARTED_FAMILY
      )
    else:
      try:
        side = self.side_at(point_m)
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return _MocCausticBridgeResolution(
          status=MocCausticBridgeStatus.SIDE_SELECTION_FAILURE,
          side=None,
          state=None,
          static_pressure_Pa=None,
          old_family_available=old_state is not None,
          restarted_family_available=restarted_state is not None,
          message=f'caustic bridge side selector raised: {error}',
        )
      ####
      if not isinstance(side, MocCausticBridgeSide):
        return _MocCausticBridgeResolution(
          status=MocCausticBridgeStatus.SIDE_SELECTION_FAILURE,
          side=None,
          state=None,
          static_pressure_Pa=None,
          old_family_available=old_state is not None,
          restarted_family_available=restarted_state is not None,
          message='caustic bridge side selector must return a MocCausticBridgeSide',
        )
      ####
    ####

    selected_state = (
      old_state if side is MocCausticBridgeSide.OLD_FAMILY else restarted_state
    )
    if selected_state is None:
      selected_name = (
        'old-family' if side is MocCausticBridgeSide.OLD_FAMILY
        else 'restarted-family'
      )
      return _MocCausticBridgeResolution(
        status=(
          MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP
          if self.side_at is not None
          else MocCausticBridgeStatus.DOMAIN_GAP
        ),
        side=side,
        state=None,
        static_pressure_Pa=None,
        old_family_available=old_state is not None,
        restarted_family_available=restarted_state is not None,
        message=(
          f'the selected {selected_name} does not cover the requested point; '
          'the other side is not used as a fallback'
        ),
      )
    ####
    selected_field = (
      self.old_family
      if side is MocCausticBridgeSide.OLD_FAMILY
      else self.restarted_family
    )
    pressure, pressure_status, pressure_message = self._pressure_from_field(
      selected_field,
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if pressure_status is not None or pressure is None:
      return _MocCausticBridgeResolution(
        status=(
          pressure_status
          if pressure_status is not None
          else MocCausticBridgeStatus.PRESSURE_FAILURE
        ),
        side=side,
        state=None,
        static_pressure_Pa=None,
        old_family_available=old_state is not None,
        restarted_family_available=restarted_state is not None,
        message=pressure_message,
      )
    ####
    return _MocCausticBridgeResolution(
      status=MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH,
      side=side,
      state=selected_state,
      static_pressure_Pa=pressure,
      old_family_available=old_state is not None,
      restarted_family_available=restarted_state is not None,
    )
  ####

  def state_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> CharacteristicState | None:
    """Return a selected state only inside the two bounded source fields."""

    if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
      raise ValueError('point_m must contain two finite coordinates')
    ####
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    resolution = self._resolve(
      (float(point_m[0]), float(point_m[1])),
      position_tolerance_m=position_tolerance_m,
    )
    return resolution.state if resolution.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH else None
  ####

  def static_pressure_at(
    self,
    point_m: tuple[float, float],
    *,
    position_tolerance_m: float = 1.0e-10,
  ) -> float | None:
    """Return the selected field's isentropic pressure, without fallback."""

    if len(point_m) != 2 or not all(isfinite(float(value)) for value in point_m):
      raise ValueError('point_m must contain two finite coordinates')
    ####
    if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
      raise ValueError('position_tolerance_m must be finite and positive')
    ####
    resolution = self._resolve(
      (float(point_m[0]), float(point_m[1])),
      position_tolerance_m=position_tolerance_m,
    )
    return (
      resolution.static_pressure_Pa
      if resolution.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH
      else None
    )
  ####
####


@dataclass(frozen=True, slots=True)
class MocCausticBridgeResult:
  """Audit of one ordered shock-path sample against a caustic bridge."""

  status: MocCausticBridgeStatus
  bridge: MocCausticUpstreamBridge | None
  requested_points_m: tuple[tuple[float, float], ...]
  samples: tuple[MocCausticBridgeSample, ...]
  first_missing_sample_index: int | None
  first_ambiguous_sample_index: int | None
  side_transition_indices: tuple[int, ...]
  first_missing_point_m: tuple[float, float] | None = None
  message: str = ''

  def __post_init__(self) -> None:
    if self.first_missing_point_m is not None:
      if len(self.first_missing_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.first_missing_point_m
      ):
        raise ValueError(
          'first_missing_point_m must contain two finite coordinates'
        )
      ####
      object.__setattr__(
        self,
        'first_missing_point_m',
        (
          float(self.first_missing_point_m[0]),
          float(self.first_missing_point_m[1]),
        ),
      )
    ####
    if self.first_missing_sample_index is None:
      if self.first_missing_point_m is not None:
        raise ValueError(
          'first_missing_point_m requires first_missing_sample_index'
        )
      ####
    elif (
      isinstance(self.first_missing_sample_index, bool)
      or not isinstance(self.first_missing_sample_index, int)
      or self.first_missing_sample_index < 0
    ):
      raise ValueError('first_missing_sample_index must be a nonnegative integer')
    ####
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH
  ####

  @property
  def sampled_count(self) -> int:
    return len(self.samples)
  ####

  @property
  def last_valid_point_m(self) -> tuple[float, float] | None:
    return None if not self.samples else self.samples[-1].point_m
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The bridge does not solve the caustic branch or downstream closure."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    side_counts = {
      side.value: sum(sample.side is side for sample in self.samples)
      for side in MocCausticBridgeSide
    }
    return {
      'status': self.status.value,
      'converged': self.converged,
      'requested_sample_count': len(self.requested_points_m),
      'sampled_count': self.sampled_count,
      'first_missing_sample_index': self.first_missing_sample_index,
      'first_missing_point_m': self.first_missing_point_m,
      'first_ambiguous_sample_index': self.first_ambiguous_sample_index,
      'last_valid_point_m': self.last_valid_point_m,
      'side_counts': side_counts,
      'side_transition_indices': list(self.side_transition_indices),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'bridge': None if self.bridge is None else self.bridge.as_report(),
      'samples': [
        {
          'point_m': sample.point_m,
          'side': sample.side.value,
          'static_pressure_Pa': sample.static_pressure_Pa,
          'old_family_available': sample.old_family_available,
          'restarted_family_available': sample.restarted_family_available,
        }
        for sample in self.samples
      ],
      'message': self.message,
    }
  ####
####


def build_caustic_upstream_bridge(
  old_family: MocSourceCharacteristicStripResult,
  restarted_family: MocCausticFamilyBandResult,
  *,
  side_at: Callable[[tuple[float, float]], MocCausticBridgeSide] | None = None,
) -> MocCausticUpstreamBridge:
  """Build a branch-explicit, domain-bounded upstream bridge provider."""

  return MocCausticUpstreamBridge(
    old_family=old_family,
    restarted_family=restarted_family,
    side_at=side_at,
  )
####


def _invalid_result(
  status: MocCausticBridgeStatus,
  *,
  bridge: MocCausticUpstreamBridge | None,
  points: tuple[tuple[float, float], ...] = (),
  first_missing_sample_index: int | None = None,
  first_missing_point_m: tuple[float, float] | None = None,
  first_ambiguous_sample_index: int | None = None,
  message: str,
) -> MocCausticBridgeResult:
  return MocCausticBridgeResult(
    status=status,
    bridge=bridge,
    requested_points_m=points,
    samples=(),
    first_missing_sample_index=first_missing_sample_index,
    first_missing_point_m=first_missing_point_m,
    first_ambiguous_sample_index=first_ambiguous_sample_index,
    side_transition_indices=(),
    message=message,
  )
####


def sample_caustic_upstream_bridge(
  bridge: MocCausticUpstreamBridge,
  shock_points_m: Sequence[tuple[float, float]],
  *,
  position_tolerance_m: float = 1.0e-10,
) -> MocCausticBridgeResult:
  """Audit an ordered path without filling a gap or averaging branches.

  The path is ordered from an outer shock attachment toward the centerline:
  ``x`` must increase and ``y`` must not increase.  A complete audit only
  means that the requested samples are covered by the selected one-sided
  fields.  It does not imply continuity, entropy closure, or a physical
  shock-cell boundary.
  """

  if not isinstance(bridge, MocCausticUpstreamBridge):
    return _invalid_result(
      MocCausticBridgeStatus.INVALID_INPUT,
      bridge=None,
      message='bridge must be a MocCausticUpstreamBridge',
    )
  ####
  try:
    points = tuple(
      (float(point[0]), float(point[1]))
      for point in shock_points_m
    )
  except (TypeError, IndexError, ValueError):
    return _invalid_result(
      MocCausticBridgeStatus.INVALID_INPUT,
      bridge=bridge,
      message='shock_points_m must contain two-coordinate points',
    )
  ####
  if not points or any(not all(isfinite(value) for value in point) for point in points):
    return _invalid_result(
      MocCausticBridgeStatus.INVALID_INPUT,
      bridge=bridge,
      points=points,
      message='caustic bridge sampling requires at least one finite point',
    )
  ####
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  ####
  for index, (previous, current) in enumerate(
    zip(points[:-1], points[1:], strict=True),
    start=1,
  ):
    if (
      current[0] <= previous[0] + position_tolerance_m
      or current[1] > previous[1] + position_tolerance_m
    ):
      return _invalid_result(
        MocCausticBridgeStatus.PATH_GEOMETRY_FAILURE,
        bridge=bridge,
        points=points,
        first_missing_sample_index=index,
        first_missing_point_m=points[index],
        message=(
          'caustic bridge shock path must be strictly downstream in x and '
          'nonincreasing in y'
        ),
      )
    ####
  ####

  samples: list[MocCausticBridgeSample] = []
  transitions: list[int] = []
  for index, point in enumerate(points):
    resolution = bridge._resolve(
      point,
      position_tolerance_m=position_tolerance_m,
    )
    if resolution.status is not MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH:
      first_missing = (
        index
        if resolution.status in (
          MocCausticBridgeStatus.DOMAIN_GAP,
          MocCausticBridgeStatus.SELECTED_SIDE_DOMAIN_GAP,
        )
        else None
      )
      first_ambiguous = (
        index
        if resolution.status is MocCausticBridgeStatus.AMBIGUOUS_OVERLAP
        else None
      )
      return MocCausticBridgeResult(
        status=resolution.status,
        bridge=bridge,
        requested_points_m=points,
        samples=tuple(samples),
        first_missing_sample_index=first_missing,
        first_missing_point_m=(point if first_missing is not None else None),
        first_ambiguous_sample_index=first_ambiguous,
        side_transition_indices=tuple(transitions),
        message=resolution.message or f'caustic bridge failed at sample {index}',
      )
    ####
    assert resolution.side is not None
    assert resolution.state is not None
    assert resolution.static_pressure_Pa is not None
    if samples and samples[-1].side is not resolution.side:
      transitions.append(index)
    ####
    samples.append(
      MocCausticBridgeSample(
        point_m=point,
        side=resolution.side,
        state=resolution.state,
        static_pressure_Pa=resolution.static_pressure_Pa,
        old_family_available=resolution.old_family_available,
        restarted_family_available=resolution.restarted_family_available,
      )
    )
  ####
  return MocCausticBridgeResult(
    status=MocCausticBridgeStatus.CONVERGED_BOUNDED_PATH,
    bridge=bridge,
    requested_points_m=points,
    samples=tuple(samples),
    first_missing_sample_index=None,
    first_ambiguous_sample_index=None,
    side_transition_indices=tuple(transitions),
    message=(
      'every requested shock-path sample is covered by exactly one selected '
      'one-sided caustic field; branch and downstream closure remain pending'
    ),
  )
####
