"""Research-only mixed-regime boundary bridge for the reflected MOC lane.

The global reflected closure currently ends with a locally verified exact-Euler
shock/ambient field and an explicitly open downstream boundary.  This module
binds that field to the existing scalar variable-entropy subsonic reference so
the next physics seam has a reproducible terminal, entropy handoff, and
control-section contract.  It does not relabel the compression envelope or
promote the scalar reference to a canonical two-dimensional closure.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from types import MappingProxyType
from typing import Any

from exhaust_plume.models.moc.chain import (
  MocChainBoundarySample,
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.compression import solve_normal_shock_terminal
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
  moc_reflected_domain_global_physical_closure_fingerprint,
)
from exhaust_plume.models.moc.mixed_regime import (
  MocMixedRegimeControlSection,
  MocMixedRegimeFieldSample,
  MocMixedRegimePerimeterRequest,
)
from exhaust_plume.models.moc.mixed_regime_entropy import (
  MocMixedRegimeEntropyHandoffResult,
  build_mixed_regime_entropy_handoff,
)
from exhaust_plume.models.moc.mixed_regime_variable_entropy import (
  MocMixedRegimeVariableEntropyFreeBoundaryResult,
  solve_mixed_regime_variable_entropy_free_boundary,
)
from exhaust_plume.models.moc.post_shock import MocPostShockBoundaryState
from exhaust_plume.models.moc.primitives import CharacteristicState

__all__ = (
  'MocReflectedDomainMixedRegimeBoundaryStatus',
  'MocReflectedDomainMixedRegimeBoundaryRequest',
  'MocReflectedDomainMixedRegimeBoundaryResult',
  'build_reflected_domain_mixed_regime_boundary_request',
  'solve_reflected_domain_mixed_regime_boundary',
)


MIXED_REGIME_BOUNDARY_MODEL = (
  'solver-owned-global-euler-terminal-variable-entropy-boundary-reference'
)


class MocReflectedDomainMixedRegimeBoundaryStatus(str, Enum):
  """Outcome of the global-to-mixed-regime boundary bridge."""

  CONVERGED_RESEARCH_REFERENCE = (
    'converged-global-euler-mixed-regime-boundary-reference'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_CLOSURE_FAILURE = 'mixed-regime-upstream-closure-failure'
  REQUEST_SEAM_FAILURE = 'mixed-regime-request-seam-failure'
  HANDOFF_FAILURE = 'mixed-regime-entropy-handoff-failure'
  CONTROL_SECTION_FAILURE = 'mixed-regime-control-section-failure'
  FIELD_FAILURE = 'mixed-regime-boundary-field-failure'
  INDEPENDENT_AUDIT_FAILURE = 'mixed-regime-boundary-independent-audit-failure'
####


def _global_shock_curve(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
) -> Any:
  if not isinstance(
    closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    raise TypeError(
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    raise ValueError(
      'mixed-regime boundary requires a locally physically verified global '
      'reflected closure'
    )
  ####
  global_euler = closure.global_euler
  curve = None if global_euler is None else global_euler.shock_boundary
  if (
    global_euler is None
    or not global_euler.converged
    or curve is None
    or not curve.converged
  ):
    raise ValueError(
      'mixed-regime boundary requires a converged global Euler shock curve'
    )
  ####
  return curve
####


def _derive_perimeter_inputs(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  pressure_tolerance: float = 1.0e-12,
) -> tuple[MocMixedRegimePerimeterRequest, MocMixedRegimeEntropyHandoffResult]:
  """Derive the typed terminal and open patch from the retained shock curve."""

  curve = _global_shock_curve(closure)
  if len(curve.shock_points_m) < 4:
    raise ValueError(
      'global Euler shock curve needs at least four samples for a mixed-regime '
      'terminal and open supersonic patch'
    )
  ####
  expected_lengths = (
    len(curve.shock_points_m),
    len(curve.upstream_states),
    len(curve.downstream_states),
    len(curve.upstream_total_pressure_Pa),
    len(curve.downstream_total_pressure_Pa),
    len(curve.downstream_static_pressure_Pa),
  )
  if len(set(expected_lengths)) != 1:
    raise ValueError(
      'global Euler shock curve lacks aligned state and pressure samples'
    )
  ####
  retained_indices: list[int] = []
  for index, (upstream, downstream) in enumerate(zip(
    curve.upstream_total_pressure_Pa,
    curve.downstream_total_pressure_Pa,
    strict=True,
  )):
    scale = max(1.0, abs(float(upstream)), abs(float(downstream)))
    if float(downstream) > float(upstream) + pressure_tolerance * scale:
      raise ValueError(
        f'global Euler shock curve contains a total-pressure gain at sample {index}'
      )
    ####
    if float(downstream) < float(upstream) - pressure_tolerance * scale:
      retained_indices.append(index)
    ####
  ####
  # The final curve sample becomes the explicit normal-shock terminal.  It is
  # not duplicated in the open patch because the entropy interface must remain
  # strictly ordered when it appends the terminal sample.
  terminal_index = len(curve.shock_points_m) - 1
  patch_indices = tuple(
    index for index in retained_indices if index < terminal_index
  )
  if not patch_indices:
    raise ValueError(
      'global Euler shock curve has no strictly lossy supersonic patch sample '
      'before its terminal point'
    )
  ####
  patch = tuple(
    MocPostShockBoundaryState(
      point_m=curve.shock_points_m[index],
      state=curve.downstream_states[index],
      upstream_total_pressure_Pa=curve.upstream_total_pressure_Pa[index],
      downstream_total_pressure_Pa=curve.downstream_total_pressure_Pa[index],
    )
    for index in patch_indices
  )
  terminal_upstream_state = curve.downstream_states[terminal_index]
  terminal = solve_normal_shock_terminal(
    terminal_upstream_state,
    upstream_pressure_Pa=curve.downstream_static_pressure_Pa[terminal_index],
    shock_point_m=curve.shock_points_m[terminal_index],
  )
  if not terminal.converged or not terminal.subsonic:
    raise ValueError(
      'the global Euler shock endpoint did not produce a converged subsonic '
      f'normal-shock terminal: {terminal.message}'
    )
  ####
  terminal_point = terminal.shock_point_m
  terminal_mach = terminal.downstream_mach
  terminal_angle = terminal.downstream_flow_angle_rad
  terminal_pressure = terminal.downstream_pressure_Pa
  terminal_total_pressure = terminal.downstream_total_pressure_Pa
  terminal_ratio = terminal.total_pressure_ratio
  if any(value is None for value in (
    terminal_point,
    terminal_mach,
    terminal_angle,
    terminal_pressure,
    terminal_total_pressure,
    terminal_ratio,
  )):
    raise ValueError('normal-shock terminal did not retain complete scalar data')
  ####
  assert terminal_point is not None
  assert terminal_mach is not None
  assert terminal_angle is not None
  assert terminal_pressure is not None
  assert terminal_total_pressure is not None
  assert terminal_ratio is not None
  perimeter_request = MocMixedRegimePerimeterRequest(
    terminal=terminal,
    terminal_point_m=terminal_point,
    terminal_downstream_mach=terminal_mach,
    terminal_downstream_flow_angle_rad=terminal_angle,
    terminal_downstream_pressure_Pa=terminal_pressure,
    terminal_downstream_total_pressure_Pa=terminal_total_pressure,
    terminal_total_pressure_ratio=terminal_ratio,
    supersonic_patch=patch,
    required_boundary_conditions=(
      'explicitly closed downstream perimeter',
      'terminal scalar seam continuity',
      'no total-pressure gain over the terminal shock',
      'global-Euler shock-curve state and pressure lineage',
    ),
    source='solver-owned-global-euler-terminal-normal-shock-reference',
  )
  handoff = build_mixed_regime_entropy_handoff(perimeter_request)
  if not handoff.converged:
    raise ValueError(
      f'global Euler terminal entropy handoff did not converge: {handoff.message}'
    )
  ####
  return perimeter_request, handoff
####


def _build_control_section(
  request: MocMixedRegimePerimeterRequest,
  handoff: MocMixedRegimeEntropyHandoffResult,
  *,
  x_offset_m: float,
  height_m: float,
  sample_count: int,
) -> MocMixedRegimeControlSection:
  """Build the explicit axis-aligned reference control section."""

  terminal = request.terminal
  upstream_state = terminal.upstream_state
  if not isinstance(upstream_state, CharacteristicState):
    raise TypeError('terminal upstream state is not available')
  ####
  if terminal.downstream_flow_angle_rad is None:
    raise ValueError('terminal downstream flow angle is unavailable')
  ####
  if abs(float(terminal.downstream_flow_angle_rad)) > 1.0e-10:
    raise ValueError(
      'global mixed-regime reference requires an axis-aligned terminal '
      'downstream flow angle'
    )
  ####
  if not handoff.converged:
    raise ValueError('a converged entropy handoff is required for the control section')
  ####
  terminal_point = request.terminal_point_m
  section_x = terminal_point[0] + x_offset_m
  gamma = upstream_state.gamma
  mach = request.terminal_downstream_mach
  samples: list[MocMixedRegimeFieldSample] = []
  for index in range(sample_count):
    fraction = index / (sample_count - 1)
    source_arc = handoff.cumulative_arc_length_m[-1] * (1.0 - fraction)
    total_pressure = handoff.total_pressure_at_arc_length(source_arc)
    static_pressure = total_pressure / (
      1.0 + 0.5 * (gamma - 1.0) * mach * mach
    ) ** (gamma / (gamma - 1.0))
    samples.append(
      MocMixedRegimeFieldSample(
        point_m=(section_x, terminal_point[1] + fraction * height_m),
        mach=mach,
        flow_angle_rad=0.0,
        static_pressure_Pa=static_pressure,
        total_pressure_Pa=total_pressure,
        gamma=gamma,
      )
    )
  ####
  return MocMixedRegimeControlSection(
    points_m=tuple(sample.point_m for sample in samples),
    samples=tuple(samples),
    normal_angle_rad=0.0,
    source='solver-owned-global-euler-mixed-regime-control-section',
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainMixedRegimeBoundaryRequest:
  """Exact data contract for the global-to-subsonic research bridge."""

  closure_fingerprint: str
  closure: MocReflectedDomainGlobalPhysicalClosureResult
  upstream_handoff: tuple[MocChainBoundarySample, ...]
  perimeter_request: MocMixedRegimePerimeterRequest
  entropy_handoff: MocMixedRegimeEntropyHandoffResult
  control_section: MocMixedRegimeControlSection
  ambient_pressure_Pa: float
  downstream_length_m: float
  initial_outlet_height_m: float
  control_section_x_offset_m: float
  control_section_height_m: float
  control_section_sample_count: int
  axial_station_count: int = 7
  source: str = MIXED_REGIME_BOUNDARY_MODEL

  def __post_init__(self) -> None:
    if not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult'
      )
    ####
    fingerprint = str(self.closure_fingerprint)
    if fingerprint != moc_reflected_domain_global_physical_closure_fingerprint(
      self.closure
    ):
      raise ValueError('closure_fingerprint does not match the retained closure')
    ####
    handoff = tuple(self.upstream_handoff)
    if not handoff:
      raise ValueError('upstream_handoff must contain the retained prior frontier')
    ####
    if any(
      not isinstance(sample, MocChainBoundarySample) for sample in handoff
    ):
      raise TypeError(
        'upstream_handoff must contain MocChainBoundarySample values'
      )
    ####
    if handoff != self.closure.incoming_handoff:
      raise ValueError(
        'upstream_handoff must exactly match the global closure incoming frontier'
      )
    ####
    if not isinstance(self.perimeter_request, MocMixedRegimePerimeterRequest):
      raise TypeError(
        'perimeter_request must be a MocMixedRegimePerimeterRequest'
      )
    ####
    if not isinstance(
      self.entropy_handoff,
      MocMixedRegimeEntropyHandoffResult,
    ):
      raise TypeError(
        'entropy_handoff must be a MocMixedRegimeEntropyHandoffResult'
      )
    ####
    if self.entropy_handoff.request != self.perimeter_request:
      raise ValueError(
        'entropy_handoff must retain the exact mixed-regime perimeter request'
      )
    ####
    if not isinstance(self.control_section, MocMixedRegimeControlSection):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection'
      )
    ####
    for name, value in (
      ('ambient_pressure_Pa', self.ambient_pressure_Pa),
      ('downstream_length_m', self.downstream_length_m),
      ('initial_outlet_height_m', self.initial_outlet_height_m),
      ('control_section_x_offset_m', self.control_section_x_offset_m),
      ('control_section_height_m', self.control_section_height_m),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name, minimum in (
      ('control_section_sample_count', 3),
      ('axial_station_count', 5),
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(
          f'{name} must be an integer greater than or equal to {minimum}'
        )
      ####
    ####
    expected_request, expected_handoff = _derive_perimeter_inputs(
      self.closure,
    )
    if self.perimeter_request != expected_request:
      raise ValueError(
        'perimeter_request is not the solver-derived global Euler terminal seam'
      )
    ####
    if self.entropy_handoff != expected_handoff:
      raise ValueError(
        'entropy_handoff is not the solver-derived global Euler pressure lineage'
      )
    ####
    expected_section = _build_control_section(
      expected_request,
      expected_handoff,
      x_offset_m=self.control_section_x_offset_m,
      height_m=self.control_section_height_m,
      sample_count=self.control_section_sample_count,
    )
    if self.control_section != expected_section:
      raise ValueError(
        'control_section was altered or is not bound to the entropy handoff'
      )
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'closure_fingerprint', fingerprint)
    object.__setattr__(self, 'upstream_handoff', handoff)
    object.__setattr__(self, 'source', source)
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MIXED_REGIME_BOUNDARY_MODEL,
      'source': self.source,
      'closure_fingerprint': self.closure_fingerprint,
      'upstream_handoff_sample_count': len(self.upstream_handoff),
      'perimeter_request': self.perimeter_request.as_report(),
      'entropy_handoff': self.entropy_handoff.as_report(),
      'control_section': self.control_section.as_report(),
      'ambient_pressure_Pa': self.ambient_pressure_Pa,
      'downstream_length_m': self.downstream_length_m,
      'initial_outlet_height_m': self.initial_outlet_height_m,
      'control_section_x_offset_m': self.control_section_x_offset_m,
      'control_section_height_m': self.control_section_height_m,
      'control_section_sample_count': self.control_section_sample_count,
      'axial_station_count': self.axial_station_count,
      'claim_status': (
        'global-euler-terminal-variable-entropy-reference-only; '
        'canonical-reflected-mixed-regime-field-pending'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainMixedRegimeBoundaryResult:
  """Audited mixed-regime boundary candidate with hard production stops."""

  status: MocReflectedDomainMixedRegimeBoundaryStatus
  request: MocReflectedDomainMixedRegimeBoundaryRequest | None
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  perimeter_request: MocMixedRegimePerimeterRequest | None
  entropy_handoff: MocMixedRegimeEntropyHandoffResult | None
  control_section: MocMixedRegimeControlSection | None
  reference: MocMixedRegimeVariableEntropyFreeBoundaryResult | None
  independent_measurement: Any | None = None
  solver_owned_reference_verified: bool = False
  upstream_handoff_verified: bool = False
  terminal_seam_verified: bool = False
  boundary_condition_verified: bool = False
  mixed_regime_field_verified: bool = False
  geometry_verified: bool = False
  pressure_lineage_verified: bool = False
  entropy_transport_verified: bool = False
  tangency_verified: bool = False
  conservative_euler_residuals_measured: bool = False
  conservative_euler_residuals_verified: bool = False
  residual_channel_coverage: Mapping[str, bool] = MappingProxyType({})
  residual_channel_validity: Mapping[str, bool] = MappingProxyType({})
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  refinement_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainMixedRegimeBoundaryStatus,
    ):
      raise TypeError(
        'status must be a MocReflectedDomainMixedRegimeBoundaryStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainMixedRegimeBoundaryRequest,
    ):
      raise TypeError(
        'request must be a MocReflectedDomainMixedRegimeBoundaryRequest or None'
      )
    ####
    if self.closure is not None and not isinstance(
      self.closure,
      MocReflectedDomainGlobalPhysicalClosureResult,
    ):
      raise TypeError(
        'closure must be a MocReflectedDomainGlobalPhysicalClosureResult or None'
      )
    ####
    if self.perimeter_request is not None and not isinstance(
      self.perimeter_request,
      MocMixedRegimePerimeterRequest,
    ):
      raise TypeError(
        'perimeter_request must be a MocMixedRegimePerimeterRequest or None'
      )
    ####
    if self.entropy_handoff is not None and not isinstance(
      self.entropy_handoff,
      MocMixedRegimeEntropyHandoffResult,
    ):
      raise TypeError(
        'entropy_handoff must be a MocMixedRegimeEntropyHandoffResult or None'
      )
    ####
    if self.control_section is not None and not isinstance(
      self.control_section,
      MocMixedRegimeControlSection,
    ):
      raise TypeError(
        'control_section must be a MocMixedRegimeControlSection or None'
      )
    ####
    if self.reference is not None and not isinstance(
      self.reference,
      MocMixedRegimeVariableEntropyFreeBoundaryResult,
    ):
      raise TypeError(
        'reference must be a MocMixedRegimeVariableEntropyFreeBoundaryResult or None'
      )
    ####
    for name in (
      'solver_owned_reference_verified',
      'upstream_handoff_verified',
      'terminal_seam_verified',
      'boundary_condition_verified',
      'mixed_regime_field_verified',
      'geometry_verified',
      'pressure_lineage_verified',
      'entropy_transport_verified',
      'tangency_verified',
      'conservative_euler_residuals_measured',
      'conservative_euler_residuals_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'refinement_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    for name in ('residual_channel_coverage', 'residual_channel_validity'):
      values = dict(getattr(self, name))
      if any(
        not isinstance(key, str) or not isinstance(value, bool)
        for key, value in values.items()
      ):
        raise TypeError(f'{name} must map string channel names to bool values')
      ####
      object.__setattr__(self, name, MappingProxyType(values))
    ####
    if self.production_claim_allowed:
      raise ValueError('mixed-regime boundary references cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def converged(self) -> bool:
    """Whether the research reference and its independent audit converged."""

    audit = self.independent_measurement
    return bool(
      self.status
      is MocReflectedDomainMixedRegimeBoundaryStatus.CONVERGED_RESEARCH_REFERENCE
      and self.solver_owned_reference_verified
      and self.upstream_handoff_verified
      and self.terminal_seam_verified
      and self.boundary_condition_verified
      and self.geometry_verified
      and self.pressure_lineage_verified
      and self.entropy_transport_verified
      and self.tangency_verified
      and self.conservative_euler_residuals_measured
      and self.conservative_euler_residuals_verified
      and audit is not None
      and bool(getattr(audit, 'converged', False))
    )
  ####

  @property
  def reference_verified(self) -> bool:
    """Whether all local reference checks passed, without canonical promotion."""

    return self.converged
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The scalar variable-entropy reference is not canonical 2-D closure."""

    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """The research candidate cannot satisfy the canonical downstream gate."""

    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.converged
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    if self.status is MocReflectedDomainMixedRegimeBoundaryStatus.INVALID_INPUT:
      reason = MocChainTerminationReason.INVALID_INPUT
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'global-to-mixed-regime reference remains below canonical reflected '
        'field and continued-chain promotion gates'
      ),
      diagnostics={
        'termination_model': MIXED_REGIME_BOUNDARY_MODEL,
        'status': self.status.value,
        'converged': self.converged,
        'solver_owned_reference_verified': self.solver_owned_reference_verified,
        'upstream_handoff_verified': self.upstream_handoff_verified,
        'terminal_seam_verified': self.terminal_seam_verified,
        'boundary_condition_verified': self.boundary_condition_verified,
        'mixed_regime_field_verified': self.mixed_regime_field_verified,
        'conservative_euler_residuals_measured': (
          self.conservative_euler_residuals_measured
        ),
        'conservative_euler_residuals_verified': (
          self.conservative_euler_residuals_verified
        ),
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'refinement_verified': self.refinement_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    audit = self.independent_measurement
    return {
      'status': self.status.value,
      'model': MIXED_REGIME_BOUNDARY_MODEL,
      'converged': self.converged,
      'reference_verified': self.reference_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'solver_owned_reference_verified': self.solver_owned_reference_verified,
      'upstream_handoff_verified': self.upstream_handoff_verified,
      'terminal_seam_verified': self.terminal_seam_verified,
      'boundary_condition_verified': self.boundary_condition_verified,
      'mixed_regime_field_verified': self.mixed_regime_field_verified,
      'geometry_verified': self.geometry_verified,
      'pressure_lineage_verified': self.pressure_lineage_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
      'tangency_verified': self.tangency_verified,
      'conservative_euler_residuals_measured': (
        self.conservative_euler_residuals_measured
      ),
      'conservative_euler_residuals_verified': (
        self.conservative_euler_residuals_verified
      ),
      'residual_channel_coverage': dict(self.residual_channel_coverage),
      'residual_channel_validity': dict(self.residual_channel_validity),
      'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
      'canonical_euler_verified': self.canonical_euler_verified,
      'refinement_verified': self.refinement_verified,
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'request': None if self.request is None else self.request.as_report(),
      'reference': (
        None if self.reference is None else self.reference.as_report()
      ),
      'independent_measurement': (
        None
        if audit is None or not hasattr(audit, 'as_report')
        else audit.as_report()
      ),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
      'claim_status': (
        'solver-owned-global-euler-terminal-variable-entropy-reference; '
        'mapped subsonic evidence only; canonical reflected 2-D closure, '
        'refinement, external validation, and production chain pending'
      ),
    }
  ####
####


def build_reflected_domain_mixed_regime_boundary_request(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  *,
  ambient_pressure_Pa: float | None = None,
  downstream_length_m: float = 0.2,
  initial_outlet_height_m: float | None = None,
  control_section_x_offset_m: float = 0.02,
  control_section_height_m: float = 0.05,
  control_section_sample_count: int = 4,
  axial_station_count: int = 7,
  terminal_angle_tolerance_rad: float = 1.0e-10,
) -> MocReflectedDomainMixedRegimeBoundaryRequest:
  """Build a solver-bound research request from one global Euler closure."""

  perimeter_request, handoff = _derive_perimeter_inputs(closure)
  if abs(perimeter_request.terminal_downstream_flow_angle_rad) > terminal_angle_tolerance_rad:
    raise ValueError(
      'global mixed-regime reference requires a terminal flow angle within the '
      f'axis tolerance: {perimeter_request.terminal_downstream_flow_angle_rad}'
    )
  ####
  resolved_ambient = ambient_pressure_Pa
  if resolved_ambient is None:
    if closure.source_band is None or closure.source_band.ambient_pressure_Pa is None:
      raise ValueError('closure does not retain an ambient pressure')
    ####
    resolved_ambient = closure.source_band.ambient_pressure_Pa
  ####
  resolved_height = (
    control_section_height_m
    if initial_outlet_height_m is None
    else initial_outlet_height_m
  )
  for name, value in (
    ('ambient_pressure_Pa', resolved_ambient),
    ('downstream_length_m', downstream_length_m),
    ('control_section_x_offset_m', control_section_x_offset_m),
    ('control_section_height_m', control_section_height_m),
    ('initial_outlet_height_m', resolved_height),
    ('terminal_angle_tolerance_rad', terminal_angle_tolerance_rad),
  ):
    if not isfinite(float(value)) or float(value) <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  if (
    isinstance(control_section_sample_count, bool)
    or not isinstance(control_section_sample_count, int)
    or control_section_sample_count < 3
  ):
    raise ValueError('control_section_sample_count must be at least three')
  ####
  if (
    isinstance(axial_station_count, bool)
    or not isinstance(axial_station_count, int)
    or axial_station_count < 5
  ):
    raise ValueError('axial_station_count must be at least five')
  ####
  control_section = _build_control_section(
    perimeter_request,
    handoff,
    x_offset_m=float(control_section_x_offset_m),
    height_m=float(control_section_height_m),
    sample_count=control_section_sample_count,
  )
  return MocReflectedDomainMixedRegimeBoundaryRequest(
    closure_fingerprint=moc_reflected_domain_global_physical_closure_fingerprint(
      closure
    ),
    closure=closure,
    upstream_handoff=closure.incoming_handoff,
    perimeter_request=perimeter_request,
    entropy_handoff=handoff,
    control_section=control_section,
    ambient_pressure_Pa=float(resolved_ambient),
    downstream_length_m=float(downstream_length_m),
    initial_outlet_height_m=float(resolved_height),
    control_section_x_offset_m=float(control_section_x_offset_m),
    control_section_height_m=float(control_section_height_m),
    control_section_sample_count=control_section_sample_count,
    axial_station_count=axial_station_count,
  )
####


def _failure(
  status: MocReflectedDomainMixedRegimeBoundaryStatus,
  message: str,
  *,
  request: MocReflectedDomainMixedRegimeBoundaryRequest | None = None,
  reference: MocMixedRegimeVariableEntropyFreeBoundaryResult | None = None,
) -> MocReflectedDomainMixedRegimeBoundaryResult:
  return MocReflectedDomainMixedRegimeBoundaryResult(
    status=status,
    request=request,
    closure=None if request is None else request.closure,
    perimeter_request=None if request is None else request.perimeter_request,
    entropy_handoff=None if request is None else request.entropy_handoff,
    control_section=None if request is None else request.control_section,
    reference=reference,
    message=message,
  )
####


def solve_reflected_domain_mixed_regime_boundary(
  request: MocReflectedDomainMixedRegimeBoundaryRequest,
) -> MocReflectedDomainMixedRegimeBoundaryResult:
  """Solve and independently audit the bound scalar mixed-regime reference."""

  if not isinstance(
    request,
    MocReflectedDomainMixedRegimeBoundaryRequest,
  ):
    return _failure(
      MocReflectedDomainMixedRegimeBoundaryStatus.INVALID_INPUT,
      'request must be a MocReflectedDomainMixedRegimeBoundaryRequest',
    )
  ####
  closure = request.closure
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainMixedRegimeBoundaryStatus.UPSTREAM_CLOSURE_FAILURE,
      'global reflected closure is not locally physically verified',
      request=request,
    )
  ####
  try:
    reference = solve_mixed_regime_variable_entropy_free_boundary(
      request.perimeter_request,
      request.entropy_handoff,
      request.control_section,
      ambient_pressure_Pa=request.ambient_pressure_Pa,
      downstream_length_m=request.downstream_length_m,
      initial_outlet_height_m=request.initial_outlet_height_m,
      axial_station_count=request.axial_station_count,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainMixedRegimeBoundaryStatus.FIELD_FAILURE,
      f'global mixed-regime reference solve raised: {error}',
      request=request,
    )
  ####
  if not reference.converged:
    return _failure(
      MocReflectedDomainMixedRegimeBoundaryStatus.FIELD_FAILURE,
      f'global mixed-regime reference did not converge: {reference.message}',
      request=request,
      reference=reference,
    )
  ####
  try:
    from exhaust_plume.validation.moc_reflected_domain_mixed_regime import (
      measure_reflected_domain_mixed_regime_boundary,
    )

    independent_measurement = measure_reflected_domain_mixed_regime_boundary(
      MocReflectedDomainMixedRegimeBoundaryResult(
        status=MocReflectedDomainMixedRegimeBoundaryStatus.FIELD_FAILURE,
        request=request,
        closure=closure,
        perimeter_request=request.perimeter_request,
        entropy_handoff=request.entropy_handoff,
        control_section=request.control_section,
        reference=reference,
      )
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainMixedRegimeBoundaryStatus.INDEPENDENT_AUDIT_FAILURE,
      f'global mixed-regime independent audit raised: {error}',
      request=request,
      reference=reference,
    )
  ####
  audit_converged = bool(getattr(independent_measurement, 'converged', False))
  status = (
    MocReflectedDomainMixedRegimeBoundaryStatus.CONVERGED_RESEARCH_REFERENCE
    if audit_converged
    else MocReflectedDomainMixedRegimeBoundaryStatus.INDEPENDENT_AUDIT_FAILURE
  )
  return MocReflectedDomainMixedRegimeBoundaryResult(
    status=status,
    request=request,
    closure=closure,
    perimeter_request=request.perimeter_request,
    entropy_handoff=request.entropy_handoff,
    control_section=request.control_section,
    reference=reference,
    independent_measurement=independent_measurement,
    solver_owned_reference_verified=bool(
      getattr(independent_measurement, 'reference_verified', False)
    ),
    upstream_handoff_verified=bool(
      getattr(independent_measurement, 'upstream_handoff_verified', False)
    ),
    terminal_seam_verified=bool(
      getattr(independent_measurement, 'terminal_seam_verified', False)
    ),
    boundary_condition_verified=bool(
      getattr(independent_measurement, 'boundary_condition_verified', False)
    ),
    mixed_regime_field_verified=False,
    geometry_verified=bool(
      getattr(independent_measurement, 'geometry_verified', False)
    ),
    pressure_lineage_verified=bool(
      getattr(independent_measurement, 'pressure_lineage_verified', False)
    ),
    entropy_transport_verified=bool(
      getattr(independent_measurement, 'entropy_transport_verified', False)
    ),
    tangency_verified=bool(
      getattr(independent_measurement, 'tangency_verified', False)
    ),
    conservative_euler_residuals_measured=bool(
      getattr(independent_measurement, 'conservative_euler_residuals_measured', False)
    ),
    conservative_euler_residuals_verified=bool(
      getattr(independent_measurement, 'conservative_euler_residuals_verified', False)
    ),
    residual_channel_coverage=getattr(
      independent_measurement,
      'residual_channel_coverage',
      {},
    ),
    residual_channel_validity=getattr(
      independent_measurement,
      'residual_channel_validity',
      {},
    ),
    message=(
      'global exact-Euler shock curve, explicit normal-shock terminal, entropy '
      'handoff, and independently measured variable-entropy boundary reference '
      'passed; canonical reflected 2-D mixed-regime closure remains pending'
      if audit_converged
      else (
        'global mixed-regime reference solved, but its independent boundary '
        'measurement did not pass: '
        f'{getattr(independent_measurement, "message", "unknown audit failure")}'
      )
    ),
  )
####
