"""Planning and audit wrappers for the isolated planar-MOC chain lane.

The chain solvers own numerical acceptance.  This module owns the lightweight
planner view used by validation and research orchestration: it records every
incoming handoff before a callback is invoked and preserves the solver's
typed termination decision.  The prescribed-boundary mode is an executable
mock only; it cannot raise a cell's fidelity or closure claim.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainBoundaryKind,
  MocChainBoundarySample,
  MocChainCell,
  MocChainContinuationPolicy,
  MocChainResult,
  MocChainTerminationDecision,
  MocCellContinuationSolver,
  continue_moc_cell_chain,
)
from exhaust_plume.models.moc.post_shock import (
  MocPostShockChainCellSolve,
  MocPostShockCharacteristicFieldResult,
  MocPostShockFieldContinuationSolver,
  continue_post_shock_characteristic_chain,
)

__all__ = (
  'MocChainPlannerKind',
  'MocChainPlannerStep',
  'MocChainPlannerResult',
  'plan_moc_chain',
  'plan_post_shock_characteristic_chain',
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
    }
  ####


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
