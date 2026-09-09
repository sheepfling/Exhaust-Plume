"""Signed local shock/expansion laws for the research MOC lane.

This module supplies the missing local distinction between an attached
compression shock and an isentropic expansion.  It is intentionally a state
law, not a global free-boundary solver: no interface position, centerline
reflection, ambient attachment, cell closure, or production claim is inferred
from a successful sample.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.compression import (
  MocTurnCompressionResult,
  solve_attached_compression_to_pressure,
  solve_attached_compression_to_turn,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicFamily,
  CharacteristicState,
  inverse_prandtl_meyer_angle_rad,
  prandtl_meyer_angle_rad,
  supersonic_mach_from_stagnation_pressure_ratio,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocMixedWaveRegime',
  'MocMixedWaveStatus',
  'MocMixedWaveSampleResult',
  'MocMixedWavePathStatus',
  'MocMixedWavePathResult',
  'solve_mixed_wave_sample',
  'solve_mixed_wave_path',
  'solve_mixed_wave_pressure_target_path',
)


class MocMixedWaveRegime(str, Enum):
  """Local wave law selected by the signed flow-angle change."""

  COMPRESSION_SHOCK = 'compression_shock'
  ISENTROPIC_EXPANSION = 'isentropic_expansion'
  MACH_WAVE = 'mach_wave'
####


class MocMixedWaveStatus(str, Enum):
  """Typed outcomes for one signed local wave sample."""

  CONVERGED = 'converged_mixed_wave'
  INVALID_INPUT = 'invalid_input'
  COMPRESSION_FAILURE = 'mixed_wave_compression_failure'
  EXPANSION_OUTSIDE_DOMAIN = 'mixed_wave_expansion_outside_domain'
  INVARIANT_FAILURE = 'mixed_wave_invariant_failure'
####


class MocMixedWavePathStatus(str, Enum):
  """Typed outcomes for an ordered collection of signed wave samples."""

  CONVERGED = 'converged_mixed_wave_path'
  INVALID_INPUT = 'invalid_input'
  SAMPLE_FAILURE = 'mixed_wave_path_sample_failure'
####


def _total_pressure(
  *,
  static_pressure_Pa: float,
  mach: float,
  gamma: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  return static_pressure_Pa * factor**(gamma / (gamma - 1.0))
####


def _static_pressure(
  *,
  total_pressure_Pa: float,
  mach: float,
  gamma: float,
) -> float:
  factor = 1.0 + 0.5 * (gamma - 1.0) * mach**2
  return total_pressure_Pa / factor**(gamma / (gamma - 1.0))
####


def _finite_positive(value: object) -> float | None:
  try:
    numeric = float(value)
  except (TypeError, ValueError):
    return None
  ####
  return numeric if isfinite(numeric) and numeric > 0.0 else None
####


@dataclass(frozen=True, slots=True)
class MocMixedWaveSampleResult:
  """Auditable state-side result for one signed wave sample.

  The compression branch is an attached Rankine--Hugoniot shock and therefore
  loses total pressure.  The expansion branch preserves total pressure and
  uses the ``C-`` compatibility invariant ``theta + nu``.  Both branches
  retain the source point and upstream state exactly; neither one constructs a
  global boundary or a shock-cell geometry.
  """

  status: MocMixedWaveStatus
  regime: MocMixedWaveRegime | None
  upstream_state: CharacteristicState | None
  downstream_state: CharacteristicState | None
  point_m: tuple[float, float] | None
  upstream_pressure_Pa: float | None
  downstream_pressure_Pa: float | None
  upstream_total_pressure_Pa: float | None
  downstream_total_pressure_Pa: float | None
  target_flow_angle_rad: float | None
  signed_turn_rad: float | None
  pressure_ratio: float | None
  total_pressure_ratio: float | None
  beta_rad: float | None
  characteristic_family: CharacteristicFamily | None
  turn_residual: float | None
  compatibility_residual: float | None
  shock_result: MocTurnCompressionResult | None = None
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedWaveStatus):
      raise TypeError('status must be a MocMixedWaveStatus')
    ####
    if self.regime is not None and not isinstance(self.regime, MocMixedWaveRegime):
      raise TypeError('regime must be a MocMixedWaveRegime or None')
    ####
    for name in ('upstream_state', 'downstream_state'):
      state = getattr(self, name)
      if state is not None and not isinstance(state, CharacteristicState):
        raise TypeError(f'{name} must be a CharacteristicState or None')
      ####
    ####
    if self.point_m is not None:
      point = tuple(float(value) for value in self.point_m)
      if len(point) != 2 or not all(isfinite(value) for value in point):
        raise ValueError('point_m must contain two finite coordinates')
      ####
      object.__setattr__(self, 'point_m', point)
    ####
    for name in (
      'upstream_pressure_Pa',
      'downstream_pressure_Pa',
      'upstream_total_pressure_Pa',
      'downstream_total_pressure_Pa',
    ):
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
      'target_flow_angle_rad',
      'signed_turn_rad',
      'pressure_ratio',
      'total_pressure_ratio',
      'beta_rad',
      'turn_residual',
      'compatibility_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric):
        raise ValueError(f'{name} must be finite when supplied')
      ####
      if name in (
        'pressure_ratio',
        'total_pressure_ratio',
        'beta_rad',
        'turn_residual',
        'compatibility_residual',
      ) and numeric < 0.0:
        raise ValueError(f'{name} must be nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.characteristic_family is not None and not isinstance(
      self.characteristic_family,
      CharacteristicFamily,
    ):
      raise TypeError('characteristic_family must be a CharacteristicFamily or None')
    ####
    if self.shock_result is not None and not isinstance(
      self.shock_result,
      MocTurnCompressionResult,
    ):
      raise TypeError('shock_result must be a MocTurnCompressionResult or None')
    ####
    if not isinstance(self.chain_promotion_blocked, bool):
      raise TypeError('chain_promotion_blocked must be a bool')
    ####
    if not isinstance(self.production_claim_allowed, bool):
      raise TypeError('production_claim_allowed must be a bool')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('mixed-wave samples must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('mixed-wave samples cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocMixedWaveStatus.CONVERGED
  ####

  @property
  def pressure_direction_verified(self) -> bool:
    if not self.converged or self.upstream_pressure_Pa is None:
      return False
    ####
    if self.downstream_pressure_Pa is None:
      return False
    ####
    if self.regime is MocMixedWaveRegime.COMPRESSION_SHOCK:
      return self.downstream_pressure_Pa > self.upstream_pressure_Pa
    ####
    if self.regime is MocMixedWaveRegime.ISENTROPIC_EXPANSION:
      return self.downstream_pressure_Pa < self.upstream_pressure_Pa
    ####
    return self.downstream_pressure_Pa == self.upstream_pressure_Pa
  ####

  @property
  def entropy_direction_verified(self) -> bool:
    if not self.converged:
      return False
    ####
    if (
      self.upstream_total_pressure_Pa is None
      or self.downstream_total_pressure_Pa is None
      or self.total_pressure_ratio is None
    ):
      return False
    ####
    if self.regime is MocMixedWaveRegime.COMPRESSION_SHOCK:
      return self.downstream_total_pressure_Pa < self.upstream_total_pressure_Pa
    ####
    return self.total_pressure_ratio == 1.0
  ####

  def as_report(self) -> dict[str, Any]:
    shock_report = None
    if self.shock_result is not None:
      shock_report = {
        'status': self.shock_result.status.value,
        'shock_status': self.shock_result.shock_status.value,
        'branch': self.shock_result.branch.value,
        'target_turn_rad': self.shock_result.target_turn_rad,
        'turn_residual': self.shock_result.turn_residual,
        'beta_rad': self.shock_result.beta_rad,
      }
    ####
    return {
      'status': self.status.value,
      'converged': self.converged,
      'regime': None if self.regime is None else self.regime.value,
      'point_m': self.point_m,
      'upstream_pressure_Pa': self.upstream_pressure_Pa,
      'downstream_pressure_Pa': self.downstream_pressure_Pa,
      'upstream_total_pressure_Pa': self.upstream_total_pressure_Pa,
      'downstream_total_pressure_Pa': self.downstream_total_pressure_Pa,
      'target_flow_angle_rad': self.target_flow_angle_rad,
      'signed_turn_rad': self.signed_turn_rad,
      'pressure_ratio': self.pressure_ratio,
      'total_pressure_ratio': self.total_pressure_ratio,
      'beta_rad': self.beta_rad,
      'characteristic_family': (
        None
        if self.characteristic_family is None
        else self.characteristic_family.value
      ),
      'turn_residual': self.turn_residual,
      'compatibility_residual': self.compatibility_residual,
      'pressure_direction_verified': self.pressure_direction_verified,
      'entropy_direction_verified': self.entropy_direction_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'shock_result': shock_report,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocMixedWavePathResult:
  """Auditable ordered path of local signed wave samples.

  The path wrapper consumes explicit source states, pressures, and target
  angles.  It does not feed a generated downstream state into the next sample;
  preserving that distinction prevents a local law from silently becoming a
  global marching or feedback solver.
  """

  status: MocMixedWavePathStatus
  samples: tuple[MocMixedWaveSampleResult, ...]
  path_points_m: tuple[tuple[float, float], ...]
  path_geometry_verified: bool
  source_pressure_lineage_verified: bool
  maximum_compatibility_residual: float | None
  minimum_total_pressure_ratio: float | None
  regime_counts: tuple[tuple[str, int], ...]
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''
  target_pressure_Pa: float | None = None
  maximum_static_pressure_residual_fraction: float | None = None
  target_pressure_verified: bool = False

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocMixedWavePathStatus):
      raise TypeError('status must be a MocMixedWavePathStatus')
    ####
    samples = tuple(self.samples)
    if any(not isinstance(sample, MocMixedWaveSampleResult) for sample in samples):
      raise TypeError('samples must contain MocMixedWaveSampleResult values')
    ####
    object.__setattr__(self, 'samples', samples)
    points = tuple(tuple(float(value) for value in point) for point in self.path_points_m)
    if any(
      len(point) != 2 or not all(isfinite(value) for value in point)
      for point in points
    ):
      raise ValueError('path_points_m must contain finite two-dimensional points')
    ####
    if len(points) != len(samples):
      raise ValueError('path_points_m and samples must have equal lengths')
    ####
    object.__setattr__(self, 'path_points_m', points)
    for name in (
      'path_geometry_verified',
      'source_pressure_lineage_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('mixed-wave paths must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('mixed-wave paths cannot allow production claims')
    ####
    if self.target_pressure_Pa is not None:
      target_pressure = float(self.target_pressure_Pa)
      if not isfinite(target_pressure) or target_pressure <= 0.0:
        raise ValueError('target_pressure_Pa must be finite and positive')
      ####
      object.__setattr__(self, 'target_pressure_Pa', target_pressure)
    ####
    if self.maximum_static_pressure_residual_fraction is not None:
      residual = float(self.maximum_static_pressure_residual_fraction)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'maximum_static_pressure_residual_fraction must be finite and nonnegative'
        )
      ####
      object.__setattr__(
        self,
        'maximum_static_pressure_residual_fraction',
        residual,
      )
    ####
    if not isinstance(self.target_pressure_verified, bool):
      raise TypeError('target_pressure_verified must be a bool')
    ####
    if self.target_pressure_verified and (
      self.target_pressure_Pa is None
      or self.maximum_static_pressure_residual_fraction is None
    ):
      raise ValueError(
        'target_pressure_verified requires target pressure and residual evidence'
      )
    ####
    for name in (
      'maximum_compatibility_residual',
      'minimum_total_pressure_ratio',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    counts = tuple((str(name), int(count)) for name, count in self.regime_counts)
    if any(count < 0 for _, count in counts):
      raise ValueError('regime_counts cannot contain negative counts')
    ####
    object.__setattr__(self, 'regime_counts', counts)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocMixedWavePathStatus.CONVERGED
      and self.path_geometry_verified
      and self.source_pressure_lineage_verified
      and (
        self.target_pressure_Pa is None or self.target_pressure_verified
      )
      and all(sample.converged for sample in self.samples)
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'path_points_m': self.path_points_m,
      'path_geometry_verified': self.path_geometry_verified,
      'source_pressure_lineage_verified': self.source_pressure_lineage_verified,
      'maximum_compatibility_residual': self.maximum_compatibility_residual,
      'minimum_total_pressure_ratio': self.minimum_total_pressure_ratio,
      'regime_counts': dict(self.regime_counts),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'target_pressure_Pa': self.target_pressure_Pa,
      'maximum_static_pressure_residual_fraction': (
        self.maximum_static_pressure_residual_fraction
      ),
      'target_pressure_verified': self.target_pressure_verified,
      'samples': tuple(sample.as_report() for sample in self.samples),
      'message': self.message,
    }
  ####
####


def _sample_failure(
  *,
  status: MocMixedWaveStatus,
  regime: MocMixedWaveRegime | None,
  upstream: CharacteristicState | None,
  point: tuple[float, float] | None,
  upstream_pressure: float | None,
  target_angle: float | None,
  signed_turn: float | None,
  message: str,
  shock_result: MocTurnCompressionResult | None = None,
  downstream_state: CharacteristicState | None = None,
  downstream_pressure: float | None = None,
  upstream_total_pressure: float | None = None,
  downstream_total_pressure: float | None = None,
  pressure_ratio: float | None = None,
  total_pressure_ratio: float | None = None,
  beta_rad: float | None = None,
  characteristic_family: CharacteristicFamily | None = None,
  turn_residual: float | None = None,
  compatibility_residual: float | None = None,
) -> MocMixedWaveSampleResult:
  return MocMixedWaveSampleResult(
    status=status,
    regime=regime,
    upstream_state=upstream,
    downstream_state=downstream_state,
    point_m=point,
    upstream_pressure_Pa=upstream_pressure,
    downstream_pressure_Pa=downstream_pressure,
    upstream_total_pressure_Pa=upstream_total_pressure,
    downstream_total_pressure_Pa=downstream_total_pressure,
    target_flow_angle_rad=target_angle,
    signed_turn_rad=signed_turn,
    pressure_ratio=pressure_ratio,
    total_pressure_ratio=total_pressure_ratio,
    beta_rad=beta_rad,
    characteristic_family=characteristic_family,
    turn_residual=turn_residual,
    compatibility_residual=compatibility_residual,
    shock_result=shock_result,
    message=message,
  )
####


def solve_mixed_wave_sample(
  upstream: CharacteristicState,
  *,
  upstream_pressure_Pa: float,
  target_flow_angle_rad: float,
  branch: ShockBranch = ShockBranch.WEAK,
  turn_tolerance_rad: float = 1.0e-12,
  residual_tolerance: float = 1.0e-10,
) -> MocMixedWaveSampleResult:
  """Solve one local compression, expansion, or zero-strength wave.

  A positive signed turn selects an attached shock.  A negative signed turn
  selects an isentropic ``C-`` expansion, with ``theta + nu`` conserved and
  total pressure unchanged.  The zero-turn case is retained as a Mach-wave
  limit.  The function never converts a detached shock or an out-of-domain
  expansion into a fallback state.
  """

  if not isinstance(upstream, CharacteristicState):
    return _sample_failure(
      status=MocMixedWaveStatus.INVALID_INPUT,
      regime=None,
      upstream=None,
      point=None,
      upstream_pressure=None,
      target_angle=None,
      signed_turn=None,
      message='upstream must be a CharacteristicState',
    )
  ####
  pressure = _finite_positive(upstream_pressure_Pa)
  try:
    target_angle = float(target_flow_angle_rad)
  except (TypeError, ValueError):
    target_angle = float('nan')
  ####
  try:
    turn_tolerance = float(turn_tolerance_rad)
    invariant_tolerance = float(residual_tolerance)
  except (TypeError, ValueError):
    turn_tolerance = float('nan')
    invariant_tolerance = float('nan')
  ####
  if pressure is None or not isfinite(target_angle):
    return _sample_failure(
      status=MocMixedWaveStatus.INVALID_INPUT,
      regime=None,
      upstream=upstream,
      point=(upstream.x_m, upstream.y_m),
      upstream_pressure=pressure,
      target_angle=target_angle,
      signed_turn=None,
      message='upstream pressure and target flow angle must be finite and valid',
    )
  ####
  if (
    not isfinite(turn_tolerance)
    or turn_tolerance <= 0.0
    or not isfinite(invariant_tolerance)
    or invariant_tolerance <= 0.0
  ):
    return _sample_failure(
      status=MocMixedWaveStatus.INVALID_INPUT,
      regime=None,
      upstream=upstream,
      point=(upstream.x_m, upstream.y_m),
      upstream_pressure=pressure,
      target_angle=target_angle,
      signed_turn=None,
      message='wave tolerances must be finite and positive',
    )
  ####
  if not isinstance(branch, ShockBranch):
    return _sample_failure(
      status=MocMixedWaveStatus.INVALID_INPUT,
      regime=None,
      upstream=upstream,
      point=(upstream.x_m, upstream.y_m),
      upstream_pressure=pressure,
      target_angle=target_angle,
      signed_turn=None,
      message='branch must be a ShockBranch',
    )
  ####
  gamma = upstream.gamma
  mach = upstream.mach
  upstream_total_pressure = _total_pressure(
    static_pressure_Pa=pressure,
    mach=mach,
    gamma=gamma,
  )
  signed_turn = target_angle - upstream.theta_rad
  point = (upstream.x_m, upstream.y_m)
  if abs(signed_turn) <= turn_tolerance:
    return MocMixedWaveSampleResult(
      status=MocMixedWaveStatus.CONVERGED,
      regime=MocMixedWaveRegime.MACH_WAVE,
      upstream_state=upstream,
      downstream_state=upstream,
      point_m=point,
      upstream_pressure_Pa=pressure,
      downstream_pressure_Pa=pressure,
      upstream_total_pressure_Pa=upstream_total_pressure,
      downstream_total_pressure_Pa=upstream_total_pressure,
      target_flow_angle_rad=target_angle,
      signed_turn_rad=signed_turn,
      pressure_ratio=1.0,
      total_pressure_ratio=1.0,
      beta_rad=upstream.mu_rad,
      characteristic_family=None,
      turn_residual=abs(signed_turn),
      compatibility_residual=0.0,
    )
  ####
  if signed_turn > 0.0:
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=mach,
        gamma=gamma,
        upstream_pressure_Pa=pressure,
        target_turn_rad=signed_turn,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _sample_failure(
        status=MocMixedWaveStatus.COMPRESSION_FAILURE,
        regime=MocMixedWaveRegime.COMPRESSION_SHOCK,
        upstream=upstream,
        point=point,
        upstream_pressure=pressure,
        target_angle=target_angle,
        signed_turn=signed_turn,
        upstream_total_pressure=upstream_total_pressure,
        message=f'attached compression solve raised: {error}',
      )
    ####
    downstream_state = None
    if compression.downstream_mach is not None and compression.downstream_mach > 1.0:
      downstream_state = CharacteristicState(
        x_m=upstream.x_m,
        y_m=upstream.y_m,
        theta_rad=target_angle,
        mach=compression.downstream_mach,
        gamma=gamma,
      )
    ####
    downstream_pressure = compression.downstream_pressure_Pa
    downstream_total_pressure = compression.downstream_total_pressure_Pa
    valid = bool(
      compression.converged
      and downstream_state is not None
      and downstream_pressure is not None
      and downstream_total_pressure is not None
      and downstream_pressure > pressure
      and downstream_total_pressure < upstream_total_pressure
      and compression.total_pressure_ratio is not None
      and 0.0 < compression.total_pressure_ratio < 1.0
      and compression.turn_residual is not None
      and abs(compression.turn_residual) <= invariant_tolerance
    )
    return _sample_failure(
      status=(
        MocMixedWaveStatus.CONVERGED
        if valid
        else (
          MocMixedWaveStatus.COMPRESSION_FAILURE
          if not compression.converged
          else MocMixedWaveStatus.INVARIANT_FAILURE
        )
      ),
      regime=MocMixedWaveRegime.COMPRESSION_SHOCK,
      upstream=upstream,
      point=point,
      upstream_pressure=pressure,
      target_angle=target_angle,
      signed_turn=signed_turn,
      downstream_state=downstream_state,
      downstream_pressure=downstream_pressure,
      upstream_total_pressure=upstream_total_pressure,
      downstream_total_pressure=downstream_total_pressure,
      pressure_ratio=compression.pressure_ratio,
      total_pressure_ratio=compression.total_pressure_ratio,
      beta_rad=compression.beta_rad,
      turn_residual=(
        None
        if compression.turn_residual is None
        else abs(compression.turn_residual)
      ),
      shock_result=compression,
      message=(
        ''
        if valid
        else (
          compression.message
          or 'attached compression did not satisfy its shock invariants'
        )
      ),
    )
  ####
  try:
    target_nu = upstream.nu_rad - signed_turn
    inverse = inverse_prandtl_meyer_angle_rad(target_nu, gamma)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _sample_failure(
      status=MocMixedWaveStatus.EXPANSION_OUTSIDE_DOMAIN,
      regime=MocMixedWaveRegime.ISENTROPIC_EXPANSION,
      upstream=upstream,
      point=point,
      upstream_pressure=pressure,
      target_angle=target_angle,
      signed_turn=signed_turn,
      upstream_total_pressure=upstream_total_pressure,
      characteristic_family=CharacteristicFamily.MINUS,
      message=f'Prandtl--Meyer expansion inversion raised: {error}',
    )
  ####
  if not inverse.converged or inverse.value is None or inverse.value <= 1.0:
    return _sample_failure(
      status=MocMixedWaveStatus.EXPANSION_OUTSIDE_DOMAIN,
      regime=MocMixedWaveRegime.ISENTROPIC_EXPANSION,
      upstream=upstream,
      point=point,
      upstream_pressure=pressure,
      target_angle=target_angle,
      signed_turn=signed_turn,
      upstream_total_pressure=upstream_total_pressure,
      characteristic_family=CharacteristicFamily.MINUS,
      message=(
        'requested expansion is outside the finite supersonic '
        f'Prandtl--Meyer domain: {inverse.message}'
      ),
    )
  ####
  downstream_mach = float(inverse.value)
  downstream_pressure = _static_pressure(
    total_pressure_Pa=upstream_total_pressure,
    mach=downstream_mach,
    gamma=gamma,
  )
  downstream_state = CharacteristicState(
    x_m=upstream.x_m,
    y_m=upstream.y_m,
    theta_rad=target_angle,
    mach=downstream_mach,
    gamma=gamma,
  )
  compatibility_residual = abs(
    downstream_state.theta_rad
    + downstream_state.nu_rad
    - upstream.theta_rad
    - upstream.nu_rad
  )
  pressure_ratio = downstream_pressure / pressure
  total_pressure_ratio = 1.0
  valid = bool(
    downstream_pressure < pressure
    and compatibility_residual <= invariant_tolerance
    and isfinite(pressure_ratio)
    and pressure_ratio > 0.0
  )
  return _sample_failure(
    status=(
      MocMixedWaveStatus.CONVERGED
      if valid
      else MocMixedWaveStatus.INVARIANT_FAILURE
    ),
    regime=MocMixedWaveRegime.ISENTROPIC_EXPANSION,
    upstream=upstream,
    point=point,
    upstream_pressure=pressure,
    target_angle=target_angle,
    signed_turn=signed_turn,
    downstream_state=downstream_state,
    downstream_pressure=downstream_pressure,
    upstream_total_pressure=upstream_total_pressure,
    downstream_total_pressure=upstream_total_pressure,
    pressure_ratio=pressure_ratio,
    total_pressure_ratio=total_pressure_ratio,
    characteristic_family=CharacteristicFamily.MINUS,
    turn_residual=0.0,
    compatibility_residual=compatibility_residual,
    message=(
      ''
      if valid
      else 'isentropic expansion did not satisfy pressure or C- invariants'
    ),
  )
####


def solve_mixed_wave_path(
  upstream_states: Sequence[CharacteristicState],
  upstream_pressures_Pa: Sequence[float],
  target_flow_angles_rad: Sequence[float],
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  turn_tolerance_rad: float = 1.0e-12,
  residual_tolerance: float = 1.0e-10,
  position_tolerance_m: float = 1.0e-12,
) -> MocMixedWavePathResult:
  """Solve an explicit downstream-ordered path of signed local wave laws.

  The source arrays must have equal length and strictly increasing axial
  coordinates.  The function returns partial typed samples when a later law
  fails, but never fabricates the failed sample or continues past it.
  """

  try:
    states = tuple(upstream_states)
    pressures = tuple(float(value) for value in upstream_pressures_Pa)
    targets = tuple(float(value) for value in target_flow_angles_rad)
    tolerance = float(position_tolerance_m)
  except (TypeError, ValueError):
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=False,
      source_pressure_lineage_verified=False,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      message='path inputs must be finite sequences',
    )
  ####
  if (
    not states
    or len(states) != len(pressures)
    or len(states) != len(targets)
    or not isfinite(tolerance)
    or tolerance <= 0.0
    or not isinstance(branch, ShockBranch)
  ):
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=False,
      source_pressure_lineage_verified=False,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      message=(
        'path requires non-empty equal-length inputs, positive position '
        'tolerance, and a ShockBranch'
      ),
    )
  ####
  if any(not isinstance(state, CharacteristicState) for state in states):
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=False,
      source_pressure_lineage_verified=False,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      message='upstream_states must contain CharacteristicState values',
    )
  ####
  path_points = tuple((state.x_m, state.y_m) for state in states)
  path_geometry_verified = all(
    current[0] > previous[0] + tolerance
    for previous, current in zip(path_points, path_points[1:])
  )
  source_pressure_lineage_verified = all(
    isfinite(pressure) and pressure > 0.0 for pressure in pressures
  )
  if not path_geometry_verified or not source_pressure_lineage_verified:
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=path_geometry_verified,
      source_pressure_lineage_verified=source_pressure_lineage_verified,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      message=(
        'path points must advance strictly downstream and source pressures '
        'must be finite and positive'
      ),
    )
  ####
  samples: list[MocMixedWaveSampleResult] = []
  for index, (state, pressure, target) in enumerate(
    zip(states, pressures, targets),
  ):
    sample = solve_mixed_wave_sample(
      state,
      upstream_pressure_Pa=pressure,
      target_flow_angle_rad=target,
      branch=branch,
      turn_tolerance_rad=turn_tolerance_rad,
      residual_tolerance=residual_tolerance,
    )
    samples.append(sample)
    if not sample.converged:
      return _build_path_result(
        status=MocMixedWavePathStatus.SAMPLE_FAILURE,
        samples=tuple(samples),
        path_points=path_points,
        path_geometry_verified=path_geometry_verified,
        source_pressure_lineage_verified=source_pressure_lineage_verified,
        message=f'mixed-wave path sample {index} failed: {sample.message}',
      )
    ####
  ####
  return _build_path_result(
    status=MocMixedWavePathStatus.CONVERGED,
    samples=tuple(samples),
    path_points=path_points,
    path_geometry_verified=path_geometry_verified,
    source_pressure_lineage_verified=source_pressure_lineage_verified,
    message='ordered local mixed-wave path converged; global closure remains open',
  )
####


def solve_mixed_wave_pressure_target_path(
  upstream_states: Sequence[CharacteristicState],
  upstream_pressures_Pa: Sequence[float],
  target_pressure_Pa: float,
  *,
  branch: ShockBranch = ShockBranch.WEAK,
  pressure_tolerance_fraction: float = 1.0e-10,
  turn_tolerance_rad: float = 1.0e-12,
  residual_tolerance: float = 1.0e-10,
  position_tolerance_m: float = 1.0e-12,
) -> MocMixedWavePathResult:
  """Solve a local mixed-wave path to one explicit static-pressure target.

  For each source state, a target above the source pressure selects an
  attached compression shock; a target below it derives the target Mach number
  from the retained source total pressure and selects an isentropic ``C-``
  expansion.  The resulting local wave samples are checked against the
  requested pressure; no global boundary shape is inferred.
  """

  try:
    states = tuple(upstream_states)
    pressures = tuple(float(value) for value in upstream_pressures_Pa)
    target_pressure = float(target_pressure_Pa)
    pressure_tolerance = float(pressure_tolerance_fraction)
  except (TypeError, ValueError):
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=False,
      source_pressure_lineage_verified=False,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      target_pressure_Pa=None,
      message='pressure-target path inputs must be finite sequences',
    )
  ####
  if (
    not states
    or len(states) != len(pressures)
    or not isfinite(target_pressure)
    or target_pressure <= 0.0
    or not isfinite(pressure_tolerance)
    or pressure_tolerance <= 0.0
    or not isinstance(branch, ShockBranch)
  ):
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=False,
      source_pressure_lineage_verified=False,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      target_pressure_Pa=target_pressure,
      message=(
        'pressure-target path requires non-empty equal-length inputs, a '
        'positive target/tolerance, and a ShockBranch'
      ),
    )
  ####
  if any(not isinstance(state, CharacteristicState) for state in states):
    return MocMixedWavePathResult(
      status=MocMixedWavePathStatus.INVALID_INPUT,
      samples=(),
      path_points_m=(),
      path_geometry_verified=False,
      source_pressure_lineage_verified=False,
      maximum_compatibility_residual=None,
      minimum_total_pressure_ratio=None,
      regime_counts=(),
      target_pressure_Pa=target_pressure,
      message='upstream_states must contain CharacteristicState values',
    )
  ####
  target_angles: list[float] = []
  for index, (state, pressure) in enumerate(zip(states, pressures)):
    if not isfinite(pressure) or pressure <= 0.0:
      return MocMixedWavePathResult(
        status=MocMixedWavePathStatus.INVALID_INPUT,
        samples=(),
        path_points_m=(),
        path_geometry_verified=False,
        source_pressure_lineage_verified=False,
        maximum_compatibility_residual=None,
        minimum_total_pressure_ratio=None,
        regime_counts=(),
        target_pressure_Pa=target_pressure,
        message=f'source pressure {index} must be finite and positive',
      )
    ####
    if target_pressure >= pressure * (1.0 - pressure_tolerance):
      if target_pressure <= pressure * (1.0 + pressure_tolerance):
        target_angles.append(state.theta_rad)
        continue
      ####
      try:
        compression = solve_attached_compression_to_pressure(
          upstream_mach=state.mach,
          gamma=state.gamma,
          upstream_pressure_Pa=pressure,
          target_pressure_Pa=target_pressure,
          branch=branch,
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        return MocMixedWavePathResult(
          status=MocMixedWavePathStatus.SAMPLE_FAILURE,
          samples=(),
          path_points_m=(),
          path_geometry_verified=False,
          source_pressure_lineage_verified=True,
          maximum_compatibility_residual=None,
          minimum_total_pressure_ratio=None,
          regime_counts=(),
          target_pressure_Pa=target_pressure,
          message=f'source {index} compression target raised: {error}',
        )
      ####
      if not compression.converged or compression.theta_rad is None:
        return MocMixedWavePathResult(
          status=MocMixedWavePathStatus.SAMPLE_FAILURE,
          samples=(),
          path_points_m=(),
          path_geometry_verified=False,
          source_pressure_lineage_verified=True,
          maximum_compatibility_residual=None,
          minimum_total_pressure_ratio=None,
          regime_counts=(),
          target_pressure_Pa=target_pressure,
          message=(
            f'source {index} attached compression could not reach the target '
            f'pressure: {compression.message}'
          ),
        )
      ####
      target_angles.append(state.theta_rad + compression.theta_rad)
      continue
    ####
    total_pressure = _total_pressure(
      static_pressure_Pa=pressure,
      mach=state.mach,
      gamma=state.gamma,
    )
    try:
      inverse = supersonic_mach_from_stagnation_pressure_ratio(
        total_pressure / target_pressure,
        state.gamma,
      )
      if not inverse.converged or inverse.value is None:
        raise ValueError(inverse.message)
      ####
      target_nu = prandtl_meyer_angle_rad(inverse.value, state.gamma)
      target_angles.append(
        state.theta_rad - (target_nu - state.nu_rad)
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocMixedWavePathResult(
        status=MocMixedWavePathStatus.INVALID_INPUT,
        samples=(),
        path_points_m=(),
        path_geometry_verified=False,
        source_pressure_lineage_verified=True,
        maximum_compatibility_residual=None,
        minimum_total_pressure_ratio=None,
        regime_counts=(),
        target_pressure_Pa=target_pressure,
        message=f'source {index} pressure target inversion failed: {error}',
      )
    ####
  ####
  path = solve_mixed_wave_path(
    states,
    pressures,
    target_angles,
    branch=branch,
    turn_tolerance_rad=turn_tolerance_rad,
    residual_tolerance=residual_tolerance,
    position_tolerance_m=position_tolerance_m,
  )
  residuals = [
    abs(sample.downstream_pressure_Pa - target_pressure) / target_pressure
    for sample in path.samples
    if sample.downstream_pressure_Pa is not None
  ]
  maximum_residual = max(residuals) if residuals else None
  target_verified = bool(
    path.status is MocMixedWavePathStatus.CONVERGED
    and len(residuals) == len(path.samples)
    and maximum_residual is not None
    and maximum_residual <= pressure_tolerance
  )
  status = path.status
  if status is MocMixedWavePathStatus.CONVERGED and not target_verified:
    status = MocMixedWavePathStatus.SAMPLE_FAILURE
  ####
  return replace(
    path,
    status=status,
    target_pressure_Pa=target_pressure,
    maximum_static_pressure_residual_fraction=maximum_residual,
    target_pressure_verified=target_verified,
    message=(
      'local mixed-wave path matched the explicit static-pressure target; '
      'global interface and boundary closure remain open'
      if target_verified
      else (
        path.message
        or 'local mixed-wave path did not match the explicit static-pressure target'
      )
    ),
  )
####


def _build_path_result(
  *,
  status: MocMixedWavePathStatus,
  samples: tuple[MocMixedWaveSampleResult, ...],
  path_points: tuple[tuple[float, float], ...],
  path_geometry_verified: bool,
  source_pressure_lineage_verified: bool,
  message: str,
  target_pressure_Pa: float | None = None,
  maximum_static_pressure_residual_fraction: float | None = None,
  target_pressure_verified: bool = False,
) -> MocMixedWavePathResult:
  residuals = [
    sample.compatibility_residual
    for sample in samples
    if sample.compatibility_residual is not None
  ]
  ratios = [
    sample.total_pressure_ratio
    for sample in samples
    if sample.total_pressure_ratio is not None
  ]
  counts: dict[str, int] = {}
  for sample in samples:
    if sample.regime is not None:
      key = sample.regime.value
      counts[key] = counts.get(key, 0) + 1
    ####
  ####
  return MocMixedWavePathResult(
    status=status,
    samples=samples,
    path_points_m=path_points[:len(samples)],
    path_geometry_verified=path_geometry_verified,
    source_pressure_lineage_verified=source_pressure_lineage_verified,
    maximum_compatibility_residual=max(residuals) if residuals else None,
    minimum_total_pressure_ratio=min(ratios) if ratios else None,
    regime_counts=tuple(sorted(counts.items())),
    target_pressure_Pa=target_pressure_Pa,
    maximum_static_pressure_residual_fraction=(
      maximum_static_pressure_residual_fraction
    ),
    target_pressure_verified=target_pressure_verified,
    message=message,
  )
####
