"""Solver-backed shock and post-shock continuation from a caustic family band.

The caustic restart produces an open, domain-bounded characteristic band.  It
is useful upstream data for a shock marcher, but its ambient edge is not the
upstream side of a shock cell.  This module starts from the explicit input
edge of that band, marches an attached shock until the axis requires a typed
normal-shock terminal, and assembles the available supersonic post-shock
layers as an open zone.

The final normal-shock point is deliberately kept outside the
``CharacteristicState`` network.  Consequently this result is a solver-backed
terminal handoff, not a resolved physical first cell and not a chain-cell
promotion result.  A future mixed-regime closure can consume the terminal and
the open post-shock zone without changing the lower-fidelity providers.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import cast

from exhaust_plume.models.moc.caustic_restart import MocCausticFamilyBandResult
from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainCell,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_with_invariant_boundary,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeBoundaryResult,
  MocMixedRegimeFieldSample,
  validate_mixed_regime_boundary as validate_scalar_mixed_regime_boundary,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockCharacteristicZoneResult,
  MocPostShockChainCellSolve,
  MocPostShockContinuationResult,
  MocPostShockFirstLayerResult,
  MocShockBoundaryFitResult,
  assemble_post_shock_characteristic_zone,
  assemble_post_shock_first_layer,
  continue_post_shock_characteristics_to_centerline_open,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocCausticFamilyBandShockStatus',
  'MocCausticFamilyBandShockResult',
  'MocCausticFamilyBandInvariantShockStatus',
  'MocCausticFamilyBandInvariantShockResult',
  'solve_marched_attached_shock_from_caustic_family_band',
  'solve_marched_attached_shock_from_caustic_family_band_with_invariant_boundary',
  'solve_marched_attached_shock_chain_cell_from_caustic_family_band',
  'solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination',
  'solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination',
)


class MocCausticFamilyBandShockStatus(str, Enum):
  """Structured outcomes for the band-to-terminal solver seam."""

  CONVERGED_OPEN_TERMINAL_FIELD = (
    'converged_open_caustic_band_terminal_field'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_DOMAIN_FAILURE = 'caustic_band_upstream_domain_failure'
  SHOCK_FAILURE = 'caustic_band_shock_failure'
  SHOCK_FIT_FAILURE = 'caustic_band_shock_fit_failure'
  CONTINUATION_FAILURE = 'caustic_band_post_shock_continuation_failure'
  FIRST_LAYER_FAILURE = 'caustic_band_post_shock_first_layer_failure'
  ZONE_FAILURE = 'caustic_band_post_shock_zone_failure'


class MocCausticFamilyBandInvariantShockStatus(str, Enum):
  """Outcome for an invariant-conditioned shock march from a family band."""

  CONVERGED_FIELD = 'converged_invariant_caustic_band_field'
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_DOMAIN_FAILURE = 'invariant_caustic_band_upstream_domain_failure'
  INVARIANT_FAILURE = 'invariant_caustic_band_invariant_failure'
  SHOCK_FAILURE = 'invariant_caustic_band_shock_failure'


@dataclass(frozen=True, slots=True)
class MocCausticFamilyBandShockResult:
  """A typed terminal and open downstream zone grown from a family band.

  ``converged`` means that the upstream band was sampled without
  extrapolation, the attached shock reached the axis terminal, the
  supersonic shock samples were refit, and the available downstream
  characteristic zone passed its local mesh gates.  It does not mean that
  the normal-shock subsonic side or the complete first-cell perimeter has
  closed.
  """

  status: MocCausticFamilyBandShockStatus
  band: MocCausticFamilyBandResult | None
  start_point_m: tuple[float, float] | None
  shock: MocFreeBoundaryShockResult | None
  shock_fit: MocShockBoundaryFitResult | None
  continuation: MocPostShockContinuationResult | None
  first_layer: MocPostShockFirstLayerResult | None
  zone: MocPostShockCharacteristicZoneResult | None
  message: str = ''
  incoming_handoff_states: tuple[CharacteristicState, ...] = ()
  incoming_handoff_total_pressure_Pa: tuple[float, ...] = ()

  def __post_init__(self) -> None:
    if len(self.incoming_handoff_states) != len(
      self.incoming_handoff_total_pressure_Pa
    ):
      raise ValueError(
        'incoming handoff states and total-pressure samples must have equal lengths'
      )
    if any(
      not isinstance(state, CharacteristicState)
      for state in self.incoming_handoff_states
    ):
      raise TypeError('incoming handoff states must be CharacteristicState values')
    if any(
      not isfinite(float(value)) or value <= 0.0
      for value in self.incoming_handoff_total_pressure_Pa
    ):
      raise ValueError('incoming handoff total pressures must be finite and positive')

  @property
  def converged(self) -> bool:
    return self.status is MocCausticFamilyBandShockStatus.CONVERGED_OPEN_TERMINAL_FIELD

  @property
  def physical_closure_verified(self) -> bool:
    """The mixed-regime side and full first-cell perimeter remain open."""

    return False

  @property
  def chain_promotion_blocked(self) -> bool:
    return True

  @property
  def terminal_normal_shock(self) -> MocNormalShockTerminalResult | None:
    if self.shock is None:
      return None
    return self.shock.normal_shock_terminal

  @property
  def physical_terminal_verified(self) -> bool:
    terminal = self.terminal_normal_shock
    return terminal is not None and terminal.converged and terminal.subsonic

  @property
  def post_shock_zone_converged(self) -> bool:
    return self.zone is not None and self.zone.converged

  def validate_mixed_regime_boundary(
    self,
    subsonic_samples: Sequence[MocMixedRegimeFieldSample],
    *,
    perimeter_points_m: Sequence[tuple[float, float]] | None = None,
    position_tolerance_m: float = 1.0e-10,
    state_tolerance: float = 1.0e-10,
    pressure_tolerance: float = 1.0e-8,
  ) -> MocMixedRegimeBoundaryResult:
    """Validate a scalar downstream perimeter at the band terminal.

    The band/shock result supplies only the verified supersonic patch and the
    scalar normal-shock terminal.  The downstream perimeter remains caller
    owned.  This method is the explicit handoff into the mixed-regime
    validator; an empty or open input returns a structured failure and never
    gets repaired from the topological open zone.
    """

    patch = () if self.shock_fit is None else self.shock_fit.boundary_states
    return validate_scalar_mixed_regime_boundary(
      cast(MocNormalShockTerminalResult, self.terminal_normal_shock),
      patch,
      supersonic_patch_converged=(
        self.shock_fit is not None
        and self.shock_fit.converged
        and self.post_shock_zone_converged
      ),
      subsonic_samples=subsonic_samples,
      perimeter_points_m=perimeter_points_m,
      position_tolerance_m=position_tolerance_m,
      state_tolerance=state_tolerance,
      pressure_tolerance=pressure_tolerance,
    )
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    """Expose an explicit open stop; never promote the open zone."""

    if not self.converged:
      raise ValueError(
        'a caustic-band chain stop requires a converged open terminal field'
      )
    terminal = self.terminal_normal_shock
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'caustic-band shock and supersonic post-shock zone converged to a '
        'typed normal-shock terminal; mixed-regime closure remains pending'
      ),
      diagnostics={
        'termination_model': 'caustic-band-open-terminal-field',
        'physical_terminal_verified': self.physical_terminal_verified,
        'shock_sample_count': None if self.shock is None else self.shock.sample_count,
        'terminal_shock_point_m': (
          None if terminal is None else terminal.shock_point_m
        ),
        'terminal_downstream_mach': (
          None if terminal is None else terminal.downstream_mach
        ),
        'post_shock_zone_cell_count': (
          None if self.zone is None else self.zone.cell_count
        ),
        'post_shock_zone_topology_forms_closed_zone': (
          None if self.zone is None else self.zone.topology.forms_closed_zone
        ),
      },
    )

  def as_report(self) -> dict[str, object]:
    terminal = self.terminal_normal_shock
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'physical_terminal_verified': self.physical_terminal_verified,
      'start_point_m': self.start_point_m,
      'shock': None if self.shock is None else self.shock.as_report(),
      'shock_fit': None if self.shock_fit is None else {
        'status': self.shock_fit.status.value,
        'converged': self.shock_fit.converged,
        'sample_count': len(self.shock_fit.boundary_states),
        'maximum_shock_angle_residual_rad': (
          self.shock_fit.maximum_shock_angle_residual_rad
        ),
      },
      'continuation': None if self.continuation is None else {
        'status': self.continuation.status.value,
        'converged': self.continuation.converged,
        'segment_count': len(self.continuation.segments),
        'centerline_point_count': len(self.continuation.centerline_states),
        'maximum_geometry_residual_m': self.continuation.maximum_geometry_residual_m,
        'maximum_absolute_invariant_residual': (
          self.continuation.maximum_absolute_invariant_residual
        ),
      },
      'first_layer': None if self.first_layer is None else {
        'status': self.first_layer.status.value,
        'converged': self.first_layer.converged,
        'crossing_count': len(self.first_layer.crossings),
        'minimum_forward_margin_m': self.first_layer.minimum_forward_margin_m,
        'maximum_geometry_residual_m': self.first_layer.maximum_geometry_residual_m,
        'maximum_absolute_invariant_residual': (
          self.first_layer.maximum_absolute_invariant_residual
        ),
      },
      'zone': None if self.zone is None else {
        'status': self.zone.status.value,
        'converged': self.zone.converged,
        'characteristic_count': self.zone.characteristic_count,
        'node_count': self.zone.node_count,
        'cell_count': self.zone.cell_count,
        'topology_connected': self.zone.topology.connected,
        'topology_forms_closed_zone': self.zone.topology.forms_closed_zone,
        'topology_nonmanifold_edge_count': self.zone.topology.nonmanifold_edge_count,
        'physical_closure_status': self.zone.physical_closure_status,
        'shock_closure_status': self.zone.shock_closure_status,
        'maximum_geometry_residual_m': self.zone.maximum_geometry_residual_m,
        'maximum_absolute_invariant_residual': (
          self.zone.maximum_absolute_invariant_residual
        ),
        'state_sampling_available': self.zone.state_sampling_available,
        'shock_boundary_sample_count': len(self.zone.boundary_states),
        'axis_boundary_sample_count': len(self.zone.axis_boundary_states),
      },
      'incoming_handoff_sample_count': len(self.incoming_handoff_states),
      'incoming_handoff_total_pressure_range_Pa': (
        None
        if not self.incoming_handoff_total_pressure_Pa
        else (
          min(self.incoming_handoff_total_pressure_Pa),
          max(self.incoming_handoff_total_pressure_Pa),
        )
      ),
      'terminal_normal_shock': None if terminal is None else terminal.as_report(),
      'chain_termination_decision': (
        None
        if not self.converged
        else self.as_chain_termination_decision().as_report()
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocCausticFamilyBandInvariantShockResult:
  """An invariant-conditioned shock attempt using a bounded family band.

  The invariant law is an explicit research boundary condition.  A converged
  result contains a solver-generated shock and downstream characteristic
  field, but it is not a universal caustic closure and remains below the
  production claim ceiling in the planner.
  """

  status: MocCausticFamilyBandInvariantShockStatus
  band: MocCausticFamilyBandResult | None
  start_point_m: tuple[float, float] | None
  invariant_family: CharacteristicFamily | None
  shock: MocFreeBoundaryShockResult | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocCausticFamilyBandInvariantShockStatus.CONVERGED_FIELD

  @property
  def first_missing_sample_index(self) -> int | None:
    if self.shock is None or self.status is not MocCausticFamilyBandInvariantShockStatus.UPSTREAM_DOMAIN_FAILURE:
      return None
    return self.shock.sample_count

  @property
  def shock_curve_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock is not None
      and self.shock.shock_fit is not None
      and self.shock.shock_fit.converged
    )

  @property
  def upstream_coupling_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock is not None
      and self.shock.field is not None
      and self.shock.field.upstream_shock_coupling_verified
    )

  @property
  def physical_closure_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock is not None
      and self.shock.field is not None
      and self.shock.field.physical_closure_verified
    )

  @property
  def chain_promotion_blocked(self) -> bool:
    return not self.physical_closure_verified

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'research_boundary_condition': 'explicit-downstream-characteristic-invariant',
      'shock_curve_verified': self.shock_curve_verified,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'band_kind': (
        None
        if self.band is None
        else 'centerline-ambient-two-triangle-characteristic-band'
      ),
      'start_point_m': self.start_point_m,
      'invariant_family': (
        None if self.invariant_family is None else self.invariant_family.value
      ),
      'first_missing_sample_index': self.first_missing_sample_index,
      'shock': None if self.shock is None else self.shock.as_report(),
      'message': self.message,
    }


def _failure(
  status: MocCausticFamilyBandShockStatus,
  *,
  band: MocCausticFamilyBandResult | None,
  start_point_m: tuple[float, float] | None,
  shock: MocFreeBoundaryShockResult | None = None,
  shock_fit: MocShockBoundaryFitResult | None = None,
  continuation: MocPostShockContinuationResult | None = None,
  first_layer: MocPostShockFirstLayerResult | None = None,
  zone: MocPostShockCharacteristicZoneResult | None = None,
  message: str,
) -> MocCausticFamilyBandShockResult:
  return MocCausticFamilyBandShockResult(
    status=status,
    band=band,
    start_point_m=start_point_m,
    shock=shock,
    shock_fit=shock_fit,
    continuation=continuation,
    first_layer=first_layer,
    zone=zone,
    message=message,
  )


def solve_marched_attached_shock_from_caustic_family_band(
  band: MocCausticFamilyBandResult,
  start_point_m: tuple[float, float],
  *,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_rad: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
) -> MocCausticFamilyBandShockResult:
  """March a shock from a band input edge to a typed axis terminal.

  The start point must be inside or on the explicit input domain of ``band``;
  its state and pressure are sampled through the band callbacks.  A zero
  centerline flow angle is required because this routine's terminal contract
  is the normal-shock seam, not a prescribed non-symmetric downstream turn.
  ``shock_angle_tolerance_rad`` defaults to a coarse research-mesh tolerance
  because the band and shock are intentionally sampled at different
  resolutions; refinement evidence must report the residual rather than
  silently tightening it.

  When ``incoming_handoff`` is supplied it is carried into the generated
  post-shock field as provenance.  It is not used as shock geometry and does
  not change the open mixed-regime closure status of this result.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=None,
      start_point_m=None,
      message='band must be a MocCausticFamilyBandResult',
    )
  if not band.converged:
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=band,
      start_point_m=None,
      message=f'caustic family band is not converged: {band.message}',
    )
  try:
    if len(start_point_m) != 2:
      raise ValueError
    start = (float(start_point_m[0]), float(start_point_m[1]))
    target_y = float(target_centerline_y_m)
    target_angle = float(downstream_flow_angle_rad)
  except (IndexError, TypeError, ValueError):
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=band,
      start_point_m=None,
      message='start point and downstream terminal coordinates must be numeric',
    )
  try:
    valid = all(isfinite(value) for value in (*start, target_y, target_angle))
    tolerance_values = (
      position_tolerance_m,
      invariant_tolerance,
      shock_angle_tolerance_rad,
    )
    valid = valid and all(isfinite(float(value)) and float(value) > 0.0 for value in tolerance_values)
  except (TypeError, ValueError):
    valid = False
  if not valid:
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=band,
      start_point_m=start,
      message='band shock tolerances and coordinates must be finite and positive',
    )
  if target_y >= start[1]:
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=band,
      start_point_m=start,
      message='target centerline ordinate must be below the shock start',
    )
  if abs(target_angle) > invariant_tolerance:
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=band,
      start_point_m=start,
      message=(
        'caustic-band terminal solver requires zero centerline flow angle; '
        'a nonzero turn is a separate open-boundary reference problem'
      ),
    )
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocCausticFamilyBandShockStatus.INVALID_INPUT,
      band=band,
      start_point_m=start,
      message='branch must be a ShockBranch',
    )
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 5:
    raise ValueError('sample_count must be an integer of at least five')
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    raise ValueError('maximum_segment_iterations must be a positive integer')

  try:
    upstream_state = band.state_at(start, position_tolerance_m=position_tolerance_m)
    upstream_pressure = band.static_pressure_at(start, position_tolerance_m=position_tolerance_m)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticFamilyBandShockStatus.UPSTREAM_DOMAIN_FAILURE,
      band=band,
      start_point_m=start,
      message=f'caustic family band sampling raised at shock start: {error}',
    )
  if upstream_state is None or upstream_pressure is None:
    return _failure(
      MocCausticFamilyBandShockStatus.UPSTREAM_DOMAIN_FAILURE,
      band=band,
      start_point_m=start,
      message=(
        'shock start is outside the bounded caustic-family band; no state '
        'or pressure extrapolation is permitted'
      ),
    )

  try:
    shock = solve_marched_attached_shock_field(
      band.state_at,
      band.static_pressure_at,
      start,
      target_centerline_y_m=target_y,
      downstream_flow_angle_rad=target_angle,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      incoming_handoff=incoming_handoff,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticFamilyBandShockStatus.SHOCK_FAILURE,
      band=band,
      start_point_m=start,
      message=f'caustic-band shock march raised: {error}',
    )
  if (
    shock.status is not MocFreeBoundaryShockStatus.SUBSONIC_TERMINAL_REQUIRED
    or not shock.terminal_model_verified
  ):
    return _failure(
      MocCausticFamilyBandShockStatus.SHOCK_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      message=(
        'caustic-band shock did not reach the required typed normal-shock '
        f'terminal: {shock.message}'
      ),
    )
  if len(shock.shock_points_m) < 4:
    return _failure(
      MocCausticFamilyBandShockStatus.SHOCK_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      message='caustic-band terminal requires at least four supersonic shock samples',
    )

  try:
    shock_fit = fit_attached_shock_boundary(
      shock.upstream_states,
      shock.upstream_pressure_Pa,
      shock.shock_points_m,
      shock.downstream_flow_angles_rad,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticFamilyBandShockStatus.SHOCK_FIT_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      message=f'caustic-band shock fit raised: {error}',
    )
  if not shock_fit.converged:
    return _failure(
      MocCausticFamilyBandShockStatus.SHOCK_FIT_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      message=f'caustic-band supersonic shock fit did not converge: {shock_fit.message}',
    )

  try:
    continuation = continue_post_shock_characteristics_to_centerline_open(
      shock_fit.boundary_states,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticFamilyBandShockStatus.CONTINUATION_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      message=f'caustic-band post-shock continuation raised: {error}',
    )
  if not continuation.converged:
    return _failure(
      MocCausticFamilyBandShockStatus.CONTINUATION_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      message=f'caustic-band post-shock continuation did not converge: {continuation.message}',
    )

  try:
    first_layer = assemble_post_shock_first_layer(
      continuation,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticFamilyBandShockStatus.FIRST_LAYER_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      message=f'caustic-band first downstream layer raised: {error}',
    )
  if not first_layer.converged:
    return _failure(
      MocCausticFamilyBandShockStatus.FIRST_LAYER_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      first_layer=first_layer,
      message=f'caustic-band first downstream layer did not converge: {first_layer.message}',
    )

  try:
    zone = assemble_post_shock_characteristic_zone(
      continuation,
      first_layer,
      shock_fit.boundary_states,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocCausticFamilyBandShockStatus.ZONE_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      first_layer=first_layer,
      message=f'caustic-band post-shock zone raised: {error}',
    )
  if not zone.converged:
    return _failure(
      MocCausticFamilyBandShockStatus.ZONE_FAILURE,
      band=band,
      start_point_m=start,
      shock=shock,
      shock_fit=shock_fit,
      continuation=continuation,
      first_layer=first_layer,
      zone=zone,
      message=f'caustic-band post-shock zone did not converge: {zone.message}',
    )

  return MocCausticFamilyBandShockResult(
    status=MocCausticFamilyBandShockStatus.CONVERGED_OPEN_TERMINAL_FIELD,
    band=band,
    start_point_m=start,
    shock=shock,
    shock_fit=shock_fit,
    continuation=continuation,
    first_layer=first_layer,
    zone=zone,
    incoming_handoff_states=(
      ()
      if incoming_handoff is None
      else tuple(sample.state for sample in incoming_handoff)
    ),
    incoming_handoff_total_pressure_Pa=(
      ()
      if incoming_handoff is None
      else tuple(sample.total_pressure_Pa for sample in incoming_handoff)
    ),
    message=(
      'caustic-family band fed a solver-generated attached shock, an open '
      'supersonic post-shock zone, and a typed normal-shock terminal; '
      'mixed-regime closure and chain promotion remain blocked'
    ),
  )


