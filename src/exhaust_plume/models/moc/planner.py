"""Planning and audit wrappers for the isolated planar-MOC chain lane.

The chain solvers own numerical acceptance.  This module owns the lightweight
planner view used by validation and research orchestration: it records every
incoming handoff before a callback is invoked and preserves the solver's
typed termination decision.  The prescribed-boundary mode is an executable
mock only; it cannot raise a cell's fidelity or closure claim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from hashlib import sha256
from math import isfinite
from types import MappingProxyType
from typing import Any, Callable

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainResult,
  MocChainTerminationDecision,
  MocChainTerminationReason,
  MocCellContinuationSolver,
  continue_moc_cell_chain,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockBoundaryState,
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldContinuationSolver,
  MocShockBoundaryFitResult,
  MocShockBoundaryFitStatus,
  assemble_post_shock_characteristic_field,
  continue_post_shock_characteristic_chain,
)
from exhaust_plume.models.moc.primitives import CharacteristicState
from exhaust_plume.models.moc.terminal_patch import MocTerminalReflectionPatchResult
from exhaust_plume.models.moc.terminal_patch_solver import (
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocChainPlannerKind',
  'MocChainPlannerStep',
  'MocChainPlannerResult',
  'MocPrescribedPostShockChainMock',
  'plan_moc_chain',
  'plan_post_shock_characteristic_chain',
  'plan_prescribed_post_shock_chain_mock',
  'plan_terminal_reflection_patch_chain',
)


class MocChainPlannerKind(str, Enum):
  """Provenance label for a planner run."""

  PRESCRIBED_BOUNDARY_MOCK = 'prescribed-boundary-mock'
  SOLVER_GENERATED_REFERENCE = 'solver-generated-reference'
  UPSTREAM_COUPLED_RESEARCH = 'upstream-coupled-research'
####


@dataclass(frozen=True, slots=True)
class MocChainPlannerStep:
  """One callback invocation and the exact handoff it was given."""

  current_cell_index: int
  next_cell_index: int
  current_end_x_m: float
  boundary_kind: MocChainBoundaryKind | None
  incoming_handoff_sample_count: int
  incoming_total_pressure_range_Pa: tuple[float, float] | None
  incoming_handoff_fingerprint: str | None = None

  def __post_init__(self) -> None:
    if isinstance(self.current_cell_index, bool) or self.current_cell_index < 1:
      raise ValueError('current_cell_index must be a positive integer')
    if isinstance(self.next_cell_index, bool) or self.next_cell_index != self.current_cell_index + 1:
      raise ValueError('next_cell_index must immediately follow current_cell_index')
    if not isfinite(float(self.current_end_x_m)):
      raise ValueError('current_end_x_m must be finite')
    if self.boundary_kind is not None and not isinstance(
        self.boundary_kind,
        MocChainBoundaryKind,
    ):
      raise TypeError('boundary_kind must be a MocChainBoundaryKind or None')
    if isinstance(self.incoming_handoff_sample_count, bool) or self.incoming_handoff_sample_count < 0:
      raise ValueError('incoming_handoff_sample_count must be nonnegative')
    pressure_range = self.incoming_total_pressure_range_Pa
    if pressure_range is not None:
      if len(pressure_range) != 2:
        raise ValueError('incoming_total_pressure_range_Pa must contain two values')
      minimum, maximum = (float(value) for value in pressure_range)
      if (
        not isfinite(minimum)
        or not isfinite(maximum)
        or minimum <= 0.0
        or maximum < minimum
      ):
        raise ValueError('incoming total-pressure range must be finite and ordered')
      object.__setattr__(self, 'incoming_total_pressure_range_Pa', (minimum, maximum))
  ####

  @classmethod
  def from_boundary(
    cls,
    current: MocChainCell,
    next_cell_index: int,
    boundary: tuple[MocChainBoundarySample, ...],
  ) -> 'MocChainPlannerStep':
    pressure_range = None
    if boundary:
      pressures = tuple(sample.total_pressure_Pa for sample in boundary)
      pressure_range = (min(pressures), max(pressures))
    return cls(
      current_cell_index=current.cell_index,
      next_cell_index=next_cell_index,
      current_end_x_m=current.end_x_m,
      boundary_kind=(
        current.continuation_boundary_kind if boundary else None
      ),
      incoming_handoff_sample_count=len(boundary),
      incoming_total_pressure_range_Pa=pressure_range,
      incoming_handoff_fingerprint=_handoff_fingerprint(boundary),
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'current_cell_index': self.current_cell_index,
      'next_cell_index': self.next_cell_index,
      'current_end_x_m': self.current_end_x_m,
      'boundary_kind': None if self.boundary_kind is None else self.boundary_kind.value,
      'incoming_handoff_sample_count': self.incoming_handoff_sample_count,
      'incoming_total_pressure_range_Pa': self.incoming_total_pressure_range_Pa,
      'incoming_handoff_fingerprint': self.incoming_handoff_fingerprint,
    }
  ####


def _handoff_fingerprint(
  boundary: tuple[MocChainBoundarySample, ...],
) -> str | None:
  """Return a deterministic audit fingerprint for an exact typed handoff.

  The digest is provenance bookkeeping, not a physical validation result.  It
  lets a serialized planner report identify the full state/pressure boundary
  that was presented to a callback without duplicating every sample in the
  report.  ``float.hex`` keeps the representation deterministic across JSON
  serialization and preserves signed zero when it is present.
  """

  if not boundary:
    return None
  payload = '\n'.join(
    '|'.join(
      (
        state_value.hex()
        for state_value in (
          sample.state.x_m,
          sample.state.y_m,
          sample.state.theta_rad,
          sample.state.mach,
          sample.state.gamma,
          sample.total_pressure_Pa,
        )
      )
    )
    for sample in boundary
  )
  return sha256(payload.encode('ascii')).hexdigest()


@dataclass(frozen=True, slots=True)
class MocChainPlannerResult:
  """A chain result plus planner provenance and callback audit steps."""

  chain: MocChainResult
  planner_kind: MocChainPlannerKind
  steps: tuple[MocChainPlannerStep, ...] = ()
  claim_status: str = ''
  diagnostics: dict[str, Any] | MappingProxyType = MappingProxyType({})

  def __post_init__(self) -> None:
    if not isinstance(self.chain, MocChainResult):
      raise TypeError('chain must be a MocChainResult')
    if not isinstance(self.planner_kind, MocChainPlannerKind):
      raise TypeError('planner_kind must be a MocChainPlannerKind')
    steps = tuple(self.steps)
    if any(not isinstance(step, MocChainPlannerStep) for step in steps):
      raise TypeError('steps must contain MocChainPlannerStep values')
    object.__setattr__(self, 'steps', steps)
    object.__setattr__(self, 'claim_status', str(self.claim_status))
    object.__setattr__(self, 'diagnostics', MappingProxyType(dict(self.diagnostics)))
  ####

  @property
  def resolved(self) -> bool:
    return self.chain.resolved
  ####

  @property
  def physical_termination(self) -> bool:
    return self.chain.physical_termination
  ####

  @property
  def production_claim_allowed(self) -> bool:
    """Whether this planner provenance may be called production evidence."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'planner_kind': self.planner_kind.value,
      'planning_only': True,
      'production_claim_allowed': self.production_claim_allowed,
      'claim_status': self.claim_status,
      'step_count': len(self.steps),
      'steps': [step.as_report() for step in self.steps],
      'chain': self.chain.as_report(),
      'diagnostics': dict(self.diagnostics),
    }
  ####


