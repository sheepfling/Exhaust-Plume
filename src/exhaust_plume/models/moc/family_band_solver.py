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

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import cast

from exhaust_plume.models.moc.caustic_restart import MocCausticFamilyBandResult
from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import MocNormalShockTerminalResult
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeBoundaryResult,
  MocMixedRegimeFieldSample,
  validate_mixed_regime_boundary as validate_scalar_mixed_regime_boundary,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockCharacteristicZoneResult,
  MocPostShockContinuationResult,
  MocPostShockFirstLayerResult,
  MocShockBoundaryFitResult,
  assemble_post_shock_characteristic_zone,
  assemble_post_shock_first_layer,
  continue_post_shock_characteristics_to_centerline_open,
  fit_attached_shock_boundary,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocCausticFamilyBandShockStatus',
  'MocCausticFamilyBandShockResult',
  'solve_marched_attached_shock_from_caustic_family_band',
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
      },
      'terminal_normal_shock': None if terminal is None else terminal.as_report(),
      'chain_termination_decision': (
        None
        if not self.converged
        else self.as_chain_termination_decision().as_report()
      ),
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
    message=(
      'caustic-family band fed a solver-generated attached shock, an open '
      'supersonic post-shock zone, and a typed normal-shock terminal; '
      'mixed-regime closure and chain promotion remain blocked'
    ),
  )
