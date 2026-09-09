"""Research downstream field driven by the mixed-wave terminal interface.

The mixed-wave interface is a solver-owned local seam.  This module consumes
that exact seam inside the existing bounded coupled-Euler/free-boundary field
solver, retaining the perimeter source, entropy handoff, control-section
geometry, and global-closure fingerprint.  A converged field here is local
downstream evidence only: centerline closure, global feedback, independent
cross-case validation, and production promotion remain separate gates.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any

from exhaust_plume.models.moc.coupled_euler_free_boundary import (
  MocReflectedDomainCoupledEulerFreeBoundaryResult,
  MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  MocReflectedDomainCoupledEulerInletBoundaryMode,
  MocReflectedDomainCoupledEulerSubsonicPressureBudget,
  MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus,
  solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request,
)
from exhaust_plume.models.moc.global_physical_closure import (
  MocReflectedDomainGlobalPhysicalClosureResult,
)
from exhaust_plume.models.moc.global_coupled_downstream import (
  build_reflected_domain_global_solver_owned_transonic_interface_placement,
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
from exhaust_plume.models.moc.moving_mixed_regime_interface import (
  MocMovingMixedRegimeInterfaceResult,
  measure_moc_moving_mixed_regime_interface,
)
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  MocReflectedDomainMixedRegimeBoundaryRequest,
  build_reflected_domain_mixed_regime_boundary_request_from_perimeter,
)
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementResult,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_interface import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
)
from exhaust_plume.validation.moc_global_transonic_mixed_wave_coverage import (
  MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage,
  assess_reflected_domain_global_transonic_mixed_wave_interface_coverage,
)

__all__ = (
  'MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_DOWNSTREAM_OPERATOR_ID',
  'MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus',
  'MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult',
  'solve_reflected_domain_global_transonic_mixed_wave_downstream',
)


MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_DOWNSTREAM_OPERATOR_ID = (
  'op.moc.reflected-domain.global-transonic-mixed-wave-downstream-field'
)
DEFAULT_CONTROL_SECTION_X_OFFSET_M = 0.02
DEFAULT_CONTROL_SECTION_SAMPLE_COUNT = 5
DEFAULT_AXIAL_CELL_COUNT = 6
DEFAULT_TRANSVERSE_CELL_COUNT = 4
DEFAULT_MAX_PSEUDO_ITERATIONS = 300
DEFAULT_MAX_SHAPE_ITERATIONS = 5
DEFAULT_TERMINAL_ANGLE_TOLERANCE_RAD = 1.0e-10
DEFAULT_TRANSONIC_PLACEMENT_SAMPLE_COUNT = 10
DEFAULT_TRANSONIC_PLACEMENT_POST_SHOCK_FRACTION = 0.25


class MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus(str, Enum):
  """Typed outcome of one mixed-wave-to-coupled-field research attempt."""

  CONVERGED_RESEARCH_FIELD = (
    'converged-research-global-transonic-mixed-wave-downstream-field'
  )
  INVALID_INPUT = 'invalid_input'
  INTERFACE_FAILURE = 'mixed-wave-downstream-interface-failure'
  HANDOFF_FAILURE = 'mixed-wave-downstream-entropy-handoff-failure'
  CONTROL_SECTION_FAILURE = 'mixed-wave-downstream-control-section-failure'
  FIELD_FAILURE = 'mixed-wave-downstream-coupled-field-failure'
  INTERFACE_COVERAGE_REQUIRED = (
    'mixed-wave-downstream-interface-coverage-required'
  )
  ADDITIONAL_ENTROPY_REQUIRED = (
    'mixed-wave-downstream-additional-entropy-required'
  )


@dataclass(frozen=True, slots=True)
class MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult:
  """Audit record for a downstream field consuming the exact local seam."""

  status: MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None
  request: MocReflectedDomainMixedRegimeBoundaryRequest | None
  field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None
  entropy_handoff: MocMixedRegimeEntropyHandoffResult | None = None
  control_section: MocMixedRegimeControlSection | None = None
  transonic_interface_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None
  subsonic_pressure_budget: (
    MocReflectedDomainCoupledEulerSubsonicPressureBudget | None
  ) = None
  interface_placement_coverage: (
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage | None
  ) = None
  moving_mixed_regime_interface: MocMovingMixedRegimeInterfaceResult | None = None
  reference_total_temperature_K: float | None = None
  interface_consumed: bool = False
  perimeter_contract_verified: bool = False
  entropy_handoff_verified: bool = False
  control_section_verified: bool = False
  transonic_interface_placement_verified: bool = False
  transonic_interface_placement_consumed: bool = False
  interface_placement_coverage_verified: bool = False
  moving_interface_verified: bool = False
  moving_interface_consumed: bool = False
  downstream_field_attempted: bool = False
  downstream_field_local_closure_verified: bool = False
  centerline_boundary_verified: bool = False
  global_coupling_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  message: str = ''

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus,
    ):
      raise TypeError('status must be a typed downstream status')
    ####
    for name, expected_type in (
      ('closure', MocReflectedDomainGlobalPhysicalClosureResult),
      (
        'interface',
        MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
      ),
      ('request', MocReflectedDomainMixedRegimeBoundaryRequest),
      ('field', MocReflectedDomainCoupledEulerFreeBoundaryResult),
      ('entropy_handoff', MocMixedRegimeEntropyHandoffResult),
      ('control_section', MocMixedRegimeControlSection),
      (
        'transonic_interface_placement',
        MocTransonicShockInterfaceFieldPlacementResult,
      ),
      (
        'subsonic_pressure_budget',
        MocReflectedDomainCoupledEulerSubsonicPressureBudget,
      ),
      (
        'interface_placement_coverage',
        MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage,
      ),
      (
        'moving_mixed_regime_interface',
        MocMovingMixedRegimeInterfaceResult,
      ),
    ):
      value = getattr(self, name)
      if value is not None and not isinstance(value, expected_type):
        raise TypeError(f'{name} must be {expected_type.__name__} or None')
      ####
    ####
    if self.reference_total_temperature_K is not None:
      temperature = float(self.reference_total_temperature_K)
      if not isfinite(temperature) or temperature <= 0.0:
        raise ValueError(
          'reference_total_temperature_K must be finite and positive'
        )
      ####
      object.__setattr__(self, 'reference_total_temperature_K', temperature)
    ####
    for name in (
      'interface_consumed',
      'perimeter_contract_verified',
      'entropy_handoff_verified',
      'control_section_verified',
      'transonic_interface_placement_verified',
      'transonic_interface_placement_consumed',
      'interface_placement_coverage_verified',
      'moving_interface_verified',
      'moving_interface_consumed',
      'downstream_field_attempted',
      'downstream_field_local_closure_verified',
      'centerline_boundary_verified',
      'global_coupling_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    if not self.chain_promotion_blocked:
      raise ValueError('downstream mixed-wave evidence must block chain promotion')
    ####
    if self.centerline_boundary_verified:
      raise ValueError(
        'centerline_boundary_verified is reserved for a future closed seam'
      )
    ####
    if self.global_coupling_verified:
      raise ValueError(
        'global_coupling_verified is reserved for a future feedback solve'
      )
    ####
    if self.production_claim_allowed:
      raise ValueError('downstream mixed-wave evidence cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def local_downstream_field_verified(self) -> bool:
    """Whether the exact local seam reached the field solver's local gate."""

    placement_path_verified = bool(
      self.transonic_interface_placement_verified
      and self.transonic_interface_placement_consumed
      and self.interface_placement_coverage_verified
    )
    moving_path_verified = bool(
      self.moving_interface_verified
      and self.moving_interface_consumed
      and self.moving_mixed_regime_interface is not None
      and self.moving_mixed_regime_interface.boundary_seam_verified
    )
    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
      .CONVERGED_RESEARCH_FIELD
      and self.interface_consumed
      and self.perimeter_contract_verified
      and self.entropy_handoff_verified
      and self.control_section_verified
      and (placement_path_verified or moving_path_verified)
      and self.downstream_field_attempted
      and self.downstream_field_local_closure_verified
      and self.field is not None
      and self.field.local_physical_closure_verified
      and self.chain_promotion_blocked
      and not self.centerline_boundary_verified
      and not self.global_coupling_verified
      and not self.production_claim_allowed
    )
  ####

  @property
  def additional_entropy_required(self) -> bool:
    """Whether the retained field exposed an unreachable subsonic budget.

    This is a typed physics requirement, not a convergence or promotion gate.
    It records that the current control-section total pressure cannot reach the
    requested ambient pressure on an isentropic subsonic branch.  A future
    joint solver must supply and independently verify the missing
    entropy-producing mechanism; this result never invents that loss.
    """

    return bool(
      self.status
      is MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
      .ADDITIONAL_ENTROPY_REQUIRED
      and self.subsonic_pressure_budget is not None
      and self.subsonic_pressure_budget.status
      is MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
      .BELOW_ISENTROPIC_SUBSONIC_BOUNDS
      and self.chain_promotion_blocked
      and not self.production_claim_allowed
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """The local downstream solve is not a globally coupled closure."""

    return False
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """Independent downstream boundary evidence remains open."""

    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': MOC_REFLECTED_DOMAIN_GLOBAL_TRANSONIC_MIXED_WAVE_DOWNSTREAM_OPERATOR_ID,
      'status': self.status.value,
      'local_downstream_field_verified': self.local_downstream_field_verified,
      'additional_entropy_required': self.additional_entropy_required,
      'physical_closure_verified': self.physical_closure_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'interface_consumed': self.interface_consumed,
      'perimeter_contract_verified': self.perimeter_contract_verified,
      'entropy_handoff_verified': self.entropy_handoff_verified,
      'control_section_verified': self.control_section_verified,
      'transonic_interface_placement_verified': (
        self.transonic_interface_placement_verified
      ),
      'transonic_interface_placement_consumed': (
        self.transonic_interface_placement_consumed
      ),
      'interface_placement_coverage_verified': (
        self.interface_placement_coverage_verified
      ),
      'downstream_field_attempted': self.downstream_field_attempted,
      'downstream_field_local_closure_verified': (
        self.downstream_field_local_closure_verified
      ),
      'centerline_boundary_verified': self.centerline_boundary_verified,
      'global_coupling_verified': self.global_coupling_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'closure': None if self.closure is None else self.closure.as_report(),
      'interface': (
        None if self.interface is None else self.interface.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'entropy_handoff': (
        None
        if self.entropy_handoff is None
        else self.entropy_handoff.as_report()
      ),
      'control_section': (
        None
        if self.control_section is None
        else self.control_section.as_report()
      ),
      'transonic_interface_placement': (
        None
        if self.transonic_interface_placement is None
        else self.transonic_interface_placement.as_report()
      ),
      'subsonic_pressure_budget': (
        None
        if self.subsonic_pressure_budget is None
        else self.subsonic_pressure_budget.as_report()
      ),
      'interface_placement_coverage': (
        None
        if self.interface_placement_coverage is None
        else self.interface_placement_coverage.as_report()
      ),
      'moving_mixed_regime_interface': (
        None
        if self.moving_mixed_regime_interface is None
        else self.moving_mixed_regime_interface.as_report()
      ),
      'moving_interface_verified': self.moving_interface_verified,
      'moving_interface_consumed': self.moving_interface_consumed,
      'field': None if self.field is None else self.field.as_report(),
      'claim_status': (
        'research-only downstream coupled-Euler field driven by an explicit '
        'mixed-wave terminal; centerline closure, global feedback, external '
        'validation, and production claims remain blocked'
      ),
      'message': self.message,
    }
  ####


def _failure(
  status: MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus,
  message: str,
  *,
  closure: MocReflectedDomainGlobalPhysicalClosureResult | None = None,
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult | None = None,
  request: MocReflectedDomainMixedRegimeBoundaryRequest | None = None,
  field: MocReflectedDomainCoupledEulerFreeBoundaryResult | None = None,
  entropy_handoff: MocMixedRegimeEntropyHandoffResult | None = None,
  control_section: MocMixedRegimeControlSection | None = None,
  transonic_interface_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None,
  subsonic_pressure_budget: (
    MocReflectedDomainCoupledEulerSubsonicPressureBudget | None
  ) = None,
  interface_placement_coverage: (
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceCoverage | None
  ) = None,
  moving_mixed_regime_interface: MocMovingMixedRegimeInterfaceResult | None = None,
  reference_total_temperature_K: float | None = None,
  interface_consumed: bool = False,
  perimeter_contract_verified: bool = False,
  entropy_handoff_verified: bool = False,
  control_section_verified: bool = False,
  transonic_interface_placement_verified: bool = False,
  transonic_interface_placement_consumed: bool = False,
  interface_placement_coverage_verified: bool = False,
  moving_interface_verified: bool = False,
  moving_interface_consumed: bool = False,
  downstream_field_attempted: bool = False,
  downstream_field_local_closure_verified: bool = False,
) -> MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult:
  return MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult(
    status=status,
    closure=closure,
    interface=interface,
    request=request,
    field=field,
    entropy_handoff=entropy_handoff,
    control_section=control_section,
    transonic_interface_placement=transonic_interface_placement,
    subsonic_pressure_budget=subsonic_pressure_budget,
    interface_placement_coverage=interface_placement_coverage,
    moving_mixed_regime_interface=moving_mixed_regime_interface,
    reference_total_temperature_K=reference_total_temperature_K,
    interface_consumed=interface_consumed,
    perimeter_contract_verified=perimeter_contract_verified,
    entropy_handoff_verified=entropy_handoff_verified,
    control_section_verified=control_section_verified,
    transonic_interface_placement_verified=(
      transonic_interface_placement_verified
    ),
    transonic_interface_placement_consumed=(
      transonic_interface_placement_consumed
    ),
    interface_placement_coverage_verified=(
      interface_placement_coverage_verified
    ),
    moving_interface_verified=moving_interface_verified,
    moving_interface_consumed=moving_interface_consumed,
    downstream_field_attempted=downstream_field_attempted,
    downstream_field_local_closure_verified=(
      downstream_field_local_closure_verified
    ),
    message=message,
  )


def _build_control_section(
  perimeter_request: MocMixedRegimePerimeterRequest,
  entropy_handoff: MocMixedRegimeEntropyHandoffResult,
  *,
  height_m: float,
  x_offset_m: float,
  sample_count: int,
  contract_source: str,
  terminal_angle_tolerance_rad: float,
) -> MocMixedRegimeControlSection:
  if not entropy_handoff.converged:
    raise ValueError(
      'a converged entropy handoff is required for the downstream control '
      'section'
    )
  ####
  terminal = perimeter_request.terminal
  gamma = float(terminal.upstream_state.gamma)
  mach = float(perimeter_request.terminal_downstream_mach)
  terminal_angle = perimeter_request.terminal_downstream_flow_angle_rad
  if terminal_angle is None:
    raise ValueError('mixed-wave terminal downstream angle is unavailable')
  ####
  if abs(float(terminal_angle)) > terminal_angle_tolerance_rad:
    raise ValueError(
      'coupled downstream research field requires an axis-aligned terminal '
      f'flow angle, got {terminal_angle}'
    )
  ####
  terminal_point = perimeter_request.terminal_point_m
  section_x = terminal_point[0] + x_offset_m
  samples: list[MocMixedRegimeFieldSample] = []
  for index in range(sample_count):
    fraction = index / (sample_count - 1)
    source_arc = entropy_handoff.cumulative_arc_length_m[-1] * (1.0 - fraction)
    total_pressure = entropy_handoff.total_pressure_at_arc_length(source_arc)
    static_pressure = total_pressure / (
      1.0 + 0.5 * (gamma - 1.0) * mach * mach
    ) ** (gamma / (gamma - 1.0))
    samples.append(
      MocMixedRegimeFieldSample(
        point_m=(section_x, terminal_point[1] + fraction * height_m),
        mach=mach,
        flow_angle_rad=float(terminal_angle),
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
    source=f'{contract_source}:control-section',
  )


def solve_reflected_domain_global_transonic_mixed_wave_downstream(
  closure: MocReflectedDomainGlobalPhysicalClosureResult,
  interface: MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  *,
  reference_total_temperature_K: float,
  control_section_height_m: float | None = None,
  control_section_x_offset_m: float = DEFAULT_CONTROL_SECTION_X_OFFSET_M,
  control_section_sample_count: int = DEFAULT_CONTROL_SECTION_SAMPLE_COUNT,
  downstream_length_m: float | None = None,
  axial_cell_count: int = DEFAULT_AXIAL_CELL_COUNT,
  transverse_cell_count: int = DEFAULT_TRANSVERSE_CELL_COUNT,
  max_pseudo_iterations: int = DEFAULT_MAX_PSEUDO_ITERATIONS,
  max_shape_iterations: int = DEFAULT_MAX_SHAPE_ITERATIONS,
  terminal_angle_tolerance_rad: float = DEFAULT_TERMINAL_ANGLE_TOLERANCE_RAD,
  transonic_placement_sample_count: int = (
    DEFAULT_TRANSONIC_PLACEMENT_SAMPLE_COUNT
  ),
  transonic_placement_post_shock_fraction: float = (
    DEFAULT_TRANSONIC_PLACEMENT_POST_SHOCK_FRACTION
  ),
  moving_mixed_regime_interface: MocMovingMixedRegimeInterfaceResult | None = None,
) -> MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult:
  """Consume one verified local interface inside the coupled Euler field.

  The control-section height and downstream length may be carried by the
  interface's optional study metadata.  If that metadata is absent, callers
  must provide the values explicitly; this operator never invents a geometry
  from the terminal point.
  """

  if not isinstance(
    closure,
    MocReflectedDomainGlobalPhysicalClosureResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INVALID_INPUT,
      'closure must be a MocReflectedDomainGlobalPhysicalClosureResult',
    )
  ####
  if not isinstance(
    interface,
    MocReflectedDomainGlobalTransonicMixedWaveInterfaceResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INVALID_INPUT,
      'interface must be a typed global transonic mixed-wave interface result',
      closure=closure,
    )
  ####
  if moving_mixed_regime_interface is not None and not isinstance(
    moving_mixed_regime_interface,
    MocMovingMixedRegimeInterfaceResult,
  ):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INVALID_INPUT,
      'moving_mixed_regime_interface must be a typed moving-interface result',
      closure=closure,
      interface=interface,
    )
  ####
  if not closure.converged or not closure.physical_closure_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INTERFACE_FAILURE,
      'global reflected closure is not locally physically verified',
      closure=closure,
      interface=interface,
    )
  ####
  interface_consumed = bool(interface.local_interface_verified)
  perimeter_request = interface.perimeter_request
  if not interface_consumed or perimeter_request is None:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INTERFACE_FAILURE,
      'mixed-wave interface must pass its local gates and retain a perimeter '
      'request before entering the downstream field',
      closure=closure,
      interface=interface,
      interface_consumed=interface_consumed,
    )
  ####
  try:
    reference_temperature = float(reference_total_temperature_K)
    if not isfinite(reference_temperature) or reference_temperature <= 0.0:
      raise ValueError(
        'reference_total_temperature_K must be finite and positive'
      )
    ####
    resolved_height = (
      interface.effective_inlet_height_m
      if control_section_height_m is None
      else float(control_section_height_m)
    )
    resolved_length = (
      interface.downstream_length_m
      if downstream_length_m is None
      else float(downstream_length_m)
    )
    if resolved_height is None or not isfinite(float(resolved_height)) or float(resolved_height) <= 0.0:
      raise ValueError(
        'control_section_height_m must be supplied when the interface does not '
        'retain an effective inlet height'
      )
    ####
    if resolved_length is None or not isfinite(float(resolved_length)) or float(resolved_length) <= 0.0:
      raise ValueError(
        'downstream_length_m must be supplied when the interface does not '
        'retain a downstream length'
      )
    ####
    if not isfinite(float(control_section_x_offset_m)) or float(control_section_x_offset_m) <= 0.0:
      raise ValueError('control_section_x_offset_m must be finite and positive')
    ####
    if (
      isinstance(control_section_sample_count, bool)
      or not isinstance(control_section_sample_count, int)
      or control_section_sample_count < 3
    ):
      raise ValueError('control_section_sample_count must be at least three')
    ####
    if (
      isinstance(axial_cell_count, bool)
      or not isinstance(axial_cell_count, int)
      or axial_cell_count < 2
    ):
      raise ValueError('axial_cell_count must be at least two')
    ####
    if (
      isinstance(transverse_cell_count, bool)
      or not isinstance(transverse_cell_count, int)
      or transverse_cell_count < 2
    ):
      raise ValueError('transverse_cell_count must be at least two')
    ####
    if (
      isinstance(max_pseudo_iterations, bool)
      or not isinstance(max_pseudo_iterations, int)
      or max_pseudo_iterations < 1
    ):
      raise ValueError('max_pseudo_iterations must be positive')
    ####
    if (
      isinstance(max_shape_iterations, bool)
      or not isinstance(max_shape_iterations, int)
      or max_shape_iterations < 1
    ):
      raise ValueError('max_shape_iterations must be positive')
    ####
    angle_tolerance = float(terminal_angle_tolerance_rad)
    if not isfinite(angle_tolerance) or angle_tolerance <= 0.0:
      raise ValueError('terminal_angle_tolerance_rad must be finite and positive')
    ####
    if (
      isinstance(transonic_placement_sample_count, bool)
      or not isinstance(transonic_placement_sample_count, int)
      or transonic_placement_sample_count < 3
    ):
      raise ValueError(
        'transonic_placement_sample_count must be at least three'
      )
    ####
    placement_fraction = float(transonic_placement_post_shock_fraction)
    if not isfinite(placement_fraction) or not 0.0 < placement_fraction < 1.0:
      raise ValueError(
        'transonic_placement_post_shock_fraction must lie strictly between '
        'zero and one'
      )
  except (TypeError, ValueError):
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INVALID_INPUT,
      'downstream field controls must be finite, positive, and well-typed',
      closure=closure,
      interface=interface,
      interface_consumed=interface_consumed,
    )
  ####
  contract_source = perimeter_request.source
  perimeter_contract_verified = bool(
    bool(contract_source)
    and perimeter_request is interface.perimeter_request
  )
  try:
    entropy_handoff = build_mixed_regime_entropy_handoff(perimeter_request)
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.HANDOFF_FAILURE,
      f'mixed-wave entropy handoff raised: {error}',
      closure=closure,
      interface=interface,
      interface_consumed=interface_consumed,
      perimeter_contract_verified=perimeter_contract_verified,
    )
  ####
  entropy_handoff_verified = bool(
    entropy_handoff.converged
    and entropy_handoff.request == perimeter_request
  )
  if not entropy_handoff_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.HANDOFF_FAILURE,
      'mixed-wave entropy handoff did not retain a converged exact perimeter '
      f'lineage: {entropy_handoff.message}',
      closure=closure,
      interface=interface,
      entropy_handoff=entropy_handoff,
      interface_consumed=interface_consumed,
      perimeter_contract_verified=perimeter_contract_verified,
    )
  ####
  ambient_pressure = interface.ambient_pressure_Pa
  if ambient_pressure is None:
    if closure.source_band is None or closure.source_band.ambient_pressure_Pa is None:
      return _failure(
        MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INVALID_INPUT,
        'mixed-wave interface and global closure retain no ambient pressure',
        closure=closure,
        interface=interface,
        entropy_handoff=entropy_handoff,
        interface_consumed=interface_consumed,
        perimeter_contract_verified=perimeter_contract_verified,
        entropy_handoff_verified=entropy_handoff_verified,
      )
    ####
    ambient_pressure = closure.source_band.ambient_pressure_Pa
  ####
  try:
    control_section = _build_control_section(
      perimeter_request,
      entropy_handoff,
      height_m=float(resolved_height),
      x_offset_m=float(control_section_x_offset_m),
      sample_count=control_section_sample_count,
      contract_source=contract_source,
      terminal_angle_tolerance_rad=angle_tolerance,
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.CONTROL_SECTION_FAILURE,
      f'mixed-wave downstream control section failed: {error}',
      closure=closure,
      interface=interface,
      entropy_handoff=entropy_handoff,
      interface_consumed=interface_consumed,
      perimeter_contract_verified=perimeter_contract_verified,
      entropy_handoff_verified=entropy_handoff_verified,
    )
  ####
  control_section_verified = bool(
    len(control_section.samples) == control_section_sample_count
    and control_section.source.startswith(contract_source)
  )
  if not control_section_verified:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.CONTROL_SECTION_FAILURE,
      'mixed-wave downstream control section did not retain its exact perimeter '
      'source contract',
      closure=closure,
      interface=interface,
      entropy_handoff=entropy_handoff,
      control_section=control_section,
      interface_consumed=interface_consumed,
      perimeter_contract_verified=perimeter_contract_verified,
      entropy_handoff_verified=entropy_handoff_verified,
    )
  ####
  try:
    request = build_reflected_domain_mixed_regime_boundary_request_from_perimeter(
      closure,
      perimeter_request,
      control_section,
      perimeter_contract_source=contract_source,
      ambient_pressure_Pa=float(ambient_pressure),
      downstream_length_m=float(resolved_length),
      initial_outlet_height_m=float(resolved_height),
      control_section_x_offset_m=float(control_section_x_offset_m),
      control_section_height_m=float(resolved_height),
      control_section_sample_count=control_section_sample_count,
      entropy_handoff=entropy_handoff,
      source=(
        'solver-owned-global-transonic-mixed-wave-interface-downstream-'
        'research-request'
      ),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.CONTROL_SECTION_FAILURE,
      f'mixed-wave downstream request seam failed: {error}',
      closure=closure,
      interface=interface,
      entropy_handoff=entropy_handoff,
      control_section=control_section,
      interface_consumed=interface_consumed,
      perimeter_contract_verified=perimeter_contract_verified,
      entropy_handoff_verified=entropy_handoff_verified,
      control_section_verified=control_section_verified,
    )
  ####
  moving_interface_verified = False
  transonic_interface_placement = None
  transonic_interface_placement_verified = False
  interface_placement_coverage = None
  interface_placement_coverage_verified = False
  if moving_mixed_regime_interface is not None:
    try:
      moving_interface_audit = measure_moc_moving_mixed_regime_interface(
        moving_mixed_regime_interface
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INTERFACE_FAILURE,
        f'moving mixed-regime interface audit raised: {error}',
        closure=closure,
        interface=interface,
        request=request,
        entropy_handoff=entropy_handoff,
        control_section=control_section,
        moving_mixed_regime_interface=moving_mixed_regime_interface,
        interface_consumed=interface_consumed,
        perimeter_contract_verified=perimeter_contract_verified,
        entropy_handoff_verified=entropy_handoff_verified,
        control_section_verified=control_section_verified,
      )
    ####
    moving_interface_verified = bool(
      moving_mixed_regime_interface.boundary_seam_verified
      and moving_interface_audit.converged
      and moving_mixed_regime_interface.request.sample_count
      == transverse_cell_count
      and moving_mixed_regime_interface.request.cross_section_x_m
      > control_section.points_m[0][0]
    )
    if not moving_interface_verified:
      return _failure(
        MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INTERFACE_FAILURE,
        'moving mixed-regime interface must pass its independent seam audit, '
        'match the coupled transverse sample count, and begin strictly '
        'downstream of the solver-owned control section',
        closure=closure,
        interface=interface,
        request=request,
        entropy_handoff=entropy_handoff,
        control_section=control_section,
        moving_mixed_regime_interface=moving_mixed_regime_interface,
        interface_consumed=interface_consumed,
        perimeter_contract_verified=perimeter_contract_verified,
        entropy_handoff_verified=entropy_handoff_verified,
        control_section_verified=control_section_verified,
      )
  else:
    try:
      transonic_interface_placement = (
        build_reflected_domain_global_solver_owned_transonic_interface_placement(
          closure,
          sample_count=transonic_placement_sample_count,
          post_shock_fraction=placement_fraction,
          minimum_cross_section_x_m=control_section.points_m[0][0],
          target_downstream_static_pressure_Pa=None,
        )
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
      return _failure(
        MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INTERFACE_FAILURE,
        f'solver-owned transonic interface placement raised: {error}',
        closure=closure,
        interface=interface,
        request=request,
        entropy_handoff=entropy_handoff,
        control_section=control_section,
        interface_consumed=interface_consumed,
        perimeter_contract_verified=perimeter_contract_verified,
        entropy_handoff_verified=entropy_handoff_verified,
        control_section_verified=control_section_verified,
      )
    ####
    exact_field = None
    if closure.global_euler is not None:
      physical = closure.global_euler.physical_field
      if physical is not None:
        exact_field = physical.field
      ####
    ####
    transonic_interface_placement_verified = bool(
      transonic_interface_placement.converged
      and exact_field is not None
      and transonic_interface_placement.request.field is exact_field
      and transonic_interface_placement.field is exact_field
      and transonic_interface_placement.profile is not None
    )
    if not transonic_interface_placement_verified:
      return _failure(
        MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.INTERFACE_FAILURE,
        'solver-owned transonic interface placement did not pass its exact '
        f'field/profile lineage gate: {transonic_interface_placement.message}',
        closure=closure,
        interface=interface,
        request=request,
        entropy_handoff=entropy_handoff,
        control_section=control_section,
        transonic_interface_placement=transonic_interface_placement,
        interface_consumed=interface_consumed,
        perimeter_contract_verified=perimeter_contract_verified,
        entropy_handoff_verified=entropy_handoff_verified,
        control_section_verified=control_section_verified,
      )
    ####
    interface_placement_coverage = (
      assess_reflected_domain_global_transonic_mixed_wave_interface_coverage(
        interface,
        transonic_interface_placement,
      )
    )
    interface_placement_coverage_verified = bool(
      interface_placement_coverage.joint_interface_coverage_verified
    )
  try:
    field = solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request(
      request,
      reference_total_temperature_K=reference_temperature,
      axial_cell_count=axial_cell_count,
      transverse_cell_count=transverse_cell_count,
      max_pseudo_iterations=max_pseudo_iterations,
      max_shape_iterations=max_shape_iterations,
      inlet_boundary_mode=(
        MocReflectedDomainCoupledEulerInletBoundaryMode
        .SOLVER_OWNED_MOVING_MIXED_REGIME_SUBSONIC_FIELD
        if moving_mixed_regime_interface is not None
        else MocReflectedDomainCoupledEulerInletBoundaryMode
        .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
      ),
      transonic_shock_interface_field_placement=(
        None
        if moving_mixed_regime_interface is not None
        else transonic_interface_placement
      ),
      moving_mixed_regime_interface=moving_mixed_regime_interface,
      outlet_static_pressure_Pa=float(ambient_pressure),
    )
  except (ArithmeticError, FloatingPointError, TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.FIELD_FAILURE,
      f'mixed-wave downstream coupled field raised: {error}',
      closure=closure,
      interface=interface,
      request=request,
      entropy_handoff=entropy_handoff,
      control_section=control_section,
      transonic_interface_placement=transonic_interface_placement,
      interface_placement_coverage=interface_placement_coverage,
      moving_mixed_regime_interface=moving_mixed_regime_interface,
      reference_total_temperature_K=reference_temperature,
      interface_consumed=interface_consumed,
      perimeter_contract_verified=perimeter_contract_verified,
      entropy_handoff_verified=entropy_handoff_verified,
      control_section_verified=control_section_verified,
      transonic_interface_placement_verified=(
        transonic_interface_placement_verified
      ),
      interface_placement_coverage_verified=(
        interface_placement_coverage_verified
      ),
      moving_interface_verified=moving_interface_verified,
      downstream_field_attempted=True,
    )
  ####
  field_verified = bool(field.local_physical_closure_verified)
  subsonic_pressure_budget = field.subsonic_pressure_budget
  transonic_interface_placement_consumed = bool(
    field.transonic_shock_interface_field_placement
    is transonic_interface_placement
    and field.transonic_shock_interface_field_placement_consumed
    and field.transonic_shock_interface_profile_consumed
  )
  moving_interface_consumed = bool(
    moving_mixed_regime_interface is not None
    and field.moving_mixed_regime_interface is moving_mixed_regime_interface
    and field.moving_mixed_regime_interface_consumed
  )
  field_path_verified = bool(
    moving_interface_verified and moving_interface_consumed
    if moving_mixed_regime_interface is not None
    else (
      transonic_interface_placement_verified
      and transonic_interface_placement_consumed
      and interface_placement_coverage_verified
    )
  )
  additional_entropy_required = bool(
    not field_verified
    and field.status
    is MocReflectedDomainCoupledEulerFreeBoundaryStatus.FREE_BOUNDARY_FAILURE
    and subsonic_pressure_budget is not None
    and subsonic_pressure_budget.status
    is MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
    .BELOW_ISENTROPIC_SUBSONIC_BOUNDS
  )
  status = (
    MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
    .CONVERGED_RESEARCH_FIELD
    if field_verified and field_path_verified
    else (
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
      .INTERFACE_COVERAGE_REQUIRED
      if (
        field_verified
        and moving_mixed_regime_interface is None
        and not interface_placement_coverage_verified
      )
      else (
      MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus
      .ADDITIONAL_ENTROPY_REQUIRED
      if additional_entropy_required
      else MocReflectedDomainGlobalTransonicMixedWaveDownstreamStatus.FIELD_FAILURE
      )
    )
  )
  coverage_message = ''
  if (
    moving_mixed_regime_interface is None
    and not interface_placement_coverage_verified
  ):
    assert interface_placement_coverage is not None
    coverage_message = (
      ' The joint interface-coverage audit remains open: '
      f'{interface_placement_coverage.message}; no boundary extension or '
      'extrapolation was used.'
    )
  if additional_entropy_required:
    assert subsonic_pressure_budget is not None
    message = (
      'the exact mixed-wave terminal and solver-owned '
      + (
        'moving-interface conservative section '
        if moving_mixed_regime_interface is not None
        else 'transonic placement '
      )
      + 'entered the coupled Euler field, but the retained subsonic branch '
      'cannot reach ambient without additional entropy-producing physics: '
      f"the pressure budget requires at least "
      f"{subsonic_pressure_budget.minimum_additional_total_pressure_loss_fraction:.6g} "
      'additional total-pressure loss; the field remains unclosed and no '
      'loss, geometry, or lower-fidelity fallback was invented.'
      f'{coverage_message}'
    )
  else:
    message = (
      'exact mixed-wave terminal, entropy handoff, and solver-owned control '
      'section were consumed by the coupled Euler field; local downstream '
      'closure passed while centerline/global coupling and promotion remain '
      'blocked'
      if field_verified
      else (
        'the exact mixed-wave terminal entered the coupled Euler field, but '
        'the local downstream field gate did not pass: '
        f'{field.message}.{coverage_message}'
      )
    )
    if (
      field_verified
      and moving_mixed_regime_interface is None
      and not interface_placement_coverage_verified
    ):
      message = (
        'the coupled Euler field passed its local residual gate, but the '
        'exact mixed-wave shock and ambient traces do not cover the selected '
        f'placement; the result remains research-only.{coverage_message}'
      )
  return MocReflectedDomainGlobalTransonicMixedWaveDownstreamResult(
    status=status,
    closure=closure,
    interface=interface,
    request=request,
    field=field,
    entropy_handoff=entropy_handoff,
    control_section=control_section,
    transonic_interface_placement=transonic_interface_placement,
    moving_mixed_regime_interface=moving_mixed_regime_interface,
    reference_total_temperature_K=reference_temperature,
    interface_consumed=interface_consumed,
    perimeter_contract_verified=perimeter_contract_verified,
    entropy_handoff_verified=entropy_handoff_verified,
    control_section_verified=control_section_verified,
    transonic_interface_placement_verified=(
      transonic_interface_placement_verified
    ),
    transonic_interface_placement_consumed=(
      transonic_interface_placement_consumed
    ),
    interface_placement_coverage=interface_placement_coverage,
    interface_placement_coverage_verified=(
      interface_placement_coverage_verified
    ),
    moving_interface_verified=moving_interface_verified,
    moving_interface_consumed=moving_interface_consumed,
    subsonic_pressure_budget=subsonic_pressure_budget,
    downstream_field_attempted=True,
    downstream_field_local_closure_verified=field_verified,
    message=message,
  )
