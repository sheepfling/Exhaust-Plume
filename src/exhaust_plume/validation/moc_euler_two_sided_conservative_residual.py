"""Independent audit for the signed conservative residual solver.

The residual solver owns the trial direction and exact field re-solves.  This
module independently rebuilds each accepted trial, remeasures the signed
mass/momentum/energy vector, and recomputes the directional least-squares
step when the solver reports one.  It is an evidence audit, not a canonical
free-boundary or production gate.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from math import isfinite, sqrt

from exhaust_plume.models.moc.euler_two_sided_conservative_residual_solve import (
  MocEulerTwoSidedConservativeResidualSolveIteration,
  MocEulerTwoSidedConservativeResidualSolveResult,
  MocEulerTwoSidedConservativeResidualSolveStatus,
)
from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationResult,
  solve_euler_two_sided_field_iteration,
)
from exhaust_plume.models.moc.euler_two_sided_interface_law import (
  MocEulerTwoSidedInterfaceLawRequest,
  build_solver_owned_euler_two_sided_interface_response,
)
from exhaust_plume.models.moc.euler_two_sided_moving_interface import (
  MocEulerTwoSidedInterfaceResponse,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_CONSERVATIVE_RESIDUAL_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedConservativeResidualAuditStatus',
  'MocEulerTwoSidedConservativeResidualAudit',
  'measure_moc_euler_two_sided_conservative_residual',
)


MOC_EULER_TWO_SIDED_CONSERVATIVE_RESIDUAL_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-conservative-residual-audit-v1'
)


class MocEulerTwoSidedConservativeResidualAuditStatus(str, Enum):
  """Typed outcomes of the independent residual audit."""

  CONVERGED_RESEARCH_AUDIT = (
    'converged_research_two-sided-conservative-residual-audit'
  )
  INVALID_INPUT = 'invalid_input'
  REQUEST_FAILURE = 'two-sided-conservative-residual-audit-request-failure'
  FIELD_FAILURE = 'two-sided-conservative-residual-audit-field-failure'
  RECORD_FAILURE = 'two-sided-conservative-residual-audit-record-failure'
  RESIDUAL_FAILURE = 'two-sided-conservative-residual-audit-residual-failure'
  DIRECTIONAL_FAILURE = (
    'two-sided-conservative-residual-audit-directional-failure'
  )
  ITERATION_LIMIT = 'two-sided-conservative-residual-audit-iteration-limit'
  PROMOTION_FAILURE = 'two-sided-conservative-residual-audit-promotion-failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedConservativeResidualAudit:
  """Independently remeasured evidence for one residual solve."""

  status: MocEulerTwoSidedConservativeResidualAuditStatus
  result_status: str | None
  request_verified: bool
  initial_field_verified: bool
  final_field_verified: bool
  record_count: int
  record_lineage_verified: bool
  response_lineage_verified: bool
  residual_vector_verified: bool
  descent_verified: bool
  field_re_solve_verified: bool
  directional_correction_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  initial_residual_norm: float | None = None
  final_residual_norm: float | None = None
  maximum_residual_norm_mismatch: float = 0.0
  message: str = ''
  operator_id: str = MOC_EULER_TWO_SIDED_CONSERVATIVE_RESIDUAL_AUDIT_OPERATOR_ID

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedConservativeResidualAuditStatus,
    ):
      raise TypeError('status must be a conservative residual audit status')
    ####
    if self.result_status is not None:
      object.__setattr__(self, 'result_status', str(self.result_status))
    ####
    if (
      isinstance(self.record_count, bool)
      or not isinstance(self.record_count, int)
      or self.record_count < 0
    ):
      raise ValueError('record_count must be a nonnegative integer')
    ####
    for name in (
      'request_verified',
      'initial_field_verified',
      'final_field_verified',
      'record_lineage_verified',
      'response_lineage_verified',
      'residual_vector_verified',
      'descent_verified',
      'field_re_solve_verified',
      'directional_correction_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'initial_residual_norm',
      'final_residual_norm',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    mismatch = float(self.maximum_residual_norm_mismatch)
    if not isfinite(mismatch) or mismatch < 0.0:
      raise ValueError('maximum_residual_norm_mismatch must be finite and nonnegative')
    ####
    object.__setattr__(self, 'maximum_residual_norm_mismatch', mismatch)
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('conservative residual audits must remain promotion-blocked')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return self.status is (
      MocEulerTwoSidedConservativeResidualAuditStatus
      .CONVERGED_RESEARCH_AUDIT
    )

  @property
  def local_consistency_verified(self) -> bool:
    return bool(
      self.converged
      and self.request_verified
      and self.initial_field_verified
      and self.final_field_verified
      and self.record_lineage_verified
      and self.response_lineage_verified
      and self.residual_vector_verified
      and self.descent_verified
      and self.field_re_solve_verified
      and self.directional_correction_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': self.operator_id,
      'status': self.status.value,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'result_status': self.result_status,
      'request_verified': self.request_verified,
      'initial_field_verified': self.initial_field_verified,
      'final_field_verified': self.final_field_verified,
      'record_count': self.record_count,
      'record_lineage_verified': self.record_lineage_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'residual_vector_verified': self.residual_vector_verified,
      'descent_verified': self.descent_verified,
      'field_re_solve_verified': self.field_re_solve_verified,
      'directional_correction_verified': self.directional_correction_verified,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'initial_residual_norm': self.initial_residual_norm,
      'final_residual_norm': self.final_residual_norm,
      'maximum_residual_norm_mismatch': self.maximum_residual_norm_mismatch,
      'claim_status': (
        'research-only independent signed-residual audit; canonical '
        'free-boundary, physical shock-cell, external-validation, and '
        'production claims remain blocked'
      ),
      'message': self.message,
    }


def _failure(
  status: MocEulerTwoSidedConservativeResidualAuditStatus,
  message: str,
  *,
  result_status: str | None = None,
  request_verified: bool = False,
  initial_field_verified: bool = False,
  final_field_verified: bool = False,
  record_count: int = 0,
  record_lineage_verified: bool = False,
  response_lineage_verified: bool = False,
  residual_vector_verified: bool = False,
  descent_verified: bool = False,
  field_re_solve_verified: bool = False,
  directional_correction_verified: bool = False,
  initial_residual_norm: float | None = None,
  final_residual_norm: float | None = None,
  maximum_residual_norm_mismatch: float = 0.0,
) -> MocEulerTwoSidedConservativeResidualAudit:
  return MocEulerTwoSidedConservativeResidualAudit(
    status=status,
    result_status=result_status,
    request_verified=request_verified,
    initial_field_verified=initial_field_verified,
    final_field_verified=final_field_verified,
    record_count=record_count,
    record_lineage_verified=record_lineage_verified,
    response_lineage_verified=response_lineage_verified,
    residual_vector_verified=residual_vector_verified,
    descent_verified=descent_verified,
    field_re_solve_verified=field_re_solve_verified,
    directional_correction_verified=directional_correction_verified,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    initial_residual_norm=initial_residual_norm,
    final_residual_norm=final_residual_norm,
    maximum_residual_norm_mismatch=maximum_residual_norm_mismatch,
    message=message,
  )


def _field_verified(field: MocEulerTwoSidedFieldIterationResult) -> bool:
  return bool(
    field.field_iteration_verified
    and field.final_physical_field is not None
    and field.final_physical_field.physical_field_verified
  )


def _scaled_vector(
  response: MocEulerTwoSidedInterfaceResponse,
  result: MocEulerTwoSidedConservativeResidualSolveResult,
) -> tuple[float, ...]:
  request = result.request
  if request is None:
    raise ValueError('residual result did not retain its request')
  moving = request.moving_request
  if not response.signed_residuals_available:
    raise ValueError('response did not retain all signed residual channels')
  mass = response.signed_mass_flux_residuals_kg_m2_s
  momentum = response.signed_normal_momentum_residuals_Pa
  energy = response.signed_energy_flux_residuals_W_m2
  assert mass is not None
  assert momentum is not None
  assert energy is not None
  if not len(mass) == len(momentum) == len(energy) or not mass:
    raise ValueError('signed residual channels are not aligned and non-empty')
  values: list[float] = []
  for mass_value, momentum_value, energy_value in zip(
    mass,
    momentum,
    energy,
    strict=True,
  ):
    values.extend(
      (
        float(mass_value) / moving.mass_flux_tolerance_kg_m2_s,
        float(momentum_value) / moving.normal_momentum_tolerance_Pa,
        float(energy_value) / moving.energy_flux_tolerance_W_m2,
      )
    )
  if any(not isfinite(value) for value in values):
    raise ValueError('scaled residual vector is non-finite')
  ####
  return tuple(values)


def _norm(values: tuple[float, ...]) -> float:
  if not values:
    raise ValueError('residual vector must be non-empty')
  value = sqrt(sum(item * item for item in values) / len(values))
  if not isfinite(value):
    raise ValueError('residual norm is non-finite')
  ####
  return value


def _close(first: float, second: float) -> bool:
  return bool(abs(first - second) <= 1.0e-8 * max(1.0, abs(first), abs(second)))


def _points_match(
  first: tuple[tuple[float, float], ...],
  second: tuple[tuple[float, float], ...],
) -> bool:
  return bool(
    len(first) == len(second)
    and all(
      abs(left[0] - right[0]) <= 1.0e-9 * max(1.0, abs(left[0]), abs(right[0]))
      and abs(left[1] - right[1]) <= 1.0e-9 * max(1.0, abs(left[1]), abs(right[1]))
      for left, right in zip(first, second, strict=True)
    )
  )


def _measure(
  field: MocEulerTwoSidedFieldIterationResult,
  law_request: MocEulerTwoSidedInterfaceLawRequest,
  result: MocEulerTwoSidedConservativeResidualSolveResult,
) -> MocEulerTwoSidedInterfaceResponse:
  response_result = build_solver_owned_euler_two_sided_interface_response(
    field,
    replace(law_request, require_conservative_flux_closure=False),
  )
  if response_result.response is None:
    raise ValueError(response_result.message)
  ####
  _scaled_vector(response_result.response, result)
  return response_result.response


def _directional_step(
  current: tuple[float, ...],
  probe: tuple[float, ...],
  probe_fraction: float,
  maximum_fraction: float,
) -> float | None:
  if len(current) != len(probe) or not current:
    raise ValueError('directional vectors must be aligned and non-empty')
  ####
  derivative = tuple(
    (right - left) / probe_fraction
    for left, right in zip(current, probe, strict=True)
  )
  denominator = sum(value * value for value in derivative)
  if not isfinite(denominator) or denominator <= 1.0e-24:
    return None
  numerator = sum(
    left * slope for left, slope in zip(current, derivative, strict=True)
  )
  raw = -numerator / denominator
  if not isfinite(raw) or raw <= 0.0:
    return None
  ####
  return min(maximum_fraction, raw)


def _trial(
  field: MocEulerTwoSidedFieldIterationResult,
  law_request: MocEulerTwoSidedInterfaceLawRequest,
  step_fraction: float,
  iteration_index: int,
  result: MocEulerTwoSidedConservativeResidualSolveResult,
) -> tuple[
  MocEulerTwoSidedInterfaceResponse,
  MocEulerTwoSidedFieldIterationResult,
  MocEulerTwoSidedInterfaceResponse,
  float,
  tuple[float, ...],
]:
  trial_request = replace(
    law_request,
    pseudo_time_step_s=law_request.pseudo_time_step_s * step_fraction,
    require_conservative_flux_closure=False,
  )
  trial_result = build_solver_owned_euler_two_sided_interface_response(
    field,
    trial_request,
    iteration_index=iteration_index,
  )
  trial_response = trial_result.response
  if trial_response is None:
    raise ValueError(trial_result.message)
  ####
  if field.request is None:
    raise ValueError('trial field did not retain a field request')
  next_request = replace(
    field.request,
    shock_boundary=trial_response.next_shock_boundary,
    companion_field=trial_response.next_companion_field,
  )
  next_field = solve_euler_two_sided_field_iteration(next_request)
  if not _field_verified(next_field):
    raise ValueError(
      'independent exact field re-solve did not pass its local gates: '
      f'{next_field.status.value}'
    )
  ####
  measured = _measure(next_field, trial_request, result)
  vector = _scaled_vector(measured, result)
  return trial_response, next_field, measured, _norm(vector), vector


def measure_moc_euler_two_sided_conservative_residual(
  result: MocEulerTwoSidedConservativeResidualSolveResult,
) -> MocEulerTwoSidedConservativeResidualAudit:
  """Independently remeasure a solver-owned conservative residual result."""

  if not isinstance(
    result,
    MocEulerTwoSidedConservativeResidualSolveResult,
  ):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.INVALID_INPUT,
      'result must be a typed conservative residual solve result',
    )
  ####
  request = result.request
  if request is None:
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.REQUEST_FAILURE,
      'result did not retain its solver request',
      result_status=result.status.value,
    )
  ####
  initial = result.initial_field_iteration
  final = result.final_field_iteration
  if initial is None or not _field_verified(initial):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.FIELD_FAILURE,
      'result did not retain a verified initial exact field',
      result_status=result.status.value,
      request_verified=True,
    )
  ####
  if final is None or not _field_verified(final):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.FIELD_FAILURE,
      'result did not retain a verified final exact field',
      result_status=result.status.value,
      request_verified=True,
      initial_field_verified=True,
    )
  ####
  try:
    initial_response = _measure(initial, request.law_request, result)
    initial_norm = _norm(_scaled_vector(initial_response, result))
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.RESIDUAL_FAILURE,
      f'independent initial residual measurement failed: {error}',
      result_status=result.status.value,
      request_verified=True,
      initial_field_verified=True,
      final_field_verified=True,
    )
  ####
  if result.initial_residual_norm is None or not _close(
    initial_norm,
    result.initial_residual_norm,
  ):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.RESIDUAL_FAILURE,
      'independent initial residual norm disagreed with the retained result',
      result_status=result.status.value,
      request_verified=True,
      initial_field_verified=True,
      final_field_verified=True,
      initial_residual_norm=initial_norm,
    )
  ####
  current = initial
  record_lineage_verified = True
  response_lineage_verified = True
  residual_vector_verified = initial_response.signed_residuals_available
  descent_verified = True
  field_re_solve_verified = True
  directional_verified = True
  maximum_mismatch = 0.0
  for record in result.records:
    if not isinstance(
      record,
      MocEulerTwoSidedConservativeResidualSolveIteration,
    ):
      return _failure(
        MocEulerTwoSidedConservativeResidualAuditStatus.RECORD_FAILURE,
        'result records contain an unexpected value',
        result_status=result.status.value,
        request_verified=True,
        initial_field_verified=True,
        final_field_verified=True,
        record_count=len(result.records),
      )
    ####
    record_lineage_verified = record_lineage_verified and record.field_iteration is current
    if not record.accepted or record.next_field_iteration is None:
      return _failure(
        MocEulerTwoSidedConservativeResidualAuditStatus.RECORD_FAILURE,
        'research residual audit requires every retained record to be accepted',
        result_status=result.status.value,
        request_verified=True,
        initial_field_verified=True,
        final_field_verified=True,
        record_count=len(result.records),
        record_lineage_verified=record_lineage_verified,
      )
    ####
    try:
      current_response = _measure(current, request.law_request, result)
      current_vector = _scaled_vector(current_response, result)
      current_norm = _norm(current_vector)
      if record.residual_norm_before is None:
        raise ValueError('record did not retain residual_norm_before')
      maximum_mismatch = max(
        maximum_mismatch,
        abs(current_norm - record.residual_norm_before),
      )
      if not _close(current_norm, record.residual_norm_before):
        raise ValueError('record residual_norm_before disagreed with remeasurement')
      ####
      trial_response, next_field, measured, after, measured_vector = _trial(
        current,
        request.law_request,
        record.step_fraction,
        record.iteration_index,
        result,
      )
      if record.response is None or record.measured_response is None:
        raise ValueError('record did not retain trial and measured responses')
      ####
      response_lineage_verified = response_lineage_verified and bool(
        trial_response.prior_shock_boundary is current.shock_boundary
        and _points_match(
          trial_response.next_shock_boundary.shock_points_m,
          record.response.next_shock_boundary.shock_points_m,
        )
        and _points_match(
          measured.prior_shock_boundary.shock_points_m,
          record.measured_response.prior_shock_boundary.shock_points_m,
        )
        and _points_match(
          next_field.shock_boundary.shock_points_m
          if next_field.shock_boundary is not None
          else (),
          record.next_field_iteration.shock_boundary.shock_points_m
          if record.next_field_iteration.shock_boundary is not None
          else (),
        )
      )
      if not response_lineage_verified:
        raise ValueError('record response or exact-field lineage disagreed')
      ####
      measured_norm = _norm(measured_vector)
      if record.residual_norm_after is None:
        raise ValueError('record did not retain residual_norm_after')
      maximum_mismatch = max(
        maximum_mismatch,
        abs(measured_norm - record.residual_norm_after),
      )
      if not _close(measured_norm, record.residual_norm_after):
        raise ValueError('record residual_norm_after disagreed with remeasurement')
      if not measured_norm < current_norm:
        raise ValueError('accepted record did not strictly descend independently')
      ####
      residual_vector_verified = residual_vector_verified and measured.signed_residuals_available
      descent_verified = descent_verified and record.residual_descent_verified
      field_re_solve_verified = field_re_solve_verified and bool(
        record.field_re_solve_verified and _field_verified(next_field)
      )
      ####
      if record.directional_jacobian_verified:
        probe_fraction = record.jacobian_probe_step_fraction
        if probe_fraction is None or record.jacobian_probe_residual_norm is None:
          raise ValueError('directional record omitted its Jacobian probe evidence')
        probe = _trial(
          current,
          request.law_request,
          probe_fraction,
          record.iteration_index,
          result,
        )
        probe_norm = probe[3]
        if not _close(probe_norm, record.jacobian_probe_residual_norm):
          raise ValueError('directional Jacobian probe norm disagreed')
        expected_step = _directional_step(
          current_vector,
          probe[4],
          probe_fraction,
          request.maximum_directional_step_fraction,
        )
        if expected_step is None or record.directional_step_fraction is None:
          raise ValueError('directional record omitted its computed step')
        if not _close(expected_step, record.directional_step_fraction):
          raise ValueError('directional least-squares step disagreed')
      else:
        directional_verified = directional_verified and not (
          request.use_directional_residual_correction
          and record.step_source == 'directional-least-squares-correction'
        )
      ####
      current = record.next_field_iteration
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocEulerTwoSidedConservativeResidualAuditStatus.RECORD_FAILURE,
        f'independent residual record audit failed: {error}',
        result_status=result.status.value,
        request_verified=True,
        initial_field_verified=True,
        final_field_verified=True,
        record_count=len(result.records),
        record_lineage_verified=record_lineage_verified,
        response_lineage_verified=response_lineage_verified,
        residual_vector_verified=residual_vector_verified,
        descent_verified=False,
        field_re_solve_verified=field_re_solve_verified,
        directional_correction_verified=directional_verified,
        initial_residual_norm=initial_norm,
        maximum_residual_norm_mismatch=maximum_mismatch,
      )
  ####
  try:
    final_response = _measure(current, request.law_request, result)
    final_norm = _norm(_scaled_vector(final_response, result))
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.RESIDUAL_FAILURE,
      f'independent final residual measurement failed: {error}',
      result_status=result.status.value,
      request_verified=True,
      initial_field_verified=True,
      final_field_verified=True,
      record_count=len(result.records),
      record_lineage_verified=record_lineage_verified,
      response_lineage_verified=response_lineage_verified,
      residual_vector_verified=residual_vector_verified,
      descent_verified=descent_verified,
      field_re_solve_verified=field_re_solve_verified,
      directional_correction_verified=directional_verified,
      initial_residual_norm=initial_norm,
      maximum_residual_norm_mismatch=maximum_mismatch,
    )
  ####
  if result.final_residual_norm is None or not _close(
    final_norm,
    result.final_residual_norm,
  ):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.RESIDUAL_FAILURE,
      'independent final residual norm disagreed with the retained result',
      result_status=result.status.value,
      request_verified=True,
      initial_field_verified=True,
      final_field_verified=True,
      record_count=len(result.records),
      record_lineage_verified=record_lineage_verified,
      response_lineage_verified=response_lineage_verified,
      residual_vector_verified=residual_vector_verified,
      descent_verified=descent_verified,
      field_re_solve_verified=field_re_solve_verified,
      directional_correction_verified=directional_verified,
      initial_residual_norm=initial_norm,
      final_residual_norm=final_norm,
      maximum_residual_norm_mismatch=max(
        maximum_mismatch,
        abs(final_norm - result.final_residual_norm),
      ),
    )
  ####
  if request.use_directional_residual_correction and result.records:
    directional_verified = directional_verified and all(
      record.directional_jacobian_verified
      for record in result.records
    )
  ####
  common = dict(
    result_status=result.status.value,
    request_verified=True,
    initial_field_verified=True,
    final_field_verified=True,
    record_count=len(result.records),
    record_lineage_verified=record_lineage_verified,
    response_lineage_verified=response_lineage_verified,
    residual_vector_verified=residual_vector_verified,
    descent_verified=descent_verified,
    field_re_solve_verified=field_re_solve_verified,
    directional_correction_verified=directional_verified,
    initial_residual_norm=initial_norm,
    final_residual_norm=final_norm,
    maximum_residual_norm_mismatch=maximum_mismatch,
  )
  ####
  if result.status is not (
    MocEulerTwoSidedConservativeResidualSolveStatus
    .CONVERGED_RESEARCH_RESIDUAL
  ):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.ITERATION_LIMIT,
      'independent residual evidence is consistent but the solver result '
      'did not reach its declared residual tolerances',
      **common,
    )
  ####
  if not (
    record_lineage_verified
    and response_lineage_verified
    and residual_vector_verified
    and descent_verified
    and field_re_solve_verified
    and directional_verified
  ):
    return _failure(
      MocEulerTwoSidedConservativeResidualAuditStatus.PROMOTION_FAILURE,
      'independent residual evidence did not satisfy every local audit gate',
      **common,
    )
  ####
  return MocEulerTwoSidedConservativeResidualAudit(
    status=(
      MocEulerTwoSidedConservativeResidualAuditStatus
      .CONVERGED_RESEARCH_AUDIT
    ),
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent exact-field re-solves reproduced the signed residual '
      'norms and directional correction evidence; canonical closure remains '
      'blocked'
    ),
    **common,
  )