@dataclass(frozen=True, slots=True)
class MocPrescribedPostShockChainMock:
  """Deterministic continued-cell fixture for planner and report validation.

  This fixture supplies a prescribed next-shock curve and therefore is not a
  free-boundary MOC solver.  It exists so the state-carrying planner contract
  can be exercised over more than one cell without making synthetic geometry
  eligible for a production plume claim.
  """

  total_cell_count: int = 3
  cell_axial_length_m: float = 0.50
  shock_start_offset_m: float = 0.20
  shock_sample_spacing_m: float = 0.02
  shock_ordinates_m: tuple[float, ...] = (0.20, 0.14, 0.08, 0.04, 0.0)
  downstream_flow_angles_rad: tuple[float, ...] = (-0.30, -0.20, -0.10, -0.05, 0.0)
  upstream_flow_angle_start_rad: float = -0.35
  upstream_flow_angle_step_rad: float = 0.08
  mach: float = 2.0
  gamma: float = 1.4
  pressure_loss_ratio: float = 8.0 / 9.0

  def __post_init__(self) -> None:
    if (
      isinstance(self.total_cell_count, bool)
      or not isinstance(self.total_cell_count, int)
      or self.total_cell_count < 1
    ):
      raise ValueError('total_cell_count must be a positive integer')
    for name, value in (
      ('cell_axial_length_m', self.cell_axial_length_m),
      ('shock_start_offset_m', self.shock_start_offset_m),
      ('shock_sample_spacing_m', self.shock_sample_spacing_m),
    ):
      if not isfinite(float(value)) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
    for name, value, lower_bound in (
      ('mach', self.mach, 1.0),
      ('gamma', self.gamma, 1.0),
    ):
      if not isfinite(float(value)) or value <= lower_bound:
        raise ValueError(f'{name} must be finite and greater than {lower_bound}')
    if (
      not isfinite(float(self.pressure_loss_ratio))
      or not 0.0 < self.pressure_loss_ratio < 1.0
    ):
      raise ValueError('pressure_loss_ratio must be finite and strictly between zero and one')
    try:
      ordinates = tuple(float(value) for value in self.shock_ordinates_m)
      downstream_angles = tuple(float(value) for value in self.downstream_flow_angles_rad)
    except (TypeError, ValueError) as error:
      raise ValueError('shock ordinates and downstream angles must be numeric sequences') from error
    if len(ordinates) < 3 or len(ordinates) != len(downstream_angles):
      raise ValueError(
        'shock ordinates and downstream angles must have equal lengths of at least three'
      )
    if any(not isfinite(value) or value < 0.0 for value in ordinates):
      raise ValueError('shock ordinates must be finite and nonnegative')
    if any(next_value > value for value, next_value in zip(ordinates, ordinates[1:])):
      raise ValueError('shock ordinates must be nonincreasing toward the centerline')
    if abs(ordinates[-1]) > 1.0e-12:
      raise ValueError('the final prescribed shock ordinate must be the centerline')
    if any(not isfinite(value) for value in downstream_angles):
      raise ValueError('downstream flow angles must be finite')
    if abs(downstream_angles[-1]) > 1.0e-12:
      raise ValueError('the final prescribed downstream flow angle must be zero')
    for name, value in (
      ('upstream_flow_angle_start_rad', self.upstream_flow_angle_start_rad),
      ('upstream_flow_angle_step_rad', self.upstream_flow_angle_step_rad),
    ):
      if not isfinite(float(value)):
        raise ValueError(f'{name} must be finite')
    object.__setattr__(self, 'shock_ordinates_m', ordinates)
    object.__setattr__(self, 'downstream_flow_angles_rad', downstream_angles)

  @property
  def sample_count(self) -> int:
    """Number of prescribed samples on each mock shock boundary."""

    return len(self.shock_ordinates_m)

  def as_report(self) -> dict[str, Any]:
    """Return explicit provenance and configuration for the fixture."""

    return {
      'model': 'prescribed-post-shock-chain-planner-mock',
      'planning_only': True,
      'production_claim_allowed': False,
      'total_cell_count_including_seed': self.total_cell_count,
      'cell_axial_length_m': self.cell_axial_length_m,
      'shock_start_offset_m': self.shock_start_offset_m,
      'shock_sample_spacing_m': self.shock_sample_spacing_m,
      'shock_ordinates_m': self.shock_ordinates_m,
      'downstream_flow_angles_rad': self.downstream_flow_angles_rad,
      'upstream_flow_angle_start_rad': self.upstream_flow_angle_start_rad,
      'upstream_flow_angle_step_rad': self.upstream_flow_angle_step_rad,
      'mach': self.mach,
      'gamma': self.gamma,
      'pressure_loss_ratio': self.pressure_loss_ratio,
      'claim_status': (
        'prescribed-next-shock-geometry-fixture; '
        'not-free-boundary-chain-evidence'
      ),
    }

  def solve_next(
    self,
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    """Return one deterministic mock cell or an explicit fixture stop."""

    if not isinstance(current, MocChainCell):
      raise TypeError('current must be a MocChainCell')
    if isinstance(next_cell_index, bool) or next_cell_index != current.cell_index + 1:
      raise ValueError('next_cell_index must immediately follow current.cell_index')
    handoff = tuple(incoming_handoff)
    if any(not isinstance(sample, MocChainBoundarySample) for sample in handoff):
      raise TypeError('incoming_handoff must contain MocChainBoundarySample values')
    if len(handoff) < 3:
      raise ValueError('incoming_handoff requires at least three state samples')
    if handoff != current.continuation_boundary:
      raise ValueError('incoming_handoff must exactly match current.continuation_boundary')
    if next_cell_index > self.total_cell_count:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'prescribed post-shock chain planner mock exhausted its configured '
          f'{self.total_cell_count}-cell fixture'
        ),
      )
    upstream_total_pressure_Pa = max(
      sample.total_pressure_Pa for sample in handoff
    )
    downstream_total_pressure_Pa = (
      self.pressure_loss_ratio * upstream_total_pressure_Pa
    )
    shock_start_x_m = current.end_x_m + self.shock_start_offset_m
    shock_points = tuple(
      (shock_start_x_m + self.shock_sample_spacing_m * index, ordinate)
      for index, ordinate in enumerate(self.shock_ordinates_m)
    )
    boundary_states = tuple(
      MocPostShockBoundaryState(
        point_m=point,
        state=CharacteristicState(
          x_m=point[0],
          y_m=point[1],
          theta_rad=angle,
          mach=self.mach,
          gamma=self.gamma,
        ),
        upstream_total_pressure_Pa=upstream_total_pressure_Pa,
        downstream_total_pressure_Pa=downstream_total_pressure_Pa,
      )
      for point, angle in zip(
        shock_points,
        self.downstream_flow_angles_rad,
        strict=True,
      )
    )
    upstream_states = tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=(
          self.upstream_flow_angle_start_rad
          + self.upstream_flow_angle_step_rad * index
        ),
        mach=self.mach,
        gamma=self.gamma,
      )
      for index, point in enumerate(shock_points)
    )
    fit = MocShockBoundaryFitResult(
      status=MocShockBoundaryFitStatus.CONVERGED_FITTED,
      boundary_states=boundary_states,
      shock_angle_residuals_rad=(0.0,) * self.sample_count,
      maximum_shock_angle_residual_rad=0.0,
      upstream_states=upstream_states,
      upstream_total_pressure_Pa=(upstream_total_pressure_Pa,) * self.sample_count,
    )
    field = assemble_post_shock_characteristic_field(
      fit,
      incoming_handoff=handoff,
    )
    if not field.converged:
      raise ValueError(
        'prescribed post-shock chain planner mock produced a non-converged '
        f'field: {field.message}'
      )
    return MocPostShockChainCellSolve(
      field=field,
      end_x_m=current.end_x_m + self.cell_axial_length_m,
    )


