"""Staged shock-cell transitions for the isolated planar-MOC lane.

This module composes the research primitives that form one physical
shock-cell transition: ambient-matched shock attachment, the physical
shock/ambient characteristic strip, centerline reflection, and a
domain-bounded next-shock probe.  It intentionally does not manufacture a
closed cell.  A transition can expose a typed next-shock handoff or a
verified normal-shock chain stop, while unresolved downstream closure remains
outside the resolved-cell provider contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Callable, Sequence

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
)
from exhaust_plume.models.moc.coupled import (
  MocAmbientAttachmentResult,
  MocAmbientAttachmentStatus,
  solve_marched_attached_shock_with_ambient_attachment_closure,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.terminal_patch import (
  MocTerminalReflectionPatchResult,
  assemble_terminal_trace_centerline_patch,
)
from exhaust_plume.models.moc.terminal_patch_solver import (
  MocTerminalReflectionPatchShockSolveResult,
  solve_marched_attached_shock_from_terminal_reflection_patch,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocShockCellTransitionStatus',
  'MocShockCellTransitionResult',
  'solve_marched_ambient_attachment_shock_cell_transition',
)


class MocShockCellTransitionStatus(str, Enum):
  """Structured outcomes for a staged shock-cell transition."""

  CONVERGED_OPEN_TRANSITION = 'converged_open_shock_cell_transition'
  PHYSICALLY_TERMINATED = 'physically_terminated_at_normal_shock'
  INVALID_INPUT = 'invalid_input'
  ATTACHMENT_FAILURE = 'attachment_failure'
  REFLECTION_FAILURE = 'centerline_reflection_failure'
  DOWNSTREAM_SHOCK_FAILURE = 'downstream_shock_failure'
####


@dataclass(frozen=True, slots=True)
class MocShockCellTransitionResult:
  """A typed open transition between adjacent planar-MOC shock regions.

  ``CONVERGED_OPEN_TRANSITION`` means that the attachment, physical
  shock/ambient strip, centerline reflection, and next-shock coupling all
  passed their local gates.  ``PHYSICALLY_TERMINATED`` means that the same
  transition reached a verified subsonic normal-shock terminal.  Neither
  result is a closed first-cell or a chain-cell promotion result: the
  downstream law used by the next-shock probe is retained as a named
  centerline-normal-shock reference.
  """

  status: MocShockCellTransitionStatus
  attachment: MocAmbientAttachmentResult
  reflection_patch: MocTerminalReflectionPatchResult | None
  downstream_shock: MocTerminalReflectionPatchShockSolveResult | None
  downstream_condition_status: str
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status in (
      MocShockCellTransitionStatus.CONVERGED_OPEN_TRANSITION,
      MocShockCellTransitionStatus.PHYSICALLY_TERMINATED,
    )
  ####

  @property
  def physical_termination(self) -> bool:
    return self.status is MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The staged transition never promotes an open field into a cell."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def next_shock_handoff(self) -> tuple[MocChainBoundarySample, ...]:
    """Return the reflected outgoing trace for a possible next shock."""

    if self.reflection_patch is None:
      return ()
    return self.reflection_patch.outgoing_trace_samples
  ####

  def as_physical_termination_decision(self) -> MocChainTerminationDecision:
    """Return the verified normal-shock stop when this transition has one."""

    if not self.physical_termination or self.downstream_shock is None:
      raise ValueError(
        'a physical shock-cell termination requires a verified downstream '
        'normal-shock terminal'
      )
    return self.downstream_shock.as_physical_termination_decision()
  ####

  def as_report(self) -> dict[str, object]:
    termination = (
      self.as_physical_termination_decision().as_report()
      if self.physical_termination
      else None
    )
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_termination': self.physical_termination,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'downstream_condition_status': self.downstream_condition_status,
      'next_shock_handoff_kind': 'terminal-characteristic-trace',
      'next_shock_handoff_sample_count': len(self.next_shock_handoff),
      'termination_decision_available': termination is not None,
      'physical_termination_decision': termination,
      'attachment': self.attachment.as_report(),
      'reflection_patch': (
        None
        if self.reflection_patch is None
        else self.reflection_patch.as_report()
      ),
      'downstream_shock': (
        None
        if self.downstream_shock is None
        else self.downstream_shock.as_report()
      ),
      'message': self.message,
    }
####


def _invalid_attachment(message: str) -> MocAmbientAttachmentResult:
  return MocAmbientAttachmentResult(
    status=MocAmbientAttachmentStatus.INVALID_INPUT,
    shock=None,
    ambient_march=None,
    strip=None,
    ambient_pressure_Pa=None,
    outer_downstream_flow_angle_rad=None,
    outer_flow_angle_bracket=None,
    attachment_pressure_residual=None,
    shooting_iterations=0,
    message=message,
  )
####


def solve_marched_ambient_attachment_shock_cell_transition(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  downstream_flow_angle_rad: float = 0.0,
  trace_position_tolerance_m: float = 2.0e-4,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
) -> MocShockCellTransitionResult:
  """Build one staged shock-cell transition and retain its open boundary.

  The outer shock turn is solved against ambient pressure first.  The
  resulting physical shock/ambient strip is reflected to the centerline, and
  its outgoing ``C-`` trace is passed to the domain-bounded next-shock probe.
  A zero downstream angle is a declared normal-shock reference condition; it
  is not silently treated as a universal downstream closure.
  """

  try:
    downstream_angle = float(downstream_flow_angle_rad)
    trace_tolerance = float(trace_position_tolerance_m)
  except (TypeError, ValueError):
    attachment = _invalid_attachment(
      'downstream flow angle and trace tolerance must be numeric',
    )
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.INVALID_INPUT,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=attachment.message,
    )
  if not isfinite(downstream_angle) or not isfinite(trace_tolerance) or trace_tolerance <= 0.0:
    attachment = _invalid_attachment(
      'downstream flow angle must be finite and trace tolerance must be positive',
    )
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.INVALID_INPUT,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=attachment.message,
    )

  try:
    attachment = solve_marched_attached_shock_with_ambient_attachment_closure(
      upstream_state_at,
      upstream_pressure_at,
      start_point_m,
      ambient_pressure_Pa,
      outer_downstream_flow_angle_lower_rad,
      outer_downstream_flow_angle_upper_rad,
      target_centerline_y_m=target_centerline_y_m,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    attachment = _invalid_attachment(f'ambient attachment raised: {error}')
  if not attachment.converged or attachment.strip is None:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.ATTACHMENT_FAILURE,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'ambient attachment did not converge: {attachment.message}',
    )

  try:
    reflection_patch = assemble_terminal_trace_centerline_patch(
      attachment.strip,
      trace_position_tolerance_m=trace_tolerance,
      invariant_tolerance=invariant_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.REFLECTION_FAILURE,
      attachment=attachment,
      reflection_patch=None,
      downstream_shock=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'centerline reflection patch raised: {error}',
    )
  if not reflection_patch.converged or not reflection_patch.outgoing_trace_points_m:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.REFLECTION_FAILURE,
      attachment=attachment,
      reflection_patch=reflection_patch,
      downstream_shock=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'centerline reflection patch did not converge: {reflection_patch.message}',
    )

  try:
    downstream_shock = solve_marched_attached_shock_from_terminal_reflection_patch(
      reflection_patch,
      reflection_patch.outgoing_trace_points_m[0],
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_rad=downstream_angle,
      incoming_handoff=reflection_patch.outgoing_trace_samples,
      sample_count=sample_count,
      position_tolerance_m=trace_tolerance,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocShockCellTransitionResult(
      status=MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE,
      attachment=attachment,
      reflection_patch=reflection_patch,
      downstream_shock=None,
      downstream_condition_status='centerline-normal-shock-reference',
      message=f'downstream shock probe raised: {error}',
    )

  if downstream_shock.physical_terminal_verified:
    status = MocShockCellTransitionStatus.PHYSICALLY_TERMINATED
    message = (
      'ambient attachment, centerline reflection, and next-shock coupling '
      'reached a verified normal-shock terminal; no closed cell was promoted'
    )
  elif downstream_shock.converged:
    status = MocShockCellTransitionStatus.CONVERGED_OPEN_TRANSITION
    message = (
      'ambient attachment, centerline reflection, and next-shock coupling '
      'converged as an open transition; downstream cell closure remains pending'
    )
  else:
    status = MocShockCellTransitionStatus.DOWNSTREAM_SHOCK_FAILURE
    message = f'downstream shock probe did not converge: {downstream_shock.message}'
  return MocShockCellTransitionResult(
    status=status,
    attachment=attachment,
    reflection_patch=reflection_patch,
    downstream_shock=downstream_shock,
    downstream_condition_status='centerline-normal-shock-reference',
    message=message,
  )
####
