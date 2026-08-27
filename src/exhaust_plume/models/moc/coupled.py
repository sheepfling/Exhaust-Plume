"""Boundary-conditioned shock closure for the isolated planar MOC lane.

The source-strip and marched-shock primitives deliberately keep their
boundary conditions explicit.  This module adds two narrow research
closures: constant-invariant shooting against a centerline angle and scalar
ambient-pressure shooting against the actual post-shock outer perimeter. The
upstream state and pressure still come from explicit callbacks, and a
candidate is promoted only when the existing attached-shock fit, closed
post-shock characteristic-field gate, and any requested external-boundary
gate all pass.

Neither shooting law is a claim that one invariant or one linear downstream
turn law is the universal physical closure for every plume regime. Callers
must provide a bracket and retain the result's fidelity label when using these
research seams in a planner or continued-cell experiment.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite
from typing import Callable, Sequence

from exhaust_plume.models.moc.ambient_boundary import (
  MocAmbientBoundarySample,
  MocAmbientPressureBoundaryResult,
  validate_post_shock_ambient_boundary,
)
from exhaust_plume.models.moc.ambient_shock_strip import (
  MocAmbientAxisClosureResult,
  MocAmbientShockBoundaryMarchResult,
  MocAmbientShockStripResult,
  march_post_shock_ambient_boundary,
  probe_post_shock_ambient_axis_closure,
  assemble_ambient_shock_characteristic_strip,
)
from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import solve_attached_compression_to_turn
from exhaust_plume.models.moc.free_boundary import (
  MocFreeBoundaryShockResult,
  MocFreeBoundaryShockStatus,
  solve_marched_attached_shock_field,
  solve_marched_attached_shock_from_source_strip,
)
from exhaust_plume.models.moc.post_shock import MocPostShockChainCellSolve
from exhaust_plume.models.moc.physical_cell import (
  MocPhysicalPostShockFieldResult,
  assemble_ambient_boundary_post_shock_field,
)
from exhaust_plume.models.moc.primitives import (
  CharacteristicState,
  prandtl_meyer_angle_rad,
)
from exhaust_plume.models.moc.source_strip import MocSourceCharacteristicStripResult
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocAmbientClosureStatus',
  'MocAmbientClosureResult',
  'solve_marched_attached_shock_with_ambient_pressure_closure',
  'MocAmbientAttachmentStatus',
  'MocAmbientAttachmentResult',
  'solve_marched_attached_shock_with_ambient_attachment_closure',
  'MocAmbientAxisClosureShootStatus',
  'MocAmbientAxisClosureShootTrial',
  'MocAmbientAxisClosureShootResult',
  'solve_marched_attached_shock_with_ambient_axis_closure',
  'MocAmbientPhysicalFieldStatus',
  'MocAmbientPhysicalFieldResult',
  'solve_marched_attached_shock_with_ambient_physical_field',
  'MocInvariantClosureFamily',
  'MocInvariantClosureStatus',
  'MocInvariantClosureResult',
  'solve_marched_attached_shock_with_constant_invariant_closure',
  'solve_marched_attached_shock_chain_cell_with_constant_invariant_closure',
  'solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure',
  'solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination',
)


class MocAmbientClosureStatus(str, Enum):
  """Structured outcomes for the ambient-pressure outer-boundary shoot."""

  CONVERGED_AMBIENT_CLOSED = 'converged_ambient_closed_field'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_BRACKET_FAILURE = 'ambient_pressure_bracket_failure'
  FIELD_FAILURE = 'ambient_closure_field_failure'
  AMBIENT_BOUNDARY_FAILURE = 'ambient_boundary_failure'
  SHOOTING_FAILURE = 'ambient_closure_shooting_failure'
####


class MocAmbientAttachmentStatus(str, Enum):
  """Outcome for an ambient-matched shock attachment and open strip."""

  CONVERGED_OPEN_STRIP = 'converged_ambient_attachment_open_strip'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_BRACKET_FAILURE = 'ambient_attachment_bracket_failure'
  SHOCK_FAILURE = 'ambient_attachment_shock_failure'
  AMBIENT_BOUNDARY_FAILURE = 'ambient_attachment_boundary_failure'
  STRIP_FAILURE = 'ambient_attachment_strip_failure'
  SHOOTING_FAILURE = 'ambient_attachment_shooting_failure'
####


@dataclass(frozen=True, slots=True)
class MocAmbientClosureResult:
  """A scalar ambient-pressure shoot with a strict perimeter acceptance gate.

  The scalar residual is the signed mean pressure residual over the actual
  non-shock/non-centerline perimeter extracted from the post-shock field.  It
  is only a shooting coordinate.  A candidate is promoted to physical closure
  only when every perimeter pressure and tangent residual also passes the
  independent ambient-boundary validator.
  """

  status: MocAmbientClosureStatus
  shock: MocFreeBoundaryShockResult | None
  ambient_boundary: MocAmbientPressureBoundaryResult | None
  ambient_pressure_Pa: float | None
  outer_downstream_flow_angle_rad: float | None
  outer_flow_angle_bracket: tuple[float, float] | None
  closure_residual: float | None
  shooting_iterations: int
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocAmbientClosureStatus.CONVERGED_AMBIENT_CLOSED
  ####


  @property
  def physical_closure_verified(self) -> bool:
    return bool(
      self.converged
      and self.shock is not None
      and self.shock.physical_closure_verified
      and self.ambient_boundary is not None
      and self.ambient_boundary.physical_closure_verified
    )
  ####

  @property
  def upstream_coupling_verified(self) -> bool:
    """Whether the accepted field carries the upstream shock states through."""

    return bool(
      self.physical_closure_verified
      and self.shock is not None
      and self.shock.field is not None
      and self.shock.field.upstream_shock_coupling_verified
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'outer_downstream_flow_angle_rad': self.outer_downstream_flow_angle_rad,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'closure_residual': self.closure_residual,
      'shooting_iterations': self.shooting_iterations,
      'shock': None if self.shock is None else self.shock.as_report(),
      'ambient_boundary': (
        None
        if self.ambient_boundary is None
        else self.ambient_boundary.as_report()
      ),
      'message': self.message,
    }
  ####

  def as_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
    diagnostics: dict[str, object] | None = None,
  ) -> MocChainCell:
    """Promote only a fully ambient-closed field into the MOC chain."""

    if (
      not self.physical_closure_verified
      or self.shock is None
      or self.shock.field is None
    ):
      raise ValueError(
        'only a converged ambient-pressure-closed shock field can become a '
        'continued MOC chain cell'
      )
    assert self.ambient_boundary is not None
    reserved_diagnostics: dict[str, object] = {
      'ambient_pressure_closure_verified': True,
      'ambient_pressure_boundary_sample_count': self.ambient_boundary.sample_count,
      'ambient_pressure_boundary_maximum_absolute_pressure_residual': (
        self.ambient_boundary.maximum_absolute_pressure_residual
      ),
      'ambient_pressure_boundary_maximum_absolute_tangent_residual': (
        self.ambient_boundary.maximum_absolute_tangent_residual
      ),
    }
    if diagnostics is not None:
      reserved = set(reserved_diagnostics) & set(diagnostics)
      if reserved:
        raise ValueError(
          f'diagnostics cannot override reserved ambient-closure keys: {sorted(reserved)!r}'
        )
      reserved_diagnostics.update(diagnostics)
    return self.shock.field.as_chain_cell(
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      cell_index=cell_index,
      diagnostics=reserved_diagnostics,
    )
  ####

  def as_coupled_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
    diagnostics: dict[str, object] | None = None,
  ) -> MocChainCell:
    """Promote only an ambient-closed field with upstream shock coupling."""

    if not self.physical_closure_verified:
      raise ValueError(
        'ambient closure is not physically verified; chain promotion is blocked'
      )
    if not self.upstream_coupling_verified:
      raise ValueError(
        'ambient closure lacks verified upstream shock-state coupling; '
        'strict chain promotion is blocked'
      )
    assert self.shock is not None
    assert self.shock.field is not None
    return self.shock.field.as_coupled_chain_cell(
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      cell_index=cell_index,
      diagnostics=diagnostics,
    )
  ####


@dataclass(frozen=True, slots=True)
class MocAmbientAttachmentResult:
  """An ambient-matched shock plus physical open-boundary strip.

  This result closes only the shock/ambient attachment condition.  The
  downstream terminal trace is retained by ``strip`` and remains open until
  a centerline reflection and next-shock solve close the cell.  It is
  therefore never a chain-cell promotion result.
  """

  status: MocAmbientAttachmentStatus
  shock: MocFreeBoundaryShockResult | None
  ambient_march: MocAmbientShockBoundaryMarchResult | None
  strip: MocAmbientShockStripResult | None
  ambient_pressure_Pa: float | None
  outer_downstream_flow_angle_rad: float | None
  outer_flow_angle_bracket: tuple[float, float] | None
  attachment_pressure_residual: float | None
  shooting_iterations: int
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocAmbientAttachmentStatus.CONVERGED_OPEN_STRIP
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'outer_downstream_flow_angle_rad': self.outer_downstream_flow_angle_rad,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'attachment_pressure_residual': self.attachment_pressure_residual,
      'shooting_iterations': self.shooting_iterations,
      'shock': None if self.shock is None else self.shock.as_report(),
      'ambient_march': (
        None if self.ambient_march is None else self.ambient_march.as_report()
      ),
      'strip': None if self.strip is None else self.strip.as_report(),
      'downstream_condition_status': 'linear-centerline-reference',
      'message': self.message,
    }
  ####


class MocAmbientAxisClosureShootStatus(str, Enum):
  """Structured outcomes for the two-boundary ambient-axis shoot."""

  CONVERGED_AXIS_PRESSURE = 'converged_ambient_axis_pressure'
  INVALID_INPUT = 'invalid_input'
  ATTACHMENT_FAILURE = 'ambient_axis_attachment_failure'
  AXIS_CANDIDATE_FAILURE = 'ambient_axis_candidate_failure'
  BRACKET_FAILURE = 'ambient_axis_bracket_failure'
  SHOOTING_FAILURE = 'ambient_axis_shooting_failure'
####


@dataclass(frozen=True, slots=True)
class MocAmbientAxisClosureShootTrial:
  """One bounded attachment-coordinate trial in the global axis shoot."""

  parameter: float
  start_point_m: tuple[float, float] | None
  attachment: MocAmbientAttachmentResult | None
  axis_closure: MocAmbientAxisClosureResult | None
  residual: float | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isfinite(float(self.parameter)):
      raise ValueError('parameter must be finite')
    if self.start_point_m is not None:
      if len(self.start_point_m) != 2 or not all(
        isfinite(float(value)) for value in self.start_point_m
      ):
        raise ValueError('start_point_m must contain two finite coordinates')
      object.__setattr__(
        self,
        'start_point_m',
        (float(self.start_point_m[0]), float(self.start_point_m[1])),
      )
    if self.attachment is not None and not isinstance(
        self.attachment,
        MocAmbientAttachmentResult,
    ):
      raise TypeError('attachment must be a MocAmbientAttachmentResult or None')
    if self.axis_closure is not None and not isinstance(
        self.axis_closure,
        MocAmbientAxisClosureResult,
    ):
      raise TypeError(
        'axis_closure must be a MocAmbientAxisClosureResult or None'
      )
    if self.residual is not None and not isfinite(float(self.residual)):
      raise ValueError('residual must be finite when supplied')
  ####

  @property
  def converged(self) -> bool:
    """Whether this trial passed the local axis pressure gate."""

    return self.axis_closure is not None and self.axis_closure.converged
  ####

  def as_report(self) -> dict[str, object]:
    """Serialize only bounded trial diagnostics, not an inferred field."""

    return {
      'parameter': self.parameter,
      'start_point_m': self.start_point_m,
      'attachment_status': (
        None if self.attachment is None else self.attachment.status.value
      ),
      'attachment_converged': (
        None if self.attachment is None else self.attachment.converged
      ),
      'outer_downstream_flow_angle_rad': (
        None
        if self.attachment is None
        else self.attachment.outer_downstream_flow_angle_rad
      ),
      'axis_closure': (
        None if self.axis_closure is None else self.axis_closure.as_report()
      ),
      'residual': self.residual,
      'converged': self.converged,
      'message': self.message,
    }
  ####


@dataclass(frozen=True, slots=True)
class MocAmbientAxisClosureShootResult:
  """A bounded global ambient/axis boundary-value shoot.

  The caller supplies a physical attachment coordinate and a mapping from
  that coordinate to a point in the already-solved upstream field.  For each
  coordinate, the local attachment angle is solved against ambient pressure;
  the resulting shock/ambient strip is then continued to a centerline
  candidate and its carried pressure is used as the outer shooting residual.

  A converged result therefore closes only these two scalar boundary gates.
  It does not claim a downstream characteristic field, mixed-regime field, or
  chain cell.  In particular, the attachment-coordinate law remains an
  explicit research callback until independently accepted for a plume model.
  """

  status: MocAmbientAxisClosureShootStatus
  selected_parameter: float | None
  selected_start_point_m: tuple[float, float] | None
  parameter_bracket: tuple[float, float] | None
  outer_flow_angle_bracket: tuple[float, float] | None
  ambient_pressure_Pa: float | None
  attachment: MocAmbientAttachmentResult | None
  axis_closure: MocAmbientAxisClosureResult | None
  closure_residual: float | None
  shooting_iterations: int
  trials: tuple[MocAmbientAxisClosureShootTrial, ...]
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocAmbientAxisClosureShootStatus):
      raise TypeError(
        'status must be a MocAmbientAxisClosureShootStatus'
      )
    for name, value in (
      ('selected_parameter', self.selected_parameter),
      ('ambient_pressure_Pa', self.ambient_pressure_Pa),
      ('closure_residual', self.closure_residual),
    ):
      if value is not None and not isfinite(float(value)):
        raise ValueError(f'{name} must be finite when supplied')
    for name, point in (
      ('selected_start_point_m', self.selected_start_point_m),
    ):
      if point is not None:
        if len(point) != 2 or not all(isfinite(float(value)) for value in point):
          raise ValueError(f'{name} must contain two finite coordinates')
    for name, bracket in (
      ('parameter_bracket', self.parameter_bracket),
      ('outer_flow_angle_bracket', self.outer_flow_angle_bracket),
    ):
      if bracket is not None:
        if len(bracket) != 2 or not all(isfinite(float(value)) for value in bracket):
          raise ValueError(f'{name} must contain two finite values')
    if isinstance(self.shooting_iterations, bool) or (
      not isinstance(self.shooting_iterations, int)
      or self.shooting_iterations < 0
    ):
      raise ValueError('shooting_iterations must be a nonnegative integer')
    if self.attachment is not None and not isinstance(
        self.attachment,
        MocAmbientAttachmentResult,
    ):
      raise TypeError('attachment must be a MocAmbientAttachmentResult or None')
    if self.axis_closure is not None and not isinstance(
        self.axis_closure,
        MocAmbientAxisClosureResult,
    ):
      raise TypeError(
        'axis_closure must be a MocAmbientAxisClosureResult or None'
      )
    if not all(
      isinstance(trial, MocAmbientAxisClosureShootTrial)
      for trial in self.trials
    ):
      raise TypeError(
        'trials must contain only MocAmbientAxisClosureShootTrial values'
      )
  ####

  @property
  def converged(self) -> bool:
    """Whether the bounded axis-pressure shoot found its coordinate root."""

    return self.status is MocAmbientAxisClosureShootStatus.CONVERGED_AXIS_PRESSURE
  ####

  @property
  def axis_pressure_closure_verified(self) -> bool:
    """Whether the selected local axis candidate matches ambient pressure."""

    return bool(self.converged and self.axis_closure is not None and self.axis_closure.converged)
  ####

  @property
  def axis_boundary_verified(self) -> bool:
    """Whether the full appended ambient-to-axis perimeter is accepted."""

    return bool(
      self.converged
      and self.axis_closure is not None
      and self.axis_closure.axis_boundary_verified
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether a full downstream physical first-cell field is present."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Whether the global scalar shoot may enter the continued chain."""

    return True
  ####

  @property
  def trial_count(self) -> int:
    """Number of bounded attachment-coordinate evaluations retained."""

    return len(self.trials)
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'axis_pressure_closure_verified': self.axis_pressure_closure_verified,
      'axis_boundary_verified': self.axis_boundary_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'selected_parameter': self.selected_parameter,
      'selected_start_point_m': self.selected_start_point_m,
      'parameter_bracket': self.parameter_bracket,
      'outer_flow_angle_bracket': self.outer_flow_angle_bracket,
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'attachment': (
        None if self.attachment is None else self.attachment.as_report()
      ),
      'axis_closure': (
        None if self.axis_closure is None else self.axis_closure.as_report()
      ),
      'closure_residual': self.closure_residual,
      'shooting_iterations': self.shooting_iterations,
      'trial_count': self.trial_count,
      'trials': tuple(trial.as_report() for trial in self.trials),
      'message': self.message,
    }
  ####