def plan_prescribed_post_shock_chain_mock(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  mock: MocPrescribedPostShockChainMock | None = None,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Run the reusable planning-only prescribed post-shock chain fixture."""

  fixture = MocPrescribedPostShockChainMock() if mock is None else mock
  if not isinstance(fixture, MocPrescribedPostShockChainMock):
    raise TypeError('mock must be a MocPrescribedPostShockChainMock')
  planner = plan_post_shock_characteristic_chain(
    seed,
    fixture.solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    planner_kind=MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK,
  )
  return replace(
    planner,
    diagnostics={
      'prescribed_chain_mock': fixture.as_report(),
    },
  )
####


def _default_claim_status(kind: MocChainPlannerKind) -> str:
  return {
    MocChainPlannerKind.PRESCRIBED_BOUNDARY_MOCK: (
      'deterministic-prescribed-next-shock-planner-mock; not-free-boundary-chain-evidence'
    ),
    MocChainPlannerKind.SOLVER_GENERATED_REFERENCE: (
      'solver-generated-chain-reference; physical-free-boundary-validation-pending'
    ),
    MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH: (
      'upstream-coupled-research-chain; external-validation-and-product-promotion-pending'
    ),
  }[kind]
####


def plan_moc_chain(
  seed: MocChainCell,
  solve_next: MocCellContinuationSolver,
  *,
  policy: MocChainContinuationPolicy | None = None,
  planner_kind: MocChainPlannerKind = MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Run the generic chain contract while recording every planned handoff."""

  steps: list[MocChainPlannerStep] = []

  def wrapped(current: MocChainCell, next_cell_index: int):
    steps.append(
      MocChainPlannerStep.from_boundary(
        current,
        next_cell_index,
        current.continuation_boundary,
      )
    )
    return solve_next(current, next_cell_index)

  chain = continue_moc_cell_chain(seed, wrapped, policy)
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=planner_kind,
    steps=tuple(steps),
    claim_status=(
      _default_claim_status(planner_kind)
      if claim_status is None
      else claim_status
    ),
  )
