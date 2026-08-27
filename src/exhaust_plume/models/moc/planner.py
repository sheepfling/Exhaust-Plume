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
  MocCellClosureStatus,
  MocCellContinuationSolver,
  MocChainGeometryFidelity,
  continue_moc_cell_chain,
)
from exhaust_plume.models.moc.caustic_restart import MocCausticFamilyBandResult
from exhaust_plume.models.moc.post_shock import (
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldContinuationSolver,
  assemble_post_shock_characteristic_field,
  continue_post_shock_characteristic_chain,
  fit_attached_shock_boundary,
)
from exhaust_plume.models.moc.primitives import CharacteristicFamily, CharacteristicState
from exhaust_plume.models.moc.terminal_patch import MocTerminalReflectionPatchResult
from exhaust_plume.models.moc.terminal_patch_solver import (
  solve_marched_attached_shock_chain_cell_from_terminal_reflection_patch_or_termination,
)
from exhaust_plume.models.moc.free_boundary import (
  solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination,
)
from exhaust_plume.models.moc.family_band_solver import (
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination,
  solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch

__all__ = (
  'MocChainPlannerKind',
  'MocChainPlannerStep',
  'MocChainPlannerResult',
  'MocPrescribedPostShockChainMock',
  'plan_moc_chain',
  'plan_post_shock_characteristic_chain',
  'plan_post_shock_field_chain',
  'plan_prescribed_post_shock_chain_mock',
  'plan_terminal_reflection_patch_chain',
  'plan_caustic_family_band_chain',
  'plan_caustic_family_band_invariant_chain',
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
  result_kind: str = 'not-recorded'
  result_status: str | None = None
  result_end_x_m: float | None = None
  result_geometry_fidelity: MocChainGeometryFidelity | None = None
  result_physical_closure: MocCellClosureStatus | None = None
  result_termination_reason: MocChainTerminationReason | None = None
  result_physical_termination: bool | None = None

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
    if not isinstance(self.result_kind, str) or not self.result_kind:
      raise ValueError('result_kind must be a non-empty string')
    if self.result_status is not None and not isinstance(self.result_status, str):
      raise TypeError('result_status must be a string or None')
    if self.result_end_x_m is not None and not isfinite(float(self.result_end_x_m)):
      raise ValueError('result_end_x_m must be finite when supplied')
    if self.result_geometry_fidelity is not None and not isinstance(
        self.result_geometry_fidelity,
        MocChainGeometryFidelity,
    ):
      raise TypeError(
        'result_geometry_fidelity must be a MocChainGeometryFidelity or None'
      )
    if self.result_physical_closure is not None and not isinstance(
        self.result_physical_closure,
        MocCellClosureStatus,
    ):
      raise TypeError(
        'result_physical_closure must be a MocCellClosureStatus or None'
      )
    if self.result_termination_reason is not None and not isinstance(
        self.result_termination_reason,
        MocChainTerminationReason,
    ):
      raise TypeError(
        'result_termination_reason must be a MocChainTerminationReason or None'
      )
    if self.result_physical_termination is not None and not isinstance(
        self.result_physical_termination,
        bool,
    ):
      raise TypeError('result_physical_termination must be a bool or None')
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
      'result_kind': self.result_kind,
      'result_status': self.result_status,
      'result_end_x_m': self.result_end_x_m,
      'result_geometry_fidelity': (
        None
        if self.result_geometry_fidelity is None
        else self.result_geometry_fidelity.value
      ),
      'result_physical_closure': (
        None
        if self.result_physical_closure is None
        else self.result_physical_closure.value
      ),
      'result_termination_reason': (
        None
        if self.result_termination_reason is None
        else self.result_termination_reason.value
      ),
      'result_physical_termination': self.result_physical_termination,
    }
  ####

  def with_solver_result(self, result: object) -> 'MocChainPlannerStep':
    """Attach the typed result returned for this planned handoff."""

    if isinstance(result, MocChainTerminationDecision):
      return replace(
        self,
        result_kind='termination-returned',
        result_status=result.reason.value,
        result_termination_reason=result.reason,
        result_physical_termination=result.physical_termination,
      )
    if isinstance(result, MocPostShockChainCellSolve):
      return replace(
        self,
        result_kind='field-solve-returned',
        result_status=result.field.status.value,
        result_end_x_m=result.end_x_m,
      )
    if isinstance(result, MocChainCell):
      return replace(
        self,
        result_kind='cell-returned',
        result_status='resolved' if result.resolved else 'unresolved',
        result_end_x_m=result.end_x_m,
        result_geometry_fidelity=result.geometry_fidelity,
        result_physical_closure=result.physical_closure,
      )
    if result is None:
      return replace(
        self,
        result_kind='no-cell-returned',
        result_status='none',
      )
    return replace(
      self,
      result_kind='invalid-result-returned',
      result_status=type(result).__name__,
    )
  ####

  def with_solver_error(self, error: BaseException) -> 'MocChainPlannerStep':
    """Record a callback exception before the chain converts it to failure."""

    return replace(
      self,
      result_kind='solver-error',
      result_status=type(error).__name__,
    )
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
  # The default line is tangent to a weak attached shock for M=2, gamma=1.4.
  # It is deliberately still prescribed geometry, but the local fit below now
  # proves that it is compatible with the requested attached-shock branch
  # before the field is assembled.  The varying downstream angles keep the
  # characteristic mesh nondegenerate.
  shock_ordinates_m: tuple[float, ...] = (
    0.08237108456402913,
    0.06177831342302184,
    0.04118554228201456,
    0.020592771141007285,
    0.0,
  )
  downstream_flow_angles_rad: tuple[float, ...] = (-0.16, -0.12, -0.08, -0.04, 0.0)
  upstream_flow_angle_start_rad: float = -0.22316537247754467
  upstream_flow_angle_step_rad: float = 0.01953284223794056
  upstream_flow_angles_rad: tuple[float, ...] = (
    -0.22316537247754467,
    -0.204175961115758,
    -0.18482733549527713,
    -0.16511536988179235,
    -0.14503421352578244,
  )
  mach: float = 2.0
  gamma: float = 1.4
  pressure_loss_ratio: float | None = None

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
    if self.pressure_loss_ratio is not None and (
      not isfinite(float(self.pressure_loss_ratio))
      or not 0.0 < self.pressure_loss_ratio < 1.0
    ):
      raise ValueError(
        'pressure_loss_ratio must be finite and strictly between zero and one '
        'when supplied'
      )
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
    try:
      configured_upstream_angles = (
        tuple(float(value) for value in self.upstream_flow_angles_rad)
        if self.upstream_flow_angles_rad is not None
        else tuple(
          float(self.upstream_flow_angle_start_rad)
          + float(self.upstream_flow_angle_step_rad) * index
          for index in range(len(downstream_angles))
        )
      )
    except (TypeError, ValueError) as error:
      raise ValueError('upstream_flow_angles_rad must be a numeric sequence') from error
    if len(configured_upstream_angles) != len(downstream_angles):
      raise ValueError(
        'upstream_flow_angles_rad must match the downstream angle sample count'
      )
    if any(not isfinite(value) for value in configured_upstream_angles):
      raise ValueError('upstream flow angles must be finite')
    object.__setattr__(self, 'shock_ordinates_m', ordinates)
    object.__setattr__(self, 'downstream_flow_angles_rad', downstream_angles)
    object.__setattr__(self, 'upstream_flow_angles_rad', configured_upstream_angles)

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
      'upstream_flow_angles_rad': self.upstream_flow_angles_rad,
      'mach': self.mach,
      'gamma': self.gamma,
      'pressure_loss_ratio': self.pressure_loss_ratio,
      'pressure_loss_ratio_role': (
        'optional expected total-pressure ratio; never used to fabricate '
        'post-shock states'
      ),
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
    shock_start_x_m = current.end_x_m + self.shock_start_offset_m
    shock_points = tuple(
      (shock_start_x_m + self.shock_sample_spacing_m * index, ordinate)
      for index, ordinate in enumerate(self.shock_ordinates_m)
    )
    upstream_angles = self.upstream_flow_angles_rad
    if upstream_angles is None:
      raise ValueError('upstream_flow_angles_rad was not normalized by the fixture')
    upstream_states = tuple(
      CharacteristicState(
        x_m=point[0],
        y_m=point[1],
        theta_rad=upstream_angles[index],
        mach=self.mach,
        gamma=self.gamma,
      )
      for index, point in enumerate(shock_points)
    )
    upstream_static_pressure_Pa = upstream_total_pressure_Pa / (
      1.0 + 0.5 * (self.gamma - 1.0) * self.mach**2
    ) ** (self.gamma / (self.gamma - 1.0))
    fit = fit_attached_shock_boundary(
      upstream_states,
      (upstream_static_pressure_Pa,) * self.sample_count,
      shock_points,
      self.downstream_flow_angles_rad,
      branch=ShockBranch.WEAK,
    )
    if not fit.converged:
      raise ValueError(
        'prescribed post-shock chain planner mock rejected its shock geometry '
        f'with the local attached-shock fit: {fit.message}'
      )
    # Use the solver-backed fit as the source of truth for the characteristic
    # field.  This prevents the mock from silently fabricating zero residuals
    # or a total-pressure loss across a cell.
    if any(
      abs(angle - fitted.state.theta_rad) > 1.0e-12
      for angle, fitted in zip(
        self.downstream_flow_angles_rad,
        fit.boundary_states,
        strict=True,
      )
    ):
      raise ValueError(
        'prescribed post-shock chain planner mock fit changed its requested '
        'downstream flow angles'
      )
    if self.pressure_loss_ratio is not None:
      fitted_pressure_ratios = tuple(
        sample.downstream_total_pressure_Pa / sample.upstream_total_pressure_Pa
        for sample in fit.boundary_states
      )
      if any(
        abs(ratio - self.pressure_loss_ratio) > 1.0e-8
        for ratio in fitted_pressure_ratios
      ):
        raise ValueError(
          'prescribed pressure_loss_ratio disagrees with the attached-shock '
          'fit; omit it to accept solver-computed pressure loss'
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
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      current.continuation_boundary,
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

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


def plan_caustic_family_band_chain(
  seed: MocChainCell,
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
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan one caustic-band-to-shock handoff through the chain audit.

  The caustic band is a finite upstream field for one next-shock solve.  Its
  current solver result ends at an open mixed-regime boundary, so a successful
  attempt produces an explicit non-physical ``OPEN_PHYSICAL_CLOSURE`` stop.
  The planner never reuses that band for a second cell and never promotes the
  open terminal field as a resolved chain cell.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
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
          'caustic-family band planner completed its one-step upstream '
          'domain; a later cell requires a new family or post-shock field'
        ),
        diagnostics={
          'termination_model': 'caustic-family-band-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
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
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'caustic-family-band-next-shock-planner; '
      'open-mixed-regime-closure-and-external-validation-pending'
    ),
  )
####


def plan_caustic_family_band_invariant_chain(
  seed: MocChainCell,
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
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan an invariant-conditioned caustic shock-chain continuation.

  The planner records the exact prior handoff and permits at most the finite
  family-band domain to be consumed.  Its provenance is always
  ``UPSTREAM_COUPLED_RESEARCH`` and its production claim remains disabled,
  even if a future remeshed band allows the local field to converge.
  """

  if not isinstance(band, MocCausticFamilyBandResult):
    raise TypeError('band must be a MocCausticFamilyBandResult')
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
          'invariant-conditioned caustic-band planner consumed its one-step '
          'upstream domain; a later cell requires a new upstream field'
        ),
        diagnostics={
          'termination_model': 'invariant-caustic-band-one-step-domain',
          'next_cell_index': next_cell_index,
        },
      )
    attempted = True
    solved = solve_marched_attached_shock_chain_cell_from_caustic_family_band_with_invariant_boundary_or_termination(
      current,
      next_cell_index,
      current.continuation_boundary,
      band,
      start_point_m=start_point_m,
      end_x_m=end_x_m,
      downstream_invariant_family=downstream_invariant_family,
      downstream_invariant_at=downstream_invariant_at,
      target_centerline_y_m=target_centerline_y_m,
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
    if isinstance(solved, MocChainTerminationDecision):
      return solved
    return solved.field.as_coupled_chain_cell(
      start_x_m=current.end_x_m,
      end_x_m=solved.end_x_m,
      cell_index=next_cell_index,
    )

  effective_policy = policy
  if effective_policy is None:
    effective_policy = MocChainContinuationPolicy(require_state_carry=True)
  elif not effective_policy.require_state_carry:
    effective_policy = replace(effective_policy, require_state_carry=True)
  return plan_moc_chain(
    seed,
    solve_next,
    policy=effective_policy,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'invariant-conditioned-caustic-band-shock-planner; '
      'one-sided-upstream-domain-and-physical-remesh-pending'
    ),
  )


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
    step = MocChainPlannerStep.from_boundary(
      current,
      next_cell_index,
      incoming_handoff,
    )
    steps.append(step)
    try:
      result = solve_next(current, next_cell_index, incoming_handoff)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      steps[-1] = step.with_solver_error(error)
      raise
    steps[-1] = step.with_solver_result(result)
    return result

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


def plan_post_shock_field_chain(
  seed: MocPostShockCharacteristicFieldResult,
  *,
  start_x_m: float,
  end_x_m: float,
  start_point_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    tuple[float, float],
  ],
  end_x_at: Callable[
    [MocPostShockCharacteristicFieldResult, MocChainCell, int],
    float,
  ] | None = None,
  target_centerline_y_m: float = 0.0,
  downstream_flow_angle_at: Callable[[int, tuple[float, float]], float] | None = None,
  downstream_flow_angle_rad: float | None = None,
  sample_count: int = 17,
  branch: ShockBranch = ShockBranch.WEAK,
  position_tolerance_m: float = 1.0e-10,
  invariant_tolerance: float = 1.0e-10,
  shock_angle_tolerance_rad: float = 1.0e-2,
  maximum_segment_iterations: int = 24,
  policy: MocChainContinuationPolicy | None = None,
) -> MocChainPlannerResult:
  """Plan a chain whose next shock consumes the prior solved field.

  ``start_point_at`` chooses each new shock start from the current field and
  cell.  The default endpoint advances by the initial seed-cell axial length;
  ``end_x_at`` may supply a different solver-owned endpoint.  The prior field
  is replaced only after a complete field-coupled next-cell solve returns, so
  an upstream-domain miss or typed terminal cannot be converted into a
  prescribed planner cell.

  This is an upstream-coupled research planner.  It is not the prescribed
  boundary mock and remains below the production claim ceiling until the
  downstream boundary and external validation gates are complete.
  """

  if not isinstance(seed, MocPostShockCharacteristicFieldResult):
    raise TypeError('seed must be a MocPostShockCharacteristicFieldResult')
  if not callable(start_point_at):
    raise TypeError('start_point_at must be callable')
  if end_x_at is not None and not callable(end_x_at):
    raise TypeError('end_x_at must be callable when supplied')
  if (downstream_flow_angle_at is None) == (downstream_flow_angle_rad is None):
    raise ValueError('supply exactly one downstream flow-angle provider')
  if not isfinite(float(start_x_m)) or not isfinite(float(end_x_m)):
    raise ValueError('start_x_m and end_x_m must be finite')
  if end_x_m <= start_x_m:
    raise ValueError('end_x_m must be strictly downstream of start_x_m')
  cell_axial_length_m = float(end_x_m) - float(start_x_m)
  current_field = seed

  def solve_next(
    current: MocChainCell,
    next_cell_index: int,
    incoming_handoff: tuple[MocChainBoundarySample, ...],
  ) -> MocPostShockChainCellSolve | MocChainTerminationDecision:
    nonlocal current_field
    start_point = start_point_at(current_field, current, next_cell_index)
    next_end_x = (
      end_x_at(current_field, current, next_cell_index)
      if end_x_at is not None
      else current.end_x_m + cell_axial_length_m
    )
    solved = solve_marched_attached_shock_chain_cell_from_post_shock_field_or_termination(
      current,
      next_cell_index,
      incoming_handoff,
      current_field,
      start_point_m=start_point,
      end_x_m=next_end_x,
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
    if isinstance(solved, MocPostShockChainCellSolve):
      current_field = solved.field
    return solved

  return plan_post_shock_characteristic_chain(
    seed,
    solve_next,
    start_x_m=start_x_m,
    end_x_m=end_x_m,
    policy=policy,
    require_upstream_shock_coupling=True,
    planner_kind=MocChainPlannerKind.UPSTREAM_COUPLED_RESEARCH,
    claim_status=(
      'bounded-post-shock-field-coupled-planner; '
      'production-shock-boundary-and-external-validation-pending'
    ),
  )
####
