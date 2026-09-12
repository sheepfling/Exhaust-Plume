"""Bounded pressure correction from the local characteristic free boundary.

The mixed-regime frontier lane now solves a local characteristic pressure and
tangency equation, while the global physical closure owns a separate outer
ambient boundary.  This adapter connects the pressure equation to a fresh
global Euler re-solve without conflating those two geometries:

``audited local free boundary -> bounded pressure overlay -> fresh global
Euler closure``

Only the pressure trace is consumed.  The local characteristic curve is an
interior research branch and is therefore not supplied as outer-boundary
geometry.  A successful bounded descent is useful coupling evidence, but it
does not close the second characteristic family, conservative/entropy
equations, downstream boundary, canonical fixed point, shock-cell, or
production gates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
import json
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
  solve_reflected_domain_global_physical_closure,
)
from exhaust_plume.models.moc.physical_field_euler_reconciliation import (
  MocPhysicalFieldEulerBoundaryPressureTarget,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit',
  'run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction',
  'audit_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-characteristic-free-boundary-pressure-correction-v1'
)
MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL = (
  'research-global-mixed-regime-characteristic-free-boundary-pressure-correction-v1'
)
DEFAULT_PRESSURE_CORRECTION_FRACTIONS = (
  0.0,
  0.01,
  0.025,
  0.05,
  0.1,
  0.2,
  0.4,
  0.7,
  1.0,
)


class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus(
  str,
  Enum,
):
  """Typed outcomes of the bounded pressure-only coupling ladder."""

  CONVERGED_RESEARCH_PRESSURE_CORRECTION = (
    'converged-research-characteristic-free-boundary-pressure-correction'
  )
  INVALID_INPUT = 'invalid_input'
  SOURCE_CLOSURE_FAILURE = (
    'characteristic-free-boundary-pressure-correction-source-closure-failure'
  )
  FRONTIER_FAILURE = (
    'characteristic-free-boundary-pressure-correction-frontier-failure'
  )
  TARGET_COVERAGE_FAILURE = (
    'characteristic-free-boundary-pressure-correction-target-coverage-failure'
  )
  BASELINE_FAILURE = (
    'characteristic-free-boundary-pressure-correction-baseline-failure'
  )
  NO_ADMISSIBLE_TRIAL = (
    'characteristic-free-boundary-pressure-correction-no-admissible-trial'
  )
  CANDIDATE_FAILURE = (
    'characteristic-free-boundary-pressure-correction-candidate-failure'
  )
####


class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of independently replaying the pressure correction."""

  VERIFIED_RESEARCH_PRESSURE_CORRECTION = (
    'verified-research-characteristic-free-boundary-pressure-correction'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = (
    'characteristic-free-boundary-pressure-correction-audit-replay-failure'
  )
  LINEAGE_FAILURE = (
    'characteristic-free-boundary-pressure-correction-audit-lineage-failure'
  )
  TRIAL_LADDER_FAILURE = (
    'characteristic-free-boundary-pressure-correction-audit-trial-ladder-failure'
  )
####


def _positive(name: str, value: object) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


def _frontier_fingerprint(
  step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
) -> str:
  payload = {
    'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_OPERATOR_ID,
    'case_id': step.case_id,
    'step': step.as_report(),
  }
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _fraction_token(fraction: float) -> str:
  return format(float(fraction), '.17g')
####


def _build_source_band_base_target(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  source_id: str,
) -> MocPhysicalFieldEulerBoundaryPressureTarget:
  """Build the complete solver-owned outer pressure frame for one trial."""

  source_band = closure.source_band
  if source_band is None or not source_band.source_field_verified:
    raise ValueError('source closure retained no verified source band')
  ####
  seed_state = source_band.outer_seed_state
  seed_total_pressure = source_band.outer_seed_total_pressure_Pa
  boundary = source_band.ambient_boundary
  if seed_state is None or seed_total_pressure is None or boundary is None:
    raise ValueError('source band retained no complete ambient pressure frame')
  ####
  seed_static_pressure = seed_total_pressure / (
    1.0 + 0.5 * (seed_state.gamma - 1.0) * seed_state.mach**2
  ) ** (seed_state.gamma / (seed_state.gamma - 1.0))
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=(
      seed_state.x_m,
      *tuple(point[0] for point in boundary.points_m),
    ),
    static_pressure_Pa=(seed_static_pressure, *boundary.static_pressure_Pa),
    source_id=source_id,
    boundary_points_m=(
      (seed_state.x_m, seed_state.y_m),
      *tuple(boundary.points_m),
    ),
    tangent_rad=(seed_state.theta_rad, *tuple(
      state.theta_rad for state in boundary.states
    )),
  )
####