####


def plan_terminal_reflection_patch_chain(
  seed: MocChainCell,
  patch: MocTerminalReflectionPatchResult,
  *,
  start_point_m: tuple[float, float],
  end_x_m: float,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 2.0e-4,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one terminal-reflection handoff through the generic chain audit.

  A terminal reflection patch is a finite upstream domain for one next-shock
  solve, not a reusable downstream field for an arbitrary number of later
  cells.  This wrapper therefore allows the adapter to be invoked once and
  records any returned cell or typed termination through ``plan_moc_chain``.
  A second callback invocation receives an explicit non-physical solver stop
  rather than reusing the terminal patch outside its solved domain.
  """

  if not isinstance(patch, MocTerminalReflectionPatchResult):
    raise TypeError('patch must be a MocTerminalReflectionPatchResult')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  attempted = False

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
  ) -> MocChainCell | MocChainTerminationDecision:
    nonlocal attempted
    if attempted:
      return MocChainTerminationDecision(
        physical_termination=False,
        reason=MocChainTerminationReason.SOLVER_RETURNED_NO_NEXT_CELL,
        message=(
          'terminal reflection patch planner completed its one-step domain; '
          'a later cell requires a new upstream field and solver adapter'
        ),
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      patch,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      target_centerline_y_m=target_centerline_y_m,
      downstream_flow_angle_at=downstream_flow_angle_at,
      downstream_flow_angle_rad=downstream_flow_angle_rad,
      sample_count=sample_count,
      branch=branch,
      position_tolerance_m=position_tolerance_m,
      invariant_tolerance=invariant_tolerance,
      shock_angle_tolerance_rad=shock_angle_tolerance_rad,
      maximum_segment_iterations=maximum_segment_iterations,
    )
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  return plan_moc_chain(
    seed,
    solve_next,
    policy=policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'terminal-reflection-patch-planner-handoff; '
      'one-step-domain; mixed-regime-or-new-field-continuation-pending'
    ),
  )
####


def plan_post_shock_characteristic_chain(
  seed: MocPostShockCharacteristicFieldResult,
  solve_next: MocPostShockFieldContinuationSolver,
  *,
  start_x_m: float,
  end_x_m: float,
  policy: MocChainContinuationPolicy | None = None,
  require_upstream_shock_coupling: bool = False,
  planner_kind: MocChainPlannerKind = MocChainPlannerKind.SOLVER_GENERATED_REFERENCE,
  claim_status: str | None = None,
) -> MocChainPlannerResult:
  """Plan a state-carrying post-shock chain with exact handoff audit steps."""

  if planner_kind is MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH and not require_upstream_shock_coupling:
    raise ValueError(
      'upstream-coupled research planning requires '
      'require_upstream_shock_coupling=True'
    )
  steps: list[MocChainPlannerStep] = []

  def wrapped(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision | None:
    if incoming_handoff != current.continuation_boundary:
      raise ValueError('planner callback received a handoff different from the current cell')
    steps.append(
      MocChainPlannerStep.from_boundary(
        current,
        next_cell_index,
        incoming_handoff,
      )
    )
    return solve_next(current, next_cell_index, incoming_handoff)

  chain = continue_post_shock_characteristic_chain(
    seed,
    wrapped,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=require_upstream_shock_coupling,
  )
  return MocChainPlannerResult(
    chain=chain,
    planner_kind=planner_kind,
    steps=tuple(steps),
    claim_status=(
      _default_claim_status(planner_kind)
      if claim_status is None
      else claim_status
    ),
  )
####
