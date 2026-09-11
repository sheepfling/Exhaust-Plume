"""Cross-resolution audit for the solver-owned interface-response law.

This audit measures the response law on freshly solved exact two-sided fields.
It requires independent local audits, increasing retained resolution, finite
conservative channels, and a non-increasing/reducing normal-momentum residual.
It deliberately reports cross-case evidence separately: a single fixture
ladder cannot authorize canonical free-boundary closure or production use.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Sequence

from exhaust_plume.models.moc.euler_two_sided_interface_law import (
  MocEulerTwoSidedInterfaceLawResult,
)
from exhaust_plume.validation.moc_euler_two_sided_interface_law import (
  MocEulerTwoSidedInterfaceLawAudit,
  measure_moc_euler_two_sided_interface_law,
)

__all__ = (
  'MOC_EULER_TWO_SIDED_INTERFACE_LAW_REFINEMENT_AUDIT_OPERATOR_ID',
  'MocEulerTwoSidedInterfaceLawRefinementCase',
  'MocEulerTwoSidedInterfaceLawRefinementStatus',
  'MocEulerTwoSidedInterfaceLawRefinementMeasurement',
  'measure_moc_euler_two_sided_interface_law_refinement',
)


MOC_EULER_TWO_SIDED_INTERFACE_LAW_REFINEMENT_AUDIT_OPERATOR_ID = (
  'op.moc.euler-two-sided-solver-owned-interface-law-refinement-audit'
)


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceLawRefinementCase:
  """One freshly solved interface-law result at a declared resolution."""

  case_id: str
  resolution_sample_count: int
  result: MocEulerTwoSidedInterfaceLawResult

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    ####
    if (
      isinstance(self.resolution_sample_count, bool)
      or not isinstance(self.resolution_sample_count, int)
      or self.resolution_sample_count < 3
    ):
      raise ValueError('resolution_sample_count must be an integer >= 3')
    ####
    if not isinstance(self.result, MocEulerTwoSidedInterfaceLawResult):
      raise TypeError(
        'result must be a MocEulerTwoSidedInterfaceLawResult'
      )
    ####
    current = self.result.current_field_iteration
    if current is not None and current.shock_boundary is not None:
      if len(current.shock_boundary.shock_points_m) != self.resolution_sample_count:
        raise ValueError(
          'resolution_sample_count must match the exact current shock sample count'
        )
    ####
    object.__setattr__(self, 'case_id', case_id)
  ####
####


class MocEulerTwoSidedInterfaceLawRefinementStatus(str, Enum):
  """Typed outcomes for the independent response-law ladder."""

  CONVERGED_LOCAL_REFINEMENT = (
    'converged-two-sided-interface-law-local-refinement'
  )
  CONVERGED_CROSS_CASE_REFINEMENT = (
    'converged-two-sided-interface-law-cross-case-refinement'
  )
  INVALID_INPUT = 'invalid_input'
  CASE_FAILURE = 'two-sided-interface-law-refinement-case-failure'
  RESOLUTION_ORDER_FAILURE = (
    'two-sided-interface-law-refinement-resolution-order-failure'
  )
  RESPONSE_MODE_FAILURE = (
    'two-sided-interface-law-refinement-response-mode-failure'
  )
  RESIDUAL_FAILURE = 'two-sided-interface-law-refinement-residual-failure'
  FLAG_FAILURE = 'two-sided-interface-law-refinement-flag-failure'


@dataclass(frozen=True, slots=True)
class MocEulerTwoSidedInterfaceLawRefinementMeasurement:
  """Independent resolution evidence below canonical promotion."""

  status: MocEulerTwoSidedInterfaceLawRefinementStatus
  cases: tuple[MocEulerTwoSidedInterfaceLawRefinementCase, ...]
  audits: tuple[MocEulerTwoSidedInterfaceLawAudit, ...]
  case_ids: tuple[str, ...]
  resolution_sample_counts: tuple[int, ...]
  maximum_interface_normal_speeds_m_s: tuple[float, ...]
  maximum_mass_flux_residuals_kg_m2_s: tuple[float, ...]
  maximum_normal_momentum_residuals_Pa: tuple[float, ...]
  maximum_energy_flux_residuals_W_m2: tuple[float, ...]
  case_audits_verified: bool
  case_identity_verified: bool
  response_mode_identity_verified: bool
  resolution_order_verified: bool
  residuals_finite: bool
  mass_residuals_verified: bool
  energy_residuals_verified: bool
  momentum_nonincreasing_verified: bool
  momentum_reduction_verified: bool
  cross_case_verified: bool
  local_refinement_verified: bool
  refinement_convergence_verified: bool
  canonical_free_boundary_verified: bool
  canonical_euler_verified: bool
  chain_promotion_blocked: bool
  production_claim_allowed: bool
  fidelity_flags_verified: bool
  refinement_tolerance: float = 1.0e-8
  mass_residual_tolerance_kg_m2_s: float = 1.0e-6
  energy_residual_tolerance_W_m2: float = 1.0e-2
  message: str = ''
  operator_id: str = (
    MOC_EULER_TWO_SIDED_INTERFACE_LAW_REFINEMENT_AUDIT_OPERATOR_ID
  )

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocEulerTwoSidedInterfaceLawRefinementStatus,
    ):
      raise TypeError('status must be an interface-law refinement status')
    ####
    cases = tuple(self.cases)
    audits = tuple(self.audits)
    if len(cases) != len(audits):
      raise ValueError('cases and audits must have equal lengths')
    ####
    if any(
      not isinstance(case, MocEulerTwoSidedInterfaceLawRefinementCase)
      for case in cases
    ):
      raise TypeError('cases must contain typed interface-law cases')
    ####
    if any(
      not isinstance(audit, MocEulerTwoSidedInterfaceLawAudit)
      for audit in audits
    ):
      raise TypeError('audits must contain typed interface-law audits')
    ####
    case_ids = tuple(str(value) for value in self.case_ids)
    resolutions = tuple(self.resolution_sample_counts)
    speeds = tuple(float(value) for value in self.maximum_interface_normal_speeds_m_s)
    mass = tuple(float(value) for value in self.maximum_mass_flux_residuals_kg_m2_s)
    momentum = tuple(float(value) for value in self.maximum_normal_momentum_residuals_Pa)
    energy = tuple(float(value) for value in self.maximum_energy_flux_residuals_W_m2)
    if not (
      len(cases)
      == len(case_ids)
      == len(resolutions)
      == len(speeds)
      == len(mass)
      == len(momentum)
      == len(energy)
    ):
      raise ValueError('refinement summaries must match the case count')
    ####
    if any(
      isinstance(value, bool) or not isinstance(value, int) or value < 0
      for value in resolutions
    ):
      raise ValueError('resolution sample counts must be nonnegative integers')
    ####
    for name, values in (
      ('maximum_interface_normal_speeds_m_s', speeds),
      ('maximum_mass_flux_residuals_kg_m2_s', mass),
      ('maximum_normal_momentum_residuals_Pa', momentum),
      ('maximum_energy_flux_residuals_W_m2', energy),
    ):
      if any(not isfinite(value) or value < 0.0 for value in values):
        raise ValueError(f'{name} must contain finite nonnegative values')
    ####
    for name in (
      'case_audits_verified',
      'case_identity_verified',
      'response_mode_identity_verified',
      'resolution_order_verified',
      'residuals_finite',
      'mass_residuals_verified',
      'energy_residuals_verified',
      'momentum_nonincreasing_verified',
      'momentum_reduction_verified',
      'cross_case_verified',
      'local_refinement_verified',
      'refinement_convergence_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
      'fidelity_flags_verified',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    ####
    for name in (
      'refinement_tolerance',
      'mass_residual_tolerance_kg_m2_s',
      'energy_residual_tolerance_W_m2',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    if self.canonical_free_boundary_verified or self.canonical_euler_verified:
      raise ValueError('research refinement cannot claim canonical closure')
    ####
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('research refinement must retain its promotion block')
    ####
    operator_id = str(self.operator_id)
    if not operator_id:
      raise ValueError('operator_id must be non-empty')
    ####
    object.__setattr__(self, 'cases', cases)
    object.__setattr__(self, 'audits', audits)
    object.__setattr__(self, 'case_ids', case_ids)
    object.__setattr__(self, 'resolution_sample_counts', resolutions)
    object.__setattr__(self, 'maximum_interface_normal_speeds_m_s', speeds)
    object.__setattr__(self, 'maximum_mass_flux_residuals_kg_m2_s', mass)
    object.__setattr__(self, 'maximum_normal_momentum_residuals_Pa', momentum)
    object.__setattr__(self, 'maximum_energy_flux_residuals_W_m2', energy)
    object.__setattr__(self, 'operator_id', operator_id)
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    return self.status in (
      MocEulerTwoSidedInterfaceLawRefinementStatus.CONVERGED_LOCAL_REFINEMENT,
      MocEulerTwoSidedInterfaceLawRefinementStatus.CONVERGED_CROSS_CASE_REFINEMENT,
    )
  ####

  @property
  def local_consistency_verified(self) -> bool:
    """Whether the local resolution evidence is internally consistent."""

    return bool(
      self.converged
      and self.case_audits_verified
      and self.case_identity_verified
      and self.response_mode_identity_verified
      and self.resolution_order_verified
      and self.residuals_finite
      and self.mass_residuals_verified
      and self.energy_residuals_verified
      and self.momentum_nonincreasing_verified
      and self.momentum_reduction_verified
      and self.local_refinement_verified
      and self.refinement_convergence_verified
      and (
        self.status
        is not MocEulerTwoSidedInterfaceLawRefinementStatus.CONVERGED_CROSS_CASE_REFINEMENT
        or self.cross_case_verified
      )
      and self.fidelity_flags_verified
      and not self.canonical_free_boundary_verified
      and not self.canonical_euler_verified
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  def as_report(self) -> dict[str, object]:
    return {
      'status': self.status.value,
      'operator_id': self.operator_id,
      'converged': self.converged,
      'local_consistency_verified': self.local_consistency_verified,
      'case_ids': list(self.case_ids),
      'resolution_sample_counts': list(self.resolution_sample_counts),
      'maximum_interface_normal_speeds_m_s': list(
        self.maximum_interface_normal_speeds_m_s
      ),
      'maximum_mass_flux_residuals_kg_m2_s': list(
        self.maximum_mass_flux_residuals_kg_m2_s
      ),
      'maximum_normal_momentum_residuals_Pa': list(
        self.maximum_normal_momentum_residuals_Pa
      ),
      'maximum_energy_flux_residuals_W_m2': list(
        self.maximum_energy_flux_residuals_W_m2
      ),
      'case_audits_verified': self.case_audits_verified,
      'case_identity_verified': self.case_identity_verified,
      'response_mode_identity_verified': self.response_mode_identity_verified,
      'resolution_order_verified': self.resolution_order_verified,
      'residuals_finite': self.residuals_finite,
      'mass_residuals_verified': self.mass_residuals_verified,
      'energy_residuals_verified': self.energy_residuals_verified,
      'momentum_nonincreasing_verified': self.momentum_nonincreasing_verified,
      'momentum_reduction_verified': self.momentum_reduction_verified,
      'cross_case_verified': self.cross_case_verified,
      'local_refinement_verified': self.local_refinement_verified,
      'refinement_convergence_verified': self.refinement_convergence_verified,
      'canonical_free_boundary_verified': False,
      'canonical_euler_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'fidelity_flags_verified': self.fidelity_flags_verified,
      'audits': [audit.as_report() for audit in self.audits],
      'refinement_tolerance': self.refinement_tolerance,
      'mass_residual_tolerance_kg_m2_s': self.mass_residual_tolerance_kg_m2_s,
      'energy_residual_tolerance_W_m2': self.energy_residual_tolerance_W_m2,
      'message': self.message,
    }
  ####
####


def _failure(
  status: MocEulerTwoSidedInterfaceLawRefinementStatus,
  message: str,
  *,
  cases: Sequence[MocEulerTwoSidedInterfaceLawRefinementCase] = (),
  audits: Sequence[MocEulerTwoSidedInterfaceLawAudit] = (),
  case_ids: Sequence[str] = (),
  resolutions: Sequence[int] = (),
  speeds: Sequence[float] = (),
  mass: Sequence[float] = (),
  momentum: Sequence[float] = (),
  energy: Sequence[float] = (),
  case_audits_verified: bool = False,
  case_identity_verified: bool = False,
  response_mode_identity_verified: bool = False,
  resolution_order_verified: bool = False,
  residuals_finite: bool = False,
  mass_residuals_verified: bool = False,
  energy_residuals_verified: bool = False,
  momentum_nonincreasing_verified: bool = False,
  momentum_reduction_verified: bool = False,
  cross_case_verified: bool = False,
  local_refinement_verified: bool = False,
  refinement_convergence_verified: bool = False,
  fidelity_flags_verified: bool = False,
  refinement_tolerance: float = 1.0e-8,
  mass_residual_tolerance_kg_m2_s: float = 1.0e-6,
  energy_residual_tolerance_W_m2: float = 1.0e-2,
) -> MocEulerTwoSidedInterfaceLawRefinementMeasurement:
  return MocEulerTwoSidedInterfaceLawRefinementMeasurement(
    status=status,
    cases=tuple(cases),
    audits=tuple(audits),
    case_ids=tuple(case_ids),
    resolution_sample_counts=tuple(resolutions),
    maximum_interface_normal_speeds_m_s=tuple(speeds),
    maximum_mass_flux_residuals_kg_m2_s=tuple(mass),
    maximum_normal_momentum_residuals_Pa=tuple(momentum),
    maximum_energy_flux_residuals_W_m2=tuple(energy),
    case_audits_verified=case_audits_verified,
    case_identity_verified=case_identity_verified,
    response_mode_identity_verified=response_mode_identity_verified,
    resolution_order_verified=resolution_order_verified,
    residuals_finite=residuals_finite,
    mass_residuals_verified=mass_residuals_verified,
    energy_residuals_verified=energy_residuals_verified,
    momentum_nonincreasing_verified=momentum_nonincreasing_verified,
    momentum_reduction_verified=momentum_reduction_verified,
    cross_case_verified=cross_case_verified,
    local_refinement_verified=local_refinement_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    fidelity_flags_verified=fidelity_flags_verified,
    refinement_tolerance=refinement_tolerance,
    mass_residual_tolerance_kg_m2_s=mass_residual_tolerance_kg_m2_s,
    energy_residual_tolerance_W_m2=energy_residual_tolerance_W_m2,
    message=message,
  )


def _case_signature(
  case: MocEulerTwoSidedInterfaceLawRefinementCase,
) -> tuple[float, ...]:
  current = case.result.current_field_iteration
  if current is None or current.shock_boundary is None:
    return ()
  ####
  shock = current.shock_boundary
  if len(shock.upstream_states) < 2 or len(shock.downstream_states) < 2:
    return ()
  ####
  upstream = shock.upstream_states[1]
  downstream = shock.downstream_states[1]
  return tuple(
    round(float(value), 12)
    for value in (
      shock.shock_points_m[1][0],
      shock.shock_points_m[1][1],
      upstream.theta_rad,
      upstream.mach,
      downstream.theta_rad,
      downstream.mach,
    )
  )


def _response_mode_signature(
  case: MocEulerTwoSidedInterfaceLawRefinementCase,
) -> tuple[object, ...]:
  """Identify the response mode that a resolution ladder is measuring.

  A stationary front-limit response and an interior moving response can share
  the same retained shock geometry while representing different equations.
  They must not be mixed into one refinement trend.
  """

  request = case.result.request
  response = case.result.response
  if request is None or response is None:
    return ()
  ####
  return (
    response.response_source,
    response.law_id,
    round(float(request.downstream_probe_fraction), 12),
    request.anchor_endpoint_samples,
    request.branch.value,
    response.stationary_equilibrium_candidate,
  )


def measure_moc_euler_two_sided_interface_law_refinement(
  cases: Sequence[MocEulerTwoSidedInterfaceLawRefinementCase],
  *,
  refinement_tolerance: float = 1.0e-8,
  mass_residual_tolerance_kg_m2_s: float = 1.0e-6,
  energy_residual_tolerance_W_m2: float = 1.0e-2,
) -> MocEulerTwoSidedInterfaceLawRefinementMeasurement:
  """Independently audit a fresh resolution ladder for the response law."""

  try:
    tolerance = float(refinement_tolerance)
    mass_tolerance = float(mass_residual_tolerance_kg_m2_s)
    energy_tolerance = float(energy_residual_tolerance_W_m2)
  except (TypeError, ValueError):
    return _failure(
      MocEulerTwoSidedInterfaceLawRefinementStatus.INVALID_INPUT,
      'refinement tolerances must be numeric',
    )
  ####
  if not all(
    isfinite(value) and value > 0.0
    for value in (tolerance, mass_tolerance, energy_tolerance)
  ):
    return _failure(
      MocEulerTwoSidedInterfaceLawRefinementStatus.INVALID_INPUT,
      'refinement tolerances must be finite and positive',
      refinement_tolerance=tolerance,
      mass_residual_tolerance_kg_m2_s=mass_tolerance,
      energy_residual_tolerance_W_m2=energy_tolerance,
    )
  ####
  case_values = tuple(cases)
  if len(case_values) < 2:
    return _failure(
      MocEulerTwoSidedInterfaceLawRefinementStatus.INVALID_INPUT,
      'interface-law refinement requires at least two resolution cases',
      refinement_tolerance=tolerance,
      mass_residual_tolerance_kg_m2_s=mass_tolerance,
      energy_residual_tolerance_W_m2=energy_tolerance,
    )
  ####
  if any(
    not isinstance(case, MocEulerTwoSidedInterfaceLawRefinementCase)
    for case in case_values
  ):
    return _failure(
      MocEulerTwoSidedInterfaceLawRefinementStatus.INVALID_INPUT,
      'cases must contain typed interface-law refinement cases',
      refinement_tolerance=tolerance,
      mass_residual_tolerance_kg_m2_s=mass_tolerance,
      energy_residual_tolerance_W_m2=energy_tolerance,
    )
  ####
  audits = tuple(
    measure_moc_euler_two_sided_interface_law(case.result)
    for case in case_values
  )
  case_ids = tuple(case.case_id for case in case_values)
  resolutions = tuple(case.resolution_sample_count for case in case_values)
  speeds = tuple(audit.maximum_interface_normal_speed_m_s for audit in audits)
  mass = tuple(audit.maximum_mass_flux_residual_kg_m2_s for audit in audits)
  momentum = tuple(audit.maximum_normal_momentum_residual_Pa for audit in audits)
  energy = tuple(audit.maximum_energy_flux_residual_W_m2 for audit in audits)
  case_audits_verified = all(audit.local_consistency_verified for audit in audits)
  case_identity_verified = bool(
    all(case_ids)
    and all(
      case.result.request is not None
      and case.result.request.source_band.source_field_verified
      for case in case_values
    )
  )
  grouped_indices: dict[str, list[int]] = {}
  for index, case_id in enumerate(case_ids):
    grouped_indices.setdefault(case_id, []).append(index)
  resolution_order_verified = all(
    all(
      resolutions[right] > resolutions[left]
      for left, right in zip(indices, indices[1:])
    )
    for indices in grouped_indices.values()
  )
  response_mode_signatures = tuple(
    _response_mode_signature(case) for case in case_values
  )
  response_mode_identity_verified = bool(
    all(response_mode_signatures)
    and all(
      len({response_mode_signatures[index] for index in indices}) == 1
      for indices in grouped_indices.values()
    )
  )
  residuals_finite = all(
    isfinite(value) and value >= 0.0
    for value in (*speeds, *mass, *momentum, *energy)
  )
  mass_residuals_verified = bool(
    residuals_finite and all(value <= mass_tolerance for value in mass)
  )
  energy_residuals_verified = bool(
    residuals_finite and all(value <= energy_tolerance for value in energy)
  )
  momentum_nonincreasing_verified = bool(
    residuals_finite
    and all(
      all(
        momentum[right] <= momentum[left] * (1.0 + tolerance)
        for left, right in zip(indices, indices[1:])
      )
      for indices in grouped_indices.values()
    )
  )
  momentum_reduction_verified = bool(
    residuals_finite
    and all(
      len(indices) >= 2
      and momentum[indices[-1]] < momentum[indices[0]]
      for indices in grouped_indices.values()
    )
  )
  group_signatures = tuple(
    _case_signature(case_values[indices[0]])
    for indices in grouped_indices.values()
    if indices
  )
  cross_case_verified = bool(
    len(grouped_indices) >= 2
    and all(len(indices) >= 3 for indices in grouped_indices.values())
    and len(group_signatures) == len(grouped_indices)
    and len(set(group_signatures)) == len(group_signatures)
  )
  local_refinement_verified = bool(
    case_audits_verified
    and case_identity_verified
    and response_mode_identity_verified
    and resolution_order_verified
    and residuals_finite
    and mass_residuals_verified
    and energy_residuals_verified
    and momentum_nonincreasing_verified
    and momentum_reduction_verified
  )
  refinement_convergence_verified = bool(
    local_refinement_verified
    and all(len(indices) >= 3 for indices in grouped_indices.values())
  )
  fidelity_flags_verified = all(
    case.result.as_report()['chain_promotion_blocked']
    and case.result.as_report()['production_claim_allowed'] is False
    for case in case_values
  )
  if not case_audits_verified:
    status = MocEulerTwoSidedInterfaceLawRefinementStatus.CASE_FAILURE
    message = 'one or more resolution cases failed the independent local interface-law audit'
  elif not resolution_order_verified:
    status = MocEulerTwoSidedInterfaceLawRefinementStatus.RESOLUTION_ORDER_FAILURE
    message = 'interface-law refinement cases are not strictly resolution ordered'
  elif not response_mode_identity_verified:
    status = MocEulerTwoSidedInterfaceLawRefinementStatus.RESPONSE_MODE_FAILURE
    message = (
      'interface-law refinement cases mix response modes within a declared '
      'resolution ladder; stationary front-limit and moving responses must be '
      'audited separately'
    )
  elif not (
    residuals_finite
    and mass_residuals_verified
    and energy_residuals_verified
    and momentum_nonincreasing_verified
    and momentum_reduction_verified
  ):
    status = MocEulerTwoSidedInterfaceLawRefinementStatus.RESIDUAL_FAILURE
    message = 'interface-law conservative residuals did not satisfy the local refinement trend'
  elif not fidelity_flags_verified:
    status = MocEulerTwoSidedInterfaceLawRefinementStatus.FLAG_FAILURE
    message = 'interface-law refinement weakened its non-promotion claim flags'
  elif cross_case_verified:
    status = (
      MocEulerTwoSidedInterfaceLawRefinementStatus
      .CONVERGED_CROSS_CASE_REFINEMENT
    )
    message = (
      'independent interface-law audit verified locally refining resolution '
      'ladders across distinct cases; canonical free-boundary, physical '
      'shock-cell, and production gates remain open'
    )
  else:
    status = MocEulerTwoSidedInterfaceLawRefinementStatus.CONVERGED_LOCAL_REFINEMENT
    message = (
      'independent interface-law audit verified a locally refining resolution '
      'ladder; cross-case, canonical free-boundary, physical shock-cell, and '
      'production gates remain open'
    )
  ####
  return _failure(
    status,
    message,
    cases=case_values,
    audits=audits,
    case_ids=case_ids,
    resolutions=resolutions,
    speeds=speeds,
    mass=mass,
    momentum=momentum,
    energy=energy,
    case_audits_verified=case_audits_verified,
    case_identity_verified=case_identity_verified,
    response_mode_identity_verified=response_mode_identity_verified,
    resolution_order_verified=resolution_order_verified,
    residuals_finite=residuals_finite,
    mass_residuals_verified=mass_residuals_verified,
    energy_residuals_verified=energy_residuals_verified,
    momentum_nonincreasing_verified=momentum_nonincreasing_verified,
    momentum_reduction_verified=momentum_reduction_verified,
    cross_case_verified=cross_case_verified,
    local_refinement_verified=local_refinement_verified,
    refinement_convergence_verified=refinement_convergence_verified,
    fidelity_flags_verified=fidelity_flags_verified,
    refinement_tolerance=tolerance,
    mass_residual_tolerance_kg_m2_s=mass_tolerance,
    energy_residual_tolerance_W_m2=energy_tolerance,
  )
