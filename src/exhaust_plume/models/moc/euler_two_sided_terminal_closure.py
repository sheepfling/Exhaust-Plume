"""Entropy-aware terminal closure for the two-sided Euler research lane.

This module consumes only a converged two-sided field iteration and then runs
the existing solver-owned terminal-wedge sequence: characteristic reflection,
entropy carry, and the bounded internal characteristic subcell field.  The
sequence closes a local terminal seam, not the global reflected free boundary
or a production shock-cell chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.euler_entropy_carry import (
  MocEulerAmbientFirstWedgeEntropyCarryResult,
  solve_euler_ambient_first_wedge_entropy_carry,
)
from exhaust_plume.models.moc.euler_entropy_characteristic_field import (
  MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
  solve_euler_ambient_first_wedge_entropy_characteristic_field,
)
from exhaust_plume.models.moc.euler_terminal_wedge import (
  MocEulerAmbientFirstWedgeCharacteristicResult,
  solve_euler_ambient_first_wedge_characteristic_remesh,
)
from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
)

__all__ = (
  'MocEulerTwoSidedTerminalClosureStatus',
  'MocEulerTwoSidedTerminalClosureRequest',
  'MocEulerTwoSidedTerminalClosureResult',
  'solve_euler_two_sided_terminal_closure',
)


class MocEulerTwoSidedTerminalClosureStatus(str, Enum):
  """Typed outcomes for the local entropy-aware terminal closure."""

  CONVERGED_INTERNAL_FIELD = 'converged_two_sided_terminal_internal_field'
  INVALID_INPUT = 'invalid_input'
  ITERATION_REQUIRED = 'two_sided_terminal_field_iteration_required'
  TERMINAL_WEDGE_FAILURE = 'two_sided_terminal_wedge_failure'
  ENTROPY_CARRY_FAILURE = 'two_sided_terminal_entropy_carry_failure'
  INTERNAL_FIELD_FAILURE = 'two_sided_terminal_internal_field_failure'
####


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
class MocEulerTwoSidedTerminalClosureRequest:
  """Inputs for the local terminal closure after two-sided iteration."""

  field_iteration: MocEulerTwoSidedFieldIterationResult
  position_tolerance_m: float = 1.0e-10
  characteristic_residual_tolerance: float = 1.0e-8
  edge_alignment_tolerance: float = 0.25
  cell_residual_tolerance: float = 1.0e-2
  pressure_lineage_tolerance: float = 1.0e-8
  compatibility_weight: float = 1.0e7
  maximum_entropy_carry_iterations: int = 24
  maximum_internal_field_iterations: int = 48

  def __post_init__(self) -> None:
    if not isinstance(
      self.field_iteration,
      MocEulerTwoSidedFieldIterationResult,
    ):
      raise TypeError(
        'field_iteration must be a MocEulerTwoSidedFieldIterationResult'
      )
    ####
    if not (
      self.field_iteration.converged
      and self.field_iteration.field_iteration_verified
      and self.field_iteration.final_physical_field is not None
      and self.field_iteration.bounded_physical_field_verified
      and self.field_iteration.chain_promotion_blocked
      and not self.field_iteration.production_claim_allowed
    ):
      raise ValueError(
        'terminal closure requires a converged, locally verified two-sided '
        'field iteration with promotion blocked'
      )
    ####
    for name in (
      'position_tolerance_m',
      'characteristic_residual_tolerance',
      'edge_alignment_tolerance',
      'cell_residual_tolerance',
      'pressure_lineage_tolerance',
      'compatibility_weight',
    ):
      object.__setattr__(self, name, _positive_float(getattr(self, name), name))
    ####
    for name in (
      'maximum_entropy_carry_iterations',
      'maximum_internal_field_iterations',
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
      ####
    ####
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'field_iteration_status': self.field_iteration.status.value,
      'position_tolerance_m': self.position_tolerance_m,
      'characteristic_residual_tolerance': self.characteristic_residual_tolerance,
      'edge_alignment_tolerance': self.edge_alignment_tolerance,
      'cell_residual_tolerance': self.cell_residual_tolerance,
      'pressure_lineage_tolerance': self.pressure_lineage_tolerance,
      'compatibility_weight': self.compatibility_weight,
      'maximum_entropy_carry_iterations': self.maximum_entropy_carry_iterations,
      'maximum_internal_field_iterations': self.maximum_internal_field_iterations,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedTerminalClosureResult:
  """Retained local terminal-wedge closure below physical promotion."""

  status: MocEulerTwoSidedTerminalClosureStatus
  request: MocEulerTwoSidedTerminalClosureRequest | None
  field_iteration: MocEulerTwoSidedFieldIterationResult | None
  terminal_wedge: MocEulerAmbientFirstWedgeCharacteristicResult | None
  entropy_carry: MocEulerAmbientFirstWedgeEntropyCarryResult | None
  internal_field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None
  terminal_geometry_verified: bool
  entropy_carry_verified: bool
  internal_characteristic_field_verified: bool
  physical_closure_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocEulerTwoSidedTerminalClosureStatus):
      raise TypeError(
        'status must be a MocEulerTwoSidedTerminalClosureStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocEulerTwoSidedTerminalClosureRequest,
    ):
      raise TypeError(
        'request must be a MocEulerTwoSidedTerminalClosureRequest or None'
      )
    ####
    if self.field_iteration is not None and not isinstance(
      self.field_iteration,
      MocEulerTwoSidedFieldIterationResult,
    ):
      raise TypeError(
        'field_iteration must be a MocEulerTwoSidedFieldIterationResult or None'
      )
    ####
    for name, expected_type in (
      (
        'terminal_wedge',
        MocEulerAmbientFirstWedgeCharacteristicResult,
      ),
      (
        'entropy_carry',
        MocEulerAmbientFirstWedgeEntropyCarryResult,
      ),
      (
        'internal_field',
        MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} has an unexpected result type')
      ####
    ####
    for name in (
      'terminal_geometry_verified',
      'entropy_carry_verified',
      'internal_characteristic_field_verified',
      'physical_closure_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if self.physical_closure_verified:
      raise ValueError('local terminal closure cannot claim physical closure')
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('local terminal closure must block chain promotion')
    ####
    if self.production_claim_allowed:
      raise ValueError('local terminal closure cannot claim production validity')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status is MocEulerTwoSidedTerminalClosureStatus.CONVERGED_INTERNAL_FIELD
  ####

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.terminal_geometry_verified
      and self.entropy_carry_verified
      and self.internal_characteristic_field_verified
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
      'field_iteration_status': (
        None
        if self.field_iteration is None
        else self.field_iteration.status.value
      ),
      'terminal_geometry_verified': self.terminal_geometry_verified,
      'entropy_carry_verified': self.entropy_carry_verified,
      'internal_characteristic_field_verified': (
        self.internal_characteristic_field_verified
      ),
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'terminal_wedge': (
        None if self.terminal_wedge is None else self.terminal_wedge.as_report()
      ),
      'entropy_carry': (
        None if self.entropy_carry is None else self.entropy_carry.as_report()
      ),
      'internal_field': (
        None if self.internal_field is None else self.internal_field.as_report()
      ),
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedTerminalClosureStatus,
  message: str,
  *,
  request: MocEulerTwoSidedTerminalClosureRequest | None = None,
  field_iteration: MocEulerTwoSidedFieldIterationResult | None = None,
  terminal_wedge: MocEulerAmbientFirstWedgeCharacteristicResult | None = None,
  entropy_carry: MocEulerAmbientFirstWedgeEntropyCarryResult | None = None,
  internal_field: MocEulerAmbientFirstWedgeEntropyCharacteristicFieldResult | None = None,
  terminal_geometry_verified: bool = False,
  entropy_carry_verified: bool = False,
  internal_characteristic_field_verified: bool = False,
) -> MocEulerTwoSidedTerminalClosureResult:
  return MocEulerTwoSidedTerminalClosureResult(
    status=status,
    request=request,
    field_iteration=field_iteration,
    terminal_wedge=terminal_wedge,
    entropy_carry=entropy_carry,
    internal_field=internal_field,
    terminal_geometry_verified=terminal_geometry_verified,
    entropy_carry_verified=entropy_carry_verified,
    internal_characteristic_field_verified=internal_characteristic_field_verified,
    physical_closure_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )
####


def solve_euler_two_sided_terminal_closure(
  request: MocEulerTwoSidedTerminalClosureRequest,
) -> MocEulerTwoSidedTerminalClosureResult:
  """Solve the local entropy-aware terminal closure after field iteration."""

  if not isinstance(request, MocEulerTwoSidedTerminalClosureRequest):
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.INVALID_INPUT,
      'request must be a MocEulerTwoSidedTerminalClosureRequest',
    )
  ####
  field_iteration = request.field_iteration
  source_field = field_iteration.final_physical_field
  if not field_iteration.converged or source_field is None:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.ITERATION_REQUIRED,
      'terminal closure requires a converged two-sided field iteration',
      request=request,
      field_iteration=field_iteration,
    )
  ####
  try:
    terminal_wedge = solve_euler_ambient_first_wedge_characteristic_remesh(
      source_field,
      position_tolerance_m=request.position_tolerance_m,
      characteristic_residual_tolerance=request.characteristic_residual_tolerance,
      edge_alignment_tolerance=request.edge_alignment_tolerance,
      cell_residual_tolerance=request.cell_residual_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.TERMINAL_WEDGE_FAILURE,
      f'terminal characteristic-wedge solve raised: {error}',
      request=request,
      field_iteration=field_iteration,
    )
  ####
  terminal_geometry_verified = bool(
    terminal_wedge.converged
    and terminal_wedge.local_consistency_verified
  )
  if not terminal_geometry_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.TERMINAL_WEDGE_FAILURE,
      f'terminal characteristic-wedge solve did not pass local gates: {terminal_wedge.message}',
      request=request,
      field_iteration=field_iteration,
      terminal_wedge=terminal_wedge,
    )
  ####
  try:
    entropy_carry = solve_euler_ambient_first_wedge_entropy_carry(
      terminal_wedge,
      position_tolerance_m=request.position_tolerance_m,
      characteristic_residual_tolerance=request.characteristic_residual_tolerance,
      edge_alignment_tolerance=request.edge_alignment_tolerance,
      cell_residual_tolerance=request.cell_residual_tolerance,
      pressure_lineage_tolerance=request.pressure_lineage_tolerance,
      maximum_iterations=request.maximum_entropy_carry_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.ENTROPY_CARRY_FAILURE,
      f'entropy-carrying terminal solve raised: {error}',
      request=request,
      field_iteration=field_iteration,
      terminal_wedge=terminal_wedge,
      terminal_geometry_verified=True,
    )
  ####
  entropy_carry_verified = bool(
    entropy_carry.local_consistency_verified
  )
  if not entropy_carry_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.ENTROPY_CARRY_FAILURE,
      f'entropy-carrying terminal solve did not pass local gates: {entropy_carry.message}',
      request=request,
      field_iteration=field_iteration,
      terminal_wedge=terminal_wedge,
      entropy_carry=entropy_carry,
      terminal_geometry_verified=True,
    )
  ####
  try:
    internal_field = solve_euler_ambient_first_wedge_entropy_characteristic_field(
      entropy_carry,
      position_tolerance_m=request.position_tolerance_m,
      characteristic_residual_tolerance=request.characteristic_residual_tolerance,
      edge_alignment_tolerance=request.edge_alignment_tolerance,
      cell_residual_tolerance=request.cell_residual_tolerance,
      pressure_lineage_tolerance=request.pressure_lineage_tolerance,
      compatibility_weight=request.compatibility_weight,
      maximum_iterations=request.maximum_internal_field_iterations,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.INTERNAL_FIELD_FAILURE,
      f'internal entropy-characteristic field solve raised: {error}',
      request=request,
      field_iteration=field_iteration,
      terminal_wedge=terminal_wedge,
      entropy_carry=entropy_carry,
      terminal_geometry_verified=True,
      entropy_carry_verified=True,
    )
  ####
  internal_verified = bool(internal_field.local_consistency_verified)
  if not internal_verified:
    return _failure(
      MocEulerTwoSidedTerminalClosureStatus.INTERNAL_FIELD_FAILURE,
      f'internal entropy-characteristic field did not pass local gates: {internal_field.message}',
      request=request,
      field_iteration=field_iteration,
      terminal_wedge=terminal_wedge,
      entropy_carry=entropy_carry,
      internal_field=internal_field,
      terminal_geometry_verified=True,
      entropy_carry_verified=True,
    )
  ####
  return _failure(
    MocEulerTwoSidedTerminalClosureStatus.CONVERGED_INTERNAL_FIELD,
    'two-sided field iteration reached a solver-owned entropy-aware internal terminal field; global reflected free-boundary closure, continuation, external validation, and production promotion remain pending',
    request=request,
    field_iteration=field_iteration,
    terminal_wedge=terminal_wedge,
    entropy_carry=entropy_carry,
    internal_field=internal_field,
    terminal_geometry_verified=True,
    entropy_carry_verified=True,
    internal_characteristic_field_verified=True,
  )
####
