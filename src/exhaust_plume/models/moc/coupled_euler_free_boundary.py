"""Research-only coupled Euler/free-boundary continuation for the MOC lane.

The existing mixed-regime variable-entropy model is a valuable, fast
reference, but it maps pressure and entropy along prescribed stream tubes.  A
canonical downstream closure needs a field solve that carries the conservative
Euler state while the ambient boundary and its geometry are updated together.

This module provides the first bounded implementation of that higher-fidelity
step.  It is deliberately restricted to a calorically perfect gas with one
constant ``gamma`` and a supplied total temperature.  The result exposes the
mesh, conservative state, boundary residuals, and solver diagnostics, but it
never grants canonical or production status.  An independent validator and
external validation data remain separate promotion gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from math import isfinite, sqrt
from types import MappingProxyType
from typing import Any

import numpy as np

from exhaust_plume.models.moc.chain import (
  MocChainTerminationDecision,
  MocChainTerminationReason,
)
from exhaust_plume.models.moc.reflected_domain_mixed_regime import (
  MocReflectedDomainMixedRegimeBoundaryRequest,
)
from exhaust_plume.models.moc.transonic_transition import (
  MocTransonicTransitionAudit,
  MocTransonicTransitionRequest,
  MocTransonicTransitionResult,
  MocTransonicTransitionStatus,
  MocTransonicShockGeometryAudit,
  MocTransonicShockGeometryRequest,
  MocTransonicShockGeometryResult,
  measure_moc_transonic_shock_geometry,
  measure_moc_transonic_transition,
  solve_moc_transonic_shock_geometry,
  solve_moc_transonic_transition,
)

__all__ = (
  'MocReflectedDomainCoupledEulerFreeBoundaryStatus',
  'MocReflectedDomainCoupledEulerInletBoundaryMode',
  'MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus',
  'MocReflectedDomainCoupledEulerSubsonicPressureBudget',
  'MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus',
  'MocReflectedDomainCoupledEulerControlSectionCompatibility',
  'MocReflectedDomainCoupledEulerFreeBoundaryRequest',
  'MocReflectedDomainCoupledEulerFreeBoundaryResult',
  'build_reflected_domain_coupled_euler_free_boundary_request',
  'assess_reflected_domain_coupled_euler_subsonic_pressure_budget',
  'assess_reflected_domain_coupled_euler_transonic_transition',
  'assess_reflected_domain_coupled_euler_control_section_compatibility',
  'solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request',
  'solve_reflected_domain_coupled_euler_free_boundary',
)


COUPLED_EULER_FREE_BOUNDARY_MODEL = (
  'research-coupled-calorically-perfect-euler-free-boundary'
)
COUPLED_EULER_FREE_BOUNDARY_FLUX_MODEL = (
  'specified-pressure-material-streamline-v1'
)
_CHANNEL_NAMES = (
  'mass',
  'streamwise_momentum',
  'transverse_momentum',
  'energy',
  'euler',
)


class MocReflectedDomainCoupledEulerFreeBoundaryStatus(str, Enum):
  """Outcome for the bounded coupled Euler/free-boundary solve."""

  CONVERGED_LOCAL_PHYSICAL_CLOSURE = (
    'converged-local-coupled-euler-free-boundary-closure'
  )
  INVALID_INPUT = 'invalid_input'
  UPSTREAM_CLOSURE_FAILURE = 'coupled-euler-upstream-closure-failure'
  NONUNIFORM_GAMMA = 'coupled-euler-nonuniform-gamma'
  CONTROL_SECTION_FAILURE = 'coupled-euler-control-section-failure'
  THERMODYNAMIC_FAILURE = 'coupled-euler-thermodynamic-failure'
  MESH_FAILURE = 'coupled-euler-mesh-failure'
  POSITIVITY_FAILURE = 'coupled-euler-positivity-failure'
  SOLVER_FAILURE = 'coupled-euler-pseudo-time-failure'
  FREE_BOUNDARY_FAILURE = 'coupled-euler-free-boundary-failure'
  RESIDUAL_FAILURE = 'coupled-euler-residual-failure'
  INLET_CHARACTERISTIC_FAILURE = 'coupled-euler-inlet-characteristic-failure'
  INLET_SHOCK_BRANCH_FAILURE = 'coupled-euler-inlet-shock-branch-failure'
####


class MocReflectedDomainCoupledEulerInletBoundaryMode(str, Enum):
  """Research inlet treatment for the coupled constant-gamma field."""

  FULL_STATE_RUSANOV = 'full-state-rusanov'
  SUBSONIC_CHARACTERISTIC = 'subsonic-characteristic'
  SCALAR_NORMAL_SHOCK_BRANCH = 'scalar-normal-shock-branch'
####


class MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus(str, Enum):
  """One-dimensional pressure reachability evidence for a subsonic exit."""

  WITHIN_ISENTROPIC_SUBSONIC_BOUNDS = (
    'within-isentropic-subsonic-pressure-bounds'
  )
  BELOW_ISENTROPIC_SUBSONIC_BOUNDS = (
    'below-isentropic-subsonic-pressure-bounds'
  )
  ABOVE_ISENTROPIC_SUBSONIC_BOUNDS = (
    'above-isentropic-subsonic-pressure-bounds'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerSubsonicPressureBudget:
  """A non-gating pressure-budget diagnostic for the coupled research lane.

  The bounds are the isentropic static-pressure range implied by the outer
  control-section total pressure for Mach numbers from zero to the sonic
  limit.  A two-dimensional field may produce additional entropy and change
  that budget; this record therefore identifies a required physics seam but
  never rejects or promotes a field by itself.
  """

  status: MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
  target_static_pressure_Pa: float
  reference_total_pressure_Pa: float
  subsonic_static_pressure_lower_bound_Pa: float
  subsonic_static_pressure_upper_bound_Pa: float
  maximum_total_pressure_compatible_with_target_Pa: float
  total_pressure_compatibility_ratio: float
  minimum_additional_total_pressure_loss_fraction: float
  gamma: float
  source: str = 'derived-outer-control-section-isentropic-pressure-budget'

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus'
      )
    ####
    for name in (
      'target_static_pressure_Pa',
      'reference_total_pressure_Pa',
      'subsonic_static_pressure_lower_bound_Pa',
      'subsonic_static_pressure_upper_bound_Pa',
      'maximum_total_pressure_compatible_with_target_Pa',
      'total_pressure_compatibility_ratio',
      'gamma',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, value)
    ####
    loss_fraction = float(self.minimum_additional_total_pressure_loss_fraction)
    if not isfinite(loss_fraction) or not 0.0 <= loss_fraction < 1.0:
      raise ValueError(
        'minimum_additional_total_pressure_loss_fraction must be finite '
        'and in the [0, 1) interval'
      )
    ####
    object.__setattr__(self, 'minimum_additional_total_pressure_loss_fraction', loss_fraction)
    if self.subsonic_static_pressure_lower_bound_Pa > (
      self.subsonic_static_pressure_upper_bound_Pa
    ):
      raise ValueError('subsonic pressure bounds must be ordered')
    ####
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'source', source)
  ####

  @property
  def reachable_without_additional_entropy(self) -> bool:
    """Whether the target lies inside the retained isentropic range."""

    return self.status is (
      MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
      .WITHIN_ISENTROPIC_SUBSONIC_BOUNDS
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'target_static_pressure_Pa': self.target_static_pressure_Pa,
      'reference_total_pressure_Pa': self.reference_total_pressure_Pa,
      'subsonic_static_pressure_lower_bound_Pa': (
        self.subsonic_static_pressure_lower_bound_Pa
      ),
      'subsonic_static_pressure_upper_bound_Pa': (
        self.subsonic_static_pressure_upper_bound_Pa
      ),
      'maximum_total_pressure_compatible_with_target_Pa': (
        self.maximum_total_pressure_compatible_with_target_Pa
      ),
      'total_pressure_compatibility_ratio': self.total_pressure_compatibility_ratio,
      'minimum_additional_total_pressure_loss_fraction': (
        self.minimum_additional_total_pressure_loss_fraction
      ),
      'gamma': self.gamma,
      'reachable_without_additional_entropy': self.reachable_without_additional_entropy,
      'source': self.source,
      'claim_status': (
        'diagnostic-only-isentropic-subsonic-pressure-budget; '
        'two-dimensional entropy production and canonical closure remain open'
      ),
    }
  ####
####


class MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus(str, Enum):
  """Classify the pressure seam at the start of the free-boundary field."""

  PRESSURE_MATCHED = 'control-section-inlet-pressure-matched'
  TARGET_BELOW_CONTROL_SECTION = 'target-below-control-section-pressure'
  TARGET_ABOVE_CONTROL_SECTION = 'target-above-control-section-pressure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerControlSectionCompatibility:
  """Explicit evidence for the control-section/free-boundary inlet seam.

  The field solver begins from a prescribed control-section state while its
  outer boundary is assigned the ambient pressure.  These values coincide
  only for the compatible research fixture.  A mismatch is not a solver
  closure and is retained as a diagnostic that identifies the missing
  characteristic or shock-placement physics at the seam.
  """

  status: MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
  target_ambient_pressure_Pa: float
  control_section_outer_static_pressure_Pa: float
  control_section_outer_total_pressure_Pa: float
  control_section_outer_mach: float
  target_minus_control_section_pressure_Pa: float
  absolute_pressure_jump_Pa: float
  absolute_pressure_jump_fraction: float
  control_section_is_subsonic: bool
  scalar_transition_status: MocTransonicTransitionStatus
  scalar_transition_required: bool
  transition_requires_supersonic_upstream: bool
  source: str = 'derived-control-section-free-boundary-inlet-seam'

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus'
      )
    ####
    for name in (
      'target_ambient_pressure_Pa',
      'control_section_outer_static_pressure_Pa',
      'control_section_outer_total_pressure_Pa',
      'control_section_outer_mach',
      'absolute_pressure_jump_Pa',
      'absolute_pressure_jump_fraction',
    ):
      value = float(getattr(self, name))
      if not isfinite(value) or value < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative')
      ####
      object.__setattr__(self, name, value)
    ####
    for name in (
      'target_ambient_pressure_Pa',
      'control_section_outer_static_pressure_Pa',
      'control_section_outer_total_pressure_Pa',
    ):
      if getattr(self, name) <= 0.0:
        raise ValueError(f'{name} must be positive')
      ####
    ####
    target_minus_control = float(self.target_minus_control_section_pressure_Pa)
    if not isfinite(target_minus_control):
      raise ValueError(
        'target_minus_control_section_pressure_Pa must be finite'
      )
    ####
    object.__setattr__(
      self,
      'target_minus_control_section_pressure_Pa',
      target_minus_control,
    )
    if not isinstance(self.scalar_transition_status, MocTransonicTransitionStatus):
      raise TypeError(
        'scalar_transition_status must be a MocTransonicTransitionStatus'
      )
    ####
    for name in (
      'control_section_is_subsonic',
      'scalar_transition_required',
      'transition_requires_supersonic_upstream',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'source', source)
  ####

  @property
  def pressure_seam_matched(self) -> bool:
    """Whether the prescribed inlet and ambient pressures coincide."""

    return self.status is (
      MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
      .PRESSURE_MATCHED
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'target_ambient_pressure_Pa': self.target_ambient_pressure_Pa,
      'control_section_outer_static_pressure_Pa': (
        self.control_section_outer_static_pressure_Pa
      ),
      'control_section_outer_total_pressure_Pa': (
        self.control_section_outer_total_pressure_Pa
      ),
      'control_section_outer_mach': self.control_section_outer_mach,
      'target_minus_control_section_pressure_Pa': (
        self.target_minus_control_section_pressure_Pa
      ),
      'absolute_pressure_jump_Pa': self.absolute_pressure_jump_Pa,
      'absolute_pressure_jump_fraction': self.absolute_pressure_jump_fraction,
      'control_section_is_subsonic': self.control_section_is_subsonic,
      'scalar_transition_status': self.scalar_transition_status.value,
      'scalar_transition_required': self.scalar_transition_required,
      'transition_requires_supersonic_upstream': (
        self.transition_requires_supersonic_upstream
      ),
      'pressure_seam_matched': self.pressure_seam_matched,
      'source': self.source,
      'claim_status': (
        'diagnostic-only-control-section-free-boundary-inlet-seam; '
        'characteristic or shock placement and canonical closure remain open'
      ),
    }
  ####
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerFreeBoundaryRequest:
  """Typed inputs for one constant-gamma downstream field solve.

  ``reference_total_temperature_K`` is explicit because the existing scalar
  mixed-regime handoff intentionally carries no absolute temperature.  It is
  a thermodynamic input to this research lane, not an inferred chemistry
  result.
  """

  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest
  reference_total_temperature_K: float
  gas_constant_J_kgK: float = 287.05
  axial_cell_count: int = 12
  transverse_cell_count: int = 6
  # The pressure-boundary flux is less diffusive than the former ghost-state
  # Rusanov boundary.  A higher, still sub-unit CFL keeps the research ladder
  # within its explicit pseudo-time budget as the mesh is refined.
  cfl_number: float = 0.85
  max_pseudo_iterations: int = 1200
  max_shape_iterations: int = 18
  euler_residual_tolerance: float = 5.0e-4
  free_boundary_pressure_tolerance_fraction: float = 0.10
  free_boundary_normal_velocity_tolerance_fraction: float = 0.05
  shape_convergence_tolerance: float = 1.0e-3
  shape_relaxation: float = 0.35
  pressure_shape_relaxation: float = 0.20
  source: str = COUPLED_EULER_FREE_BOUNDARY_MODEL
  outlet_static_pressure_Pa: float | None = None
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  )
  transonic_shock_geometry: MocTransonicShockGeometryRequest | None = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.mixed_regime_request,
      MocReflectedDomainMixedRegimeBoundaryRequest,
    ):
      raise TypeError(
        'mixed_regime_request must be a '
        'MocReflectedDomainMixedRegimeBoundaryRequest'
      )
    ####
    if not isinstance(
      self.inlet_boundary_mode,
      MocReflectedDomainCoupledEulerInletBoundaryMode,
    ):
      raise TypeError(
        'inlet_boundary_mode must be a '
        'MocReflectedDomainCoupledEulerInletBoundaryMode'
      )
    ####
    for name, value in (
      ('reference_total_temperature_K', self.reference_total_temperature_K),
      ('gas_constant_J_kgK', self.gas_constant_J_kgK),
      ('cfl_number', self.cfl_number),
      ('euler_residual_tolerance', self.euler_residual_tolerance),
      (
        'free_boundary_pressure_tolerance_fraction',
        self.free_boundary_pressure_tolerance_fraction,
      ),
      (
        'free_boundary_normal_velocity_tolerance_fraction',
        self.free_boundary_normal_velocity_tolerance_fraction,
      ),
      ('shape_convergence_tolerance', self.shape_convergence_tolerance),
      ('shape_relaxation', self.shape_relaxation),
      ('pressure_shape_relaxation', self.pressure_shape_relaxation),
    ):
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, numeric)
    ####
    if self.cfl_number >= 1.0:
      raise ValueError('cfl_number must be less than one')
    ####
    if self.free_boundary_pressure_tolerance_fraction >= 1.0:
      raise ValueError(
        'free_boundary_pressure_tolerance_fraction must be less than one'
      )
    ####
    if self.free_boundary_normal_velocity_tolerance_fraction >= 1.0:
      raise ValueError(
        'free_boundary_normal_velocity_tolerance_fraction must be less than one'
      )
    ####
    for name, minimum in (
      ('axial_cell_count', 4),
      ('transverse_cell_count', 3),
      ('max_pseudo_iterations', 20),
      ('max_shape_iterations', 1),
    ):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(
          f'{name} must be an integer greater than or equal to {minimum}'
        )
      ####
    ####
    for name in ('shape_relaxation', 'pressure_shape_relaxation'):
      if getattr(self, name) > 1.0:
        raise ValueError(f'{name} must be no greater than one')
      ####
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'source', source)
    if self.outlet_static_pressure_Pa is not None:
      outlet_pressure = float(self.outlet_static_pressure_Pa)
      if not isfinite(outlet_pressure) or outlet_pressure <= 0.0:
        raise ValueError(
          'outlet_static_pressure_Pa must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'outlet_static_pressure_Pa', outlet_pressure)
    ####
    if self.transonic_shock_geometry is not None and not isinstance(
      self.transonic_shock_geometry,
      MocTransonicShockGeometryRequest,
    ):
      raise TypeError(
        'transonic_shock_geometry must be a '
        'MocTransonicShockGeometryRequest or None'
      )
    ####
    if (
      self.inlet_boundary_mode
      is MocReflectedDomainCoupledEulerInletBoundaryMode.SCALAR_NORMAL_SHOCK_BRANCH
    ) != (self.transonic_shock_geometry is not None):
      raise ValueError(
        'scalar-normal-shock-branch mode requires transonic_shock_geometry, '
        'and other inlet modes must not supply it'
      )
    ####
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'model': COUPLED_EULER_FREE_BOUNDARY_MODEL,
      'source': self.source,
      'source_closure_fingerprint': self.source_closure_fingerprint,
      'mixed_regime_request': self.mixed_regime_request.as_report(),
      'reference_total_temperature_K': self.reference_total_temperature_K,
      'gas_constant_J_kgK': self.gas_constant_J_kgK,
      'axial_cell_count': self.axial_cell_count,
      'transverse_cell_count': self.transverse_cell_count,
      'cfl_number': self.cfl_number,
      'max_pseudo_iterations': self.max_pseudo_iterations,
      'max_shape_iterations': self.max_shape_iterations,
      'euler_residual_tolerance': self.euler_residual_tolerance,
      'free_boundary_pressure_tolerance_fraction': (
        self.free_boundary_pressure_tolerance_fraction
      ),
      'free_boundary_normal_velocity_tolerance_fraction': (
        self.free_boundary_normal_velocity_tolerance_fraction
      ),
      'shape_convergence_tolerance': self.shape_convergence_tolerance,
      'shape_relaxation': self.shape_relaxation,
      'pressure_shape_relaxation': self.pressure_shape_relaxation,
      'outlet_static_pressure_Pa': self.outlet_static_pressure_Pa,
      'inlet_boundary_mode': self.inlet_boundary_mode.value,
      'transonic_shock_geometry': (
        None
        if self.transonic_shock_geometry is None
        else self.transonic_shock_geometry.as_report()
      ),
      'free_boundary_flux_model': COUPLED_EULER_FREE_BOUNDARY_FLUX_MODEL,
      'claim_status': (
        'constant-gamma-coupled-euler-free-boundary-research-lane; '
        'independent-audit-and-external-validation-required'
      ),
    }
  ####

  @property
  def source_closure_fingerprint(self) -> str:
    """Return the exact global closure fingerprint carried by the request."""

    return self.mixed_regime_request.closure_fingerprint
  ####
####


def build_reflected_domain_coupled_euler_free_boundary_request(
  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest,
  *,
  reference_total_temperature_K: float,
  gas_constant_J_kgK: float = 287.05,
  axial_cell_count: int = 12,
  transverse_cell_count: int = 6,
  cfl_number: float = 0.85,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  euler_residual_tolerance: float = 5.0e-4,
  free_boundary_pressure_tolerance_fraction: float = 0.10,
  free_boundary_normal_velocity_tolerance_fraction: float = 0.05,
  shape_convergence_tolerance: float = 1.0e-3,
  shape_relaxation: float = 0.35,
  pressure_shape_relaxation: float = 0.20,
  source: str = COUPLED_EULER_FREE_BOUNDARY_MODEL,
  outlet_static_pressure_Pa: float | None = None,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  transonic_shock_geometry: MocTransonicShockGeometryRequest | None = None,
) -> MocReflectedDomainCoupledEulerFreeBoundaryRequest:
  """Bind one mixed-regime reference to the coupled-Euler research lane.

  The mixed-regime request must already be solver-bound to a global closure.
  This builder makes that lineage explicit at the coupled-field seam and
  prevents callers from silently replacing the upstream reference with a
  separately constructed control section.  It does not change the claim
  ceiling: the resulting request is still a constant-gamma research case.
  """

  if not isinstance(
    mixed_regime_request,
    MocReflectedDomainMixedRegimeBoundaryRequest,
  ):
    raise TypeError(
      'mixed_regime_request must be a '
      'MocReflectedDomainMixedRegimeBoundaryRequest'
    )
  ####
  return MocReflectedDomainCoupledEulerFreeBoundaryRequest(
    mixed_regime_request=mixed_regime_request,
    reference_total_temperature_K=reference_total_temperature_K,
    gas_constant_J_kgK=gas_constant_J_kgK,
    axial_cell_count=axial_cell_count,
    transverse_cell_count=transverse_cell_count,
    cfl_number=cfl_number,
    max_pseudo_iterations=max_pseudo_iterations,
    max_shape_iterations=max_shape_iterations,
    euler_residual_tolerance=euler_residual_tolerance,
    free_boundary_pressure_tolerance_fraction=(
      free_boundary_pressure_tolerance_fraction
    ),
    free_boundary_normal_velocity_tolerance_fraction=(
      free_boundary_normal_velocity_tolerance_fraction
    ),
    shape_convergence_tolerance=shape_convergence_tolerance,
    shape_relaxation=shape_relaxation,
    pressure_shape_relaxation=pressure_shape_relaxation,
    source=source,
    outlet_static_pressure_Pa=outlet_static_pressure_Pa,
    inlet_boundary_mode=inlet_boundary_mode,
    transonic_shock_geometry=transonic_shock_geometry,
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerFreeBoundaryResult:
  """Mesh-backed result with explicit local and promotion-level gates."""

  status: MocReflectedDomainCoupledEulerFreeBoundaryStatus
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None
  message: str = ''
  x_stations_m: tuple[float, ...] = ()
  free_boundary_points_m: tuple[tuple[float, float], ...] = ()
  cell_centers_m: tuple[tuple[float, float], ...] = ()
  conservative_states_by_cell: tuple[tuple[float, float, float, float], ...] = ()
  density_by_cell_kg_m3: tuple[float, ...] = ()
  static_pressure_by_cell_Pa: tuple[float, ...] = ()
  temperature_by_cell_K: tuple[float, ...] = ()
  velocity_u_by_cell_m_s: tuple[float, ...] = ()
  velocity_v_by_cell_m_s: tuple[float, ...] = ()
  mach_by_cell: tuple[float, ...] = ()
  total_pressure_by_cell_Pa: tuple[float, ...] = ()
  entropy_proxy_by_cell: tuple[float, ...] = ()
  entropy_production_fraction_by_cell: tuple[float, ...] = ()
  residual_channels_by_cell: tuple[tuple[float, float, float, float, float], ...] = ()
  residual_history: tuple[float, ...] = ()
  shape_residual_history_m: tuple[float, ...] = ()
  free_boundary_pressure_residuals_Pa: tuple[float, ...] = ()
  free_boundary_normal_velocity_residuals_m_s: tuple[float, ...] = ()
  pseudo_iteration_count: int = 0
  shape_iteration_count: int = 0
  maximum_conservative_mass_residual: float | None = None
  maximum_conservative_streamwise_momentum_residual: float | None = None
  maximum_conservative_transverse_momentum_residual: float | None = None
  maximum_conservative_energy_residual: float | None = None
  maximum_conservative_euler_residual: float | None = None
  maximum_free_boundary_pressure_residual_Pa: float | None = None
  maximum_free_boundary_normal_velocity_residual_m_s: float | None = None
  maximum_free_boundary_normal_velocity_residual_fraction: float | None = None
  maximum_shape_residual_m: float | None = None
  maximum_entropy_transport_residual: float | None = None
  maximum_entropy_production_fraction: float | None = None
  coupled_euler_field_verified: bool = False
  free_boundary_condition_verified: bool = False
  entropy_transport_verified: bool = False
  conservative_euler_residuals_measured: bool = False
  conservative_euler_residuals_verified: bool = False
  residual_channel_coverage: MappingProxyType = field(
    default_factory=lambda: MappingProxyType({})
  )
  residual_channel_validity: MappingProxyType = field(
    default_factory=lambda: MappingProxyType({})
  )
  canonical_free_boundary_verified: bool = False
  canonical_euler_verified: bool = False
  external_validation_verified: bool = False
  chain_promotion_blocked: bool = True
  production_claim_allowed: bool = False
  cell_vertices_by_cell_m: tuple[tuple[tuple[float, float], ...], ...] = ()
  subsonic_pressure_budget: (
    MocReflectedDomainCoupledEulerSubsonicPressureBudget | None
  ) = None
  transonic_transition: MocTransonicTransitionResult | None = None
  transonic_transition_audit: MocTransonicTransitionAudit | None = None
  transonic_shock_geometry: MocTransonicShockGeometryResult | None = None
  transonic_shock_geometry_audit: MocTransonicShockGeometryAudit | None = None
  control_section_compatibility: (
    MocReflectedDomainCoupledEulerControlSectionCompatibility | None
  ) = None

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerFreeBoundaryStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryStatus'
      )
    ####
    if self.request is not None and not isinstance(
      self.request,
      MocReflectedDomainCoupledEulerFreeBoundaryRequest,
    ):
      raise TypeError(
        'request must be a '
        'MocReflectedDomainCoupledEulerFreeBoundaryRequest or None'
      )
    ####
    for name in (
      'x_stations_m',
      'density_by_cell_kg_m3',
      'static_pressure_by_cell_Pa',
      'temperature_by_cell_K',
      'velocity_u_by_cell_m_s',
      'velocity_v_by_cell_m_s',
      'mach_by_cell',
      'total_pressure_by_cell_Pa',
      'entropy_proxy_by_cell',
      'entropy_production_fraction_by_cell',
      'residual_history',
      'shape_residual_history_m',
      'free_boundary_pressure_residuals_Pa',
      'free_boundary_normal_velocity_residuals_m_s',
    ):
      values = tuple(float(value) for value in getattr(self, name))
      if any(not isfinite(value) for value in values):
        raise ValueError(f'{name} must contain finite values')
      ####
      object.__setattr__(self, name, values)
    ####
    for name in ('free_boundary_points_m', 'cell_centers_m'):
      values = tuple(
        (float(point[0]), float(point[1]))
        for point in getattr(self, name)
      )
      if any(not all(isfinite(value) for value in point) for point in values):
        raise ValueError(f'{name} must contain finite points')
      ####
      object.__setattr__(self, name, values)
    ####
    states = tuple(
      tuple(float(value) for value in state)
      for state in self.conservative_states_by_cell
    )
    if any(len(state) != 4 for state in states):
      raise ValueError('conservative_states_by_cell must contain four values')
    ####
    if any(not all(isfinite(value) for value in state) for state in states):
      raise ValueError('conservative_states_by_cell must be finite')
    ####
    object.__setattr__(self, 'conservative_states_by_cell', states)
    residuals = tuple(
      tuple(float(value) for value in residual)
      for residual in self.residual_channels_by_cell
    )
    if any(len(residual) != 5 for residual in residuals):
      raise ValueError('residual_channels_by_cell must contain five values')
    ####
    if any(not all(isfinite(value) for value in residual) for residual in residuals):
      raise ValueError('residual_channels_by_cell must be finite')
    ####
    object.__setattr__(self, 'residual_channels_by_cell', residuals)
    cell_vertices = tuple(
      tuple(
        (float(point[0]), float(point[1]))
        for point in polygon
      )
      for polygon in self.cell_vertices_by_cell_m
    )
    if any(len(polygon) != 4 for polygon in cell_vertices):
      raise ValueError('cell_vertices_by_cell_m must contain quadrilateral cells')
    ####
    if any(
      not all(isfinite(value) for point in polygon for value in point)
      for polygon in cell_vertices
    ):
      raise ValueError('cell_vertices_by_cell_m must contain finite points')
    ####
    if cell_vertices and len(cell_vertices) != len(states):
      raise ValueError(
        'cell_vertices_by_cell_m must match conservative state count'
      )
    ####
    object.__setattr__(self, 'cell_vertices_by_cell_m', cell_vertices)
    if self.entropy_production_fraction_by_cell:
      if len(self.entropy_production_fraction_by_cell) != len(states):
        raise ValueError(
          'entropy_production_fraction_by_cell must match conservative state count'
        )
      ####
      if any(value < 0.0 for value in self.entropy_production_fraction_by_cell):
        raise ValueError(
          'entropy_production_fraction_by_cell must be nonnegative'
        )
      ####
    ####
    if self.subsonic_pressure_budget is not None and not isinstance(
      self.subsonic_pressure_budget,
      MocReflectedDomainCoupledEulerSubsonicPressureBudget,
    ):
      raise TypeError(
        'subsonic_pressure_budget must be a '
        'MocReflectedDomainCoupledEulerSubsonicPressureBudget or None'
      )
    ####
    if self.transonic_transition is not None and not isinstance(
      self.transonic_transition,
      MocTransonicTransitionResult,
    ):
      raise TypeError(
        'transonic_transition must be a MocTransonicTransitionResult or None'
      )
    ####
    if self.transonic_transition_audit is not None and not isinstance(
      self.transonic_transition_audit,
      MocTransonicTransitionAudit,
    ):
      raise TypeError(
        'transonic_transition_audit must be a MocTransonicTransitionAudit or None'
      )
    ####
    if self.transonic_shock_geometry is not None and not isinstance(
      self.transonic_shock_geometry,
      MocTransonicShockGeometryResult,
    ):
      raise TypeError(
        'transonic_shock_geometry must be a '
        'MocTransonicShockGeometryResult or None'
      )
    ####
    if self.transonic_shock_geometry_audit is not None and not isinstance(
      self.transonic_shock_geometry_audit,
      MocTransonicShockGeometryAudit,
    ):
      raise TypeError(
        'transonic_shock_geometry_audit must be a '
        'MocTransonicShockGeometryAudit or None'
      )
    ####
    if self.control_section_compatibility is not None and not isinstance(
      self.control_section_compatibility,
      MocReflectedDomainCoupledEulerControlSectionCompatibility,
    ):
      raise TypeError(
        'control_section_compatibility must be a '
        'MocReflectedDomainCoupledEulerControlSectionCompatibility or None'
      )
    ####
    if (
      self.transonic_transition is None
    ) != (
      self.transonic_transition_audit is None
    ):
      raise ValueError(
        'transonic_transition and transonic_transition_audit must be supplied together'
      )
    ####
    if (
      self.transonic_shock_geometry is None
    ) != (
      self.transonic_shock_geometry_audit is None
    ):
      raise ValueError(
        'transonic_shock_geometry and transonic_shock_geometry_audit must be '
        'supplied together'
      )
    ####
    if self.request is not None and (
      self.request.transonic_shock_geometry is None
    ) != (
      self.transonic_shock_geometry is None
    ):
      raise ValueError(
        'retained transonic shock geometry must match the request mode'
      )
    ####
    for name in (
      'maximum_conservative_mass_residual',
      'maximum_conservative_streamwise_momentum_residual',
      'maximum_conservative_transverse_momentum_residual',
      'maximum_conservative_energy_residual',
      'maximum_conservative_euler_residual',
      'maximum_free_boundary_pressure_residual_Pa',
      'maximum_free_boundary_normal_velocity_residual_m_s',
      'maximum_free_boundary_normal_velocity_residual_fraction',
      'maximum_shape_residual_m',
      'maximum_entropy_transport_residual',
      'maximum_entropy_production_fraction',
    ):
      value = getattr(self, name)
      if value is not None:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0.0:
          raise ValueError(f'{name} must be finite and nonnegative')
        ####
        object.__setattr__(self, name, numeric)
      ####
    ####
    for name in (
      'coupled_euler_field_verified',
      'free_boundary_condition_verified',
      'entropy_transport_verified',
      'conservative_euler_residuals_measured',
      'conservative_euler_residuals_verified',
      'canonical_free_boundary_verified',
      'canonical_euler_verified',
      'external_validation_verified',
      'chain_promotion_blocked',
      'production_claim_allowed',
    ):
      if not isinstance(getattr(self, name), bool):
        raise TypeError(f'{name} must be a bool')
      ####
    ####
    coverage = dict(self.residual_channel_coverage)
    validity = dict(self.residual_channel_validity)
    if any(
      not isinstance(key, str) or not isinstance(value, bool)
      for key, value in (*coverage.items(), *validity.items())
    ):
      raise TypeError('residual channel maps must map strings to bool values')
    ####
    object.__setattr__(self, 'residual_channel_coverage', MappingProxyType(coverage))
    object.__setattr__(self, 'residual_channel_validity', MappingProxyType(validity))
    if self.production_claim_allowed:
      raise ValueError('coupled Euler research results cannot allow production claims')
    ####
    object.__setattr__(self, 'message', str(self.message))
  ####

  @property
  def local_physical_closure_verified(self) -> bool:
    return bool(
      self.status
      is MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONVERGED_LOCAL_PHYSICAL_CLOSURE
      and self.coupled_euler_field_verified
      and self.free_boundary_condition_verified
      and self.entropy_transport_verified
      and self.conservative_euler_residuals_measured
      and self.conservative_euler_residuals_verified
    )
  ####

  @property
  def converged(self) -> bool:
    return self.local_physical_closure_verified
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """Report only the local coupled field closure, never canonical status."""

    return self.local_physical_closure_verified
  ####

  @property
  def downstream_boundary_closure_verified(self) -> bool:
    """Independent audit and cross-case evidence are still outstanding."""

    return False
  ####

  def as_chain_termination_decision(self) -> MocChainTerminationDecision:
    reason = (
      MocChainTerminationReason.FIDELITY_NOT_ALLOWED
      if self.local_physical_closure_verified
      else MocChainTerminationReason.OPEN_PHYSICAL_CLOSURE
    )
    if self.status is (
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.INVALID_INPUT
    ):
      reason = MocChainTerminationReason.INVALID_INPUT
    ####
    return MocChainTerminationDecision(
      physical_termination=False,
      reason=reason,
      message=(
        self.message
        or 'coupled Euler/free-boundary result remains research-only pending '
        'independent audit, refinement, external validation, and contract review'
      ),
      diagnostics={
        'model': COUPLED_EULER_FREE_BOUNDARY_MODEL,
        'status': self.status.value,
        'converged': self.converged,
        'local_physical_closure_verified': self.local_physical_closure_verified,
        'downstream_boundary_closure_verified': (
          self.downstream_boundary_closure_verified
        ),
        'canonical_free_boundary_verified': self.canonical_free_boundary_verified,
        'canonical_euler_verified': self.canonical_euler_verified,
        'external_validation_verified': self.external_validation_verified,
        'chain_promotion_blocked': self.chain_promotion_blocked,
        'production_claim_allowed': self.production_claim_allowed,
        'transonic_transition': (
          None
          if self.transonic_transition is None
          else self.transonic_transition.as_report()
        ),
        'transonic_transition_audit': (
          None
          if self.transonic_transition_audit is None
          else self.transonic_transition_audit.as_report()
        ),
        'control_section_compatibility': (
          None
          if self.control_section_compatibility is None
          else self.control_section_compatibility.as_report()
        ),
      },
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'model': COUPLED_EULER_FREE_BOUNDARY_MODEL,
      'converged': self.converged,
      'local_physical_closure_verified': self.local_physical_closure_verified,
      'physical_closure_verified': self.physical_closure_verified,
      'downstream_boundary_closure_verified': (
        self.downstream_boundary_closure_verified
      ),
      'x_stations_m': self.x_stations_m,
      'free_boundary_points_m': self.free_boundary_points_m,
      'cell_centers_m': self.cell_centers_m,
      'conservative_states_by_cell': self.conservative_states_by_cell,
      'density_by_cell_kg_m3': self.density_by_cell_kg_m3,
      'static_pressure_by_cell_Pa': self.static_pressure_by_cell_Pa,
      'temperature_by_cell_K': self.temperature_by_cell_K,
      'velocity_u_by_cell_m_s': self.velocity_u_by_cell_m_s,
      'velocity_v_by_cell_m_s': self.velocity_v_by_cell_m_s,
      'mach_by_cell': self.mach_by_cell,
      'total_pressure_by_cell_Pa': self.total_pressure_by_cell_Pa,
      'entropy_proxy_by_cell': self.entropy_proxy_by_cell,
      'entropy_production_fraction_by_cell': (
        self.entropy_production_fraction_by_cell
      ),
      'residual_channels_by_cell': self.residual_channels_by_cell,
      'residual_history': self.residual_history,
      'shape_residual_history_m': self.shape_residual_history_m,
      'free_boundary_pressure_residuals_Pa': (
        self.free_boundary_pressure_residuals_Pa
      ),
      'free_boundary_normal_velocity_residuals_m_s': (
        self.free_boundary_normal_velocity_residuals_m_s
      ),
      'pseudo_iteration_count': self.pseudo_iteration_count,
      'shape_iteration_count': self.shape_iteration_count,
      'maximum_conservative_mass_residual': (
        self.maximum_conservative_mass_residual
      ),
      'maximum_conservative_streamwise_momentum_residual': (
        self.maximum_conservative_streamwise_momentum_residual
      ),
      'maximum_conservative_transverse_momentum_residual': (
        self.maximum_conservative_transverse_momentum_residual
      ),
      'maximum_conservative_energy_residual': (
        self.maximum_conservative_energy_residual
      ),
      'maximum_conservative_euler_residual': (
        self.maximum_conservative_euler_residual
      ),
      'maximum_free_boundary_pressure_residual_Pa': (
        self.maximum_free_boundary_pressure_residual_Pa
      ),
      'maximum_free_boundary_normal_velocity_residual_m_s': (
        self.maximum_free_boundary_normal_velocity_residual_m_s
      ),
      'maximum_free_boundary_normal_velocity_residual_fraction': (
        self.maximum_free_boundary_normal_velocity_residual_fraction
      ),
      'maximum_shape_residual_m': self.maximum_shape_residual_m,
      'maximum_entropy_transport_residual': (
        self.maximum_entropy_transport_residual
      ),
      'maximum_entropy_production_fraction': (
        self.maximum_entropy_production_fraction
      ),
      'coupled_euler_field_verified': self.coupled_euler_field_verified,
      'free_boundary_condition_verified': self.free_boundary_condition_verified,
      'entropy_transport_verified': self.entropy_transport_verified,
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
      'external_validation_verified': self.external_validation_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'cell_vertices_by_cell_m': self.cell_vertices_by_cell_m,
      'subsonic_pressure_budget': (
        None
        if self.subsonic_pressure_budget is None
        else self.subsonic_pressure_budget.as_report()
      ),
      'transonic_transition': (
        None
        if self.transonic_transition is None
        else self.transonic_transition.as_report()
      ),
      'transonic_transition_audit': (
        None
        if self.transonic_transition_audit is None
        else self.transonic_transition_audit.as_report()
      ),
      'transonic_shock_geometry': (
        None
        if self.transonic_shock_geometry is None
        else self.transonic_shock_geometry.as_report()
      ),
      'transonic_shock_geometry_audit': (
        None
        if self.transonic_shock_geometry_audit is None
        else self.transonic_shock_geometry_audit.as_report()
      ),
      'control_section_compatibility': (
        None
        if self.control_section_compatibility is None
        else self.control_section_compatibility.as_report()
      ),
      'request': None if self.request is None else self.request.as_report(),
      'chain_termination_decision': self.as_chain_termination_decision().as_report(),
      'message': self.message,
      'claim_status': (
        'research-only-coupled-constant-gamma-euler-free-boundary; '
        'local closure evidence does not authorize canonical or production use'
      ),
    }
  ####
####


def assess_reflected_domain_coupled_euler_subsonic_pressure_budget(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> MocReflectedDomainCoupledEulerSubsonicPressureBudget:
  """Derive a non-gating subsonic pressure reachability diagnostic.

  The outermost control-section sample supplies the retained total pressure.
  For a calorically perfect gas, an isentropic subsonic state can only span
  the static-pressure interval between its stagnation and sonic limits.  The
  diagnostic quantifies how much total-pressure loss would be needed before a
  target below that interval could be reached at the sonic limit.  It does not
  assume that a future two-dimensional solver must obey this one-dimensional
  bound after shocks or mixing add entropy.
  """

  if not isinstance(
    request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
    )
  ####
  control = request.mixed_regime_request.control_section
  sample = control.samples[-1]
  gamma = float(sample.gamma)
  target_pressure = float(request.mixed_regime_request.ambient_pressure_Pa)
  reference_total_pressure = float(sample.total_pressure_Pa)
  if not isfinite(gamma) or gamma <= 1.0:
    raise ValueError('control-section gamma must be finite and greater than one')
  ####
  if not isfinite(target_pressure) or target_pressure <= 0.0:
    raise ValueError('target ambient pressure must be finite and positive')
  ####
  if not isfinite(reference_total_pressure) or reference_total_pressure <= 0.0:
    raise ValueError('outer control-section total pressure must be finite and positive')
  ####
  sonic_pressure_factor = (1.0 + 0.5 * (gamma - 1.0)) ** (
    gamma / (gamma - 1.0)
  )
  lower_bound = reference_total_pressure / sonic_pressure_factor
  upper_bound = reference_total_pressure
  maximum_compatible_total_pressure = target_pressure * sonic_pressure_factor
  compatibility_ratio = maximum_compatible_total_pressure / reference_total_pressure
  pressure_scale = max(target_pressure, lower_bound, upper_bound, 1.0)
  tolerance = 1.0e-10 * pressure_scale
  if target_pressure < lower_bound - tolerance:
    status = (
      MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
      .BELOW_ISENTROPIC_SUBSONIC_BOUNDS
    )
  elif target_pressure > upper_bound + tolerance:
    status = (
      MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
      .ABOVE_ISENTROPIC_SUBSONIC_BOUNDS
    )
  else:
    status = (
      MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus
      .WITHIN_ISENTROPIC_SUBSONIC_BOUNDS
    )
  ####
  return MocReflectedDomainCoupledEulerSubsonicPressureBudget(
    status=status,
    target_static_pressure_Pa=target_pressure,
    reference_total_pressure_Pa=reference_total_pressure,
    subsonic_static_pressure_lower_bound_Pa=lower_bound,
    subsonic_static_pressure_upper_bound_Pa=upper_bound,
    maximum_total_pressure_compatible_with_target_Pa=(
      maximum_compatible_total_pressure
    ),
    total_pressure_compatibility_ratio=compatibility_ratio,
    minimum_additional_total_pressure_loss_fraction=max(
      0.0,
      1.0 - compatibility_ratio,
    ),
    gamma=gamma,
  )
####


def assess_reflected_domain_coupled_euler_transonic_transition(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> MocTransonicTransitionResult:
  """Bind the actual coupled control-section seam to the scalar transition reference.

  The returned normal-shock target is an explicit mechanism diagnostic for a
  target below the subsonic sonic bound.  It does not alter the coupled field,
  add a shock to its mesh, or authorize a mixed-regime closure.
  """

  if not isinstance(
    request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
    )
  ####
  sample = request.mixed_regime_request.control_section.samples[-1]
  return solve_moc_transonic_transition(
    MocTransonicTransitionRequest(
      upstream_total_pressure_Pa=float(sample.total_pressure_Pa),
      target_downstream_static_pressure_Pa=(
        float(request.mixed_regime_request.ambient_pressure_Pa)
      ),
      gamma=float(sample.gamma),
      gas_constant_J_kgK=request.gas_constant_J_kgK,
      upstream_total_temperature_K=request.reference_total_temperature_K,
    )
  )
####


def assess_reflected_domain_coupled_euler_control_section_compatibility(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  transition: MocTransonicTransitionResult | None = None,
) -> MocReflectedDomainCoupledEulerControlSectionCompatibility:
  """Measure the prescribed control-section/free-boundary inlet pressure seam.

  The comparison is intentionally strict: a target within the subsonic
  pressure budget can still require a characteristic adjustment, while a
  target below the sonic bound additionally requires the scalar transition
  mechanism.  Neither condition places a transition in the two-dimensional
  field or closes the downstream boundary.
  """

  if not isinstance(
    request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    raise TypeError(
      'request must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryRequest'
    )
  ####
  if transition is None:
    transition = assess_reflected_domain_coupled_euler_transonic_transition(
      request
    )
  ####
  if not isinstance(transition, MocTransonicTransitionResult):
    raise TypeError('transition must be a MocTransonicTransitionResult or None')
  ####
  sample = request.mixed_regime_request.control_section.samples[-1]
  target_pressure = float(request.mixed_regime_request.ambient_pressure_Pa)
  control_pressure = float(sample.static_pressure_Pa)
  control_total_pressure = float(sample.total_pressure_Pa)
  control_mach = float(sample.mach)
  for name, value in (
    ('target ambient pressure', target_pressure),
    ('control-section static pressure', control_pressure),
    ('control-section total pressure', control_total_pressure),
    ('control-section Mach number', control_mach),
  ):
    if not isfinite(value) or value <= 0.0:
      raise ValueError(f'{name} must be finite and positive')
    ####
  ####
  target_minus_control = target_pressure - control_pressure
  absolute_jump = abs(target_minus_control)
  pressure_scale = max(target_pressure, control_pressure, 1.0)
  jump_fraction = absolute_jump / pressure_scale
  tolerance = 1.0e-10 * pressure_scale
  if absolute_jump <= tolerance:
    status = (
      MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
      .PRESSURE_MATCHED
    )
  elif target_minus_control < 0.0:
    status = (
      MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
      .TARGET_BELOW_CONTROL_SECTION
    )
  else:
    status = (
      MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus
      .TARGET_ABOVE_CONTROL_SECTION
    )
  ####
  control_section_is_subsonic = control_mach < 1.0 - 1.0e-10
  transition_requires_supersonic_upstream = bool(
    transition.transition_required
    and control_section_is_subsonic
    and transition.required_upstream_mach is not None
    and transition.required_upstream_mach > 1.0 + 1.0e-10
  )
  return MocReflectedDomainCoupledEulerControlSectionCompatibility(
    status=status,
    target_ambient_pressure_Pa=target_pressure,
    control_section_outer_static_pressure_Pa=control_pressure,
    control_section_outer_total_pressure_Pa=control_total_pressure,
    control_section_outer_mach=control_mach,
    target_minus_control_section_pressure_Pa=target_minus_control,
    absolute_pressure_jump_Pa=absolute_jump,
    absolute_pressure_jump_fraction=jump_fraction,
    control_section_is_subsonic=control_section_is_subsonic,
    scalar_transition_status=transition.status,
    scalar_transition_required=transition.transition_required,
    transition_requires_supersonic_upstream=(
      transition_requires_supersonic_upstream
    ),
  )
####


def _failure(
  status: MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  message: str,
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest | None,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult:
  transonic_shock_geometry = None
  transonic_shock_geometry_audit = None
  if request is not None and request.transonic_shock_geometry is not None:
    transonic_shock_geometry = solve_moc_transonic_shock_geometry(
      request.transonic_shock_geometry
    )
    transonic_shock_geometry_audit = measure_moc_transonic_shock_geometry(
      transonic_shock_geometry
    )
  ####
  return MocReflectedDomainCoupledEulerFreeBoundaryResult(
    status=status,
    request=request,
    message=message,
    transonic_shock_geometry=transonic_shock_geometry,
    transonic_shock_geometry_audit=transonic_shock_geometry_audit,
  )
####


def solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request(
  mixed_regime_request: MocReflectedDomainMixedRegimeBoundaryRequest,
  *,
  reference_total_temperature_K: float,
  gas_constant_J_kgK: float = 287.05,
  axial_cell_count: int = 12,
  transverse_cell_count: int = 6,
  cfl_number: float = 0.85,
  max_pseudo_iterations: int = 1200,
  max_shape_iterations: int = 18,
  euler_residual_tolerance: float = 5.0e-4,
  free_boundary_pressure_tolerance_fraction: float = 0.10,
  free_boundary_normal_velocity_tolerance_fraction: float = 0.05,
  shape_convergence_tolerance: float = 1.0e-3,
  shape_relaxation: float = 0.35,
  pressure_shape_relaxation: float = 0.20,
  source: str = COUPLED_EULER_FREE_BOUNDARY_MODEL,
  outlet_static_pressure_Pa: float | None = None,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  transonic_shock_geometry: MocTransonicShockGeometryRequest | None = None,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult:
  """Run the coupled research field from one bound mixed-regime reference.

  This is an orchestration seam for the actual global-to-downstream lineage:
  the caller supplies the already audited mixed-regime request, the builder
  retains its closure fingerprint, and the field solver receives the exact
  resulting request.  Invalid request construction is returned as a typed
  solver result; no fallback control section or lower-fidelity model is used.
  """

  try:
    request = build_reflected_domain_coupled_euler_free_boundary_request(
      mixed_regime_request,
      reference_total_temperature_K=reference_total_temperature_K,
      gas_constant_J_kgK=gas_constant_J_kgK,
      axial_cell_count=axial_cell_count,
      transverse_cell_count=transverse_cell_count,
      cfl_number=cfl_number,
      max_pseudo_iterations=max_pseudo_iterations,
      max_shape_iterations=max_shape_iterations,
      euler_residual_tolerance=euler_residual_tolerance,
      free_boundary_pressure_tolerance_fraction=(
        free_boundary_pressure_tolerance_fraction
      ),
      free_boundary_normal_velocity_tolerance_fraction=(
        free_boundary_normal_velocity_tolerance_fraction
      ),
      shape_convergence_tolerance=shape_convergence_tolerance,
      shape_relaxation=shape_relaxation,
      pressure_shape_relaxation=pressure_shape_relaxation,
      source=source,
      outlet_static_pressure_Pa=outlet_static_pressure_Pa,
      inlet_boundary_mode=inlet_boundary_mode,
      transonic_shock_geometry=transonic_shock_geometry,
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.INVALID_INPUT,
      f'coupled Euler request construction failed: {error}',
      None,
    )
  ####
  return solve_reflected_domain_coupled_euler_free_boundary(request)
####


def _validate_control_request(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> tuple[float, float, float, float]:
  mixed = request.mixed_regime_request
  control = mixed.control_section
  if not mixed.closure.converged or not mixed.closure.physical_closure_verified:
    raise RuntimeError(
      'mixed-regime request requires a locally physically verified upstream '
      'global Euler closure'
    )
  ####
  if abs(control.normal_angle_rad) > 1.0e-10:
    raise ValueError(
      'coupled Euler research solve currently requires an axis-aligned '
      'vertical control section'
    )
  ####
  points = control.points_m
  x_values = tuple(point[0] for point in points)
  y_values = tuple(point[1] for point in points)
  if max(x_values) - min(x_values) > 1.0e-10:
    raise ValueError('control section must be vertical for the coupled solver')
  ####
  if any(second <= first for first, second in zip(y_values, y_values[1:])):
    raise ValueError('control section ordinates must be strictly increasing')
  ####
  inlet_height = y_values[-1] - y_values[0]
  if inlet_height <= 0.0:
    raise ValueError('control section height must be positive')
  ####
  gammas = tuple(float(sample.gamma) for sample in control.samples)
  if max(gammas) - min(gammas) > 1.0e-10:
    raise ArithmeticError('control section has nonuniform gamma')
  ####
  gamma = gammas[0]
  if gamma <= 1.0 or not isfinite(gamma):
    raise ValueError('control section gamma must be finite and greater than one')
  ####
  if (
    request.inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
    and any(float(sample.mach) >= 1.0 for sample in control.samples)
  ):
    raise ValueError(
      'subsonic characteristic inlet requires every control-section sample '
      'to have Mach number below one'
    )
  ####
  return x_values[0], y_values[0], inlet_height, gamma
####


def _primitive_from_conservative(
  state: np.ndarray,
  gamma: float,
  gas_constant: float,
) -> tuple[float, float, float, float, float, float]:
  rho = float(state[0])
  if not isfinite(rho) or rho <= 0.0:
    raise FloatingPointError('conservative density is not positive')
  ####
  u = float(state[1]) / rho
  v = float(state[2]) / rho
  energy = float(state[3])
  kinetic = 0.5 * rho * (u * u + v * v)
  pressure = (gamma - 1.0) * (energy - kinetic)
  if not isfinite(pressure) or pressure <= 0.0:
    raise FloatingPointError('conservative pressure is not positive')
  ####
  temperature = pressure / (rho * gas_constant)
  if not isfinite(temperature) or temperature <= 0.0:
    raise FloatingPointError('conservative temperature is not positive')
  ####
  sound_speed = sqrt(gamma * pressure / rho)
  return rho, u, v, pressure, temperature, sound_speed
####


def _conservative_from_primitive(
  density: float,
  velocity_u: float,
  velocity_v: float,
  pressure: float,
  gamma: float,
) -> np.ndarray:
  return np.array(
    (
      density,
      density * velocity_u,
      density * velocity_v,
      pressure / (gamma - 1.0)
      + 0.5 * density * (velocity_u * velocity_u + velocity_v * velocity_v),
    ),
    dtype=float,
  )
####


def _state_from_sample(
  total_pressure: float,
  mach: float,
  flow_angle: float,
  gamma: float,
  total_temperature: float,
  gas_constant: float,
) -> np.ndarray:
  pressure_factor = 1.0 + 0.5 * (gamma - 1.0) * mach * mach
  static_pressure = total_pressure / pressure_factor ** (
    gamma / (gamma - 1.0)
  )
  static_temperature = total_temperature / pressure_factor
  density = static_pressure / (gas_constant * static_temperature)
  sound_speed = sqrt(gamma * gas_constant * static_temperature)
  speed = mach * sound_speed
  state = _conservative_from_primitive(
    density,
    speed * np.cos(flow_angle),
    speed * np.sin(flow_angle),
    static_pressure,
    gamma,
  )
  _primitive_from_conservative(state, gamma, gas_constant)
  return state
####


def _interpolate_inlet_state(
  ordinate: float,
  control_points: tuple[tuple[float, float], ...],
  control_samples: tuple[Any, ...],
  gamma: float,
  total_temperature: float,
  gas_constant: float,
) -> np.ndarray:
  ordinates = np.array([point[1] for point in control_points], dtype=float)
  clamped = float(np.clip(ordinate, ordinates[0], ordinates[-1]))
  total_pressure = float(
    np.interp(
      clamped,
      ordinates,
      [sample.total_pressure_Pa for sample in control_samples],
    )
  )
  mach = float(
    np.interp(clamped, ordinates, [sample.mach for sample in control_samples])
  )
  angle = float(
    np.interp(
      clamped,
      ordinates,
      [sample.flow_angle_rad for sample in control_samples],
    )
  )
  return _state_from_sample(
    total_pressure,
    mach,
    angle,
    gamma,
    total_temperature,
    gas_constant,
  )
####


def _subsonic_characteristic_inlet_state(
  interior_state: np.ndarray,
  reference_state: np.ndarray,
  gamma: float,
  gas_constant: float,
) -> np.ndarray:
  """Release the outgoing acoustic characteristic at a subsonic inlet.

  The control-section state supplies total pressure, total temperature, and
  flow direction.  The interior state supplies the outgoing ``u-a`` Riemann
  invariant.  Solving the resulting one-dimensional Mach equation avoids
  prescribing all primitive variables at a subsonic inlet while the outer
  boundary is pressure-coupled.
  """

  _rho, interior_u, _interior_v, _pressure, _temperature, interior_sound = (
    _primitive_from_conservative(interior_state, gamma, gas_constant)
  )
  _reference_rho, reference_u, reference_v, reference_pressure, reference_temperature, reference_sound = (
    _primitive_from_conservative(reference_state, gamma, gas_constant)
  )
  reference_speed = sqrt(reference_u * reference_u + reference_v * reference_v)
  if reference_speed <= 1.0e-12:
    raise RuntimeError(
      'subsonic characteristic inlet requires a positive reference speed'
    )
  ####
  reference_mach = reference_speed / reference_sound
  if reference_mach >= 1.0:
    raise RuntimeError(
      'subsonic characteristic inlet requires a subsonic reference state'
    )
  ####
  pressure_factor = 1.0 + 0.5 * (gamma - 1.0) * reference_mach * reference_mach
  total_temperature = reference_temperature * pressure_factor
  total_pressure = reference_pressure * pressure_factor ** (
    gamma / (gamma - 1.0)
  )
  direction_u = reference_u / reference_speed
  direction_v = reference_v / reference_speed
  outgoing_invariant = interior_u - 2.0 * interior_sound / (gamma - 1.0)
  beta = 0.5 * (gamma - 1.0)

  def state_and_residual(mach: float) -> tuple[np.ndarray, float]:
    factor = 1.0 + beta * mach * mach
    temperature = total_temperature / factor
    sound_speed = sqrt(gamma * gas_constant * temperature)
    speed = mach * sound_speed
    velocity_u = speed * direction_u
    velocity_v = speed * direction_v
    pressure = total_pressure / factor ** (gamma / (gamma - 1.0))
    density = pressure / (gas_constant * temperature)
    state = _conservative_from_primitive(
      density,
      velocity_u,
      velocity_v,
      pressure,
      gamma,
    )
    return state, velocity_u - 2.0 * sound_speed / (gamma - 1.0) - outgoing_invariant
  ####

  lower_mach = 1.0e-8
  upper_mach = 1.0 - 1.0e-8
  lower_state, lower_residual = state_and_residual(lower_mach)
  upper_state, upper_residual = state_and_residual(upper_mach)
  if abs(lower_residual) <= 1.0e-10:
    return lower_state
  ####
  if abs(upper_residual) <= 1.0e-10:
    return upper_state
  ####
  if lower_residual * upper_residual > 0.0:
    raise RuntimeError(
      'subsonic characteristic inlet has no admissible Mach root for the '
      'outgoing acoustic invariant'
    )
  ####
  for _iteration in range(80):
    middle_mach = 0.5 * (lower_mach + upper_mach)
    middle_state, middle_residual = state_and_residual(middle_mach)
    if abs(middle_residual) <= 1.0e-10:
      return middle_state
    ####
    if lower_residual * middle_residual <= 0.0:
      upper_mach = middle_mach
      upper_residual = middle_residual
    else:
      lower_mach = middle_mach
      lower_residual = middle_residual
    ####
  ####
  return state_and_residual(0.5 * (lower_mach + upper_mach))[0]
####


def _build_mesh(
  x_stations: np.ndarray,
  free_boundary_heights: np.ndarray,
  lower_ordinate: float,
  transverse_cell_count: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
  eta = np.linspace(0.0, 1.0, transverse_cell_count + 1)
  points = np.empty(
    (len(x_stations), transverse_cell_count + 1, 2),
    dtype=float,
  )
  points[:, :, 0] = x_stations[:, None]
  points[:, :, 1] = lower_ordinate + free_boundary_heights[:, None] * eta[None, :]
  corners = np.empty(
    (len(x_stations) - 1, transverse_cell_count, 4, 2),
    dtype=float,
  )
  for i in range(len(x_stations) - 1):
    for j in range(transverse_cell_count):
      corners[i, j] = (
        points[i, j],
        points[i + 1, j],
        points[i + 1, j + 1],
        points[i, j + 1],
      )
    ####
  ####
  areas = np.empty((len(x_stations) - 1, transverse_cell_count), dtype=float)
  centers = np.empty_like(areas[..., None].repeat(2, axis=-1))
  for i in range(len(x_stations) - 1):
    for j in range(transverse_cell_count):
      cell = corners[i, j]
      areas[i, j] = 0.5 * abs(
        sum(
          cell[k, 0] * cell[(k + 1) % 4, 1]
          - cell[(k + 1) % 4, 0] * cell[k, 1]
          for k in range(4)
        )
      )
      centers[i, j] = np.mean(cell, axis=0)
      if not isfinite(float(areas[i, j])) or areas[i, j] <= 0.0:
        raise ValueError('coupled Euler mesh contains a nonpositive cell area')
      ####
    ####
  ####
  return points, corners, areas, centers
####


def _face_geometry(
  first: np.ndarray,
  second: np.ndarray,
) -> tuple[float, float, float]:
  delta = second - first
  length = float(np.hypot(delta[0], delta[1]))
  if not isfinite(length) or length <= 0.0:
    raise ValueError('coupled Euler mesh contains a zero-length face')
  ####
  return float(delta[1] / length), float(-delta[0] / length), length
####


def _euler_flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  rho, u, v, pressure, _temperature, sound_speed = _primitive_from_conservative(
    state,
    gamma,
    gas_constant,
  )
  normal_velocity = u * normal_x + v * normal_y
  flux = np.array(
    (
      rho * normal_velocity,
      rho * u * normal_velocity + pressure * normal_x,
      rho * v * normal_velocity + pressure * normal_y,
      (state[3] + pressure) * normal_velocity,
    ),
    dtype=float,
  )
  return flux, abs(normal_velocity) + sound_speed
####


def _rusanov_flux(
  left: np.ndarray,
  right: np.ndarray,
  normal_x: float,
  normal_y: float,
  face_length: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  left_flux, left_wave = _euler_flux(
    left,
    normal_x,
    normal_y,
    gamma,
    gas_constant,
  )
  right_flux, right_wave = _euler_flux(
    right,
    normal_x,
    normal_y,
    gamma,
    gas_constant,
  )
  wave = max(left_wave, right_wave)
  return (
    0.5 * (left_flux + right_flux)
    - 0.5 * wave * (right - left)
  ) * face_length, wave
####


def _wall_flux(
  state: np.ndarray,
  normal_x: float,
  normal_y: float,
  face_length: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  _rho, _u, _v, pressure, _temperature, sound_speed = _primitive_from_conservative(
    state,
    gamma,
    gas_constant,
  )
  return (
    np.array((0.0, pressure * normal_x, pressure * normal_y, 0.0))
    * face_length,
    sound_speed,
  )
####


def _specified_pressure_wall_flux(
  state: np.ndarray,
  boundary_pressure: float,
  normal_x: float,
  normal_y: float,
  face_length: float,
  gamma: float,
  gas_constant: float,
) -> tuple[np.ndarray, float]:
  """Return an inviscid pressure-boundary flux with no mass crossing.

  The outer plume boundary is a material streamline with a prescribed ambient
  pressure.  A Rusanov ghost state carries a numerical mass and energy flux
  whenever the interior normal velocity is nonzero, which makes the boundary
  condition inconsistent with the free-boundary tangency constraint.  The
  pressure-boundary flux is the integral of the inviscid wall flux using the
  prescribed pressure: mass and energy flux are zero, while the pressure
  impulse acts on the boundary.  The interior sound speed remains the local
  pseudo-time wave-speed estimate.
  """

  _rho, _u, _v, _pressure, _temperature, sound_speed = (
    _primitive_from_conservative(state, gamma, gas_constant)
  )
  if not isfinite(boundary_pressure) or boundary_pressure <= 0.0:
    raise ValueError('specified pressure boundary must be finite and positive')
  ####
  return (
    np.array((0.0, boundary_pressure * normal_x, boundary_pressure * normal_y, 0.0))
    * face_length,
    sound_speed,
  )
####


def _ambient_ghost_state(
  state: np.ndarray,
  ambient_pressure: float,
  normal_x: float,
  normal_y: float,
  gamma: float,
  gas_constant: float,
) -> np.ndarray:
  rho, u, v, pressure, _temperature, _sound_speed = _primitive_from_conservative(
    state,
    gamma,
    gas_constant,
  )
  entropy_proxy = pressure / rho ** gamma
  if not isfinite(entropy_proxy) or entropy_proxy <= 0.0:
    raise FloatingPointError('ambient ghost entropy proxy is not positive')
  ####
  ghost_density = (ambient_pressure / entropy_proxy) ** (1.0 / gamma)
  return _conservative_from_primitive(
    ghost_density,
    u,
    v,
    ambient_pressure,
    gamma,
  )
####


def _cell_residuals(
  states: np.ndarray,
  points: np.ndarray,
  corners: np.ndarray,
  areas: np.ndarray,
  control_points: tuple[tuple[float, float], ...],
  control_samples: tuple[Any, ...],
  ambient_pressure: float,
  outlet_static_pressure: float | None,
  gamma: float,
  total_temperature: float,
  gas_constant: float,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode,
  inlet_override_states: tuple[np.ndarray, ...] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
  axial_count, transverse_count = areas.shape
  residual = np.zeros_like(states)
  wave_sums = np.zeros_like(areas)
  top_pressures = np.zeros(axial_count, dtype=float)
  top_normal_velocities = np.zeros(axial_count, dtype=float)
  for i in range(axial_count):
    for j in range(transverse_count):
      cell = corners[i, j]
      state = states[i, j]
      for edge_index in range(4):
        first = cell[edge_index]
        second = cell[(edge_index + 1) % 4]
        normal_x, normal_y, face_length = _face_geometry(first, second)
        if edge_index == 0 and j == 0:
          flux, wave = _wall_flux(
            state,
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
        elif edge_index == 0:
          flux, wave = _rusanov_flux(
            state,
            states[i, j - 1],
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
        elif edge_index == 1 and i == axial_count - 1:
          if outlet_static_pressure is None:
            flux, wave = _euler_flux(
              state,
              normal_x,
              normal_y,
              gamma,
              gas_constant,
            )
            flux = flux * face_length
          else:
            outlet = _ambient_ghost_state(
              state,
              outlet_static_pressure,
              normal_x,
              normal_y,
              gamma,
              gas_constant,
            )
            flux, wave = _rusanov_flux(
              state,
              outlet,
              normal_x,
              normal_y,
              face_length,
              gamma,
              gas_constant,
            )
          ####
        elif edge_index == 1:
          flux, wave = _rusanov_flux(
            state,
            states[i + 1, j],
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
        elif edge_index == 2 and j == transverse_count - 1:
          flux, wave = _specified_pressure_wall_flux(
            state,
            ambient_pressure,
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
          _rho, u, v, pressure, _temperature, _sound_speed = (
            _primitive_from_conservative(state, gamma, gas_constant)
          )
          top_pressures[i] = pressure
          top_normal_velocities[i] = u * normal_x + v * normal_y
        elif edge_index == 2:
          flux, wave = _rusanov_flux(
            state,
            states[i, j + 1],
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
        elif i == 0:
          if inlet_override_states is not None:
            if len(inlet_override_states) != transverse_count:
              raise ValueError(
                'inlet override state count must match the transverse mesh'
              )
            ####
            inlet = inlet_override_states[j]
          else:
            midpoint_ordinate = 0.5 * (first[1] + second[1])
            inlet = _interpolate_inlet_state(
              midpoint_ordinate,
              control_points,
              control_samples,
              gamma,
              total_temperature,
              gas_constant,
            )
            if (
              inlet_boundary_mode
              is MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
            ):
              inlet = _subsonic_characteristic_inlet_state(
                state,
                inlet,
                gamma,
                gas_constant,
              )
            ####
          ####
          flux, wave = _rusanov_flux(
            state,
            inlet,
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
        else:
          flux, wave = _rusanov_flux(
            state,
            states[i - 1, j],
            normal_x,
            normal_y,
            face_length,
            gamma,
            gas_constant,
          )
        ####
        residual[i, j] += flux
        wave_sums[i, j] += wave * face_length
      ####
    ####
  ####
  return residual, wave_sums, top_pressures, top_normal_velocities
####


def _normalise_residuals(
  states: np.ndarray,
  residual: np.ndarray,
  corners: np.ndarray,
  gamma: float,
  gas_constant: float,
) -> np.ndarray:
  axial_count, transverse_count = residual.shape[:2]
  normalised = np.empty((axial_count, transverse_count, 5), dtype=float)
  for i in range(axial_count):
    for j in range(transverse_count):
      _rho, u, v, pressure, _temperature, sound_speed = (
        _primitive_from_conservative(states[i, j], gamma, gas_constant)
      )
      perimeter = 0.0
      cell = corners[i, j]
      for edge_index in range(4):
        perimeter += float(
          np.linalg.norm(cell[(edge_index + 1) % 4] - cell[edge_index])
        )
      ####
      density = float(states[i, j, 0])
      energy = float(states[i, j, 3])
      speed_squared = u * u + v * v
      mass_scale = max(density * sound_speed * perimeter, 1.0e-12)
      momentum_scale = max(
        (density * speed_squared + pressure) * perimeter,
        1.0e-12,
      )
      energy_scale = max((energy + pressure) * sound_speed * perimeter, 1.0e-12)
      normalised[i, j] = (
        abs(residual[i, j, 0]) / mass_scale,
        abs(residual[i, j, 1]) / momentum_scale,
        abs(residual[i, j, 2]) / momentum_scale,
        abs(residual[i, j, 3]) / energy_scale,
        0.0,
      )
      normalised[i, j, 4] = float(np.max(normalised[i, j, :4]))
    ####
  ####
  return normalised
####


def _initial_states(
  centers: np.ndarray,
  free_boundary_heights: np.ndarray,
  lower_ordinate: float,
  control_points: tuple[tuple[float, float], ...],
  control_samples: tuple[Any, ...],
  gamma: float,
  total_temperature: float,
  gas_constant: float,
  inlet_override_states: tuple[np.ndarray, ...] | None = None,
) -> np.ndarray:
  axial_count, transverse_count = centers.shape[:2]
  states = np.empty((axial_count, transverse_count, 4), dtype=float)
  for i in range(axial_count):
    left_height = free_boundary_heights[i]
    right_height = free_boundary_heights[i + 1]
    mean_height = 0.5 * (left_height + right_height)
    for j in range(transverse_count):
      if inlet_override_states is not None:
        if len(inlet_override_states) != transverse_count:
          raise ValueError(
            'inlet override state count must match the transverse mesh'
          )
        ####
        states[i, j] = inlet_override_states[j]
        continue
      ####
      eta = (centers[i, j, 1] - lower_ordinate) / mean_height
      ordinate = control_points[0][1] + np.clip(eta, 0.0, 1.0) * (
        control_points[-1][1] - control_points[0][1]
      )
      states[i, j] = _interpolate_inlet_state(
        ordinate,
        control_points,
        control_samples,
        gamma,
        total_temperature,
        gas_constant,
      )
    ####
  ####
  return states
####


def _entropy_diagnostics(
  states: np.ndarray,
  inlet_states: tuple[np.ndarray, ...],
  gamma: float,
  gas_constant: float,
) -> tuple[float, float, bool]:
  """Measure entropy loss separately from physically allowed production.

  A shock or a numerically resolved compressive layer must be allowed to
  increase the entropy proxy.  The local gate therefore rejects only entropy
  loss below the inlet envelope, while retaining the largest production
  fraction as diagnostic evidence.  This is still a research-lane inequality
  check: it does not identify a resolved shock or close the free boundary.
  """

  inlet_entropy = []
  for state in inlet_states:
    rho, _u, _v, pressure, _temperature, _sound_speed = (
      _primitive_from_conservative(state, gamma, gas_constant)
    )
    inlet_entropy.append(pressure / rho ** gamma)
  ####
  minimum_inlet = min(inlet_entropy)
  maximum_inlet = max(inlet_entropy)
  loss_residual = 0.0
  production_fraction = 0.0
  valid = True
  for state in states.reshape((-1, 4)):
    rho, _u, _v, pressure, _temperature, _sound_speed = (
      _primitive_from_conservative(state, gamma, gas_constant)
    )
    entropy_proxy = pressure / rho ** gamma
    if not isfinite(entropy_proxy) or entropy_proxy <= 0.0:
      valid = False
      continue
    ####
    if entropy_proxy < minimum_inlet:
      loss_residual = max(
        loss_residual,
        (minimum_inlet - entropy_proxy) / maximum(maximum_inlet, 1.0e-12),
      )
    ####
    if entropy_proxy > maximum_inlet:
      production_fraction = max(
        production_fraction,
        (entropy_proxy - maximum_inlet)
        / maximum(maximum_inlet, 1.0e-12),
      )
    ####
  ####
  return loss_residual, production_fraction, valid and loss_residual <= 0.05
####


def _inlet_states(
  control_points: tuple[tuple[float, float], ...],
  control_samples: tuple[Any, ...],
  gamma: float,
  total_temperature: float,
  gas_constant: float,
) -> tuple[np.ndarray, ...]:
  """Reconstruct the inlet state at each control-section face midpoint."""

  return tuple(
    _interpolate_inlet_state(
      0.5 * (first[1] + second[1]),
      control_points,
      control_samples,
      gamma,
      total_temperature,
      gas_constant,
    )
    for first, second in zip(control_points, control_points[1:])
  )
####


def _prepare_transonic_branch_inlet(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  *,
  x_start: float,
  lower_ordinate: float,
  inlet_height: float,
) -> tuple[
  tuple[np.ndarray, ...],
  MocTransonicShockGeometryResult,
  MocTransonicShockGeometryAudit,
]:
  """Prepare a locally closed post-shock inlet from an audited scalar branch.

  The branch is intentionally an inlet boundary condition.  It does not
  reconstruct the upstream global field or claim that the shock is placed in
  the full plume domain.
  """

  geometry_request = request.transonic_shock_geometry
  if geometry_request is None:
    raise RuntimeError(
      'scalar-normal-shock-branch mode requires a shock geometry request'
    )
  ####
  geometry = solve_moc_transonic_shock_geometry(geometry_request)
  audit = measure_moc_transonic_shock_geometry(geometry)
  if not geometry.geometry_verified or not audit.converged:
    raise RuntimeError(
      'scalar-normal-shock-branch inlet geometry failed its independent audit'
    )
  ####
  state = geometry_request.shock_state
  sample = request.mixed_regime_request.control_section.samples[-1]
  pressure_scale = max(
    request.mixed_regime_request.ambient_pressure_Pa,
    state.downstream_static_pressure_Pa,
    1.0,
  )
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(geometry.shock_point_m[0] - x_start) > x_tolerance:
    raise RuntimeError(
      'scalar-normal-shock-branch geometry must bind to the coupled-field inlet x'
    )
  ####
  if not (
    lower_ordinate - y_tolerance
    <= geometry.shock_point_m[1]
    <= lower_ordinate + inlet_height + y_tolerance
  ):
    raise RuntimeError(
      'scalar-normal-shock-branch geometry point must lie on the inlet section'
    )
  ####
  if abs(
    state.downstream_static_pressure_Pa
    - request.mixed_regime_request.ambient_pressure_Pa
  ) > 1.0e-8 * pressure_scale:
    raise RuntimeError(
      'scalar-normal-shock-branch downstream pressure must match the ambient '
      'target used to construct the branch'
    )
  ####
  if abs(state.gamma - float(sample.gamma)) > 1.0e-10:
    raise RuntimeError('scalar-normal-shock-branch gamma does not match the inlet')
  ####
  if abs(state.gas_constant_J_kgK - request.gas_constant_J_kgK) > 1.0e-10:
    raise RuntimeError(
      'scalar-normal-shock-branch gas constant does not match the inlet'
    )
  ####
  if abs(
    state.upstream_total_temperature_K - request.reference_total_temperature_K
  ) > 1.0e-8 * max(request.reference_total_temperature_K, 1.0):
    raise RuntimeError(
      'scalar-normal-shock-branch total temperature does not match the inlet'
    )
  ####
  downstream_speed = state.downstream_speed_m_s
  flow_angle = state.upstream_flow_angle_rad
  downstream_state = _conservative_from_primitive(
    state.downstream_density_kg_m3,
    downstream_speed * np.cos(flow_angle),
    downstream_speed * np.sin(flow_angle),
    state.downstream_static_pressure_Pa,
    state.gamma,
  )
  return (
    tuple(
      downstream_state.copy()
      for _ in range(request.transverse_cell_count)
    ),
    geometry,
    audit,
  )
####


def _entropy_production_fractions(
  states: np.ndarray,
  inlet_states: tuple[np.ndarray, ...],
  gamma: float,
  gas_constant: float,
) -> tuple[float, ...]:
  """Return cell-wise entropy-production evidence in flattened cell order.

  The value is a normalized excess over the maximum inlet entropy proxy.  It
  is intentionally an evidence channel rather than a shock label: numerical
  compression, mixing, or an unresolved shock can all contribute to it.
  """

  inlet_entropy_values: list[float] = []
  for state in inlet_states:
    density, _u, _v, pressure, _temperature, _sound_speed = (
      _primitive_from_conservative(state, gamma, gas_constant)
    )
    inlet_entropy_values.append(pressure / density ** gamma)
  ####
  inlet_entropy = tuple(inlet_entropy_values)
  if not inlet_entropy:
    raise ValueError('entropy-production evidence requires inlet states')
  ####
  maximum_inlet = max(inlet_entropy)
  denominator = max(maximum_inlet, 1.0e-12)
  fractions: list[float] = []
  for state in states.reshape((-1, 4)):
    density, _u, _v, pressure, _temperature, _sound_speed = (
      _primitive_from_conservative(state, gamma, gas_constant)
    )
    entropy_proxy = pressure / density ** gamma
    fractions.append(max(0.0, (entropy_proxy - maximum_inlet) / denominator))
  ####
  return tuple(fractions)
####


def maximum(value: float, other: float) -> float:
  """Return the larger finite diagnostic denominator."""

  return value if value >= other else other
####


def _flatten_field(
  states: np.ndarray,
  centers: np.ndarray,
  residual_channels: np.ndarray,
  gamma: float,
  gas_constant: float,
) -> dict[str, tuple[Any, ...]]:
  centers_out: list[tuple[float, float]] = []
  states_out: list[tuple[float, float, float, float]] = []
  residuals_out: list[tuple[float, float, float, float, float]] = []
  density: list[float] = []
  pressure: list[float] = []
  temperature: list[float] = []
  velocity_u: list[float] = []
  velocity_v: list[float] = []
  mach: list[float] = []
  total_pressure: list[float] = []
  entropy_proxy: list[float] = []
  for index in np.ndindex(states.shape[:2]):
    state = states[index]
    rho, u, v, static_pressure, static_temperature, sound_speed = (
      _primitive_from_conservative(state, gamma, gas_constant)
    )
    speed = sqrt(u * u + v * v)
    local_mach = speed / sound_speed
    local_total_pressure = static_pressure * (
      1.0 + 0.5 * (gamma - 1.0) * local_mach * local_mach
    ) ** (gamma / (gamma - 1.0))
    local_entropy_proxy = static_pressure / rho ** gamma
    centers_out.append(tuple(float(value) for value in centers[index]))
    states_out.append(tuple(float(value) for value in state))
    residuals_out.append(
      tuple(float(value) for value in residual_channels[index])
    )
    density.append(rho)
    pressure.append(static_pressure)
    temperature.append(static_temperature)
    velocity_u.append(u)
    velocity_v.append(v)
    mach.append(local_mach)
    total_pressure.append(local_total_pressure)
    entropy_proxy.append(local_entropy_proxy)
  ####
  return {
    'cell_centers_m': tuple(centers_out),
    'conservative_states_by_cell': tuple(states_out),
    'residual_channels_by_cell': tuple(residuals_out),
    'density_by_cell_kg_m3': tuple(density),
    'static_pressure_by_cell_Pa': tuple(pressure),
    'temperature_by_cell_K': tuple(temperature),
    'velocity_u_by_cell_m_s': tuple(velocity_u),
    'velocity_v_by_cell_m_s': tuple(velocity_v),
    'mach_by_cell': tuple(mach),
    'total_pressure_by_cell_Pa': tuple(total_pressure),
    'entropy_proxy_by_cell': tuple(entropy_proxy),
  }
####


def _result_from_field(
  status: MocReflectedDomainCoupledEulerFreeBoundaryStatus,
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  message: str,
  x_stations: np.ndarray,
  free_boundary_heights: np.ndarray,
  states: np.ndarray,
  centers: np.ndarray,
  corners: np.ndarray,
  residual_channels: np.ndarray,
  residual_history: list[float],
  shape_residual_history: list[float],
  top_pressures: np.ndarray,
  top_normal_velocities: np.ndarray,
  shape_iteration_count: int,
  pseudo_iteration_count: int,
  gamma: float,
  gas_constant: float,
  entropy_residual: float | None,
  entropy_production_fraction: float | None,
  entropy_verified: bool,
  field_verified: bool,
  boundary_verified: bool,
  inlet_override_states: tuple[np.ndarray, ...] | None = None,
  transonic_shock_geometry: MocTransonicShockGeometryResult | None = None,
  transonic_shock_geometry_audit: MocTransonicShockGeometryAudit | None = None,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult:
  flattened = _flatten_field(
    states,
    centers,
    residual_channels,
    gamma,
    gas_constant,
  )
  inlet_states = (
    inlet_override_states
    if inlet_override_states is not None
    else _inlet_states(
      request.mixed_regime_request.control_section.points_m,
      request.mixed_regime_request.control_section.samples,
      gamma,
      request.reference_total_temperature_K,
      gas_constant,
    )
  )
  flattened['entropy_production_fraction_by_cell'] = (
    _entropy_production_fractions(
      states,
      inlet_states,
      gamma,
      gas_constant,
    )
  )
  maxima = tuple(
    float(np.max(residual_channels[..., channel]))
    for channel in range(5)
  )
  speeds = np.sqrt(
    np.asarray(flattened['velocity_u_by_cell_m_s']) ** 2
    + np.asarray(flattened['velocity_v_by_cell_m_s']) ** 2
  )
  maximum_speed = max(float(np.max(speeds)), 1.0e-12)
  normal_fraction = float(np.max(np.abs(top_normal_velocities))) / maximum_speed
  channel_validity = {
    name: bool(maxima[index] <= request.euler_residual_tolerance)
    for index, name in enumerate(_CHANNEL_NAMES)
  }
  pressure_budget = (
    assess_reflected_domain_coupled_euler_subsonic_pressure_budget(request)
  )
  transonic_transition = assess_reflected_domain_coupled_euler_transonic_transition(
    request
  )
  transonic_transition_audit = measure_moc_transonic_transition(
    transonic_transition
  )
  control_section_compatibility = (
    assess_reflected_domain_coupled_euler_control_section_compatibility(
      request,
      transonic_transition,
    )
  )
  channel_coverage = {name: True for name in _CHANNEL_NAMES}
  return MocReflectedDomainCoupledEulerFreeBoundaryResult(
    status=status,
    request=request,
    message=message,
    x_stations_m=tuple(float(value) for value in x_stations),
    free_boundary_points_m=tuple(
      (float(x), float(y))
      for x, y in zip(
        x_stations,
        free_boundary_heights + request.mixed_regime_request.control_section.points_m[0][1],
        strict=True,
      )
    ),
    residual_history=tuple(residual_history),
    shape_residual_history_m=tuple(shape_residual_history),
    free_boundary_pressure_residuals_Pa=tuple(
      float(abs(value - request.mixed_regime_request.ambient_pressure_Pa))
      for value in top_pressures
    ),
    free_boundary_normal_velocity_residuals_m_s=tuple(
      float(abs(value)) for value in top_normal_velocities
    ),
    pseudo_iteration_count=pseudo_iteration_count,
    shape_iteration_count=shape_iteration_count,
    maximum_conservative_mass_residual=maxima[0],
    maximum_conservative_streamwise_momentum_residual=maxima[1],
    maximum_conservative_transverse_momentum_residual=maxima[2],
    maximum_conservative_energy_residual=maxima[3],
    maximum_conservative_euler_residual=maxima[4],
    maximum_free_boundary_pressure_residual_Pa=float(
      np.max(np.abs(top_pressures - request.mixed_regime_request.ambient_pressure_Pa))
    ),
    maximum_free_boundary_normal_velocity_residual_m_s=float(
      np.max(np.abs(top_normal_velocities))
    ),
    maximum_free_boundary_normal_velocity_residual_fraction=normal_fraction,
    maximum_shape_residual_m=(
      None
      if not shape_residual_history
      else float(max(shape_residual_history))
    ),
    maximum_entropy_transport_residual=entropy_residual,
    maximum_entropy_production_fraction=entropy_production_fraction,
    coupled_euler_field_verified=field_verified,
    free_boundary_condition_verified=boundary_verified,
    entropy_transport_verified=entropy_verified,
    conservative_euler_residuals_measured=True,
    conservative_euler_residuals_verified=all(channel_validity.values()),
    residual_channel_coverage=MappingProxyType(channel_coverage),
    residual_channel_validity=MappingProxyType(channel_validity),
    canonical_free_boundary_verified=False,
    canonical_euler_verified=False,
    external_validation_verified=False,
    chain_promotion_blocked=True,
    production_claim_allowed=False,
    cell_vertices_by_cell_m=tuple(
      tuple(
        tuple((float(point[0]), float(point[1])) for point in corners[index])
      )
      for index in np.ndindex(corners.shape[:2])
    ),
    subsonic_pressure_budget=pressure_budget,
    transonic_transition=transonic_transition,
    transonic_transition_audit=transonic_transition_audit,
    transonic_shock_geometry=transonic_shock_geometry,
    transonic_shock_geometry_audit=transonic_shock_geometry_audit,
    control_section_compatibility=control_section_compatibility,
    **flattened,
  )
####


def _solve_pseudo_time(
  states: np.ndarray,
  points: np.ndarray,
  corners: np.ndarray,
  areas: np.ndarray,
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  gamma: float,
  lower_ordinate: float,
  inlet_override_states: tuple[np.ndarray, ...] | None = None,
) -> tuple[np.ndarray, list[float], bool, bool, np.ndarray, np.ndarray, np.ndarray]:
  residual_history: list[float] = []
  residual = np.zeros_like(states)
  wave_sums = np.zeros_like(areas)
  top_pressures = np.zeros(areas.shape[0], dtype=float)
  top_normal_velocities = np.zeros(areas.shape[0], dtype=float)
  converged = False
  positivity_failure = False
  for _iteration in range(request.max_pseudo_iterations):
    residual, wave_sums, top_pressures, top_normal_velocities = _cell_residuals(
      states,
      points,
      corners,
      areas,
      request.mixed_regime_request.control_section.points_m,
      request.mixed_regime_request.control_section.samples,
      request.mixed_regime_request.ambient_pressure_Pa,
      request.outlet_static_pressure_Pa,
      gamma,
      request.reference_total_temperature_K,
      request.gas_constant_J_kgK,
      request.inlet_boundary_mode,
      inlet_override_states,
    )
    normalised = _normalise_residuals(
      states,
      residual,
      corners,
      gamma,
      request.gas_constant_J_kgK,
    )
    maximum_residual = float(np.max(normalised[..., 4]))
    if not isfinite(maximum_residual):
      positivity_failure = True
      break
    ####
    residual_history.append(maximum_residual)
    if maximum_residual <= request.euler_residual_tolerance:
      converged = True
      break
    ####
    candidate = states.copy()
    for index in np.ndindex(areas.shape):
      dt = request.cfl_number * areas[index] / max(wave_sums[index], 1.0e-12)
      delta = -dt / areas[index] * residual[index]
      relaxation = 0.8
      accepted = False
      while relaxation >= 1.0e-4:
        trial = states[index] + relaxation * delta
        try:
          _primitive_from_conservative(
            trial,
            gamma,
            request.gas_constant_J_kgK,
          )
        except (FloatingPointError, ValueError):
          relaxation *= 0.5
          continue
        ####
        candidate[index] = trial
        accepted = True
        break
      ####
      if not accepted:
        positivity_failure = True
        break
      ####
    ####
    if positivity_failure:
      break
    ####
    states = candidate
  ####
  return (
    states,
    residual_history,
    converged,
    positivity_failure,
    top_pressures,
    top_normal_velocities,
    residual,
  )
####


def solve_reflected_domain_coupled_euler_free_boundary(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult:
  """Solve the bounded constant-gamma coupled Euler/free-boundary tranche."""

  if not isinstance(
    request,
    MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  ):
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.INVALID_INPUT,
      'request must be a '
      'MocReflectedDomainCoupledEulerFreeBoundaryRequest',
      None,
    )
  ####
  try:
    x_start, lower_ordinate, inlet_height, gamma = _validate_control_request(
      request
    )
  except RuntimeError as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.UPSTREAM_CLOSURE_FAILURE,
      str(error),
      request,
    )
  except ArithmeticError as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.NONUNIFORM_GAMMA,
      str(error),
      request,
    )
  except (TypeError, ValueError) as error:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
      str(error),
      request,
    )
  ####
  if request.reference_total_temperature_K <= 0.0:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.THERMODYNAMIC_FAILURE,
      'reference total temperature must be positive',
      request,
    )
  ####
  inlet_override_states: tuple[np.ndarray, ...] | None = None
  transonic_shock_geometry: MocTransonicShockGeometryResult | None = None
  transonic_shock_geometry_audit: MocTransonicShockGeometryAudit | None = None
  if (
    request.inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode.SCALAR_NORMAL_SHOCK_BRANCH
  ):
    try:
      (
        inlet_override_states,
        transonic_shock_geometry,
        transonic_shock_geometry_audit,
      ) = _prepare_transonic_branch_inlet(
        request,
        x_start=x_start,
        lower_ordinate=lower_ordinate,
        inlet_height=inlet_height,
      )
    except RuntimeError as error:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.INLET_SHOCK_BRANCH_FAILURE,
        str(error),
        request,
      )
    ####
  ####
  x_stations = np.linspace(
    x_start,
    x_start + request.mixed_regime_request.downstream_length_m,
    request.axial_cell_count + 1,
  )
  free_boundary_heights = np.full(
    request.axial_cell_count + 1,
    request.mixed_regime_request.initial_outlet_height_m,
    dtype=float,
  )
  free_boundary_heights[0] = inlet_height
  residual_history: list[float] = []
  shape_residual_history: list[float] = []
  states: np.ndarray | None = None
  centers = np.empty((request.axial_cell_count, request.transverse_cell_count, 2))
  points = np.empty((request.axial_cell_count + 1, request.transverse_cell_count + 1, 2))
  corners = np.empty(
    (request.axial_cell_count, request.transverse_cell_count, 4, 2)
  )
  areas = np.empty((request.axial_cell_count, request.transverse_cell_count))
  final_top_pressures = np.zeros(request.axial_cell_count, dtype=float)
  final_top_normal_velocities = np.zeros(request.axial_cell_count, dtype=float)
  final_residual = np.zeros(
    (request.axial_cell_count, request.transverse_cell_count, 4),
    dtype=float,
  )
  pseudo_iteration_count = 0
  entropy_residual = None
  entropy_production_fraction = None
  entropy_verified = False
  field_verified = False
  boundary_verified = False
  converged = False
  status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.RESIDUAL_FAILURE
  message = 'coupled Euler/free-boundary solve reached its iteration limit'
  for shape_iteration in range(1, request.max_shape_iterations + 1):
    try:
      points, corners, areas, centers = _build_mesh(
        x_stations,
        free_boundary_heights,
        lower_ordinate,
        request.transverse_cell_count,
      )
      if states is None:
        states = _initial_states(
          centers,
          free_boundary_heights,
          lower_ordinate,
          request.mixed_regime_request.control_section.points_m,
          request.mixed_regime_request.control_section.samples,
          gamma,
          request.reference_total_temperature_K,
          request.gas_constant_J_kgK,
          inlet_override_states,
        )
      ####
      (
        states,
        inner_history,
        inner_converged,
        positivity_failure,
        final_top_pressures,
        final_top_normal_velocities,
        final_residual,
      ) = _solve_pseudo_time(
        states,
        points,
        corners,
        areas,
        request,
        gamma,
        lower_ordinate,
        inlet_override_states,
      )
      residual_history.extend(inner_history)
      pseudo_iteration_count += len(inner_history)
    except FloatingPointError as error:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.POSITIVITY_FAILURE
      message = str(error)
      break
    except RuntimeError as error:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.INLET_CHARACTERISTIC_FAILURE
      message = str(error)
      break
    except (ArithmeticError, TypeError, ValueError) as error:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.MESH_FAILURE
      message = str(error)
      break
    ####
    if positivity_failure:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.POSITIVITY_FAILURE
      message = 'pseudo-time update could not retain positive density and pressure'
      break
    ####
    normalised = _normalise_residuals(
      states,
      final_residual,
      corners,
      gamma,
      request.gas_constant_J_kgK,
    )
    field_verified = bool(
      inner_converged
      and float(np.max(normalised[..., 4])) <= request.euler_residual_tolerance
    )
    new_heights = free_boundary_heights.copy()
    new_heights[0] = inlet_height
    dx = request.mixed_regime_request.downstream_length_m / request.axial_cell_count
    for i in range(request.axial_cell_count):
      top_cell = states[i, request.transverse_cell_count - 1]
      _rho, u, v, pressure, _temperature, _sound_speed = (
        _primitive_from_conservative(top_cell, gamma, request.gas_constant_J_kgK)
      )
      pressure_error = (
        pressure - request.mixed_regime_request.ambient_pressure_Pa
      ) / max(pressure, request.mixed_regime_request.ambient_pressure_Pa)
      flow_slope = 0.0 if abs(u) <= 1.0e-12 else v / u
      target_slope = float(
        np.clip(
          flow_slope
          + request.pressure_shape_relaxation * pressure_error,
          -0.75,
          0.75,
        )
      )
      target_height = new_heights[i] + dx * target_slope
      lower_bound = max(0.20 * inlet_height, 1.0e-8)
      upper_bound = 5.0 * max(inlet_height, request.mixed_regime_request.initial_outlet_height_m)
      target_height = float(np.clip(target_height, lower_bound, upper_bound))
      new_heights[i + 1] = (
        (1.0 - request.shape_relaxation) * free_boundary_heights[i + 1]
        + request.shape_relaxation * target_height
      )
    ####
    shape_residual = float(np.max(np.abs(new_heights - free_boundary_heights)))
    shape_residual_history.append(shape_residual)
    speeds = np.sqrt(
      np.asarray([_primitive_from_conservative(state, gamma, request.gas_constant_J_kgK)[1] for state in states.reshape((-1, 4))]) ** 2
      + np.asarray([_primitive_from_conservative(state, gamma, request.gas_constant_J_kgK)[2] for state in states.reshape((-1, 4))]) ** 2
    )
    maximum_speed = max(float(np.max(speeds)), 1.0e-12)
    normal_fraction = float(np.max(np.abs(final_top_normal_velocities))) / maximum_speed
    pressure_residual = float(
      np.max(
        np.abs(
          final_top_pressures
          - request.mixed_regime_request.ambient_pressure_Pa
        )
      )
    )
    boundary_verified = bool(
      pressure_residual
      <= request.free_boundary_pressure_tolerance_fraction
      * request.mixed_regime_request.ambient_pressure_Pa
      and normal_fraction
      <= request.free_boundary_normal_velocity_tolerance_fraction
    )
    inlet_states = (
      inlet_override_states
      if inlet_override_states is not None
      else _inlet_states(
        request.mixed_regime_request.control_section.points_m,
        request.mixed_regime_request.control_section.samples,
        gamma,
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
    )
    (
      entropy_residual,
      entropy_production_fraction,
      entropy_verified,
    ) = _entropy_diagnostics(
      states,
      inlet_states,
      gamma,
      request.gas_constant_J_kgK,
    )
    if field_verified and boundary_verified and entropy_verified and shape_residual <= request.shape_convergence_tolerance:
      status = (
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONVERGED_LOCAL_PHYSICAL_CLOSURE
      )
      message = (
        'local coupled Euler/free-boundary residual, pressure, tangency, and '
        'entropy checks converged; promotion remains blocked'
      )
      converged = True
      break
    ####
    if shape_iteration < request.max_shape_iterations:
      free_boundary_heights = new_heights
    ####
  ####
  if states is None:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.SOLVER_FAILURE,
      message,
      request,
    )
  ####
  if not converged and status is MocReflectedDomainCoupledEulerFreeBoundaryStatus.RESIDUAL_FAILURE:
    if not field_verified:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.RESIDUAL_FAILURE
      message = 'coupled Euler conservative residual tolerance was not reached'
    elif not boundary_verified:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.FREE_BOUNDARY_FAILURE
      message = 'free-boundary pressure or tangency tolerance was not reached'
    else:
      status = MocReflectedDomainCoupledEulerFreeBoundaryStatus.SOLVER_FAILURE
    ####
  ####
  residual_channels = _normalise_residuals(
    states,
    final_residual,
    corners,
    gamma,
    request.gas_constant_J_kgK,
  )
  return _result_from_field(
    status,
    request,
    message,
    x_stations,
    free_boundary_heights,
    states,
    centers,
    corners,
    residual_channels,
    residual_history,
    shape_residual_history,
    final_top_pressures,
    final_top_normal_velocities,
    len(shape_residual_history),
    pseudo_iteration_count,
    gamma,
    request.gas_constant_J_kgK,
    entropy_residual,
    entropy_production_fraction,
    entropy_verified,
    field_verified,
    boundary_verified,
    inlet_override_states,
    transonic_shock_geometry,
    transonic_shock_geometry_audit,
  )
####