def solve_marched_attached_shock_from_caustic_family_band_with_invariant_boundary(
  band: MocCausticFamilyBandResult,
  start_point_m: tuple[float, float],
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float],
  *,
  target_centerline_y_m: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
) -> MocCausticFamilyBandInvariantShockResult:
  """Attempt a shock march from a bounded family band with an invariant law.

  The family band is sampled only through its bounded state/pressure methods.
  The downstream invariant callback supplies the extra shock-side condition
  needed to determine the local turn.  A complete result is still a
  boundary-conditioned research solution; an upstream-domain miss is kept as
  a precise non-physical failure instead of being repaired with extrapolation.
  """

  def failure(
    status: MocCausticFamilyBandInvariantShockStatus,
    message: str,
    *,
    band_value: MocCausticFamilyBandResult | None = None,
    start_value: tuple[float, float] | None = None,
    family_value: CharacteristicFamily | None = None,
    shock_value: MocFreeBoundaryShockResult | None = None,
  ) -> MocCausticFamilyBandInvariantShockResult:
    return MocCausticFamilyBandInvariantShockResult(
      status=status,
      band=band_value,
      start_point_m=start_value,
      invariant_family=family_value,
      shock=shock_value,
      message=message,
    )

  if not isinstance(band, MocCausticFamilyBandResult):
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'band must be a MocCausticFamilyBandResult',
    )
  if not band.converged:
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      f'caustic family band is not converged: {band.message}',
      band_value=band,
    )
  if not isinstance(downstream_invariant_family, CharacteristicFamily):
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'downstream_invariant_family must be a CharacteristicFamily',
      band_value=band,
    )
  if not callable(downstream_invariant_at):
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'downstream_invariant_at must be callable',
      band_value=band,
      family_value=downstream_invariant_family,
    )
  try:
    if len(start_point_m) != 2:
      raise ValueError
    start = (float(start_point_m[0]), float(start_point_m[1]))
    target_y = float(target_centerline_y_m)
  except (IndexError, TypeError, ValueError):
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'start point and target centerline ordinate must be numeric',
      band_value=band,
      family_value=downstream_invariant_family,
    )
  if not all(isfinite(value) for value in (*start, target_y)):
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'start point and target centerline ordinate must be finite',
      band_value=band,
      start_value=start,
      family_value=downstream_invariant_family,
    )
  if target_y >= start[1]:
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'target centerline ordinate must be below the shock start',
      band_value=band,
      start_value=start,
      family_value=downstream_invariant_family,
    )
  if not isinstance(branch, ShockBranch):
    return failure(
      MocCausticFamilyBandInvariantShockStatus.INVALID_INPUT,
      'branch must be a ShockBranch',
      band_value=band,
      start_value=start,
      family_value=downstream_invariant_family,
    )
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')
  if (
    isinstance(maximum_segment_iterations, bool)
    or not isinstance(maximum_segment_iterations, int)
    or maximum_segment_iterations < 1
  ):
    raise ValueError('maximum_segment_iterations must be a positive integer')
  if (
    isinstance(maximum_invariant_scan_samples, bool)
    or not isinstance(maximum_invariant_scan_samples, int)
    or maximum_invariant_scan_samples < 4
  ):
    raise ValueError('maximum_invariant_scan_samples must be an integer of at least four')
  if (
    isinstance(maximum_invariant_iterations, bool)
    or not isinstance(maximum_invariant_iterations, int)
    or maximum_invariant_iterations < 1
  ):
    raise ValueError('maximum_invariant_iterations must be a positive integer')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('maximum_downstream_angle_rad', maximum_downstream_angle_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  try:
    upstream_state = band.state_at(start, position_tolerance_m=position_tolerance_m)
    upstream_pressure = band.static_pressure_at(
      start,
      position_tolerance_m=position_tolerance_m,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure(
      MocCausticFamilyBandInvariantShockStatus.UPSTREAM_DOMAIN_FAILURE,
      f'caustic family band sampling raised at shock start: {error}',
      band_value=band,
      start_value=start,
      family_value=downstream_invariant_family,
    )
  if upstream_state is None or upstream_pressure is None:
    return failure(
      MocCausticFamilyBandInvariantShockStatus.UPSTREAM_DOMAIN_FAILURE,
      'shock start is outside the bounded caustic-family band; no state or pressure extrapolation is permitted',
      band_value=band,
      start_value=start,
      family_value=downstream_invariant_family,
    )

  try:
    shock = solve_marched_attached_shock_with_invariant_boundary(
      band.state_at,
      band.static_pressure_at,
      start,
      downstream_invariant_family,
      downstream_invariant_at,
      target_centerline_y_m=target_y,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return failure(
      MocCausticFamilyBandInvariantShockStatus.SHOCK_FAILURE,
      f'invariant-conditioned caustic-band shock march raised: {error}',
      band_value=band,
      start_value=start,
      family_value=downstream_invariant_family,
    )

  if shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE:
    status = MocCausticFamilyBandInvariantShockStatus.UPSTREAM_DOMAIN_FAILURE
  elif shock.status is MocFreeBoundaryShockStatus.INVARIANT_BOUNDARY_FAILURE:
    status = MocCausticFamilyBandInvariantShockStatus.INVARIANT_FAILURE
  elif shock.status is MocFreeBoundaryShockStatus.CONVERGED_FIELD:
    status = MocCausticFamilyBandInvariantShockStatus.CONVERGED_FIELD
  else:
    status = MocCausticFamilyBandInvariantShockStatus.SHOCK_FAILURE
  return failure(
    status,
    (
      'invariant-conditioned caustic-band shock march '
      f'{"converged" if status is MocCausticFamilyBandInvariantShockStatus.CONVERGED_FIELD else "stopped"}: '
      f'{shock.message}'
    ),
    band_value=band,
    start_value=start,
    family_value=downstream_invariant_family,
    shock_value=shock,
  )


def _validate_caustic_band_chain_inputs(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  position_tolerance_m: float,
) -> tuple[tuple[MocChainBoundarySample, ...], tuple[float, float], float]:
  """Validate the chain seam before consuming a caustic-band field."""

  if not isinstance(current_cell, MocChainCell):
    raise TypeError('current_cell must be a MocChainCell')
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    raise ValueError('next_cell_index must immediately follow current_cell.cell_index')
  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
  if not band.converged:
    raise ValueError(f'caustic family band is not converged: {band.message}')
  try:
    handoff = tuple(incoming_handoff)
  except TypeError as error:
    raise ValueError(
      'incoming_handoff must be an iterable of MocChainBoundarySample values'
    ) from error
  if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
    raise ValueError('incoming_handoff must contain MocChainBoundarySample values')
  if handoff != current_cell.continuation_boundary:
    raise ValueError('incoming_handoff must exactly match the current cell boundary')
  if len(handoff) < 3:
    raise ValueError('caustic-band continued cells require at least three handoff samples')
  try:
    if len(start_point_m) != 2:
      raise ValueError
    start = (float(start_point_m[0]), float(start_point_m[1]))
    end_x = float(end_x_m)
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('caustic-band continued-cell geometry must be numeric') from error
  if not all(isfinite(value) for value in (*start, end_x)):
    raise ValueError('caustic-band continued-cell geometry must be finite')
  if not isfinite(float(position_tolerance_m)) or position_tolerance_m <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if start[0] <= current_cell.end_x_m + position_tolerance_m:
    raise ValueError(
      'caustic-band shock start point must be downstream of the current cell'
    )
  if end_x <= current_cell.end_x_m:
    raise ValueError(
      'caustic-band continued-cell end_x_m must be downstream of the current cell'
    )
  return handoff, start, end_x


def solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
  """Consume a caustic-family band at a continued-cell chain boundary.

  The band is a bounded upstream field for one solver attempt.  Its current
  result stops at an open mixed-regime boundary, so this adapter returns a
  typed non-physical ``OPEN_PHYSICAL_CLOSURE`` decision after a successful
  shock/field solve.  It never appends the open band or its terminal field as
  a resolved chain cell.  If the band cannot cover the requested shock, the
  first upstream-domain seam is retained as a non-physical stop.
  """

  handoff, start, end_x = _validate_caustic_band_chain_inputs(
    current_cell,
    next_cell_index,
    incoming_handoff,
    band,
    start_point_m=start_point_m,
    end_x_m=end_x_m,
    position_tolerance_m=position_tolerance_m,
  )
  try:
    solved = solve_marched_attached_shock_from_caustic_family_band(
      band,
      start,
      target_centerline_y_m=target_centerline_y_m,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      incoming_handoff=handoff,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'caustic-family band shock solver failed before a continued cell '
        'could be assembled; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'caustic-family-band-solver-error',
        'upstream_field_model': 'bounded-caustic-family-band',
        'next_cell_index': next_cell_index,
        'error': str(error),
      },
    )

  if solved.status is MocCausticFamilyBandShockStatus.UPSTREAM_DOMAIN_FAILURE:
    shock = solved.shock
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=(
        'caustic-family band shock path left its bounded upstream field; '
        'no extrapolation or physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'caustic-family-band-upstream-field-boundary',
        'upstream_field_model': 'bounded-caustic-family-band',
        'next_cell_index': next_cell_index,
        'sampled_count': 0 if shock is None else len(shock.upstream_states),
        'first_missing_sample_index': (
          None if shock is None else len(shock.upstream_states)
        ),
        'shock_status': None if shock is None else shock.status.value,
        'message': solved.message,
      },
    )

  if not solved.converged or solved.shock is None:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'caustic-family band shock path did not produce a complete open '
        'terminal field; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'caustic-family-band-solver-failure',
        'upstream_field_model': 'bounded-caustic-family-band',
        'next_cell_index': next_cell_index,
        'shock_status': None if solved.shock is None else solved.shock.status.value,
        'message': solved.message,
      },
    )

  expected_states = tuple(sample.state for sample in handoff)
  expected_pressures = tuple(sample.total_pressure_Pa for sample in handoff)
  if (
    solved.incoming_handoff_states != expected_states
    or solved.incoming_handoff_total_pressure_Pa != expected_pressures
  ):
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.STATE_NOT_CARRIED,
      message=(
        'caustic-family band shock field did not retain the exact incoming '
        'handoff and fitted upstream shock carry'
      ),
      diagnostics={
        'termination_model': 'caustic-family-band-state-handoff',
        'upstream_field_model': 'bounded-caustic-family-band',
        'next_cell_index': next_cell_index,
        'incoming_handoff_sample_count': len(handoff),
      },
    )

  open_decision = solved.as_chain_termination_decision()
  diagnostics = dict(open_decision.diagnostics)
  diagnostics.update({
    'upstream_field_model': 'bounded-caustic-family-band',
    'incoming_handoff_sample_count': len(handoff),
    'next_cell_index': next_cell_index,
    'post_shock_zone_converged': solved.post_shock_zone_converged,
    'upstream_shock_coupling_verified': True,
    'physical_terminal_verified': solved.physical_terminal_verified,
  })
  return MocChainTerminationDecision(
    physical_termination=False,
    reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
    message=(
      'caustic-family band fed a solver-generated next shock and open '
      'post-shock field; mixed-regime closure remains an explicit fidelity '
      'boundary and the open result was not promoted'
    ),
    diagnostics=diagnostics,
  )


def solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  downstream_invariant_family: CharacteristicFamily,
  downstream_invariant_at: Callable[[int, tuple[float, float]], float],
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
  maximum_invariant_iterations: int = 80,
) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
  """Consume a family band with an explicit invariant-conditioned shock law.

  A complete local shock/field can be returned as a state-carrying chain
  cell, but the planner remains research-only because the invariant law is
  caller supplied.  If the one-sided band cannot cover the marched shock, the
  first missing sample is returned as an upstream-field boundary stop.
  """

  handoff, start, end_x = _validate_caustic_band_chain_inputs(
    current_cell,
    next_cell_index,
    incoming_handoff,
    band,
    start_point_m=start_point_m,
    end_x_m=end_x_m,
    position_tolerance_m=position_tolerance_m,
  )
  try:
    solved = solve_marched_attached_shock_from_caustic_family_band_with_invariant_boundary(
      band,
      start,
      downstream_invariant_family,
      downstream_invariant_at,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
      maximum_invariant_iterations=maximum_invariant_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'invariant-conditioned caustic-band shock solver failed before a '
        'continued cell could be assembled; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'invariant-caustic-band-solver-error',
        'upstream_field_model': 'bounded-caustic-family-band',
        'invariant_family': (
          downstream_invariant_family.value
          if isinstance(downstream_invariant_family, CharacteristicFamily)
          else None
        ),
        'next_cell_index': next_cell_index,
        'error': str(error),
      },
    )

  if solved.status is MocCausticFamilyBandInvariantShockStatus.UPSTREAM_DOMAIN_FAILURE:
    shock = solved.shock
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=(
        'invariant-conditioned shock path left the bounded caustic-family '
        'band; no extrapolation or physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'invariant-caustic-band-upstream-field-boundary',
        'upstream_field_model': 'bounded-caustic-family-band',
        'invariant_family': (
          None
          if solved.invariant_family is None
          else solved.invariant_family.value
        ),
        'next_cell_index': next_cell_index,
        'sampled_count': 0 if shock is None else shock.sample_count,
        'first_missing_sample_index': solved.first_missing_sample_index,
        'last_valid_point_m': None if shock is None else shock.endpoint_m,
        'shock_status': None if shock is None else shock.status.value,
        'message': solved.message,
      },
    )

  if solved.status is MocCausticFamilyBandInvariantShockStatus.INVARIANT_FAILURE:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'the explicit downstream invariant could not be satisfied along the '
        'caustic-band shock path; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'invariant-caustic-band-boundary-failure',
        'upstream_field_model': 'bounded-caustic-family-band',
        'invariant_family': (
          None
          if solved.invariant_family is None
          else solved.invariant_family.value
        ),
        'next_cell_index': next_cell_index,
        'sampled_count': 0 if solved.shock is None else solved.shock.sample_count,
        'shock_status': None if solved.shock is None else solved.shock.status.value,
        'message': solved.message,
      },
    )

  if not solved.converged or solved.shock is None or solved.shock.field is None:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.SOLVER_ERROR,
      message=(
        'invariant-conditioned caustic-band shock path did not produce a '
        'complete closed field; no physical endpoint was inferred'
      ),
      diagnostics={
        'termination_model': 'invariant-caustic-band-solver-failure',
        'upstream_field_model': 'bounded-caustic-family-band',
        'invariant_family': (
          None
          if solved.invariant_family is None
          else solved.invariant_family.value
        ),
        'next_cell_index': next_cell_index,
        'shock_status': None if solved.shock is None else solved.shock.status.value,
        'message': solved.message,
      },
    )

  field = solved.shock.field
  expected_states = tuple(sample.state for sample in handoff)
  expected_pressures = tuple(sample.total_pressure_Pa for sample in handoff)
  if (
    field.incoming_handoff_states != expected_states
    or field.incoming_handoff_total_pressure_Pa != expected_pressures
  ):
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.STATE_NOT_CARRIED,
      message=(
        'invariant-conditioned caustic-band field did not retain the exact '
        'incoming handoff'
      ),
      diagnostics={
        'termination_model': 'invariant-caustic-band-state-handoff',
        'upstream_field_model': 'bounded-caustic-family-band',
        'next_cell_index': next_cell_index,
        'incoming_handoff_sample_count': len(handoff),
      },
    )
  if not field.upstream_shock_coupling_verified:
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.STATE_NOT_CARRIED,
      message=(
        'invariant-conditioned caustic-band field did not retain complete '
        'upstream shock state and total-pressure coupling'
      ),
      diagnostics={
        'termination_model': 'invariant-caustic-band-upstream-coupling',
        'upstream_field_model': 'bounded-caustic-family-band',
        'next_cell_index': next_cell_index,
      },
    )
  return MocPostShockChainCellSolve(field=field, end_x_m=end_x)


def solve_marched_attached_shock_chain_cell_from_caustic_family_band(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  band: MocCausticFamilyBandResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  sample_count: int = 9,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 0.1,
  maximum_segment_iterations: int = 24,
) -> MocPostShockChainCellSolve:
  """Strictly require a promotable caustic-band continued-cell solve.

  The current caustic-band result is intentionally open, so this function
  raises with the typed stop's message.  It exists as the strict counterpart
  to the ``or_termination`` adapter for a future mixed-regime-complete band.
  """

  solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination(
    current_cell,
    next_cell_index,
    incoming_handoff,
    band,
    start_point_m=start_point_m,
    end_x_m=end_x_m,
    target_centerline_y_m=target_centerline_y_m,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  if isinstance(solved, MocChainTerminationDecision):
    raise ValueError(solved.message)
  return solved
