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

from dataclasses import dataclass, field, replace
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
from exhaust_plume.models.moc.transonic_interface import (
  MocTransonicShockInterfaceFieldPlacementResult,
  MocTransonicShockInterfaceProfile,
  MocTransonicShockInterfaceResult,
  MocTransonicShockInterfaceStatus,
)
from exhaust_plume.models.moc.field_continuation import (
  MocPhysicalFieldContinuationProfile,
  MocPhysicalFieldContinuationProfileResult,
)
from exhaust_plume.models.moc.physical_field_shock_front import (
  MocPhysicalFieldShockFrontConditionResult,
)

__all__ = (
  'MocReflectedDomainCoupledEulerFreeBoundaryStatus',
  'MocReflectedDomainCoupledEulerInletBoundaryMode',
  'MocReflectedDomainCoupledEulerSubsonicPressureBudgetStatus',
  'MocReflectedDomainCoupledEulerSubsonicPressureBudget',
  'MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus',
  'MocReflectedDomainCoupledEulerPressureProfileCompatibility',
  'MocReflectedDomainCoupledEulerControlSectionCompatibilityStatus',
  'MocReflectedDomainCoupledEulerControlSectionCompatibility',
  'MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus',
  'MocReflectedDomainCoupledEulerTransonicFrontierCompatibility',
  'MocReflectedDomainCoupledEulerFreeBoundaryRequest',
  'MocReflectedDomainCoupledEulerFreeBoundaryResult',
  'MocPhysicalFieldContinuationProfile',
  'MocPhysicalFieldContinuationProfileResult',
  'MocPhysicalFieldShockFrontConditionResult',
  'build_reflected_domain_coupled_euler_free_boundary_request',
  'assess_reflected_domain_coupled_euler_subsonic_pressure_budget',
  'assess_reflected_domain_coupled_euler_pressure_profile_compatibility',
  'assess_reflected_domain_coupled_euler_transonic_transition',
  'assess_reflected_domain_coupled_euler_control_section_compatibility',
  'assess_reflected_domain_coupled_euler_transonic_frontier_compatibility',
  'solve_reflected_domain_coupled_euler_free_boundary_from_mixed_regime_request',
  'solve_reflected_domain_coupled_euler_free_boundary',
)