def _local_pressure_frame(
  step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
) -> tuple[tuple[float, float], ...]:
  """Return ``(x, pressure)`` pairs using exact local branch order.

  The characteristic free-boundary request supplies pressure at incoming
  characteristic coordinates, while its result supplies the solved boundary
  coordinates.  The two sequences are intentionally paired by their exact
  solver order.  No spatial interpolation or endpoint extrapolation is
  introduced at this seam.
  """

  request = step.free_boundary_request
  profile = request.ambient_pressure_profile
  points = step.free_boundary.boundary_points_m
  if profile is None or len(profile) != len(points) or len(points) < 2:
    raise ValueError(
      'characteristic free-boundary pressure profile must match at least two '
      'solved boundary points'
    )
  ####
  frame: list[tuple[float, float]] = []
  for point, sample in zip(points, profile, strict=True):
    x_value = float(point[0])
    pressure = float(sample.ambient_pressure_Pa)
    if not isfinite(x_value) or not isfinite(pressure) or pressure <= 0.0:
      raise ValueError(
        'characteristic free-boundary pressure frame must be finite and positive'
      )
    ####
    if frame and x_value <= frame[-1][0]:
      raise ValueError(
        'characteristic free-boundary pressure frame must be downstream ordered'
      )
    ####
    frame.append((x_value, pressure))
  ####
  return tuple(frame)
####


def _build_pressure_overlay(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
  base_frame: MocPhysicalFieldEulerBoundaryPressureTarget,
  pressure_frame: Sequence[tuple[float, float]],
  fraction: float,
  *,
  source_closure_fingerprint: str,
  source_proposal_fingerprint: str,
) -> MocPhysicalFieldEulerBoundaryPressureTarget:
  """Relax the local characteristic pressure onto the full outer frame seam."""

  del closure  # The closure is retained in the fingerprints and exact request.
  source_id = (
    f'{MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL}'
    f':{step.case_id}:fraction:{_fraction_token(fraction)}'
  )
  base_source_id = f'global-physical-closure:source-band-base:{source_id}'
  if base_frame.source_id != base_source_id:
    raise ValueError(
      'base pressure frame identity does not match the declared trial overlay'
    )
  ####
  pressures: list[float] = []
  for x_value, characteristic_pressure in pressure_frame:
    base_pressure = base_frame.pressure_at_x(
      x_value,
      position_tolerance_m=1.0e-8,
    )
    if base_pressure is None:
      raise ValueError(
        'characteristic free-boundary pressure frame is outside the complete '
        'source-band target; no extrapolation is allowed'
      )
    ####
    pressure = base_pressure + fraction * (characteristic_pressure - base_pressure)
    if not isfinite(pressure) or pressure <= 0.0:
      raise ValueError('relaxed pressure overlay must remain finite and positive')
    ####
    pressures.append(float(pressure))
  ####
  return MocPhysicalFieldEulerBoundaryPressureTarget(
    x_stations_m=tuple(x_value for x_value, _pressure in pressure_frame),
    static_pressure_Pa=tuple(pressures),
    source_id=source_id,
    source_closure_fingerprint=source_closure_fingerprint,
    source_proposal_fingerprint=source_proposal_fingerprint,
  )
####


def _cell_residual(
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None,
) -> float | None:
  if closure is None or closure.field_audit is None:
    return None
  ####
  value = getattr(closure.field_audit, 'maximum_cell_euler_residual', None)
  if value is None:
    return None
  ####
  numeric = float(value)
  if not isfinite(numeric) or numeric < 0.0:
    return None
  ####
  return numeric
####


def _target_consumed(
  candidate: MocReflectedDomainGlobalPhysicalClosureResult | None,
  overlay: MocPhysicalFieldEulerBoundaryPressureTarget,
  *,
  source_closure_fingerprint: str,
  source_proposal_fingerprint: str,
) -> bool:
  """Verify the fresh source march consumed this exact pressure overlay."""

  if candidate is None or not candidate.source_pressure_target_consumed:
    return False
  ####
  source_band = candidate.source_band
  target = None if source_band is None else source_band.ambient_pressure_target
  expected_base = f'global-physical-closure:source-band-base:{overlay.source_id}'
  expected_source = f'global-physical-closure:source-band-overlay:{overlay.source_id}'
  return bool(
    source_band is not None
    and source_band.source_field_verified
    and target is not None
    and target.source_id == expected_source
    and target.composition_mode == 'explicit-overlay'
    and target.composition_base_source_id == expected_base
    and target.composition_overlay_source_id == overlay.source_id
    and target.source_closure_fingerprint == source_closure_fingerprint
    and target.source_proposal_fingerprint == source_proposal_fingerprint
    and candidate.source_pressure_target_source == expected_source
  )
####


