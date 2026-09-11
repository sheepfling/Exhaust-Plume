"""Conservative residual line-search for the two-sided Euler interface.

The existing moving-interface law derives a physically scaled normal update
from the mass Rankine--Hugoniot equation and retains the signed mass,
momentum, and energy residuals.  This module consumes that complete vector as
the acceptance criterion for a bounded nonlinear front/field iteration:

``exact field -> signed residual response -> trial front -> exact field
re-solve -> residual measurement``.

The trial step is backtracked when the re-solved field does not reduce the
dimensionless conservative residual norm.  This is a real solver-owned
consumer of the residual vector, but it is intentionally not a canonical
mixed-regime closure.  The downstream probe remains a research measurement,
and all canonical, chain, production, and external-validation gates stay
closed here.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite, sqrt
from typing import Any

from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
  solve_euler_two_sided_field_iteration,
)
from exhaust_plume.models.moc.euler_two_sided_interface_law import (
  MocEulerTwoSidedInterfaceLawRequest,
  MocEulerTwoSidedInterfaceLawResult,
  build_solver_owned_euler_two_sided_interface_response,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
  MocEulerTwoSidedMovingInterfaceRequest,
)

__all__ = (
  'MocEulerTwoSidedConservativeResidualSolveStatus',
  'MocEulerTwoSidedConservativeResidualSolveRequest',
  'MocEulerTwoSidedConservativeResidualSolveIteration',
  'MocEulerTwoSidedConservativeResidualSolveResult',
  'solve_euler_two_sided_conservative_residual',
)


MOC_EULER_TWO_SIDED_CONSERVATIVE_RESIDUAL_SOLVER_ID = (
  'op.moc.euler-two-sided-conservative-residual-line-search-v1'
)


class MocEulerTwoSidedConservativeResidualSolveStatus(str, Enum):
  """Typed outcome of one bounded conservative residual solve."""

  CONVERGED_RESEARCH_RESIDUAL = (
    'converged-research-two-sided-conservative-residual'
  )
  INVALID_INPUT = 'invalid_input'
  INITIAL_FIELD_FAILURE = 'two-sided-conservative-initial-field-failure'
  RESPONSE_FAILURE = 'two-sided-conservative-response-failure'
  FIELD_RESOLVE_FAILURE = 'two-sided-conservative-field-resolve-failure'
  LINE_SEARCH_FAILURE = 'two-sided-conservative-line-search-failure'
  ITERATION_LIMIT = 'two-sided-conservative-iteration-limit'


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


def _bounded_fraction(value: Any, name: str) -> float:
  numeric = _positive_float(value, name)
  if numeric > 1.0:
    raise ValueError(f'{name} must be no greater than one')
  ####
  return numeric


def _nonnegative_float(value: Any, name: str) -> float:
  try:
    numeric = float(value)
  except (TypeError, ValueError) as error:
    raise ValueError(f'{name} must be numeric') from error
  ####
  if not isfinite(numeric) or numeric < 0.0:
    raise ValueError(f'{name} must be finite and nonnegative')
  ####
  return numeric


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedConservativeResidualSolveRequest:
  """Controls for a solver-owned residual/vector line-search solve."""

  moving_request: MocEulerTwoSidedMovingInterfaceRequest
  law_request: MocEulerTwoSidedInterfaceLawRequest
  maximum_iterations: int = 8
  maximum_backtracks: int = 5
  backtrack_factor: float = 0.5
  minimum_step_fraction: float = 1.0e-2
  minimum_descent_fraction: float = 1.0e-6
  require_strict_descent: bool = True
  use_directional_residual_correction: bool = True
  jacobian_probe_fraction: float = 0.5
  maximum_directional_step_fraction: float = 1.0

  def __post_init__(self) -> None:
    if not isinstance(
      self.moving_request,
      MocEulerTwoSidedMovingInterfaceRequest,
    ):
      raise TypeError(
        'moving_request must be a MocEulerTwoSidedMovingInterfaceRequest'
      )
    ####
    if not isinstance(self.law_request, MocEulerTwoSidedInterfaceLawRequest):
      raise TypeError(
        'law_request must be a MocEulerTwoSidedInterfaceLawRequest'
      )
    ####
    for name in ('maximum_iterations', 'maximum_backtracks'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be a positive integer')
      ####
    ####
    object.__setattr__(
      self,
      'backtrack_factor',
      _bounded_fraction(self.backtrack_factor, 'backtrack_factor'),
    )
    object.__setattr__(
      self,
      'minimum_step_fraction',
      _bounded_fraction(self.minimum_step_fraction, 'minimum_step_fraction'),
    )
    object.__setattr__(
      self,
      'minimum_descent_fraction',
      _bounded_fraction(
        self.minimum_descent_fraction,
        'minimum_descent_fraction',
      ),
    )
    ####
    if not isinstance(self.require_strict_descent, bool):
      raise TypeError('require_strict_descent must be a bool')
    ####
    if not isinstance(self.use_directional_residual_correction, bool):
      raise TypeError('use_directional_residual_correction must be a bool')
    ####
    if self.backtrack_factor >= 1.0:
      raise ValueError('backtrack_factor must be less than one')
    ####
    object.__setattr__(
      self,
      'jacobian_probe_fraction',
      _bounded_fraction(self.jacobian_probe_fraction, 'jacobian_probe_fraction'),
    )
    object.__setattr__(
      self,
      'maximum_directional_step_fraction',
      _bounded_fraction(
        self.maximum_directional_step_fraction,
        'maximum_directional_step_fraction',
      ),
    )
    ####
    if self.law_request.source_band is None:
      raise ValueError('law_request must retain a source band')
    ####

  def as_report(self) -> dict[str, object]:
    return {
      'solver_id': MOC_EULER_TWO_SIDED_CONSERVATIVE_RESIDUAL_SOLVER_ID,
      'moving_request': self.moving_request.as_report(),
      'law_request': self.law_request.as_report(),
      'maximum_iterations': self.maximum_iterations,
      'maximum_backtracks': self.maximum_backtracks,
      'backtrack_factor': self.backtrack_factor,
      'minimum_step_fraction': self.minimum_step_fraction,
      'minimum_descent_fraction': self.minimum_descent_fraction,
      'require_strict_descent': self.require_strict_descent,
      'use_directional_residual_correction': (
        self.use_directional_residual_correction
      ),
      'jacobian_probe_fraction': self.jacobian_probe_fraction,
      'maximum_directional_step_fraction': (
        self.maximum_directional_step_fraction
      ),
      'production_claim_allowed': False,
    }


def _scaled_residual_vector(
  response: MocEulerTwoSidedInterfaceResponse,
  request: MocEulerTwoSidedMovingInterfaceRequest,
) -> tuple[float, ...]:
  """Return the complete signed conservative vector in declared units."""

  if not response.signed_residuals_available:
    raise ValueError('response did not retain the complete signed residual vector')
  signed_mass = response.signed_mass_flux_residuals_kg_m2_s
  signed_momentum = response.signed_normal_momentum_residuals_Pa
  signed_energy = response.signed_energy_flux_residuals_W_m2
  assert signed_mass is not None
  assert signed_momentum is not None
  assert signed_energy is not None
  if not (len(signed_mass) == len(signed_momentum) == len(signed_energy)):
    raise ValueError('signed residual channels are not aligned')
  if not signed_mass:
    raise ValueError('signed residual vector is empty')
  terms: list[float] = []
  for mass, momentum, energy in zip(
    signed_mass,
    signed_momentum,
    signed_energy,
    strict=True,
  ):
    terms.extend(
      (
        float(mass) / request.mass_flux_tolerance_kg_m2_s,
        float(momentum) / request.normal_momentum_tolerance_Pa,
        float(energy) / request.energy_flux_tolerance_W_m2,
      )
    )
  if any(not isfinite(term) for term in terms):
    raise ValueError('scaled conservative residual vector is non-finite')
  ####
  return tuple(terms)


def _residual_norm(
  response: MocEulerTwoSidedInterfaceResponse,
  request: MocEulerTwoSidedMovingInterfaceRequest,
) -> float:
  """Return an RMS norm of the complete signed conservative vector."""

  terms = _scaled_residual_vector(response, request)
  value = sqrt(sum(term * term for term in terms) / len(terms))
  if not isfinite(value):
    raise ValueError('conservative residual norm is non-finite')
  ####
  return value


def _residuals_verified(
  response: MocEulerTwoSidedInterfaceResponse,
  request: MocEulerTwoSidedMovingInterfaceRequest,
) -> bool:
  return bool(
    response.maximum_mass_flux_residual_kg_m2_s
    <= request.mass_flux_tolerance_kg_m2_s
    and response.maximum_normal_momentum_residual_Pa
    <= request.normal_momentum_tolerance_Pa
    and response.maximum_energy_flux_residual_W_m2
    <= request.energy_flux_tolerance_W_m2
  )


def _directional_least_squares_step(
  current_vector: tuple[float, ...],
  probe_vector: tuple[float, ...],
  probe_fraction: float,
  maximum_step_fraction: float,
) -> float | None:
  """Estimate a bounded scalar correction along the solver-owned direction."""

  if len(current_vector) != len(probe_vector) or not current_vector:
    raise ValueError('directional residual vectors must be non-empty and aligned')
  ####
  derivative = tuple(
    (probe - current) / probe_fraction
    for current, probe in zip(current_vector, probe_vector, strict=True)
  )
  denominator = sum(value * value for value in derivative)
  if not isfinite(denominator) or denominator <= 1.0e-24:
    return None
  ####
  numerator = sum(
    current * slope
    for current, slope in zip(current_vector, derivative, strict=True)
  )
  if not isfinite(numerator):
    return None
  ####
  raw_step = -numerator / denominator
  if not isfinite(raw_step) or raw_step <= 0.0:
    return None
  ####
  return min(maximum_step_fraction, raw_step)


def _field_verified(field: MocEulerTwoSidedFieldIterationResult) -> bool:
  return bool(
    field.field_iteration_verified
    and field.final_physical_field is not None
    and field.final_physical_field.physical_field_verified
  )


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedConservativeResidualSolveIteration:
  """One trial, exact field re-solve, and residual acceptance decision."""

  iteration_index: int
  step_fraction: float
  backtrack_count: int
  field_iteration: MocEulerTwoSidedFieldIterationResult
  response: MocEulerTwoSidedInterfaceResponse | None
  next_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  measured_response: MocEulerTwoSidedInterfaceResponse | None
  residual_norm_before: float | None
  residual_norm_after: float | None
  residual_descent_verified: bool
  accepted: bool
  field_re_solve_verified: bool
  message: str = ''
  directional_jacobian_verified: bool = False
  jacobian_probe_step_fraction: float | None = None
  jacobian_probe_residual_norm: float | None = None
  directional_step_fraction: float | None = None
  step_source: str = 'backtracked-law-direction'

  def __post_init__(self) -> None:
    if (
      isinstance(self.iteration_index, bool)
      or not isinstance(self.iteration_index, int)
      or self.iteration_index < 0
    ):
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    if not isinstance(self.field_iteration, MocEulerTwoSidedFieldIterationResult):
      raise TypeError(
        'field_iteration must be a MocEulerTwoSidedFieldIterationResult'
      )
    ####
    if self.next_field_iteration is not None and not isinstance(
      self.next_field_iteration,
      MocEulerTwoSidedFieldIterationResult,
    ):
      raise TypeError(
        'next_field_iteration must be a '
        'MocEulerTwoSidedFieldIterationResult or None'
      )
    ####
    for name in ('response', 'measured_response'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocEulerTwoSidedInterfaceResponse,
      ):
        raise TypeError(
          f'{name} must be a MocEulerTwoSidedInterfaceResponse or None'
        )
      ####
    ####
    step = _bounded_fraction(self.step_fraction, 'step_fraction')
    object.__setattr__(self, 'step_fraction', step)
    if (
      isinstance(self.backtrack_count, bool)
      or not isinstance(self.backtrack_count, int)
      or self.backtrack_count < 0
    ):
      raise ValueError('backtrack_count must be a nonnegative integer')
    ####
    for name in ('residual_norm_before', 'residual_norm_after'):
      value = getattr(self, name)
      if value is not None:
        numeric = _nonnegative_float(value, name)
        object.__setattr__(self, name, numeric)
      ####
    ####
    if self.jacobian_probe_step_fraction is not None:
      object.__setattr__(
        self,
        'jacobian_probe_step_fraction',
        _bounded_fraction(
          self.jacobian_probe_step_fraction,
          'jacobian_probe_step_fraction',
        ),
      )
    if self.jacobian_probe_residual_norm is not None:
      object.__setattr__(
        self,
        'jacobian_probe_residual_norm',
        _nonnegative_float(
          self.jacobian_probe_residual_norm,
          'jacobian_probe_residual_norm',
        ),
      )
    if self.directional_step_fraction is not None:
      object.__setattr__(
        self,
        'directional_step_fraction',
        _bounded_fraction(
          self.directional_step_fraction,
          'directional_step_fraction',
        ),
      )
    if not isinstance(self.directional_jacobian_verified, bool):
      raise TypeError('directional_jacobian_verified must be a bool')
    ####
    object.__setattr__(self, 'step_source', str(self.step_source))
    if not self.step_source:
      raise ValueError('step_source must be non-empty')
    ####
    for name in ('residual_descent_verified', 'accepted', 'field_re_solve_verified'):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    object.__setattr__(self, 'message', str(self.message))

  def as_report(self) -> dict[str, object]:
    return {
      'iteration_index': self.iteration_index,
      'step_fraction': self.step_fraction,
      'backtrack_count': self.backtrack_count,
      'residual_norm_before': self.residual_norm_before,
      'residual_norm_after': self.residual_norm_after,
      'residual_descent_verified': self.residual_descent_verified,
      'accepted': self.accepted,
      'field_re_solve_verified': self.field_re_solve_verified,
      'directional_jacobian_verified': self.directional_jacobian_verified,
      'jacobian_probe_step_fraction': self.jacobian_probe_step_fraction,
      'jacobian_probe_residual_norm': self.jacobian_probe_residual_norm,
      'directional_step_fraction': self.directional_step_fraction,
      'step_source': self.step_source,
      'response': None if self.response is None else self.response.as_report(),
      'measured_response': (
        None
        if self.measured_response is None
        else self.measured_response.as_report()
      ),
      'field_iteration': self.field_iteration.as_report(),
      'next_field_iteration': (
        None
        if self.next_field_iteration is None
        else self.next_field_iteration.as_report()
      ),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedConservativeResidualSolveResult:
  """Research-only result of the signed-vector front/field solve."""

  status: MocEulerTwoSidedConservativeResidualSolveStatus
  request: MocEulerTwoSidedConservativeResidualSolveRequest | None
  initial_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  final_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  records: tuple[MocEulerTwoSidedConservativeResidualSolveIteration, ...]
  final_response: MocEulerTwoSidedInterfaceResponse | None
  initial_residual_norm: float | None
  final_residual_norm: float | None
  residual_vector_verified: bool
  conservative_flux_closure_verified: bool
  field_re_solve_verified: bool
  terminal_fixed_point_verified: bool
  directional_residual_correction_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedConservativeResidualSolveStatus,
    ):
      raise TypeError(
        'status must be a MocEulerTwoSidedConservativeResidualSolveStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocEulerTwoSidedConservativeResidualSolveRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocEulerTwoSidedConservativeResidualSolveRequest or None'
      )
    ####
    for name in ('initial_field_iteration', 'final_field_iteration'):
      value = getattr(self, name)
      if value is not None and not isinstance(
        value,
        MocEulerTwoSidedFieldIterationResult,
      ):
        raise TypeError(
          f'{name} must be a MocEulerTwoSidedFieldIterationResult or None'
        )
      ####
    if self.final_response is not None and not isinstance(
      self.final_response,
      MocEulerTwoSidedInterfaceResponse,
    ):
      raise TypeError(
        'final_response must be a MocEulerTwoSidedInterfaceResponse or None'
      )
    ####
    records = tuple(self.records)
    if any(
      not isinstance(
        record,
        MocEulerTwoSidedConservativeResidualSolveIteration,
      )
      for record in records
    ):
      raise TypeError(
        'records must contain '
        'MocEulerTwoSidedConservativeResidualSolveIteration values'
      )
    ####
    for name in (
      'initial_residual_norm',
      'final_residual_norm',
    ):
      value = getattr(self, name)
      if value is not None:
        object.__setattr__(self, name, _nonnegative_float(value, name))
      ####
    ####
    for name in (
      'residual_vector_verified',
      'conservative_flux_closure_verified',
      'field_re_solve_verified',
      'terminal_fixed_point_verified',
      'directional_residual_correction_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'conservative residual results must remain blocked from promotion'
      )
    ####
    if self.status is (
      MocEulerTwoSidedConservativeResidualSolveStatus
      .CONVERGED_RESEARCH_RESIDUAL
    ) and not (
      self.final_response is not None
      and self.residual_vector_verified
      and self.conservative_flux_closure_verified
      and self.field_re_solve_verified
    ):
      raise ValueError(
        'a converged residual result must retain a verified response and '
        'exact field re-solve'
      )
    ####
    object.__setattr__(self, 'records', records)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerTwoSidedConservativeResidualSolveStatus
      .CONVERGED_RESEARCH_RESIDUAL
    )

  def as_report(self) -> dict[str, object]:
    return {
      'solver_id': MOC_EULER_TWO_SIDED_CONSERVATIVE_RESIDUAL_SOLVER_ID,
      'status': self.status.value,
      'converged': self.converged,
      'initial_residual_norm': self.initial_residual_norm,
      'final_residual_norm': self.final_residual_norm,
      'residual_vector_verified': self.residual_vector_verified,
      'conservative_flux_closure_verified': (
        self.conservative_flux_closure_verified
      ),
      'field_re_solve_verified': self.field_re_solve_verified,
      'terminal_fixed_point_verified': self.terminal_fixed_point_verified,
      'directional_residual_correction_verified': (
        self.directional_residual_correction_verified
      ),
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': None if self.request is None else self.request.as_report(),
      'initial_field_iteration': (
        None
        if self.initial_field_iteration is None
        else self.initial_field_iteration.as_report()
      ),
      'final_field_iteration': (
        None
        if self.final_field_iteration is None
        else self.final_field_iteration.as_report()
      ),
      'final_response': (
        None if self.final_response is None else self.final_response.as_report()
      ),
      'records': tuple(record.as_report() for record in self.records),
      'claim_status': (
        'research-only-signed-conservative-residual-line-search; canonical '
        'mixed-regime closure, refinement, external validation, and '
        'production claims remain blocked'
      ),
      'message': self.message,
    }


def _failure(
  status: MocEulerTwoSidedConservativeResidualSolveStatus,
  message: str,
  *,
  request: MocEulerTwoSidedConservativeResidualSolveRequest | None = None,
  initial_field: MocEulerTwoSidedFieldIterationResult | None = None,
  final_field: MocEulerTwoSidedFieldIterationResult | None = None,
  records: tuple[MocEulerTwoSidedConservativeResidualSolveIteration, ...] = (),
  final_response: MocEulerTwoSidedInterfaceResponse | None = None,
  initial_norm: float | None = None,
  final_norm: float | None = None,
  residual_vector_verified: bool = False,
  conservative_flux_closure_verified: bool = False,
  field_re_solve_verified: bool = False,
  terminal_fixed_point_verified: bool = False,
  directional_residual_correction_verified: bool = False,
) -> MocEulerTwoSidedConservativeResidualSolveResult:
  return MocEulerTwoSidedConservativeResidualSolveResult(
    status=status,
    request=request,
    initial_field_iteration=initial_field,
    final_field_iteration=final_field,
    records=records,
    final_response=final_response,
    initial_residual_norm=initial_norm,
    final_residual_norm=final_norm,
    residual_vector_verified=residual_vector_verified,
    conservative_flux_closure_verified=conservative_flux_closure_verified,
    field_re_solve_verified=field_re_solve_verified,
    terminal_fixed_point_verified=terminal_fixed_point_verified,
    directional_residual_correction_verified=(
      directional_residual_correction_verified
    ),
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=message,
  )


def _law_result(
  field: MocEulerTwoSidedFieldIterationResult,
  law_request: MocEulerTwoSidedInterfaceLawRequest,
) -> MocEulerTwoSidedInterfaceLawResult:
  """Measure a response without letting the measurement update geometry."""

  # The law's conservative flag is an admission gate for the one-step
  # response.  The residual solver must see the vector even while it is large,
  # so the outer solver owns the final strict gate.
  measurement_request = replace(
    law_request,
    require_conservative_flux_closure=False,
  )
  return build_solver_owned_euler_two_sided_interface_response(
    field,
    measurement_request,
  )


def solve_euler_two_sided_conservative_residual(
  request: MocEulerTwoSidedConservativeResidualSolveRequest,
) -> MocEulerTwoSidedConservativeResidualSolveResult:
  """Solve the bounded signed conservative residual/free-front system."""

  if not isinstance(
    request,
    MocEulerTwoSidedConservativeResidualSolveRequest,
  ):
    return _failure(
      MocEulerTwoSidedConservativeResidualSolveStatus.INVALID_INPUT,
      'request must be a '
      'MocEulerTwoSidedConservativeResidualSolveRequest',
    )
  ####
  try:
    initial = solve_euler_two_sided_field_iteration(
      request.moving_request.field_request
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedConservativeResidualSolveStatus.INITIAL_FIELD_FAILURE,
      f'initial exact two-sided field iteration raised: {error}',
      request=request,
    )
  ####
  if not _field_verified(initial):
    return _failure(
      MocEulerTwoSidedConservativeResidualSolveStatus.INITIAL_FIELD_FAILURE,
      'initial exact two-sided field iteration did not pass its local gates; '
      'no residual update was attempted',
      request=request,
      initial_field=initial,
      final_field=initial,
    )
  ####
  try:
    initial_law = _law_result(initial, request.law_request)
    if initial_law.response is None:
      raise ValueError(initial_law.message)
    initial_response = initial_law.response
    initial_norm = _residual_norm(initial_response, request.moving_request)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedConservativeResidualSolveStatus.RESPONSE_FAILURE,
      f'initial signed residual response failed: {error}',
      request=request,
      initial_field=initial,
      final_field=initial,
    )
  ####
  current = initial
  current_response = initial_response
  current_norm = initial_norm
  records: list[MocEulerTwoSidedConservativeResidualSolveIteration] = []
  motion_seen = False
  field_re_solve_verified = True
  directional_correction_seen = False
  ####
  for iteration_index in range(request.maximum_iterations):
    full_response_result = _law_result(current, request.law_request)
    full_response = full_response_result.response
    if full_response is None:
      return _failure(
        MocEulerTwoSidedConservativeResidualSolveStatus.RESPONSE_FAILURE,
        f'iteration {iteration_index} could not measure a signed response: '
        f'{full_response_result.message}',
        request=request,
        initial_field=initial,
        final_field=current,
        records=tuple(records),
        final_response=current_response,
        initial_norm=initial_norm,
        final_norm=current_norm,
        field_re_solve_verified=field_re_solve_verified,
      )
    ####
    try:
      full_norm = _residual_norm(full_response, request.moving_request)
      full_vector = _scaled_residual_vector(
        full_response,
        request.moving_request,
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerTwoSidedConservativeResidualSolveStatus.RESPONSE_FAILURE,
        f'iteration {iteration_index} residual norm failed: {error}',
        request=request,
        initial_field=initial,
        final_field=current,
        records=tuple(records),
        final_response=current_response,
        initial_norm=initial_norm,
        final_norm=current_norm,
        field_re_solve_verified=field_re_solve_verified,
      )
    ####
    response_closed = _residuals_verified(
      full_response,
      request.moving_request,
    )
    motion = full_response.maximum_normal_displacement_m > (
      request.moving_request.position_tolerance_m
    )
    motion_seen = motion_seen or motion
    terminal_zero = full_response.maximum_normal_displacement_m <= (
      request.moving_request.position_tolerance_m
    )
    stationary_allowed = bool(
      terminal_zero
      and request.moving_request.allow_stationary_equilibrium
      and full_response.stationary_equilibrium_candidate
    )
    if response_closed and (
      not request.moving_request.require_terminal_fixed_point or terminal_zero
    ) and (
      motion_seen
      or stationary_allowed
      or not request.moving_request.require_interface_motion
    ):
      return MocEulerTwoSidedConservativeResidualSolveResult(
        status=(
          MocEulerTwoSidedConservativeResidualSolveStatus
          .CONVERGED_RESEARCH_RESIDUAL
        ),
        request=request,
        initial_field_iteration=initial,
        final_field_iteration=current,
        records=tuple(records),
        final_response=full_response,
        initial_residual_norm=initial_norm,
        final_residual_norm=full_norm,
        residual_vector_verified=full_response.signed_residuals_available,
        conservative_flux_closure_verified=full_response.conservative_flux_closure_verified,
        field_re_solve_verified=field_re_solve_verified,
        terminal_fixed_point_verified=terminal_zero,
        directional_residual_correction_verified=(
          directional_correction_seen
        ),
        chain_promotion_blocked=True,
        production_claim_allowed=False,
        message=(
          'signed mass, normal-momentum, and energy residuals passed the '
          'declared research tolerances after exact field re-solves; '
          'canonical mixed-regime/free-boundary closure remains blocked'
        ),
      )
    ####
    accepted = False
    accepted_field: MocEulerTwoSidedFieldIterationResult | None = None
    accepted_response: MocEulerTwoSidedInterfaceResponse | None = None
    accepted_measurement: MocEulerTwoSidedInterfaceResponse | None = None
    accepted_after: float | None = None
    accepted_step = 1.0
    accepted_backtracks = 0
    accepted_step_source = 'backtracked-law-direction'
    directional_jacobian_verified = False
    jacobian_probe_step_fraction: float | None = None
    jacobian_probe_residual_norm: float | None = None
    directional_step_fraction: float | None = None
    last_message = 'no trial passed the residual descent criterion'

    def evaluate_step(
      step_fraction: float,
    ) -> tuple[
      MocEulerTwoSidedInterfaceResponse,
      MocEulerTwoSidedFieldIterationResult,
      MocEulerTwoSidedInterfaceResponse,
      float,
      tuple[float, ...],
    ]:
      trial_law_request = replace(
        request.law_request,
        pseudo_time_step_s=(
          request.law_request.pseudo_time_step_s * step_fraction
        ),
        require_conservative_flux_closure=False,
      )
      trial_law = build_solver_owned_euler_two_sided_interface_response(
        current,
        trial_law_request,
        iteration_index=iteration_index,
      )
      trial_response = trial_law.response
      if trial_response is None:
        raise ValueError(trial_law.message)
      ####
      next_request = replace(
        current.request,
        shock_boundary=trial_response.next_shock_boundary,
        companion_field=trial_response.next_companion_field,
      )
      candidate = solve_euler_two_sided_field_iteration(next_request)
      if not _field_verified(candidate):
        raise ValueError(
          'exact field re-solve did not pass its local gates: '
          f'{candidate.status.value}'
        )
      ####
      measurement = _law_result(candidate, trial_law_request)
      measured_response = measurement.response
      if measured_response is None:
        raise ValueError(measurement.message)
      ####
      after = _residual_norm(measured_response, request.moving_request)
      measured_vector = _scaled_residual_vector(
        measured_response,
        request.moving_request,
      )
      return (
        trial_response,
        candidate,
        measured_response,
        after,
        measured_vector,
      )

    def is_descent(
      after: float,
      measured_response: MocEulerTwoSidedInterfaceResponse,
    ) -> bool:
      strict_descent = after < full_norm * (
        1.0 - request.minimum_descent_fraction
      )
      nonstrict_descent = after < full_norm
      descent = strict_descent if request.require_strict_descent else nonstrict_descent
      if not descent and _residuals_verified(
        measured_response,
        request.moving_request,
      ):
        # A closed residual vector is admissible even when the final
        # backtracked movement is below numerical descent resolution.
        descent = True
      return descent

    if request.use_directional_residual_correction:
      try:
        jacobian_probe_step_fraction = request.jacobian_probe_fraction
        probe = evaluate_step(jacobian_probe_step_fraction)
        jacobian_probe_residual_norm = probe[3]
        directional_step_fraction = _directional_least_squares_step(
          full_vector,
          probe[4],
          jacobian_probe_step_fraction,
          request.maximum_directional_step_fraction,
        )
        if directional_step_fraction is not None:
          directional_jacobian_verified = True
          directional_correction_seen = True
          directional_candidate = evaluate_step(directional_step_fraction)
          if is_descent(directional_candidate[3], directional_candidate[2]):
            accepted = True
            accepted_field = directional_candidate[1]
            accepted_response = directional_candidate[0]
            accepted_measurement = directional_candidate[2]
            accepted_after = directional_candidate[3]
            accepted_step = directional_step_fraction
            accepted_step_source = 'directional-least-squares-correction'
          else:
            last_message = (
              'directional least-squares correction did not descend the '
              f'conservative residual norm ({directional_candidate[3]:.6g} '
              f'from {full_norm:.6g})'
            )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        last_message = f'directional residual correction failed: {error}'
    ####
    for backtrack_count in range(request.maximum_backtracks + 1):
      if accepted:
        break
      step_fraction = request.backtrack_factor**backtrack_count
      if step_fraction < request.minimum_step_fraction:
        break
      ####
      try:
        trial_response, candidate, measured_response, after, _ = evaluate_step(
          step_fraction
        )
        if is_descent(after, measured_response):
          accepted = True
          accepted_field = candidate
          accepted_response = trial_response
          accepted_measurement = measured_response
          accepted_after = after
          accepted_step = step_fraction
          accepted_backtracks = backtrack_count
          accepted_step_source = 'backtracked-law-direction'
          break
        ####
        last_message = (
          f'trial residual norm {after:.6g} did not descend from '
          f'{current_norm:.6g}'
        )
      except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
        last_message = f'trial step {step_fraction:.6g} failed: {error}'
        continue
      ####
    ####
    if not accepted or accepted_field is None or accepted_measurement is None:
      record = MocEulerTwoSidedConservativeResidualSolveIteration(
        iteration_index=iteration_index,
        step_fraction=accepted_step,
        backtrack_count=accepted_backtracks,
        field_iteration=current,
        response=full_response,
        next_field_iteration=None,
        measured_response=None,
        residual_norm_before=full_norm,
        residual_norm_after=None,
        residual_descent_verified=False,
        accepted=False,
        field_re_solve_verified=False,
        directional_jacobian_verified=directional_jacobian_verified,
        jacobian_probe_step_fraction=jacobian_probe_step_fraction,
        jacobian_probe_residual_norm=jacobian_probe_residual_norm,
        directional_step_fraction=directional_step_fraction,
        step_source=accepted_step_source,
        message=last_message,
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedConservativeResidualSolveStatus.LINE_SEARCH_FAILURE,
        f'conservative residual line search stopped at iteration '
        f'{iteration_index}: {last_message}',
        request=request,
        initial_field=initial,
        final_field=current,
        records=tuple(records),
        final_response=full_response,
        initial_norm=initial_norm,
        final_norm=full_norm,
        residual_vector_verified=full_response.signed_residuals_available,
        conservative_flux_closure_verified=full_response.conservative_flux_closure_verified,
        field_re_solve_verified=field_re_solve_verified,
        directional_residual_correction_verified=(
          directional_correction_seen
        ),
      )
    ####
    record = MocEulerTwoSidedConservativeResidualSolveIteration(
      iteration_index=iteration_index,
      step_fraction=accepted_step,
      backtrack_count=accepted_backtracks,
      field_iteration=current,
      response=accepted_response,
      next_field_iteration=accepted_field,
      measured_response=accepted_measurement,
      residual_norm_before=full_norm,
      residual_norm_after=accepted_after,
      residual_descent_verified=True,
      accepted=True,
      field_re_solve_verified=True,
      directional_jacobian_verified=directional_jacobian_verified,
      jacobian_probe_step_fraction=jacobian_probe_step_fraction,
      jacobian_probe_residual_norm=jacobian_probe_residual_norm,
      directional_step_fraction=directional_step_fraction,
      step_source=accepted_step_source,
      message=(
        'trial front was accepted after an exact field re-solve because the '
        'complete signed conservative residual norm descended; step source='
        f'{accepted_step_source}'
      ),
    )
    records.append(record)
    current = accepted_field
    current_response = accepted_measurement
    assert accepted_after is not None
    current_norm = accepted_after
    field_re_solve_verified = field_re_solve_verified and True
  ####
  return _failure(
    MocEulerTwoSidedConservativeResidualSolveStatus.ITERATION_LIMIT,
    'conservative residual line-search iteration limit reached before the '
    'declared mass, normal-momentum, and energy tolerances closed',
    request=request,
    initial_field=initial,
    final_field=current,
    records=tuple(records),
    final_response=current_response,
    initial_norm=initial_norm,
    final_norm=current_norm,
    residual_vector_verified=(
      current_response is not None
      and current_response.signed_residuals_available
    ),
    conservative_flux_closure_verified=(
      current_response is not None
      and current_response.conservative_flux_closure_verified
    ),
    field_re_solve_verified=field_re_solve_verified,
    directional_residual_correction_verified=directional_correction_seen,
  )
