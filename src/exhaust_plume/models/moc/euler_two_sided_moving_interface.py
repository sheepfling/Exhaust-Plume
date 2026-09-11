"""Research-only driver for a solver-owned two-sided moving interface.

The exact two-sided field iteration can close a terminal trace while keeping
the shock curve fixed.  A physical mixed-regime solve needs one more contract:
the downstream field must return signed interface residuals and a new shock
curve, after which the field is solved again on that new geometry.  This module
owns that orchestration seam, but it does not invent the interface law.  The
caller must provide a solver-owned advance callback; a missing callback, a
zero-motion update, or a lineage mismatch is a typed research stop.

Even a locally converged moving-interface iteration remains below canonical
free-boundary closure, continued shock-cell promotion, and production claims.
Those gates require an independent conservative/entropy audit, refinement,
and external validation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from math import hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.euler_characteristic_field import (
  MocEulerCompanionFieldResult,
)
from exhaust_plume.models.moc.euler_shock_boundary import (
  MocEulerShockBoundaryCurveResult,
)
from exhaust_plume.models.moc.euler_two_sided_field_iteration import (
  MocEulerTwoSidedFieldIterationRequest,
  MocEulerTwoSidedFieldIterationResult,
  solve_euler_two_sided_field_iteration,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID',
  'MocEulerTwoSidedMovingInterfaceStatus',
  'MocEulerTwoSidedInterfaceResponse',
  'MocEulerTwoSidedMovingInterfaceRequest',
  'MocEulerTwoSidedMovingInterfaceIterationRecord',
  'MocEulerTwoSidedMovingInterfaceResult',
  'compute_moc_euler_two_sided_interface_normal_displacements',
  'solve_euler_two_sided_moving_interface',
)


MOC_EULER_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID = (
  'op.moc.euler-two-sided-moving-interface'
)


class MocEulerTwoSidedMovingInterfaceStatus(str, Enum):
  """Typed outcomes of the moving-interface research driver."""

  CONVERGED_RESEARCH_MOVING_INTERFACE = (
    'converged_research_two_sided_moving_interface'
  )
  CONVERGED_RESEARCH_STATIONARY_INTERFACE = (
    'converged_research_two_sided_stationary_interface'
  )
  INVALID_INPUT = 'invalid_input'
  FIELD_ITERATION_REQUIRED = 'two_sided_moving_interface_field_iteration_required'
  INTERFACE_UPDATE_REQUIRED = 'two_sided_moving_interface_update_required'
  RESPONSE_LINEAGE_FAILURE = 'two_sided_moving_interface_response_lineage_failure'
  MOVEMENT_REQUIRED = 'two_sided_moving_interface_motion_required'
  CONSERVATIVE_FLUX_FAILURE = (
    'two_sided_moving_interface_conservative_flux_failure'
  )
  FIELD_RESOLVE_FAILURE = 'two_sided_moving_interface_field_resolve_failure'
  ITERATION_LIMIT = 'two_sided_moving_interface_iteration_limit'


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


def _finite_residuals(
  values: Sequence[float],
  name: str,
) -> tuple[float, ...]:
  residuals = tuple(float(value) for value in values)
  if any(not isfinite(value) or value < 0.0 for value in residuals):
    raise ValueError(f'{name} must contain finite nonnegative values')
  ####
  return residuals


def compute_moc_euler_two_sided_interface_normal_displacements(
  prior_shock_boundary: MocEulerShockBoundaryCurveResult,
  next_shock_boundary: MocEulerShockBoundaryCurveResult,
) -> tuple[float, ...]:
  """Recompute signed normal motion between two identically sampled curves.

  The normal convention is ``(-t_y, t_x)`` for the downstream-ordered shock
  tangent.  Remeshing is deliberately not hidden here: the two curves must
  retain the same sample count so a response cannot silently interpolate or
  match by nearest endpoint.
  """

  if not isinstance(
    prior_shock_boundary,
    MocEulerShockBoundaryCurveResult,
  ) or not isinstance(next_shock_boundary, MocEulerShockBoundaryCurveResult):
    raise TypeError('shock boundaries must be typed Euler shock curves')
  ####
  prior_points = tuple(prior_shock_boundary.shock_points_m)
  next_points = tuple(next_shock_boundary.shock_points_m)
  if len(prior_points) != len(next_points) or len(prior_points) < 2:
    raise ValueError(
      'moving-interface response requires equally sampled shock curves with '
      'at least two points'
    )
  ####
  displacements: list[float] = []
  for index, (prior, next_point) in enumerate(
    zip(prior_points, next_points, strict=True)
  ):
    if index == 0:
      tangent_start = prior_points[0]
      tangent_end = prior_points[1]
    elif index == len(prior_points) - 1:
      tangent_start = prior_points[-2]
      tangent_end = prior_points[-1]
    else:
      tangent_start = prior_points[index - 1]
      tangent_end = prior_points[index + 1]
    ####
    tangent_x = tangent_end[0] - tangent_start[0]
    tangent_y = tangent_end[1] - tangent_start[1]
    tangent_length = hypot(tangent_x, tangent_y)
    if not isfinite(tangent_length) or tangent_length <= 0.0:
      raise ValueError('prior shock boundary contains a degenerate tangent')
    ####
    normal_x = -tangent_y / tangent_length
    normal_y = tangent_x / tangent_length
    displacement = (
      (next_point[0] - prior[0]) * normal_x
      + (next_point[1] - prior[1]) * normal_y
    )
    if not isfinite(displacement):
      raise ValueError('interface normal displacement must be finite')
    ####
    displacements.append(float(displacement))
  ####
  return tuple(displacements)


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceResponse:
  """One solver-owned residual/update packet for the moving shock curve.

  The three flux channels are magnitudes of the mismatch between the current
  downstream field and the proposed interface state.  Their units are kept
  explicit so a caller cannot collapse unrelated residuals into one arbitrary
  dimensionless score.  Solver-owned responses may additionally retain the
  complete signed conservative residual vector for a future coupled solve.
  """

  prior_shock_boundary: MocEulerShockBoundaryCurveResult
  next_shock_boundary: MocEulerShockBoundaryCurveResult
  next_companion_field: MocEulerCompanionFieldResult
  normal_displacements_m: tuple[float, ...]
  mass_flux_residuals_kg_m2_s: tuple[float, ...]
  normal_momentum_residuals_Pa: tuple[float, ...]
  energy_flux_residuals_W_m2: tuple[float, ...]
  response_source: str = (
    'solver-owned-two-sided-euler-moving-interface-response-v1'
  )
  law_id: str = 'solver-owned-two-sided-euler-interface-law-required'
  stationary_equilibrium_candidate: bool = False
  conservative_flux_closure_verified: bool = False
  signed_mass_flux_residuals_kg_m2_s: tuple[float, ...] | None = None
  signed_normal_momentum_residuals_Pa: tuple[float, ...] | None = None
  signed_energy_flux_residuals_W_m2: tuple[float, ...] | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.prior_shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'prior_shock_boundary must be a MocEulerShockBoundaryCurveResult'
      )
    ####
    if not isinstance(
      self.next_shock_boundary,
      MocEulerShockBoundaryCurveResult,
    ):
      raise TypeError(
        'next_shock_boundary must be a MocEulerShockBoundaryCurveResult'
      )
    ####
    if not isinstance(self.next_companion_field, MocEulerCompanionFieldResult):
      raise TypeError(
        'next_companion_field must be a MocEulerCompanionFieldResult'
      )
    ####
    if self.next_companion_field.shock_boundary is not self.next_shock_boundary:
      raise ValueError(
        'next_companion_field must retain the exact proposed shock boundary'
      )
    ####
    if not (
      self.prior_shock_boundary.converged
      and self.prior_shock_boundary.local_euler_verified
      and self.next_shock_boundary.converged
      and self.next_shock_boundary.local_euler_verified
    ):
      raise ValueError(
        'moving-interface responses require locally Euler-verified prior and '
        'next shock boundaries'
      )
    ####
    if not (
      self.next_companion_field.converged
      and self.next_companion_field.state_sampling_available
      and self.next_companion_field.shock_boundary_local_euler_verified
      and self.next_companion_field.companion_boundary_contract_verified
      and self.next_companion_field.pressure_lineage_verified
      and not self.next_companion_field.physical_closure_verified
      and self.next_companion_field.chain_promotion_blocked
      and not self.next_companion_field.production_claim_allowed
    ):
      raise ValueError(
        'moving-interface responses require an open, verified, non-promotable '
        'next companion field'
      )
    ####
    sample_count = len(self.next_shock_boundary.shock_points_m)
    if sample_count < 2:
      raise ValueError('moving-interface responses require at least two samples')
    ####
    displacement = tuple(float(value) for value in self.normal_displacements_m)
    if len(displacement) != sample_count or any(
      not isfinite(value) for value in displacement
    ):
      raise ValueError(
        'normal_displacements_m must be finite and align with the next shock '
        'boundary'
      )
    ####
    object.__setattr__(self, 'normal_displacements_m', displacement)
    for name in (
      'mass_flux_residuals_kg_m2_s',
      'normal_momentum_residuals_Pa',
      'energy_flux_residuals_W_m2',
    ):
      residuals = _finite_residuals(getattr(self, name), name)
      if len(residuals) != sample_count:
        raise ValueError(f'{name} must align with the next shock boundary')
      ####
      object.__setattr__(self, name, residuals)
    ####
    signed_fields = (
      'signed_mass_flux_residuals_kg_m2_s',
      'signed_normal_momentum_residuals_Pa',
      'signed_energy_flux_residuals_W_m2',
    )
    signed_presence = tuple(
      getattr(self, name) is not None for name in signed_fields
    )
    if any(signed_presence) and not all(signed_presence):
      raise ValueError(
        'signed residual channels must be supplied together'
      )
    ####
    for signed_name, magnitude_name in (
      (
        'signed_mass_flux_residuals_kg_m2_s',
        'mass_flux_residuals_kg_m2_s',
      ),
      (
        'signed_normal_momentum_residuals_Pa',
        'normal_momentum_residuals_Pa',
      ),
      (
        'signed_energy_flux_residuals_W_m2',
        'energy_flux_residuals_W_m2',
      ),
    ):
      signed_values = getattr(self, signed_name)
      if signed_values is None:
        continue
      ####
      signed_residuals = tuple(float(value) for value in signed_values)
      if len(signed_residuals) != sample_count or any(
        not isfinite(value) for value in signed_residuals
      ):
        raise ValueError(
          f'{signed_name} must be finite and align with the next shock boundary'
        )
      ####
      magnitudes = getattr(self, magnitude_name)
      if any(
        abs(abs(signed) - magnitude)
        > 1.0e-10 * max(1.0, abs(magnitude))
        for signed, magnitude in zip(signed_residuals, magnitudes, strict=True)
      ):
        raise ValueError(
          f'{signed_name} must agree with the corresponding residual magnitudes'
        )
      ####
      object.__setattr__(self, signed_name, signed_residuals)
    ####
    source = str(self.response_source)
    law_id = str(self.law_id)
    if not source or not law_id:
      raise ValueError('response_source and law_id must be non-empty')
    ####
    if not isinstance(self.stationary_equilibrium_candidate, bool):
      raise TypeError('stationary_equilibrium_candidate must be a bool')
    ####
    if not isinstance(self.conservative_flux_closure_verified, bool):
      raise TypeError('conservative_flux_closure_verified must be a bool')
    ####
    object.__setattr__(self, 'response_source', source)
    object.__setattr__(self, 'law_id', law_id)
  ####

  @property
  def sample_count(self) -> int:
    return len(self.normal_displacements_m)
  ####

  @property
  def maximum_normal_displacement_m(self) -> float:
    return max(
      (abs(value) for value in self.normal_displacements_m),
      default=0.0,
    )
  ####

  @property
  def maximum_mass_flux_residual_kg_m2_s(self) -> float:
    return max(self.mass_flux_residuals_kg_m2_s, default=0.0)
  ####

  @property
  def maximum_normal_momentum_residual_Pa(self) -> float:
    return max(self.normal_momentum_residuals_Pa, default=0.0)
  ####

  @property
  def maximum_energy_flux_residual_W_m2(self) -> float:
    return max(self.energy_flux_residuals_W_m2, default=0.0)
  ####

  @property
  def signed_residuals_available(self) -> bool:
    """Whether the complete signed conservative residual vector is retained."""

    return bool(
      self.signed_mass_flux_residuals_kg_m2_s is not None
      and self.signed_normal_momentum_residuals_Pa is not None
      and self.signed_energy_flux_residuals_W_m2 is not None
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_EULER_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID,
      'prior_shock_sample_count': len(self.prior_shock_boundary.shock_points_m),
      'next_shock_sample_count': len(self.next_shock_boundary.shock_points_m),
      'normal_displacements_m': self.normal_displacements_m,
      'maximum_normal_displacement_m': self.maximum_normal_displacement_m,
      'mass_flux_residuals_kg_m2_s': self.mass_flux_residuals_kg_m2_s,
      'normal_momentum_residuals_Pa': self.normal_momentum_residuals_Pa,
      'energy_flux_residuals_W_m2': self.energy_flux_residuals_W_m2,
      'signed_mass_flux_residuals_kg_m2_s': (
        self.signed_mass_flux_residuals_kg_m2_s
      ),
      'signed_normal_momentum_residuals_Pa': (
        self.signed_normal_momentum_residuals_Pa
      ),
      'signed_energy_flux_residuals_W_m2': (
        self.signed_energy_flux_residuals_W_m2
      ),
      'signed_residuals_available': self.signed_residuals_available,
      'maximum_mass_flux_residual_kg_m2_s': (
        self.maximum_mass_flux_residual_kg_m2_s
      ),
      'maximum_normal_momentum_residual_Pa': (
        self.maximum_normal_momentum_residual_Pa
      ),
      'maximum_energy_flux_residual_W_m2': (
        self.maximum_energy_flux_residual_W_m2
      ),
      'response_source': self.response_source,
      'law_id': self.law_id,
      'stationary_equilibrium_candidate': self.stationary_equilibrium_candidate,
      'conservative_flux_closure_verified': (
        self.conservative_flux_closure_verified
      ),
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedMovingInterfaceRequest:
  """Controls for a bounded re-solve over solver-owned moving geometry."""

  field_request: MocEulerTwoSidedFieldIterationRequest
  maximum_interface_iterations: int = 3
  position_tolerance_m: float = 1.0e-8
  mass_flux_tolerance_kg_m2_s: float = 1.0e-3
  normal_momentum_tolerance_Pa: float = 1.0e-2
  energy_flux_tolerance_W_m2: float = 1.0e-1
  require_interface_motion: bool = True
  allow_stationary_equilibrium: bool = False
  require_conservative_flux_closure: bool = False
  # A residual-passing response is not necessarily a settled front.  When
  # enabled, keep consuming solver-owned responses until the terminal normal
  # update is zero or the bounded iteration budget is exhausted.
  require_terminal_fixed_point: bool = False

  def __post_init__(self) -> None:
    if not isinstance(
      self.field_request,
      MocEulerTwoSidedFieldIterationRequest,
    ):
      raise TypeError(
        'field_request must be a MocEulerTwoSidedFieldIterationRequest'
      )
    ####
    if (
      isinstance(self.maximum_interface_iterations, bool)
      or not isinstance(self.maximum_interface_iterations, int)
      or self.maximum_interface_iterations < 1
    ):
      raise ValueError('maximum_interface_iterations must be a positive integer')
    ####
    for name in (
      'position_tolerance_m',
      'mass_flux_tolerance_kg_m2_s',
      'normal_momentum_tolerance_Pa',
      'energy_flux_tolerance_W_m2',
    ):
      object.__setattr__(
        self,
        name,
        _positive_float(getattr(self, name), name),
      )
    ####
    if not isinstance(self.require_interface_motion, bool):
      raise TypeError('require_interface_motion must be a bool')
    ####
    if not isinstance(self.allow_stationary_equilibrium, bool):
      raise TypeError('allow_stationary_equilibrium must be a bool')
    ####
    if not isinstance(self.require_conservative_flux_closure, bool):
      raise TypeError('require_conservative_flux_closure must be a bool')
    ####
    if not isinstance(self.require_terminal_fixed_point, bool):
      raise TypeError('require_terminal_fixed_point must be a bool')
    ####

  def as_report(self) -> dict[str, object]:
    return {
      'field_request': self.field_request.as_report(),
      'maximum_interface_iterations': self.maximum_interface_iterations,
      'position_tolerance_m': self.position_tolerance_m,
      'mass_flux_tolerance_kg_m2_s': self.mass_flux_tolerance_kg_m2_s,
      'normal_momentum_tolerance_Pa': self.normal_momentum_tolerance_Pa,
      'energy_flux_tolerance_W_m2': self.energy_flux_tolerance_W_m2,
      'require_interface_motion': self.require_interface_motion,
      'allow_stationary_equilibrium': self.allow_stationary_equilibrium,
      'require_conservative_flux_closure': self.require_conservative_flux_closure,
      'require_terminal_fixed_point': self.require_terminal_fixed_point,
      'production_claim_allowed': False,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedMovingInterfaceIterationRecord:
  """Evidence retained for one interface response and exact field re-solve."""

  iteration_index: int
  field_iteration: MocEulerTwoSidedFieldIterationResult
  response: MocEulerTwoSidedInterfaceResponse | None
  next_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  response_lineage_verified: bool
  interface_motion_verified: bool
  response_residuals_verified: bool
  field_re_solve_verified: bool
  stationary_equilibrium_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if (
      isinstance(self.iteration_index, bool)
      or not isinstance(self.iteration_index, int)
      or self.iteration_index < 0
    ):
      raise ValueError('iteration_index must be a nonnegative integer')
    ####
    if not isinstance(
      self.field_iteration,
      MocEulerTwoSidedFieldIterationResult,
    ):
      raise TypeError(
        'field_iteration must be a MocEulerTwoSidedFieldIterationResult'
      )
    ####
    if self.response is not None and not isinstance(
      self.response,
      MocEulerTwoSidedInterfaceResponse,
    ):
      raise TypeError(
        'response must be a MocEulerTwoSidedInterfaceResponse or None'
      )
    ####
    if self.next_field_iteration is not None and not isinstance(
      self.next_field_iteration,
      MocEulerTwoSidedFieldIterationResult,
    ):
      raise TypeError(
        'next_field_iteration must be a MocEulerTwoSidedFieldIterationResult '
        'or None'
      )
    ####
    for name in (
      'response_lineage_verified',
      'interface_motion_verified',
      'response_residuals_verified',
      'field_re_solve_verified',
      'stationary_equilibrium_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'iteration_index': self.iteration_index,
      'field_iteration': self.field_iteration.as_report(),
      'response': None if self.response is None else self.response.as_report(),
      'next_field_iteration': (
        None
        if self.next_field_iteration is None
        else self.next_field_iteration.as_report()
      ),
      'response_lineage_verified': self.response_lineage_verified,
      'interface_motion_verified': self.interface_motion_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'field_re_solve_verified': self.field_re_solve_verified,
      'stationary_equilibrium_verified': self.stationary_equilibrium_verified,
      'message': self.message,
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedMovingInterfaceResult:
  """Research result for the bounded moving-interface/re-solve ladder."""

  status: MocEulerTwoSidedMovingInterfaceStatus
  request: MocEulerTwoSidedMovingInterfaceRequest | None
  records: tuple[MocEulerTwoSidedMovingInterfaceIterationRecord, ...]
  initial_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  final_field_iteration: MocEulerTwoSidedFieldIterationResult | None
  moving_interface_verified: bool
  response_lineage_verified: bool
  interface_motion_verified: bool
  response_residuals_verified: bool
  field_re_solve_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  conservative_flux_closure_required: bool = False
  conservative_flux_closure_verified: bool = False
  stationary_equilibrium_verified: bool = False
  terminal_fixed_point_required: bool = False
  terminal_fixed_point_verified: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedMovingInterfaceStatus,
    ):
      raise TypeError(
        'status must be a MocEulerTwoSidedMovingInterfaceStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocEulerTwoSidedMovingInterfaceRequest,
    ):
      raise TypeError(
        'request must be a MocEulerTwoSidedMovingInterfaceRequest or None'
      )
    ####
    records = tuple(self.records)
    if any(
      not isinstance(record, MocEulerTwoSidedMovingInterfaceIterationRecord)
      for record in records
    ):
      raise TypeError(
        'records must contain MocEulerTwoSidedMovingInterfaceIterationRecord '
        'values'
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
    for name in (
      'moving_interface_verified',
      'response_lineage_verified',
      'interface_motion_verified',
      'response_residuals_verified',
      'field_re_solve_verified',
      'stationary_equilibrium_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'conservative_flux_closure_required',
      'conservative_flux_closure_verified',
      'terminal_fixed_point_required',
      'terminal_fixed_point_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    if self.canonical_free_boundary_verified or self.canonical_euler_verified:
      raise ValueError(
        'moving-interface research results cannot claim canonical closure'
      )
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError(
        'moving-interface research results must retain their promotion block'
      )
    ####
    if self.moving_interface_verified and not (
      self.response_lineage_verified
      and (
        self.interface_motion_verified
        or self.stationary_equilibrium_verified
      )
      and self.response_residuals_verified
      and self.field_re_solve_verified
      and self.final_field_iteration is not None
      and self.final_field_iteration.field_iteration_verified
    ):
      raise ValueError(
        'moving_interface_verified requires an audited interface response and '
        'a verified exact field re-solve'
      )
    ####
    if (
      self.moving_interface_verified
      and self.conservative_flux_closure_required
      and not self.conservative_flux_closure_verified
    ):
      raise ValueError(
        'strict moving-interface results require conservative flux closure '
        'evidence across every accepted response'
      )
    ####
    if (
      self.moving_interface_verified
      and self.terminal_fixed_point_required
      and not self.terminal_fixed_point_verified
    ):
      raise ValueError(
        'terminal fixed-point mode requires a verified zero terminal '
        'interface update'
      )
    ####
    object.__setattr__(self, 'records', records)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return bool(
      self.status
      in (
        MocEulerTwoSidedMovingInterfaceStatus
        .CONVERGED_RESEARCH_MOVING_INTERFACE,
        MocEulerTwoSidedMovingInterfaceStatus
        .CONVERGED_RESEARCH_STATIONARY_INTERFACE,
      )
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'operator_id': MOC_EULER_TWO_SIDED_MOVING_INTERFACE_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'moving_interface_verified': self.moving_interface_verified,
      'response_lineage_verified': self.response_lineage_verified,
      'interface_motion_verified': self.interface_motion_verified,
      'response_residuals_verified': self.response_residuals_verified,
      'field_re_solve_verified': self.field_re_solve_verified,
      'stationary_equilibrium_verified': self.stationary_equilibrium_verified,
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'conservative_flux_closure_required': (
        self.conservative_flux_closure_required
      ),
      'conservative_flux_closure_verified': (
        self.conservative_flux_closure_verified
      ),
      'terminal_fixed_point_required': self.terminal_fixed_point_required,
      'terminal_fixed_point_verified': self.terminal_fixed_point_verified,
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
      'records': tuple(record.as_report() for record in self.records),
      'message': self.message,
      'claim_status': (
        'research-only solver-owned moving-interface/re-solve seam; canonical '
        'free-boundary closure, refinement, physical shock-cell fitting, '
        'external validation, and production claims remain blocked'
      ),
    }
  ####
####


MocEulerTwoSidedInterfaceAdvance = Callable[
  [MocEulerTwoSidedFieldIterationResult, int],
  MocEulerTwoSidedInterfaceResponse,
]


def _failure(
  status: MocEulerTwoSidedMovingInterfaceStatus,
  message: str,
  *,
  request: MocEulerTwoSidedMovingInterfaceRequest | None = None,
  records: Sequence[MocEulerTwoSidedMovingInterfaceIterationRecord] = (),
  initial_field_iteration: MocEulerTwoSidedFieldIterationResult | None = None,
  final_field_iteration: MocEulerTwoSidedFieldIterationResult | None = None,
  response_lineage_verified: bool = False,
  interface_motion_verified: bool = False,
  response_residuals_verified: bool = False,
  field_re_solve_verified: bool = False,
  stationary_equilibrium_verified: bool = False,
  conservative_flux_closure_required: bool = False,
  conservative_flux_closure_verified: bool = False,
  terminal_fixed_point_required: bool = False,
  terminal_fixed_point_verified: bool = False,
) -> MocEulerTwoSidedMovingInterfaceResult:
  return MocEulerTwoSidedMovingInterfaceResult(
    status=status,
    request=request,
    records=tuple(records),
    initial_field_iteration=initial_field_iteration,
    final_field_iteration=final_field_iteration,
    moving_interface_verified=False,
    response_lineage_verified=response_lineage_verified,
    interface_motion_verified=interface_motion_verified,
    response_residuals_verified=response_residuals_verified,
    field_re_solve_verified=field_re_solve_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    conservative_flux_closure_required=(
      request.require_conservative_flux_closure
      if request is not None
      else conservative_flux_closure_required
    ),
    conservative_flux_closure_verified=conservative_flux_closure_verified,
    stationary_equilibrium_verified=stationary_equilibrium_verified,
    terminal_fixed_point_required=(
      request.require_terminal_fixed_point
      if request is not None
      else terminal_fixed_point_required
    ),
    terminal_fixed_point_verified=terminal_fixed_point_verified,
    message=message,
  )


def _response_lineage_and_motion(
  current: MocEulerTwoSidedFieldIterationResult,
  response: MocEulerTwoSidedInterfaceResponse,
  request: MocEulerTwoSidedMovingInterfaceRequest,
) -> tuple[bool, bool, str]:
  if current.shock_boundary is None:
    return False, False, 'current field iteration retained no shock boundary'
  ####
  if response.prior_shock_boundary is not current.shock_boundary:
    return False, False, (
      'interface response prior shock boundary is not the exact current '
      'solver object'
    )
  ####
  try:
    recomputed = compute_moc_euler_two_sided_interface_normal_displacements(
      response.prior_shock_boundary,
      response.next_shock_boundary,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return False, False, f'interface displacement remeasurement failed: {error}'
  ####
  if len(recomputed) != len(response.normal_displacements_m) or any(
    abs(left - right) > request.position_tolerance_m
    for left, right in zip(
      recomputed,
      response.normal_displacements_m,
      strict=True,
    )
  ):
    return False, False, (
      'interface response normal-displacement channel does not match the '
      'solver-owned shock geometry'
    )
  ####
  moved = any(
    abs(value) > request.position_tolerance_m
    for value in recomputed
  )
  if request.require_interface_motion and not moved:
    return True, False, (
      'solver-owned moving-interface response retained the prior geometry; '
      'a fixed shock trace cannot close the moving-interface gate'
    )
  ####
  return True, moved, 'solver-owned shock geometry moved and was independently remeasured'


def _response_residuals_verified(
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


def _response_conservative_flux_verified(
  response: MocEulerTwoSidedInterfaceResponse,
  request: MocEulerTwoSidedMovingInterfaceRequest,
) -> bool:
  return bool(
    _response_residuals_verified(response, request)
    and response.conservative_flux_closure_verified
  )


def solve_euler_two_sided_moving_interface(
  request: MocEulerTwoSidedMovingInterfaceRequest,
  advance_interface: MocEulerTwoSidedInterfaceAdvance | None = None,
) -> MocEulerTwoSidedMovingInterfaceResult:
  """Run exact field/re-solve iterations using an explicit advance law.

  ``advance_interface`` is intentionally required for progress.  It is the
  future solver-owned mixed-wave/free-boundary law, not an interpolation or a
  pressure-profile controller.  The driver only checks its exact lineage,
  re-solves the field on its proposed curve, and keeps the claim ceiling
  closed.
  """

  if not isinstance(request, MocEulerTwoSidedMovingInterfaceRequest):
    return _failure(
      MocEulerTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      'request must be a MocEulerTwoSidedMovingInterfaceRequest',
    )
  ####
  if advance_interface is not None and not callable(advance_interface):
    return _failure(
      MocEulerTwoSidedMovingInterfaceStatus.INVALID_INPUT,
      'advance_interface must be callable when supplied',
      request=request,
    )
  ####
  try:
    initial = solve_euler_two_sided_field_iteration(request.field_request)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocEulerTwoSidedMovingInterfaceStatus.FIELD_ITERATION_REQUIRED,
      f'initial exact two-sided field iteration raised: {error}',
      request=request,
    )
  ####
  if not initial.field_iteration_verified:
    return _failure(
      MocEulerTwoSidedMovingInterfaceStatus.FIELD_ITERATION_REQUIRED,
      'initial exact two-sided field iteration did not pass its local gates; '
      'no interface update or lower-fidelity fallback was attempted',
      request=request,
      initial_field_iteration=initial,
      final_field_iteration=initial,
    )
  ####
  if advance_interface is None:
    return _failure(
      MocEulerTwoSidedMovingInterfaceStatus.INTERFACE_UPDATE_REQUIRED,
      'no solver-owned moving-interface advance law was supplied; fixed '
      'geometry cannot be promoted to a moving/free-boundary solve',
      request=request,
      initial_field_iteration=initial,
      final_field_iteration=initial,
    )
  ####
  records: list[MocEulerTwoSidedMovingInterfaceIterationRecord] = []
  current_request = request.field_request
  current_field = initial
  for iteration_index in range(request.maximum_interface_iterations):
    try:
      response = advance_interface(current_field, iteration_index)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      record = MocEulerTwoSidedMovingInterfaceIterationRecord(
        iteration_index=iteration_index,
        field_iteration=current_field,
        response=None,
        next_field_iteration=None,
        response_lineage_verified=False,
        interface_motion_verified=False,
        response_residuals_verified=False,
        field_re_solve_verified=False,
        message=f'solver-owned interface advance raised: {error}',
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedMovingInterfaceStatus.INTERFACE_UPDATE_REQUIRED,
        record.message,
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=current_field,
      )
    ####
    if not isinstance(response, MocEulerTwoSidedInterfaceResponse):
      record = MocEulerTwoSidedMovingInterfaceIterationRecord(
        iteration_index=iteration_index,
        field_iteration=current_field,
        response=None,
        next_field_iteration=None,
        response_lineage_verified=False,
        interface_motion_verified=False,
        response_residuals_verified=False,
        field_re_solve_verified=False,
        message=(
          'solver-owned interface advance returned no typed residual/update '
          'packet; no fallback was attempted'
        ),
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedMovingInterfaceStatus.INTERFACE_UPDATE_REQUIRED,
        record.message,
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=current_field,
      )
    ####
    lineage_verified, motion_verified, lineage_message = (
      _response_lineage_and_motion(current_field, response, request)
    )
    if not lineage_verified:
      record = MocEulerTwoSidedMovingInterfaceIterationRecord(
        iteration_index=iteration_index,
        field_iteration=current_field,
        response=response,
        next_field_iteration=None,
        response_lineage_verified=False,
        interface_motion_verified=False,
        response_residuals_verified=False,
        field_re_solve_verified=False,
        message=lineage_message,
      )
      records.append(record)
      status = (
        MocEulerTwoSidedMovingInterfaceStatus.MOVEMENT_REQUIRED
        if 'retained the prior geometry' in lineage_message
        else MocEulerTwoSidedMovingInterfaceStatus.RESPONSE_LINEAGE_FAILURE
      )
      return _failure(
        status,
        record.message,
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=current_field,
      )
    ####
    # In terminal-fixed-point mode a later response may legitimately return
    # zero motion after one or more accepted moving updates.  The initial
    # response still has to move when ``require_interface_motion`` is set.
    allow_terminal_zero_motion = bool(
      request.require_terminal_fixed_point
      and records
      and not motion_verified
    )
    if request.require_interface_motion and not motion_verified and not allow_terminal_zero_motion:
      record = MocEulerTwoSidedMovingInterfaceIterationRecord(
        iteration_index=iteration_index,
        field_iteration=current_field,
        response=response,
        next_field_iteration=None,
        response_lineage_verified=True,
        interface_motion_verified=False,
        response_residuals_verified=False,
        field_re_solve_verified=False,
        message=lineage_message,
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedMovingInterfaceStatus.MOVEMENT_REQUIRED,
        record.message,
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=current_field,
      )
    ####
    residuals_verified = _response_residuals_verified(response, request)
    conservative_flux_verified = _response_conservative_flux_verified(
      response,
      request,
    )
    if request.require_conservative_flux_closure and not conservative_flux_verified:
      record = MocEulerTwoSidedMovingInterfaceIterationRecord(
        iteration_index=iteration_index,
        field_iteration=current_field,
        response=response,
        next_field_iteration=None,
        response_lineage_verified=True,
        interface_motion_verified=motion_verified,
        response_residuals_verified=False,
        field_re_solve_verified=False,
        message=(
          'strict moving-interface mode rejected a response without verified '
          'mass, normal-momentum, and energy conservative-flux closure; no '
          'geometry update was consumed'
        ),
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedMovingInterfaceStatus.CONSERVATIVE_FLUX_FAILURE,
        record.message,
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=current_field,
        response_lineage_verified=True,
        interface_motion_verified=motion_verified,
        conservative_flux_closure_required=True,
        conservative_flux_closure_verified=False,
      )
    ####
    next_request = replace(
      current_request,
      shock_boundary=response.next_shock_boundary,
      companion_field=response.next_companion_field,
    )
    try:
      next_field = solve_euler_two_sided_field_iteration(next_request)
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      record = MocEulerTwoSidedMovingInterfaceIterationRecord(
        iteration_index=iteration_index,
        field_iteration=current_field,
        response=response,
        next_field_iteration=None,
        response_lineage_verified=True,
        interface_motion_verified=motion_verified,
        response_residuals_verified=False,
        field_re_solve_verified=False,
        message=f'exact field re-solve raised: {error}',
      )
      records.append(record)
      return _failure(
        MocEulerTwoSidedMovingInterfaceStatus.FIELD_RESOLVE_FAILURE,
        record.message,
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=current_field,
        response_lineage_verified=True,
        interface_motion_verified=motion_verified,
      )
    ####
    field_re_solve_verified = bool(
      next_field.request is next_request
      and next_field.shock_boundary is response.next_shock_boundary
      and next_field.initial_companion_field is response.next_companion_field
      and next_field.field_iteration_verified
    )
    stationary_equilibrium_verified = bool(
      not motion_verified
      and not request.require_interface_motion
      and request.allow_stationary_equilibrium
      and response.stationary_equilibrium_candidate
      and residuals_verified
    )
    terminal_fixed_point_verified = bool(
      residuals_verified
      and response.maximum_normal_displacement_m <= request.position_tolerance_m
      and (
        motion_verified
        or stationary_equilibrium_verified
        or allow_terminal_zero_motion
      )
    )
    record = MocEulerTwoSidedMovingInterfaceIterationRecord(
      iteration_index=iteration_index,
      field_iteration=current_field,
      response=response,
      next_field_iteration=next_field,
      response_lineage_verified=True,
      interface_motion_verified=motion_verified,
      response_residuals_verified=residuals_verified,
      field_re_solve_verified=field_re_solve_verified,
      stationary_equilibrium_verified=stationary_equilibrium_verified,
      message=(
        'solver-owned interface response was consumed by an exact field '
        're-solve; '
        + (
          'declared flux residual tolerances passed'
          if residuals_verified
          else 'declared flux residual tolerances remain open'
        )
      ),
    )
    records.append(record)
    if not field_re_solve_verified:
      return _failure(
        MocEulerTwoSidedMovingInterfaceStatus.FIELD_RESOLVE_FAILURE,
        record.message + '; the re-solved field did not pass its local gates',
        request=request,
        records=records,
        initial_field_iteration=initial,
        final_field_iteration=next_field,
        response_lineage_verified=True,
        interface_motion_verified=motion_verified,
        response_residuals_verified=residuals_verified,
        stationary_equilibrium_verified=stationary_equilibrium_verified,
      )
    ####
    if residuals_verified:
      if request.require_terminal_fixed_point and not terminal_fixed_point_verified:
        current_request = next_request
        current_field = next_field
        continue
      motion_seen = bool(
        any(record.interface_motion_verified for record in records)
      )
      if not (motion_verified or stationary_equilibrium_verified or motion_seen):
        return _failure(
          MocEulerTwoSidedMovingInterfaceStatus.MOVEMENT_REQUIRED,
          'response fluxes passed, but the solver did not declare either '
          'interface motion or an allowed stationary equilibrium',
          request=request,
          records=records,
          initial_field_iteration=initial,
          final_field_iteration=next_field,
          response_lineage_verified=True,
          interface_motion_verified=motion_verified,
          response_residuals_verified=True,
          field_re_solve_verified=True,
          conservative_flux_closure_verified=conservative_flux_verified,
          stationary_equilibrium_verified=False,
          terminal_fixed_point_verified=terminal_fixed_point_verified,
        )
      return MocEulerTwoSidedMovingInterfaceResult(
        status=(
          MocEulerTwoSidedMovingInterfaceStatus
          .CONVERGED_RESEARCH_STATIONARY_INTERFACE
          if stationary_equilibrium_verified
          else MocEulerTwoSidedMovingInterfaceStatus
          .CONVERGED_RESEARCH_MOVING_INTERFACE
        ),
        request=request,
        records=tuple(records),
        initial_field_iteration=initial,
        final_field_iteration=next_field,
        moving_interface_verified=True,
        response_lineage_verified=True,
        interface_motion_verified=bool(motion_verified or motion_seen),
        response_residuals_verified=True,
        field_re_solve_verified=True,
        canonical_free_boundary_verified=False,
        canonical_euler_verified=False,
        chain_promotion_blocked=True,
        production_claim_allowed=False,
        conservative_flux_closure_required=(
          request.require_conservative_flux_closure
        ),
        conservative_flux_closure_verified=conservative_flux_verified,
        stationary_equilibrium_verified=stationary_equilibrium_verified,
        terminal_fixed_point_required=request.require_terminal_fixed_point,
        terminal_fixed_point_verified=terminal_fixed_point_verified,
        message=(
          'solver-owned two-sided interface response and exact field re-solve '
          'met the declared research residual tolerances; canonical '
          'free-boundary closure, refinement, and external validation remain '
          'pending'
        ),
      )
    ####
    current_request = next_request
    current_field = next_field
  ####
  return _failure(
    MocEulerTwoSidedMovingInterfaceStatus.ITERATION_LIMIT,
    'solver-owned moving-interface re-solve ladder reached its iteration '
    'limit before the declared flux residual tolerances passed',
    request=request,
    records=records,
    initial_field_iteration=initial,
    final_field_iteration=current_field,
    response_lineage_verified=bool(records and all(
      record.response_lineage_verified for record in records
    )),
    interface_motion_verified=bool(records and all(
      record.interface_motion_verified for record in records
    )),
    response_residuals_verified=bool(records and all(
      record.response_residuals_verified for record in records
    )),
    field_re_solve_verified=bool(records and all(
      record.field_re_solve_verified for record in records
    )),
    stationary_equilibrium_verified=bool(records and all(
      record.stationary_equilibrium_verified for record in records
    )),
    terminal_fixed_point_required=request.require_terminal_fixed_point,
    terminal_fixed_point_verified=False,
    conservative_flux_closure_verified=bool(records and all(
      record.response is not None
      and record.response.conservative_flux_closure_verified
      and record.response_residuals_verified
      for record in records
    )),
  )