COUPLED_EULER_FREE_BOUNDARY_MODEL = (
  'research-coupled-calorically-perfect-euler-free-boundary'
)
COUPLED_EULER_FREE_BOUNDARY_FLUX_MODEL = (
  'specified-pressure-material-streamline-v1'
)
PHYSICAL_FIELD_AMBIENT_NEIGHBOR_PRESSURE_PROFILE_SOURCE = (
  'solver-owned-physical-field-ambient-neighbor-pressure-profile-v1'
)
PHYSICAL_FIELD_AMBIENT_NEIGHBOR_GEOMETRY_PROFILE_SOURCE = (
  'solver-owned-physical-field-ambient-neighbor-geometry-profile-v1'
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
  TRANSONIC_FRONTIER_FAILURE = 'coupled-euler-transonic-frontier-failure'
  INLET_CHARACTERISTIC_FAILURE = 'coupled-euler-inlet-characteristic-failure'
  INLET_SHOCK_BRANCH_FAILURE = 'coupled-euler-inlet-shock-branch-failure'
  INLET_SHOCK_INTERFACE_FAILURE = 'coupled-euler-inlet-shock-interface-failure'
  INLET_SHOCK_INTERFACE_PROFILE_FAILURE = (
    'coupled-euler-inlet-shock-interface-profile-failure'
  )
  INLET_SHOCK_INTERFACE_PLACEMENT_FAILURE = (
    'coupled-euler-inlet-shock-interface-placement-failure'
  )
  INLET_PHYSICAL_FIELD_CONTINUATION_FAILURE = (
    'coupled-euler-inlet-physical-field-continuation-failure'
  )
  INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE = (
    'coupled-euler-inlet-physical-field-shock-front-condition-failure'
  )
####


class MocReflectedDomainCoupledEulerInletBoundaryMode(str, Enum):
  """Research inlet treatment for the coupled constant-gamma field."""

  FULL_STATE_RUSANOV = 'full-state-rusanov'
  SUBSONIC_CHARACTERISTIC = 'subsonic-characteristic'
  SCALAR_NORMAL_SHOCK_BRANCH = 'scalar-normal-shock-branch'
  AUDITED_SHOCK_INTERFACE = 'audited-shock-interface'
  AUDITED_SHOCK_INTERFACE_PROFILE = 'audited-shock-interface-profile'
  AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE = (
    'audited-interior-shock-interface-profile'
  )
  SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE = (
    'solver-owned-interior-shock-interface-profile'
  )
  SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE = (
    'solver-owned-physical-field-continuation-profile'
  )
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


class MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus(
  str,
  Enum,
):
  """Classify every solver-owned downstream pressure target."""

  ALL_TARGETS_WITHIN_ISENTROPIC_SUBSONIC_BOUNDS = (
    'all-targets-within-isentropic-subsonic-pressure-bounds'
  )
  SOME_TARGETS_BELOW_ISENTROPIC_SUBSONIC_BOUNDS = (
    'some-targets-below-isentropic-subsonic-pressure-bounds'
  )
  SOME_TARGETS_ABOVE_ISENTROPIC_SUBSONIC_BOUNDS = (
    'some-targets-above-isentropic-subsonic-pressure-bounds'
  )
  TARGETS_SPAN_BELOW_AND_ABOVE_ISENTROPIC_SUBSONIC_BOUNDS = (
    'targets-span-below-and-above-isentropic-subsonic-pressure-bounds'
  )
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerPressureProfileCompatibility:
  """Diagnostic reachability evidence for a solver-owned pressure profile.

  The profile targets are compared independently at every coupled cell
  column with the isentropic subsonic pressure range implied by the outer
  control-section total pressure.  This does not reject a two-dimensional
  field: shocks and mixing may add entropy, so the result identifies the
  missing physical budget instead of asserting that the profile is impossible.
  """

  status: MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
  target_count: int
  target_pressure_min_Pa: float
  target_pressure_max_Pa: float
  reference_total_pressure_Pa: float
  subsonic_static_pressure_lower_bound_Pa: float
  subsonic_static_pressure_upper_bound_Pa: float
  minimum_compatible_total_pressure_Pa: float
  minimum_total_pressure_compatibility_ratio: float
  minimum_additional_total_pressure_loss_fraction: float
  below_bound_count: int
  within_bound_count: int
  above_bound_count: int
  gamma: float
  source: str = 'derived-downstream-pressure-profile-isentropic-budget'

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus'
      )
    ####
    if (
      isinstance(self.target_count, bool)
      or not isinstance(self.target_count, int)
      or self.target_count <= 0
    ):
      raise ValueError('target_count must be a positive integer')
    ####
    for name in (
      'target_pressure_min_Pa',
      'target_pressure_max_Pa',
      'reference_total_pressure_Pa',
      'subsonic_static_pressure_lower_bound_Pa',
      'subsonic_static_pressure_upper_bound_Pa',
      'minimum_compatible_total_pressure_Pa',
      'minimum_total_pressure_compatibility_ratio',
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
    object.__setattr__(
      self,
      'minimum_additional_total_pressure_loss_fraction',
      loss_fraction,
    )
    if self.subsonic_static_pressure_lower_bound_Pa > (
      self.subsonic_static_pressure_upper_bound_Pa
    ):
      raise ValueError('subsonic pressure bounds must be ordered')
    ####
    if self.target_pressure_min_Pa > self.target_pressure_max_Pa:
      raise ValueError('target pressure extrema must be ordered')
    ####
    if self.gamma <= 1.0:
      raise ValueError('gamma must be greater than one')
    ####
    for name in ('below_bound_count', 'within_bound_count', 'above_bound_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if (
      self.below_bound_count
      + self.within_bound_count
      + self.above_bound_count
      != self.target_count
    ):
      raise ValueError(
        'pressure-profile compatibility counts must sum to target_count'
      )
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'source', source)
  ####

  @property
  def all_targets_within_isentropic_subsonic_bounds(self) -> bool:
    """Whether no profile target crosses the retained isentropic budget."""

    return self.status is (
      MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
      .ALL_TARGETS_WITHIN_ISENTROPIC_SUBSONIC_BOUNDS
    )
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'target_count': self.target_count,
      'target_pressure_min_Pa': self.target_pressure_min_Pa,
      'target_pressure_max_Pa': self.target_pressure_max_Pa,
      'reference_total_pressure_Pa': self.reference_total_pressure_Pa,
      'subsonic_static_pressure_lower_bound_Pa': (
        self.subsonic_static_pressure_lower_bound_Pa
      ),
      'subsonic_static_pressure_upper_bound_Pa': (
        self.subsonic_static_pressure_upper_bound_Pa
      ),
      'minimum_compatible_total_pressure_Pa': (
        self.minimum_compatible_total_pressure_Pa
      ),
      'minimum_total_pressure_compatibility_ratio': (
        self.minimum_total_pressure_compatibility_ratio
      ),
      'minimum_additional_total_pressure_loss_fraction': (
        self.minimum_additional_total_pressure_loss_fraction
      ),
      'below_bound_count': self.below_bound_count,
      'within_bound_count': self.within_bound_count,
      'above_bound_count': self.above_bound_count,
      'gamma': self.gamma,
      'all_targets_within_isentropic_subsonic_bounds': (
        self.all_targets_within_isentropic_subsonic_bounds
      ),
      'source': self.source,
      'claim_status': (
        'diagnostic-only-downstream-pressure-profile-isentropic-budget; '
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


class MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus(
  str,
  Enum,
):
  """Classify whether a scalar transition state exists on the retained frontier."""

  NOT_REQUIRED = 'transonic-frontier-check-not-required'
  MATCHED_FRONTIER_STATE = 'transonic-upstream-state-matched-frontier'
  REQUIRED_UPSTREAM_NOT_RETAINED = (
    'transonic-required-upstream-state-not-retained-on-frontier'
  )
  FRONTIER_DATA_FAILURE = 'transonic-frontier-data-failure'
####


@dataclass(frozen=True, slots=True)
class MocReflectedDomainCoupledEulerTransonicFrontierCompatibility:
  """Evidence for the scalar-to-global-frontier transition seam.

  The scalar pressure reference can identify an upstream Mach number that
  would reach the ambient target after a normal shock.  This record checks
  that requirement against the exact downstream states retained on the
  global Euler shock frontier.  It never interpolates a missing state, moves
  the transition, or treats a scalar match as a placed two-dimensional
  shock.
  """

  status: MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
  transition_required: bool
  required_upstream_mach: float | None = None
  required_upstream_static_pressure_Pa: float | None = None
  required_upstream_total_pressure_Pa: float | None = None
  frontier_sample_count: int = 0
  frontier_downstream_mach_min: float | None = None
  frontier_downstream_mach_max: float | None = None
  matching_sample_count: int = 0
  nearest_sample_index: int | None = None
  nearest_sample_point_m: tuple[float, float] | None = None
  nearest_mach_residual: float | None = None
  nearest_static_pressure_residual_fraction: float | None = None
  nearest_total_pressure_residual_fraction: float | None = None
  mach_tolerance: float = 1.0e-6
  pressure_tolerance_fraction: float = 1.0e-6
  source: str = 'global-euler-shock-frontier-transonic-compatibility-v1'

  def __post_init__(self) -> None:
    if not isinstance(
      self.status,
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus,
    ):
      raise TypeError(
        'status must be a '
        'MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus'
      )
    ####
    if not isinstance(self.transition_required, bool):
      raise TypeError('transition_required must be a bool')
    ####
    for name in (
      'required_upstream_mach',
      'required_upstream_static_pressure_Pa',
      'required_upstream_total_pressure_Pa',
      'frontier_downstream_mach_min',
      'frontier_downstream_mach_max',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in (
      'nearest_mach_residual',
      'nearest_static_pressure_residual_fraction',
      'nearest_total_pressure_residual_fraction',
    ):
      value = getattr(self, name)
      if value is None:
        continue
      ####
      numeric = float(value)
      if not isfinite(numeric) or numeric < 0.0:
        raise ValueError(f'{name} must be finite and nonnegative when supplied')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in ('mach_tolerance', 'pressure_tolerance_fraction'):
      numeric = float(getattr(self, name))
      if not isfinite(numeric) or numeric <= 0.0:
        raise ValueError(f'{name} must be finite and positive')
      ####
      object.__setattr__(self, name, numeric)
    ####
    for name in ('frontier_sample_count', 'matching_sample_count'):
      value = getattr(self, name)
      if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f'{name} must be a nonnegative integer')
      ####
    ####
    if self.matching_sample_count > self.frontier_sample_count:
      raise ValueError('matching_sample_count cannot exceed frontier_sample_count')
    ####
    if self.nearest_sample_index is not None:
      if (
        isinstance(self.nearest_sample_index, bool)
        or not isinstance(self.nearest_sample_index, int)
        or not 0 <= self.nearest_sample_index < self.frontier_sample_count
      ):
        raise ValueError('nearest_sample_index must identify a frontier sample')
      ####
    ####
    if self.nearest_sample_point_m is not None:
      point = tuple(float(value) for value in self.nearest_sample_point_m)
      if len(point) != 2 or any(not isfinite(value) for value in point):
        raise ValueError('nearest_sample_point_m must contain two finite values')
      ####
      object.__setattr__(self, 'nearest_sample_point_m', point)
    ####
    source = str(self.source)
    if not source:
      raise ValueError('source must be a non-empty string')
    ####
    object.__setattr__(self, 'source', source)
    if self.status is (
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .MATCHED_FRONTIER_STATE
    ) and self.matching_sample_count <= 0:
      raise ValueError('a matched frontier status requires a matching sample')
    ####
    if self.status is (
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .NOT_REQUIRED
    ) and self.transition_required:
      raise ValueError('a not-required frontier status cannot require a transition')
    ####
  ####

  @property
  def frontier_state_compatible(self) -> bool:
    """Whether an exact retained frontier state meets the scalar requirement."""

    return self.status is (
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .MATCHED_FRONTIER_STATE
    )
  ####

  @property
  def physical_closure_verified(self) -> bool:
    """A frontier state match is not a placed two-dimensional transition."""

    return False
  ####

  @property
  def chain_promotion_blocked(self) -> bool:
    return True
  ####

  @property
  def production_claim_allowed(self) -> bool:
    return False
  ####

  def as_report(self) -> dict[str, Any]:
    return {
      'status': self.status.value,
      'transition_required': self.transition_required,
      'frontier_state_compatible': self.frontier_state_compatible,
      'required_upstream_mach': self.required_upstream_mach,
      'required_upstream_static_pressure_Pa': (
        self.required_upstream_static_pressure_Pa
      ),
      'required_upstream_total_pressure_Pa': (
        self.required_upstream_total_pressure_Pa
      ),
      'frontier_sample_count': self.frontier_sample_count,
      'frontier_downstream_mach_min': self.frontier_downstream_mach_min,
      'frontier_downstream_mach_max': self.frontier_downstream_mach_max,
      'matching_sample_count': self.matching_sample_count,
      'nearest_sample_index': self.nearest_sample_index,
      'nearest_sample_point_m': self.nearest_sample_point_m,
      'nearest_mach_residual': self.nearest_mach_residual,
      'nearest_static_pressure_residual_fraction': (
        self.nearest_static_pressure_residual_fraction
      ),
      'nearest_total_pressure_residual_fraction': (
        self.nearest_total_pressure_residual_fraction
      ),
      'mach_tolerance': self.mach_tolerance,
      'pressure_tolerance_fraction': self.pressure_tolerance_fraction,
      'physical_closure_verified': self.physical_closure_verified,
      'chain_promotion_blocked': self.chain_promotion_blocked,
      'production_claim_allowed': self.production_claim_allowed,
      'source': self.source,
      'claim_status': (
        'research-only-scalar-to-global-frontier-compatibility; placed-2d-'
        'transonic-transition-and-mixed-regime-closure-remain-open'
      ),
    }
  ####
####


def assess_reflected_domain_coupled_euler_transonic_frontier_compatibility(
  request: 'MocReflectedDomainCoupledEulerFreeBoundaryRequest',
  transition: MocTransonicTransitionResult | None = None,
) -> MocReflectedDomainCoupledEulerTransonicFrontierCompatibility:
  """Check a scalar transition requirement against retained global states.

  The exact global shock curve carries downstream states that remain
  supersonic along its retained patch.  This diagnostic checks those states
  directly; it does not synthesize a higher-Mach state or choose a shock
  location when the required state is absent.
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
  status_type = MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
  closure = request.mixed_regime_request.closure
  global_euler = closure.global_euler
  curve = None if global_euler is None else global_euler.shock_boundary
  if curve is None:
    return MocReflectedDomainCoupledEulerTransonicFrontierCompatibility(
      status=status_type.FRONTIER_DATA_FAILURE,
      transition_required=transition.transition_required,
      required_upstream_mach=transition.required_upstream_mach,
      required_upstream_static_pressure_Pa=transition.upstream_static_pressure_Pa,
      required_upstream_total_pressure_Pa=transition.request.upstream_total_pressure_Pa,
      source='global-euler-shock-frontier-transonic-compatibility-v1',
    )
  ####
  points = tuple(curve.shock_points_m)
  states = tuple(curve.downstream_states)
  static_pressures = tuple(curve.downstream_static_pressure_Pa)
  total_pressures = tuple(curve.downstream_total_pressure_Pa)
  lengths = (len(points), len(states), len(static_pressures), len(total_pressures))
  if not lengths[0] or len(set(lengths)) != 1:
    return MocReflectedDomainCoupledEulerTransonicFrontierCompatibility(
      status=status_type.FRONTIER_DATA_FAILURE,
      transition_required=transition.transition_required,
      required_upstream_mach=transition.required_upstream_mach,
      required_upstream_static_pressure_Pa=transition.upstream_static_pressure_Pa,
      required_upstream_total_pressure_Pa=transition.request.upstream_total_pressure_Pa,
      frontier_sample_count=lengths[0],
      source='global-euler-shock-frontier-transonic-compatibility-v1',
    )
  ####
  frontier_machs = tuple(float(state.mach) for state in states)
  if not transition.transition_required:
    return MocReflectedDomainCoupledEulerTransonicFrontierCompatibility(
      status=status_type.NOT_REQUIRED,
      transition_required=False,
      frontier_sample_count=len(states),
      frontier_downstream_mach_min=min(frontier_machs),
      frontier_downstream_mach_max=max(frontier_machs),
      source='global-euler-shock-frontier-transonic-compatibility-v1',
    )
  ####
  required_mach = transition.required_upstream_mach
  required_static_pressure = transition.upstream_static_pressure_Pa
  required_total_pressure = transition.request.upstream_total_pressure_Pa
  if any(value is None for value in (required_mach, required_static_pressure)):
    return MocReflectedDomainCoupledEulerTransonicFrontierCompatibility(
      status=status_type.FRONTIER_DATA_FAILURE,
      transition_required=True,
      required_upstream_total_pressure_Pa=required_total_pressure,
      frontier_sample_count=len(states),
      frontier_downstream_mach_min=min(frontier_machs),
      frontier_downstream_mach_max=max(frontier_machs),
      source='global-euler-shock-frontier-transonic-compatibility-v1',
    )
  ####
  assert required_mach is not None
  assert required_static_pressure is not None
  assert required_total_pressure is not None
  candidates: list[tuple[float, int, float, float, float]] = []
  for index, (state, static_pressure, total_pressure) in enumerate(zip(
    states,
    static_pressures,
    total_pressures,
    strict=True,
  )):
    mach_residual = abs(float(state.mach) - required_mach)
    static_residual = abs(float(static_pressure) - required_static_pressure) / max(
      abs(required_static_pressure),
      abs(float(static_pressure)),
      1.0,
    )
    total_residual = abs(float(total_pressure) - required_total_pressure) / max(
      abs(required_total_pressure),
      abs(float(total_pressure)),
      1.0,
    )
    score = max(
      mach_residual / 1.0e-6,
      static_residual / 1.0e-6,
      total_residual / 1.0e-6,
    )
    candidates.append((score, index, mach_residual, static_residual, total_residual))
  ####
  _score, nearest_index, mach_residual, static_residual, total_residual = min(
    candidates,
    key=lambda candidate: candidate[0],
  )
  matching = tuple(
    candidate
    for candidate in candidates
    if candidate[2] <= 1.0e-6
    and candidate[3] <= 1.0e-6
    and candidate[4] <= 1.0e-6
  )
  status = (
    status_type.MATCHED_FRONTIER_STATE
    if matching
    else status_type.REQUIRED_UPSTREAM_NOT_RETAINED
  )
  return MocReflectedDomainCoupledEulerTransonicFrontierCompatibility(
    status=status,
    transition_required=True,
    required_upstream_mach=required_mach,
    required_upstream_static_pressure_Pa=required_static_pressure,
    required_upstream_total_pressure_Pa=required_total_pressure,
    frontier_sample_count=len(states),
    frontier_downstream_mach_min=min(frontier_machs),
    frontier_downstream_mach_max=max(frontier_machs),
    matching_sample_count=len(matching),
    nearest_sample_index=nearest_index,
    nearest_sample_point_m=tuple(float(value) for value in points[nearest_index]),
    nearest_mach_residual=mach_residual,
    nearest_static_pressure_residual_fraction=static_residual,
    nearest_total_pressure_residual_fraction=total_residual,
    source='global-euler-shock-frontier-transonic-compatibility-v1',
  )
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
  downstream_length_m: float | None = None
  source: str = COUPLED_EULER_FREE_BOUNDARY_MODEL
  outlet_static_pressure_Pa: float | None = None
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  )
  transonic_shock_geometry: MocTransonicShockGeometryRequest | None = None
  transonic_shock_interface: MocTransonicShockInterfaceResult | None = None
  transonic_shock_interface_profile: MocTransonicShockInterfaceProfile | None = None
  transonic_shock_interface_field_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None
  # Optional solver-owned pressure targets for the free-boundary cell columns.
  # These are a downstream handoff seam, not a promotion or validation claim.
  free_boundary_pressure_profile_Pa: tuple[float, ...] | None = None
  free_boundary_pressure_profile_x_stations_m: tuple[float, ...] | None = None
  free_boundary_pressure_profile_source: str | None = None
  # Optional solver-owned ordinate targets for the free-boundary nodes.  The
  # geometry profile is intentionally separate from pressure: pressure
  # feedback cannot silently repair a spatial boundary mismatch.
  free_boundary_geometry_profile_y_m: tuple[float, ...] | None = None
  free_boundary_geometry_profile_x_stations_m: tuple[float, ...] | None = None
  free_boundary_geometry_profile_source: str | None = None
  free_boundary_geometry_profile_lower_ordinate_m: float | None = None

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
    if self.downstream_length_m is not None:
      downstream_length = float(self.downstream_length_m)
      if not isfinite(downstream_length) or downstream_length <= 0.0:
        raise ValueError(
          'downstream_length_m must be finite and positive when supplied'
        )
      ####
      object.__setattr__(self, 'downstream_length_m', downstream_length)
    ####
    pressure_profile = self.free_boundary_pressure_profile_Pa
    pressure_profile_x = self.free_boundary_pressure_profile_x_stations_m
    pressure_profile_source = self.free_boundary_pressure_profile_source
    if pressure_profile is None:
      if pressure_profile_x is not None or pressure_profile_source is not None:
        raise ValueError(
          'free-boundary pressure-profile coordinates and source require a '
          'pressure profile'
        )
      ####
    else:
      if pressure_profile_x is None or pressure_profile_source is None:
        raise ValueError(
          'free-boundary pressure profile requires aligned coordinates and a '
          'non-empty source'
        )
      ####
      pressures = tuple(float(value) for value in pressure_profile)
      coordinates = tuple(float(value) for value in pressure_profile_x)
      if len(pressures) != self.axial_cell_count:
        raise ValueError(
          'free_boundary_pressure_profile_Pa must contain one value per '
          'axial cell column'
        )
      ####
      if len(coordinates) != len(pressures):
        raise ValueError(
          'free_boundary_pressure_profile_x_stations_m must align with the '
          'pressure profile'
        )
      ####
      if any(not isfinite(value) or value <= 0.0 for value in pressures):
        raise ValueError(
          'free_boundary_pressure_profile_Pa must contain finite positive values'
        )
      ####
      if any(not isfinite(value) for value in coordinates):
        raise ValueError(
          'free_boundary_pressure_profile_x_stations_m must contain finite values'
        )
      ####
      if any(
        second <= first for first, second in zip(coordinates, coordinates[1:])
      ):
        raise ValueError(
          'free_boundary_pressure_profile_x_stations_m must be strictly '
          'downstream ordered'
        )
      ####
      source = str(pressure_profile_source)
      if not source:
        raise ValueError('free_boundary_pressure_profile_source must be non-empty')
      ####
      object.__setattr__(self, 'free_boundary_pressure_profile_Pa', pressures)
      object.__setattr__(self, 'free_boundary_pressure_profile_x_stations_m', coordinates)
      object.__setattr__(self, 'free_boundary_pressure_profile_source', source)
    ####
    geometry_profile = self.free_boundary_geometry_profile_y_m
    geometry_profile_x = self.free_boundary_geometry_profile_x_stations_m
    geometry_profile_source = self.free_boundary_geometry_profile_source
    geometry_profile_lower = (
      self.free_boundary_geometry_profile_lower_ordinate_m
    )
    if geometry_profile is None:
      if (
        geometry_profile_x is not None
        or geometry_profile_source is not None
        or geometry_profile_lower is not None
      ):
        raise ValueError(
          'free-boundary geometry-profile coordinates, source, and lower '
          'ordinate require a geometry profile'
        )
      ####
    else:
      if geometry_profile_x is None or geometry_profile_source is None:
        raise ValueError(
          'free-boundary geometry profile requires aligned coordinates and a '
          'non-empty source'
        )
      ####
      ordinates = tuple(float(value) for value in geometry_profile)
      coordinates = tuple(float(value) for value in geometry_profile_x)
      if len(ordinates) != self.axial_cell_count + 1:
        raise ValueError(
          'free_boundary_geometry_profile_y_m must contain one value per '
          'free-boundary node'
        )
      ####
      if len(coordinates) != len(ordinates):
        raise ValueError(
          'free_boundary_geometry_profile_x_stations_m must align with the '
          'geometry profile'
        )
      ####
      if any(not isfinite(value) for value in (*ordinates, *coordinates)):
        raise ValueError(
          'free-boundary geometry profile values must be finite'
        )
      ####
      if any(
        second <= first for first, second in zip(coordinates, coordinates[1:])
      ):
        raise ValueError(
          'free_boundary_geometry_profile_x_stations_m must be strictly '
          'downstream ordered'
        )
      ####
      source = str(geometry_profile_source)
      if not source:
        raise ValueError(
          'free_boundary_geometry_profile_source must be non-empty'
        )
      ####
      lower_ordinate = (
        float(
          self.mixed_regime_request.control_section.points_m[0][1]
        )
        if geometry_profile_lower is None
        else float(geometry_profile_lower)
      )
      if not isfinite(lower_ordinate):
        raise ValueError(
          'free_boundary_geometry_profile_lower_ordinate_m must be finite'
        )
      ####
      object.__setattr__(self, 'free_boundary_geometry_profile_y_m', ordinates)
      object.__setattr__(
        self,
        'free_boundary_geometry_profile_x_stations_m',
        coordinates,
      )
      object.__setattr__(self, 'free_boundary_geometry_profile_source', source)
      object.__setattr__(
        self,
        'free_boundary_geometry_profile_lower_ordinate_m',
        lower_ordinate,
      )
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
    if self.transonic_shock_interface is not None and not isinstance(
      self.transonic_shock_interface,
      MocTransonicShockInterfaceResult,
    ):
      raise TypeError(
        'transonic_shock_interface must be a '
        'MocTransonicShockInterfaceResult or None'
      )
    ####
    if self.transonic_shock_interface_profile is not None and not isinstance(
      self.transonic_shock_interface_profile,
      MocTransonicShockInterfaceProfile,
    ):
      raise TypeError(
        'transonic_shock_interface_profile must be a '
        'MocTransonicShockInterfaceProfile or None'
      )
    ####
    if self.transonic_shock_interface_field_placement is not None and not isinstance(
      self.transonic_shock_interface_field_placement,
      MocTransonicShockInterfaceFieldPlacementResult,
    ):
      raise TypeError(
        'transonic_shock_interface_field_placement must be a '
        'MocTransonicShockInterfaceFieldPlacementResult or None'
      )
    ####
    if self.physical_field_continuation_profile is not None and not isinstance(
      self.physical_field_continuation_profile,
      MocPhysicalFieldContinuationProfileResult,
    ):
      raise TypeError(
        'physical_field_continuation_profile must be a '
        'MocPhysicalFieldContinuationProfileResult or None'
      )
    ####
    if self.physical_field_shock_front_condition is not None and not isinstance(
      self.physical_field_shock_front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'physical_field_shock_front_condition must be a '
        'MocPhysicalFieldShockFrontConditionResult or None'
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
    if (
      self.inlet_boundary_mode
      is MocReflectedDomainCoupledEulerInletBoundaryMode.AUDITED_SHOCK_INTERFACE
    ) != (self.transonic_shock_interface is not None):
      raise ValueError(
        'audited-shock-interface mode requires transonic_shock_interface, '
        'and other inlet modes must not supply it'
      )
    ####
    profile_mode = self.inlet_boundary_mode in (
      MocReflectedDomainCoupledEulerInletBoundaryMode.AUDITED_SHOCK_INTERFACE_PROFILE,
      MocReflectedDomainCoupledEulerInletBoundaryMode.AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE,
    )
    if profile_mode != (self.transonic_shock_interface_profile is not None):
      raise ValueError(
        'an audited shock-interface-profile mode requires '
        'transonic_shock_interface_profile, and other inlet modes must not '
      'supply it'
      )
    ####
    placement_mode = (
      self.inlet_boundary_mode
      is MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    )
    if placement_mode != (
      self.transonic_shock_interface_field_placement is not None
    ):
      raise ValueError(
        'solver-owned interior shock-interface mode requires '
        'transonic_shock_interface_field_placement, and other inlet modes '
      'must not supply it'
      )
    ####
    continuation_mode = (
      self.inlet_boundary_mode
      is MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
    )
    if continuation_mode != (
      self.physical_field_continuation_profile is not None
    ):
      raise ValueError(
        'solver-owned physical-field continuation mode requires '
        'physical_field_continuation_profile, and other inlet modes must not '
        'supply it'
      )
    ####
    if continuation_mode != (
      self.physical_field_shock_front_condition is not None
    ):
      raise ValueError(
        'solver-owned physical-field continuation mode requires an explicit '
        'physical-field shock-front condition, and other inlet modes must not '
        'supply it'
      )
    ####
    if (
      self.physical_field_shock_front_condition is not None
      and self.physical_field_continuation_profile is not None
      and self.physical_field_shock_front_condition.continuation_profile
      != self.physical_field_continuation_profile
    ):
      raise ValueError(
        'physical-field shock-front condition must retain the exact '
        'physical-field continuation profile supplied to the request'
      )
    ####
    if (
      continuation_mode
      and self.physical_field_shock_front_condition is not None
      and self.physical_field_shock_front_condition.coupled_inlet_profile is None
    ):
      raise ValueError(
        'solver-owned physical-field continuation mode requires the retained '
        'shock-front condition to carry a complete coupled inlet profile'
      )
    ####
    if (
      self.transonic_shock_interface is not None
      and self.transonic_shock_interface_profile is not None
    ):
      raise ValueError(
        'scalar shock-interface and shock-interface profile handoffs are '
        'mutually exclusive'
      )
    ####
    if (
      self.transonic_shock_interface_profile is not None
      and self.transonic_shock_interface_field_placement is not None
    ):
      raise ValueError(
        'explicit shock-interface profile and solver-owned placement handoff '
      'are mutually exclusive'
      )
    ####
    if (
      self.physical_field_continuation_profile is not None
      and (
        self.transonic_shock_interface is not None
        or self.transonic_shock_interface_profile is not None
        or self.transonic_shock_interface_field_placement is not None
      )
    ):
      raise ValueError(
        'physical-field continuation and shock-interface handoffs are '
        'mutually exclusive'
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
      'downstream_length_m': self.downstream_length_m,
      'effective_downstream_length_m': self.effective_downstream_length_m,
      'outlet_static_pressure_Pa': self.outlet_static_pressure_Pa,
      'free_boundary_pressure_profile_Pa': self.free_boundary_pressure_profile_Pa,
      'free_boundary_pressure_profile_x_stations_m': (
        self.free_boundary_pressure_profile_x_stations_m
      ),
      'free_boundary_pressure_profile_source': (
        self.free_boundary_pressure_profile_source
      ),
      'free_boundary_geometry_profile_y_m': (
        self.free_boundary_geometry_profile_y_m
      ),
      'free_boundary_geometry_profile_x_stations_m': (
        self.free_boundary_geometry_profile_x_stations_m
      ),
      'free_boundary_geometry_profile_source': (
        self.free_boundary_geometry_profile_source
      ),
      'free_boundary_geometry_profile_lower_ordinate_m': (
        self.free_boundary_geometry_profile_lower_ordinate_m
      ),
      'inlet_boundary_mode': self.inlet_boundary_mode.value,
      'transonic_shock_geometry': (
        None
        if self.transonic_shock_geometry is None
        else self.transonic_shock_geometry.as_report()
      ),
      'transonic_shock_interface': (
        None
        if self.transonic_shock_interface is None
        else self.transonic_shock_interface.as_report()
      ),
      'transonic_shock_interface_profile': (
        None
        if self.transonic_shock_interface_profile is None
        else self.transonic_shock_interface_profile.as_report()
      ),
      'transonic_shock_interface_field_placement': (
        None
        if self.transonic_shock_interface_field_placement is None
        else self.transonic_shock_interface_field_placement.as_report()
      ),
      'physical_field_continuation_profile': (
        None
        if self.physical_field_continuation_profile is None
        else self.physical_field_continuation_profile.as_report()
      ),
      'physical_field_shock_front_condition': (
        None
        if self.physical_field_shock_front_condition is None
        else self.physical_field_shock_front_condition.as_report()
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

  @property
  def effective_downstream_length_m(self) -> float:
    """Return the explicit study window or the bound reference window."""

    return float(
      self.mixed_regime_request.downstream_length_m
      if self.downstream_length_m is None
      else self.downstream_length_m
    )
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
  downstream_length_m: float | None = None,
  source: str = COUPLED_EULER_FREE_BOUNDARY_MODEL,
  outlet_static_pressure_Pa: float | None = None,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  transonic_shock_geometry: MocTransonicShockGeometryRequest | None = None,
  transonic_shock_interface: MocTransonicShockInterfaceResult | None = None,
  transonic_shock_interface_profile: MocTransonicShockInterfaceProfile | None = None,
  transonic_shock_interface_field_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None,
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None,
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None,
  free_boundary_pressure_profile_Pa: tuple[float, ...] | None = None,
  free_boundary_pressure_profile_x_stations_m: tuple[float, ...] | None = None,
  free_boundary_pressure_profile_source: str | None = None,
  free_boundary_geometry_profile_y_m: tuple[float, ...] | None = None,
  free_boundary_geometry_profile_x_stations_m: tuple[float, ...] | None = None,
  free_boundary_geometry_profile_source: str | None = None,
  free_boundary_geometry_profile_lower_ordinate_m: float | None = None,
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
    downstream_length_m=downstream_length_m,
    source=source,
    outlet_static_pressure_Pa=outlet_static_pressure_Pa,
    inlet_boundary_mode=inlet_boundary_mode,
    transonic_shock_geometry=transonic_shock_geometry,
    transonic_shock_interface=transonic_shock_interface,
    transonic_shock_interface_profile=transonic_shock_interface_profile,
    transonic_shock_interface_field_placement=(
      transonic_shock_interface_field_placement
    ),
    physical_field_continuation_profile=physical_field_continuation_profile,
    physical_field_shock_front_condition=physical_field_shock_front_condition,
    free_boundary_pressure_profile_Pa=free_boundary_pressure_profile_Pa,
    free_boundary_pressure_profile_x_stations_m=(
      free_boundary_pressure_profile_x_stations_m
    ),
    free_boundary_pressure_profile_source=free_boundary_pressure_profile_source,
    free_boundary_geometry_profile_y_m=free_boundary_geometry_profile_y_m,
    free_boundary_geometry_profile_x_stations_m=(
      free_boundary_geometry_profile_x_stations_m
    ),
    free_boundary_geometry_profile_source=free_boundary_geometry_profile_source,
    free_boundary_geometry_profile_lower_ordinate_m=(
      free_boundary_geometry_profile_lower_ordinate_m
    ),
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
  free_boundary_adjacent_static_pressure_Pa: tuple[float, ...] = ()
  cell_centers_m: tuple[tuple[float, float], ...] = ()
  conservative_states_by_cell: tuple[tuple[float, float, float, float], ...] = ()
  inlet_boundary_conservative_states_by_face: tuple[
    tuple[float, float, float, float], ...
  ] = ()
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
  free_boundary_pressure_profile_consumed: bool = False
  free_boundary_geometry_profile_consumed: bool = False
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
  free_boundary_pressure_profile_compatibility: (
    MocReflectedDomainCoupledEulerPressureProfileCompatibility | None
  ) = None
  transonic_transition: MocTransonicTransitionResult | None = None
  transonic_transition_audit: MocTransonicTransitionAudit | None = None
  transonic_shock_geometry: MocTransonicShockGeometryResult | None = None
  transonic_shock_geometry_audit: MocTransonicShockGeometryAudit | None = None
  transonic_shock_interface: MocTransonicShockInterfaceResult | None = None
  transonic_shock_interface_consumed: bool = False
  transonic_shock_interface_profile: MocTransonicShockInterfaceProfile | None = None
  transonic_shock_interface_profile_consumed: bool = False
  transonic_shock_interface_field_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None
  transonic_shock_interface_field_placement_consumed: bool = False
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None
  physical_field_continuation_profile_consumed: bool = False
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None
  physical_field_shock_front_condition_consumed: bool = False
  inlet_boundary_states_consumed: bool = False
  transonic_frontier_compatibility: (
    MocReflectedDomainCoupledEulerTransonicFrontierCompatibility | None
  ) = None
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
    boundary_pressures = tuple(
      float(value)
      for value in self.free_boundary_adjacent_static_pressure_Pa
    )
    if any(not isfinite(value) or value <= 0.0 for value in boundary_pressures):
      raise ValueError(
        'free_boundary_adjacent_static_pressure_Pa must contain finite positive values'
      )
    ####
    if boundary_pressures and len(boundary_pressures) != max(
      len(self.free_boundary_points_m) - 1,
      0,
    ):
      raise ValueError(
        'free_boundary_adjacent_static_pressure_Pa must match the free-boundary '
        'cell columns'
      )
    ####
    object.__setattr__(
      self,
      'free_boundary_adjacent_static_pressure_Pa',
      boundary_pressures,
    )
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
    inlet_states = tuple(
      tuple(float(value) for value in state)
      for state in self.inlet_boundary_conservative_states_by_face
    )
    if any(len(state) != 4 for state in inlet_states):
      raise ValueError(
        'inlet_boundary_conservative_states_by_face must contain four values'
      )
    ####
    if any(not all(isfinite(value) for value in state) for state in inlet_states):
      raise ValueError(
        'inlet_boundary_conservative_states_by_face must be finite'
      )
    ####
    if self.request is not None and self.inlet_boundary_states_consumed and (
      len(inlet_states) != self.request.transverse_cell_count
    ):
      raise ValueError(
        'consumed inlet boundary states must match the transverse cell count'
      )
    ####
    object.__setattr__(
      self,
      'inlet_boundary_conservative_states_by_face',
      inlet_states,
    )
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
    if (
      self.free_boundary_pressure_profile_compatibility is not None
      and not isinstance(
        self.free_boundary_pressure_profile_compatibility,
        MocReflectedDomainCoupledEulerPressureProfileCompatibility,
      )
    ):
      raise TypeError(
        'free_boundary_pressure_profile_compatibility must be a '
        'MocReflectedDomainCoupledEulerPressureProfileCompatibility or None'
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
    if self.transonic_shock_interface is not None and not isinstance(
      self.transonic_shock_interface,
      MocTransonicShockInterfaceResult,
    ):
      raise TypeError(
        'transonic_shock_interface must be a '
        'MocTransonicShockInterfaceResult or None'
      )
    ####
    if self.transonic_shock_interface_profile is not None and not isinstance(
      self.transonic_shock_interface_profile,
      MocTransonicShockInterfaceProfile,
    ):
      raise TypeError(
        'transonic_shock_interface_profile must be a '
        'MocTransonicShockInterfaceProfile or None'
      )
    ####
    if self.transonic_shock_interface_field_placement is not None and not isinstance(
      self.transonic_shock_interface_field_placement,
      MocTransonicShockInterfaceFieldPlacementResult,
    ):
      raise TypeError(
        'transonic_shock_interface_field_placement must be a '
        'MocTransonicShockInterfaceFieldPlacementResult or None'
      )
    ####
    if self.physical_field_continuation_profile is not None and not isinstance(
      self.physical_field_continuation_profile,
      MocPhysicalFieldContinuationProfileResult,
    ):
      raise TypeError(
        'physical_field_continuation_profile must be a '
        'MocPhysicalFieldContinuationProfileResult or None'
      )
    ####
    if self.physical_field_shock_front_condition is not None and not isinstance(
      self.physical_field_shock_front_condition,
      MocPhysicalFieldShockFrontConditionResult,
    ):
      raise TypeError(
        'physical_field_shock_front_condition must be a '
        'MocPhysicalFieldShockFrontConditionResult or None'
      )
    ####
    if self.transonic_frontier_compatibility is not None and not isinstance(
      self.transonic_frontier_compatibility,
      MocReflectedDomainCoupledEulerTransonicFrontierCompatibility,
    ):
      raise TypeError(
        'transonic_frontier_compatibility must be a '
        'MocReflectedDomainCoupledEulerTransonicFrontierCompatibility or None'
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
    if self.request is not None and (
      self.request.transonic_shock_interface is None
    ) != (
      self.transonic_shock_interface is None
    ):
      raise ValueError(
        'retained transonic shock interface must match the request mode'
      )
    ####
    expected_profile_present = bool(
      self.request is not None
      and (
        self.request.transonic_shock_interface_profile is not None
        or (
          self.request.transonic_shock_interface_field_placement is not None
          and self.request.transonic_shock_interface_field_placement.profile
          is not None
        )
      )
    )
    if expected_profile_present != (
      self.transonic_shock_interface_profile is not None
    ):
      raise ValueError(
        'retained transonic shock-interface profile must match the request mode'
      )
    ####
    if self.request is not None and (
      self.request.transonic_shock_interface_field_placement is None
    ) != (
      self.transonic_shock_interface_field_placement is None
    ):
      raise ValueError(
      'retained solver-owned field placement must match the request mode'
      )
    ####
    if self.request is not None and (
      self.request.physical_field_continuation_profile is None
    ) != (
      self.physical_field_continuation_profile is None
    ):
      raise ValueError(
        'retained physical-field continuation profile must match the request mode'
      )
    ####
    if self.request is not None and (
      self.request.physical_field_shock_front_condition is None
    ) != (
      self.physical_field_shock_front_condition is None
    ):
      raise ValueError(
        'retained physical-field shock-front condition must match the request mode'
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
    if not isinstance(self.transonic_shock_interface_consumed, bool):
      raise TypeError('transonic_shock_interface_consumed must be a bool')
    ####
    if not isinstance(self.transonic_shock_interface_profile_consumed, bool):
      raise TypeError(
        'transonic_shock_interface_profile_consumed must be a bool'
      )
    ####
    if not isinstance(
      self.transonic_shock_interface_field_placement_consumed,
      bool,
    ):
      raise TypeError(
        'transonic_shock_interface_field_placement_consumed must be a bool'
      )
    ####
    if not isinstance(
      self.physical_field_continuation_profile_consumed,
      bool,
    ):
      raise TypeError(
        'physical_field_continuation_profile_consumed must be a bool'
      )
    ####
    if not isinstance(
      self.physical_field_shock_front_condition_consumed,
      bool,
    ):
      raise TypeError(
        'physical_field_shock_front_condition_consumed must be a bool'
      )
    ####
    if not isinstance(self.inlet_boundary_states_consumed, bool):
      raise TypeError('inlet_boundary_states_consumed must be a bool')
    ####
    if not isinstance(self.free_boundary_pressure_profile_consumed, bool):
      raise TypeError('free_boundary_pressure_profile_consumed must be a bool')
    ####
    if not isinstance(self.free_boundary_geometry_profile_consumed, bool):
      raise TypeError(
        'free_boundary_geometry_profile_consumed must be a bool'
      )
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
        'free_boundary_pressure_profile_compatibility': (
          None
          if self.free_boundary_pressure_profile_compatibility is None
          else self.free_boundary_pressure_profile_compatibility.as_report()
        ),
        'transonic_shock_interface_consumed': (
          self.transonic_shock_interface_consumed
        ),
        'transonic_shock_interface_profile_consumed': (
          self.transonic_shock_interface_profile_consumed
        ),
        'transonic_shock_interface_field_placement_consumed': (
          self.transonic_shock_interface_field_placement_consumed
        ),
        'physical_field_continuation_profile_consumed': (
          self.physical_field_continuation_profile_consumed
        ),
        'physical_field_shock_front_condition_consumed': (
          self.physical_field_shock_front_condition_consumed
        ),
        'free_boundary_pressure_profile_consumed': (
          self.free_boundary_pressure_profile_consumed
        ),
        'free_boundary_geometry_profile_consumed': (
          self.free_boundary_geometry_profile_consumed
        ),
        'inlet_boundary_states_consumed': self.inlet_boundary_states_consumed,
        'inlet_boundary_conservative_states_by_face': (
          self.inlet_boundary_conservative_states_by_face
        ),
        'physical_field_shock_front_condition': (
          None
          if self.physical_field_shock_front_condition is None
          else self.physical_field_shock_front_condition.as_report()
        ),
        'physical_field_continuation_profile': (
          None
          if self.physical_field_continuation_profile is None
          else self.physical_field_continuation_profile.as_report()
        ),
        'transonic_shock_interface_field_placement': (
          None
          if self.transonic_shock_interface_field_placement is None
          else self.transonic_shock_interface_field_placement.as_report()
        ),
        'transonic_frontier_compatibility': (
          None
          if self.transonic_frontier_compatibility is None
          else self.transonic_frontier_compatibility.as_report()
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
      'free_boundary_adjacent_static_pressure_Pa': (
        self.free_boundary_adjacent_static_pressure_Pa
      ),
      'cell_centers_m': self.cell_centers_m,
      'conservative_states_by_cell': self.conservative_states_by_cell,
      'inlet_boundary_conservative_states_by_face': (
        self.inlet_boundary_conservative_states_by_face
      ),
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
      'free_boundary_pressure_profile_consumed': (
        self.free_boundary_pressure_profile_consumed
      ),
      'free_boundary_geometry_profile_consumed': (
        self.free_boundary_geometry_profile_consumed
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
      'free_boundary_pressure_profile_compatibility': (
        None
        if self.free_boundary_pressure_profile_compatibility is None
        else self.free_boundary_pressure_profile_compatibility.as_report()
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
      'transonic_shock_interface': (
        None
        if self.transonic_shock_interface is None
        else self.transonic_shock_interface.as_report()
      ),
      'transonic_shock_interface_consumed': (
        self.transonic_shock_interface_consumed
      ),
      'transonic_shock_interface_profile': (
        None
        if self.transonic_shock_interface_profile is None
        else self.transonic_shock_interface_profile.as_report()
      ),
      'transonic_shock_interface_profile_consumed': (
        self.transonic_shock_interface_profile_consumed
      ),
      'transonic_shock_interface_field_placement': (
        None
        if self.transonic_shock_interface_field_placement is None
        else self.transonic_shock_interface_field_placement.as_report()
      ),
      'transonic_shock_interface_field_placement_consumed': (
        self.transonic_shock_interface_field_placement_consumed
      ),
      'physical_field_continuation_profile': (
        None
        if self.physical_field_continuation_profile is None
        else self.physical_field_continuation_profile.as_report()
      ),
      'physical_field_continuation_profile_consumed': (
        self.physical_field_continuation_profile_consumed
      ),
      'physical_field_shock_front_condition_consumed': (
        self.physical_field_shock_front_condition_consumed
      ),
      'inlet_boundary_states_consumed': self.inlet_boundary_states_consumed,
      'physical_field_shock_front_condition': (
        None
        if self.physical_field_shock_front_condition is None
        else self.physical_field_shock_front_condition.as_report()
      ),
      'transonic_frontier_compatibility': (
        None
        if self.transonic_frontier_compatibility is None
        else self.transonic_frontier_compatibility.as_report()
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


def assess_reflected_domain_coupled_euler_pressure_profile_compatibility(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> MocReflectedDomainCoupledEulerPressureProfileCompatibility | None:
  """Derive the per-column budget for an optional pressure profile.

  The pressure profile is a solver-owned downstream handoff.  This diagnostic
  makes its target range explicit without changing the field solve or treating
  the one-dimensional budget as a two-dimensional closure proof.
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
  profile = request.free_boundary_pressure_profile_Pa
  if profile is None:
    return None
  ####
  targets = tuple(float(value) for value in profile)
  if len(targets) != request.axial_cell_count:
    raise ValueError(
      'free-boundary pressure profile must contain one target per axial cell'
    )
  ####
  if any(not isfinite(value) or value <= 0.0 for value in targets):
    raise ValueError('free-boundary pressure profile targets must be positive')
  ####
  sample = request.mixed_regime_request.control_section.samples[-1]
  gamma = float(sample.gamma)
  reference_total_pressure = float(sample.total_pressure_Pa)
  if not isfinite(gamma) or gamma <= 1.0:
    raise ValueError('control-section gamma must be finite and greater than one')
  ####
  if not isfinite(reference_total_pressure) or reference_total_pressure <= 0.0:
    raise ValueError(
      'outer control-section total pressure must be finite and positive'
    )
  ####
  sonic_pressure_factor = (1.0 + 0.5 * (gamma - 1.0)) ** (
    gamma / (gamma - 1.0)
  )
  lower_bound = reference_total_pressure / sonic_pressure_factor
  upper_bound = reference_total_pressure
  pressure_scale = max(*targets, lower_bound, upper_bound, 1.0)
  tolerance = 1.0e-10 * pressure_scale
  below_bound_count = sum(value < lower_bound - tolerance for value in targets)
  above_bound_count = sum(value > upper_bound + tolerance for value in targets)
  within_bound_count = len(targets) - below_bound_count - above_bound_count
  if below_bound_count and above_bound_count:
    status = (
      MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
      .TARGETS_SPAN_BELOW_AND_ABOVE_ISENTROPIC_SUBSONIC_BOUNDS
    )
  elif below_bound_count:
    status = (
      MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
      .SOME_TARGETS_BELOW_ISENTROPIC_SUBSONIC_BOUNDS
    )
  elif above_bound_count:
    status = (
      MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
      .SOME_TARGETS_ABOVE_ISENTROPIC_SUBSONIC_BOUNDS
    )
  else:
    status = (
      MocReflectedDomainCoupledEulerPressureProfileCompatibilityStatus
      .ALL_TARGETS_WITHIN_ISENTROPIC_SUBSONIC_BOUNDS
    )
  ####
  minimum_compatible_total_pressure = min(targets) * sonic_pressure_factor
  compatibility_ratio = minimum_compatible_total_pressure / reference_total_pressure
  return MocReflectedDomainCoupledEulerPressureProfileCompatibility(
    status=status,
    target_count=len(targets),
    target_pressure_min_Pa=min(targets),
    target_pressure_max_Pa=max(targets),
    reference_total_pressure_Pa=reference_total_pressure,
    subsonic_static_pressure_lower_bound_Pa=lower_bound,
    subsonic_static_pressure_upper_bound_Pa=upper_bound,
    minimum_compatible_total_pressure_Pa=minimum_compatible_total_pressure,
    minimum_total_pressure_compatibility_ratio=compatibility_ratio,
    minimum_additional_total_pressure_loss_fraction=max(
      0.0,
      1.0 - compatibility_ratio,
    ),
    below_bound_count=below_bound_count,
    within_bound_count=within_bound_count,
    above_bound_count=above_bound_count,
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
  *,
  subsonic_pressure_budget: (
    MocReflectedDomainCoupledEulerSubsonicPressureBudget | None
  ) = None,
  transonic_transition: MocTransonicTransitionResult | None = None,
  transonic_transition_audit: MocTransonicTransitionAudit | None = None,
  transonic_frontier_compatibility: (
    MocReflectedDomainCoupledEulerTransonicFrontierCompatibility | None
  ) = None,
  control_section_compatibility: (
    MocReflectedDomainCoupledEulerControlSectionCompatibility | None
  ) = None,
) -> MocReflectedDomainCoupledEulerFreeBoundaryResult:
  transonic_shock_geometry = None
  transonic_shock_geometry_audit = None
  transonic_shock_interface = None
  transonic_shock_interface_profile = None
  transonic_shock_interface_field_placement = None
  physical_field_continuation_profile = None
  physical_field_shock_front_condition = None
  if request is not None and request.transonic_shock_geometry is not None:
    transonic_shock_geometry = solve_moc_transonic_shock_geometry(
      request.transonic_shock_geometry
    )
    transonic_shock_geometry_audit = measure_moc_transonic_shock_geometry(
      transonic_shock_geometry
    )
  ####
  if request is not None and request.transonic_shock_interface is not None:
    transonic_shock_interface = request.transonic_shock_interface
  ####
  if request is not None and request.transonic_shock_interface_profile is not None:
    transonic_shock_interface_profile = request.transonic_shock_interface_profile
  ####
  if request is not None and request.transonic_shock_interface_field_placement is not None:
    transonic_shock_interface_field_placement = (
      request.transonic_shock_interface_field_placement
    )
    transonic_shock_interface_profile = (
      transonic_shock_interface_field_placement.profile
    )
  ####
  if request is not None and request.physical_field_continuation_profile is not None:
    physical_field_continuation_profile = (
      request.physical_field_continuation_profile
    )
  ####
  if request is not None and request.physical_field_shock_front_condition is not None:
    physical_field_shock_front_condition = (
      request.physical_field_shock_front_condition
    )
  ####
  return MocReflectedDomainCoupledEulerFreeBoundaryResult(
    status=status,
    request=request,
    message=message,
    subsonic_pressure_budget=subsonic_pressure_budget,
    free_boundary_pressure_profile_compatibility=(
      None
      if request is None
      else assess_reflected_domain_coupled_euler_pressure_profile_compatibility(
        request
      )
    ),
    transonic_transition=transonic_transition,
    transonic_transition_audit=transonic_transition_audit,
    transonic_frontier_compatibility=transonic_frontier_compatibility,
    control_section_compatibility=control_section_compatibility,
    transonic_shock_geometry=transonic_shock_geometry,
    transonic_shock_geometry_audit=transonic_shock_geometry_audit,
    transonic_shock_interface=transonic_shock_interface,
    transonic_shock_interface_profile=transonic_shock_interface_profile,
    transonic_shock_interface_field_placement=(
      transonic_shock_interface_field_placement
    ),
    physical_field_continuation_profile=physical_field_continuation_profile,
    physical_field_shock_front_condition=physical_field_shock_front_condition,
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
  downstream_length_m: float | None = None,
  source: str = COUPLED_EULER_FREE_BOUNDARY_MODEL,
  outlet_static_pressure_Pa: float | None = None,
  inlet_boundary_mode: MocReflectedDomainCoupledEulerInletBoundaryMode = (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV
  ),
  transonic_shock_geometry: MocTransonicShockGeometryRequest | None = None,
  transonic_shock_interface: MocTransonicShockInterfaceResult | None = None,
  transonic_shock_interface_profile: MocTransonicShockInterfaceProfile | None = None,
  transonic_shock_interface_field_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None,
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None,
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None,
  free_boundary_pressure_profile_Pa: tuple[float, ...] | None = None,
  free_boundary_pressure_profile_x_stations_m: tuple[float, ...] | None = None,
  free_boundary_pressure_profile_source: str | None = None,
  free_boundary_geometry_profile_y_m: tuple[float, ...] | None = None,
  free_boundary_geometry_profile_x_stations_m: tuple[float, ...] | None = None,
  free_boundary_geometry_profile_source: str | None = None,
  free_boundary_geometry_profile_lower_ordinate_m: float | None = None,
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
      downstream_length_m=downstream_length_m,
      source=source,
      outlet_static_pressure_Pa=outlet_static_pressure_Pa,
      inlet_boundary_mode=inlet_boundary_mode,
      transonic_shock_geometry=transonic_shock_geometry,
      transonic_shock_interface=transonic_shock_interface,
      transonic_shock_interface_profile=transonic_shock_interface_profile,
      transonic_shock_interface_field_placement=(
        transonic_shock_interface_field_placement
      ),
      physical_field_continuation_profile=physical_field_continuation_profile,
      physical_field_shock_front_condition=physical_field_shock_front_condition,
      free_boundary_pressure_profile_Pa=free_boundary_pressure_profile_Pa,
      free_boundary_pressure_profile_x_stations_m=(
        free_boundary_pressure_profile_x_stations_m
      ),
      free_boundary_pressure_profile_source=free_boundary_pressure_profile_source,
      free_boundary_geometry_profile_y_m=free_boundary_geometry_profile_y_m,
      free_boundary_geometry_profile_x_stations_m=(
        free_boundary_geometry_profile_x_stations_m
      ),
      free_boundary_geometry_profile_source=free_boundary_geometry_profile_source,
      free_boundary_geometry_profile_lower_ordinate_m=(
        free_boundary_geometry_profile_lower_ordinate_m
      ),
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


def _free_boundary_pressure_targets(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> np.ndarray:
  """Return one positive pressure target for each free-boundary column."""

  if request.free_boundary_pressure_profile_Pa is None:
    return np.full(
      request.axial_cell_count,
      request.mixed_regime_request.ambient_pressure_Pa,
      dtype=float,
    )
  ####
  return np.asarray(request.free_boundary_pressure_profile_Pa, dtype=float)
####


def _free_boundary_geometry_targets(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
) -> np.ndarray | None:
  """Return absolute ordinate targets for the retained boundary nodes."""

  if request.free_boundary_geometry_profile_y_m is None:
    return None
  ####
  return np.asarray(request.free_boundary_geometry_profile_y_m, dtype=float)
####


def _cell_residuals(
  states: np.ndarray,
  points: np.ndarray,
  corners: np.ndarray,
  areas: np.ndarray,
  control_points: tuple[tuple[float, float], ...],
  control_samples: tuple[Any, ...],
  ambient_pressure: float,
  free_boundary_pressure_profile: tuple[float, ...] | None,
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
          boundary_pressure = (
            ambient_pressure
            if free_boundary_pressure_profile is None
            else free_boundary_pressure_profile[i]
          )
          flux, wave = _specified_pressure_wall_flux(
            state,
            boundary_pressure,
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


def _consumed_inlet_boundary_states(
  states: np.ndarray,
  free_boundary_heights: np.ndarray,
  lower_ordinate: float,
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  gamma: float,
  gas_constant: float,
  inlet_override_states: tuple[np.ndarray, ...] | None,
) -> tuple[np.ndarray, ...]:
  """Reconstruct the exact conservative states used on the inlet faces."""

  if inlet_override_states is not None:
    return inlet_override_states
  ####
  control_points = request.mixed_regime_request.control_section.points_m
  control_samples = request.mixed_regime_request.control_section.samples
  inlet_height = float(free_boundary_heights[0])
  face_width = inlet_height / request.transverse_cell_count
  inlet_states: list[np.ndarray] = []
  for index in range(request.transverse_cell_count):
    ordinate = lower_ordinate + (index + 0.5) * face_width
    inlet = _interpolate_inlet_state(
      ordinate,
      control_points,
      control_samples,
      gamma,
      request.reference_total_temperature_K,
      gas_constant,
    )
    if (
      request.inlet_boundary_mode
      is MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC
    ):
      inlet = _subsonic_characteristic_inlet_state(
        states[0, index],
        inlet,
        gamma,
        gas_constant,
      )
    ####
    inlet_states.append(inlet)
  ####
  return tuple(inlet_states)
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


def _prepare_transonic_interface_inlet(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  *,
  x_start: float,
  lower_ordinate: float,
  inlet_height: float,
) -> tuple[tuple[np.ndarray, ...], MocTransonicShockInterfaceResult]:
  """Consume one audited interface as an explicit coupled-field inlet.

  The current field mesh can only accept a cross-section inlet handoff.  An
  interface placed in the interior of the plume therefore fails explicitly;
  it is not projected onto the inlet and it does not fall back to the scalar
  geometry branch.  Internal placement remains a separate P2.2b solver seam.
  """

  interface = request.transonic_shock_interface
  if interface is None:
    raise RuntimeError(
      'audited-shock-interface mode requires a retained interface result'
    )
  ####
  if (
    interface.status
    is not MocTransonicShockInterfaceStatus.CONVERGED_BOUNDED_INTERFACE
    or not interface.interface_verified
  ):
    raise RuntimeError(
      'audited shock-interface inlet requires an independently verified '
      'transonic interface handoff'
    )
  ####
  from exhaust_plume.validation.moc_transonic_interface import (
    measure_moc_transonic_shock_interface,
  )

  interface_audit = measure_moc_transonic_shock_interface(interface)
  if not interface_audit.converged:
    raise RuntimeError(
      'audited shock-interface inlet failed its independent handoff audit'
    )
  ####
  sample = interface.downstream_sample
  geometry = interface.shock_geometry
  if sample is None or geometry is None:
    raise RuntimeError(
      'audited shock-interface inlet retained no downstream sample or geometry'
    )
  ####
  shock_state = geometry.request.shock_state
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(sample.point_m[0] - x_start) > x_tolerance:
    raise RuntimeError(
      'audited shock-interface handoff is interior to the field; only an '
      'inlet-bound interface is accepted by this coupled-field tranche'
    )
  ####
  if not (
    lower_ordinate - y_tolerance
    <= sample.point_m[1]
    <= lower_ordinate + inlet_height + y_tolerance
  ):
    raise RuntimeError(
      'audited shock-interface handoff point must lie on the coupled-field '
      'inlet section'
    )
  ####
  reference_sample = request.mixed_regime_request.control_section.samples[-1]
  if abs(sample.gamma - float(reference_sample.gamma)) > 1.0e-10:
    raise RuntimeError(
      'audited shock-interface downstream gamma does not match the inlet'
    )
  ####
  if abs(shock_state.gas_constant_J_kgK - request.gas_constant_J_kgK) > 1.0e-10:
    raise RuntimeError(
      'audited shock-interface gas constant does not match the coupled inlet'
    )
  ####
  if abs(
    shock_state.upstream_total_temperature_K
    - request.reference_total_temperature_K
  ) > 1.0e-8 * max(request.reference_total_temperature_K, 1.0):
    raise RuntimeError(
      'audited shock-interface total temperature does not match the coupled '
      'inlet'
    )
  ####
  downstream_state = _state_from_sample(
    sample.total_pressure_Pa,
    sample.mach,
    sample.flow_angle_rad,
    sample.gamma,
    request.reference_total_temperature_K,
    request.gas_constant_J_kgK,
  )
  _density, velocity_u, velocity_v, static_pressure, _temperature, sound_speed = (
    _primitive_from_conservative(
      downstream_state,
      request.mixed_regime_request.control_section.samples[-1].gamma,
      request.gas_constant_J_kgK,
    )
  )
  reconstructed_mach = float(
    np.hypot(velocity_u, velocity_v) / max(sound_speed, 1.0e-12)
  )
  pressure_scale = max(sample.static_pressure_Pa, static_pressure, 1.0)
  if (
    abs(static_pressure - sample.static_pressure_Pa) / pressure_scale > 1.0e-8
    or abs(reconstructed_mach - sample.mach) > 1.0e-8
  ):
    raise RuntimeError(
      'audited shock-interface downstream sample is thermodynamically '
      'inconsistent with its total pressure, Mach number, and temperature'
    )
  ####
  return (
    tuple(
      downstream_state.copy()
      for _ in range(request.transverse_cell_count)
    ),
    interface,
  )
####


def _prepare_transonic_interface_profile_inlet(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  *,
  x_start: float,
  lower_ordinate: float,
  inlet_height: float,
  profile_override: MocTransonicShockInterfaceProfile | None = None,
) -> tuple[
  tuple[np.ndarray, ...],
  MocTransonicShockInterfaceProfile,
]:
  """Consume a verified spatially varying shock-interface inlet profile.

  This is a multi-face handoff into the coupled field.  The ordinary profile
  mode accepts only the original control-section inlet.  The distinct
  interior mode starts a new downstream field at the exact profile
  cross-section; it still never projects, clips, or replaces the profile.
  """

  profile = (
    request.transonic_shock_interface_profile
    if profile_override is None
    else profile_override
  )
  if profile is None:
    raise RuntimeError(
      'audited-shock-interface-profile mode requires a retained profile'
    )
  ####
  from exhaust_plume.validation.moc_transonic_interface import (
    measure_moc_transonic_shock_interface_profile,
  )

  profile_audit = measure_moc_transonic_shock_interface_profile(profile)
  if not profile_audit.converged:
    raise RuntimeError(
      'audited shock-interface profile failed its independent profile audit'
    )
  ####
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(profile.cross_section_x_m - x_start) > x_tolerance:
    if request.inlet_boundary_mode not in (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE,
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE,
    ):
      raise RuntimeError(
        'audited shock-interface profile is interior to the field; only an '
        'inlet-bound profile is accepted by this coupled-field tranche'
      )
    ####
    raise RuntimeError(
      'audited shock-interface profile cross-section does not match the '
      'interior downstream-field inlet'
    )
  ####
  if abs(profile.lower_ordinate_m - lower_ordinate) > y_tolerance:
    raise RuntimeError(
      'audited shock-interface profile lower ordinate does not match the '
      'coupled-field inlet'
    )
  ####
  if abs(profile.upper_ordinate_m - (lower_ordinate + inlet_height)) > y_tolerance:
    raise RuntimeError(
      'audited shock-interface profile upper ordinate does not match the '
      'coupled-field inlet'
    )
  ####
  if abs(np.sin(profile.interface_normal_angle_rad)) > 1.0e-8:
    raise RuntimeError(
      'audited shock-interface profile normal must be aligned with the '
      'vertical coupled-field inlet'
    )
  ####
  reference_sample = request.mixed_regime_request.control_section.samples[-1]
  if abs(profile.gamma - float(reference_sample.gamma)) > 1.0e-10:
    raise RuntimeError(
      'audited shock-interface profile gamma does not match the coupled inlet'
    )
  ####
  ordinates = np.asarray(
    [sample.point_m[1] for sample in profile.downstream_samples],
    dtype=float,
  )
  fields = {
    name: np.asarray(
      [getattr(sample, name) for sample in profile.downstream_samples],
      dtype=float,
    )
    for name in ('total_pressure_Pa', 'mach', 'flow_angle_rad')
  }
  inlet_states: list[np.ndarray] = []
  face_width = inlet_height / request.transverse_cell_count
  for index in range(request.transverse_cell_count):
    ordinate = lower_ordinate + (index + 0.5) * face_width
    total_pressure = float(np.interp(ordinate, ordinates, fields['total_pressure_Pa']))
    mach = float(np.interp(ordinate, ordinates, fields['mach']))
    flow_angle = float(np.interp(ordinate, ordinates, fields['flow_angle_rad']))
    inlet_states.append(
      _state_from_sample(
        total_pressure,
        mach,
        flow_angle,
        profile.gamma,
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
    )
  ####
  if len(inlet_states) != request.transverse_cell_count:
    raise RuntimeError(
      'audited shock-interface profile could not provide every coupled-field '
      'inlet face state'
    )
  ####
  return tuple(inlet_states), profile
####


def _prepare_physical_field_continuation_inlet(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  *,
  x_start: float,
  lower_ordinate: float,
  inlet_height: float,
) -> tuple[
  tuple[np.ndarray, ...],
  MocPhysicalFieldContinuationProfileResult,
]:
  """Consume an exact physical-field section without a second shock jump."""

  continuation = request.physical_field_continuation_profile
  if continuation is None:
    raise RuntimeError(
      'physical-field continuation mode requires a retained continuation result'
    )
  ####
  from exhaust_plume.validation.moc_field_continuation import (
    measure_moc_physical_field_continuation_profile,
  )

  audit = measure_moc_physical_field_continuation_profile(continuation)
  if not continuation.converged or not audit.converged:
    raise RuntimeError(
      'physical-field continuation inlet failed its independent field audit'
    )
  ####
  profile = continuation.profile
  shock_front_condition = request.physical_field_shock_front_condition
  if profile is None or shock_front_condition is None:
    raise RuntimeError(
      'physical-field continuation result retained no profile or shock-front '
      'condition'
    )
  ####
  coupled_profile = shock_front_condition.coupled_inlet_profile
  if coupled_profile is None:
    raise RuntimeError(
      'physical-field shock-front condition retained no complete coupled '
      'inlet profile'
    )
  ####
  profile = coupled_profile
  x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
  y_tolerance = max(1.0e-10, 1.0e-8 * max(abs(inlet_height), 1.0))
  if abs(profile.cross_section_x_m - x_start) > x_tolerance:
    raise RuntimeError(
      'physical-field continuation profile cross-section does not match the '
      'coupled-field inlet'
    )
  ####
  if abs(profile.lower_ordinate_m - lower_ordinate) > y_tolerance:
    raise RuntimeError(
      'physical-field continuation profile lower ordinate does not match the '
      'coupled-field inlet'
    )
  ####
  if abs(profile.upper_ordinate_m - (lower_ordinate + inlet_height)) > y_tolerance:
    raise RuntimeError(
      'physical-field continuation profile upper ordinate does not match the '
      'coupled-field inlet'
    )
  ####
  reference_sample = request.mixed_regime_request.control_section.samples[-1]
  if abs(profile.gamma - float(reference_sample.gamma)) > 1.0e-10:
    raise RuntimeError(
      'physical-field continuation profile gamma does not match the coupled '
      'inlet'
    )
  ####
  ordinates = np.asarray(
    [sample.point_m[1] for sample in profile.samples],
    dtype=float,
  )
  fields = {
    name: np.asarray(
      [getattr(sample, name) for sample in profile.samples],
      dtype=float,
    )
    for name in ('total_pressure_Pa', 'mach', 'flow_angle_rad')
  }
  inlet_states: list[np.ndarray] = []
  face_width = inlet_height / request.transverse_cell_count
  for index in range(request.transverse_cell_count):
    ordinate = lower_ordinate + (index + 0.5) * face_width
    inlet_states.append(
      _state_from_sample(
        float(np.interp(ordinate, ordinates, fields['total_pressure_Pa'])),
        float(np.interp(ordinate, ordinates, fields['mach'])),
        float(np.interp(ordinate, ordinates, fields['flow_angle_rad'])),
        profile.gamma,
        request.reference_total_temperature_K,
        request.gas_constant_J_kgK,
      )
    )
  ####
  if len(inlet_states) != request.transverse_cell_count:
    raise RuntimeError(
      'physical-field continuation profile could not provide every coupled '
      'inlet face state'
    )
  ####
  return tuple(inlet_states), continuation
####


def _interpolate_physical_field_ambient_neighbor(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  x_m: float,
  *,
  position_tolerance_m: float,
) -> tuple[float, float] | None:
  """Sample the exact ambient-neighbor path retained by the shock condition."""

  condition = request.physical_field_shock_front_condition
  if condition is None or condition.field is None:
    return None
  ####
  boundary = condition.field.ambient_boundary
  points = tuple(boundary.points_m)
  pressures = tuple(boundary.static_pressure_Pa)
  if len(points) != len(pressures) or len(points) < 2:
    return None
  ####
  if any(
    second[0] <= first[0] + position_tolerance_m
    for first, second in zip(points, points[1:])
  ):
    return None
  ####
  if (
    x_m < points[0][0] - position_tolerance_m
    or x_m > points[-1][0] + position_tolerance_m
  ):
    return None
  ####
  for index, (first_point, second_point) in enumerate(zip(points, points[1:])):
    if abs(x_m - first_point[0]) <= position_tolerance_m:
      return float(first_point[1]), float(pressures[index])
    ####
    if x_m <= second_point[0] + position_tolerance_m:
      span = second_point[0] - first_point[0]
      if span <= position_tolerance_m:
        return None
      ####
      fraction = min(max((x_m - first_point[0]) / span, 0.0), 1.0)
      return (
        float(first_point[1] + fraction * (second_point[1] - first_point[1])),
        float(
          pressures[index]
          + fraction * (pressures[index + 1] - pressures[index])
        ),
      )
    ####
  ####
  if abs(x_m - points[-1][0]) <= position_tolerance_m:
    return float(points[-1][1]), float(pressures[-1])
  ####
  return None
####


def _derive_physical_field_neighbor_profiles(
  request: MocReflectedDomainCoupledEulerFreeBoundaryRequest,
  x_stations: np.ndarray,
  *,
  lower_ordinate: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
  """Derive aligned pressure and geometry targets from the exact field path."""

  tolerance = max(1.0e-10, 1.0e-8 * max(abs(float(x_stations[0])), 1.0))
  samples = tuple(
    _interpolate_physical_field_ambient_neighbor(
      request,
      float(x_value),
      position_tolerance_m=tolerance,
    )
    for x_value in x_stations
  )
  if any(sample is None for sample in samples):
    raise RuntimeError(
      'solver-owned physical-field ambient-neighbor path does not cover the '
      'complete coupled downstream window; no extrapolation was attempted'
    )
  ####
  geometry = tuple(float(sample[0]) for sample in samples if sample is not None)
  pressures = tuple(float(sample[1]) for sample in samples if sample is not None)
  if any(ordinate <= lower_ordinate for ordinate in geometry):
    raise RuntimeError(
      'solver-owned physical-field ambient-neighbor path must remain above '
      'the coupled lower ordinate'
    )
  ####
  return pressures, geometry
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
  lower_ordinate: float,
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
  transonic_shock_interface: MocTransonicShockInterfaceResult | None = None,
  transonic_shock_interface_profile: MocTransonicShockInterfaceProfile | None = None,
  transonic_shock_interface_field_placement: (
    MocTransonicShockInterfaceFieldPlacementResult | None
  ) = None,
  physical_field_continuation_profile: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None,
  physical_field_shock_front_condition: (
    MocPhysicalFieldShockFrontConditionResult | None
  ) = None,
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
  consumed_inlet_states = _consumed_inlet_boundary_states(
    states,
    free_boundary_heights,
    lower_ordinate,
    request,
    gamma,
    gas_constant,
    inlet_override_states,
  )
  inlet_boundary_states = tuple(
    tuple(float(value) for value in state)
    for state in consumed_inlet_states
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
  pressure_targets = _free_boundary_pressure_targets(request)
  channel_validity = {
    name: bool(maxima[index] <= request.euler_residual_tolerance)
    for index, name in enumerate(_CHANNEL_NAMES)
  }
  pressure_budget = (
    assess_reflected_domain_coupled_euler_subsonic_pressure_budget(request)
  )
  pressure_profile_compatibility = (
    assess_reflected_domain_coupled_euler_pressure_profile_compatibility(request)
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
  transonic_frontier_compatibility = (
    assess_reflected_domain_coupled_euler_transonic_frontier_compatibility(
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
        free_boundary_heights + lower_ordinate,
        strict=True,
      )
    ),
    free_boundary_adjacent_static_pressure_Pa=tuple(
      float(value) for value in top_pressures
    ),
    residual_history=tuple(residual_history),
    shape_residual_history_m=tuple(shape_residual_history),
    inlet_boundary_conservative_states_by_face=inlet_boundary_states,
    free_boundary_pressure_residuals_Pa=tuple(
      float(abs(value - target))
      for value, target in zip(top_pressures, pressure_targets, strict=True)
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
      np.max(np.abs(top_pressures - pressure_targets))
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
    free_boundary_pressure_profile_compatibility=(
      pressure_profile_compatibility
    ),
    transonic_transition=transonic_transition,
    transonic_transition_audit=transonic_transition_audit,
    transonic_shock_geometry=transonic_shock_geometry,
    transonic_shock_geometry_audit=transonic_shock_geometry_audit,
    transonic_shock_interface=transonic_shock_interface,
    transonic_shock_interface_consumed=transonic_shock_interface is not None,
    transonic_shock_interface_profile=transonic_shock_interface_profile,
    transonic_shock_interface_profile_consumed=(
      transonic_shock_interface_profile is not None
    ),
    transonic_shock_interface_field_placement=(
      transonic_shock_interface_field_placement
    ),
    transonic_shock_interface_field_placement_consumed=(
      transonic_shock_interface_field_placement is not None
    ),
    physical_field_continuation_profile=physical_field_continuation_profile,
    physical_field_continuation_profile_consumed=(
      physical_field_continuation_profile is not None
    ),
    physical_field_shock_front_condition=physical_field_shock_front_condition,
    physical_field_shock_front_condition_consumed=(
      physical_field_shock_front_condition is not None
    ),
    free_boundary_pressure_profile_consumed=(
      request.free_boundary_pressure_profile_Pa is not None
    ),
    free_boundary_geometry_profile_consumed=(
      request.free_boundary_geometry_profile_y_m is not None
    ),
    inlet_boundary_states_consumed=True,
    transonic_frontier_compatibility=transonic_frontier_compatibility,
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
      request.free_boundary_pressure_profile_Pa,
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
  solver_owned_placement = (
    request.transonic_shock_interface_field_placement
    if request.inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE
    else None
  )
  effective_profile = request.transonic_shock_interface_profile
  physical_field_continuation = request.physical_field_continuation_profile
  physical_field_shock_front_condition = (
    request.physical_field_shock_front_condition
  )
  if solver_owned_placement is not None:
    try:
      from exhaust_plume.validation.moc_transonic_interface import (
        measure_moc_transonic_shock_interface_field_placement,
      )

      placement_audit = measure_moc_transonic_shock_interface_field_placement(
        solver_owned_placement
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      placement_audit = None
    ####
    if (
      not solver_owned_placement.converged
      or placement_audit is None
      or not placement_audit.converged
      or not placement_audit.full_field_cross_section_verified
      or solver_owned_placement.profile is None
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_SHOCK_INTERFACE_PLACEMENT_FAILURE,
        'solver-owned interior shock-interface placement must pass its '
        'independent field/profile audit and span the complete retained '
        'field cross-section before coupled free-boundary consumption',
        request,
      )
    ####
    effective_profile = solver_owned_placement.profile
  ####
  if request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    if (
      physical_field_continuation is None
      or not physical_field_continuation.converged
      or physical_field_continuation.profile is None
      or physical_field_shock_front_condition is None
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE,
        'solver-owned physical-field continuation requires a converged exact '
        'shock-front condition before coupled free-boundary consumption',
        request,
      )
    ####
    try:
      from exhaust_plume.validation.moc_physical_field_shock_front import (
        measure_moc_physical_field_shock_front_condition,
      )

      shock_front_audit = measure_moc_physical_field_shock_front_condition(
        physical_field_shock_front_condition
      )
    except (ArithmeticError, FloatingPointError, TypeError, ValueError):
      shock_front_audit = None
    ####
    if (
      not physical_field_shock_front_condition.converged
      or shock_front_audit is None
      or not shock_front_audit.converged
      or physical_field_shock_front_condition.continuation_profile
      != physical_field_continuation
      or physical_field_shock_front_condition.coupled_inlet_profile is None
      or not physical_field_shock_front_condition.coupled_inlet_profile_verified
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE,
        'solver-owned physical-field shock-front condition failed its '
        'independent audit or does not retain the exact continuation result',
        request,
      )
    ####
    continuation_profile = physical_field_continuation.profile
    coupled_inlet_profile = physical_field_shock_front_condition.coupled_inlet_profile
    if continuation_profile is None or coupled_inlet_profile is None:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE,
        'solver-owned physical-field shock-front condition retained no '
        'complete coupled inlet profile',
        request,
      )
    ####
    x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
    if continuation_profile.cross_section_x_m <= x_start + x_tolerance:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_PHYSICAL_FIELD_CONTINUATION_FAILURE,
        'solver-owned physical-field continuation must start strictly '
        'downstream of the upstream control section',
        request,
      )
    ####
    x_start = coupled_inlet_profile.cross_section_x_m
    lower_ordinate = coupled_inlet_profile.lower_ordinate_m
    inlet_height = (
      coupled_inlet_profile.upper_ordinate_m - lower_ordinate
    )
  ####
  if request.inlet_boundary_mode in (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE,
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE,
  ):
    profile = effective_profile
    if profile is None:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_SHOCK_INTERFACE_PROFILE_FAILURE,
        'interior shock-interface-profile mode requires a retained profile',
        request,
      )
    ####
    x_tolerance = max(1.0e-10, 1.0e-8 * max(abs(x_start), 1.0))
    if profile.cross_section_x_m <= x_start + x_tolerance:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_SHOCK_INTERFACE_PROFILE_FAILURE,
        'interior shock-interface profile must start strictly downstream of '
        'the upstream control section',
        request,
      )
    ####
    x_start = profile.cross_section_x_m
    lower_ordinate = profile.lower_ordinate_m
    inlet_height = profile.upper_ordinate_m - lower_ordinate
  ####
  if request.reference_total_temperature_K <= 0.0:
    return _failure(
      MocReflectedDomainCoupledEulerFreeBoundaryStatus.THERMODYNAMIC_FAILURE,
      'reference total temperature must be positive',
      request,
    )
  ####
  if request.inlet_boundary_mode in (
    MocReflectedDomainCoupledEulerInletBoundaryMode.FULL_STATE_RUSANOV,
    MocReflectedDomainCoupledEulerInletBoundaryMode.SUBSONIC_CHARACTERISTIC,
  ):
    transition = assess_reflected_domain_coupled_euler_transonic_transition(
      request
    )
    transition_audit = measure_moc_transonic_transition(transition)
    frontier_compatibility = (
      assess_reflected_domain_coupled_euler_transonic_frontier_compatibility(
        request,
        transition,
      )
    )
    control_section_compatibility = (
      assess_reflected_domain_coupled_euler_control_section_compatibility(
        request,
        transition,
      )
    )
    if (
      transition.transition_required
      and frontier_compatibility.status
      is not MocReflectedDomainCoupledEulerTransonicFrontierCompatibilityStatus
      .MATCHED_FRONTIER_STATE
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .TRANSONIC_FRONTIER_FAILURE,
        'coupled Euler field requires a placed transonic interface, but the '
        'retained global Euler frontier does not contain the scalar required '
        f'upstream state ({frontier_compatibility.status.value}); no field '
        'iteration or lower-fidelity fallback was attempted',
        request,
        subsonic_pressure_budget=(
          assess_reflected_domain_coupled_euler_subsonic_pressure_budget(
            request
          )
        ),
        transonic_transition=transition,
        transonic_transition_audit=transition_audit,
        transonic_frontier_compatibility=frontier_compatibility,
        control_section_compatibility=control_section_compatibility,
      )
    ####
  ####
  inlet_override_states: tuple[np.ndarray, ...] | None = None
  transonic_shock_geometry: MocTransonicShockGeometryResult | None = None
  transonic_shock_geometry_audit: MocTransonicShockGeometryAudit | None = None
  transonic_shock_interface: MocTransonicShockInterfaceResult | None = None
  transonic_shock_interface_profile: MocTransonicShockInterfaceProfile | None = None
  physical_field_continuation_result: (
    MocPhysicalFieldContinuationProfileResult | None
  ) = None
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
  elif (
    request.inlet_boundary_mode
    is MocReflectedDomainCoupledEulerInletBoundaryMode.AUDITED_SHOCK_INTERFACE
  ):
    try:
      inlet_override_states, transonic_shock_interface = (
        _prepare_transonic_interface_inlet(
          request,
          x_start=x_start,
          lower_ordinate=lower_ordinate,
          inlet_height=inlet_height,
        )
      )
    except RuntimeError as error:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.INLET_SHOCK_INTERFACE_FAILURE,
        str(error),
        request,
      )
    ####
  elif request.inlet_boundary_mode in (
    MocReflectedDomainCoupledEulerInletBoundaryMode.AUDITED_SHOCK_INTERFACE_PROFILE,
    MocReflectedDomainCoupledEulerInletBoundaryMode.AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE,
    MocReflectedDomainCoupledEulerInletBoundaryMode.SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE,
  ):
    try:
      inlet_override_states, transonic_shock_interface_profile = (
        _prepare_transonic_interface_profile_inlet(
          request,
          x_start=x_start,
          lower_ordinate=lower_ordinate,
          inlet_height=inlet_height,
          profile_override=effective_profile,
        )
      )
    except RuntimeError as error:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_SHOCK_INTERFACE_PROFILE_FAILURE,
        str(error),
        request,
      )
    ####
  elif request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ):
    try:
      inlet_override_states, physical_field_continuation_result = (
        _prepare_physical_field_continuation_inlet(
          request,
          x_start=x_start,
          lower_ordinate=lower_ordinate,
          inlet_height=inlet_height,
        )
      )
    except RuntimeError as error:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_PHYSICAL_FIELD_CONTINUATION_FAILURE,
        str(error),
        request,
      )
    ####
  ####
  downstream_length = request.effective_downstream_length_m
  x_stations = np.linspace(
    x_start,
    x_start + downstream_length,
    request.axial_cell_count + 1,
  )
  if request.inlet_boundary_mode is (
    MocReflectedDomainCoupledEulerInletBoundaryMode
    .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE
  ) and (
    request.free_boundary_pressure_profile_Pa is None
    or request.free_boundary_geometry_profile_y_m is None
  ):
    pressure_x_stations = 0.5 * (x_stations[:-1] + x_stations[1:])
    neighbor_pressures: tuple[float, ...] | None = None
    neighbor_geometry: tuple[float, ...] | None = None
    try:
      if request.free_boundary_pressure_profile_Pa is None:
        neighbor_pressures, _ = _derive_physical_field_neighbor_profiles(
          request,
          pressure_x_stations,
          lower_ordinate=lower_ordinate,
        )
      ####
      if request.free_boundary_geometry_profile_y_m is None:
        _, neighbor_geometry = _derive_physical_field_neighbor_profiles(
          request,
          x_stations,
          lower_ordinate=lower_ordinate,
        )
      ####
    except RuntimeError as error:
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus
        .INLET_PHYSICAL_FIELD_SHOCK_FRONT_CONDITION_FAILURE,
        str(error),
        request,
      )
    ####
    request_updates: dict[str, Any] = {}
    if request.free_boundary_pressure_profile_Pa is None:
      assert neighbor_pressures is not None
      request_updates.update(
        free_boundary_pressure_profile_Pa=neighbor_pressures,
        free_boundary_pressure_profile_x_stations_m=tuple(
          float(value) for value in pressure_x_stations
        ),
        free_boundary_pressure_profile_source=(
          PHYSICAL_FIELD_AMBIENT_NEIGHBOR_PRESSURE_PROFILE_SOURCE
        ),
      )
    ####
    if request.free_boundary_geometry_profile_y_m is None:
      assert neighbor_geometry is not None
      request_updates.update(
        free_boundary_geometry_profile_y_m=neighbor_geometry,
        free_boundary_geometry_profile_x_stations_m=tuple(
          float(value) for value in x_stations
        ),
        free_boundary_geometry_profile_source=(
          PHYSICAL_FIELD_AMBIENT_NEIGHBOR_GEOMETRY_PROFILE_SOURCE
        ),
        free_boundary_geometry_profile_lower_ordinate_m=lower_ordinate,
      )
    ####
    request = replace(request, **request_updates)
  ####
  if request.free_boundary_pressure_profile_x_stations_m is not None:
    expected_profile_x = 0.5 * (x_stations[:-1] + x_stations[1:])
    supplied_profile_x = np.asarray(
      request.free_boundary_pressure_profile_x_stations_m,
      dtype=float,
    )
    if not np.allclose(
      supplied_profile_x,
      expected_profile_x,
      rtol=1.0e-9,
      atol=1.0e-10,
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
        'free-boundary pressure profile coordinates must match the coupled '
        'cell-column centers; no spatial regridding or extrapolation was used',
        request,
      )
    ####
  ####
  geometry_targets = _free_boundary_geometry_targets(request)
  if request.free_boundary_geometry_profile_lower_ordinate_m is not None:
    if not np.isclose(
      request.free_boundary_geometry_profile_lower_ordinate_m,
      lower_ordinate,
      rtol=1.0e-9,
      atol=1.0e-10,
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
        'free-boundary geometry profile lower ordinate must match the '
        'coupled-field inlet frame; no frame translation was inferred',
        request,
      )
    ####
  ####
  if request.free_boundary_geometry_profile_x_stations_m is not None:
    supplied_geometry_x = np.asarray(
      request.free_boundary_geometry_profile_x_stations_m,
      dtype=float,
    )
    if not np.allclose(
      supplied_geometry_x,
      x_stations,
      rtol=1.0e-9,
      atol=1.0e-10,
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
        'free-boundary geometry profile coordinates must match the coupled '
        'boundary nodes; no spatial regridding or extrapolation was used',
        request,
      )
    ####
    if geometry_targets is None or len(geometry_targets) != len(x_stations):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
        'free-boundary geometry profile must retain one ordinate per coupled '
        'boundary node',
        request,
      )
    ####
    if np.any(geometry_targets <= lower_ordinate):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
        'free-boundary geometry profile must remain strictly above the '
        'centerline ordinate',
        request,
      )
    ####
    geometry_inlet_height = float(geometry_targets[0] - lower_ordinate)
    if not np.isclose(
      geometry_inlet_height,
      inlet_height,
      rtol=1.0e-9,
      atol=max(1.0e-10, request.shape_convergence_tolerance),
    ):
      return _failure(
        MocReflectedDomainCoupledEulerFreeBoundaryStatus.CONTROL_SECTION_FAILURE,
        'free-boundary geometry profile inlet ordinate must match the exact '
        'coupled-field inlet section; no inlet seam correction was inferred',
        request,
      )
    ####
  ####
  pressure_targets = _free_boundary_pressure_targets(request)
  # An interior shock-interface profile starts a new downstream field at the
  # retained cross-section.  The upstream mixed-regime reference's outlet
  # height belongs to its own control-section origin and may be unrelated to
  # the profile height.  Reusing it here can collapse the first mesh column
  # before any Euler iteration has run.  Preserve the exact handoff geometry
  # for the first downstream boundary instead.
  initial_boundary_height = (
    inlet_height
    if request.inlet_boundary_mode in (
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .AUDITED_INTERIOR_SHOCK_INTERFACE_PROFILE,
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_INTERIOR_SHOCK_INTERFACE_PROFILE,
      MocReflectedDomainCoupledEulerInletBoundaryMode
      .SOLVER_OWNED_PHYSICAL_FIELD_CONTINUATION_PROFILE,
    )
    else request.mixed_regime_request.initial_outlet_height_m
  )
  free_boundary_heights = np.full(
    request.axial_cell_count + 1,
    initial_boundary_height,
    dtype=float,
  )
  free_boundary_heights[0] = inlet_height
  if geometry_targets is not None:
    free_boundary_heights = geometry_targets - lower_ordinate
    free_boundary_heights[0] = inlet_height
  ####
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
    dx = downstream_length / request.axial_cell_count
    for i in range(request.axial_cell_count):
      top_cell = states[i, request.transverse_cell_count - 1]
      _rho, u, v, pressure, _temperature, _sound_speed = (
        _primitive_from_conservative(top_cell, gamma, request.gas_constant_J_kgK)
      )
      pressure_error = (
        pressure - pressure_targets[i]
      ) / max(pressure, pressure_targets[i])
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
    if geometry_targets is not None:
      # A retained geometry profile is an explicit boundary condition, not a
      # diagnostic displacement.  Consume the exact aligned ordinates after
      # the local pressure/tangency predictor has been evaluated so the
      # residual report still exposes the cost of replacing that predictor.
      new_heights[1:] = geometry_targets[1:] - lower_ordinate
    ####
    shape_residual = float(np.max(np.abs(new_heights - free_boundary_heights)))
    shape_residual_history.append(shape_residual)
    speeds = np.sqrt(
      np.asarray([_primitive_from_conservative(state, gamma, request.gas_constant_J_kgK)[1] for state in states.reshape((-1, 4))]) ** 2
      + np.asarray([_primitive_from_conservative(state, gamma, request.gas_constant_J_kgK)[2] for state in states.reshape((-1, 4))]) ** 2
    )
    maximum_speed = max(float(np.max(speeds)), 1.0e-12)
    normal_fraction = float(np.max(np.abs(final_top_normal_velocities))) / maximum_speed
    boundary_verified = bool(
      np.all(
        np.abs(final_top_pressures - pressure_targets)
        <= request.free_boundary_pressure_tolerance_fraction * pressure_targets
      )
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
    lower_ordinate,
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
    transonic_shock_interface,
    transonic_shock_interface_profile,
    solver_owned_placement,
    physical_field_continuation_result,
    request.physical_field_shock_front_condition,
  )
####
