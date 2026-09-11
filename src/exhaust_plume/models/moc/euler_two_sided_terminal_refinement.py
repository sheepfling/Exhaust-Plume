"""Continuation-ladder evidence for the two-sided terminal Euler lane.

The local terminal field is a four-cell characteristic construction.  This
module extends its solver-owned frontier at several declared cycle counts so
that topology growth and residual behavior are measured explicitly.  The
extension is not a physical shock-cell fit and it does not turn a stable
continuation ladder into canonical free-boundary closure.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, Sequence

from exhaust_plume.models.moc.euler_entropy_characteristic_continuation import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_continuation,
)
from exhaust_plume.models.moc.euler_two_sided_terminal_closure import (
  MocEulerTwoSidedTerminalClosureResult,
)

__all__ = (
  'MocEulerTwoSidedTerminalRefinementStatus',
  'MocEulerTwoSidedTerminalRefinementRequest',
  'MocEulerTwoSidedTerminalRefinementResult',
  'refine_euler_two_sided_terminal_closure',
)


class MocEulerTwoSidedTerminalRefinementStatus(str, Enum):
  """Typed outcomes for the terminal continuation ladder."""

  CONVERGED_LOCAL_LADDER = 'converged_two_sided_terminal_local_ladder'
  INVALID_INPUT = 'invalid_input'
  TERMINAL_CLOSURE_REQUIRED = 'two_sided_terminal_refinement_closure_required'
  LEVEL_FAILURE = 'two_sided_terminal_refinement_level_failure'
  CONTINUATION_FAILURE = 'two_sided_terminal_refinement_continuation_failure'


def _positive_float(value: Any, name: str) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  ####
  return numeric
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedTerminalRefinementRequest:
  """Declared solver-owned continuation resolutions after terminal closure."""

  terminal_closure: MocEulerTwoSidedTerminalClosureResult
  cycle_counts: tuple[int, ...] = (2, 3, 4)
  position_tolerance_m: float = 1.0e-8
  characteristic_residual_tolerance: float = 1.0e-8
  pressure_lineage_tolerance: float = 1.0e-8
  cell_residual_tolerance: float = 1.0e-2
  refinement_tolerance: float = 1.0e-8
  maximum_iterations: int = 48

  def __post_init__(self) -> None:
    if not isinstance(
      self.terminal_closure,
      MocEulerTwoSidedTerminalClosureResult,
    ):
      raise TypeError(
        'terminal_closure must be a MocEulerTwoSidedTerminalClosureResult'
      )
    ####
    if not (
      self.terminal_closure.converged
      and self.terminal_closure.local_consistency_verified
      and self.terminal_closure.internal_field is not None
      and self.terminal_closure.chain_promotion_blocked
      and not self.terminal_closure.production_claim_allowed
    ):
      raise ValueError(
        'terminal refinement requires a locally consistent terminal closure '
        'with promotion blocked'
      )
    ####
    try:
      levels = tuple(self.cycle_counts)
    except TypeError as error:
      raise ValueError('cycle_counts must be an iterable of integers') from error
    ####
    if len(levels) < 2 or any(
      isinstance(value, bool) or not isinstance(value, int) or value < 1
      for value in levels
    ):
      raise ValueError('cycle_counts must contain at least two positive integers')
    ####
    if any(right <= left for left, right in zip(levels, levels[1:])):
      raise ValueError('cycle_counts must be strictly increasing')
    ####
    object.__setattr__(self, 'cycle_counts', levels)
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'pressure_lineage_tolerance',
      'cell_residual_tolerance',
      'refinement_tolerance',
    ):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
    ####
  ####

  @property
  def ambient_pressure_Pa(self) -> float:
    """Return the exact ambient target retained by the field iteration."""

    field_iteration = self.terminal_closure.field_iteration
    if field_iteration is None or field_iteration.request is None:
      raise ValueError('terminal closure did not retain field-iteration request')
    ####
    return field_iteration.request.ambient_pressure_Pa
  ####

  @property
  def target_centerline_y_m(self) -> float:
    field_iteration = self.terminal_closure.field_iteration
    if field_iteration is None or field_iteration.request is None:
      raise ValueError('terminal closure did not retain field-iteration request')
    ####
    return field_iteration.request.target_centerline_y_m
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'terminal_closure_status': self.terminal_closure.status.value,
      'cycle_counts': list(self.cycle_counts),
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'target_centerline_y_m': self.target_centerline_y_m,
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'refinement_tolerance': self.refinement_tolerance,
      'maximum_iterations': self.maximum_iterations,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedTerminalRefinementResult:
  """Retained continuation ladder with an explicit refinement claim gate."""

  status: MocEulerTwoSidedTerminalRefinementStatus
  request: MocEulerTwoSidedTerminalRefinementRequest | None
  terminal_closure: MocEulerTwoSidedTerminalClosureResult | None
  continuations: tuple[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult, ...
  ]
  cycle_counts: tuple[int, ...]
  cell_counts: tuple[int, ...]
  maximum_cell_euler_residuals: tuple[float, ...]
  continuation_boundaries_verified: tuple[bool, ...]
  structural_ladder_verified: bool
  cell_growth_verified: bool
  residuals_finite: bool
  residuals_verified: bool
  residual_nonincreasing_verified: bool
  residual_reduction_verified: bool
  refinement_convergence_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedTerminalRefinementStatus):
      raise TypeError('status must be a terminal refinement status')
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocEulerTwoSidedTerminalRefinementRequest,
    ):
      raise TypeError('request must be typed or None')
    ####
    if self.terminal_closure is not None and not isinstance(
      self.terminal_closure,
      MocEulerTwoSidedTerminalClosureResult,
    ):
      raise TypeError('terminal_closure must be typed or None')
    ####
    continuations = tuple(self.continuations)
    if any(
      not isinstance(
        result,
        MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult,
      )
      for result in continuations
    ):
      raise TypeError('continuations must contain typed continuation results')
    ####
    cycle_counts = tuple(self.cycle_counts)
    cell_counts = tuple(self.cell_counts)
    residuals = tuple(float(value) for value in self.maximum_cell_euler_residuals)
    boundary_flags = tuple(self.continuation_boundaries_verified)
    if not (
      len(continuations)
      == len(cycle_counts)
      == len(cell_counts)
      == len(residuals)
      == len(boundary_flags)
    ):
      raise ValueError('ladder summaries must match the continuation count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in (*cycle_counts, *cell_counts)
    ):
      raise ValueError('cycle and cell counts must be nonnegative integers')
    ####
    if any(not isfinite(value) or value < 0.0 for value in residuals):
      raise ValueError('maximum residuals must be finite and nonnegative')
    ####
    if any(not isinstance(value, bool) for value in boundary_flags):
      raise TypeError('continuation boundary flags must be bool values')
    ####
    object.__setattr__(self, 'continuations', continuations)
    object.__setattr__(self, 'cycle_counts', cycle_counts)
    object.__setattr__(self, 'cell_counts', cell_counts)
    object.__setattr__(self, 'maximum_cell_euler_residuals', residuals)
    object.__setattr__(self, 'continuation_boundaries_verified', boundary_flags)
    for name in (
      'structural_ladder_verified',
      'cell_growth_verified',
      'residuals_finite',
      'residuals_verified',
      'residual_nonincreasing_verified',
      'residual_reduction_verified',
      'refinement_convergence_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.physical_closure_verified:
      raise ValueError('terminal refinement cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('terminal refinement must retain the promotion block')
    ####
    if self.production_claim_allowed:
      raise ValueError('terminal refinement cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedTerminalRefinementStatus.CONVERGED_LOCAL_LADDER
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.structural_ladder_verified
      and self.cell_growth_verified
      and self.residuals_finite
      and self.residuals_verified
      and self.residual_nonincreasing_verified
      and not self.physical_closure_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'cycle_counts': list(self.cycle_counts),
      'cell_counts': list(self.cell_counts),
      'maximum_cell_euler_residuals': list(self.maximum_cell_euler_residuals),
      'continuation_boundaries_verified': list(
        self.continuation_boundaries_verified
      ),
      'structural_ladder_verified': self.structural_ladder_verified,
      'cell_growth_verified': self.cell_growth_verified,
      'residuals_finite': self.residuals_finite,
      'residuals_verified': self.residuals_verified,
      'residual_nonincreasing_verified': self.residual_nonincreasing_verified,
      'residual_reduction_verified': self.residual_reduction_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'physical_closure_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'terminal_closure_status': (
        None
        if self.terminal_closure is None
        else self.terminal_closure.status.value
      ),
      'continuations': [result.as_report() for result in self.continuations],
      'request': None if self.request is None else self.request.as_report(),
      'external_validation_required': True,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedTerminalRefinementStatus,
  message: str,
  *,
  request: MocEulerTwoSidedTerminalRefinementRequest | None = None,
  terminal_closure: MocEulerTwoSidedTerminalClosureResult | None = None,
  continuations: Sequence[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ] = (),
  cycle_counts: Sequence[int] = (),
  cell_counts: Sequence[int] = (),
  residuals: Sequence[float] = (),
  boundary_flags: Sequence[bool] = (),
  structural_ladder_verified: bool = False,
  cell_growth_verified: bool = False,
  residuals_finite: bool = False,
  residuals_verified: bool = False,
  residual_nonincreasing_verified: bool = False,
  residual_reduction_verified: bool = False,
  refinement_convergence_verified: bool = False,
) -> MocEulerTwoSidedTerminalRefinementResult:
  return MocEulerTwoSidedTerminalRefinementResult(
    status=status,
    request=request,
    terminal_closure=terminal_closure,
    continuations=tuple(continuations),
    cycle_counts=tuple(cycle_counts),
    cell_counts=tuple(cell_counts),
    maximum_cell_euler_residuals=tuple(residuals),
    continuation_boundaries_verified=tuple(boundary_flags),
    structural_ladder_verified=structural_ladder_verified,
    cell_growth_verified=cell_growth_verified,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing_verified,
    residual_reduction_verified=residual_reduction_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )
####


def refine_euler_two_sided_terminal_closure(
  request: MocEulerTwoSidedTerminalRefinementRequest,
) -> MocEulerTwoSidedTerminalRefinementResult:
  """Run a solver-owned continuation ladder without promoting it."""

  if not isinstance(request, MocEulerTwoSidedTerminalRefinementRequest):
    return _failure(
      MocEulerTwoSidedTerminalRefinementStatus.INVALID_INPUT,
      'request must be a MocEulerTwoSidedTerminalRefinementRequest',
    )
  ####
  source = request.terminal_closure.internal_field
  if source is None:
    return _failure(
      MocEulerTwoSidedTerminalRefinementStatus.TERMINAL_CLOSURE_REQUIRED,
      'terminal refinement requires a retained internal characteristic field',
      request=request,
      terminal_closure=request.terminal_closure,
    )
  ####
  continuations: list[
    MocEulerAmbientFirstWedgeEntropyCharacteristicContinuationResult
  ] = []
  for cycle_count in request.cycle_counts:
    try:
      continuation = solve_euler_ambient_first_wedge_entropy_characteristic_continuation(
        source,
        source.continuation_boundary,
        request.ambient_pressure_Pa,
        cycle_count=cycle_count,
        target_centerline_y_m=request.target_centerline_y_m,
        position_tolerance_m=request.position_tolerance_m,
        characteristic_residual_tolerance=request.characteristic_residual_tolerance,
        pressure_lineage_tolerance=request.pressure_lineage_tolerance,
        cell_residual_tolerance=request.cell_residual_tolerance,
        maximum_iterations=request.maximum_iterations,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerTwoSidedTerminalRefinementStatus.CONTINUATION_FAILURE,
        f'terminal continuation ladder raised: {error}',
        request=request,
        terminal_closure=request.terminal_closure,
        continuations=continuations,
        cycle_counts=request.cycle_counts[:len(continuations)],
        cell_counts=tuple(len(result.cells) for result in continuations),
        residuals=tuple(
          result.maximum_cell_euler_residual or 0.0
          for result in continuations
        ),
        boundary_flags=tuple(
          result.continuation_boundary_verified for result in continuations
        ),
      )
    ####
    continuations.append(continuation)
    if not continuation.local_consistency_verified:
      return _failure(
        MocEulerTwoSidedTerminalRefinementStatus.CONTINUATION_FAILURE,
        'one terminal continuation level failed its local solver gates',
        request=request,
        terminal_closure=request.terminal_closure,
        continuations=continuations,
        cycle_counts=request.cycle_counts[:len(continuations)],
        cell_counts=tuple(len(result.cells) for result in continuations),
        residuals=tuple(
          result.maximum_cell_euler_residual or 0.0
          for result in continuations
        ),
        boundary_flags=tuple(
          result.continuation_boundary_verified for result in continuations
        ),
      )
    ####
  ####
  cell_counts = tuple(len(result.cells) for result in continuations)
  residuals = tuple(
    result.maximum_cell_euler_residual or 0.0 for result in continuations
  )
  boundary_flags = tuple(
    result.continuation_boundary_verified for result in continuations
  )
  structural = bool(
    continuations
    and all(result.local_consistency_verified for result in continuations)
    and all(boundary_flags)
  )
  cell_growth = bool(
    all(right > left for left, right in zip(cell_counts, cell_counts[1:]))
  )
  residuals_finite = bool(
    residuals and all(isfinite(value) and value >= 0.0 for value in residuals)
  )
  residuals_verified = bool(
    residuals_finite and all(
      result.cell_euler_residuals_verified
      and value <= request.cell_residual_tolerance
      for result, value in zip(continuations, residuals, strict=True)
    )
  )
  residual_nonincreasing = bool(
    all(
      right <= left + request.refinement_tolerance * max(1.0, abs(left))
      for left, right in zip(residuals, residuals[1:])
    )
  )
  residual_reduction = bool(len(residuals) >= 2 and residuals[-1] < residuals[0])
  refinement_convergence = bool(
    structural
    and cell_growth
    and residuals_finite
    and residuals_verified
    and residual_nonincreasing
    and residual_reduction
  )
  return _failure(
    MocEulerTwoSidedTerminalRefinementStatus.CONVERGED_LOCAL_LADDER,
    (
      'solver-owned terminal continuation ladder passed topology and local '
      'residual gates; strict residual reduction is still required for '
      'refinement convergence and physical shock-cell promotion'
      if not refinement_convergence
      else 'terminal continuation ladder passed local refinement gates; '
      'canonical closure and physical shock-cell promotion remain pending'
    ),
    request=request,
    terminal_closure=request.terminal_closure,
    continuations=continuations,
    cycle_counts=request.cycle_counts,
    cell_counts=cell_counts,
    residuals=residuals,
    boundary_flags=boundary_flags,
    structural_ladder_verified=structural,
    cell_growth_verified=cell_growth,
    residuals_finite=residuals_finite,
    residuals_verified=residuals_verified,
    residual_nonincreasing_verified=residual_nonincreasing,
    residual_reduction_verified=residual_reduction,
    refinement_convergence_verified=refinement_convergence,
  )
####