class MocAmbientPhysicalFieldStatus(str, Enum):
  """Outcome for promoting an ambient/axis shoot into a physical field."""

  CONVERGED_AMBIENT_CLOSED = 'converged_ambient_closed_physical_field'
  INVALID_INPUT = 'invalid_input'
  AXIS_SHOOT_FAILURE = 'ambient_axis_shoot_failure'
  AXIS_BOUNDARY_FAILURE = 'ambient_axis_boundary_failure'
  FIELD_FAILURE = 'ambient_physical_field_failure'
####


@dataclass(frozen=True, slots=True)
class MocAmbientPhysicalFieldResult:
  """A strict bridge from scalar ambient/axis shooting to a physical field.

  The axis shoot is useful for finding a candidate attachment coordinate, but
  its scalar pressure root is not itself a closed MOC cell.  This result keeps
  that distinction explicit: the existing shoot must first pass the complete
  appended ambient-to-axis boundary validator, after which the retained
  boundary states are assembled into the shock/ambient/centerline field.
  """

  status: MocAmbientPhysicalFieldStatus
  axis_closure_shoot: MocAmbientAxisClosureShootResult | None
  field: MocPhysicalPostShockFieldResult | None
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocAmbientPhysicalFieldStatus):
      raise TypeError('status must be a MocAmbientPhysicalFieldStatus')
    if self.axis_closure_shoot is not None and not isinstance(
        self.axis_closure_shoot,
        MocAmbientAxisClosureShootResult,
    ):
      raise TypeError(
        'axis_closure_shoot must be a MocAmbientAxisClosureShootResult or None'
      )
    if self.field is not None and not isinstance(
        self.field,
        MocPhysicalPostShockFieldResult,
    ):
      raise TypeError(
        'field must be a MocPhysicalPostShockFieldResult or None'
      )
  ####

  @property
  def converged(self) -> bool:
    """Whether the physical-field assembly passed its status gate."""

    return bool(
      self.status is MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED
      and self.field is not None
      and self.field.converged
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Whether the immutable physical-field gates all passed."""

    return bool(self.converged and self.field is not None and self.field.physical_closure_verified)
  ####

  @property
  def state_sampling_available(self) -> bool:
    """Whether the accepted field can safely feed a later shock solve."""

    return bool(self.field is not None and self.field.state_sampling_available)
  ####

  @property
  def upstream_coupling_verified(self) -> bool:
    """Whether the accepted field retains the fitted upstream shock data."""

    return bool(self.field is not None and self.field.upstream_shock_coupling_verified)
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    """Whether this result may enter the continued physical shock chain."""

    return not (
      self.physical_closure_verified
      and self.state_sampling_available
      and self.upstream_coupling_verified
    )
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """The bridge remains a research lane until independently validated."""

    return False
  ####

  def as_coupled_chain_cell(
    self,
    *,
    start_x_m: float,
    end_x_m: float,
    cell_index: int = 1,
  ) -> MocChainCell:
    """Promote only a fully sampled, upstream-coupled physical field."""

    if self.chain_promotion_blocked or self.field is None:
      raise ValueError(
        'ambient physical-field result is not eligible for coupled chain promotion'
      )
    return self.field.as_coupled_chain_cell(
      start_x_m=start_x_m,
      end_x_m=end_x_m,
      cell_index=cell_index,
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'state_sampling_available': self.state_sampling_available,
      'upstream_coupling_verified': self.upstream_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'axis_closure_shoot': (
        None
        if self.axis_closure_shoot is None
        else self.axis_closure_shoot.as_report()
      ),
      'field': None if self.field is None else self.field.as_report(),
      'message': self.message,
    }
  ####


def _ambient_attachment_failure(
  status: MocAmbientAttachmentStatus,
  *,
  ambient_pressure_Pa: float | None = None,
  outer_downstream_flow_angle_rad: float | None = None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  attachment_pressure_residual: float | None = None,
  shooting_iterations: int = 0,
  shock: MocFreeBoundaryShockResult | None = None,
  ambient_march: MocAmbientShockBoundaryMarchResult | None = None,
  strip: MocAmbientShockStripResult | None = None,
  message: str,
) -> MocAmbientAttachmentResult:
  return MocAmbientAttachmentResult(
    status=status,
    shock=shock,
    ambient_march=ambient_march,
    strip=strip,
    ambient_pressure_Pa=ambient_pressure_Pa,
    outer_downstream_flow_angle_rad=outer_downstream_flow_angle_rad,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    attachment_pressure_residual=attachment_pressure_residual,
    shooting_iterations=shooting_iterations,
    message=message,
  )
####


def solve_marched_attached_shock_with_ambient_attachment_closure(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_shooting_iterations: int = 40,
) -> MocAmbientAttachmentResult:
  """Close the shock/ambient attachment before assembling an open strip.

  The unknown is the downstream flow angle at the outer shock attachment.
  Each bracket trial solves the local attached compression and matches its
  downstream static pressure to the requested ambient pressure.  The selected
  angle is then used only for the declared linear-to-centerline reference law
  while the shock is marched and the physical ambient ``C-`` boundary is
  generated from the shock ``C+`` sources.

  This removes the attachment angle from the caller's fixed input, but it does
  not close the downstream terminal trace.  The returned strip is therefore a
  physical-boundary continuation seam, not a resolved first cell or a chain
  promotion result.
  """

  if not callable(upstream_state_at) or not callable(upstream_pressure_at):
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      message='upstream state and pressure providers must be callable',
    )
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    ambient_pressure = float(ambient_pressure_Pa)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
  except (IndexError, TypeError, ValueError):
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      message='ambient attachment coordinates, pressure, and angle bracket must be numeric',
    )
  bracket = (lower_angle, upper_angle)
  if not all(
    isfinite(value)
    for value in (*start, ambient_pressure, lower_angle, upper_angle, target_y, target_angle)
  ):
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='ambient attachment inputs must be finite',
    )
  if ambient_pressure <= 0.0:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='ambient_pressure_Pa must be finite and positive',
    )
  if target_y >= start[1]:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='target centerline ordinate must be below the shock start',
    )
  if lower_angle >= upper_angle:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='outer downstream flow-angle lower bound must be below its upper bound',
    )
  if not isinstance(branch, ShockBranch):
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='branch must be a ShockBranch',
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
    isinstance(maximum_boundary_iterations, bool)
    or not isinstance(maximum_boundary_iterations, int)
    or maximum_boundary_iterations < 1
  ):
    raise ValueError('maximum_boundary_iterations must be a positive integer')
  if (
    isinstance(maximum_shooting_iterations, bool)
    or not isinstance(maximum_shooting_iterations, int)
    or maximum_shooting_iterations < 1
  ):
    raise ValueError('maximum_shooting_iterations must be a positive integer')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('attachment_pressure_tolerance', attachment_pressure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')

  try:
    upstream_state = upstream_state_at(start)
    upstream_pressure = upstream_pressure_at(start)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message=f'upstream attachment callback failed: {error}',
    )
  if not isinstance(upstream_state, CharacteristicState):
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='upstream attachment callback returned no CharacteristicState',
    )
  if (
    abs(upstream_state.x_m - start[0]) > position_tolerance_m
    or abs(upstream_state.y_m - start[1]) > position_tolerance_m
  ):
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='upstream attachment state does not lie at the shock start',
    )
  if upstream_pressure is None or not isfinite(float(upstream_pressure)) or upstream_pressure <= 0.0:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='upstream attachment pressure must be finite and positive',
    )
  upstream_pressure_value = float(upstream_pressure)

  def attachment_residual(angle_rad: float) -> tuple[float | None, str]:
    turn = angle_rad - upstream_state.theta_rad
    if turn <= 0.0:
      return None, 'attachment angle does not provide a positive compression turn'
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=upstream_state.mach,
        gamma=upstream_state.gamma,
        upstream_pressure_Pa=upstream_pressure_value,
        target_turn_rad=turn,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return None, f'attachment compression raised: {error}'
    if not compression.converged or compression.downstream_pressure_Pa is None:
      return None, f'attachment compression failed: {compression.message}'
    residual = (
      compression.downstream_pressure_Pa - ambient_pressure
    ) / ambient_pressure
    if not isfinite(residual):
      return None, 'attachment pressure residual is not finite'
    return float(residual), ''

  lower_residual, lower_error = attachment_residual(lower_angle)
  upper_residual, upper_error = attachment_residual(upper_angle)
  if lower_residual is None or upper_residual is None:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message=(
        'ambient attachment requires both angle endpoints to produce an '
        f'attached compression; lower={lower_error}; upper={upper_error}'
      ),
    )
  selected_angle: float | None = None
  selected_residual: float | None = None
  shooting_iterations = 0
  if abs(lower_residual) <= attachment_pressure_tolerance:
    selected_angle = lower_angle
    selected_residual = lower_residual
  elif abs(upper_residual) <= attachment_pressure_tolerance:
    selected_angle = upper_angle
    selected_residual = upper_residual
  elif lower_residual * upper_residual > 0.0:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.BOUNDARY_BRACKET_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=upper_residual,
      message=(
        'outer downstream angle bracket does not straddle the ambient '
        f'attachment pressure residual: lower={lower_residual}, upper={upper_residual}'
      ),
    )
  else:
    current_lower = lower_angle
    current_upper = upper_angle
    current_lower_residual = lower_residual
    last_residual = upper_residual
    for iteration in range(1, maximum_shooting_iterations + 1):
      midpoint = 0.5 * (current_lower + current_upper)
      midpoint_residual, midpoint_error = attachment_residual(midpoint)
      if midpoint_residual is None:
        return _ambient_attachment_failure(
          MocAmbientAttachmentStatus.SHOOTING_FAILURE,
          ambient_pressure_Pa=ambient_pressure,
          outer_flow_angle_bracket=(current_lower, current_upper),
          shooting_iterations=iteration,
          message=(
            'ambient attachment encountered an invalid midpoint and stopped: '
            f'{midpoint_error}'
          ),
        )
      shooting_iterations = iteration
      last_residual = midpoint_residual
      if abs(midpoint_residual) <= attachment_pressure_tolerance:
        selected_angle = midpoint
        selected_residual = midpoint_residual
        break
      if current_lower_residual * midpoint_residual <= 0.0:
        current_upper = midpoint
      else:
        current_lower = midpoint
        current_lower_residual = midpoint_residual
    if selected_angle is None:
      return _ambient_attachment_failure(
        MocAmbientAttachmentStatus.SHOOTING_FAILURE,
        ambient_pressure_Pa=ambient_pressure,
        outer_flow_angle_bracket=(current_lower, current_upper),
        attachment_pressure_residual=last_residual,
        shooting_iterations=shooting_iterations,
        message=(
          'ambient attachment reached its angle-shooting limit before the '
          f'pressure tolerance passed: residual={last_residual}'
        ),
      )
  assert selected_residual is not None
  denominator = start[1] - target_y

  def downstream_angle_at(_index: int, point_m: tuple[float, float]) -> float:
    fraction = (point_m[1] - target_y) / denominator
    fraction = max(0.0, min(1.0, fraction))
    return target_angle + (selected_angle - target_angle) * fraction

  try:
    shock = solve_marched_attached_shock_field(
      upstream_state_at,
      upstream_pressure_at,
      start,
      target_centerline_y_m=target_y,
      downstream_flow_angle_at=downstream_angle_at,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_downstream_flow_angle_rad=selected_angle,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=selected_residual,
      shooting_iterations=shooting_iterations,
      message=f'ambient attachment shock march raised: {error}',
    )
  if not shock.converged or shock.shock_fit is None:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.SHOCK_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_downstream_flow_angle_rad=selected_angle,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=selected_residual,
      shooting_iterations=shooting_iterations,
      shock=shock,
      message=f'ambient attachment shock march did not converge: {shock.message}',
    )
  try:
    ambient_march = march_post_shock_ambient_boundary(
      shock.shock_fit,
      ambient_pressure,
      target_centerline_y_m=target_y,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      maximum_iterations=maximum_boundary_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.AMBIENT_BOUNDARY_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_downstream_flow_angle_rad=selected_angle,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=selected_residual,
      shooting_iterations=shooting_iterations,
      shock=shock,
      message=f'ambient boundary march raised: {error}',
    )
  if not ambient_march.converged:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.AMBIENT_BOUNDARY_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_downstream_flow_angle_rad=selected_angle,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=selected_residual,
      shooting_iterations=shooting_iterations,
      shock=shock,
      ambient_march=ambient_march,
      message=f'ambient boundary march did not converge: {ambient_march.message}',
    )
  try:
    strip = assemble_ambient_shock_characteristic_strip(
      shock.shock_fit,
      ambient_march.boundary_samples,
      ambient_pressure,
      target_centerline_y_m=target_y,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.STRIP_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_downstream_flow_angle_rad=selected_angle,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=selected_residual,
      shooting_iterations=shooting_iterations,
      shock=shock,
      ambient_march=ambient_march,
      message=f'ambient shock/ambient strip assembly raised: {error}',
    )
  if not strip.converged:
    return _ambient_attachment_failure(
      MocAmbientAttachmentStatus.STRIP_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      outer_downstream_flow_angle_rad=selected_angle,
      outer_flow_angle_bracket=bracket,
      attachment_pressure_residual=selected_residual,
      shooting_iterations=shooting_iterations,
      shock=shock,
      ambient_march=ambient_march,
      strip=strip,
      message=f'ambient shock/ambient strip did not converge: {strip.message}',
    )
  return MocAmbientAttachmentResult(
    status=MocAmbientAttachmentStatus.CONVERGED_OPEN_STRIP,
    shock=shock,
    ambient_march=ambient_march,
    strip=strip,
    ambient_pressure_Pa=ambient_pressure,
    outer_downstream_flow_angle_rad=selected_angle,
    outer_flow_angle_bracket=bracket,
    attachment_pressure_residual=selected_residual,
    shooting_iterations=shooting_iterations,
    message=(
      'ambient shock attachment converged and produced a physical open '
      'shock/ambient strip; terminal centerline closure remains pending'
    ),
  )
####


def _ambient_axis_shoot_failure(
  status: MocAmbientAxisClosureShootStatus,
  *,
  ambient_pressure_Pa: float | None = None,
  parameter_bracket: tuple[float, float] | None = None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  selected_trial: MocAmbientAxisClosureShootTrial | None = None,
  shooting_iterations: int = 0,
  trials: Sequence[MocAmbientAxisClosureShootTrial] = (),
  message: str,
) -> MocAmbientAxisClosureShootResult:
  return MocAmbientAxisClosureShootResult(
    status=status,
    selected_parameter=(
      None if selected_trial is None else selected_trial.parameter
    ),
    selected_start_point_m=(
      None if selected_trial is None else selected_trial.start_point_m
    ),
    parameter_bracket=parameter_bracket,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    ambient_pressure_Pa=ambient_pressure_Pa,
    attachment=(None if selected_trial is None else selected_trial.attachment),
    axis_closure=(
      None if selected_trial is None else selected_trial.axis_closure
    ),
    closure_residual=(
      None if selected_trial is None else selected_trial.residual
    ),
    shooting_iterations=shooting_iterations,
    trials=tuple(trials),
    message=message,
  )
####


def solve_marched_attached_shock_with_ambient_axis_closure(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  shock_start_point_at: Callable[[float], tuple[float, float]],
  start_parameter_lower: float,
  start_parameter_upper: float,
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  parameter_tolerance: float = 1.0e-10,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_attachment_shooting_iterations: int = 40,
  maximum_shooting_iterations: int = 40,
) -> MocAmbientAxisClosureShootResult:
  """Shoot an explicit attachment coordinate against the axis pressure.

  The caller owns the physical coordinate and its mapping to an upstream
  boundary point.  At each coordinate, the local downstream attachment angle
  is first solved against ambient pressure.  The resulting shock/ambient
  strip is then continued to a geometric centerline candidate, and the
  carried static-pressure mismatch at that candidate is the global residual.

  This is a bounded two-boundary research solve, not an inferred nozzle law.
  A converged scalar root proves only the attachment and axis-pressure gates;
  the downstream characteristic field, mixed-regime field, and chain-cell
  promotion remain explicitly blocked.
  """

  if not callable(upstream_state_at) or not callable(upstream_pressure_at):
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      message='upstream state and pressure providers must be callable',
    )
  if not callable(shock_start_point_at):
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      message='shock_start_point_at must be callable',
    )
  try:
    lower_parameter = float(start_parameter_lower)
    upper_parameter = float(start_parameter_upper)
    ambient_pressure = float(ambient_pressure_Pa)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
  except (TypeError, ValueError):
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      message='axis-closure parameters, pressure, and angle bracket must be numeric',
    )
  parameter_bracket = (lower_parameter, upper_parameter)
  outer_bracket = (lower_angle, upper_angle)
  if not all(
    isfinite(value)
    for value in (*parameter_bracket, *outer_bracket, ambient_pressure)
  ):
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      parameter_bracket=parameter_bracket,
      outer_flow_angle_bracket=outer_bracket,
      message='axis-closure inputs must be finite',
    )
  if ambient_pressure <= 0.0:
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      parameter_bracket=parameter_bracket,
      outer_flow_angle_bracket=outer_bracket,
      message='ambient_pressure_Pa must be finite and positive',
    )
  if lower_parameter >= upper_parameter:
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      parameter_bracket=parameter_bracket,
      outer_flow_angle_bracket=outer_bracket,
      message='start-parameter lower bound must be below its upper bound',
    )
  if lower_angle >= upper_angle:
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      parameter_bracket=parameter_bracket,
      outer_flow_angle_bracket=outer_bracket,
      message='outer downstream flow-angle lower bound must be below its upper bound',
    )
  if not isinstance(branch, ShockBranch):
    return _ambient_axis_shoot_failure(
      MocAmbientAxisClosureShootStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      parameter_bracket=parameter_bracket,
      outer_flow_angle_bracket=outer_bracket,
      message='branch must be a ShockBranch',
    )
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('attachment_pressure_tolerance', attachment_pressure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('parameter_tolerance', parameter_tolerance),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  for name, value in (
    ('maximum_segment_iterations', maximum_segment_iterations),
    ('maximum_boundary_iterations', maximum_boundary_iterations),
    ('maximum_attachment_shooting_iterations', maximum_attachment_shooting_iterations),
    ('maximum_shooting_iterations', maximum_shooting_iterations),
  ):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
      raise ValueError(f'{name} must be a positive integer')

  trials: list[MocAmbientAxisClosureShootTrial] = []

  def evaluate(parameter: float) -> MocAmbientAxisClosureShootTrial:
    try:
      raw_point = shock_start_point_at(parameter)
      start_point = (float(raw_point[0]), float(raw_point[1]))
    except (IndexError, TypeError, ValueError) as error:
      return MocAmbientAxisClosureShootTrial(
        parameter=parameter,
        start_point_m=None,
        attachment=None,
        axis_closure=None,
        residual=None,
        message=f'shock start point callback failed: {error}',
      )
    if not all(isfinite(value) for value in start_point):
      return MocAmbientAxisClosureShootTrial(
        parameter=parameter,
        start_point_m=start_point,
        attachment=None,
        axis_closure=None,
        residual=None,
        message='shock start point callback returned non-finite coordinates',
      )
    try:
      attachment = solve_marched_attached_shock_with_ambient_attachment_closure(
        upstream_state_at,
        upstream_pressure_at,
        start_point,
        ambient_pressure,
        lower_angle,
        upper_angle,
        target_centerline_y_m=target_centerline_y_m,
        target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
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
        maximum_shooting_iterations=maximum_attachment_shooting_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocAmbientAxisClosureShootTrial(
        parameter=parameter,
        start_point_m=start_point,
        attachment=None,
        axis_closure=None,
        residual=None,
        message=f'ambient attachment trial raised: {error}',
      )
    if not attachment.converged or attachment.ambient_march is None:
      return MocAmbientAxisClosureShootTrial(
        parameter=parameter,
        start_point_m=start_point,
        attachment=attachment,
        axis_closure=None,
        residual=None,
        message=f'ambient attachment trial did not converge: {attachment.message}',
      )
    try:
      axis_closure = probe_post_shock_ambient_axis_closure(
        attachment.ambient_march,
        ambient_pressure,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        pressure_tolerance=pressure_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return MocAmbientAxisClosureShootTrial(
        parameter=parameter,
        start_point_m=start_point,
        attachment=attachment,
        axis_closure=None,
        residual=None,
        message=f'ambient axis trial raised: {error}',
      )
    residual = (
      axis_closure.relative_pressure_residual
      if axis_closure.axis_candidate_verified
      else None
    )
    if residual is None:
      message = f'ambient axis candidate did not converge: {axis_closure.message}'
    else:
      message = axis_closure.message
    return MocAmbientAxisClosureShootTrial(
      parameter=parameter,
      start_point_m=start_point,
      attachment=attachment,
      axis_closure=axis_closure,
      residual=residual,
      message=message,
    )

  def result_for(
    status: MocAmbientAxisClosureShootStatus,
    trial: MocAmbientAxisClosureShootTrial | None,
    current_bracket: tuple[float, float] | None,
    iterations: int,
    message: str,
  ) -> MocAmbientAxisClosureShootResult:
    return _ambient_axis_shoot_failure(
      status,
      ambient_pressure_Pa=ambient_pressure,
      parameter_bracket=current_bracket,
      outer_flow_angle_bracket=outer_bracket,
      selected_trial=trial,
      shooting_iterations=iterations,
      trials=trials,
      message=message,
    )

  lower_trial = evaluate(lower_parameter)
  trials.append(lower_trial)
  if lower_trial.converged:
    return result_for(
      MocAmbientAxisClosureShootStatus.CONVERGED_AXIS_PRESSURE,
      lower_trial,
      parameter_bracket,
      0,
      'ambient attachment and axis-pressure closure converged at the lower parameter bound; downstream physical closure remains pending',
    )
  upper_trial = evaluate(upper_parameter)
  trials.append(upper_trial)
  if upper_trial.converged:
    return result_for(
      MocAmbientAxisClosureShootStatus.CONVERGED_AXIS_PRESSURE,
      upper_trial,
      parameter_bracket,
      0,
      'ambient attachment and axis-pressure closure converged at the upper parameter bound; downstream physical closure remains pending',
    )
  if lower_trial.residual is None or upper_trial.residual is None:
    missing = lower_trial if lower_trial.residual is None else upper_trial
    preferred = upper_trial if upper_trial.residual is not None else lower_trial
    status = (
      MocAmbientAxisClosureShootStatus.ATTACHMENT_FAILURE
      if missing.attachment is None or not missing.attachment.converged
      else MocAmbientAxisClosureShootStatus.AXIS_CANDIDATE_FAILURE
    )
    return result_for(
      status,
      preferred,
      parameter_bracket,
      0,
      'both attachment-coordinate bracket endpoints must produce a valid '
      f'axis candidate: lower={lower_trial.message}; upper={upper_trial.message}',
    )
  if lower_trial.residual * upper_trial.residual > 0.0:
    return result_for(
      MocAmbientAxisClosureShootStatus.BRACKET_FAILURE,
      upper_trial,
      parameter_bracket,
      0,
      'attachment-coordinate bracket does not straddle the signed axis-pressure residual: '
      f'lower={lower_trial.residual}, upper={upper_trial.residual}',
    )

  current_lower = lower_trial
  current_upper = upper_trial
  last_trial = upper_trial
  completed_iterations = 0
  for iteration in range(1, maximum_shooting_iterations + 1):
    if abs(current_upper.parameter - current_lower.parameter) <= parameter_tolerance:
      break
    midpoint_parameter = 0.5 * (
      current_lower.parameter + current_upper.parameter
    )
    midpoint_trial = evaluate(midpoint_parameter)
    trials.append(midpoint_trial)
    completed_iterations = iteration
    last_trial = midpoint_trial
    if midpoint_trial.converged:
      return result_for(
        MocAmbientAxisClosureShootStatus.CONVERGED_AXIS_PRESSURE,
        midpoint_trial,
        (current_lower.parameter, current_upper.parameter),
        iteration,
        'ambient attachment and axis-pressure closure converged in the bounded parameter shoot; downstream physical closure remains pending',
      )
    if midpoint_trial.residual is None:
      return result_for(
        MocAmbientAxisClosureShootStatus.SHOOTING_FAILURE,
        midpoint_trial,
        (current_lower.parameter, current_upper.parameter),
        iteration,
        'axis-pressure shooting encountered a trial without a valid residual and stopped without extrapolating the upstream field: '
        f'{midpoint_trial.message}',
      )
    lower_residual = current_lower.residual
    assert lower_residual is not None
    if lower_residual * midpoint_trial.residual <= 0.0:
      current_upper = midpoint_trial
    else:
      current_lower = midpoint_trial
  return result_for(
    MocAmbientAxisClosureShootStatus.SHOOTING_FAILURE,
    last_trial,
    (current_lower.parameter, current_upper.parameter),
    completed_iterations,
    'axis-pressure shooting reached its iteration or parameter-width limit '
    f'before the ambient axis gate passed: residual={last_trial.residual}',
  )
####


def solve_marched_attached_shock_with_ambient_physical_field(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  shock_start_point_at: Callable[[float], tuple[float, float]],
  start_parameter_lower: float,
  start_parameter_upper: float,
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  attachment_pressure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  parameter_tolerance: float = 1.0e-10,
  maximum_segment_iterations: int = 24,
  maximum_boundary_iterations: int = 16,
  maximum_attachment_shooting_iterations: int = 40,
  maximum_shooting_iterations: int = 40,
) -> MocAmbientPhysicalFieldResult:
  """Gate an ambient/axis shoot before assembling a physical MOC field.

  The underlying axis shoot deliberately reports a scalar pressure result.
  This adapter promotes that result only when its appended ambient-to-axis
  perimeter also passes pressure and streamline-tangency validation.  The
  retained boundary states are then consumed by the coupled shock/ambient/
  centerline assembler; no ambient state, shock point, or downstream turn is
  inferred by this adapter.

  A successful result is suitable for the research continued-cell seam, but
  remains outside the production provider claim until the canonical reflected
  free-boundary and external validation work is complete.
  """

  try:
    shoot = solve_marched_attached_shock_with_ambient_axis_closure(
      upstream_state_at,
      upstream_pressure_at,
      shock_start_point_at,
      start_parameter_lower,
      start_parameter_upper,
      ambient_pressure_Pa,
      outer_downstream_flow_angle_lower_rad,
      outer_downstream_flow_angle_upper_rad,
      target_centerline_y_m=target_centerline_y_m,
      target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      attachment_pressure_tolerance=attachment_pressure_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      parameter_tolerance=parameter_tolerance,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_boundary_iterations=maximum_boundary_iterations,
      maximum_attachment_shooting_iterations=maximum_attachment_shooting_iterations,
      maximum_shooting_iterations=maximum_shooting_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.INVALID_INPUT,
      axis_closure_shoot=None,
      field=None,
      message=f'ambient axis physical-field solve raised: {error}',
    )
  if shoot.status is MocAmbientAxisClosureShootStatus.INVALID_INPUT:
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.INVALID_INPUT,
      axis_closure_shoot=shoot,
      field=None,
      message=f'ambient axis shoot rejected its inputs: {shoot.message}',
    )
  if not shoot.converged:
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.AXIS_SHOOT_FAILURE,
      axis_closure_shoot=shoot,
      field=None,
      message=(
        'ambient axis shooting did not produce a scalar closure candidate: '
        f'{shoot.message}'
      ),
    )

  axis_closure = shoot.axis_closure
  axis_boundary = None if axis_closure is None else axis_closure.axis_boundary
  if (
    axis_closure is None
    or not axis_closure.converged
    or axis_boundary is None
    or not shoot.axis_boundary_verified
    or not axis_boundary.converged
  ):
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.AXIS_BOUNDARY_FAILURE,
      axis_closure_shoot=shoot,
      field=None,
      message=(
        'ambient axis pressure shooting converged, but the complete '
        'ambient-to-axis perimeter did not pass pressure and tangency '
        'validation; no physical field was assembled'
      ),
    )

  attachment = shoot.attachment
  shock = None if attachment is None else attachment.shock
  shock_fit = None if shock is None else shock.shock_fit
  if (
    attachment is None
    or not attachment.converged
    or shock is None
    or not shock.converged
    or shock_fit is None
    or not shock_fit.converged
  ):
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.FIELD_FAILURE,
      axis_closure_shoot=shoot,
      field=None,
      message=(
        'ambient axis shooting retained no converged attached-shock fit for '
        'physical-field assembly'
      ),
    )

  boundary_points = tuple(axis_boundary.points_m)
  boundary_states = tuple(axis_boundary.states)
  boundary_pressures = tuple(axis_boundary.total_pressure_Pa)
  if not (
    len(boundary_points) == len(boundary_states) == len(boundary_pressures)
    and len(boundary_points) >= 2
  ):
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.AXIS_BOUNDARY_FAILURE,
      axis_closure_shoot=shoot,
      field=None,
      message=(
        'accepted ambient axis boundary did not retain matching point, state, '
        'and total-pressure samples'
      ),
    )
  try:
    ambient_samples = tuple(
      MocAmbientBoundarySample(
        point_m=point,
        state=state,
        total_pressure_Pa=pressure,
      )
      for point, state, pressure in zip(
        boundary_points,
        boundary_states,
        boundary_pressures,
        strict=True,
      )
    )
    field = assemble_ambient_boundary_post_shock_field(
      shock_fit,
      ambient_samples,
      float(ambient_pressure_Pa),
      incoming_handoff=incoming_handoff,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      pressure_tolerance=pressure_tolerance,
      tangent_tolerance=tangent_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.FIELD_FAILURE,
      axis_closure_shoot=shoot,
      field=None,
      message=f'ambient physical-field assembly raised: {error}',
    )
  if not field.converged or not field.physical_closure_verified:
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.FIELD_FAILURE,
      axis_closure_shoot=shoot,
      field=field,
      message=(
        'ambient axis boundary passed its local validator, but the coupled '
        f'physical field did not pass immutable closure gates: {field.message}'
      ),
    )
  if not field.state_sampling_available or not field.upstream_shock_coupling_verified:
    return MocAmbientPhysicalFieldResult(
      status=MocAmbientPhysicalFieldStatus.FIELD_FAILURE,
      axis_closure_shoot=shoot,
      field=field,
      message=(
        'ambient physical field closed geometrically but did not retain the '
        'bounded state and upstream-shock samples required for chain continuation'
      ),
    )
  return MocAmbientPhysicalFieldResult(
    status=MocAmbientPhysicalFieldStatus.CONVERGED_AMBIENT_CLOSED,
    axis_closure_shoot=shoot,
    field=field,
    message=(
      'ambient axis shoot passed its full boundary gate and assembled a '
      'state-carrying ambient-closed physical MOC field; production claim and '
      'canonical reflected-domain validation remain pending'
    ),
  )
####


@dataclass(frozen=True, slots=True)
class _AmbientClosureEvaluation:
  angle_rad: float
  shock: MocFreeBoundaryShockResult
  ambient_boundary: MocAmbientPressureBoundaryResult | None
  residual: float | None
  message: str
####


def _ambient_closure_failure(
  status: MocAmbientClosureStatus,
  *,
  ambient_pressure_Pa: float | None = None,
  shock: MocFreeBoundaryShockResult | None = None,
  ambient_boundary: MocAmbientPressureBoundaryResult | None = None,
  outer_downstream_flow_angle_rad: float | None = None,
  outer_flow_angle_bracket: tuple[float, float] | None = None,
  closure_residual: float | None = None,
  shooting_iterations: int = 0,
  message: str,
) -> MocAmbientClosureResult:
  return MocAmbientClosureResult(
    status=status,
    shock=shock,
    ambient_boundary=ambient_boundary,
    ambient_pressure_Pa=ambient_pressure_Pa,
    outer_downstream_flow_angle_rad=outer_downstream_flow_angle_rad,
    outer_flow_angle_bracket=outer_flow_angle_bracket,
    closure_residual=closure_residual,
    shooting_iterations=shooting_iterations,
    message=message,
  )
####


def solve_marched_attached_shock_with_ambient_pressure_closure(
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  closure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
) -> MocAmbientClosureResult:
  """Shoot a linear downstream turn law against the actual outer perimeter.

  The downstream angle is interpolated linearly between the requested outer
  angle at ``start_point_m`` and the requested centerline angle.  Each trial
  generates a fresh attached shock and post-shock characteristic field.  The
  signed scalar residual is the mean static-pressure mismatch on the
  extracted non-shock/non-centerline perimeter.  The independent validator
  still has to accept every pressure and tangent sample before this result can
  be called ambient-closed.

  This is a bounded, one-parameter research closure for the planar lane.  It
  is not a universal plume free-boundary solver: a non-straddling bracket,
  missing upstream state, invalid characteristic field, or failed perimeter
  gate is returned explicitly and never repaired by extrapolating a state.
  """

  if not callable(upstream_state_at) or not callable(upstream_pressure_at):
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      message='upstream state and pressure providers must be callable',
    )
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    ambient_pressure = float(ambient_pressure_Pa)
    lower_angle = float(outer_downstream_flow_angle_lower_rad)
    upper_angle = float(outer_downstream_flow_angle_upper_rad)
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
  except (IndexError, TypeError, ValueError):
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      message='ambient closure coordinates, pressure, and angle bracket must be numeric',
    )
  bracket = (lower_angle, upper_angle)
  if not all(
    isfinite(value)
    for value in (*start, ambient_pressure, lower_angle, upper_angle, target_y, target_angle)
  ):
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='ambient closure inputs must be finite',
    )
  if ambient_pressure <= 0.0:
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='ambient_pressure_Pa must be finite and positive',
    )
  if target_y >= start[1]:
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='target centerline ordinate must be below the shock start',
    )
  if lower_angle >= upper_angle:
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='outer downstream flow-angle lower bound must be below its upper bound',
    )
  if not isinstance(branch, ShockBranch):
    return _ambient_closure_failure(
      MocAmbientClosureStatus.INVALID_INPUT,
      ambient_pressure_Pa=ambient_pressure,
      outer_flow_angle_bracket=bracket,
      message='branch must be a ShockBranch',
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
    isinstance(maximum_shooting_iterations, bool)
    or not isinstance(maximum_shooting_iterations, int)
    or maximum_shooting_iterations < 1
  ):
    raise ValueError('maximum_shooting_iterations must be a positive integer')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('closure_tolerance', closure_tolerance),
    ('pressure_tolerance', pressure_tolerance),
    ('tangent_tolerance', tangent_tolerance),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  ####

  denominator = start[1] - target_y

  def evaluate(angle_rad: float) -> _AmbientClosureEvaluation:
    def downstream_angle_at(_index: int, point_m: tuple[float, float]) -> float:
      fraction = (point_m[1] - target_y) / denominator
      fraction = max(0.0, min(1.0, fraction))
      return target_angle + (angle_rad - target_angle) * fraction

    try:
      shock = solve_marched_attached_shock_field(
        upstream_state_at,
        upstream_pressure_at,
        start,
        target_centerline_y_m=target_y,
        downstream_flow_angle_at=downstream_angle_at,
        incoming_handoff=incoming_handoff,
        sample_count=sample_count,
        branch=branch,
        position_tolerance_m=position_tolerance_m,
        invariant_tolerance=invariant_tolerance,
        shock_angle_tolerance_rad=shock_angle_tolerance_rad,
        maximum_segment_iterations=maximum_segment_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      shock = MocFreeBoundaryShockResult(
        status=MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE,
        shock_fit=None,
        field=None,
        shock_points_m=(),
        upstream_states=(),
        upstream_pressure_Pa=(),
        downstream_flow_angles_rad=(),
        shock_angle_residuals_rad=(),
        maximum_shock_angle_residual_rad=None,
        endpoint_m=None,
        message=f'ambient closure trial raised while generating the shock: {error}',
      )
      return _AmbientClosureEvaluation(angle_rad, shock, None, None, shock.message)
    if not shock.converged or shock.field is None or shock.shock_fit is None:
      return _AmbientClosureEvaluation(
        angle_rad,
        shock,
        None,
        None,
        f'generated shock/field did not converge: {shock.message}',
      )
    try:
      ambient_boundary = validate_post_shock_ambient_boundary(
        shock.field,
        shock.shock_fit,
        ambient_pressure,
        position_tolerance_m=position_tolerance_m,
        pressure_tolerance=pressure_tolerance,
        tangent_tolerance=tangent_tolerance,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _AmbientClosureEvaluation(
        angle_rad,
        shock,
        None,
        None,
        f'ambient perimeter validation raised: {error}',
      )
    if not ambient_boundary.pressure_residuals:
      return _AmbientClosureEvaluation(
        angle_rad,
        shock,
        ambient_boundary,
        None,
        f'ambient perimeter has no scalar pressure residual: {ambient_boundary.message}',
      )
    residual = sum(ambient_boundary.pressure_residuals) / len(ambient_boundary.pressure_residuals)
    if not isfinite(residual):
      return _AmbientClosureEvaluation(
        angle_rad,
        shock,
        ambient_boundary,
        None,
        'ambient perimeter scalar pressure residual is not finite',
      )
    return _AmbientClosureEvaluation(
      angle_rad,
      shock,
      ambient_boundary,
      float(residual),
      ambient_boundary.message or 'ambient perimeter pressure residual evaluated',
    )

  lower = evaluate(lower_angle)
  upper = evaluate(upper_angle)

  def accepted(
    trial: _AmbientClosureEvaluation,
    iterations: int,
    current_bracket: tuple[float, float],
  ) -> MocAmbientClosureResult | None:
    if trial.residual is None or abs(trial.residual) > closure_tolerance:
      return None
    if trial.ambient_boundary is not None and trial.ambient_boundary.converged:
      return _ambient_closure_failure(
        MocAmbientClosureStatus.CONVERGED_AMBIENT_CLOSED,
        ambient_pressure_Pa=ambient_pressure,
        shock=trial.shock,
        ambient_boundary=trial.ambient_boundary,
        outer_downstream_flow_angle_rad=trial.angle_rad,
        outer_flow_angle_bracket=current_bracket,
        closure_residual=trial.residual,
        shooting_iterations=iterations,
        message=(
          'ambient-pressure shooting converged on the actual post-shock outer '
          'perimeter; all pressure and streamline-tangency gates passed'
        ),
      )
    return _ambient_closure_failure(
      MocAmbientClosureStatus.AMBIENT_BOUNDARY_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      shock=trial.shock,
      ambient_boundary=trial.ambient_boundary,
      outer_downstream_flow_angle_rad=trial.angle_rad,
      outer_flow_angle_bracket=current_bracket,
      closure_residual=trial.residual,
      shooting_iterations=iterations,
      message=(
        'the scalar mean ambient-pressure residual reached tolerance, but '
        'the full outer perimeter did not pass pressure and tangent validation: '
        f'{trial.ambient_boundary.message if trial.ambient_boundary is not None else trial.message}'
      ),
    )

  endpoint = accepted(lower, 0, bracket)
  if endpoint is not None:
    return endpoint
  endpoint = accepted(upper, 0, bracket)
  if endpoint is not None:
    return endpoint

  if lower.residual is None or upper.residual is None:
    preferred = upper if upper.shock.converged else lower
    status = (
      MocAmbientClosureStatus.AMBIENT_BOUNDARY_FAILURE
      if preferred.shock.converged
      else MocAmbientClosureStatus.FIELD_FAILURE
    )
    return _ambient_closure_failure(
      status,
      ambient_pressure_Pa=ambient_pressure,
      shock=preferred.shock,
      ambient_boundary=preferred.ambient_boundary,
      outer_downstream_flow_angle_rad=preferred.angle_rad,
      outer_flow_angle_bracket=bracket,
      closure_residual=preferred.residual,
      message=(
        'ambient-pressure shooting requires both bracket endpoints to produce '
        'a complete post-shock outer perimeter; '
        f'lower={lower.message}; upper={upper.message}'
      ),
    )
  if lower.residual * upper.residual > 0.0:
    return _ambient_closure_failure(
      MocAmbientClosureStatus.BOUNDARY_BRACKET_FAILURE,
      ambient_pressure_Pa=ambient_pressure,
      shock=upper.shock,
      ambient_boundary=upper.ambient_boundary,
      outer_downstream_flow_angle_rad=upper.angle_rad,
      outer_flow_angle_bracket=bracket,
      closure_residual=upper.residual,
      message=(
        'outer downstream flow-angle bracket does not straddle the signed '
        'mean ambient-pressure residual: '
        f'lower={lower.residual}, upper={upper.residual}'
      ),
    )

  current_lower = lower
  current_upper = upper
  last = upper
  for iteration in range(1, maximum_shooting_iterations + 1):
    midpoint_angle = 0.5 * (current_lower.angle_rad + current_upper.angle_rad)
    midpoint = evaluate(midpoint_angle)
    if midpoint.residual is None:
      return _ambient_closure_failure(
        MocAmbientClosureStatus.SHOOTING_FAILURE,
        ambient_pressure_Pa=ambient_pressure,
        shock=midpoint.shock,
        ambient_boundary=midpoint.ambient_boundary,
        outer_downstream_flow_angle_rad=midpoint.angle_rad,
        outer_flow_angle_bracket=(current_lower.angle_rad, current_upper.angle_rad),
        closure_residual=midpoint.residual,
        shooting_iterations=iteration,
        message=(
          'ambient-pressure shooting encountered an invalid midpoint and stopped '
          'without extrapolating the upstream field: '
          f'{midpoint.message}'
        ),
      )
    last = midpoint
    endpoint = accepted(
      midpoint,
      iteration,
      (current_lower.angle_rad, current_upper.angle_rad),
    )
    if endpoint is not None:
      return endpoint
    midpoint_residual = midpoint.residual
    lower_residual = current_lower.residual
    assert lower_residual is not None
    assert midpoint_residual is not None
    if lower_residual * midpoint_residual <= 0.0:
      current_upper = midpoint
    else:
      current_lower = midpoint
  ####
  return _ambient_closure_failure(
    MocAmbientClosureStatus.SHOOTING_FAILURE,
    ambient_pressure_Pa=ambient_pressure,
    shock=last.shock,
    ambient_boundary=last.ambient_boundary,
    outer_downstream_flow_angle_rad=last.angle_rad,
    outer_flow_angle_bracket=(current_lower.angle_rad, current_upper.angle_rad),
    closure_residual=last.residual,
    shooting_iterations=maximum_shooting_iterations,
    message=(
      'ambient-pressure shooting reached its iteration limit before the full '
      f'outer-boundary closure gate passed; residual={last.residual}'
    ),
  )
####


class MocInvariantClosureFamily(str, Enum):
  """The downstream characteristic invariant held during shooting."""

  K_PLUS = 'K+'
  K_MINUS = 'K-'
####


class MocInvariantClosureStatus(str, Enum):
  """Structured outcomes for invariant-conditioned shock closure."""

  CONVERGED_CLOSED = 'converged_invariant_conditioned_field'
  INVALID_INPUT = 'invalid_input'
  BOUNDARY_CONDITION_FAILURE = 'boundary_condition_failure'
  SHOOTING_FAILURE = 'shooting_failure'
  FIELD_FAILURE = 'field_failure'
####


@dataclass(frozen=True, slots=True)
class MocInvariantClosureResult:
  """A bracketed invariant shoot and its optional closed shock field."""

  status: MocInvariantClosureStatus
  invariant_family: MocInvariantClosureFamily
  shock: MocFreeBoundaryShockResult | None
  invariant_target: float | None
  invariant_bracket: tuple[float, float] | None
  closure_residual_rad: float | None
  shooting_iterations: int
  source_window_start_index: int | None
  message: str = ''

  @property
  def converged(self) -> bool:
    return self.status is MocInvariantClosureStatus.CONVERGED_CLOSED
  ####

  @property
  def physical_closure_verified(self) -> bool:
    return self.converged and self.shock is not None and self.shock.physical_closure_verified
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'physical_closure_verified': self.physical_closure_verified,
      'invariant_family': self.invariant_family.value,
      'invariant_target': self.invariant_target,
      'invariant_bracket': self.invariant_bracket,
      'closure_residual_rad': self.closure_residual_rad,
      'shooting_iterations': self.shooting_iterations,
      'source_window_start_index': self.source_window_start_index,
      'shock': None if self.shock is None else self.shock.as_report(),
      'message': self.message,
    }
####


@dataclass(frozen=True, slots=True)
class _InvariantEvaluation:
  angle_rad: float | None
  residual: float | None
  message: str
####


def _failure(
  status: MocInvariantClosureStatus,
  family: MocInvariantClosureFamily,
  *,
  shock: MocFreeBoundaryShockResult | None = None,
  invariant_target: float | None = None,
  invariant_bracket: tuple[float, float] | None = None,
  closure_residual_rad: float | None = None,
  shooting_iterations: int = 0,
  source_window_start_index: int | None = None,
  message: str,
) -> MocInvariantClosureResult:
  return MocInvariantClosureResult(
    status=status,
    invariant_family=family,
    shock=shock,
    invariant_target=invariant_target,
    invariant_bracket=invariant_bracket,
    closure_residual_rad=closure_residual_rad,
    shooting_iterations=shooting_iterations,
    source_window_start_index=source_window_start_index,
    message=message,
  )
####


def _invariant_value(
  family: MocInvariantClosureFamily,
  theta_rad: float,
  downstream_mach: float,
  gamma: float,
) -> float:
  nu = prandtl_meyer_angle_rad(downstream_mach, gamma)
  return theta_rad - nu if family is MocInvariantClosureFamily.K_PLUS else theta_rad + nu
####


def _solve_downstream_angle(
  state: CharacteristicState,
  pressure_Pa: float,
  family: MocInvariantClosureFamily,
  invariant_target: float,
  *,
  branch: ShockBranch,
  maximum_downstream_angle_rad: float,
  invariant_tolerance: float,
  maximum_scan_samples: int,
) -> _InvariantEvaluation:
  """Solve one local downstream angle on the selected attached branch."""

  lower = state.theta_rad + max(1.0e-8, invariant_tolerance)
  upper = float(maximum_downstream_angle_rad)
  if upper <= lower:
    return _InvariantEvaluation(
      angle_rad=None,
      residual=None,
      message='downstream invariant search interval is empty for the local state',
    )

  def evaluate(angle_rad: float) -> tuple[float | None, str] | None:
    try:
      compression = solve_attached_compression_to_turn(
        upstream_mach=state.mach,
        gamma=state.gamma,
        upstream_pressure_Pa=pressure_Pa,
        target_turn_rad=angle_rad - state.theta_rad,
        branch=branch,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return None, f'local attached-compression inversion failed: {error}'
    if not compression.converged or compression.downstream_mach is None:
      return None, f'local attached-compression inversion failed: {compression.message}'
    value = _invariant_value(
      family,
      angle_rad,
      compression.downstream_mach,
      state.gamma,
    )
    return value - invariant_target, ''

  try:
    lower_value = evaluate(lower)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _InvariantEvaluation(None, None, f'local invariant evaluation failed: {error}')
  if lower_value is None or lower_value[0] is None:
    return _InvariantEvaluation(
      None,
      None,
      'local invariant evaluation returned no result at the lower angle',
    )
  previous_angle = lower
  previous_residual = lower_value[0]
  if abs(previous_residual) <= invariant_tolerance:
    return _InvariantEvaluation(previous_angle, previous_residual, '')

  for index in range(1, maximum_scan_samples + 1):
    angle = lower + (upper - lower) * index / maximum_scan_samples
    current = evaluate(angle)
    if current is None or current[0] is None:
      if index == 1:
        continue
      break
    current_residual = current[0]
    if abs(current_residual) <= invariant_tolerance:
      return _InvariantEvaluation(angle, current_residual, '')
    if previous_residual * current_residual < 0.0:
      bracket_lower = previous_angle
      bracket_upper = angle
      bracket_residual = previous_residual
      for _ in range(80):
        midpoint = 0.5 * (bracket_lower + bracket_upper)
        midpoint_result = evaluate(midpoint)
        if midpoint_result is None or midpoint_result[0] is None:
          return _InvariantEvaluation(
            None,
            None,
            'local invariant bisection left the attached-compression branch',
          )
        midpoint_residual = midpoint_result[0]
        if abs(midpoint_residual) <= invariant_tolerance:
          return _InvariantEvaluation(midpoint, midpoint_residual, '')
        if bracket_residual * midpoint_residual <= 0.0:
          bracket_upper = midpoint
        else:
          bracket_lower = midpoint
          bracket_residual = midpoint_residual
      return _InvariantEvaluation(
        0.5 * (bracket_lower + bracket_upper),
        midpoint_residual,
        'local invariant bisection did not meet its residual tolerance',
      )
    previous_angle = angle
    previous_residual = current_residual
  return _InvariantEvaluation(
    None,
    None,
    'the requested downstream invariant was not reached on the attached branch',
  )
####


def _run_invariant_target(
  upstream_strip: MocSourceCharacteristicStripResult,
  start_point_m: tuple[float, float],
  family: MocInvariantClosureFamily,
  invariant_target: float,
  *,
  target_centerline_y_m: float,
  target_centerline_flow_angle_rad: float,
  incoming_handoff: Sequence[MocChainBoundarySample] | None,
  sample_count: int,
  branch: ShockBranch,
  position_tolerance_m: float,
  invariant_tolerance: float,
  shock_angle_tolerance_rad: float,
  maximum_segment_iterations: int,
  maximum_downstream_angle_rad: float,
  maximum_invariant_scan_samples: int,
) -> tuple[float | None, MocFreeBoundaryShockResult, str | None]:
  boundary_errors: list[str] = []

  def downstream_angle_at(index: int, point_m: tuple[float, float]) -> float:
    state = upstream_strip.state_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    pressure = upstream_strip.static_pressure_at(
      point_m,
      position_tolerance_m=position_tolerance_m,
    )
    if state is None or pressure is None:
      message = f'upstream source strip has no state/pressure at shock sample {index}'
      boundary_errors.append(message)
      return float('nan')
    evaluation = _solve_downstream_angle(
      state,
      pressure,
      family,
      invariant_target,
      branch=branch,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      invariant_tolerance=invariant_tolerance,
      maximum_scan_samples=maximum_invariant_scan_samples,
    )
    if evaluation.angle_rad is None:
      boundary_errors.append(
        f'downstream invariant boundary failed at shock sample {index}: '
        f'{evaluation.message}'
      )
      return float('nan')
    return evaluation.angle_rad

  shock = solve_marched_attached_shock_from_source_strip(
    upstream_strip,
    start_point_m,
    target_centerline_y_m=target_centerline_y_m,
    downstream_flow_angle_at=downstream_angle_at,
    incoming_handoff=incoming_handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
  )
  if shock.sample_count != sample_count:
    return (
      None,
      shock,
      boundary_errors[-1]
      if boundary_errors
      else f'invariant-conditioned shock stopped at {shock.sample_count}/{sample_count} samples',
    )
  if shock.shock_fit is None or not shock.shock_fit.converged:
    return (
      None,
      shock,
      boundary_errors[-1]
      if boundary_errors
      else f'invariant-conditioned shock fit did not converge: {shock.message}',
    )
  if len(shock.downstream_flow_angles_rad) != sample_count:
    return None, shock, 'invariant-conditioned shock returned an incomplete downstream angle trace'
  terminal_angle = shock.downstream_flow_angles_rad[-1]
  residual = float(terminal_angle) - float(target_centerline_flow_angle_rad)
  if not isfinite(residual):
    return None, shock, 'invariant-conditioned shock produced a non-finite centerline closure residual'
  return residual, shock, None
####


def solve_marched_attached_shock_with_constant_invariant_closure(
  upstream_strip: MocSourceCharacteristicStripResult,
  start_point_m: tuple[float, float],
  invariant_family: MocInvariantClosureFamily,
  invariant_target_lower: float,
  invariant_target_upper: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  incoming_handoff: Sequence[MocChainBoundarySample] | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-9,
  closure_tolerance_rad: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-1,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
) -> MocInvariantClosureResult:
  """Shoot a constant downstream invariant to a centerline flow-angle target.

  Both bracket endpoints must produce a complete, attached shock sample set;
  a missing source-strip state or an unattached local compression invalidates
  the bracket.  The solver never skips an invalid midpoint or extrapolates the
  upstream field.  A returned converged result therefore includes both the
  scalar closure residual and the existing closed post-shock field gate.
  """

  family = (
    invariant_family
    if isinstance(invariant_family, MocInvariantClosureFamily)
    else MocInvariantClosureFamily.K_PLUS
  )
  if not isinstance(upstream_strip, MocSourceCharacteristicStripResult):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      message='upstream_strip must be a MocSourceCharacteristicStripResult',
    )
  if not isinstance(invariant_family, MocInvariantClosureFamily):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      MocInvariantClosureFamily.K_PLUS,
      message='invariant_family must be a MocInvariantClosureFamily',
    )
  if not upstream_strip.converged:
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=f'upstream source strip is not converged: {upstream_strip.message}',
    )
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    target_y = float(target_centerline_y_m)
    target_angle = float(target_centerline_flow_angle_rad)
    lower_target = float(invariant_target_lower)
    upper_target = float(invariant_target_upper)
  except (IndexError, TypeError, ValueError):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='shock closure coordinates, target angle, and invariant bracket must be numeric',
    )
  if not all(isfinite(value) for value in (*start, target_y, target_angle, lower_target, upper_target)):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='shock closure inputs must be finite',
    )
  if target_y >= start[1]:
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='target centerline ordinate must be below the shock start',
    )
  if lower_target >= upper_target:
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='invariant bracket lower target must be below upper target',
    )
  if not isinstance(branch, ShockBranch):
    return _failure(
      MocInvariantClosureStatus.INVALID_INPUT,
      family,
      source_window_start_index=upstream_strip.source_window_start_index,
      message='branch must be a ShockBranch',
    )
  if isinstance(sample_count, bool) or not isinstance(sample_count, int) or sample_count < 3:
    raise ValueError('sample_count must be an integer of at least three')
  if isinstance(maximum_shooting_iterations, bool) or not isinstance(maximum_shooting_iterations, int) or maximum_shooting_iterations < 1:
    raise ValueError('maximum_shooting_iterations must be a positive integer')
  if isinstance(maximum_segment_iterations, bool) or not isinstance(maximum_segment_iterations, int) or maximum_segment_iterations < 1:
    raise ValueError('maximum_segment_iterations must be a positive integer')
  if isinstance(maximum_invariant_scan_samples, bool) or not isinstance(maximum_invariant_scan_samples, int) or maximum_invariant_scan_samples < 4:
    raise ValueError('maximum_invariant_scan_samples must be an integer of at least four')
  for name, value in (
    ('position_tolerance_m', position_tolerance_m),
    ('invariant_tolerance', invariant_tolerance),
    ('closure_tolerance_rad', closure_tolerance_rad),
    ('shock_angle_tolerance_rad', shock_angle_tolerance_rad),
    ('maximum_downstream_angle_rad', maximum_downstream_angle_rad),
  ):
    if not isfinite(float(value)) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
  if maximum_downstream_angle_rad <= target_angle:
    raise ValueError('maximum_downstream_angle_rad must exceed the target flow angle')
  ####

  bracket = (lower_target, upper_target)
  lower_residual, lower_shock, lower_error = _run_invariant_target(
    upstream_strip,
    start,
    invariant_family,
    lower_target,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_angle,
    incoming_handoff=incoming_handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
  )
  upper_residual, upper_shock, upper_error = _run_invariant_target(
    upstream_strip,
    start,
    invariant_family,
    upper_target,
    target_centerline_y_m=target_y,
    target_centerline_flow_angle_rad=target_angle,
    incoming_handoff=incoming_handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
  )
  if lower_residual is None or upper_residual is None:
    return _failure(
      MocInvariantClosureStatus.BOUNDARY_CONDITION_FAILURE,
      invariant_family,
      shock=upper_shock if upper_residual is None else lower_shock,
      invariant_bracket=bracket,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=(
        'invariant shooting requires both bracket endpoints to reach the '
        'centerline with a complete attached-shock fit; '
        f'lower={lower_error or "valid"}; upper={upper_error or "valid"}'
      ),
    )

  def accept(
    residual: float,
    shock: MocFreeBoundaryShockResult,
    target: float,
    iterations: int,
  ) -> MocInvariantClosureResult | None:
    if abs(residual) > closure_tolerance_rad:
      return None
    if shock.converged and shock.field is not None and shock.field.converged:
      return _failure(
        MocInvariantClosureStatus.CONVERGED_CLOSED,
        invariant_family,
        shock=shock,
        invariant_target=target,
        invariant_bracket=bracket,
        closure_residual_rad=residual,
        shooting_iterations=iterations,
        source_window_start_index=upstream_strip.source_window_start_index,
        message=(
          'constant downstream invariant shooting converged with a closed '
          'attached-shock and post-shock characteristic field; this remains '
          'a boundary-conditioned research result'
        ),
      )
    return _failure(
      MocInvariantClosureStatus.FIELD_FAILURE,
      invariant_family,
      shock=shock,
      invariant_target=target,
      invariant_bracket=bracket,
      closure_residual_rad=residual,
      shooting_iterations=iterations,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=(
        'invariant shooting reached the centerline angle target, but the '
        f'generated shock field did not close: {shock.message}'
      ),
    )

  endpoint = accept(lower_residual, lower_shock, lower_target, 0)
  if endpoint is not None:
    return endpoint
  endpoint = accept(upper_residual, upper_shock, upper_target, 0)
  if endpoint is not None:
    return endpoint
  if lower_residual * upper_residual > 0.0:
    return _failure(
      MocInvariantClosureStatus.SHOOTING_FAILURE,
      invariant_family,
      shock=upper_shock,
      invariant_bracket=bracket,
      closure_residual_rad=upper_residual,
      source_window_start_index=upstream_strip.source_window_start_index,
      message=(
        'invariant bracket does not straddle the requested centerline flow-angle '
        f'closure: lower residual={lower_residual}, upper residual={upper_residual}'
      ),
    )

  current_lower = lower_target
  current_upper = upper_target
  current_lower_residual = lower_residual
  last_shock = upper_shock
  last_residual = upper_residual
  for iteration in range(1, maximum_shooting_iterations + 1):
    midpoint = 0.5 * (current_lower + current_upper)
    midpoint_residual, midpoint_shock, midpoint_error = _run_invariant_target(
      upstream_strip,
      start,
      invariant_family,
      midpoint,
      target_centerline_y_m=target_y,
      target_centerline_flow_angle_rad=target_angle,
      incoming_handoff=incoming_handoff,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
      maximum_downstream_angle_rad=maximum_downstream_angle_rad,
      maximum_invariant_scan_samples=maximum_invariant_scan_samples,
    )
    if midpoint_residual is None:
      return _failure(
        MocInvariantClosureStatus.SHOOTING_FAILURE,
        invariant_family,
        shock=midpoint_shock,
        invariant_target=midpoint,
        invariant_bracket=(current_lower, current_upper),
        source_window_start_index=upstream_strip.source_window_start_index,
        message=(
          'invariant shooting encountered an invalid midpoint and stopped '
          'without extrapolating the upstream field: '
          f'{midpoint_error or midpoint_shock.message}'
        ),
      )
    last_shock = midpoint_shock
    last_residual = midpoint_residual
    endpoint = accept(midpoint_residual, midpoint_shock, midpoint, iteration)
    if endpoint is not None:
      return endpoint
    if current_lower_residual * midpoint_residual <= 0.0:
      current_upper = midpoint
    else:
      current_lower = midpoint
      current_lower_residual = midpoint_residual
  ####
  return _failure(
    MocInvariantClosureStatus.SHOOTING_FAILURE,
    invariant_family,
    shock=last_shock,
    invariant_target=0.5 * (current_lower + current_upper),
    invariant_bracket=(current_lower, current_upper),
    closure_residual_rad=last_residual,
    shooting_iterations=maximum_shooting_iterations,
    source_window_start_index=upstream_strip.source_window_start_index,
    message=(
      'invariant shooting reached its iteration limit before satisfying the '
      f'centerline closure tolerance; residual={last_residual}'
    ),
  )
####


def solve_marched_attached_shock_chain_cell_with_constant_invariant_closure(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_strip: MocSourceCharacteristicStripResult,
  start_point_m: tuple[float, float],
  end_x_m: float,
  invariant_family: MocInvariantClosureFamily,
  invariant_target_lower: float,
  invariant_target_upper: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-9,
  invariant_tolerance: float = 1.0e-9,
  closure_tolerance_rad: float = 1.0e-9,
  shock_angle_tolerance_rad: float = 1.0e-1,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
  maximum_downstream_angle_rad: float = 0.9,
  maximum_invariant_scan_samples: int = 64,
) -> MocPostShockChainCellSolve:
  """Adapt an invariant-conditioned field into one typed chain-cell solve.

  The prior cell's terminal trace is checked byte-for-byte at this boundary
  and passed to the field assembler as ``incoming_handoff``.  This helper does
  not infer the next shock location from an axial section and does not accept a
  reduced-order candidate; an unresolved invariant shoot raises instead of
  returning a relabeled cell.
  """

  if not isinstance(current_cell, MocChainCell):
    raise TypeError('current_cell must be a MocChainCell')
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    raise ValueError('next_cell_index must immediately follow current_cell.cell_index')
  handoff = tuple(incoming_handoff)
  if handoff != current_cell.continuation_boundary:
    raise ValueError('incoming_handoff must exactly match the current cell boundary')
  if len(handoff) < 3:
    raise ValueError('continued invariant-conditioned cells require at least three handoff samples')
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    end_x = float(end_x_m)
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError('continued invariant-conditioned cell geometry must be numeric') from error
  if not all(isfinite(value) for value in (*start, end_x)):
    raise ValueError('continued invariant-conditioned cell geometry must be finite')
  if start[0] <= current_cell.end_x_m + position_tolerance_m:
    raise ValueError('continued invariant-conditioned shock must start downstream of the current cell')
  if end_x <= current_cell.end_x_m:
    raise ValueError('continued invariant-conditioned cell end_x_m must be downstream of the current cell')

  result = solve_marched_attached_shock_with_constant_invariant_closure(
    upstream_strip,
    start,
    invariant_family,
    invariant_target_lower,
    invariant_target_upper,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    incoming_handoff=handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    closure_tolerance_rad=closure_tolerance_rad,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
    maximum_downstream_angle_rad=maximum_downstream_angle_rad,
    maximum_invariant_scan_samples=maximum_invariant_scan_samples,
  )
  if not result.converged or result.shock is None or result.shock.field is None:
    raise ValueError(
      'continued invariant-conditioned shock cell did not converge: '
      f'{result.status.value}: {result.message}'
    )
  field = result.shock.field
  expected_states = tuple(sample.state for sample in handoff)
  expected_pressures = tuple(sample.total_pressure_Pa for sample in handoff)
  if (
    field.incoming_handoff_states != expected_states
    or field.incoming_handoff_total_pressure_Pa != expected_pressures
  ):
    raise ValueError(
      'continued invariant-conditioned field did not retain the exact incoming handoff'
    )
  return MocPostShockChainCellSolve(field=field, end_x_m=end_x)
####


def solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  end_x_m: float,
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  closure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
  """Solve one ambient-pressure-conditioned continued cell or stop explicitly.

  The prior post-shock perimeter is consumed as an exact handoff, while the
  caller-supplied state and pressure callbacks remain the only upstream field
  source.  A fully accepted ambient closure may replace that upstream field
  for a later research-cell attempt.  Bracket, tangent, and domain failures
  are typed stops; this adapter never extrapolates a missing upstream state or
  relabels a failed candidate as a chain cell.
  """

  if not isinstance(current_cell, MocChainCell):
    raise TypeError('current_cell must be a MocChainCell')
  if (
    isinstance(next_cell_index, bool)
    or not isinstance(next_cell_index, int)
    or next_cell_index != current_cell.cell_index + 1
  ):
    raise ValueError('next_cell_index must immediately follow current_cell.cell_index')
  if not callable(upstream_state_at) or not callable(upstream_pressure_at):
    raise TypeError('upstream state and pressure providers must be callable')
  if current_cell.continuation_boundary_kind is not MocChainBoundaryKind.POST_SHOCK_FIELD_PERIMETER:
    raise ValueError(
      'ambient-pressure field-coupled continuation requires a post-shock '
      'field perimeter handoff'
    )
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
    raise ValueError(
      'ambient-pressure field-coupled continuation requires at least three '
      'handoff samples'
    )
  try:
    start = (float(start_point_m[0]), float(start_point_m[1]))
    end_x = float(end_x_m)
    tolerance = float(position_tolerance_m)
  except (IndexError, TypeError, ValueError) as error:
    raise ValueError(
      'continued ambient-pressure cell geometry and tolerance must be numeric'
    ) from error
  if not all(isfinite(value) for value in (*start, end_x, tolerance)):
    raise ValueError('continued ambient-pressure cell geometry must be finite')
  if tolerance <= 0.0:
    raise ValueError('position_tolerance_m must be finite and positive')
  if start[0] <= current_cell.end_x_m + tolerance:
    raise ValueError(
      'continued ambient-pressure shock must start downstream of the current cell'
    )
  if end_x <= current_cell.end_x_m:
    raise ValueError(
      'continued ambient-pressure cell end_x_m must be downstream of the current cell'
    )

  result = solve_marched_attached_shock_with_ambient_pressure_closure(
    upstream_state_at,
    upstream_pressure_at,
    start,
    ambient_pressure_Pa,
    outer_downstream_flow_angle_lower_rad,
    outer_downstream_flow_angle_upper_rad,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    incoming_handoff=handoff,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    closure_tolerance=closure_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
  )
  shock = result.shock
  field = None if shock is None else shock.field
  diagnostics: dict[str, object] = {
    'termination_model': 'ambient-pressure-field-coupled-chain',
    'upstream_field_model': 'caller-bounded-state-pressure-field',
    'ambient_closure_status': result.status.value,
    'ambient_closure_report': result.as_report(),
    'next_cell_index': next_cell_index,
    'incoming_handoff_sample_count': len(handoff),
  }

  if (
    result.converged
    and result.physical_closure_verified
    and result.upstream_coupling_verified
    and shock is not None
    and field is not None
    and field.converged
    and field.upstream_shock_coupling_verified
  ):
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
          'ambient-pressure closure produced a field but did not retain the '
          'exact incoming chain handoff'
        ),
        diagnostics=diagnostics,
      )
    diagnostics['accepted_field_status'] = field.status.value
    diagnostics['physical_closure_verified'] = True
    # Preserve the field's numerical evidence while keeping the research
    # closure provenance visible to downstream reports.
    return MocPostShockChainCellSolve(
      field=replace(
        field,
        shock_closure_status='ambient-pressure-closed-research',
      ),
      end_x_m=end_x,
    )

  if shock is not None and shock.status is MocFreeBoundaryShockStatus.UPSTREAM_FIELD_FAILURE:
    diagnostics['sampled_count'] = len(shock.upstream_states)
    diagnostics['first_missing_sample_index'] = len(shock.upstream_states)
    last_valid = shock.upstream_states[-1] if shock.upstream_states else None
    diagnostics['last_valid_point_m'] = (
      None if last_valid is None else (last_valid.x_m, last_valid.y_m)
    )
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.UPSTREAM_FIELD_BOUNDARY,
      message=(
        'ambient-pressure field-coupled shock left the bounded upstream field; '
        'no extrapolation or physical endpoint was inferred'
      ),
      diagnostics=diagnostics,
    )

  if result.status in (
    MocAmbientClosureStatus.BOUNDARY_BRACKET_FAILURE,
    MocAmbientClosureStatus.AMBIENT_BOUNDARY_FAILURE,
    MocAmbientClosureStatus.SHOOTING_FAILURE,
  ):
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE,
      message=(
        'ambient-pressure shooting did not close the next cell boundary; '
        'the candidate remains a research stop'
      ),
      diagnostics=diagnostics,
    )
  if (
    result.converged
    and result.physical_closure_verified
    and result.upstream_coupling_verified
  ):
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=MocChainTerminationReason.STATE_NOT_CARRIED,
      message=(
        'ambient-pressure closure reported acceptance but its field could not '
        'be used as an exact state-carrying next cell'
      ),
      diagnostics=diagnostics,
    )
  return MocChainTerminationDecision(
    physical_termination=False,
    reason=MocChainTerminationReason.SOLVER_ERROR,
    message=(
      'ambient-pressure field-coupled shock solver did not produce a complete '
      'next cell; no physical endpoint was inferred'
    ),
    diagnostics=diagnostics,
  )
####


def solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure(
  current_cell: MocChainCell,
  next_cell_index: int,
  incoming_handoff: Sequence[MocChainBoundarySample],
  upstream_state_at: Callable[[tuple[float, float]], CharacteristicState | None],
  upstream_pressure_at: Callable[[tuple[float, float]], float | None],
  start_point_m: tuple[float, float],
  end_x_m: float,
  ambient_pressure_Pa: float,
  outer_downstream_flow_angle_lower_rad: float,
  outer_downstream_flow_angle_upper_rad: float,
  *,
  target_centerline_y_m: float = 0.0,
  target_centerline_flow_angle_rad: float = 0.0,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  closure_tolerance: float = 1.0e-8,
  pressure_tolerance: float = 1.0e-8,
  tangent_tolerance: float = 1.0e-8,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  maximum_shooting_iterations: int = 40,
) -> MocPostShockChainCellSolve:
  """Strictly return an accepted ambient-pressure-conditioned chain cell."""

  solved = solve_marched_attached_shock_chain_cell_with_ambient_pressure_closure_or_termination(
    current_cell,
    next_cell_index,
    incoming_handoff,
    upstream_state_at,
    upstream_pressure_at,
    start_point_m,
    end_x_m,
    ambient_pressure_Pa,
    outer_downstream_flow_angle_lower_rad,
    outer_downstream_flow_angle_upper_rad,
    target_centerline_y_m=target_centerline_y_m,
    target_centerline_flow_angle_rad=target_centerline_flow_angle_rad,
    sample_count=sample_count,
    branch=branch,
    position_tolerance_m=position_tolerance_m,
    invariant_tolerance=invariant_tolerance,
    closure_tolerance=closure_tolerance,
    pressure_tolerance=pressure_tolerance,
    tangent_tolerance=tangent_tolerance,
    shock_angle_tolerance_rad=shock_angle_tolerance_rad,
    maximum_segment_iterations=maximum_segment_iterations,
    maximum_shooting_iterations=maximum_shooting_iterations,
  )
  if isinstance(solved, MocChainTerminationDecision):
    raise ValueError(solved.message)
  return solved
####
