"""Solver-owned exchange of mixed-regime frontier residuals.

The physical mixed-regime frontier already measures mass, normal/tangential
momentum, energy, and entropy-proxy flux mismatches.  Earlier consumers only
replayed those channels after a global update.  This module makes the next
research seam explicit: use the signed normal-momentum channel to propose a
bounded shock-normal geometry trial, refit the exact Euler shock, rebuild the
global physical field, and rerun the frontier closure.  The trial is admitted
only when every frontier component is non-worsening and at least one component
strictly improves.

This is not a canonical free-boundary solver.  The geometry trial is a
bounded research control, the operator remains promotion-blocked, and failed
or non-improving trials are retained as typed evidence rather than being
silently accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
import json
from math import copysign, hypot, isfinite
from typing import Any

from exhaust_plume.models.moc.euler_shock_boundary import (
  fit_euler_consistent_shock_boundary_from_geometry,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  consume_reflected_domain_global_shock_geometry_response,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.util.aero.shock_validity import ShockBranch
from exhaust_plume.validation.moc_global_mixed_regime_shock_frontier_refinement import (
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase,
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
  run_reflected_domain_global_mixed_regime_shock_frontier_step,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAuditStatus',
  'MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit',
  'build_reflected_domain_global_mixed_regime_frontier_residual_packet',
  'run_reflected_domain_global_mixed_regime_frontier_residual_exchange',
  'audit_reflected_domain_global_mixed_regime_frontier_residual_exchange',
)


MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID = (
  'op.moc.reflected-domain.global-mixed-regime-frontier-residual-exchange-v1'
)
FRONTIER_RESIDUAL_COMPONENT_NAMES = (
  'mass_flux',
  'normal_momentum_flux',
  'tangential_momentum_flux',
  'energy_flux',
  'entropy_proxy_flux',
)
FRONTIER_RESIDUAL_UPDATE_MODES = (
  'normal',
  'attachment-tangent',
)


class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus(
  str,
  Enum,
):
  """Typed outcomes of one bounded frontier-residual geometry update."""

  CONVERGED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE = (
    'converged-research-frontier-residual-exchange'
  )
  COMPLETED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE_WITH_OPEN_RESIDUAL = (
    'completed-research-frontier-residual-exchange-with-open-residual'
  )
  INVALID_INPUT = 'invalid_input'
  INPUT_FAILURE = 'frontier-residual-exchange-input-failure'
  GEOMETRY_UPDATE_FAILURE = 'frontier-residual-exchange-geometry-update-failure'
  FRONTIER_RECHECK_FAILURE = 'frontier-residual-exchange-frontier-recheck-failure'
  RESIDUAL_REJECTION = 'frontier-residual-exchange-residual-rejection'


class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason(
  str,
  Enum,
):
  """Typed reason why a bounded residual trial was or was not admitted."""

  ACCEPTED = 'accepted'
  NO_VALID_TRIAL_GEOMETRY = 'no-valid-trial-geometry'
  COMPONENT_WORSENING = 'component-worsening'
  NO_STRICT_COMPONENT_DESCENT = 'no-strict-component-descent'


class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAuditStatus(
  str,
  Enum,
):
  """Typed outcomes of the independent exchange replay."""

  VERIFIED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE = (
    'verified-research-frontier-residual-exchange'
  )
  INVALID_INPUT = 'invalid_input'
  REPLAY_FAILURE = 'frontier-residual-exchange-audit-replay-failure'
  LINEAGE_FAILURE = 'frontier-residual-exchange-audit-lineage-failure'


def _positive(value: object, name: str) -> float:
  numeric = float(value)
  if not isfinite(numeric) or numeric <= 0.0:
    raise ValueError(f'{name} must be finite and positive')
  return numeric


def _digest(value: object, name: str) -> str:
  digest = str(value)
  if len(digest) != 64 or any(
    character not in '0123456789abcdef' for character in digest
  ):
    raise ValueError(f'{name} must be a lowercase SHA-256 digest')
  return digest


def _normals(
  points: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...]:
  if len(points) < 2:
    raise ValueError('frontier geometry requires at least two points')
  normals: list[tuple[float, float]] = []
  for index in range(len(points)):
    if index == 0:
      first, second = points[0], points[1]
    elif index == len(points) - 1:
      first, second = points[-2], points[-1]
    else:
      first, second = points[index - 1], points[index + 1]
    tangent_x = second[0] - first[0]
    tangent_y = second[1] - first[1]
    length = hypot(tangent_x, tangent_y)
    if not isfinite(length) or length <= 0.0:
      raise ValueError('frontier geometry contains a degenerate tangent')
    normals.append((-tangent_y / length, tangent_x / length))
  return tuple(normals)


def _packet_fingerprint(
  packet: 'MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket',
) -> str:
  payload = {
    'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID,
    'case_id': packet.case_id,
    'sample_start_index': packet.sample_start_index,
    'sample_indices': packet.sample_indices,
    'sample_count': packet.sample_count,
    'source_closure_fingerprint': packet.source_closure_fingerprint,
    'point_m': packet.point_m,
    'signed_mass_flux_residuals_kg_m2_s': packet.signed_mass_flux_residuals_kg_m2_s,
    'signed_normal_momentum_residuals_Pa': packet.signed_normal_momentum_residuals_Pa,
    'signed_tangential_momentum_residuals_Pa': packet.signed_tangential_momentum_residuals_Pa,
    'signed_energy_flux_residuals_W_m2': packet.signed_energy_flux_residuals_W_m2,
    'signed_entropy_proxy_flux_residuals': packet.signed_entropy_proxy_flux_residuals,
    'component_names': FRONTIER_RESIDUAL_COMPONENT_NAMES,
    'component_residuals': packet.component_residuals,
    'component_tolerance': packet.component_tolerance,
  }
  serialized = json.dumps(
    payload,
    sort_keys=True,
    separators=(',', ':'),
    ensure_ascii=True,
    default=str,
  )
  return sha256(serialized.encode('utf-8')).hexdigest()


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket:
  """Exact signed frontier flux residuals carried across the update seam."""

  case_id: str
  sample_start_index: int
  source_closure_fingerprint: str
  point_m: tuple[tuple[float, float], ...]
  sample_indices: tuple[int, ...]
  signed_mass_flux_residuals_kg_m2_s: tuple[float, ...]
  signed_normal_momentum_residuals_Pa: tuple[float, ...]
  signed_tangential_momentum_residuals_Pa: tuple[float, ...]
  signed_energy_flux_residuals_W_m2: tuple[float, ...]
  signed_entropy_proxy_flux_residuals: tuple[float, ...]
  component_residuals: tuple[tuple[float, ...], ...]
  component_tolerance: float

  def __post_init__(self) -> None:
    case_id = str(self.case_id)
    if not case_id:
      raise ValueError('case_id must be non-empty')
    if (
      isinstance(self.sample_start_index, bool)
      or not isinstance(self.sample_start_index, int)
      or self.sample_start_index < 0
    ):
      raise ValueError('sample_start_index must be a nonnegative integer')
    ####
    points = tuple((float(point[0]), float(point[1])) for point in self.point_m)
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('point_m must contain finite points')
    ####
    indices = tuple(int(value) for value in self.sample_indices)
    if indices != tuple(range(self.sample_start_index, self.sample_start_index + len(indices))):
      raise ValueError('sample_indices must be contiguous from sample_start_index')
    ####
    channels = (
      tuple(float(value) for value in self.signed_mass_flux_residuals_kg_m2_s),
      tuple(float(value) for value in self.signed_normal_momentum_residuals_Pa),
      tuple(float(value) for value in self.signed_tangential_momentum_residuals_Pa),
      tuple(float(value) for value in self.signed_energy_flux_residuals_W_m2),
      tuple(float(value) for value in self.signed_entropy_proxy_flux_residuals),
    )
    if any(len(channel) != len(points) for channel in channels):
      raise ValueError('signed frontier residual channels must align with points')
    if any(not isfinite(value) for channel in channels for value in channel):
      raise ValueError('signed frontier residual channels must be finite')
    ####
    residuals = tuple(
      tuple(float(value) for value in sample)
      for sample in self.component_residuals
    )
    if len(residuals) != len(points) or any(
      len(sample) != len(FRONTIER_RESIDUAL_COMPONENT_NAMES)
      for sample in residuals
    ):
      raise ValueError('component_residuals must align with five frontier channels')
    if any(
      not isfinite(value) or value < 0.0
      for sample in residuals
      for value in sample
    ):
      raise ValueError('component residuals must be finite and nonnegative')
    ####
    tolerance = _positive(self.component_tolerance, 'component_tolerance')
    object.__setattr__(self, 'case_id', case_id)
    object.__setattr__(self, 'source_closure_fingerprint', _digest(
      self.source_closure_fingerprint,
      'source_closure_fingerprint',
    ))
    object.__setattr__(self, 'point_m', points)
    object.__setattr__(self, 'sample_indices', indices)
    object.__setattr__(self, 'signed_mass_flux_residuals_kg_m2_s', channels[0])
    object.__setattr__(self, 'signed_normal_momentum_residuals_Pa', channels[1])
    object.__setattr__(self, 'signed_tangential_momentum_residuals_Pa', channels[2])
    object.__setattr__(self, 'signed_energy_flux_residuals_W_m2', channels[3])
    object.__setattr__(self, 'signed_entropy_proxy_flux_residuals', channels[4])
    object.__setattr__(self, 'component_residuals', residuals)
    object.__setattr__(self, 'component_tolerance', tolerance)

  @property
  def sample_count(self) -> int:
    return len(self.point_m)

  @property
  def maximum_by_component(self) -> tuple[float, ...]:
    return tuple(
      max((sample[index] for sample in self.component_residuals), default=float('inf'))
      for index in range(len(FRONTIER_RESIDUAL_COMPONENT_NAMES))
    )

  @property
  def residual_norm(self) -> float:
    values = tuple(
      value / self.component_tolerance
      for sample in self.component_residuals
      for value in sample
    )
    return max(values, default=float('inf'))

  @property
  def fingerprint(self) -> str:
    return _packet_fingerprint(self)

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID,
      'case_id': self.case_id,
      'sample_start_index': self.sample_start_index,
      'sample_indices': self.sample_indices,
      'sample_count': self.sample_count,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'point_m': self.point_m,
      'signed_mass_flux_residuals_kg_m2_s': self.signed_mass_flux_residuals_kg_m2_s,
      'signed_normal_momentum_residuals_Pa': self.signed_normal_momentum_residuals_Pa,
      'signed_tangential_momentum_residuals_Pa': self.signed_tangential_momentum_residuals_Pa,
      'signed_energy_flux_residuals_W_m2': self.signed_energy_flux_residuals_W_m2,
      'signed_entropy_proxy_flux_residuals': self.signed_entropy_proxy_flux_residuals,
      'component_names': FRONTIER_RESIDUAL_COMPONENT_NAMES,
      'component_residuals': self.component_residuals,
      'maximum_by_component': self.maximum_by_component,
      'component_tolerance': self.component_tolerance,
      'residual_norm': self.residual_norm,
      'fingerprint': self.fingerprint,
      'research_only': True,
      'production_claim_allowed': False,
    }


def build_reflected_domain_global_mixed_regime_frontier_residual_packet(
  step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket:
  """Extract signed, unit-bearing flux residuals from one exact frontier step."""

  if not isinstance(
    step,
    MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
  ):
    raise TypeError('step must be a typed shock-frontier refinement step')
  if not step.locally_verified:
    raise ValueError('frontier residual exchange requires a locally verified step')
  samples = step.normal_closure.closure_samples
  if not samples:
    raise ValueError('frontier normal closure retained no residual samples')
  ####
  return MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket(
    case_id=step.case_id,
    sample_start_index=step.sample_start_index,
    source_closure_fingerprint=step.source_closure_fingerprint,
    point_m=tuple(sample.interface_flux.point_m for sample in samples),
    sample_indices=tuple(
      step.sample_start_index + index for index in range(len(samples))
    ),
    signed_mass_flux_residuals_kg_m2_s=tuple(
      sample.interface_flux.mass_flux_kg_m2_s - sample.ambient_mass_flux_kg_m2_s
      for sample in samples
    ),
    signed_normal_momentum_residuals_Pa=tuple(
      sample.interface_flux.normal_momentum_flux_Pa
      - sample.ambient_normal_momentum_flux_Pa
      for sample in samples
    ),
    signed_tangential_momentum_residuals_Pa=tuple(
      sample.interface_flux.tangential_momentum_flux_Pa
      - sample.ambient_tangential_momentum_flux_Pa
      for sample in samples
    ),
    signed_energy_flux_residuals_W_m2=tuple(
      sample.interface_flux.total_energy_flux_W_m2
      - sample.ambient_total_energy_flux_W_m2
      for sample in samples
    ),
    signed_entropy_proxy_flux_residuals=tuple(
      sample.interface_flux.entropy_proxy_flux
      - sample.ambient_entropy_proxy_flux
      for sample in samples
    ),
    component_residuals=tuple(sample.component_residuals for sample in samples),
    component_tolerance=step.normal_closure_request.component_tolerance,
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest:
  """Inputs for one bounded geometry update driven by frontier residuals."""

  source_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep
  target_closure: MocReflectedDomainGlobalPhysicalClosureResult
  reference_total_temperature_K: float
  maximum_iterations: int = 1
  probe_displacement_m: float = 1.0e-4
  maximum_displacement_m: float = 1.0e-3
  relaxation: float = 0.5
  line_search_scales: tuple[float, ...] = (
    1.0,
    0.5,
    0.25,
    0.1,
    0.05,
    0.025,
    0.01,
  )
  try_opposite_direction: bool = True
  allow_attachment_tangent_update: bool = True
  branch: ShockBranch = ShockBranch.WEAK
  position_tolerance_m: float = 1.0e-8
  invariant_tolerance: float = 1.0e-8
  pressure_tolerance: float = 1.0e-8
  tangent_tolerance: float = 1.0e-8
  source: str = 'research-global-mixed-regime-frontier-residual-exchange-v1'

  def __post_init__(self) -> None:
    if not isinstance(
      self.source_frontier_step,
      MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
    ):
      raise TypeError('source_frontier_step must be a typed frontier step')
    if not self.source_frontier_step.locally_verified:
      raise ValueError('source_frontier_step must be locally verified')
    if not isinstance(
      self.target_closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError('target_closure must be a typed global physical closure')
    if not self.target_closure.converged or not self.target_closure.physical_closure_verified:
      raise ValueError('target_closure must be locally physically verified')
    if self.target_closure.global_euler is None or self.target_closure.global_euler.shock_boundary is None:
      raise ValueError('target_closure must retain a global Euler shock boundary')
    if (
      isinstance(self.maximum_iterations, bool)
      or not isinstance(self.maximum_iterations, int)
      or self.maximum_iterations < 1
    ):
      raise ValueError('maximum_iterations must be a positive integer')
    ####
    for name in (
      'reference_total_temperature_K',
      'probe_displacement_m',
      'maximum_displacement_m',
      'position_tolerance_m',
      'invariant_tolerance',
      'pressure_tolerance',
      'tangent_tolerance',
    ):
      object.__setattr__(self, name, _positive(getattr(self, name), name))
    relaxation = _positive(self.relaxation, 'relaxation')
    if relaxation > 1.0:
      raise ValueError('relaxation must be no greater than one')
    if self.probe_displacement_m > self.maximum_displacement_m:
      raise ValueError('probe_displacement_m cannot exceed maximum_displacement_m')
    scales = tuple(float(value) for value in self.line_search_scales)
    if not scales or any(not isfinite(value) or value <= 0.0 or value > 1.0 for value in scales):
      raise ValueError('line_search_scales must contain finite values in (0, 1]')
    if any(right >= left for left, right in zip(scales, scales[1:])):
      raise ValueError('line_search_scales must be strictly decreasing')
    if not isinstance(self.try_opposite_direction, bool):
      raise TypeError('try_opposite_direction must be a bool')
    if not isinstance(self.allow_attachment_tangent_update, bool):
      raise TypeError('allow_attachment_tangent_update must be a bool')
    if not isinstance(self.branch, ShockBranch):
      raise TypeError('branch must be a ShockBranch')
    source = str(self.source)
    if not source:
      raise ValueError('source must be non-empty')
    object.__setattr__(self, 'relaxation', relaxation)
    object.__setattr__(self, 'line_search_scales', scales)
    object.__setattr__(self, 'source', source)

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID,
      'source': self.source,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'maximum_iterations': self.maximum_iterations,
      'probe_displacement_m': self.probe_displacement_m,
      'maximum_displacement_m': self.maximum_displacement_m,
      'relaxation': self.relaxation,
      'line_search_scales': self.line_search_scales,
      'try_opposite_direction': self.try_opposite_direction,
      'allow_attachment_tangent_update': self.allow_attachment_tangent_update,
      'branch': self.branch.value,
      'position_tolerance_m': self.position_tolerance_m,
      'invariant_tolerance': self.invariant_tolerance,
      'pressure_tolerance': self.pressure_tolerance,
      'tangent_tolerance': self.tangent_tolerance,
      'source_closure_fingerprint': self.source_frontier_step.source_closure_fingerprint,
      'target_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(self.target_closure),
      'source_frontier_step': self.source_frontier_step.as_report(),
      'research_only': True,
      'production_claim_allowed': False,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration:
  """One residual-driven geometry trial and physical frontier replay."""

  iteration_index: int
  source_packet: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket
  trial_packet: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket | None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult
  trial_closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  trial_frontier_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep | None
  trial_points_m: tuple[tuple[float, float], ...]
  componentwise_non_worsening: bool
  strict_component_descent: bool
  geometry_update_attempted: bool
  geometry_update_consumed: bool
  accepted: bool
  candidate_count: int = 1
  selected_direction_multiplier: float = 1.0
  selected_step_scale: float = 1.0
  selected_update_mode: str = 'normal'
  admission_reason: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason = (
    MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason.NO_VALID_TRIAL_GEOMETRY
  )
  message: str = ''

  def __post_init__(self) -> None:
    if isinstance(self.iteration_index, bool) or not isinstance(self.iteration_index, int) or self.iteration_index < 0:
      raise ValueError('iteration_index must be a nonnegative integer')
    if not isinstance(self.source_packet, MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket):
      raise TypeError('source_packet must be a typed residual packet')
    for name, expected in (
      ('trial_packet', MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket),
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('trial_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('trial_frontier_step', MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain its typed result or None')
    points = tuple((float(point[0]), float(point[1])) for point in self.trial_points_m)
    if any(not all(isfinite(value) for value in point) for point in points):
      raise ValueError('trial_points_m must contain finite points')
    for name in (
      'componentwise_non_worsening',
      'strict_component_descent',
      'geometry_update_attempted',
      'geometry_update_consumed',
      'accepted',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if (
      isinstance(self.candidate_count, bool)
      or not isinstance(self.candidate_count, int)
      or self.candidate_count < 0
    ):
      raise ValueError('candidate_count must be a nonnegative integer')
    for name in ('selected_direction_multiplier', 'selected_step_scale'):
      value = float(getattr(self, name))
      if not isfinite(value):
        raise ValueError(f'{name} must be finite')
      object.__setattr__(self, name, value)
    update_mode = str(self.selected_update_mode)
    if update_mode not in FRONTIER_RESIDUAL_UPDATE_MODES:
      raise ValueError(
        'selected_update_mode must be one of '
        f'{FRONTIER_RESIDUAL_UPDATE_MODES}'
      )
    object.__setattr__(self, 'selected_update_mode', update_mode)
    if not isinstance(
      self.admission_reason,
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason,
    ):
      raise TypeError('admission_reason must be a typed admission reason')
    if self.accepted and not (
      self.componentwise_non_worsening
      and self.strict_component_descent
      and self.geometry_update_consumed
      and self.trial_packet is not None
      and self.trial_frontier_step is not None
    ):
      raise ValueError('accepted exchange iterations require consumed improving trial evidence')
    object.__setattr__(self, 'trial_points_m', points)
    object.__setattr__(self, 'message', str(self.message))

  def as_report(self) -> dict[str, Any]:
    return {
      'iteration_index': self.iteration_index,
      'source_packet': self.source_packet.as_report(),
      'trial_packet': None if self.trial_packet is None else self.trial_packet.as_report(),
      'source_closure_fingerprint': moc_reflected_domain_global_physical_closure_fingerprint(self.source_closure),
      'trial_closure_fingerprint': (
        None
        if self.trial_closure is None
        else moc_reflected_domain_global_physical_closure_fingerprint(self.trial_closure)
      ),
      'trial_points_m': self.trial_points_m,
      'componentwise_non_worsening': self.componentwise_non_worsening,
      'strict_component_descent': self.strict_component_descent,
      'geometry_update_attempted': self.geometry_update_attempted,
      'geometry_update_consumed': self.geometry_update_consumed,
      'accepted': self.accepted,
      'candidate_count': self.candidate_count,
      'selected_direction_multiplier': self.selected_direction_multiplier,
      'selected_step_scale': self.selected_step_scale,
      'selected_update_mode': self.selected_update_mode,
      'admission_reason': self.admission_reason.value,
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult:
  """Research result from the residual-consuming geometry update."""

  status: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus
  request: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest | None
  source_packet: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket | None = None
  final_packet: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket | None = None
  source_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  final_closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None
  iterations: tuple[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration, ...] = ()
  geometry_update_attempted: bool = False
  geometry_update_consumed: bool = False
  componentwise_non_worsening: bool = False
  strict_component_descent: bool = False
  independent_audit_verified: bool = False
  global_coupling_verified: bool = False
  canonical_free_boundary_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus):
      raise TypeError('status must be a typed residual-exchange status')
    if self.request is not None and not isinstance(self.request, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest):
      raise TypeError('request must be a typed residual-exchange request')
    for name, expected in (
      ('source_packet', MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket),
      ('final_packet', MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket),
      ('source_closure', MocReflectedDomainGlobalPhysicalClosureResult),
      ('final_closure', MocReflectedDomainGlobalPhysicalClosureResult),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected):
        raise TypeError(f'{name} must retain a typed result or None')
    iterations = tuple(self.iterations)
    if any(not isinstance(item, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration) for item in iterations):
      raise TypeError('iterations must contain typed residual-exchange iterations')
    if tuple(item.iteration_index for item in iterations) != tuple(range(len(iterations))):
      raise ValueError('iterations must have contiguous zero-based indices')
    object.__setattr__(self, 'iterations', iterations)
    for name in (
      'geometry_update_attempted',
      'geometry_update_consumed',
      'componentwise_non_worsening',
      'strict_component_descent',
      'independent_audit_verified',
      'global_coupling_verified',
      'canonical_free_boundary_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.global_coupling_verified or self.canonical_free_boundary_verified:
      raise ValueError('residual exchange cannot claim canonical closure')
    if not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('residual exchange must remain promotion-blocked')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus.CONVERGED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE
      and self.geometry_update_attempted
      and self.geometry_update_consumed
      and self.componentwise_non_worsening
      and self.strict_component_descent
      and self.independent_audit_verified
      and self.chain_promotion_blocked
      and not self.global_coupling_verified
      and not self.canonical_free_boundary_verified
      and not self.production_claim_allowed
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID,
      'status': self.status.value,
      'converged': self.converged,
      'source_packet': None if self.source_packet is None else self.source_packet.as_report(),
      'final_packet': None if self.final_packet is None else self.final_packet.as_report(),
      'source_closure_fingerprint': (
        None if self.source_closure is None else moc_reflected_domain_global_physical_closure_fingerprint(self.source_closure)
      ),
      'final_closure_fingerprint': (
        None if self.final_closure is None else moc_reflected_domain_global_physical_closure_fingerprint(self.final_closure)
      ),
      'geometry_update_attempted': self.geometry_update_attempted,
      'geometry_update_consumed': self.geometry_update_consumed,
      'componentwise_non_worsening': self.componentwise_non_worsening,
      'strict_component_descent': self.strict_component_descent,
      'independent_audit_verified': self.independent_audit_verified,
      'global_coupling_verified': False,
      'canonical_free_boundary_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'iterations': tuple(item.as_report() for item in self.iterations),
      'request': None if self.request is None else self.request.as_report(),
      'message': self.message,
    }


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit:
  """Independent replay audit for the residual-consuming update."""

  status: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAuditStatus
  candidate: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult | None
  request_replayed: bool = False
  packet_replayed: bool = False
  update_replayed: bool = False
  response_replayed: bool = False
  independent_exchange_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(self.status, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAuditStatus):
      raise TypeError('status must be a typed residual-exchange audit status')
    if self.candidate is not None and not isinstance(self.candidate, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult):
      raise TypeError('candidate must be a typed residual-exchange result')
    for name in (
      'request_replayed',
      'packet_replayed',
      'update_replayed',
      'response_replayed',
      'independent_exchange_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
    if self.global_coupling_verified or not self.chain_promotion_blocked or self.production_claim_allowed:
      raise ValueError('residual-exchange audit must remain promotion-blocked')
    object.__setattr__(self, 'message', str(self.message))

  @property
  def converged(self) -> bool:
    return bool(
      self.status is MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAuditStatus.VERIFIED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE
      and self.independent_exchange_verified
    )

  def as_report(self) -> dict[str, Any]:
    return {
      'operator_id': MOC_REFLECTED_DOMAIN_GLOBAL_MIXED_REGIME_FRONTIER_RESIDUAL_EXCHANGE_OPERATOR_ID,
      'audit_status': self.status.value,
      'converged': self.converged,
      'request_replayed': self.request_replayed,
      'packet_replayed': self.packet_replayed,
      'update_replayed': self.update_replayed,
      'response_replayed': self.response_replayed,
      'independent_exchange_verified': self.independent_exchange_verified,
      'global_coupling_verified': False,
      'chain_promotion_blocked': True,
      'production_claim_allowed': False,
      'candidate': None if self.candidate is None else self.candidate.as_report(),
      'message': self.message,
    }


def _failure(
  status: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus,
  message: str,
  *,
  request: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest | None = None,
  **values: Any,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult:
  return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult(
    status=status,
    request=request,
    message=message,
    **values,
  )


def _comparison(
  before: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket,
  after: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket,
) -> tuple[bool, bool]:
  if before.sample_count != after.sample_count:
    return False, False
  before_max = before.maximum_by_component
  after_max = after.maximum_by_component
  tolerance = 1.0e-12
  non_worsening = all(
    after_value <= before_value + tolerance * max(1.0, abs(before_value))
    for before_value, after_value in zip(before_max, after_max, strict=True)
  )
  strict = any(
    after_value < before_value - tolerance * max(1.0, abs(before_value))
    for before_value, after_value in zip(before_max, after_max, strict=True)
  )
  return bool(non_worsening), bool(strict)


def _trial_points(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  packet: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket,
  request: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest,
  *,
  direction_multiplier: float = 1.0,
  step_scale: float = 1.0,
  update_mode: str = 'normal',
) -> tuple[tuple[float, float], ...]:
  if closure.global_euler is None or closure.global_euler.shock_boundary is None:
    raise ValueError('target closure retains no global shock boundary')
  curve = closure.global_euler.shock_boundary
  points = tuple(curve.shock_points_m)
  if len(points) <= packet.sample_start_index:
    raise ValueError('target shock boundary is shorter than the frontier packet')
  if packet.sample_start_index + packet.sample_count > len(points):
    raise ValueError('frontier packet does not align with target shock boundary')
  if update_mode not in FRONTIER_RESIDUAL_UPDATE_MODES:
    raise ValueError(f'unsupported frontier residual update mode: {update_mode}')
  normals = _normals(points)
  updated = [list(point) for point in points]
  for local_index, signed_residual in enumerate(
    packet.signed_normal_momentum_residuals_Pa
  ):
    global_index = packet.sample_start_index + local_index
    if update_mode == 'attachment-tangent':
      if global_index != 1 or not request.allow_attachment_tangent_update:
        continue
      # Sample zero is a solver-owned zero-strength Mach-wave endpoint.  The
      # first compressive sample may move only along that fixed endpoint ray;
      # this preserves the attachment tangent while allowing the exact source
      # band and Euler refit to respond to its normal residual.
      first = points[0]
      second = points[1]
      endpoint_length = hypot(
        second[0] - first[0],
        second[1] - first[1],
      )
      if len(points) > 2:
        next_point = points[2]
        next_spacing = hypot(
          next_point[0] - second[0],
          next_point[1] - second[1],
        )
      else:
        next_spacing = endpoint_length
      step = min(
        request.probe_displacement_m,
        request.maximum_displacement_m,
        0.25 * endpoint_length,
        0.25 * next_spacing,
      ) * request.relaxation * step_scale
      if not isfinite(step) or step <= request.position_tolerance_m:
        continue
      ####
      endpoint_unit = (
        (second[0] - first[0]) / endpoint_length,
        (second[1] - first[1]) / endpoint_length,
      )
      direction = direction_multiplier * copysign(1.0, signed_residual)
      updated[global_index][0] += direction * step * endpoint_unit[0]
      updated[global_index][1] += direction * step * endpoint_unit[1]
      continue
    ####
    if global_index <= 1 or global_index >= len(points) - 2:
      # The first and centerline endpoints are solver-owned attachment or
      # termination conditions.  Their adjacent samples are also held fixed
      # so a local displacement cannot change an endpoint tangent and violate
      # a zero-strength attachment condition.
      continue
    ####
    if abs(signed_residual) <= 0.0:
      continue
    previous = points[global_index - 1]
    following = points[global_index + 1]
    spacing = min(
      hypot(points[global_index][0] - previous[0], points[global_index][1] - previous[1]),
      hypot(following[0] - points[global_index][0], following[1] - points[global_index][1]),
    )
    step = min(
      request.probe_displacement_m,
      request.maximum_displacement_m,
      0.25 * spacing,
    ) * request.relaxation * step_scale
    if not isfinite(step) or step <= request.position_tolerance_m:
      continue
    ####
    direction = direction_multiplier * -copysign(1.0, signed_residual)
    updated[global_index][0] += direction * step * normals[global_index][0]
    updated[global_index][1] += direction * step * normals[global_index][1]
  return tuple((point[0], point[1]) for point in updated)


def _run_trial(
  current_closure: MocReflectedDomainGlobalPhysicalClosureResult,
  current_packet: MocReflectedDomainGlobalMixedRegimeFrontierResidualPacket,
  current_step: MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
  request: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest,
  iteration_index: int,
  *,
  direction_multiplier: float = 1.0,
  step_scale: float = 1.0,
  update_mode: str = 'normal',
) -> tuple[
  tuple[tuple[float, float], ...],
  MocReflectedDomainGlobalPhysicalClosureResult,
  MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementStep,
]:
  trial_points = _trial_points(
    current_closure,
    current_packet,
    request,
    direction_multiplier=direction_multiplier,
    step_scale=step_scale,
    update_mode=update_mode,
  )
  if current_closure.global_euler is None or current_closure.global_euler.shock_boundary is None:
    raise ValueError('target closure retains no global shock boundary')
  if current_closure.source_band is None:
    raise ValueError('target closure retains no solver-owned source band')
  curve = current_closure.global_euler.shock_boundary
  upstream_states = []
  upstream_pressures = []
  for index, point in enumerate(trial_points):
    original_point = curve.shock_points_m[index]
    if all(
      abs(point[coordinate] - original_point[coordinate])
      <= request.position_tolerance_m
      for coordinate in (0, 1)
    ):
      state = curve.upstream_states[index]
      pressure = curve.upstream_static_pressure_Pa[index]
    else:
      state = current_closure.source_band.state_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
      pressure = current_closure.source_band.static_pressure_at(
        point,
        position_tolerance_m=request.position_tolerance_m,
      )
    if (
      state is None
      or pressure is None
      or not isfinite(float(pressure))
      or pressure <= 0.0
    ):
      raise ValueError(
        f'geometry-conditioned trial point {index} is outside the retained source band'
      )
    upstream_states.append(state)
    upstream_pressures.append(float(pressure))
  ####
  trial_curve = fit_euler_consistent_shock_boundary_from_geometry(
    tuple(upstream_states),
    tuple(upstream_pressures),
    trial_points,
    branch=request.branch,
    position_tolerance_m=request.position_tolerance_m,
    shock_angle_tolerance_rad=max(
      request.tangent_tolerance,
      curve.shock_angle_tolerance_rad,
    ),
    residual_tolerance=max(request.pressure_tolerance, curve.residual_tolerance),
    allow_zero_strength_endpoints=True,
  )
  if not trial_curve.converged or not trial_curve.local_euler_verified:
    raise ValueError(f'geometry-conditioned shock refit did not converge: {trial_curve.message}')
  trial_closure = consume_reflected_domain_global_shock_geometry_response(
    current_closure,
    trial_curve,
    branch=request.branch,
    position_tolerance_m=request.position_tolerance_m,
    invariant_tolerance=request.invariant_tolerance,
    pressure_tolerance=request.pressure_tolerance,
    tangent_tolerance=request.tangent_tolerance,
  )
  if not trial_closure.converged or not trial_closure.physical_closure_verified:
    raise ValueError(f'global geometry update did not close: {trial_closure.message}')
  source_request = current_step.state_equation_request
  trial_step = run_reflected_domain_global_mixed_regime_shock_frontier_step(
    MocReflectedDomainGlobalMixedRegimeShockFrontierRefinementCase(
      case_id=f'{current_step.case_id}-residual-exchange-{iteration_index}',
      closure=trial_closure,
      reference_total_temperature_K=request.reference_total_temperature_K,
      sample_start_index=current_step.sample_start_index,
      normal_offset_m=source_request.normal_offset_m,
      offset_side=source_request.offset_side,
      invariant_tolerance=current_step.compatibility_request.invariant_tolerance,
      geometry_tolerance=current_step.compatibility_request.geometry_tolerance,
      component_tolerance=current_step.normal_closure_request.component_tolerance,
      target_entropy_consistency_tolerance=(
        source_request.target_entropy_consistency_tolerance
      ),
    )
  )
  return trial_points, trial_closure, trial_step


def run_reflected_domain_global_mixed_regime_frontier_residual_exchange(
  request: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult:
  """Consume frontier residuals in a bounded exact-Euler geometry trial."""

  status_type = MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeStatus
  if not isinstance(request, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeRequest):
    return _failure(status_type.INVALID_INPUT, 'request must be a typed residual-exchange request')
  try:
    source_packet = build_reflected_domain_global_mixed_regime_frontier_residual_packet(
      request.source_frontier_step
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(status_type.INPUT_FAILURE, f'frontier residual packet failed: {error}', request=request)
  current_closure = request.target_closure
  current_step = request.source_frontier_step
  current_packet = source_packet
  retained: list[MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration] = []
  for iteration_index in range(request.maximum_iterations):
    directions = (1.0, -1.0) if request.try_opposite_direction else (1.0,)
    attachment_sample_active = bool(
      request.allow_attachment_tangent_update
      and current_packet.sample_start_index <= 1
      and current_packet.sample_start_index + current_packet.sample_count > 1
    )
    update_modes = (
      ('attachment-tangent', 'normal')
      if attachment_sample_active
      else ('normal',)
    )
    candidates: list[Any] = []
    failures: list[str] = []
    attempted = 0
    accepted_candidate: Any | None = None
    for update_mode in update_modes:
      for direction_multiplier in directions:
        for step_scale in request.line_search_scales:
          attempted += 1
          try:
            trial_points, trial_closure, trial_step = _run_trial(
              current_closure,
              current_packet,
              current_step,
              request,
              iteration_index,
              direction_multiplier=direction_multiplier,
              step_scale=step_scale,
              update_mode=update_mode,
            )
            trial_packet = build_reflected_domain_global_mixed_regime_frontier_residual_packet(
              trial_step
            )
            non_worsening, strict = _comparison(current_packet, trial_packet)
          except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
            failures.append(
              f'mode={update_mode},direction={direction_multiplier:g},'
              f'scale={step_scale:g}: {error}'
            )
            continue
          candidate = (
            trial_points,
            trial_closure,
            trial_step,
            trial_packet,
            non_worsening,
            strict,
            direction_multiplier,
            step_scale,
            update_mode,
          )
          candidates.append(candidate)
          if non_worsening and strict:
            accepted_candidate = candidate
            break
        if accepted_candidate is not None:
          break
      if accepted_candidate is not None:
        break
    if not candidates:
      error = '; '.join(failures) or 'no bounded line-search candidates were produced'
      iteration = MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration(
        iteration_index=iteration_index,
        source_packet=current_packet,
        trial_packet=None,
        source_closure=current_closure,
        trial_closure=None,
        trial_frontier_step=None,
        trial_points_m=(),
        componentwise_non_worsening=False,
        strict_component_descent=False,
        geometry_update_attempted=True,
        geometry_update_consumed=False,
        accepted=False,
        candidate_count=attempted,
        admission_reason=(
          MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason
          .NO_VALID_TRIAL_GEOMETRY
        ),
        message=f'geometry/frontier line search failed closed: {error}',
      )
      retained.append(iteration)
      return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult(
        status=status_type.GEOMETRY_UPDATE_FAILURE,
        request=request,
        source_packet=source_packet,
        final_packet=current_packet,
        source_closure=request.target_closure,
        final_closure=current_closure,
        iterations=tuple(retained),
        geometry_update_attempted=True,
        geometry_update_consumed=False,
        componentwise_non_worsening=False,
        strict_component_descent=False,
        independent_audit_verified=False,
        global_coupling_verified=False,
        canonical_free_boundary_verified=False,
        chain_promotion_blocked=True,
        production_claim_allowed=False,
        message=f'frontier residual geometry line search failed closed: {error}',
      )
    ####
    selected = (
      accepted_candidate
      if accepted_candidate is not None
      else min(candidates, key=lambda candidate: candidate[3].residual_norm)
    )
    (
      trial_points,
      trial_closure,
      trial_step,
      trial_packet,
      non_worsening,
      strict,
      selected_direction_multiplier,
      selected_step_scale,
      selected_update_mode,
    ) = selected
    accepted = bool(non_worsening and strict)
    admission_reason = (
      MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason.ACCEPTED
      if accepted
      else (
        MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason
        .COMPONENT_WORSENING
        if not non_worsening
        else (
          MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAdmissionReason
          .NO_STRICT_COMPONENT_DESCENT
        )
      )
    )
    iteration = MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeIteration(
      iteration_index=iteration_index,
      source_packet=current_packet,
      trial_packet=trial_packet,
      source_closure=current_closure,
      trial_closure=trial_closure,
      trial_frontier_step=trial_step,
      trial_points_m=trial_points,
      componentwise_non_worsening=non_worsening,
      strict_component_descent=strict,
      geometry_update_attempted=True,
      geometry_update_consumed=True,
      accepted=accepted,
      candidate_count=attempted,
      selected_direction_multiplier=selected_direction_multiplier,
      selected_step_scale=selected_step_scale,
      selected_update_mode=selected_update_mode,
      admission_reason=admission_reason,
      message=(
        'frontier residuals drove a bounded exact-Euler shock geometry trial '
        f'line search ({attempted} candidates; mode {selected_update_mode}, '
        f'direction {selected_direction_multiplier:g}, '
        f'scale {selected_step_scale:g}) '
        'and the refreshed physical frontier was component-wise admitted'
        if accepted
        else (
          'refreshed physical frontier was retained after a bounded line '
          f'search ({attempted} candidates; mode {selected_update_mode}, '
          f'selected direction {selected_direction_multiplier:g}, '
          f'scale {selected_step_scale:g}), '
          + (
            'at least one component worsened'
            if not non_worsening
            else (
              'no candidate achieved strict component descent under the '
              'solver-owned endpoint stencil'
            )
          )
        )
      ),
    )
    retained.append(iteration)
    if not accepted:
      return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult(
        status=status_type.RESIDUAL_REJECTION,
        request=request,
        source_packet=source_packet,
        final_packet=current_packet,
        source_closure=request.target_closure,
        final_closure=current_closure,
        iterations=tuple(retained),
        geometry_update_attempted=True,
        geometry_update_consumed=True,
        componentwise_non_worsening=non_worsening,
        strict_component_descent=strict,
        independent_audit_verified=bool(trial_step.independent_audits_verified),
        global_coupling_verified=False,
        canonical_free_boundary_verified=False,
        chain_promotion_blocked=True,
        production_claim_allowed=False,
        message=iteration.message,
      )
    current_closure = trial_closure
    current_step = trial_step
    current_packet = trial_packet
  ####
  independent = bool(
    retained
    and all(
      item.trial_frontier_step is not None
      and item.trial_frontier_step.independent_audits_verified
      for item in retained
    )
  )
  return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult(
    status=status_type.CONVERGED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE,
    request=request,
    source_packet=source_packet,
    final_packet=current_packet,
    source_closure=request.target_closure,
    final_closure=current_closure,
    iterations=tuple(retained),
    geometry_update_attempted=True,
    geometry_update_consumed=True,
    componentwise_non_worsening=all(item.componentwise_non_worsening for item in retained),
    strict_component_descent=all(item.strict_component_descent for item in retained),
    independent_audit_verified=independent,
    global_coupling_verified=False,
    canonical_free_boundary_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'frontier normal-closure residuals were consumed by a bounded global '
      'shock geometry update and independently replayed; canonical coupling '
      'and production promotion remain closed'
    ),
  )


def audit_reflected_domain_global_mixed_regime_frontier_residual_exchange(
  result: MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult,
) -> MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit:
  """Replay one exact residual exchange and compare packet/update identity."""

  audit_status = MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAuditStatus
  if not isinstance(result, MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeResult):
    return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit(
      status=audit_status.INVALID_INPUT,
      candidate=None,
      message='result must be a typed residual-exchange result',
    )
  if result.request is None:
    return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message='residual-exchange replay requires the retained request',
    )
  try:
    replay = run_reflected_domain_global_mixed_regime_frontier_residual_exchange(result.request)
  except (ArithmeticError, FloatingPointError, RuntimeError, TypeError, ValueError) as error:
    return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit(
      status=audit_status.REPLAY_FAILURE,
      candidate=result,
      message=f'residual-exchange replay raised: {error}',
    )
  request_replayed = replay.request is result.request
  packet_replayed = bool(
    replay.source_packet is not None
    and result.source_packet is not None
    and replay.source_packet.fingerprint == result.source_packet.fingerprint
  )
  update_replayed = bool(
    replay.geometry_update_attempted == result.geometry_update_attempted
    and replay.geometry_update_consumed == result.geometry_update_consumed
    and replay.status is result.status
  )
  response_replayed = bool(
    replay.final_packet is not None
    and result.final_packet is not None
    and replay.final_packet.fingerprint == result.final_packet.fingerprint
    and (
      replay.final_closure is None
      if result.final_closure is None
      else replay.final_closure is not None
      and moc_reflected_domain_global_physical_closure_fingerprint(replay.final_closure)
      == moc_reflected_domain_global_physical_closure_fingerprint(result.final_closure)
    )
  )
  independent = bool(
    request_replayed
    and packet_replayed
    and update_replayed
    and response_replayed
    and replay.componentwise_non_worsening == result.componentwise_non_worsening
    and replay.strict_component_descent == result.strict_component_descent
    and replay.chain_promotion_blocked
    and not replay.production_claim_allowed
  )
  return MocReflectedDomainGlobalMixedRegimeFrontierResidualExchangeAudit(
    status=(
      audit_status.VERIFIED_RESEARCH_FRONTIER_RESIDUAL_EXCHANGE
      if independent
      else audit_status.LINEAGE_FAILURE
    ),
    candidate=result,
    request_replayed=request_replayed,
    packet_replayed=packet_replayed,
    update_replayed=update_replayed,
    response_replayed=response_replayed,
    independent_exchange_verified=independent,
    global_coupling_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    message=(
      'independent replay reproduced the exact frontier packet, geometry '
      'trial, refreshed frontier, and claim ceiling'
      if independent
      else 'independent replay did not reproduce the exact residual exchange'
    ),
  )