def _fresh_global_resolve(
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  overlay: MocPhysicalFieldEulerBoundaryPressureTarget,
  request: 'MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest',
) -> MocReflectedDomainGlobalPhysicalClosureResult:
  """Re-run the selected source/remesh branch with the pressure target."""

  source_band = source_closure.source_band
  remesh = source_closure.global_remesh
  if source_band is None or remesh is None or remesh.selected_attempt is None:
    raise ValueError('source closure retained no selected global remesh attempt')
  ####
  selected = remesh.selected_attempt
  first_cell = selected.first_cell_result
  selected_field = first_cell.selected_physical_field
  bracket = first_cell.compression_amplitude_bracket
  if selected_field is None or selected_field.field is None or bracket is None:
    raise ValueError('selected global remesh attempt retained no complete field')
  ####
  return solve_reflected_domain_global_physical_closure(
    source_band,
    outer_source_indices=remesh.outer_source_indices,
    target_centerline_indices=remesh.target_centerline_indices,
    compression_amplitude_lower_rad=bracket[0],
    compression_amplitude_upper_rad=bracket[1],
    compression_envelope_skews=(selected.compression_envelope_skew,),
    incoming_handoff=source_band.incoming_handoff,
    ambient_pressure_target=overlay,
    sample_count=len(selected_field.field.shock_boundary_points_m),
    branch=ShockBranch.WEAK,
    position_tolerance_m=request.position_tolerance_m,
    shock_angle_tolerance_rad=request.shock_angle_tolerance_rad,
    maximum_boundary_iterations=request.maximum_boundary_iterations,
    consume_ambient_pressure_target_geometry=False,
    use_composed_source_pressure_target_for_global_euler=True,
    consume_ambient_pressure_target_geometry_at_global_boundary=False,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest:
  """Exact source/frontier inputs for one bounded pressure correction ladder."""

  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep
  fractions: tuple[float, ...] = DEFAULT_PRESSURE_CORRECTION_FRACTIONS
  seam_pressure_tolerance_fraction: float = 0.25
  position_tolerance_m: float = 1.0e-9
  shock_angle_tolerance_rad: float = 0.02
  maximum_boundary_iterations: int = 16
  source: str = (
    MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'source_closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    if not isinstance(
      self.source_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError(
        'source_frontier_step must be a typed shock-frontier refinement step'
      )
    ####
    if self.source_frontier_step.closure is not self.source_closure:
      raise ValueError(
        'source_frontier_step must retain the exact source_closure object'
      )
    ####
    fractions = tuple(float(value) for value in self.fractions)
    if len(fractions) < 2 or fractions[0] != 0.0:
      raise ValueError(
        'fractions must contain a zero baseline followed by at least one trial'
      )
    ####
    if any(
      not isfinite(value) or value < 0.0 or value > 1.0
      for value in fractions
    ):
      raise ValueError('fractions must be finite values in [0, 1]')
    ####
    if any(second <= first for first, second in zip(fractions, fractions[1:])):
      raise ValueError('fractions must be strictly increasing')
    ####
    if not any(value > 0.0 for value in fractions):
      raise ValueError('fractions must contain at least one positive trial')
    ####
    seam_tolerance = float(self.seam_pressure_tolerance_fraction)
    if not isfinite(seam_tolerance) or seam_tolerance < 0.0 or seam_tolerance >= 1.0:
      raise ValueError(
        'seam_pressure_tolerance_fraction must be finite in [0, 1)'
      )
    ####
    if (
      isinstance(self.maximum_boundary_iterations, bool)
      or not isinstance(self.maximum_boundary_iterations, int)
      or self.maximum_boundary_iterations < 1
    ):
      raise ValueError('maximum_boundary_iterations must be a positive integer')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    ####
    object.__setattr__(self, 'fractions', fractions)
    object.__setattr__(self, 'seam_pressure_tolerance_fraction', seam_tolerance)
    object.__setattr__(
      self,
      'position_tolerance_m',
      _positive('position_tolerance_m', self.position_tolerance_m),
    )
    object.__setattr__(
      self,
      'shock_angle_tolerance_rad',
      _positive('shock_angle_tolerance_rad', self.shock_angle_tolerance_rad),
    )
    object.__setattr__(self, 'source', source)
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    return moc_reflected_domain_global_physical_closure_fingerprint(
      self.source_closure
    )
  ####

  @property
  def source_frontier_fingerprint(self) -> str:
    return _frontier_fingerprint(self.source_frontier_step)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_OPERATOR_ID,
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL,
      'source': self.source,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'source_frontier_case_id': self.source_frontier_step.case_id,
      'source_frontier_fingerprint': self.source_frontier_fingerprint,
      'fractions': self.fractions,
      'seam_pressure_tolerance_fraction': self.seam_pressure_tolerance_fraction,
      'position_tolerance_m': self.position_tolerance_m,
      'shock_angle_tolerance_rad': self.shock_angle_tolerance_rad,
      'maximum_boundary_iterations': self.maximum_boundary_iterations,
      'pressure_trace_consumed': True,
      'characteristic_geometry_consumed': False,
      'research_only': True,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt:
  """One pressure fraction and its fresh global closure result."""

  pressure_fraction: float
  pressure_overlay: MocPhysicalFieldEulerBoundaryPressureTarget | None
  candidate_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  fresh_global_solve_attempted: bool = False
  pressure_target_consumed: bool = False
  target_geometry_consumed: bool = False
  physical_closure_verified: bool = False
  maximum_cell_euler_residual: float | None = None
  strict_improvement_over_baseline: bool = False
  accepted: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    fraction = float(self.pressure_fraction)
    if not isfinite(fraction) or fraction < 0.0 or fraction > 1.0:
      raise ValueError('pressure_fraction must be finite in [0, 1]')
    ####
    if self.pressure_overlay is not None and not isinstance(
      self.pressure_overlay,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError(
        'pressure_overlay must be a MocPhysicalFieldEulerBoundaryPressureTarget or None'
      )
    ####
    if self.candidate_closure is not None and not isinstance(
      self.candidate_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'candidate_closure must be a MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    if self.maximum_cell_euler_residual is not None:
      residual = float(self.maximum_cell_euler_residual)
      if not isfinite(residual) or residual < 0.0:
        raise ValueError(
          'maximum_cell_euler_residual must be finite and nonnegative'
        )
      ####
      object.__setattr__(self, 'maximum_cell_euler_residual', residual)
    ####
    for name in (
      'fresh_global_solve_attempted',
      'pressure_target_consumed',
      'target_geometry_consumed',
      'physical_closure_verified',
      'strict_improvement_over_baseline',
      'accepted',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'pressure_fraction', fraction)
    object.__setattr__(self, 'message', str(self.message))
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'pressure_fraction': self.pressure_fraction,
      'fresh_global_solve_attempted': self.fresh_global_solve_attempted,
      'pressure_target_consumed': self.pressure_target_consumed,
      'target_geometry_consumed': self.target_geometry_consumed,
      'physical_closure_verified': self.physical_closure_verified,
      'maximum_cell_euler_residual': self.maximum_cell_euler_residual,
      'strict_improvement_over_baseline': self.strict_improvement_over_baseline,
      'accepted': self.accepted,
      'pressure_overlay': (
        None if self.pressure_overlay is None else self.pressure_overlay.as_report()
      ),
      'candidate_closure_fingerprint': (
        None
        if self.candidate_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.candidate_closure
        )
      ),
      'candidate_closure': (
        None
        if self.candidate_closure is None
        else self.candidate_closure.as_report()
      ),
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult:
  """Research pressure-correction evidence below the global claim ceiling."""

  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus
  request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep | None
  base_target: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
  attempts: tuple[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt, ...] = ()
  selected_attempt_index: int | None = None
  selected_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  baseline_max_cell_euler_residual: float | None = None
  selected_max_cell_euler_residual: float | None = None
  pressure_trace_consumed: bool = False
  fresh_global_solve_verified: bool = False
  pressure_target_consumption_verified: bool = False
  strict_cell_residual_descent_verified: bool = False
  characteristic_geometry_segregated: bool = False
  fidelity_isolation_verified: bool = False
  canonical_free_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus,
    ):
      raise TypeError('status must be a typed pressure-correction status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest,
    ):
      raise TypeError('request must be a typed pressure-correction request')
    ####
    for name in ('source_closure', 'selected_closure'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalPhysicalClosureResult,
      ):
        raise TypeError(f'{name} must be a typed global physical closure')
      ####
    ####
    if self.source_frontier_step is not None and not isinstance(
      self.source_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError('source_frontier_step must be a typed frontier step')
    ####
    if self.base_target is not None and not isinstance(
      self.base_target,
      MocPhysicalFieldEulerBoundaryPressureTarget,
    ):
      raise TypeError('base_target must be a typed pressure target')
    ####
    attempts = tuple(self.attempts)
    if any(
      not isinstance(
        attempt,
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt,
      )
      for attempt in attempts
    ):
      raise TypeError('attempts must contain typed pressure-correction attempts')
    ####
    if self.selected_attempt_index is not None and (
      isinstance(self.selected_attempt_index, bool)
      or not isinstance(self.selected_attempt_index, int)
      or self.selected_attempt_index < 0
      or self.selected_attempt_index >= len(attempts)
    ):
      raise ValueError('selected_attempt_index must select a retained attempt')
    ####
    for name in (
      'baseline_max_cell_euler_residual',
      'selected_max_cell_euler_residual',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'pressure_trace_consumed',
      'fresh_global_solve_verified',
      'pressure_target_consumption_verified',
      'strict_cell_residual_descent_verified',
      'characteristic_geometry_segregated',
      'fidelity_isolation_verified',
      'canonical_free_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.canonical_free_boundary_verified or self.global_coupling_verified:
      raise ValueError('pressure correction cannot claim global closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('pressure correction must remain promotion-blocked')
    ####
    object.__setattr__(self, 'attempts', attempts)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def selected_attempt(self):
    return (
      None
      if self.selected_attempt_index is None
      else self.attempts[self.selected_attempt_index]
    )
  ####

  @property
  def converged_research_pressure_correction(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus
      .CONVERGED_RESEARCH_PRESSURE_CORRECTION
      and self.source_closure is not None
      and self.source_frontier_step is not None
      and self.base_target is not None
      and self.selected_attempt is not None
      and self.selected_closure is not None
      and self.pressure_trace_consumed
      and self.fresh_global_solve_verified
      and self.pressure_target_consumption_verified
      and self.strict_cell_residual_descent_verified
      and self.characteristic_geometry_segregated
      and self.fidelity_isolation_verified
      and self.selected_closure.physical_closure_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_OPERATOR_ID,
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL,
      'status': self.status.value,
      'converged_research_pressure_correction': self.converged_research_pressure_correction,
      'source_closure_fingerprint': (
        None
        if self.source_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(
          self.source_closure
        )
      ),
      'source_frontier_fingerprint': (
        None
        if self.source_frontier_step is None
        else _frontier_fingerprint(self.source_frontier_step)
      ),
      'base_target': None if self.base_target is None else self.base_target.as_report(),
      'attempt_count': len(self.attempts),
      'selected_attempt_index': self.selected_attempt_index,
      'selected_pressure_fraction': (
        None
        if self.selected_attempt is None
        else self.selected_attempt.pressure_fraction
      ),
      'baseline_max_cell_euler_residual': self.baseline_max_cell_euler_residual,
      'selected_max_cell_euler_residual': self.selected_max_cell_euler_residual,
      'pressure_trace_consumed': self.pressure_trace_consumed,
      'fresh_global_solve_verified': self.fresh_global_solve_verified,
      'pressure_target_consumption_verified': self.pressure_target_consumption_verified,
      'strict_cell_residual_descent_verified': self.strict_cell_residual_descent_verified,
      'characteristic_geometry_segregated': self.characteristic_geometry_segregated,
      'fidelity_isolation_verified': self.fidelity_isolation_verified,
      'canonical_free_boundary_verified': False,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'attempts': tuple(attempt.as_report() for attempt in self.attempts),
      'selected_closure': (
        None
        if self.selected_closure is None
        else self.selected_closure.as_report()
      ),
      'source_frontier_step': (
        None
        if self.source_frontier_step is None
        else self.source_frontier_step.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'claim_status': (
        'research-only pressure consumption from a local characteristic '
        'free-boundary branch; the characteristic geometry remains segregated '
        'from the outer ambient boundary and canonical, fixed-point, '
        'shock-cell, validation, and production gates remain open'
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult:
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult(
    status=status,
    request=request,
    source_closure=None if request is None else request.source_closure,
    source_frontier_step=(
      None if request is None else request.source_frontier_step
    ),
    message=message,
    **values,
  )
####


def _make_attempt(
  fraction: float,
  overlay: MocPhysicalFieldEulerBoundaryPressureTarget | None,
  candidate: MocReflectedDomainGlobalPhysicalClosureResult | None,
  *,
  source_closure_fingerprint: str,
  source_proposal_fingerprint: str,
  fresh_global_solve_attempted: bool,
  message: str,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt:
  target_consumed = _target_consumed(
    candidate,
    overlay,
    source_closure_fingerprint=source_closure_fingerprint,
    source_proposal_fingerprint=source_proposal_fingerprint,
  ) if overlay is not None else False
  geometry_consumed = bool(
    candidate is not None and candidate.source_pressure_target_geometry_consumed
  )
  physical = bool(candidate is not None and candidate.physical_closure_verified)
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt(
    pressure_fraction=fraction,
    pressure_overlay=overlay,
    candidate_closure=candidate,
    fresh_global_solve_attempted=fresh_global_solve_attempted,
    pressure_target_consumed=target_consumed,
    target_geometry_consumed=geometry_consumed,
    physical_closure_verified=physical,
    maximum_cell_euler_residual=_cell_residual(candidate),
    message=message,
  )
####


def run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction(
  request: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult:
  """Consume local characteristic pressure through fresh global closures."""

  status_type = MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionStatus
  if not isinstance(
    request,
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionRequest,
  ):
    return _failure(
      status_type.INVALID_INPUT,
      'request must be a typed characteristic pressure-correction request',
    )
  ####
  source_closure = request.source_closure
  frontier_step = request.source_frontier_step
  if not source_closure.physical_closure_verified:
    return _failure(
      status_type.SOURCE_CLOSURE_FAILURE,
      'pressure correction requires a locally physically verified source closure',
      request=request,
    )
  ####
  if not frontier_step.locally_verified:
    return _failure(
      status_type.FRONTIER_FAILURE,
      'pressure correction requires an independently audited local frontier step',
      request=request,
    )
  ####
  source_closure_fingerprint = request.source_closure_fingerprint
  source_proposal_fingerprint = request.source_frontier_fingerprint
  try:
    pressure_frame = _local_pressure_frame(frontier_step)
    template_base = _build_source_band_base_target(
      source_closure,
      source_id=(
        f'{MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL}'
        f':base-frame:{source_closure_fingerprint}'
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      status_type.TARGET_COVERAGE_FAILURE,
      f'pressure correction could not build a bounded target frame: {error}',
      request=request,
    )
  ####
  attempts: list[MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt] = []
  baseline_residual: float | None = None
  baseline_ok = False
  selected_index: int | None = None
  selected_residual: float | None = None
  selected_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  for fraction in request.fractions:
    overlay: MocPhysicalFieldEulerBoundaryPressureTarget | None = None
    candidate: MocReflectedDomainGlobalPhysicalClosureResult | None = None
    try:
      source_id = (
        f'{MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_MODEL}'
        f':{frontier_step.case_id}:fraction:{_fraction_token(fraction)}'
      )
      attempt_base = _build_source_band_base_target(
        source_closure,
        source_id=f'global-physical-closure:source-band-base:{source_id}',
      )
      overlay = _build_pressure_overlay(
        source_closure,
        frontier_step,
        attempt_base,
        pressure_frame,
        fraction,
        source_closure_fingerprint=source_closure_fingerprint,
        source_proposal_fingerprint=source_proposal_fingerprint,
      )
      seam_jumps: list[float] = []
      for seam_x in (overlay.x_stations_m[0], overlay.x_stations_m[-1]):
        base_pressure = template_base.pressure_at_x(
          seam_x,
          position_tolerance_m=1.0e-8,
        )
        overlay_pressure = overlay.pressure_at_x(
          seam_x,
          position_tolerance_m=1.0e-8,
        )
        if base_pressure is None or overlay_pressure is None:
          raise ValueError('pressure overlay seam left the base target frame')
        ####
        seam_jumps.append(
          abs(overlay_pressure - base_pressure)
          / max(overlay_pressure, base_pressure)
        )
      ####
      if max(seam_jumps, default=0.0) > request.seam_pressure_tolerance_fraction:
        raise ValueError(
          'pressure overlay seam exceeded the declared tolerance: '
          f'{max(seam_jumps, default=0.0)} > '
          f'{request.seam_pressure_tolerance_fraction}'
        )
      ####
      candidate = _fresh_global_resolve(source_closure, overlay, request)
      message = candidate.message
      fresh_attempted = True
    except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
      message = str(error)
      fresh_attempted = candidate is not None
    ####
    attempt = _make_attempt(
      fraction,
      overlay,
      candidate,
      source_closure_fingerprint=source_closure_fingerprint,
      source_proposal_fingerprint=source_proposal_fingerprint,
      fresh_global_solve_attempted=fresh_attempted,
      message=message,
    )
    if fraction == 0.0:
      baseline_residual = attempt.maximum_cell_euler_residual
      baseline_ok = bool(
        attempt.fresh_global_solve_attempted
        and attempt.pressure_target_consumed
        and not attempt.target_geometry_consumed
        and attempt.physical_closure_verified
        and baseline_residual is not None
      )
      attempt = replace(
        attempt,
        accepted=baseline_ok,
      )
    elif baseline_ok:
      residual = attempt.maximum_cell_euler_residual
      improvement = bool(
        residual is not None
        and baseline_residual is not None
        and residual < baseline_residual
        - 1.0e-12 * max(1.0, abs(baseline_residual))
      )
      accepted = bool(
        attempt.fresh_global_solve_attempted
        and attempt.pressure_target_consumed
        and not attempt.target_geometry_consumed
        and attempt.physical_closure_verified
        and improvement
      )
      attempt = replace(
        attempt,
        strict_improvement_over_baseline=improvement,
        accepted=accepted,
      )
      if accepted and (
        selected_residual is None
        or residual is not None and residual < selected_residual
      ):
        selected_index = len(attempts)
        selected_residual = residual
        selected_closure = candidate
      ####
    ####
    attempts.append(attempt)
    if fraction == 0.0 and not baseline_ok:
      break
    ####
  ####
  retained_attempts = tuple(attempts)
  if not baseline_ok:
    geometry_segregated = all(
      not attempt.target_geometry_consumed for attempt in retained_attempts
    )
    return _failure(
      status_type.BASELINE_FAILURE,
      'fresh pressure-correction baseline did not pass local physical and '
      'pressure-target consumption gates',
      request=request,
      base_target=template_base,
      attempts=retained_attempts,
      baseline_max_cell_euler_residual=baseline_residual,
      characteristic_geometry_segregated=geometry_segregated,
      fidelity_isolation_verified=geometry_segregated,
    )
  ####
  if selected_index is None or selected_closure is None or selected_residual is None:
    geometry_segregated = all(
      not attempt.target_geometry_consumed for attempt in retained_attempts
    )
    return _failure(
      status_type.NO_ADMISSIBLE_TRIAL,
      'baseline closed locally, but no positive characteristic pressure trial '
      'produced strict fresh-cell residual descent',
      request=request,
      base_target=template_base,
      attempts=retained_attempts,
      baseline_max_cell_euler_residual=baseline_residual,
      characteristic_geometry_segregated=geometry_segregated,
      fidelity_isolation_verified=geometry_segregated,
    )
  ####
  selected_attempt = retained_attempts[selected_index]
  geometry_segregated = bool(
    not selected_attempt.target_geometry_consumed
    and all(not attempt.target_geometry_consumed for attempt in retained_attempts)
  )
  pressure_consumed = bool(selected_attempt.pressure_target_consumed)
  fresh_verified = bool(
    selected_attempt.fresh_global_solve_attempted
    and selected_closure is not source_closure
    and selected_closure.source_band is not None
    and selected_closure.source_band is not source_closure.source_band
  )
  fidelity_isolation = bool(
    geometry_segregated
    and selected_closure.chain_promotion_blocked
    and not selected_closure.production_claim_allowed
    and not selected_closure.canonical_free_boundary_verified
    and not selected_closure.canonical_euler_verified
  )
  return _failure(
    status_type.CONVERGED_RESEARCH_PRESSURE_CORRECTION,
    'bounded characteristic free-boundary pressure trace was consumed by '
    'fresh global Euler closures; the best positive trial strictly reduced '
    'the measured local cell residual while characteristic geometry remained '
    'segregated from the outer ambient boundary',
    request=request,
    base_target=template_base,
    attempts=retained_attempts,
    selected_attempt_index=selected_index,
    selected_closure=selected_closure,
    baseline_max_cell_euler_residual=baseline_residual,
    selected_max_cell_euler_residual=selected_residual,
    pressure_trace_consumed=pressure_consumed,
    fresh_global_solve_verified=fresh_verified,
    pressure_target_consumption_verified=pressure_consumed,
    strict_cell_residual_descent_verified=bool(
      selected_attempt.strict_improvement_over_baseline
    ),
    characteristic_geometry_segregated=geometry_segregated,
    fidelity_isolation_verified=fidelity_isolation,
  )
####


def _attempt_fingerprint(
  attempt: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAttempt,
) -> str:
  payload = {
    'pressure_fraction': attempt.pressure_fraction,
    'pressure_overlay': (
      None if attempt.pressure_overlay is None else attempt.pressure_overlay.as_report()
    ),
    'candidate_closure_fingerprint': (
      None
      if attempt.candidate_closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        attempt.candidate_closure
      )
    ),
    'fresh_global_solve_attempted': attempt.fresh_global_solve_attempted,
    'pressure_target_consumed': attempt.pressure_target_consumed,
    'target_geometry_consumed': attempt.target_geometry_consumed,
    'physical_closure_verified': attempt.physical_closure_verified,
    'maximum_cell_euler_residual': attempt.maximum_cell_euler_residual,
    'strict_improvement_over_baseline': attempt.strict_improvement_over_baseline,
    'accepted': attempt.accepted,
    'message': attempt.message,
  }
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()
####


def _result_identity(
  first: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
  second: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
) -> bool:
  return bool(
    first.status is second.status
    and first.selected_attempt_index == second.selected_attempt_index
    and (
      None if first.selected_attempt is None else first.selected_attempt.pressure_fraction
    ) == (
      None if second.selected_attempt is None else second.selected_attempt.pressure_fraction
    )
    and first.baseline_max_cell_euler_residual == second.baseline_max_cell_euler_residual
    and first.selected_max_cell_euler_residual == second.selected_max_cell_euler_residual
    and first.pressure_trace_consumed == second.pressure_trace_consumed
    and first.fresh_global_solve_verified == second.fresh_global_solve_verified
    and first.pressure_target_consumption_verified == second.pressure_target_consumption_verified
    and first.strict_cell_residual_descent_verified == second.strict_cell_residual_descent_verified
    and first.characteristic_geometry_segregated == second.characteristic_geometry_segregated
    and first.fidelity_isolation_verified == second.fidelity_isolation_verified
    and tuple(_attempt_fingerprint(item) for item in first.attempts)
    == tuple(_attempt_fingerprint(item) for item in second.attempts)
    and (
      None
      if first.selected_closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        first.selected_closure
      )
    ) == (
      None
      if second.selected_closure is None
      else moc_reflected_domain_global_physical_closure_fingerprint(
        second.selected_closure
      )
    )
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit:
  """Independent replay evidence for the pressure-only global correction."""

  status: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult | None
  replay: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult | None
  request_replayed: bool = False
  source_lineage_replayed: bool = False
  frontier_lineage_replayed: bool = False
  base_target_replayed: bool = False
  trial_ladder_replayed: bool = False
  selected_closure_replayed: bool = False
  independent_pressure_correction_verified: bool = False
  characteristic_geometry_segregated: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAuditStatus,
    ):
      raise TypeError('status must be a typed pressure-correction audit status')
    ####
    for name in ('candidate', 'replay'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
      ):
        raise TypeError(f'{name} must be a typed pressure-correction result')
      ####
    ####
    for name in (
      'request_replayed',
      'source_lineage_replayed',
      'frontier_lineage_replayed',
      'base_target_replayed',
      'trial_ladder_replayed',
      'selected_closure_replayed',
      'independent_pressure_correction_verified',
      'characteristic_geometry_segregated',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.global_coupling_verified or not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('pressure-correction audit must remain promotion-blocked')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAuditStatus
      .VERIFIED_RESEARCH_PRESSURE_CORRECTION
      and self.independent_pressure_correction_verified
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_CHARACTERISTIC_FREE_BOUNDARY_PRESSURE_CORRECTION_OPERATOR_ID,
      'audit_status': self.status.value,
      'converged': self.converged,
      'request_replayed': self.request_replayed,
      'source_lineage_replayed': self.source_lineage_replayed,
      'frontier_lineage_replayed': self.frontier_lineage_replayed,
      'base_target_replayed': self.base_target_replayed,
      'trial_ladder_replayed': self.trial_ladder_replayed,
      'selected_closure_replayed': self.selected_closure_replayed,
      'independent_pressure_correction_verified': self.independent_pressure_correction_verified,
      'characteristic_geometry_segregated': self.characteristic_geometry_segregated,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': None if self.candidate is None else self.candidate.as_report(),
      'replay': None if self.replay is None else self.replay.as_report(),
      'message': self.message,
    }
  ####
####


def audit_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction(
  result: MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
) -> MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit:
  """Replay one exact pressure correction and compare every retained trial."""

  audit_status = MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAuditStatus
  if not isinstance(
    result,
    MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionResult,
  ):
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      replay=None,
      message='result must be a typed pressure-correction result',
    )
  ####
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message='pressure-correction replay requires the retained request',
    )
  ####
  try:
    replay = run_reflected_domain_global_mixed_regime_characteristic_free_boundary_pressure_correction(
      result.request
    )
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      replay=None,
      message=f'pressure-correction replay raised: {error}',
    )
  ####
  request_replayed = replay.request is result.request
  source_lineage_replayed = bool(
    replay.source_closure is result.source_closure
    and replay.source_closure is result.request.source_closure
  )
  frontier_lineage_replayed = bool(
    replay.source_frontier_step is result.source_frontier_step
    and replay.source_frontier_step is result.request.source_frontier_step
    and replay.source_frontier_step is not None
    and _frontier_fingerprint(replay.source_frontier_step)
    == _frontier_fingerprint(result.source_frontier_step)
  )
  base_target_replayed = bool(
    replay.base_target is not None
    and result.base_target is not None
    and replay.base_target.as_report() == result.base_target.as_report()
  )
  trial_ladder_replayed = bool(
    len(replay.attempts) == len(result.attempts)
    and tuple(_attempt_fingerprint(item) for item in replay.attempts)
    == tuple(_attempt_fingerprint(item) for item in result.attempts)
  )
  selected_closure_replayed = bool(
    (
      replay.selected_closure is None
      if result.selected_closure is None
      else replay.selected_closure is not None
      and moc_reflected_domain_global_physical_closure_fingerprint(
        replay.selected_closure
      )
      == moc_reflected_domain_global_physical_closure_fingerprint(
        result.selected_closure
      )
    )
  )
  independent = bool(
    request_replayed
    and source_lineage_replayed
    and frontier_lineage_replayed
    and base_target_replayed
    and trial_ladder_replayed
    and selected_closure_replayed
    and _result_identity(replay, result)
    and replay.characteristic_geometry_segregated
    and replay.chain_promotion_blocked
    and not replay.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeCharacteristicFreeBoundaryPressureCorrectionAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_PRESSURE_CORRECTION
      if independent
      else audit_status.TRIAL_LADDER_FAILURE
    ),
    candidate=result,
    replay=replay,
    request_replayed=request_replayed,
    source_lineage_replayed=source_lineage_replayed,
    frontier_lineage_replayed=frontier_lineage_replayed,
    base_target_replayed=base_target_replayed,
    trial_ladder_replayed=trial_ladder_replayed,
    selected_closure_replayed=selected_closure_replayed,
    independent_pressure_correction_verified=independent,
    characteristic_geometry_segregated=replay.characteristic_geometry_segregated,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact pressure overlay ladder, fresh '
      'global candidates, selected residual descent, and segregated geometry '
      'claim ceiling'
      if independent
      else 'independent replay did not reproduce the exact pressure correction '
      'ladder or its claim ceiling'
    ),
  )
####
